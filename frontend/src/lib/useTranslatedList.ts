'use client';

import { useEffect, useState } from 'react';
import { translateTexts } from '@/lib/api';
import { spokenOrPreferred } from '@/components/ReviewInHerLanguage';

/**
 * Her language for a list of short strings — the checklist and the approval
 * bullets, which are the other things she must act on and were English-only
 * even after the title/description review went bilingual.
 *
 * Same rule as everywhere else: what she just spoke wins over what she
 * registered with (spokenOrPreferred), and a failed or partial translation
 * degrades to plain English rather than a blank — get() returns undefined for
 * anything untranslated, and callers fall back to the original text.
 */
export function useTranslatedList(items: string[], detectedLanguage?: string | null) {
  const [map, setMap] = useState<Record<string, string>>({});
  const [lang, setLang] = useState<string | null>(null);
  // items is typically built fresh (e.g. via .map()) on every render, so its
  // array identity is not a safe effect dependency — join it into one stable
  // string instead. ␟ is the "unit separator" control character, chosen
  // so it can't collide with anything a seller or the crew would ever type.
  const key = items.join('␟');

  useEffect(() => {
    let active = true;
    (async () => {
      const list = key ? key.split('␟') : [];
      if (!list.length) {
        if (active) {
          setMap({});
          setLang(null);
        }
        return;
      }
      try {
        const r = await translateTexts(list, spokenOrPreferred(detectedLanguage));
        if (!active) return;
        if (r.language === 'en') {
          setMap({});
          setLang(null);
          return;
        }
        const m: Record<string, string> = {};
        for (const t of r.translations) if (t.provider !== 'none') m[t.original] = t.text;
        setMap(m);
        setLang(r.language);
      } catch {
        if (active) {
          setMap({});
          setLang(null);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [key, detectedLanguage]);

  return { lang, get: (original: string) => map[original] };
}
