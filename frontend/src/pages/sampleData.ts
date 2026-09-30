// SAMPLE DATA ONLY — copied from the design so the dashboard looks right.
// Stage 3 replaces this with real jobs from the backend.

export type JobStatus = 'approved' | 'in_review' | 'sent_back' | 'generating' | 'draft'

export type SampleJob = {
  title: string
  kind: string
  status: JobStatus
  progress?: number
  outputs: number
  languages: string
  updated: string
}

export const SAMPLE_STATS = [
  { label: 'Jobs this week', value: '12', note: '+3 from last week', icon: 'history', tone: 'saffron' },
  { label: 'Outputs approved', value: '64', note: 'Across 7 formats', icon: 'shieldCheck', tone: 'green' },
  { label: 'Hours saved (est.)', value: '41', note: 'Compared with manual writing', icon: 'clock', tone: 'navy' },
  { label: 'Languages used', value: '7', note: 'हिन्दी, தமிழ், বাংলা +4', icon: 'globe', tone: 'saffron' },
] as const

export const SAMPLE_JOBS: SampleJob[] = [
  { title: 'Ransomware attack on hospital networks', kind: 'Advisory kit', status: 'approved', outputs: 7, languages: 'EN · हि · த', updated: '10:21' },
  { title: 'Phishing using fake electricity bills', kind: 'Public awareness kit', status: 'in_review', outputs: 5, languages: 'EN · हि', updated: '09:40' },
  { title: 'Monsoon flood advisory, coastal districts', kind: 'Emergency alert', status: 'sent_back', outputs: 4, languages: 'EN · த · తె', updated: 'Yesterday' },
  { title: 'New data protection rules explained', kind: 'Explainer kit', status: 'generating', progress: 62, outputs: 6, languages: 'EN', updated: 'Now' },
  { title: 'Weekly threat summary, week 39', kind: 'Executive brief', status: 'draft', outputs: 3, languages: 'EN', updated: 'Mon' },
]

export const SAMPLE_ATTENTION = [
  { tone: 'red', icon: 'arrowLeft', title: 'Sent back: Monsoon flood advisory', detail: 'Arjun: “Check the district names in the Tamil version.”' },
  { tone: 'yellow', icon: 'warning', title: '1 sentence not found in source', detail: 'Phishing job · advisory, paragraph 2' },
  { tone: 'saffron', icon: 'folder', title: 'Watch folder drafted 2 reports', detail: 'Ready for you to check and send' },
] as const
