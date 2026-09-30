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
