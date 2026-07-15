'use client';

import { useRef, useState } from 'react';
import { startRecording, type RecorderHandle } from '@/lib/recorder';
import { transcribeAudio } from '@/lib/api';
import { Icon } from './icons';

type Phase = 'idle' | 'recording' | 'transcribing' | 'review';

export function VoiceRecorder({
  onTranscript,
  disabled,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [heard, setHeard] = useState('');
  const handleRef = useRef<RecorderHandle | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopTimer() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }

  async function begin() {
    setError(null);
    setHeard('');
    try {
      handleRef.current = await startRecording();
      setSeconds(0);
      setPhase('recording');
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      setError('Microphone blocked. Allow mic access, or just type below.');
    }
  }

  async function finish() {
    if (!handleRef.current) return;
    stopTimer();
    setPhase('transcribing');
    try {
      const wav = await handleRef.current.stop();
      const { text } = await transcribeAudio(wav);
      // Fill the field now so she can also edit inline, but hold a review step
      // so a non-technical seller explicitly confirms (or re-records) before running.
      onTranscript(text);
      setHeard(text);
      setPhase('review');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Transcription failed. Please try again.');
      setPhase('idle');
    } finally {
      handleRef.current = null;
    }
  }

  // Very short transcripts usually mean noise drowned the speech — nudge a re-record.
  const looksWeak = heard.trim().length > 0 && heard.trim().length < 12;
  const mmss = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

  return (
    <div className="mt-2">
      {phase === 'idle' && (
        <button
          type="button"
          onClick={begin}
          disabled={disabled}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-4 py-2.5 text-[13px] font-semibold text-brand-700 transition hover:bg-brand-100 disabled:opacity-50"
        >
          <MicIcon /> Record a voice note
        </button>
      )}

      {phase === 'recording' && (
        <button
          type="button"
          onClick={finish}
          className="flex w-full items-center justify-center gap-2.5 rounded-xl bg-brand px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-brand-600"
        >
          <span className="flex h-2.5 w-2.5 animate-pulse rounded-full bg-white" />
          Recording {mmss} — tap to stop
        </button>
      )}

      {phase === 'transcribing' && (
        <div className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-line bg-canvas px-4 py-2.5 text-[13px] font-semibold text-ink-2">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand-200 border-t-brand" />
          Transcribing your voice…
        </div>
      )}

      {phase === 'review' && (
        <div className="rounded-xl border border-brand-200 bg-brand-50/60 p-3.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-700">
            We heard
          </p>
          <p className="mt-1 text-[13.5px] leading-relaxed text-ink">“{heard}”</p>
          {looksWeak && (
            <p className="mt-2 rounded-lg bg-warn-bg px-2.5 py-1.5 text-[11px] font-medium text-warn">
              That sounded very short — background noise may have cut in. Please re-record in a
              quieter spot.
            </p>
          )}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setPhase('idle')}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-[13px] font-semibold text-white transition hover:bg-brand-600"
            >
              <Icon name="check" size={15} /> Sounds right
            </button>
            <button
              type="button"
              onClick={begin}
              className="flex items-center gap-1.5 rounded-lg border border-brand-200 bg-surface px-3 py-2 text-[13px] font-semibold text-brand-700 transition hover:bg-brand-100"
            >
              <MicIcon /> Re-record
            </button>
          </div>
          <p className="mt-2 text-[11px] text-muted">You can also edit the text below directly.</p>
        </div>
      )}

      {error && <p className="mt-2 text-[12px] text-danger">{error}</p>}
    </div>
  );
}

function MicIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Z"
        fill="currentColor"
      />
      <path
        d="M19 11a7 7 0 0 1-14 0M12 18v3"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
