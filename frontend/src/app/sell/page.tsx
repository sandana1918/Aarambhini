'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Header } from '@/components/Chrome';
import { AgentTimeline } from '@/components/AgentTimeline';
import { VoiceRecorder } from '@/components/VoiceRecorder';
import { ProductDetails } from '@/components/ProductDetails';
import { ReviewInHerLanguage } from '@/components/ReviewInHerLanguage';
import { FillMissingDetails } from '@/components/FillMissingDetails';
import { Icon } from '@/components/icons';
import { runListingStream, approveListing, clarifyListing, fetchMe } from '@/lib/api';
import { clearSession, loadSession, type Session } from '@/lib/session';
import type { RunResult } from '@/lib/types';

const HINDI_EXAMPLE = 'मैं हाथ से बने जूट बैग बनाती हूँ, 40 पीस, ₹200 लागत।';

const RISK: Record<string, { dot: string; text: string; bg: string }> = {
  low: { dot: 'bg-ok', text: 'text-ok', bg: 'bg-ok-bg' },
  medium: { dot: 'bg-saffron', text: 'text-warn', bg: 'bg-warn-bg' },
  high: { dot: 'bg-danger', text: 'text-danger', bg: 'bg-danger-bg' },
};

export default function SellPage() {
  const [voiceText, setVoiceText] = useState(HINDI_EXAMPLE);
  const [margin, setMargin] = useState(20);
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [published, setPublished] = useState(false);
  const [rejected, setRejected] = useState(false);
  const [editPrice, setEditPrice] = useState<string>('');
  // null = untouched, so the field shows the crew's text without copying it into
  // state. Anything non-null is her edit, even when she clears it back to empty.
  const [editTitle, setEditTitle] = useState<string | null>(null);
  const [editDescription, setEditDescription] = useState<string | null>(null);
  // Missing details she answered by voice, held until she publishes — the
  // graph's checkpoint is the source of truth, so they ride in as edits.
  const [attributeEdits, setAttributeEdits] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState('');
  const [approving, setApproving] = useState(false);
  const [clarifyValue, setClarifyValue] = useState('');
  const [clarifyCategory, setClarifyCategory] = useState('');
  const [clarifying, setClarifying] = useState(false);
  const [liveSteps, setLiveSteps] = useState<string[]>([]);
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // A stored token can be expired, revoked, or signed with a restarted dev
  // server's secret — so confirm it with the server rather than trusting
  // localStorage, and send her to log in if it doesn't hold up.
  useEffect(() => {
    let active = true;
    (async () => {
      const stored = loadSession();
      const me = stored ? await fetchMe() : null;
      if (!active) return;
      if (me) setSession(stored);
      else router.replace('/login'); // replace: back shouldn't return here
    })();
    return () => {
      active = false;
    };
  }, [router]);

  function onSignOut() {
    clearSession();
    setSession(null);
    setResult(null);
    router.push('/login');
  }

  function pickPhoto(f: File | null) {
    setPhoto(f);
    setPreview(f ? URL.createObjectURL(f) : null);
  }

  async function onRun() {
    setLoading(true);
    setError(null);
    setResult(null);
    setPublished(false);
    setRejected(false);
    setNotes('');
    setEditPrice('');
    setEditTitle(null);
    setEditDescription(null);
    setAttributeEdits({});
    setLiveSteps([]);
    try {
      const r = await runListingStream({ voiceText, marginPct: margin, photo }, (agent) =>
        setLiveSteps((prev) => [...prev, agent]),
      );
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  function buildEdits() {
    const edits: {
      price?: number;
      title?: string;
      description?: string;
      attributes?: Record<string, string>;
    } = {};
    if (Object.keys(attributeEdits).length) edits.attributes = attributeEdits;
    const p = Number(editPrice);
    if (editPrice.trim() && Number.isFinite(p) && p > 0 && p !== result?.price?.selling_price_inr) {
      edits.price = Math.round(p);
    }
    // Only send what she actually changed — the graph treats every present key
    // as a deliberate override and stamps the listing accordingly.
    const t = editTitle?.trim();
    if (t && t !== result?.listing?.title) edits.title = t;
    const d = editDescription?.trim();
    if (d && d !== result?.listing?.description) edits.description = d;
    return Object.keys(edits).length ? edits : undefined;
  }

  async function onApprove() {
    if (!result) return;
    setApproving(true);
    setError(null);
    const edits = buildEdits();
    try {
      await approveListing(result.id, true, notes || undefined, edits);
      // Reflect what actually went live in the confirmation — showing her the
      // crew's wording after she rewrote it would be a small lie.
      if (edits) {
        setResult({
          ...result,
          price: edits.price && result.price
            ? { ...result.price, selling_price_inr: edits.price }
            : result.price,
          listing: result.listing
            ? {
                ...result.listing,
                title: edits.title ?? result.listing.title,
                description: edits.description ?? result.listing.description,
              }
            : result.listing,
        });
      }
      setPublished(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not publish.');
    } finally {
      setApproving(false);
    }
  }

  async function onClarify() {
    if (!result) return;
    const answers: { cost_price_inr?: number; category?: string } = {};

    if (priceQuestion) {
      const v = Number(clarifyValue);
      if (!clarifyValue.trim() || !Number.isFinite(v) || v <= 0) {
        setError('Please enter a valid amount in ₹.');
        return;
      }
      answers.cost_price_inr = Math.round(v);
    }
    if (categoryQuestion) {
      if (!clarifyCategory) {
        setError('Please choose what best describes your product.');
        return;
      }
      answers.category = clarifyCategory;
    }

    setClarifying(true);
    setError(null);
    try {
      const r = await clarifyListing(result.id, answers);
      setResult(r);
      setClarifyValue('');
      setClarifyCategory('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not submit that answer.');
    } finally {
      setClarifying(false);
    }
  }

  async function onReject() {
    if (!result) return;
    setApproving(true);
    setError(null);
    try {
      await approveListing(result.id, false, notes || undefined);
      setRejected(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reject.');
    } finally {
      setApproving(false);
    }
  }

  const ready = result?.status === 'ready_for_approval';
  const retake = result?.status === 'needs_retake';
  const needsClarification = result?.status === 'needs_clarification';
  const questions = result?.clarification?.questions ?? [];
  const priceQuestion = questions.find((q) => q.field === 'cost_price_inr');
  // Asked when the category couldn't be determined — it decides which law
  // applies, so it's answered here rather than guessed.
  const categoryQuestion = questions.find((q) => q.field === 'category');
  const risk = result?.returns?.risk_level ?? 'low';
  const riskStyle = RISK[risk] ?? RISK.low;

  return (
    <>
      <Header />

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8">
        <div className="mb-7">
          <h1 className="text-2xl font-bold text-ink">Create your listing</h1>
          <p className="mt-1.5 text-[14px] text-muted">
            Speak in your language, add one photo — the crew does the rest.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)] lg:items-start">
          {/* ── INPUT ─────────────────────────────── */}
          {!session ? (
            /* Either still checking, or already being redirected to /login. */
            <section className="card p-5 lg:sticky lg:top-24">
              <div className="flex items-center gap-3">
                <span className="h-5 w-5 animate-spin rounded-full border-[3px] border-brand-100 border-t-brand" />
                <p className="text-[13px] text-muted">Checking your session…</p>
              </div>
            </section>
          ) : (
          <section className="card p-5 lg:sticky lg:top-24">
            <div className="mb-4 flex items-center justify-between gap-2 rounded-xl bg-canvas px-3 py-2">
              <span className="min-w-0 truncate text-[12px] text-ink-2">
                Signed in as <strong className="text-ink">{session.name}</strong>
              </span>
              <button
                onClick={onSignOut}
                className="shrink-0 text-[11px] font-semibold text-muted underline-offset-2 transition hover:text-ink hover:underline"
              >
                Sign out
              </button>
            </div>
            <label className="block text-[13px] font-semibold text-ink">
              1. Tell us about your product
            </label>
            <VoiceRecorder onTranscript={setVoiceText} disabled={loading} />
            <div className="my-2.5 flex items-center gap-3">
              <span className="h-px flex-1 bg-line" />
              <span className="text-[11px] text-muted">or type it</span>
              <span className="h-px flex-1 bg-line" />
            </div>
            <textarea
              value={voiceText}
              onChange={(e) => setVoiceText(e.target.value)}
              rows={4}
              className="w-full resize-none rounded-xl border border-line bg-canvas px-3.5 py-3 text-[14px] text-ink outline-none transition placeholder:text-muted focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand-100"
              placeholder="Hindi, Tamil, Bengali, English…"
            />
            <p className="mt-1.5 text-[11px] text-muted">
              Speak or type — Suno detects the language automatically.
            </p>

            <label className="mt-6 block text-[13px] font-semibold text-ink">
              2. Add one product photo
            </label>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)}
            />
            <button
              onClick={() => fileRef.current?.click()}
              className="mt-2 flex w-full items-center gap-3 rounded-xl border-2 border-dashed border-line bg-canvas px-4 py-4 text-left transition hover:border-brand-400 hover:bg-brand-50/50"
            >
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={preview}
                  alt="Your product"
                  className="h-14 w-14 shrink-0 rounded-lg object-cover"
                />
              ) : (
                <span className="grid h-14 w-14 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand">
                  <Icon name="camera" size={22} />
                </span>
              )}
              <span className="min-w-0">
                <span className="block truncate text-[13px] font-semibold text-ink">
                  {photo ? photo.name : 'Tap to upload a photo'}
                </span>
                <span className="block text-[11px] text-muted">
                  {photo ? 'Tap to change' : 'Clear, well-lit, product in focus'}
                </span>
              </span>
            </button>

            <label className="mt-6 flex items-center justify-between text-[13px] font-semibold text-ink">
              3. Your margin
              <span className="rounded-lg bg-brand-50 px-2 py-0.5 font-mono text-[12px] text-brand-700">
                {margin}%
              </span>
            </label>
            <input
              type="range"
              min={5}
              max={60}
              step={5}
              value={margin}
              onChange={(e) => setMargin(Number(e.target.value))}
              className="mt-3 w-full accent-brand"
            />

            <button
              onClick={onRun}
              disabled={loading || !voiceText.trim()}
              className="mt-6 w-full rounded-xl bg-brand py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-600 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'The crew is working…' : 'Run Aarambhini'}
            </button>

            {error && (
              <p className="mt-3 rounded-lg bg-danger-bg px-3 py-2 text-[12px] text-danger">
                {error}
              </p>
            )}
          </section>
          )}

          {/* ── OUTPUT ────────────────────────────── */}
          <div className="min-w-0 space-y-6">
            {!result && !loading && (
              <div className="card grid place-items-center px-6 py-20 text-center">
                <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand">
                  <Icon name="sparkles" size={26} />
                </span>
                <p className="mt-4 text-[15px] font-semibold text-ink">
                  Your agent crew is standing by
                </p>
                <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-muted">
                  Hit <strong>Run Aarambhini</strong> and watch six agents write, price, legally
                  check and returns-proof your listing — rejecting each other&apos;s work until
                  it&apos;s right.
                </p>
              </div>
            )}

            {loading && (
              <div className="card px-6 py-10">
                <div className="flex items-center gap-3">
                  <span className="h-6 w-6 animate-spin rounded-full border-[3px] border-brand-100 border-t-brand" />
                  <p className="text-[15px] font-semibold text-ink">
                    {liveSteps.length ? `${liveSteps[liveSteps.length - 1]} just finished…` : 'The crew is starting…'}
                  </p>
                </div>
                {liveSteps.length > 0 && (
                  <ol className="mt-5 space-y-1.5">
                    {liveSteps.map((agent, i) => (
                      <li
                        key={i}
                        className="animate-rise flex items-center gap-2.5 text-[13px] text-ink-2"
                      >
                        <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-ok-bg text-ok">
                          <Icon name="check" size={11} />
                        </span>
                        {agent}
                      </li>
                    ))}
                  </ol>
                )}
                <p className="mt-4 text-[11px] text-muted">
                  Live — each agent appears the moment it finishes.
                </p>
              </div>
            )}

            {/* Photo rejected — quality issue or a stolen/duplicate photo */}
            {retake &&
              (() => {
                const blocked = result?.authenticity?.verdict === 'blocked';
                return (
                  <div className="card border-saffron/40 p-6">
                    <div className="flex items-start gap-3">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-warn-bg text-warn">
                        <Icon name={blocked ? 'ban' : 'camera'} size={20} />
                      </span>
                      <div>
                        <p className="text-[15px] font-bold text-ink">
                          {blocked ? 'This photo can’t be used' : 'Suno stopped the pipeline'}
                        </p>
                        <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">
                          {result?.reason}
                        </p>
                        <p className="mt-3 text-[12px] text-muted">
                          {blocked
                            ? 'Take a fresh photo of your own product and run again — it keeps every seller’s listings genuine.'
                            : 'Nothing else ran — no point writing a listing around a photo buyers can’t see. Upload a clearer photo and run again.'}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })()}

            {needsClarification && result && (
              <div className="card border-brand-200 p-6">
                <div className="flex items-start gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand">
                    <Icon name="help" size={20} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] font-bold text-ink">
                      {questions.length > 1 ? 'Two quick things' : 'One quick thing'}
                    </p>

                    {priceQuestion && (
                      <div className="mt-2">
                        <p className="text-[13.5px] leading-relaxed text-ink-2">
                          {priceQuestion.prompt}
                        </p>
                        <div className="relative mt-3">
                          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[14px] text-muted">
                            ₹
                          </span>
                          <input
                            type="number"
                            inputMode="numeric"
                            autoFocus
                            value={clarifyValue}
                            onChange={(e) => setClarifyValue(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && !categoryQuestion && onClarify()}
                            placeholder="e.g. 250"
                            className="w-full rounded-xl border border-line bg-canvas py-3 pl-7 pr-3 text-[14px] text-ink outline-none focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand-100"
                          />
                        </div>
                      </div>
                    )}

                    {categoryQuestion && (
                      <div className={priceQuestion ? 'mt-5' : 'mt-2'}>
                        <p className="text-[13.5px] leading-relaxed text-ink-2">
                          {categoryQuestion.prompt}
                        </p>
                        <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
                          {categoryQuestion.options?.map((opt) => {
                            const picked = clarifyCategory === opt.key;
                            return (
                              <button
                                key={opt.key}
                                type="button"
                                onClick={() => setClarifyCategory(opt.key)}
                                aria-pressed={picked}
                                className={`rounded-xl border px-3.5 py-2.5 text-left text-[13px] font-medium transition ${
                                  picked
                                    ? 'border-brand bg-brand-50 text-brand-700'
                                    : 'border-line bg-canvas text-ink-2 hover:border-brand-200 hover:bg-brand-50/40'
                                }`}
                              >
                                {opt.label}
                              </button>
                            );
                          })}
                        </div>
                        <p className="mt-2 text-[11px] leading-relaxed text-muted">
                          This decides which labels and licences the law asks of you — a wrong
                          guess here is the one mistake that could get your listing pulled.
                        </p>
                      </div>
                    )}

                    <button
                      onClick={onClarify}
                      disabled={clarifying}
                      className="mt-4 w-full rounded-xl bg-brand px-6 py-3 text-[14px] font-semibold text-white transition hover:bg-brand-600 disabled:opacity-60 sm:w-auto"
                    >
                      {clarifying ? 'Continuing…' : 'Continue'}
                    </button>
                    <p className="mt-2.5 text-[11px] text-muted">
                      The crew paused here and will pick up exactly where it left off.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {ready && result && (
              <>
                {/* Status strip */}
                <div className="card flex flex-wrap items-center gap-x-6 gap-y-3 p-4">
                  <span className="flex items-center gap-2 text-[13px] font-semibold text-ok">
                    <span className="h-2 w-2 rounded-full bg-ok" /> Ready to list
                  </span>
                  <span className="text-[13px] text-ink-2">
                    Price <strong className="text-ink">₹{result.price?.selling_price_inr}</strong>
                  </span>
                  <span className={`flex items-center gap-2 text-[13px] ${riskStyle.text}`}>
                    <span className={`h-2 w-2 rounded-full ${riskStyle.dot}`} />
                    Returns risk: {risk}
                  </span>
                  {result.authenticity?.verdict === 'ok' && (
                    <span className="flex items-center gap-1.5 text-[13px] text-ok">
                      <Icon name="check" size={14} /> Photo verified
                    </span>
                  )}
                  {result.suno?.detected_language && (
                    <span className="ml-auto rounded-full bg-brand-50 px-2.5 py-1 font-mono text-[11px] text-brand-700">
                      lang: {result.suno.detected_language}
                    </span>
                  )}
                </div>

                {/* Photo authenticity — soft flags surfaced for review, never auto-rejected */}
                {result.authenticity?.verdict === 'review' &&
                  !!result.authenticity.flags?.length && (
                    <div className="card border-saffron/40 bg-warn-bg/40 p-4">
                      <div className="flex items-center gap-2 text-warn">
                        <Icon name="alert" size={16} />
                        <p className="text-[13px] font-bold">Please double-check this photo</p>
                      </div>
                      <ul className="mt-2 space-y-1">
                        {result.authenticity.flags.map((f) => (
                          <li key={f} className="text-[12px] leading-relaxed text-ink-2">
                            • {f}
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 text-[11px] text-muted">
                        You can still publish — this is just a heads-up to make sure it’s your own
                        product photo.
                      </p>
                    </div>
                  )}

                {/* Listing */}
                <section className="card overflow-hidden">
                  <div className="flex items-start gap-4 p-5">
                    {preview && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={preview}
                        alt=""
                        className="h-24 w-24 shrink-0 rounded-xl object-cover"
                      />
                    )}
                    <div className="min-w-0">
                      <h2 className="text-[17px] font-bold leading-snug text-ink">
                        {result.listing?.title}
                      </h2>
                      <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-ink">
                          ₹{result.price?.selling_price_inr}
                        </span>
                        <span className="rounded bg-ok-bg px-1.5 py-0.5 text-[11px] font-bold text-ok">
                          {result.price?.margin_pct}% margin
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-muted">
                        Never sell below ₹{result.price?.discount_floor_inr} (your break-even)
                      </p>
                    </div>
                  </div>

                  <div className="border-t border-line p-5">
                    <p className="text-[14px] leading-relaxed text-ink-2">
                      {result.listing?.description}
                    </p>
                    {result.listing?.maker_story && (
                      <p className="mt-4 flex gap-2.5 rounded-xl bg-brand-50 px-4 py-3 text-[13px] italic leading-relaxed text-brand-700">
                        <Icon name="sprout" size={16} className="mt-0.5 shrink-0" />
                        <span>{result.listing.maker_story}</span>
                      </p>
                    )}
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {result.listing?.keywords?.map((k) => (
                        <span
                          key={k}
                          className="rounded-full bg-canvas px-2.5 py-1 text-[11px] text-ink-2"
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                </section>

                {/* Meesho-style structured attributes */}
                <ProductDetails
                  attributes={result.product_attributes}
                  missing={result.missing_attributes}
                />

                {/* Compliance / Returns / Packaging */}
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="card p-5">
                    <div className="flex items-center gap-2 text-brand">
                      <Icon name="scale" size={18} />
                      <p className="text-[13px] font-bold text-ink">Compliance</p>
                    </div>
                    <p
                      className={`mt-3 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold ${
                        result.compliance?.compliance_ok
                          ? 'bg-ok-bg text-ok'
                          : 'bg-warn-bg text-warn'
                      }`}
                    >
                      <Icon name={result.compliance?.compliance_ok ? 'check' : 'alert'} size={12} />
                      {result.compliance?.compliance_ok ? 'Labels applied' : 'Action needed'}
                    </p>
                    {!!result.compliance?.required_licenses?.length && (
                      <p className="mt-3 rounded-lg bg-warn-bg px-2.5 py-2 text-[11px] font-medium text-warn">
                        Licence needed: {result.compliance.required_licenses.join(', ')}
                      </p>
                    )}
                    <p className="mt-3 text-[11px] leading-relaxed text-muted">
                      {result.compliance?.gst_note}
                    </p>
                  </div>

                  <div className="card p-5">
                    <div className="flex items-center gap-2 text-brand">
                      <Icon name="refresh" size={18} />
                      <p className="text-[13px] font-bold text-ink">Returns</p>
                    </div>
                    <p
                      className={`mt-3 inline-block rounded-full px-2.5 py-1 text-[11px] font-bold ${riskStyle.bg} ${riskStyle.text}`}
                    >
                      {risk} risk
                    </p>
                    <p className="mt-3 text-[12px] leading-relaxed text-ink-2">
                      {result.returns?.top_return_reason}
                    </p>
                    {result.returns?.learned_from_returns ? (
                      <p className="mt-2.5 flex items-center gap-1.5 rounded-lg bg-brand-50 px-2 py-1 text-[10.5px] font-medium text-brand-700">
                        <Icon name="refresh" size={11} />
                        Learned from {result.returns.learned_from_returns} past returns in this category
                      </p>
                    ) : (
                      <p className="mt-2.5 text-[10.5px] text-muted">
                        No return history yet — reasoned from category patterns.
                      </p>
                    )}
                  </div>

                  <div className="card p-5">
                    <div className="flex items-center gap-2 text-brand">
                      <Icon name="package" size={18} />
                      <p className="text-[13px] font-bold text-ink">Packaging</p>
                    </div>
                    <p className="mt-3 text-[12px] leading-relaxed text-ink-2">
                      {result.packaging_plan?.primary_pack}
                    </p>
                    <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
                      → {result.packaging_plan?.outer_pack}
                    </p>
                    {result.packaging_plan?.shipping_label && (
                      <p className="mt-3 rounded-lg bg-canvas px-2.5 py-1.5 text-center font-mono text-[10px] font-bold tracking-wide text-ink-2">
                        {result.packaging_plan.shipping_label}
                      </p>
                    )}
                  </div>
                </div>

                {/* Checklist */}
                {!!result.action_checklist?.length && (
                  <section className="card p-5">
                    <p className="text-[13px] font-bold text-ink">Your next steps</p>
                    <ul className="mt-3 space-y-2">
                      {result.action_checklist.map((item, i) => (
                        <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-2">
                          <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border border-line text-[9px] text-muted">
                            {i + 1}
                          </span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* Activity log */}
                <section className="card p-5">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-[13px] font-bold text-ink">Agent activity</p>
                      <p className="mt-0.5 text-[11px] text-muted">
                        Tap any step to see exactly what that agent returned.
                      </p>
                    </div>
                    <span className="rounded-full bg-canvas px-2.5 py-1 font-mono text-[11px] text-muted">
                      {result.activity_log?.length ?? 0} steps
                    </span>
                  </div>
                  <AgentTimeline log={result.activity_log ?? []} />
                </section>

                {/* Approval gate */}
                <section
                  className={`card p-6 ${published ? 'border-ok/40 bg-ok-bg/40' : 'border-brand-200'}`}
                >
                  {published ? (
                    <div className="text-center">
                      <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-ok-bg text-ok">
                        <Icon name="success" size={26} />
                      </span>
                      <p className="mt-3 text-[16px] font-bold text-ink">Published!</p>
                      <p className="mt-1.5 text-[13px] text-ink-2">
                        Your listing is live at ₹{result.price?.selling_price_inr}.
                      </p>
                      <Link
                        href="/sell"
                        onClick={() => {
                          setResult(null);
                          setPublished(false);
                        }}
                        className="mt-5 inline-block rounded-xl border border-line bg-surface px-5 py-2.5 text-[13px] font-semibold text-ink-2 transition hover:border-brand-200"
                      >
                        Create another listing
                      </Link>
                    </div>
                  ) : rejected ? (
                    <div className="text-center">
                      <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-canvas text-muted">
                        <Icon name="ban" size={24} />
                      </span>
                      <p className="mt-3 text-[16px] font-bold text-ink">Not published</p>
                      <p className="mt-1.5 text-[13px] text-ink-2">
                        You rejected this listing. Nothing went live.
                      </p>
                      <Link
                        href="/sell"
                        onClick={() => {
                          setResult(null);
                          setRejected(false);
                        }}
                        className="mt-5 inline-block rounded-xl border border-line bg-surface px-5 py-2.5 text-[13px] font-semibold text-ink-2 transition hover:border-brand-200"
                      >
                        Start over
                      </Link>
                    </div>
                  ) : (
                    <>
                      <p className="text-[14px] font-bold text-ink">
                        Nothing goes live without your tap
                      </p>
                      <p className="mt-1 text-[12px] text-muted">
                        Change the title, description or price if the crew got it wrong — then
                        publish, or reject.
                      </p>
                      <ul className="mt-4 space-y-2">
                        {result.approvals?.map((a, i) =>
                          a.type === 'conflict' ? (
                            // The label disagrees with the listing. On a toy that's
                            // a child-safety statement, so it can't look like the
                            // routine "Publish this listing?" bullet next to it.
                            <li
                              key={`${a.type}-${i}`}
                              className="flex items-start gap-2.5 rounded-xl border border-danger/40 bg-danger-bg px-3.5 py-2.5 text-[13px] leading-relaxed text-danger"
                            >
                              <Icon name="alert" size={15} className="mt-0.5 shrink-0" />
                              <span>
                                <strong className="font-bold">Please check this before printing.</strong>{' '}
                                {a.summary}
                              </span>
                            </li>
                          ) : (
                            <li
                              key={`${a.type}-${i}`}
                              className="flex items-start gap-2.5 rounded-xl bg-canvas px-3.5 py-2.5 text-[13px] leading-relaxed text-ink-2"
                            >
                              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                              {a.summary}
                            </li>
                          ),
                        )}
                      </ul>

                      {/* She reads it in her own language before she's asked to
                          vouch for it — the English below is what publishes. */}
                      <ReviewInHerLanguage
                        title={result.listing?.title}
                        description={result.listing?.description}
                      />

                      {/* The missing details, answerable by voice in her own
                          language — not just listed at her in English. */}
                      <FillMissingDetails
                        listingId={result.id}
                        missingLabels={result.missing_attributes ?? []}
                        filled={attributeEdits}
                        onFilled={(key, value) =>
                          setAttributeEdits((prev) => ({ ...prev, [key]: value }))
                        }
                      />

                      {/* Seller edits — resumed into the graph via Command(resume).
                          The crew wrote these words; she gets the last one. */}
                      <div className="mt-4 grid gap-3.5 rounded-xl border border-line bg-canvas p-3.5">
                        <div>
                          <label
                            htmlFor="edit-title"
                            className="block text-[12px] font-semibold text-ink-2"
                          >
                            Title
                          </label>
                          <input
                            id="edit-title"
                            type="text"
                            value={editTitle ?? result.listing?.title ?? ''}
                            onChange={(e) => setEditTitle(e.target.value)}
                            className="mt-1.5 w-full rounded-lg border border-line bg-surface px-2.5 py-2 text-[13px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-100"
                          />
                        </div>

                        <div>
                          <label
                            htmlFor="edit-description"
                            className="block text-[12px] font-semibold text-ink-2"
                          >
                            Description
                          </label>
                          <textarea
                            id="edit-description"
                            rows={4}
                            value={editDescription ?? result.listing?.description ?? ''}
                            onChange={(e) => setEditDescription(e.target.value)}
                            className="mt-1.5 w-full resize-y rounded-lg border border-line bg-surface px-2.5 py-2 text-[13px] leading-relaxed text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-100"
                          />
                          <p className="mt-1 text-[10.5px] leading-relaxed text-muted">
                            These are your words to change — the crew only drafted them.
                          </p>
                        </div>

                        <label className="flex items-center justify-between text-[12px] font-semibold text-ink-2">
                          Price (₹)
                          <input
                            type="number"
                            inputMode="numeric"
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            placeholder={String(result.price?.selling_price_inr ?? '')}
                            className="w-28 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-right text-[13px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-100"
                          />
                        </label>
                        {/* Her break-even is deterministic; selling under it loses her money. */}
                        {(() => {
                          const p = Number(editPrice);
                          const floor = result.price?.discount_floor_inr;
                          if (!editPrice.trim() || !Number.isFinite(p) || !floor || p >= floor) return null;
                          return (
                            <p className="-mt-1 rounded-lg bg-warn-bg px-2.5 py-1.5 text-[11px] leading-relaxed text-warn">
                              {/* One template string, not JSX text around expressions —
                                  the space before the dash got eaten otherwise. */}
                              {`₹${p} is below your break-even of ₹${floor} — you'd lose money on every sale. You can still publish it if you mean to.`}
                            </p>
                          );
                        })()}

                        <input
                          type="text"
                          value={notes}
                          onChange={(e) => setNotes(e.target.value)}
                          placeholder="Add a note (optional)"
                          className="w-full rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-100"
                        />
                      </div>

                      <div className="mt-4 flex gap-2.5">
                        <button
                          onClick={onApprove}
                          disabled={approving}
                          className="flex-1 rounded-xl bg-brand py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-600 active:scale-[0.99] disabled:opacity-60"
                        >
                          {approving ? 'Publishing…' : buildEdits() ? 'Publish with changes' : 'Approve & publish'}
                        </button>
                        <button
                          onClick={onReject}
                          disabled={approving}
                          className="rounded-xl border border-line bg-surface px-5 py-3.5 text-[15px] font-semibold text-ink-2 transition hover:border-danger/40 hover:text-danger disabled:opacity-60"
                        >
                          Reject
                        </button>
                      </div>
                      <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-relaxed text-muted">
                        <Icon name="check" size={13} className="mt-0.5 shrink-0" />
                        By publishing, you confirm this is your own product and your own photo.
                      </p>
                    </>
                  )}
                </section>
              </>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
