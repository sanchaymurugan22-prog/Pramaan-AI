import type { Finding, SafetyChoice, Tlp } from '../api'
import type { IconName } from '../components/Icon'

// Words and icons shared by the Safety check step and the Safety section of the Results page.

export const TLP_LEVELS: { tlp: Tlp; title: string; description: string }[] = [
  { tlp: 'RED', title: 'Named people only', description: 'Public formats are switched off.' },
  { tlp: 'AMBER', title: 'Your organisation', description: 'Shared inside your organisation. Public formats are switched off.' },
  { tlp: 'GREEN', title: 'Wider community', description: 'All formats. Hidden details are masked in public ones.' },
  { tlp: 'CLEAR', title: 'Anyone', description: 'For fully public material.' },
]

export const CHOICES: { value: SafetyChoice; label: string }[] = [
  { value: 'hide_public', label: 'Hide in public outputs' },
  { value: 'hide_all', label: 'Hide everywhere' },
  { value: 'keep', label: 'Keep' },
]

// Indicators: the same three choices, in words that fit them
export const INDICATOR_CHOICES: { value: SafetyChoice; label: string }[] = [
  { value: 'hide_public', label: 'Advisory only, not in public posts' },
  { value: 'hide_all', label: 'Hide everywhere' },
  { value: 'keep', label: 'Keep everywhere' },
]

export const choiceLabel = (choice: SafetyChoice) => CHOICES.find((c) => c.value === choice)?.label ?? choice

// Icon for each kind of finding
export function findingIcon(finding: Finding): IconName {
  switch (finding.kind) {
    case 'aadhaar':
    case 'pan':
    case 'passport':
      return 'card'
    case 'phone':
      return 'phone'
    case 'email':
      return 'mail'
    case 'bank_account':
    case 'ifsc':
      return 'lock'
    case 'private_ip':
    case 'internal_host':
      return 'hash'
    case 'password':
    case 'api_key':
    case 'token':
    case 'private_key':
      return 'key'
    case 'classification':
      return 'lock'
    case 'gps':
    case 'vehicle':
      return 'mapPin'
    default:
      return 'target'
  }
}

// The rows that say "None found" when nothing of that kind was found (as in the design)
export const ALWAYS_CHECKED: { label: string; kinds: string[]; icon: IconName }[] = [
  { label: 'Aadhaar or PAN numbers', kinds: ['aadhaar', 'pan'], icon: 'user' },
  { label: 'Phone numbers', kinds: ['phone'], icon: 'phone' },
  { label: 'Email addresses', kinds: ['email'], icon: 'mail' },
  { label: 'Passwords or access keys', kinds: ['password', 'api_key', 'token', 'private_key'], icon: 'key' },
  { label: 'Internal addresses', kinds: ['private_ip', 'internal_host'], icon: 'hash' },
  { label: 'Classification markings', kinds: ['classification'], icon: 'lock' },
]

// "S1 p.1, 4" — where a finding is, short
export function whereFound(finding: Finding): string {
  const bySource = new Map<string, Set<number>>()
  finding.occurrences.forEach((o) => {
    if (!bySource.has(o.source_id)) bySource.set(o.source_id, new Set())
    bySource.get(o.source_id)!.add(o.page)
  })
  return [...bySource.entries()]
    .map(([source, pages]) => `${bySource.size > 1 ? `${source} ` : ''}${pages.size > 1 ? 'Pages' : 'Page'} ${[...pages].join(', ')}`)
    .join(' · ')
}
