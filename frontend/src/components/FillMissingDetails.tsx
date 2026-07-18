'use client';

import { useEffect, useState } from 'react';
import { Icon } from '@/components/icons';
import { VoiceRecorder } from '@/components/VoiceRecorder';
import { spokenOrPreferred } from '@/components/ReviewInHerLanguage';
import {
  getPendingAttributes,
  resolveAttribute,
  speakUrl,
  translateTexts,
  type PendingField,
} from '@/lib/api';

/**
 * The missing details, answerable — by voice, in her language.
 *
 * The listing used to tell her "Add these details before publishing: Age Group"
 * and give her nowhere to put the answer, in English, for a field she would
 * naturally just say out loud. Now each one opens: the question in her
 * language, a Listen button, tappable options where the marketplace fixes them,
 * and the same recorder she used for the voice note.
 *
 * Answers do NOT write to the listing here. The graph is paused at the approval
 * interrupt and its checkpoint is the source of truth, so they ride in with
 * edits.attributes when she publishes.
 */

function ListenButton({ text, lang }: { text: string; lang: string }) {
  const [busy, setBusy] = useState(false);
  const [dead, setDead] = useState(false);

  async function play() {
    if (busy) return;
    setBusy(true);
    try {
      const url = await speakUrl(text, lang);
      if (!url) {
        setDead(true);
        return;
      }
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch {
      setDead(true);
    } finally {
      setBusy(false);
    }
  }

  if (dead) return null;
  return (
    <button
      type="button"
      onClick={play}
      disabled={busy}
      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-brand-200 bg-surface px-2 py-1 text-[11px] font-semibold text-brand transition hover:bg-brand-50 disabled:opacity-50"
    >
      <Icon name={busy ? 'refresh' : 'ear'} size={11} /> {busy ? '…' : 'Listen'}
    </button>
  );
}

export function FillMissingDetails({
  listingId,
  missingLabels,
  filled,
  onFilled,
  detectedLanguage,
}: {
  listingId: string;
  missingLabels: string[];
  filled: Record<string, string>;
  onFilled: (key: string, value: string) => void;
  /** Ask in the language she just spoke, not the one she registered with. */
  detectedLanguage?: string | null;
}) {
  const [fields, setFields] = useState<PendingField[] | null>(null);
  const [open, setOpen] = useState<PendingField | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState('');
  // English question -> her language, keyed by the English so lookups are direct.
  const [lang, setLang] = useState('en');
  const [phrases, setPhrases] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const r = await getPendingAttributes(listingId);
        // Trust the backend's list as-is. It already includes both the
        // required-missing fields AND unset optional ones like "dimensions" —
        // which matters because Wapsi's confirmation question ("confirm the
        // exact height and width") has no chip to answer unless dimensions is
        // offered here too. Re-filtering down to missingLabels (required-only)
        // silently dropped it, leaving her question unanswerable.
        if (active) setFields(r.fields);
      } catch {
        if (active) setFields([]); // stay quiet rather than block the approval
      }
    })();
    return () => {
      active = false;
    };
  }, [listingId, missingLabels]);

  // Translate the open question (and its options) into her language.
  useEffect(() => {
    if (!open) return;
    let active = true;
    (async () => {
      const texts = [questionFor(open), ...open.options];
      try {
        const r = await translateTexts(texts, spokenOrPreferred(detectedLanguage));
        if (!active) return;
        setLang(r.language);
        const map: Record<string, string> = {};
        for (const t of r.translations) {
          if (t.provider !== 'none') map[t.original] = t.text;
        }
        setPhrases(map);
      } catch {
        /* English is already on screen — nothing to undo */
      }
    })();
    return () => {
      active = false;
    };
  }, [open, detectedLanguage]);

  async function submit(spoken: string) {
    if (!open || !spoken.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await resolveAttribute(listingId, open.key, spoken);
      onFilled(open.key, r.value);
      setOpen(null);
      setTyped('');
      setPhrases({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not use that answer.');
    } finally {
      setBusy(false);
    }
  }

  if (!fields || fields.length === 0) return null;

  const pending = fields.filter((f) => !filled[f.key]);
  const done = fields.filter((f) => filled[f.key]);
  // Required-missing actually blocks a good listing; an optional field being
  // asked about (dimensions, prompted by Wapsi) does not — so it gets a
  // calmer style rather than the same warning colour, which would otherwise
  // read as "you must fill this" for something she's free to skip.
  const requiredPending = pending.filter((f) => f.required).length;

  return (
    <div className="mt-4 rounded-xl border border-line bg-canvas p-3.5">
      <p className="text-[12.5px] font-bold text-ink">
        {requiredPending
          ? 'Add these details before publishing'
          : pending.length
            ? 'A couple of optional details'
            : 'All details added'}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-muted">
        Tap one and just say the answer — the same as your voice note.
      </p>

      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {pending.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => {
              setOpen(f);
              setError(null);
              setPhrases({});
            }}
            className={`rounded-full border px-2.5 py-1 text-[11.5px] font-semibold transition ${
              open?.key === f.key
                ? 'border-brand bg-brand-50 text-brand-700'
                : f.required
                  ? 'border-saffron/50 bg-warn-bg text-warn hover:border-brand-300'
                  : 'border-line bg-surface text-ink-2 hover:border-brand-300'
            }`}
          >
            {f.label} {f.required ? '' : '(optional) '}+
          </button>
        ))}
        {done.map((f) => (
          // Clickable so she can redo it — voice mis-hears ("No. of
          // Compartments: Paint" when she said "plain"), and a green tick she
          // can't undo is worse than no tick. Tapping re-opens the recorder.
          <button
            key={f.key}
            type="button"
            title="Tap to record again"
            onClick={() => {
              setOpen(f);
              setError(null);
              setPhrases({});
            }}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11.5px] font-semibold transition ${
              open?.key === f.key
                ? 'border-brand bg-brand-50 text-brand-700'
                : 'border-ok/40 bg-ok-bg text-ok hover:border-brand-300'
            }`}
          >
            <Icon name="check" size={10} /> {f.label}: {filled[f.key]}
            <span className="ml-0.5 opacity-60">↻</span>
          </button>
        ))}
      </div>

      {open && (
        <div className="mt-3 rounded-xl border border-brand-200 bg-surface p-3">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[13px] font-semibold leading-relaxed text-ink">
              {phrases[questionFor(open)] ?? questionFor(open)}
            </p>
            <ListenButton text={phrases[questionFor(open)] ?? questionFor(open)} lang={lang} />
          </div>
          {phrases[questionFor(open)] && (
            <p className="mt-1 text-[11px] text-muted">{questionFor(open)}</p>
          )}

          {/* Fixed options: tapping is exact, so offer it before the recorder. */}
          {open.options.length > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {open.options.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    onFilled(open.key, opt); // already an exact value — no model needed
                    setOpen(null);
                    setPhrases({});
                  }}
                  className="rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-[12px] text-ink-2 transition hover:border-brand-300 hover:bg-brand-50 disabled:opacity-50"
                >
                  {phrases[opt] && phrases[opt] !== opt ? `${phrases[opt]} · ${opt}` : opt}
                </button>
              ))}
            </div>
          )}

          <div className="mt-3">
            <p className="mb-1.5 text-[11px] font-semibold text-muted">
              {open.options.length ? 'or say it in your own words' : 'Say it in your own words'}
            </p>
            <VoiceRecorder onTranscript={submit} disabled={busy} />
          </div>

          <div className="mt-2 flex gap-2">
            <input
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit(typed)}
              placeholder="or type it"
              className="flex-1 rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-[12px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-100"
            />
            <button
              type="button"
              onClick={() => submit(typed)}
              disabled={busy || !typed.trim()}
              className="rounded-lg bg-brand px-3 py-1.5 text-[12px] font-semibold text-white transition hover:bg-brand-600 disabled:opacity-50"
            >
              {busy ? '…' : 'Add'}
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(null);
                setPhrases({});
              }}
              className="rounded-lg border border-line px-3 py-1.5 text-[12px] font-semibold text-muted transition hover:text-ink"
            >
              Cancel
            </button>
          </div>

          {error && (
            <p role="alert" className="mt-2 rounded-lg bg-danger-bg px-2.5 py-1.5 text-[11px] text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function questionFor(f: PendingField) {
  return `What is the ${f.label} of your product?`;
}
