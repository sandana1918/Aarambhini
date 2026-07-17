'use client';

import { useId, useState, type ReactNode } from 'react';

export type Tab = { id: string; label: string; badge?: string | null; content: ReactNode };

/**
 * Reference panes only.
 *
 * Never put anything she is vouching for behind a tab. "Nothing publishes
 * without her approval" is a lie if the thing she approves is hidden one click
 * away — an unopened tab reads as "no problem here". The conflict warning, the
 * missing details and the approval gate stay on the page; this is for the
 * detail she may want to look at, not the detail she must see.
 */
export function Tabs({ tabs, initial }: { tabs: Tab[]; initial?: string }) {
  const base = useId();
  const [active, setActive] = useState(initial ?? tabs[0]?.id);
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  if (!tabs.length) return null;

  function onKeyDown(e: React.KeyboardEvent) {
    const i = tabs.findIndex((t) => t.id === active);
    if (e.key === 'ArrowRight') setActive(tabs[(i + 1) % tabs.length].id);
    if (e.key === 'ArrowLeft') setActive(tabs[(i - 1 + tabs.length) % tabs.length].id);
  }

  return (
    <section className="card overflow-hidden">
      {/* Scrolls rather than wraps: on a phone these must not become two rows
          that push the approval gate off the screen. */}
      <div
        role="tablist"
        aria-label="Listing details"
        onKeyDown={onKeyDown}
        className="flex gap-1 overflow-x-auto border-b border-line bg-canvas px-2 py-1.5"
      >
        {tabs.map((t) => {
          const on = t.id === active;
          return (
            <button
              key={t.id}
              role="tab"
              id={`${base}-tab-${t.id}`}
              aria-selected={on}
              aria-controls={`${base}-panel-${t.id}`}
              tabIndex={on ? 0 : -1}
              onClick={() => setActive(t.id)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-[12.5px] font-semibold transition ${
                on
                  ? 'bg-surface text-brand shadow-sm'
                  : 'text-muted hover:bg-surface/60 hover:text-ink-2'
              }`}
            >
              {t.label}
              {t.badge && (
                <span className="ml-1.5 rounded-full bg-warn-bg px-1.5 py-0.5 text-[10px] font-bold text-warn">
                  {t.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${base}-panel-${current.id}`}
        aria-labelledby={`${base}-tab-${current.id}`}
        className="p-5"
      >
        {current.content}
      </div>
    </section>
  );
}
