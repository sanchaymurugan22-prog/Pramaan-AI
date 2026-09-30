import type { Tlp } from '../api'

// Traffic Light Protocol label: coloured letters on black, as the TLP 2.0 standard asks.
export function TlpLabel({ tlp }: { tlp: Tlp }) {
  return <span className={`tlp tlp-${tlp.toLowerCase()}`}>TLP:{tlp}</span>
}
