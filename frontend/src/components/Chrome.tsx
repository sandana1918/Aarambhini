import Link from 'next/link';

export function Logo({ size = 'md' }: { size?: 'sm' | 'md' }) {
  const dim = size === 'sm' ? 'h-8 w-8' : 'h-9 w-9';
  return (
    <Link href="/" className="flex items-center gap-2.5 shrink-0">
      <span
        className={`${dim} grid place-items-center rounded-xl bg-brand text-white font-bold shadow-sm`}
        aria-hidden
      >
        आ
      </span>
      <span className="flex flex-col leading-none">
        <span className="text-[17px] font-bold tracking-tight text-ink">Aarambhini</span>
        <span className="text-[10px] font-medium text-muted">she who begins</span>
      </span>
    </Link>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Logo />
        <nav className="flex items-center gap-1 sm:gap-2">
          <Link
            href="/#how"
            className="hidden rounded-lg px-3 py-2 text-sm font-medium text-ink-2 transition hover:bg-brand-50 hover:text-brand-700 sm:block"
          >
            How it works
          </Link>
          <Link
            href="/#agents"
            className="hidden rounded-lg px-3 py-2 text-sm font-medium text-ink-2 transition hover:bg-brand-50 hover:text-brand-700 sm:block"
          >
            The crew
          </Link>
          <Link
            href="/sell"
            className="rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-600 active:scale-[0.98]"
          >
            Start selling
          </Link>
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="mt-24 border-t border-line bg-surface">
      <div className="mx-auto max-w-6xl px-5 py-12">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-sm">
            <Logo size="sm" />
            <p className="mt-4 text-sm leading-relaxed text-muted">
              An agentic AI co-founder for Bharat&apos;s women sellers. From one voice note to a
              live, compliant, returns-proofed listing.
            </p>
          </div>
          <div className="text-sm text-muted">
            <p className="font-semibold text-ink-2">Built for</p>
            <p className="mt-2">ScriptedBy&#123;Her&#125; 2.0</p>
            <p className="mt-1">An on-ramp to existing marketplaces — not another storefront.</p>
          </div>
        </div>
        <p className="mt-10 border-t border-line pt-6 text-xs leading-relaxed text-muted">
          Compliance guidance is accurate at the category level and flagged for legal review — it is
          not legal advice. Returns risk is <em>reasoned</em> from the product and category; it does
          not use any marketplace&apos;s private return data.
        </p>
      </div>
    </footer>
  );
}
