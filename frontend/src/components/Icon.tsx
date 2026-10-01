// Line icons copied from the clickable prototype. Each icon is a list of SVG path "d" values.
const ICONS = {
  home: ['M3 11 12 4l9 7', 'M5 10v10h14V10'],
  plus: ['M12 5v14M5 12h14'],
  history: ['M3 12a9 9 0 1 0 3-6.7', 'M3 4v5h5', 'M12 8v4l3 2'],
  siren: ['M7 18v-6a5 5 0 0 1 10 0v6', 'M5 18h14v3H5z', 'M12 2v2M4.2 5.2l1.4 1.4M19.8 5.2l-1.4 1.4'],
  folder: ['M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'],
  scan: ['M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3', 'M7 12h10'],
  bell: ['M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z', 'M10 20a2 2 0 0 0 4 0'],
  sliders: ['M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1', 'M15 4v4M9 10v4M17 16v4'],
  wifiOff: ['M2 8.8a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 19.5h.01', 'M3 3l18 18'],
  signOut: ['M15 4h4v16h-4', 'M10 8l-4 4 4 4M6 12h11'],
  search: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z', 'm20 20-4-4'],
  chip: ['M7 7h10v10H7z', 'M9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4'],
  globe: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M3 12h18', 'M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z'],
  shieldCheck: ['M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6l-7-3Z', 'm9 12 2 2 4-4'],
  clock: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 7v5l3 2'],
  arrowRight: ['M5 12h14M13 6l6 6-6 6'],
  arrowLeft: ['M19 12H5M11 6l-6 6 6 6'],
  chevronRight: ['m9 6 6 6-6 6'],
  check: ['m5 12 5 5L20 7'],
  eye: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z', 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z'],
  spinner: ['M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.8 2.8M14.9 14.9l2.8 2.8M6.3 17.7l2.8-2.8M14.9 9.1l2.8-2.8'],
  pencil: ['M4 20h4L19 9l-4-4L4 16z', 'm13.5 6.5 4 4'],
  warning: ['M12 3 2 20h20L12 3Z', 'M12 10v4M12 17h.01'],
  cross: ['M6 6l12 12M18 6 6 18'],
  upload: ['M12 16V4', 'm6 10 6-6 6 6', 'M4 20h16'],
  file: ['M6 3h8l4 4v14H6z', 'M14 3v4h4'],
  refresh: ['M20 11a8 8 0 1 0-2.3 5.7', 'M20 4v7h-7'],
  code: ['m8 8-4 4 4 4', 'm16 8 4 4-4 4'],
  download: ['M12 4v12', 'm6 10 6 6 6-6', 'M4 20h16'],
  box: ['M3 7l9-4 9 4-9 4-9-4z', 'M3 7v10l9 4 9-4V7', 'M12 11v10'],
  // Stage 6A: safety check
  lock: ['M6 11h12v10H6z', 'M9 11V8a3 3 0 0 1 6 0v3'],
  hash: ['M5 9h14M5 15h14', 'M10 4 8 20M16 4l-2 16'],
  mail: ['M3 6h18v12H3z', 'm3 7 9 6 9-6'],
  user: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21a8 8 0 0 1 16 0'],
  phone: ['M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z', 'M11 18h2'],
  key: ['M8 15a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M11.5 11H21', 'M18 11v3M15 11v2'],
  mapPin: ['M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12z', 'M12 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z'],
  target: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M12 12h.01'],
  card: ['M3 6h18v12H3z', 'M7 10h4M7 14h6', 'M15 10h2v4h-2z'],
  shield: ['M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6l-7-3Z'],
  eyeOff: ['M3 3l18 18', 'M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.2', 'M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a9.6 9.6 0 0 0 5.4-1.6', 'M9.9 9.9a3 3 0 0 0 4.2 4.2'],
  // Stage 9A: results tabs, kit, alerts, watch folder, notifications (same line style as the prototype)
  menu: ['M4 6h16M4 12h16M4 18h16'],
  send: ['M21 3 3 10.5l7 2.5 2.5 7z', 'M10 13l11-10'],
  copy: ['M9 9h11v11H9z', 'M5 15H4V4h11v1'],
  monitor: ['M3 4h18v12H3z', 'M12 16v4M8 20h8'],
  video: ['M3 6h13v12H3z', 'm16 10 5-3v10l-5-3'],
  share: ['M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', 'm8.6 13.5 6.8 4M15.4 6.5l-6.8 4'],
  image: ['M4 5h16v14H4z', 'm4 16 5-5 4 4 3-3 4 4', 'M15.5 9.5h.01'],
  summary: ['M4 5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2z', 'M4 19V5'],
  mic: ['M12 3a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z', 'M5 11a7 7 0 0 0 14 0', 'M12 18v3'],
  bolt: ['M13 2 4 14h7l-1 8 9-12h-7z'],
  volume: ['M4 9h4l5-4v14l-5-4H4z', 'M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11'],
  award: ['M12 15a6 6 0 1 0 0-12 6 6 0 0 0 0 12z', 'M8.5 13.5 7 21l5-3 5 3-1.5-7.5'],
  play: ['M7 4v16l13-8z'],
  filter: ['M4 5h16l-6 8v6l-4-2v-4z'],
  calendar: ['M4 6h16v14H4z', 'M4 10h16M8 3v4M16 3v4'],
  chevronDown: ['m6 9 6 6 6-6'],
  chevronLeft: ['m15 6-6 6 6 6'],
  compare: ['M8 3v18M16 3v18', 'M3 8h5M16 16h5'],
  subtitles: ['M3 5h18v14H3z', 'M7 15h4M13 15h4M7 11h10'],
  usb: ['M9 2h6v6H9z', 'M7 8h10v9a5 5 0 0 1-10 0z', 'M12 13v4'],
} as const

export type IconName = keyof typeof ICONS

type Props = {
  name: IconName
  size?: number
  color?: string
  strokeWidth?: number
}

export function Icon({ name, size = 20, color = 'currentColor', strokeWidth = 1.9 }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      {ICONS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}
