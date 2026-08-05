'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Header } from '@/components/Chrome';
import { Icon } from '@/components/icons';
import {
  listMyListings,
  getStoreStatus,
  publishToStore,
  type ListingSummary,
} from '@/lib/api';
import { loadSession, type Session } from '@/lib/session';

/** How each status reads on the shelf: a badge, and what she can do next. */
const STATUS: Record<string, { label: string; badge: string }> = {
  ready_for_approval: { label: 'Ready to publish', badge: 'bg-ok-bg text-ok' },
  needs_clarification: { label: 'Needs a detail', badge: 'bg-brand-50 text-brand-700' },
  needs_retake: { label: 'Photo rejected', badge: 'bg-warn-bg text-warn' },
  published: { label: 'Approved', badge: 'bg-brand-50 text-brand-700' },
  rejected_by_seller: { label: 'Not published', badge: 'bg-canvas text-muted' },
};

function statusMeta(status: string) {
  return STATUS[status] ?? { label: status, badge: 'bg-canvas text-muted' };
}

function formatDate(iso: string | null) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return '';
  }
}

export default function ListingsPage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [listings, setListings] = useState<ListingSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [storeConfigured, setStoreConfigured] = useState(false);
  // Per-card publish-to-store state, keyed by listing id.
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<Record<string, string>>({});

  // Confirm the stored token with the server before trusting it, exactly as the
  // sell page does — a dead token should send her to log in, not show an empty
  // shelf that looks like she has no listings.
  useEffect(() => {
    let active = true;
    (async () => {
      const stored = loadSession();
      if (!stored) {
        router.replace('/login');
        return;
      }
      try {
        const rows = await listMyListings();
        if (!active) return;
        setSession(stored);
        setListings(rows);
      } catch (e) {
        if (!active) return;
        // 401 clears the session inside the client; bounce to login.
        if (!loadSession()) router.replace('/login');
        else setError(e instanceof Error ? e.message : 'Could not load your listings.');
      }
    })();
    return () => {
      active = false;
    };
  }, [router]);

  useEffect(() => {
    let active = true;
    (async () => {
      const { configured } = await getStoreStatus();
      if (active) setStoreConfigured(configured);
    })();
    return () => {
      active = false;
    };
  }, []);

  async function onPublish(id: string) {
    setBusyId(id);
    setRowError((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const result = await publishToStore(id);
      // Reflect the new live state in place, so the button becomes a link.
      setListings((prev) =>
        (prev ?? []).map((l) =>
          l.id === id
            ? { ...l, on_store: true, store_url: result.storefront_url ?? result.admin_url }
            : l,
        ),
      );
    } catch (e) {
      setRowError((prev) => ({
        ...prev,
        [id]: e instanceof Error ? e.message : 'Could not send it to your store.',
      }));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-8">
        <div className="mb-6 flex items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-ink">Your listings</h1>
            <p className="mt-1.5 text-[14px] text-muted">
              Everything you&apos;ve started — approve or publish whenever you&apos;re ready.
            </p>
          </div>
          <Link
            href="/sell"
            className="shrink-0 rounded-xl bg-brand px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-brand-600 active:scale-[0.98]"
          >
            + New listing
          </Link>
        </div>

        {error && (
          <p className="rounded-lg bg-danger-bg px-3 py-2 text-[12px] text-danger">{error}</p>
        )}

        {/* Loading — session unconfirmed or listings not back yet. */}
        {!session || listings === null ? (
          <div className="card flex items-center gap-3 p-5">
            <span className="h-5 w-5 animate-spin rounded-full border-[3px] border-brand-100 border-t-brand" />
            <p className="text-[13px] text-muted">Loading your listings…</p>
          </div>
        ) : listings.length === 0 ? (
          <div className="card p-8 text-center">
            <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-brand-50 text-brand">
              <Icon name="sprout" size={24} />
            </span>
            <p className="mt-3 text-[15px] font-bold text-ink">No listings yet</p>
            <p className="mx-auto mt-1.5 max-w-sm text-[13px] text-muted">
              Record one voice note and add a photo — the crew turns it into a ready-to-publish
              listing you can come back to any time.
            </p>
            <Link
              href="/sell"
              className="mt-5 inline-block rounded-xl bg-brand px-5 py-2.5 text-[13px] font-semibold text-white transition hover:bg-brand-600"
            >
              Create your first listing
            </Link>
          </div>
        ) : (
          <ul className="space-y-3">
            {listings.map((l) => {
              const meta = statusMeta(l.status);
              const resumable = l.status === 'ready_for_approval' || l.status === 'needs_clarification';
              return (
                <li key={l.id} className="card flex items-center gap-4 p-4">
                  {/* Thumbnail (embedded data URI) or a placeholder. */}
                  {l.thumb ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={l.thumb}
                      alt=""
                      className="h-16 w-16 shrink-0 rounded-xl object-cover"
                    />
                  ) : (
                    <span className="grid h-16 w-16 shrink-0 place-items-center rounded-xl bg-canvas text-muted">
                      <Icon name="camera" size={20} />
                    </span>
                  )}

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold ${meta.badge}`}
                      >
                        {meta.label}
                      </span>
                      {l.on_store && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-ok-bg px-2 py-0.5 text-[10.5px] font-bold text-ok">
                          <Icon name="check" size={10} /> Live on store
                        </span>
                      )}
                    </div>
                    <p className="mt-1.5 truncate text-[14px] font-semibold text-ink">
                      {l.title ?? 'Untitled listing'}
                    </p>
                    <p className="mt-0.5 text-[12px] text-muted">
                      {l.price ? `₹${l.price}` : 'No price yet'}
                      {l.created_at ? ` · ${formatDate(l.created_at)}` : ''}
                    </p>
                    {rowError[l.id] && (
                      <p className="mt-1.5 rounded-lg bg-danger-bg px-2 py-1 text-[11px] text-danger">
                        {rowError[l.id]}
                      </p>
                    )}
                  </div>

                  {/* The one action that fits this listing's state. */}
                  <div className="shrink-0">
                    {resumable ? (
                      <Link
                        href={`/sell?id=${l.id}`}
                        className="rounded-xl bg-brand px-4 py-2 text-[12.5px] font-semibold text-white transition hover:bg-brand-600"
                      >
                        {l.status === 'ready_for_approval' ? 'Review & publish' : 'Finish'}
                      </Link>
                    ) : l.status === 'published' && l.on_store ? (
                      <a
                        href={l.store_url ?? '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-xl border border-line bg-surface px-4 py-2 text-[12.5px] font-semibold text-ink-2 transition hover:border-brand-200"
                      >
                        View on store
                      </a>
                    ) : l.status === 'published' && storeConfigured ? (
                      <button
                        onClick={() => onPublish(l.id)}
                        disabled={busyId === l.id}
                        className="rounded-xl bg-brand px-4 py-2 text-[12.5px] font-semibold text-white transition hover:bg-brand-600 disabled:opacity-60"
                      >
                        {busyId === l.id ? 'Sending…' : 'Publish to store'}
                      </button>
                    ) : l.status === 'needs_retake' ? (
                      <Link
                        href="/sell"
                        className="rounded-xl border border-line bg-surface px-4 py-2 text-[12.5px] font-semibold text-ink-2 transition hover:border-brand-200"
                      >
                        Start over
                      </Link>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </>
  );
}
