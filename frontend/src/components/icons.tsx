import type { ReactNode, SVGProps } from 'react';

export type IconName =
  | 'compass'
  | 'ear'
  | 'pen'
  | 'rupee'
  | 'scale'
  | 'refresh'
  | 'package'
  | 'bot'
  | 'catalog'
  | 'camera'
  | 'sparkles'
  | 'sprout'
  | 'success'
  | 'ban'
  | 'help'
  | 'check'
  | 'alert';

/**
 * One consistent line-icon set (24×24, stroke = currentColor). Replaces every
 * emoji in the UI so icons inherit text colour, scale crisply, and read as one
 * system across light/dark. Size via a width/height className or the size prop.
 */
export function Icon({
  name,
  size = 20,
  className,
  ...rest
}: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}

const PATHS: Record<IconName, ReactNode> = {
  // Mukhiya — the manager, plans & arbitrates
  compass: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="m15.8 8.2-2.1 5.6-5.5 2.1 2.1-5.6z" />
    </>
  ),
  // Suno — the ear, listens
  ear: (
    <>
      <path d="M6 8.5a6 6 0 0 1 12 0c0 5.5-5 5.5-5 9a3 3 0 0 1-6 0" />
      <path d="M14.5 8.5a2.5 2.5 0 0 0-5 0v1a1.8 1.8 0 1 1 0 3.6" />
    </>
  ),
  // Likho — the pen, writes
  pen: (
    <>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
    </>
  ),
  // Daam — the pricer
  rupee: (
    <>
      <path d="M6 4h12" />
      <path d="M6 9h12" />
      <path d="M6 14h3c3.3 0 5-1.9 5-5s-1.7-5-5-5" />
      <path d="M6 14l8 6" />
    </>
  ),
  // Niyam — compliance / balance
  scale: (
    <>
      <path d="M12 4v16" />
      <path d="M7 20h10" />
      <path d="M5 7h14" />
      <path d="M5 7 2.5 13a3 3 0 0 0 5 0z" />
      <path d="M19 7l-2.5 6a3 3 0 0 0 5 0z" />
    </>
  ),
  // Wapsi — returns / retry
  refresh: (
    <>
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M21 4v4h-4" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      <path d="M3 20v-4h4" />
    </>
  ),
  // Packaging
  package: (
    <>
      <path d="M21 8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <path d="m3.3 7 8.7 5 8.7-5" />
      <path d="M12 22V12" />
      <path d="m7.5 4.3 9 5.1" />
    </>
  ),
  // Generic agent
  bot: (
    <>
      <rect x="4" y="8" width="16" height="12" rx="2.5" />
      <path d="M12 8V4" />
      <circle cx="12" cy="3" r="1" />
      <path d="M9 13h.01M15 13h.01" />
      <path d="M2 14v2M22 14v2" />
    </>
  ),
  // Cataloging
  catalog: (
    <>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <path d="M14 3v6h6" />
      <path d="M8 13h8M8 17h8M8 9h2" />
    </>
  ),
  // Photography / photo upload
  camera: (
    <>
      <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z" />
      <circle cx="12" cy="13" r="3.2" />
    </>
  ),
  // Standing by / craft
  sparkles: (
    <>
      <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
      <path d="M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8z" />
    </>
  ),
  // Maker / artisan (rural, handmade)
  sprout: (
    <>
      <path d="M7 20h10" />
      <path d="M12 20c0-5 0-7 2-9" />
      <path d="M12 11c-1-3-3.5-4.5-7-4 .5 3.5 2 5 5 5" />
      <path d="M13 9c.5-3 2.5-4.5 6-4-.5 3.5-2 5-5 5" />
    </>
  ),
  // Published / success
  success: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </>
  ),
  // Rejected
  ban: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="m5.5 5.5 13 13" />
    </>
  ),
  // Clarification / question
  help: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M9.2 9.3a2.8 2.8 0 0 1 5.4 1c0 1.9-2.8 2.5-2.8 2.5" />
      <path d="M12 17h.01" />
    </>
  ),
  check: <path d="M20 6 9 17l-5-5" />,
  alert: (
    <>
      <path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4M12 17h.01" />
    </>
  ),
};
