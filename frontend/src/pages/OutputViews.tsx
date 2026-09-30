// Readable views of each output type. The JSON shapes come from
// backend/app/pipeline/output_types.py. Every piece of text shows the facts it is based on;
// text that is not linked to any fact is highlighted in yellow (it must never be hidden).
import type { FactSheet } from '../api'
import type { FactLookup } from './format'

// ---- shapes of the output JSON ------------------------------------------------------------

type Grounded = { text: string; fact_ids: string[] }
type XThread = { tweets: Grounded[] }
type LinkedInPost = { paragraphs: Grounded[]; hashtags: string[] }
type ExecutiveSummary = { title: string; bottom_line: Grounded; key_points: Grounded[]; actions_needed: Grounded[] }
type Infographic = {
  headline: string
  subheadline: string
  key_numbers: { value: string; label: string; fact_ids: string[] }[]
  steps: Grounded[]
  layout: string
}
type Advisory = {
  title: string
  severity: string
  overview: Grounded
  affected: Grounded[]
  description: Grounded
  impact: Grounded
  recommendations: Grounded[]
  indicators?: FactSheet['indicators']
}
type Presentation = {
  title: string
  slides: { title: string; bullets: string[]; speaker_notes: string; fact_ids: string[] }[]
}
type VideoPackage = {
  title: string
  duration_seconds: number
  scenes: { visual: string; on_screen_text: string; narration: string; fact_ids: string[]; start: number; end: number }[]
  subtitles: { index: number; start: string; end: string; text: string }[]
}

// ---- grounding helpers --------------------------------------------------------------------

function FactChips({ ids, facts }: { ids: string[]; facts: FactLookup }) {
  const known = (ids ?? []).filter((id) => facts.has(id))
  if (known.length === 0) return <span className="not-linked">Not linked to a fact</span>
  return (
    <span className="fact-chips">
      {known.map((id) => {
        const fact = facts.get(id)!
        return (
          <span key={id} className="fact-chip" title={`${id}: ${fact.text}${fact.page ? ` (page ${fact.page})` : ''}`}>
            {id}
          </span>
        )
      })}
    </span>
  )
}

// A piece of text with its fact chips; yellow if it is not linked to any fact.
function GroundedText({ item, facts, as = 'p' }: { item?: Grounded; facts: FactLookup; as?: 'p' | 'li' }) {
  if (!item) return null
  const linked = (item.fact_ids ?? []).some((id) => facts.has(id))
  const Tag = as
  return (
    <Tag className={linked ? 'grounded' : 'grounded is-unlinked'}>
      {item.text} <FactChips ids={item.fact_ids} facts={facts} />
    </Tag>
  )
}

const list = <T,>(value: T[] | undefined): T[] => value ?? []

// ---- one view per output type -------------------------------------------------------------

function XThreadView({ c, facts }: { c: XThread; facts: FactLookup }) {
  return (
    <ol className="tweet-list">
      {list(c.tweets).map((tweet, i) => (
        <li key={i} className="tweet">
          <GroundedText item={tweet} facts={facts} />
          <span className={tweet.text.length > 280 ? 'tweet-count is-over' : 'tweet-count'}>
            {i + 1}/{c.tweets.length} · {tweet.text.length}/280
          </span>
        </li>
      ))}
    </ol>
  )
}

function LinkedInView({ c, facts }: { c: LinkedInPost; facts: FactLookup }) {
  return (
    <div className="stack gap-10">
      {list(c.paragraphs).map((p, i) => (
        <GroundedText key={i} item={p} facts={facts} />
      ))}
      {list(c.hashtags).length > 0 && <p className="hashtags">{c.hashtags.map((t) => `#${t}`).join(' ')}</p>}
    </div>
  )
}

function ExecutiveSummaryView({ c, facts }: { c: ExecutiveSummary; facts: FactLookup }) {
  return (
    <div className="stack gap-12">
      <h3>{c.title}</h3>
      <div className="bottom-line">
        <span className="section-label">Bottom line</span>
        <GroundedText item={c.bottom_line} facts={facts} />
      </div>
      <span className="section-label">Key points</span>
      <ul className="clean-list">
        {list(c.key_points).map((p, i) => (
          <GroundedText key={i} item={p} facts={facts} as="li" />
        ))}
      </ul>
      <span className="section-label">Actions needed</span>
      <ol className="clean-list numbered">
        {list(c.actions_needed).map((p, i) => (
          <GroundedText key={i} item={p} facts={facts} as="li" />
        ))}
      </ol>
    </div>
  )
}

function InfographicView({ c, facts }: { c: Infographic; facts: FactLookup }) {
  return (
    <div className="infographic">
      <div className="infographic-head">
        <h3>{c.headline}</h3>
        <p>{c.subheadline}</p>
      </div>
      <div className="number-tiles">
        {list(c.key_numbers).map((n, i) => (
          <div key={i} className="number-tile">
            <span className="number-value">{n.value}</span>
            <span className="number-label">{n.label}</span>
            <FactChips ids={n.fact_ids} facts={facts} />
          </div>
        ))}
      </div>
      <ol className="clean-list numbered">
        {list(c.steps).map((s, i) => (
          <GroundedText key={i} item={s} facts={facts} as="li" />
        ))}
      </ol>
      <span className="muted small">Suggested layout: {c.layout?.replace('_', ' ')}</span>
    </div>
  )
}

function AdvisoryView({ c, facts }: { c: Advisory; facts: FactLookup }) {
  const ind = c.indicators
  return (
    <div className="stack gap-12">
      <div className="row gap-10 wrap">
        <span className="mono muted">ADVISORY</span>
        <SeverityChip severity={c.severity} />
      </div>
      <h3>{c.title}</h3>
      <span className="section-title">Overview</span>
      <GroundedText item={c.overview} facts={facts} />
      <span className="section-title">Who and what is affected</span>
      <ul className="clean-list">
        {list(c.affected).map((a, i) => (
          <GroundedText key={i} item={a} facts={facts} as="li" />
        ))}
      </ul>
      <span className="section-title">How the attack works</span>
      <GroundedText item={c.description} facts={facts} />
      <span className="section-title">Impact</span>
      <GroundedText item={c.impact} facts={facts} />
      {ind && (ind.cves.length > 0 || ind.ips.length > 0 || ind.hashes.length > 0) && (
        <>
          <span className="section-title">Indicators found in the source</span>
          <IndicatorTable indicators={ind} />
        </>
      )}
      <span className="section-title">Recommended actions</span>
      <ol className="clean-list numbered">
        {list(c.recommendations).map((r, i) => (
          <GroundedText key={i} item={r} facts={facts} as="li" />
        ))}
      </ol>
    </div>
  )
}

function PresentationView({ c, facts }: { c: Presentation; facts: FactLookup }) {
  return (
    <div className="stack gap-12">
      <h3>{c.title}</h3>
      <div className="slide-list">
        {list(c.slides).map((slide, i) => (
          <div key={i} className="slide">
            <div className="row gap-10">
              <span className="slide-number">{i + 1}</span>
              <span className="slide-title grow">{slide.title}</span>
              <FactChips ids={slide.fact_ids} facts={facts} />
            </div>
            <ul className="clean-list">
              {list(slide.bullets).map((b, j) => (
                <li key={j}>{b}</li>
              ))}
            </ul>
            <p className="speaker-notes">
              <strong>Speaker notes:</strong> {slide.speaker_notes}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

function VideoView({ c, facts }: { c: VideoPackage; facts: FactLookup }) {
  return (
    <div className="stack gap-12">
      <div className="row gap-10 wrap">
        <h3 className="grow">{c.title}</h3>
        <span className="chip chip-neutral">About {c.duration_seconds} seconds</span>
      </div>
      <div className="scene-list">
        {list(c.scenes).map((scene, i) => (
          <div key={i} className="scene">
            <div className="scene-time mono">
              {scene.start}s–{scene.end}s
            </div>
            <div className="stack gap-6 grow">
              <span>
                <span className="section-label">Visual</span> {scene.visual}
              </span>
              <span>
                <span className="section-label">On screen</span> <strong>{scene.on_screen_text}</strong>
              </span>
              <GroundedText item={{ text: scene.narration, fact_ids: scene.fact_ids }} facts={facts} />
            </div>
          </div>
        ))}
      </div>
      <details>
        <summary>Subtitles ({list(c.subtitles).length} lines)</summary>
        <pre className="json-box">
          {list(c.subtitles)
            .map((s) => `${s.index}\n${s.start} --> ${s.end}\n${s.text}\n`)
            .join('\n')}
        </pre>
      </details>
    </div>
  )
}

// ---- shared bits --------------------------------------------------------------------------

export function SeverityChip({ severity }: { severity: string }) {
  const tone = severity === 'critical' || severity === 'high' ? 'chip-red' : severity === 'medium' ? 'chip-saffron' : 'chip-neutral'
  return <span className={`chip ${tone}`}>Severity: {severity}</span>
}

export function IndicatorTable({ indicators }: { indicators: FactSheet['indicators'] }) {
  const rows: [string, string[]][] = [
    ['Vulnerability (CVE)', indicators.cves],
    ['IP addresses', indicators.ips],
    ['File fingerprints', indicators.hashes],
  ]
  return (
    <div className="indicator-table">
      {rows
        .filter(([, values]) => values.length > 0)
        .map(([label, values]) => (
          <div key={label} className="indicator-row">
            <span className="indicator-label">{label}</span>
            <span className="mono stack gap-2">
              {values.map((v) => (
                <span key={v} className="break-all">
                  {v}
                </span>
              ))}
            </span>
          </div>
        ))}
    </div>
  )
}

// Picks the right view for an output type. Unknown types just show their JSON.
export function OutputBody({ type, content, facts }: { type: string; content: Record<string, unknown>; facts: FactLookup }) {
  switch (type) {
    case 'x_thread':
      return <XThreadView c={content as XThread} facts={facts} />
    case 'linkedin_post':
      return <LinkedInView c={content as LinkedInPost} facts={facts} />
    case 'executive_summary':
      return <ExecutiveSummaryView c={content as ExecutiveSummary} facts={facts} />
    case 'infographic':
      return <InfographicView c={content as Infographic} facts={facts} />
    case 'advisory':
      return <AdvisoryView c={content as Advisory} facts={facts} />
    case 'presentation':
      return <PresentationView c={content as Presentation} facts={facts} />
    case 'video_package':
      return <VideoView c={content as VideoPackage} facts={facts} />
    default:
      return <pre className="json-box">{JSON.stringify(content, null, 2)}</pre>
  }
}
