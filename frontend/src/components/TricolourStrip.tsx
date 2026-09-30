// Thin saffron / white / green strip shown at the very top of the page.
export function TricolourStrip() {
  return (
    <div className="tricolour" aria-hidden="true">
      <span style={{ background: 'var(--saffron)' }} />
      <span style={{ background: '#FFFFFF' }} />
      <span style={{ background: 'var(--green)' }} />
    </div>
  )
}
