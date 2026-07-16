'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Header } from '@/components/Chrome';
import { Icon } from '@/components/icons';
import { logIn } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await logIn(phone.trim(), password);
      router.push('/sell');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not log you in.');
      setBusy(false); // stay on the form; on success we navigate away instead
    }
  }

  return (
    <>
      <Header />
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-5 py-12">
        <div className="card p-7">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand">
            <Icon name="sprout" size={22} />
          </span>
          <h1 className="mt-4 text-[22px] font-bold text-ink">Welcome back</h1>
          <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">
            Log in to write listings and publish them. Only you can publish yours.
          </p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="phone" className="block text-[13px] font-semibold text-ink">
                Phone number
              </label>
              <input
                id="phone"
                name="phone"
                type="tel"
                inputMode="numeric"
                autoComplete="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="10-digit phone number"
                className="mt-2 w-full rounded-xl border border-line bg-canvas px-3.5 py-3 text-[14px] text-ink outline-none transition placeholder:text-muted focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand-100"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-[13px] font-semibold text-ink">
                Password
              </label>
              <div className="relative mt-2">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                  className="w-full rounded-xl border border-line bg-canvas px-3.5 py-3 pr-16 text-[14px] text-ink outline-none transition placeholder:text-muted focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand-100"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] font-semibold text-muted transition hover:text-ink"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {error && (
              <p
                role="alert"
                className="rounded-lg bg-danger-bg px-3 py-2 text-[12px] leading-relaxed text-danger"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy || !phone.trim() || !password}
              className="w-full rounded-xl bg-brand py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-600 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? 'Logging in…' : 'Log in'}
            </button>
          </form>

          <p className="mt-5 text-center text-[13px] text-muted">
            New here?{' '}
            <Link href="/register" className="font-semibold text-brand hover:underline">
              Create an account
            </Link>
          </p>
        </div>

        <p className="mt-4 px-2 text-center text-[11px] leading-relaxed text-muted">
          Prototype: there is no password reset yet, and no OTP. Don&apos;t reuse a password that
          matters to you.
        </p>
      </main>
    </>
  );
}
