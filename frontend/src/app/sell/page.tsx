'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { Header } from '@/components/Chrome';
import { AgentTimeline } from '@/components/AgentTimeline';
import { VoiceRecorder } from '@/components/VoiceRecorder';
import { ProductDetails } from '@/components/ProductDetails';
import { runListing, approveListing } from '@/lib/api';
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
  const [notes, setNotes] = useState('');
  const [approving, setApproving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

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
    try {
      const r = await runListing({ voiceText, marginPct: margin, photo });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  function buildEdits() {
    const edits: { price?: number } = {};
    const p = Number(editPrice);
    if (editPrice.trim() && Number.isFinite(p) && p > 0 && p !== result?.price?.selling_price_inr) {
      edits.price = Math.round(p);
    }
    return Object.keys(edits).length ? edits : undefined;
  }

  async function onApprove() {
    if (!result) return;
    setApproving(true);
    setError(null);
    const edits = buildEdits();
    try {
      await approveListing(result.id, true, notes || undefined, edits);
      // Reflect the published price (possibly edited) in the confirmation.
      if (edits?.price && result.price) {
        setResult({ ...result, price: { ...result.price, selling_price_inr: edits.price } });
      }
      setPublished(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not publish.');
    } finally {
      setApproving(false);
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
          <section className="card p-5 lg:sticky lg:top-24">
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
                <span className="grid h-14 w-14 shrink-0 place-items-center rounded-lg bg-brand-50 text-xl">
                  📷
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

          {/* ── OUTPUT ────────────────────────────── */}
          <div className="min-w-0 space-y-6">
            {!result && !loading && (
              <div className="card grid place-items-center px-6 py-20 text-center">
                <span className="text-4xl">🪡</span>
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
              <div className="card grid place-items-center px-6 py-20 text-center">
                <span className="h-9 w-9 animate-spin rounded-full border-[3px] border-brand-100 border-t-brand" />
                <p className="mt-5 text-[15px] font-semibold text-ink">The crew is working…</p>
                <p className="mt-1.5 text-[13px] text-muted">
                  Suno is listening, Niyam is checking the law.
                </p>
              </div>
            )}

            {/* Photo rejected */}
            {retake && (
              <div className="card border-saffron/40 p-6">
                <div className="flex items-start gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-warn-bg text-xl">
                    📷
                  </span>
                  <div>
                    <p className="text-[15px] font-bold text-ink">Suno stopped the pipeline</p>
                    <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">
                      {result?.reason}
                    </p>
                    <p className="mt-3 text-[12px] text-muted">
                      Nothing else ran — no point writing a listing around a photo buyers
                      can&apos;t see. Upload a clearer photo and run again.
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
                  {result.suno?.detected_language && (
                    <span className="ml-auto rounded-full bg-brand-50 px-2.5 py-1 font-mono text-[11px] text-brand-700">
                      lang: {result.suno.detected_language}
                    </span>
                  )}
                </div>

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
                      <p className="mt-4 rounded-xl bg-brand-50 px-4 py-3 text-[13px] italic leading-relaxed text-brand-700">
                        👩‍🌾 {result.listing.maker_story}
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
                    <div className="flex items-center gap-2">
                      <span className="text-lg">⚖️</span>
                      <p className="text-[13px] font-bold text-ink">Compliance</p>
                    </div>
                    <p
                      className={`mt-3 inline-block rounded-full px-2.5 py-1 text-[11px] font-bold ${
                        result.compliance?.compliance_ok
                          ? 'bg-ok-bg text-ok'
                          : 'bg-warn-bg text-warn'
                      }`}
                    >
                      {result.compliance?.compliance_ok ? '✓ Labels applied' : '⚠ Action needed'}
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
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🔄</span>
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
                  </div>

                  <div className="card p-5">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">📦</span>
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
                      <span className="text-3xl">🎉</span>
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
                      <span className="text-3xl">✋</span>
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
                        Review, edit anything, then publish — or reject.
                      </p>
                      <ul className="mt-4 space-y-2">
                        {result.approvals?.map((a) => (
                          <li
                            key={a.type}
                            className="flex items-start gap-2.5 rounded-xl bg-canvas px-3.5 py-2.5 text-[13px] leading-relaxed text-ink-2"
                          >
                            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                            {a.summary}
                          </li>
                        ))}
                      </ul>

                      {/* Seller edits — resumed into the graph via Command(resume) */}
                      <div className="mt-4 grid gap-3 rounded-xl border border-line bg-canvas p-3.5">
                        <label className="flex items-center justify-between text-[12px] font-semibold text-ink-2">
                          Adjust price (₹)
                          <input
                            type="number"
                            inputMode="numeric"
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            placeholder={String(result.price?.selling_price_inr ?? '')}
                            className="w-28 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-right text-[13px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-100"
                          />
                        </label>
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
