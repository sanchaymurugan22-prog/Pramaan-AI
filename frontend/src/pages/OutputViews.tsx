// Readable views of each output type. The JSON shapes come from
// backend/app/pipeline/output_types.py. Every text field is drawn with <Traced>, which splits it into
// sentences and shows the facts each sentence uses; a sentence that is not linked to any fact is
// underlined in yellow, and numbers that are not in the source in red (they must never be hidden).
// The path given to <Traced> is where that text is in the output JSON, e.g. ['tweets', 0, 'text'].
import type { FactSheet } from '../api'
import { Traced, TraceTags } from './trace'
import { useTraceBlock } from './traceState'

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

const list = <T,>(value: T[] | undefined): T[] => value ?? []

// A grounded piece of text ({text, fact_ids}) at `path` in the output JSON
function G({ item, path, as: Tag = 'p' }: { item?: Grounded; path: (string | number)[]; as?: 'p' | 'li' }) {
  if (!item) return null
  return (
    <Tag className="grounded">
      <Traced path={[...path, 'text']} text={item.text} />
    </Tag>
  )
}

// ---- one view per output type -------------------------------------------------------------

function XThreadView({ c }: { c: XThread }) {
  return (
    <ol className="tweet-list">
      {list(c.tweets).map((tweet, i) => (
        <li key={i} className="tweet">
          <G item={tweet} path={['tweets', i]} />
          <span className={tweet.text.length > 280 ? 'tweet-count is-over' : 'tweet-count'}>
            {i + 1}/{c.tweets.length} · {tweet.text.length}/280
          </span>
        </li>
      ))}
    </ol>
  )
}

function LinkedInView({ c }: { c: LinkedInPost }) {
  return (
    <div className="stack gap-10">
      {list(c.paragraphs).map((p, i) => (
        <G key={i} item={p} path={['paragraphs', i]} />
      ))}
      {list(c.hashtags).length > 0 && <p className="hashtags">{c.hashtags.map((t) => `#${t}`).join(' ')}</p>}
    </div>
  )
}

function ExecutiveSummaryView({ c }: { c: ExecutiveSummary }) {
  return (
    <div className="stack gap-12">
      <h3>
        <Traced path={['title']} text={c.title} />
      </h3>
      <div className="bottom-line">
        <span className="section-label">Bottom line</span>
        <G item={c.bottom_line} path={['bottom_line']} />
      </div>
      <span className="section-label">Key points</span>
      <ul className="clean-list">
        {list(c.key_points).map((p, i) => (
          <G key={i} item={p} path={['key_points', i]} as="li" />
        ))}
      </ul>
      <span className="section-label">Actions needed</span>
      <ol className="clean-list numbered">
        {list(c.actions_needed).map((p, i) => (
          <G key={i} item={p} path={['actions_needed', i]} as="li" />
        ))}
      </ol>
    </div>
  )
}

// A number tile is checked as one sentence ("42 hospitals disrupted"); clicking the tile traces it.
function NumberTile({ n, i }: { n: Infographic['key_numbers'][number]; i: number }) {
  const block = useTraceBlock(['key_numbers', i])
  return (
    <div className={`number-tile ${block.className}`} onClick={block.onClick}>
      <span className="number-value">{n.value}</span>
      <span className="number-label">{n.label}</span>
      <span>
        <TraceTags path={['key_numbers', i]} />
      </span>
    </div>
  )
}

function InfographicView({ c }: { c: Infographic }) {
  return (
    <div className="infographic">
      <div className="infographic-head">
        <h3>
          <Traced path={['headline']} text={c.headline} />
        </h3>
        <p>
          <Traced path={['subheadline']} text={c.subheadline} />
        </p>
      </div>
      <div className="number-tiles">
        {list(c.key_numbers).map((n, i) => (
          <NumberTile key={i} n={n} i={i} />
        ))}
      </div>
      <ol className="clean-list numbered">
        {list(c.steps).map((s, i) => (
          <G key={i} item={s} path={['steps', i]} as="li" />
        ))}
      </ol>
      <span className="muted small">Suggested layout: {c.layout?.replace('_', ' ')}</span>
    </div>
  )
}

function AdvisoryView({ c }: { c: Advisory }) {
  const ind = c.indicators
  return (
    <div className="stack gap-12">
      <div className="row gap-10 wrap">
        <span className="mono muted">ADVISORY</span>
        <SeverityChip severity={c.severity} />
      </div>
      <h3>
        <Traced path={['title']} text={c.title} />
      </h3>
      <span className="section-title">Overview</span>
      <G item={c.overview} path={['overview']} />
      <span className="section-title">Who and what is affected</span>
      <ul className="clean-list">
        {list(c.affected).map((a, i) => (
          <G key={i} item={a} path={['affected', i]} as="li" />
        ))}
      </ul>
      <span className="section-title">How the attack works</span>
      <G item={c.description} path={['description']} />
      <span className="section-title">Impact</span>
      <G item={c.impact} path={['impact']} />
      {ind && (ind.cves.length > 0 || ind.ips.length > 0 || ind.hashes.length > 0) && (
        <>
          <span className="section-title">Indicators found in the source</span>
          <IndicatorTable indicators={ind} />
        </>
      )}
      <span className="section-title">Recommended actions</span>
      <ol className="clean-list numbered">
        {list(c.recommendations).map((r, i) => (
          <G key={i} item={r} path={['recommendations', i]} as="li" />
        ))}
      </ol>
    </div>
  )
}

function PresentationView({ c }: { c: Presentation }) {
  return (
    <div className="stack gap-12">
      <h3>
        <Traced path={['title']} text={c.title} />
      </h3>
      <div className="slide-list">
        {list(c.slides).map((slide, i) => (
          <div key={i} className="slide">
            <div className="row gap-10">
              <span className="slide-number">{i + 1}</span>
              <span className="slide-title grow">
                <Traced path={['slides', i, 'title']} text={slide.title} />
              </span>
            </div>
            <ul className="clean-list">
              {list(slide.bullets).map((b, j) => (
                <li key={j} className="grounded">
                  <Traced path={['slides', i, 'bullets', j]} text={b} />
                </li>
              ))}
            </ul>
            <p className="speaker-notes">
              <strong>Speaker notes:</strong> <Traced path={['slides', i, 'speaker_notes']} text={slide.speaker_notes} />
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

function VideoView({ c }: { c: VideoPackage }) {
  return (
    <div className="stack gap-12">
      <div className="row gap-10 wrap">
        <h3 className="grow">
          <Traced path={['title']} text={c.title} />
        </h3>
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
                <span className="section-label">Visual</span> <Traced path={['scenes', i, 'visual']} text={scene.visual} />
              </span>
              <span>
                <span className="section-label">On screen</span>{' '}
                <strong>
                  <Traced path={['scenes', i, 'on_screen_text']} text={scene.on_screen_text} />
                </strong>
              </span>
              <p className="grounded">
                <Traced path={['scenes', i, 'narration']} text={scene.narration} />
              </p>
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
// The facts and warnings come from the surrounding <TraceProvider> (see trace.tsx).
export function OutputBody({ type, content }: { type: string; content: Record<string, unknown> }) {
  switch (type) {
    case 'x_thread':
      return <XThreadView c={content as XThread} />
    case 'linkedin_post':
      return <LinkedInView c={content as LinkedInPost} />
    case 'executive_summary':
      return <ExecutiveSummaryView c={content as ExecutiveSummary} />
    case 'infographic':
      return <InfographicView c={content as Infographic} />
    case 'advisory':
      return <AdvisoryView c={content as Advisory} />
    case 'presentation':
      return <PresentationView c={content as Presentation} />
    case 'video_package':
      return <VideoView c={content as VideoPackage} />
    default:
      return <pre className="json-box">{JSON.stringify(content, null, 2)}</pre>
  }
}
