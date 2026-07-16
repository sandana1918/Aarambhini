/**
 * The signed-in seller, held in localStorage.
 *
 * The token is a signed bearer token from POST /sessions — see backend/auth.py
 * for what it does and does not prove. localStorage means any XSS on this page
 * can read it; that is an accepted trade for now, and the short server-side TTL
 * limits the blast radius.
 */
const KEY = 'aarambhini.session';

export type Session = {
  token: string;
  sellerId: string;
  name: string;
};

export function loadSession(): Session | null {
  // Guard for the server render pass, where localStorage does not exist.
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null; // unreadable or disabled storage — treat as signed out
  }
}

export function saveSession(session: Session): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    /* storage disabled — the session just won't survive a reload */
  }
}

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing useful to do */
  }
}
