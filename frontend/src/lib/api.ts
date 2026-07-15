import type { RunResult } from './types';

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
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

  const res = await fetch(`${API_BASE}/listings/run`, { method: 'POST', body: fd });
  return json<RunResult>(res);
}

export async function transcribeAudio(audio: Blob): Promise<{ text: string }> {
  const fd = new FormData();
  // Filename extension hints the server/Gemini at the container; WAV is universal.
  fd.append('audio', audio, 'voice-note.wav');
  const res = await fetch(`${API_BASE}/listings/transcribe`, { method: 'POST', body: fd });
  return json<{ text: string }>(res);
}

export async function approveListing(
  id: string,
  approved: boolean,
  notes?: string,
): Promise<{ id: string; status: string }> {
  const res = await fetch(`${API_BASE}/listings/${id}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, notes: notes ?? null }),
  });
  return json(res);
}

export async function getHealth(): Promise<{ status: string; db: string }> {
  const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
  return json(res);
}
