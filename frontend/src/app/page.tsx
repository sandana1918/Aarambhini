import Link from 'next/link';
import { Header, Footer } from '@/components/Chrome';
import { Icon, type IconName } from '@/components/icons';

const CREW: { name: string; role: string; desc: string; icon: IconName }[] = [
  { name: 'Mukhiya', role: 'The Manager', desc: 'Plans the work, arbitrates the loops, and holds the approval gate.', icon: 'compass' },
  { name: 'Suno', role: 'The Ear', desc: 'Hears your voice note in your language and reads your photo — rejecting blurry or copied shots.', icon: 'ear' },
  { name: 'Likho', role: 'The Pen', desc: 'Writes the title, description, keywords and your maker story.', icon: 'pen' },
  { name: 'Daam', role: 'The Pricer', desc: 'Sets a fair price with a margin, and a discount floor you should never go below.', icon: 'rupee' },
  { name: 'Niyam', role: 'The Rulekeeper', desc: 'Checks GST, labels and licences — and blocks the listing until they are right.', icon: 'scale' },
  { name: 'Wapsi', role: 'The Returns Guard', desc: 'Predicts why a buyer would return it, and fixes the listing before that happens.', icon: 'refresh' },
  { name: 'Packaging', role: 'The Packer', desc: 'Builds a safe packing plan — poly bag, mailer or box — from what’s fragile or perishable in your category.', icon: 'package' },
];

const LOOPS = [
  {
    n: '01',
    title: 'Quality loop',
    line: 'Mukhiya ⟲ Likho',
    desc: 'Mukhiya rejects a thin listing and sends it back to be rewritten richer.',
    tone: 'brand',
  },
  {
    n: '02',
    title: 'Compliance loop',
    line: 'Niyam ⟲ Likho + Daam',
    desc: 'Niyam demands a label. Likho adds it, and Daam re-prices so your margin survives the extra cost.',
    tone: 'danger',
  },
  {
    n: '03',
    title: 'Returns loop',
    line: 'Wapsi ⟲ Likho',
    desc: 'High return risk? A size guide is added and the listing is held for your confirmation.',
    tone: 'saffron',
  },
];

export default function Home() {
  return (
    <>
      <Header />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0 -z-10"
            style={{
              background:
                'radial-gradient(70% 60% at 80% -10%, #fde7f1 0%, transparent 60%), radial-gradient(50% 50% at 0% 0%, #fef3c7 0%, transparent 55%)',
            }}
          />
          <div className="mx-auto grid max-w-6xl gap-12 px-5 py-16 sm:py-24 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
            <div className="animate-rise">
              <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3.5 py-1.5 text-xs font-semibold text-brand-700">
                <span className="h-1.5 w-1.5 rounded-full bg-brand" />
                Agentic AI for Bharat&apos;s women sellers
              </span>

              <h1 className="mt-6 text-4xl font-bold leading-[1.08] tracking-tight text-ink sm:text-5xl lg:text-[3.4rem]">
                Speak once.
                <br />
                Get a listing that&apos;s{' '}
                <span className="relative whitespace-nowrap text-brand">
                  ready to sell
                  <svg
                    className="absolute -bottom-1.5 left-0 w-full"
                    height="10"
                    viewBox="0 0 300 10"
                    fill="none"
                    aria-hidden
                  >
                    <path
                      d="M2 7c60-5 120-5 180-3s90 3 116 1"
                      stroke="#f870b4"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>
                .
              </h1>

              <p className="mt-7 max-w-xl text-[17px] leading-relaxed text-ink-2">
                Record one voice note in your own language and upload one phone photo. A crew of AI
                agents writes your listing, prices it, makes it legally compliant, and protects you
                from returns — then waits for your approval before anything goes live.
              </p>

              <div className="mt-9 flex flex-wrap items-center gap-3">
                <Link
                  href="/sell"
                  className="rounded-xl bg-brand px-6 py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-600 active:scale-[0.98]"
                >
                  Create my listing — free
                </Link>
                <Link
                  href="#how"
                  className="rounded-xl border border-line bg-surface px-6 py-3.5 text-[15px] font-semibold text-ink-2 transition hover:border-brand-200 hover:text-brand-700"
                >
                  See how it works
                </Link>
              </div>

              <dl className="mt-12 flex flex-wrap gap-x-10 gap-y-5">
                {[
                  ['22', 'Indian languages'],
                  ['13', 'product categories'],
                  ['3', 'self-correcting loops'],
                ].map(([v, l]) => (
                  <div key={l}>
                    <dt className="text-2xl font-bold text-ink">{v}</dt>
                    <dd className="text-xs font-medium text-muted">{l}</dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* Phone mock */}
            <div className="animate-rise justify-self-center [animation-delay:120ms]">
              <div className="w-[300px] rounded-[2.2rem] border-8 border-ink bg-ink p-1 shadow-2xl">
                <div className="overflow-hidden rounded-[1.7rem] bg-canvas">
                  <div className="bg-brand px-4 py-3 text-white">
                    <p className="text-[11px] opacity-80">Aarambhini</p>
                    <p className="text-sm font-semibold">Your listing is ready</p>
                  </div>
                  <div className="space-y-2.5 p-3.5">
                    <div className="rounded-xl bg-surface p-3 shadow-sm">
                      <div className="flex gap-2.5">
                        <div className="h-14 w-14 shrink-0 rounded-lg bg-gradient-to-br from-saffron-100 to-brand-100" />
                        <div className="min-w-0">
                          <p className="truncate text-[13px] font-semibold text-ink">
                            Handwoven Jute Bag
                          </p>
                          <p className="mt-0.5 text-[11px] text-muted">Eco-friendly · handmade</p>
                          <p className="mt-1 text-sm font-bold text-ink">
                            ₹294 <span className="text-[10px] font-medium text-ok">20% margin</span>
                          </p>
                        </div>
                      </div>
                    </div>
                    {([
                      ['scale', 'Fabric + care label added'],
                      ['refresh', 'Size guide added — fewer returns'],
                      ['package', 'Poly bag → courier mailer'],
                    ] as [IconName, string][]).map(([icon, t]) => (
                      <div
                        key={t}
                        className="flex items-center gap-2 rounded-lg bg-ok-bg px-2.5 py-2 text-[11px] font-medium"
                      >
                        <Icon name={icon} size={14} className="shrink-0 text-ok" />
                        <span className="text-ink-2">{t}</span>
                      </div>
                    ))}
                    <button className="w-full rounded-xl bg-brand py-2.5 text-[13px] font-semibold text-white animate-pulse-ring">
                      Approve &amp; publish
                    </button>
                    <p className="text-center text-[10px] text-muted">
                      Nothing goes live without your tap
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Problem */}
        <section className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-5 py-16">
            <p className="text-xs font-bold uppercase tracking-widest text-brand">The problem</p>
            <h2 className="mt-3 max-w-3xl text-2xl font-bold leading-snug text-ink sm:text-3xl">
              10 crore women are in Self-Help Groups. Almost none of them sell online.
            </h2>
            <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-2">
              It isn&apos;t a lack of marketplaces — it&apos;s that the journey from a home-made
              product to a live listing is blocked at five points a first-time, non-English seller
              can&apos;t cross alone.
            </p>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {([
                ['catalog', 'Cataloging', 'Can’t write English titles or pick a category'],
                ['rupee', 'Pricing', 'No idea what price sells — or protects her margin'],
                ['scale', 'Compliance', 'GST, FSSAI, labels feel like an impossible wall'],
                ['camera', 'Photography', 'Phone photos get rejected as “not marketplace-ready”'],
                ['refresh', 'Returns', 'One wrong-fit return wipes out a week’s profit'],
              ] as [IconName, string, string][]).map(([icon, t, d]) => (
                <div key={t} className="card p-5">
                  <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-50 text-brand">
                    <Icon name={icon} size={22} />
                  </span>
                  <p className="mt-3 text-sm font-bold text-ink">{t}</p>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-5 py-20">
          <p className="text-xs font-bold uppercase tracking-widest text-brand">How it works</p>
          <h2 className="mt-3 text-2xl font-bold text-ink sm:text-3xl">
            Two inputs. One complete commerce package.
          </h2>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                n: '1',
                t: 'Speak in your language',
                d: 'Record a voice note in Hindi, Tamil, Bengali — anything. Suno understands it and reads your one phone photo.',
              },
              {
                n: '2',
                t: 'The agents argue it out',
                d: 'Seven agents write, price, and legally check your listing — rejecting and re-doing each other’s work until it’s right.',
              },
              {
                n: '3',
                t: 'You approve. Then it goes live.',
                d: 'Nothing publishes, no price changes, no assumption is made without your explicit tap.',
              },
            ].map((s) => (
              <div key={s.n} className="card relative p-7">
                <span className="absolute -top-3.5 left-7 grid h-8 w-8 place-items-center rounded-full bg-brand text-sm font-bold text-white shadow-md">
                  {s.n}
                </span>
                <p className="mt-3 text-base font-bold text-ink">{s.t}</p>
                <p className="mt-2.5 text-[14px] leading-relaxed text-ink-2">{s.d}</p>
              </div>
            ))}
          </div>

          <div className="mt-16">
            <h3 className="text-lg font-bold text-ink">
              What makes it <span className="text-brand">agentic</span>, not just AI
            </h3>
            <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-ink-2">
              This isn&apos;t one prompt in, one listing out. The agents check and re-do each
              other&apos;s work through three self-correcting loops — you can watch it happen live.
            </p>

            <div className="mt-7 grid gap-4 md:grid-cols-3">
              {LOOPS.map((l) => {
                const tone =
                  l.tone === 'danger'
                    ? 'border-t-danger'
                    : l.tone === 'saffron'
                      ? 'border-t-saffron'
                      : 'border-t-brand';
                return (
                  <div key={l.n} className={`card border-t-[3px] p-6 ${tone}`}>
                    <p className="font-mono text-[11px] font-semibold text-muted">Loop {l.n}</p>
                    <p className="mt-1.5 text-base font-bold text-ink">{l.title}</p>
                    <p className="mt-3 rounded-lg bg-canvas px-3 py-2 font-mono text-[12px] text-ink-2">
                      {l.line}
                    </p>
                    <p className="mt-3 text-[13px] leading-relaxed text-ink-2">{l.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Crew */}
        <section id="agents" className="scroll-mt-20 border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <p className="text-xs font-bold uppercase tracking-widest text-brand">The crew</p>
            <h2 className="mt-3 text-2xl font-bold text-ink sm:text-3xl">
              Seven agents. One co-founder.
            </h2>
            <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {CREW.map((a) => (
                <div
                  key={a.name}
                  className="group rounded-2xl border border-line p-6 transition hover:border-brand-200 hover:bg-brand-50/40"
                >
                  <div className="flex items-center gap-3">
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-50 text-brand transition group-hover:bg-white">
                      <Icon name={a.icon} size={22} />
                    </span>
                    <div>
                      <p className="text-[15px] font-bold text-ink">{a.name}</p>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-brand">
                        {a.role}
                      </p>
                    </div>
                  </div>
                  <p className="mt-4 text-[13.5px] leading-relaxed text-ink-2">{a.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-5 py-20">
          <div className="relative overflow-hidden rounded-3xl bg-brand px-8 py-14 text-center shadow-xl shadow-brand/20 sm:px-16">
            <div
              className="pointer-events-none absolute inset-0 opacity-20"
              style={{
                background:
                  'radial-gradient(50% 80% at 20% 0%, #fff 0%, transparent 60%), radial-gradient(40% 70% at 90% 100%, #fff 0%, transparent 55%)',
              }}
            />
            <h2 className="relative text-2xl font-bold leading-snug text-white sm:text-3xl">
              Your product is ready. Let&apos;s get it selling.
            </h2>
            <p className="relative mx-auto mt-4 max-w-lg text-[15px] leading-relaxed text-white/85">
              One voice note. One photo. Two minutes. You stay in control the whole way.
            </p>
            <Link
              href="/sell"
              className="relative mt-9 inline-block rounded-xl bg-white px-8 py-4 text-[15px] font-bold text-brand-700 shadow-lg transition hover:bg-brand-50 active:scale-[0.98]"
            >
              Create my listing
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}
