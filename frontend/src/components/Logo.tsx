// The Pramaan AI seal: navy circle with a saffron -> white -> green tick.
export function LogoSeal({ size = 42 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" style={{ flexShrink: 0 }}>
      <circle cx="32" cy="32" r="31" fill="var(--navy-dark)" />
      <circle cx="32" cy="32" r="25" fill="none" stroke="#FFFFFF" strokeOpacity="0.45" strokeWidth="1.2" strokeDasharray="1.6 3.4" />
      <path d="M19.5 33.5 28 42" fill="none" stroke="var(--saffron)" strokeWidth="6" strokeLinecap="round" />
      <path d="M28 42 45.5 22" fill="none" stroke="var(--logo-green)" strokeWidth="6" strokeLinecap="round" />
      <circle cx="28" cy="42" r="3.8" fill="#FFFFFF" />
    </svg>
  )
}

// Seal + name + tagline, as shown at the top of the sidebar.
export function Logo() {
  return (
    <div className="logo">
      <LogoSeal />
      <div className="logo-text">
        <span className="logo-name">Pramaan AI</span>
        <span className="logo-tagline">प्रमाण · Content you can prove</span>
      </div>
    </div>
  )
}
