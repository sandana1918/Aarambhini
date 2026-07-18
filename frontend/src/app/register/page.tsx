'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Header } from '@/components/Chrome';
import { Icon } from '@/components/icons';
import { registerSeller } from '@/lib/api';

/** Mirrors MIN_PASSWORD_LENGTH in backend/auth.py — the server enforces it too. */
const MIN_PASSWORD = 8;

// Suno detects the language of each voice note on its own; this is only the
// language we'd prefer to speak back to her in.
const LANGUAGES = [
  { code: 'hi', label: 'हिन्दी — Hindi' },
  { code: 'ta', label: 'தமிழ் — Tamil' },
  { code: 'te', label: 'తెలుగు — Telugu' },
  { code: 'bn', label: 'বাংলা — Bengali' },
  { code: 'mr', label: 'मराठी — Marathi' },
  { code: 'kn', label: 'ಕನ್ನಡ — Kannada' },
  { code: 'ml', label: 'മലയാളം — Malayalam' },
  { code: 'or', label: 'ଓଡ଼ିଆ — Odia' },
  { code: 'gu', label: 'ગુજરાતી — Gujarati' },
  { code: 'pa', label: 'ਪੰਜਾਬੀ — Punjabi' },
  { code: 'en', label: 'English' },
];

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [shgName, setShgName] = useState('');
  const [language, setLanguage] = useState('hi');
  // Address is required: it's the packer name+address the law demands on every
  // printed label. Without it the compliance label reads "<Insert Name and
  // Address>" — a blank on the one document the buyer and the inspector see.
  const [addressLine, setAddressLine] = useState('');
  const [district, setDistrict] = useState('');
  const [stateName, setStateName] = useState('');
  const [pincode, setPincode] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phoneDigits = phone.replace(/\D/g, '');
  const mismatch = confirm.length > 0 && password !== confirm;
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;
  const canSubmit =
    name.trim().length > 0 &&
    phoneDigits.length >= 8 &&
    addressLine.trim().length > 0 &&
    district.trim().length > 0 &&
    stateName.trim().length > 0 &&
    password.length >= MIN_PASSWORD &&
    password === confirm;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await registerSeller({
        name: name.trim(),
        phone: phoneDigits,
        password,
        preferred_language: language,
        shg_name: shgName.trim() || undefined,
        address: {
          line: addressLine.trim(),
          district: district.trim(),
          state: stateName.trim(),
          pincode: pincode.trim(),
        },
      });
      router.push('/sell'); // register returns a session — straight to work
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create your account.');
      setBusy(false);
    }
  }

  const field =
    'mt-2 w-full rounded-xl border border-line bg-canvas px-3.5 py-3 text-[14px] text-ink outline-none transition placeholder:text-muted focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand-100';

  return (
    <>
      <Header />
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-5 py-12">
        <div className="card p-7">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand">
            <Icon name="sparkles" size={22} />
          </span>
          <h1 className="mt-4 text-[22px] font-bold text-ink">Create your account</h1>
          <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">
            One account, so your listings stay yours — and only you can publish them.
          </p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="name" className="block text-[13px] font-semibold text-ink">
                Your name
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Lakshmi Ammal"
                className={field}
              />
            </div>

            <div>
              <label htmlFor="phone" className="block text-[13px] font-semibold text-ink">
                Phone number
              </label>
              <input
                id="phone"
                type="tel"
                inputMode="numeric"
                autoComplete="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="10-digit phone number"
                className={field}
              />
              <p className="mt-1.5 text-[11px] text-muted">This is how you&apos;ll log in.</p>
            </div>

            <div>
              <label htmlFor="shg" className="block text-[13px] font-semibold text-ink">
                Self-help group <span className="font-normal text-muted">(optional)</span>
              </label>
              <input
                id="shg"
                type="text"
                value={shgName}
                onChange={(e) => setShgName(e.target.value)}
                placeholder="e.g. Kaveri Mahila Sangam"
                className={field}
              />
            </div>

            <div>
              <label htmlFor="addr" className="block text-[13px] font-semibold text-ink">
                Your address
              </label>
              <p className="mt-1 text-[11px] leading-relaxed text-muted">
                The law requires your name and address on every product label — this is
                what goes there, so buyers and inspectors can reach you.
              </p>
              <input
                id="addr"
                type="text"
                value={addressLine}
                onChange={(e) => setAddressLine(e.target.value)}
                placeholder="House / street / village"
                className={field}
              />
              <div className="mt-2 grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  placeholder="District"
                  className={field.replace('mt-2 ', '')}
                />
                <input
                  type="text"
                  value={stateName}
                  onChange={(e) => setStateName(e.target.value)}
                  placeholder="State"
                  className={field.replace('mt-2 ', '')}
                />
              </div>
              <input
                type="text"
                inputMode="numeric"
                value={pincode}
                onChange={(e) => setPincode(e.target.value)}
                placeholder="PIN code"
                className={field}
              />
            </div>

            <div>
              <label htmlFor="language" className="block text-[13px] font-semibold text-ink">
                Language you prefer
              </label>
              <select
                id="language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className={`${field} cursor-pointer`}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
              <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
                You can still speak your voice notes in any language — Suno detects it each time.
              </p>
            </div>

            <div>
              <label htmlFor="password" className="block text-[13px] font-semibold text-ink">
                Password
              </label>
              <div className="relative mt-2">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  minLength={MIN_PASSWORD}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={`At least ${MIN_PASSWORD} characters`}
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
              {tooShort && (
                <p className="mt-1.5 text-[11px] text-warn">
                  A little longer — {MIN_PASSWORD} characters minimum.
                </p>
              )}
            </div>

            <div>
              <label htmlFor="confirm" className="block text-[13px] font-semibold text-ink">
                Confirm password
              </label>
              <input
                id="confirm"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Type it once more"
                className={field}
              />
              {mismatch && (
                <p className="mt-1.5 text-[11px] text-warn">
                  These two don&apos;t match yet.
                </p>
              )}
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
              disabled={busy || !canSubmit}
              className="w-full rounded-xl bg-brand py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-600 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? 'Creating your account…' : 'Create account'}
            </button>
          </form>

          <p className="mt-5 text-center text-[13px] text-muted">
            Already registered?{' '}
            <Link href="/login" className="font-semibold text-brand hover:underline">
              Log in
            </Link>
          </p>
        </div>

        <p className="mt-4 px-2 text-center text-[11px] leading-relaxed text-muted">
          Prototype: there is no password reset yet, so a forgotten password can&apos;t be
          recovered. Don&apos;t reuse a password that matters to you.
        </p>
      </main>
    </>
  );
}
