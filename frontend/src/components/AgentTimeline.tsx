'use client';

import { useState } from 'react';
import { loopKind, type AgentLogEntry } from '@/lib/types';
import { Icon, type IconName } from './icons';

const AGENT_ICON: Record<string, IconName> = {
  Suno: 'ear',
  Likho: 'pen',
  Daam: 'rupee',
  Niyam: 'scale',
  Wapsi: 'refresh',
  Mukhiya: 'compass',
  Packaging: 'package',
  Seller: 'check',
};

function iconFor(agent: string): IconName {
  const base = agent.split(' ')[0];
  return AGENT_ICON[base] ?? 'bot';
}

const LOOP_STYLE = {
  quality: { chip: 'bg-brand-100 text-brand-700', label: 'Quality loop', ring: 'border-brand-200' },
  compliance: { chip: 'bg-danger-bg text-danger', label: 'Compliance loop', ring: 'border-danger/30' },
  returns: { chip: 'bg-warn-bg text-warn', label: 'Returns loop', ring: 'border-saffron/40' },
} as const;

export function AgentTimeline({ log }: { log: AgentLogEntry[] }) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <ol className="relative space-y-2.5 pl-7">
      <span
        className="absolute left-[13px] top-2 bottom-2 w-px bg-line"
        aria-hidden
      />
      {log.map((entry, i) => {
        const kind = loopKind(entry.agent);
        const style = kind ? LOOP_STYLE[kind] : null;
        const isOpen = open === i;

        return (
          <li key={i} className="relative animate-rise" style={{ animationDelay: `${i * 45}ms` }}>
            <span
              className={`absolute -left-7 top-2.5 grid h-6 w-6 place-items-center rounded-full border-2 bg-surface text-ink-2 ${
                style ? style.ring : 'border-line'
              }`}
            >
              <Icon name={iconFor(entry.agent)} size={12} />
            </span>

            <button
              onClick={() => setOpen(isOpen ? null : i)}
              className={`w-full rounded-xl border px-3.5 py-2.5 text-left transition hover:bg-canvas ${
                style ? `${style.ring} bg-canvas` : 'border-line bg-surface'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[13px] font-semibold text-ink">{entry.agent}</span>
                <div className="flex shrink-0 items-center gap-1.5">
                  {style && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${style.chip}`}
                    >
                      ⟲ {style.label}
                    </span>
                  )}
                  <span className="text-[10px] text-muted">{isOpen ? '−' : '+'}</span>
                </div>
              </div>
            </button>

            {isOpen && (
              <pre className="mt-1.5 max-h-64 overflow-auto rounded-xl bg-ink p-3.5 font-mono text-[11px] leading-relaxed text-white/85">
                {JSON.stringify(entry.output, null, 2)}
              </pre>
            )}
          </li>
        );
      })}
    </ol>
  );
}
