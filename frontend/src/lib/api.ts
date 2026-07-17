import type { RunResult } from './types';
import { clearSession, loadSession, saveSession, type Session } from './session';

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

/** Bearer header for the current session, or {} when signed out. */
function authHeaders(): Record<string, string> {
  const session = loadSession();
  return session ? { Authorization: `Bearer ${session.token}` } : {};
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* keep status text */
    }
    // An expired or rejected token is dead weight — drop it so the UI falls
    // back to the sign-in prompt instead of retrying with it forever.
    if (res.status === 401) clearSession();
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

type SessionResponse = { token: string; seller_id: string; name: string };

function keep(data: SessionResponse): Session {
  const session: Session = { token: data.token, sellerId: data.seller_id, name: data.name };
  saveSession(session);
  return session;
}

export async function logIn(phone: string, password: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, password }),
  });
  return keep(await json<SessionResponse>(res));
}

export type RegisterInput = {
  name: string;
  phone: string;
  password: string;
  preferred_language: string;
  shg_name?: string;
};

/** Register and land signed in — no second trip through the login form. */
export async function registerSeller(input: RegisterInput): Promise<Session> {
  const res = await fetch(`${API_BASE}/sellers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...input, shg_name: input.shg_name || null }),
  });
  return keep(await json<SessionResponse>(res));
}

/** Confirm a stored session is still valid server-side. Null if not. */
export async function fetchMe(): Promise<{ seller_id: string; name: string } | null> {
  if (!loadSession()) return null;
  try {
    const res = await fetch(`${API_BASE}/sessions/me`, { headers: authHeaders() });
    return await json<{ seller_id: string; name: string }>(res);
  } catch {
    return null; // json() already cleared the session on a 401
  }
}

export async function runListing(input: {
  voiceText: string;
  marginPct: number;
  photo?: File | null;
}): Promise<RunResult> {
  const fd = new FormData();
  fd.append('voice_text', input.voiceText);
  fd.append('desired_margin_pct', String(input.marginPct));
  if (input.photo) fd.append('photo', input.photo);

  const res = await fetch(`${API_BASE}/listings/run`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  });
  return json<RunResult>(res);
}

export async function transcribeAudio(audio: Blob): Promise<{ text: string }> {
  const fd = new FormData();
  // Filename extension hints the server/Gemini at the container; WAV is universal.
  fd.append('audio', audio, 'voice-note.wav');
  const res = await fetch(`${API_BASE}/listings/transcribe`, { method: 'POST', body: fd });
  return json<{ text: string }>(res);
}

export type ApprovalEdits = {
  price?: number;
  title?: string;
  description?: string;
  attributes?: Record<string, string>;
};

export async function clarifyListing(
  id: string,
  answers: { cost_price_inr?: number; category?: string },
): Promise<RunResult> {
  const res = await fetch(`${API_BASE}/listings/${id}/clarify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(answers),
  });
  return json<RunResult>(res);
}

export async function runListingStream(
  input: { voiceText: string; marginPct: number; photo?: File | null },
  onStep: (agent: string) => void,
): Promise<RunResult> {
  const fd = new FormData();
  fd.append('voice_text', input.voiceText);
  fd.append('desired_margin_pct', String(input.marginPct));
  if (input.photo) fd.append('photo', input.photo);

  const res = await fetch(`${API_BASE}/listings/run/stream`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  });
  if (res.status === 401) clearSession();
  if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: RunResult | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() ?? ''; // keep the incomplete tail
    for (const frame of frames) {
      const ev = frame.match(/^event: (.+)$/m)?.[1]?.trim();
      const dataLine = frame.match(/^data: (.+)$/m)?.[1];
      if (!ev || !dataLine) continue;
      const data = JSON.parse(dataLine);
      if (ev === 'step') onStep(data.agent);
      else if (ev === 'done') result = data as RunResult;
      else if (ev === 'error') throw new Error(data.detail || 'Streaming failed.');
    }
  }
  if (!result) throw new Error('The run ended without a result.');
  return result;
}

export async function approveListing(
  id: string,
  approved: boolean,
  notes?: string,
  edits?: ApprovalEdits,
): Promise<{ id: string; status: string }> {
  const res = await fetch(`${API_BASE}/listings/${id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ approved, notes: notes ?? null, edits: edits ?? null }),
  });
  return json(res);
}

export type PendingField = {
  key: string;
  label: string;
  type: string;
  options: string[];
  required: boolean;
};

/** The details still missing, with the key + options needed to answer them. */
export async function getPendingAttributes(
  id: string,
): Promise<{ category: string | null; fields: PendingField[] }> {
  const res = await fetch(`${API_BASE}/listings/${id}/pending-attributes`, {
    headers: authHeaders(),
  });
  return json(res);
}

/** Her spoken answer -> a value this field accepts. Throws if it can't match. */
export async function resolveAttribute(
  id: string,
  key: string,
  spokenText: string,
): Promise<{ key: string; value: string; provider: string }> {
  const res = await fetch(`${API_BASE}/listings/${id}/attribute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ key, spoken_text: spokenText }),
  });
  return json(res);
}

export type Translation = { original: string; text: string; provider: string };

/** English -> her language, for reading only. Defaults to her registered language. */
export async function translateTexts(
  texts: string[],
  to?: string,
): Promise<{ language: string; translations: Translation[] }> {
  const res = await fetch(`${API_BASE}/language/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ texts, to: to ?? null }),
  });
  return json(res);
}

/**
 * Her language -> a playable audio URL, or null when speech isn't available.
 * Null is normal (404) — the caller hides the button rather than showing a
 * broken one. Caller owns revokeObjectURL.
 */
export async function speakUrl(text: string, lang?: string): Promise<string | null> {
  const res = await fetch(`${API_BASE}/language/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ text, lang: lang ?? null }),
  });
  if (!res.ok) {
    if (res.status === 401) clearSession();
    return null;
  }
  return URL.createObjectURL(await res.blob());
}

export async function getHealth(): Promise<{ status: string; db: string }> {
  const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
  return json(res);
}
