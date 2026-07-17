'use client';

import { Icon } from '@/components/icons';

export type StepId = 1 | 2 | 3;

const STEPS: { id: StepId; label: string; hint: string }[] = [
  { id: 1, label: 'Tell us', hint: 'Speak or type, add one photo' },
  { id: 2, label: 'The crew works', hint: 'Six agents, live' },
  { id: 3, label: 'Review & publish', hint: 'Nothing goes live without you' },
];

/**
 * Steps, not tabs.
 *
 * The flow is sequential — she cannot review a listing before the crew has
 * written one — and tabs imply peers you may visit in any order. Steps say
 * "you are here", which is what a first-time seller needs. Step 1 stays
 * reachable so she can change her words or photo; the rest are not clickable,
 * because there is nothing there until the crew has run.
 */
export function Stepper({
  current,
  onBack,
  canGoBack,
}: {
  current: StepId;
  onBack: () => void;
  canGoBack: boolean;
}) {
  return (
    <ol className="mb-6 flex flex-wrap items-center gap-x-2 gap-y-2">
      {STEPS.map((s, i) => {
        const done = s.id < current;
        const active = s.id === current;
        const clickable = s.id === 1 && canGoBack && current !== 1;
        return (
          <li key={s.id} className="flex items-center gap-2">
            {i > 0 && <span aria-hidden className="h-px w-4 bg-line sm:w-8" />}
            <button
              type="button"
              onClick={clickable ? onBack : undefined}
              disabled={!clickable}
              aria-current={active ? 'step' : undefined}
              className={`flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-left transition ${
                clickable ? 'cursor-pointer hover:bg-brand-50' : 'cursor-default'
              }`}
            >
              <span
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold ${
                  done
                    ? 'bg-ok-bg text-ok'
                    : active
                      ? 'bg-brand text-white'
                      : 'bg-canvas text-muted'
                }`}
              >
                {done ? <Icon name="check" size={11} /> : s.id}
              </span>
              <span className="min-w-0">
                <span
                  className={`block text-[13px] font-semibold leading-tight ${
                    active ? 'text-ink' : done ? 'text-ink-2' : 'text-muted'
                  }`}
                >
                  {s.label}
                </span>
                <span className="hidden text-[10.5px] leading-tight text-muted sm:block">
                  {s.hint}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
