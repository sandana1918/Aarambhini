'use client';

import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/icons';
import { speakUrl, translateTexts, type Translation } from '@/lib/api';

/**
 * The listing she is about to vouch for, in the language she actually speaks.
 *
 * The listing itself publishes in English — that's what the marketplace and its
 * buyers need. But asking a seller to approve English she can't read is the
 * exact problem this product exists to solve, so the review is shown in her
 * language with the English kept visible underneath and labelled as the text
 * that will actually go live. Anything else would be approval she can't give.
 */

function SpeakButton({ text, lang }: { text: string; lang: string }) {
  const [busy, setBusy] = useState(false);
  const [dead, setDead] = useState(false); // speech unavailable — hide, don't nag
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  // Release the blob URL and stop playback when this unmounts.
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  async function play() {
    if (busy) return;
    setBusy(true);
    try {
      if (!urlRef.current) {
        const url = await speakUrl(text, lang);
        if (!url) {
          setDead(true);
          return;
        }
        urlRef.current = url;
        audioRef.current = new Audio(url);
      }
      audioRef.current!.currentTime = 0;
      await audioRef.current!.play();
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
      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-brand-200 bg-surface px-2.5 py-1 text-[11px] font-semibold text-brand transition hover:bg-brand-50 disabled:opacity-50"
    >
      <Icon name={busy ? 'refresh' : 'ear'} size={12} />
      {busy ? 'Loading…' : 'Listen'}
    </button>
  );
}

function Block({
  heading,
  english,
  translated,
  lang,
}: {
  heading: string;
  english: string;
  translated?: Translation;
  lang: string;
}) {
  if (!english) return null;
  // provider 'none' means the translation didn't happen — show the English
  // plainly rather than pretending the untranslated string is her language.
  const hasTranslation = !!translated && translated.provider !== 'none' && translated.text !== english;

  return (
    <div className="rounded-xl border border-line bg-surface p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{heading}</p>
        {hasTranslation && <SpeakButton text={translated!.text} lang={lang} />}
      </div>

      {hasTranslation ? (
        <>
          <p className="mt-1.5 text-[14px] leading-relaxed text-ink">{translated!.text}</p>
          <p className="mt-2 border-t border-line pt-2 text-[12px] leading-relaxed text-muted">
            {english}
          </p>
        </>
      ) : (
        <p className="mt-1.5 text-[14px] leading-relaxed text-ink">{english}</p>
      )}
    </div>
  );
}

/**
 * The language to talk back in.
 *
 * What she just spoke beats what she ticked at registration: a seller
 * registered as Tamil who records a Hindi voice note is speaking Hindi today,
 * and answering her in Tamil is the same failure as answering in English —
 * a language she didn't choose *right now*.
 *
 * English input is the exception. Typing English doesn't mean she wants an
 * English review (she may have typed it because the box was there), so fall
 * back to her registered language and let the server decide.
 */
export function spokenOrPreferred(detected?: string | null) {
  const lang = (detected || '').trim().toLowerCase().slice(0, 2);
  return lang && lang !== 'en' ? lang : undefined;
}

export function ReviewInHerLanguage({
  title,
  description,
  detectedLanguage,
}: {
  title?: string | null;
  description?: string | null;
  /** From Suno — the language of this voice note. */
  detectedLanguage?: string | null;
}) {
  const [data, setData] = useState<{ language: string; translations: Translation[] } | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const texts = [title ?? '', description ?? ''].filter(Boolean);
    if (!texts.length) return;
    let active = true;
    (async () => {
      try {
        const r = await translateTexts(texts, spokenOrPreferred(detectedLanguage));
        if (active) {
          setData(r);
          setFailed(false);
        }
      } catch {
        if (active) setFailed(true);
      }
    })();
    return () => {
      active = false;
    };
  }, [title, description, detectedLanguage, attempt]);

  // Say so rather than disappear. A seller who can't read English and gets an
  // empty space has no way to tell "nothing to check here" from "this broke" —
  // silence is the worst of the three outcomes.
  if (failed && !data) {
    return (
      <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-line bg-canvas px-3.5 py-2.5">
        <p className="text-[12px] leading-relaxed text-muted">
          Couldn&apos;t load your language just now — the English below is still what publishes.
        </p>
        <button
          type="button"
          onClick={() => setAttempt((n) => n + 1)}
          className="shrink-0 rounded-lg border border-brand-200 bg-surface px-2.5 py-1 text-[11px] font-semibold text-brand transition hover:bg-brand-50"
        >
          Try again
        </button>
      </div>
    );
  }

  // English-speaking sellers need no second copy of their own listing.
  if (!data || data.language === 'en') return null;

  const byOriginal = new Map(data.translations.map((t) => [t.original, t]));
  const anyTranslated = data.translations.some((t) => t.provider !== 'none');
  if (!anyTranslated) return null;

  return (
    <div className="mt-4 rounded-xl border border-brand-200 bg-brand-50/40 p-3.5">
      <div className="flex items-center gap-2 text-brand">
        <Icon name="sprout" size={15} />
        <p className="text-[12.5px] font-bold text-ink">Read this in your language first</p>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-muted">
        Your listing goes out in English so buyers can find it. Here is what it says — tap
        Listen if you&apos;d rather hear it.
      </p>

      <div className="mt-3 grid gap-2.5">
        {title && (
          <Block
            heading="Title"
            english={title}
            translated={byOriginal.get(title)}
            lang={data.language}
          />
        )}
        {description && (
          <Block
            heading="Description"
            english={description}
            translated={byOriginal.get(description)}
            lang={data.language}
          />
        )}
      </div>

      <p className="mt-2.5 text-[10.5px] leading-relaxed text-muted">
        The smaller English text is what actually publishes. The translation is only to help
        you read it — if the two don&apos;t match, trust the English and fix it below.
      </p>
    </div>
  );
}
