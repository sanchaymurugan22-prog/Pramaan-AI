// SAMPLE DATA ONLY — copied from the design so the dashboard looks right.
// Recent jobs are real since Stage 3; the stats and "needs attention" items are still samples.

export const SAMPLE_STATS = [
  { label: 'Jobs this week', value: '12', note: '+3 from last week', icon: 'history', tone: 'saffron' },
  { label: 'Outputs approved', value: '64', note: 'Across 7 formats', icon: 'shieldCheck', tone: 'green' },
  { label: 'Hours saved (est.)', value: '41', note: 'Compared with manual writing', icon: 'clock', tone: 'navy' },
  { label: 'Languages used', value: '7', note: 'हिन्दी, தமிழ், বাংলা +4', icon: 'globe', tone: 'saffron' },
] as const

export const SAMPLE_ATTENTION = [
  { tone: 'red', icon: 'arrowLeft', title: 'Sent back: Monsoon flood advisory', detail: 'Arjun: “Check the district names in the Tamil version.”' },
  { tone: 'yellow', icon: 'warning', title: '1 sentence not found in source', detail: 'Phishing job · advisory, paragraph 2' },
  { tone: 'saffron', icon: 'folder', title: 'Watch folder drafted 2 reports', detail: 'Ready for you to check and send' },
] as const
