import type { ReactNode } from 'react'

type Name = 'shield' | 'arrow' | 'upload' | 'check' | 'alert' | 'sparkle' | 'refresh' | 'clock' | 'file' | 'plus'
export function Icon({ name, size = 20 }: { name: Name; size?: number }) {
  const paths: Record<Name, ReactNode> = {
    shield: <path d="M12 3 4.5 6v5.4c0 4.6 3.1 8.8 7.5 9.6 4.4-.8 7.5-5 7.5-9.6V6L12 3Zm-3 9 2 2 4-4" />,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    upload: <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" />,
    check: <path d="m5 12 4 4L19 6" />,
    alert: <path d="M12 3 2.8 19h18.4L12 3Zm0 6v4m0 3h.01" />,
    sparkle: <path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Zm7 11 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7L19 14Z" />,
    refresh: <path d="M20 11a8.1 8.1 0 0 0-14.4-3L4 10m0-6v6h6m-6 3a8.1 8.1 0 0 0 14.4 3L20 14m0 6v-6h-6" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    file: <path d="M6 3h8l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm8 0v5h5M8 13h8M8 17h8" />,
    plus: <path d="M12 5v14M5 12h14" />,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
