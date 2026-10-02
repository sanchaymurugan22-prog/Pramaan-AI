// Readable views of each output type, as in the designs 13-18 (Stage 9A). The JSON shapes come from
// backend/app/pipeline/output_types.py. Every text field is drawn with <Traced>, which splits it into
// sentences and shows the facts each sentence uses; a sentence that is not linked to any fact is
// underlined in yellow and tagged, and numbers that are not in the source in red (never hidden).
// The path given to <Traced> is where that text is in the output JSON, e.g. ['tweets', 0, 'text'].
import { useState } from 'react'
import type { FactSheet, Quality, Tlp } from '../api'
import { Icon } from '../components/Icon'
import { LogoSeal } from '../components/Logo'
import { TlpLabel } from '../components/TlpLabel'
import { Traced, TraceTags } from './trace'
import { useTraceBlock } from './traceState'
import { locale, t } from '../i18n'

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
type Slide = { title: string; bullets: string[]; speaker_notes: string; fact_ids: string[] }
type Presentation = { title: string; slides: Slide[] }
type Scene = { visual: string; on_screen_text: string; narration: string; fact_ids: string[]; start: number; end: number }
type VideoPackage = {
  title: string
  duration_seconds: number
  scenes: Scene[]
  subtitles: { index: number; start: string; end: string; text: string }[]
}

// What every view may show besides the output itself
export type ViewMeta = {
  title: string // the job's title
  tlp: Tlp | null
  recordNo: string | null // once signed
  audience: string
  quality: Quality | null // checks of the version on screen
}

const list = <T,>(value: T[] | undefined): T[] => value ?? []
const words = (text: string) => text.split(/\s+/).filter(Boolean).length

// "Traced to source": claims linked to a fact, out of all claims
function traced(quality: Quality | null): { linked: number; claims: number } {
  const claims = (quality?.sentences ?? []).filter((s) => s.status === 'linked' || s.status === 'unlinked' || s.status === 'unverified')
  return { linked: claims.filter((s) => s.status === 'linked').length, claims: claims.length }
}

// A grounded piece of text ({text, fact_ids}) at `path` in the output JSON
function G({ item, path, as: Tag = 'p' }: { item?: Grounded; path: (string | number)[]; as?: 'p' | 'li' }) {
  if (!item) return null
  return (
    <Tag className="grounded">
      <Traced path={[...path, 'text']} text={item.text} />
    </Tag>
  )
}

function Footnote({ meta }: { meta: ViewMeta }) {
  return (
    <p className="doc-foot">
      {meta.recordNo ? t("AI-assisted · human-approved · Record {recordNo}", { recordNo: meta.recordNo }) : t("AI-assisted · pending human approval")}
    </p>
  )
}

// A copy button that says when it worked (for pasting a post into the real site)
function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setState('copied')
    } catch {
      setState('failed')
    }
    window.setTimeout(() => setState('idle'), 2500)
  }
  return (
    <button type="button" className="btn btn-outline btn-xs" onClick={copy}>
      <Icon name={state === 'copied' ? 'check' : 'copy'} size={16} strokeWidth={2} />
      {state === 'copied' ? t("Copied") : state === 'failed' ? t("Could not copy") : label}
      <span className="sr-only" role="status">{state === 'copied' ? t("Copied to the clipboard") : ''}</span>
    </button>
  )
}

// ---- Social posts (design 16) ------------------------------------------------------------------

function PostAuthor({ detail }: { detail: string }) {
  return (
    <div className="post-author">
      <span className="post-avatar" aria-hidden="true">
        <LogoSeal size={36} />
      </span>
      <span className="stack">
        <strong>{t("[ORGANISATION NAME]")}</strong>
        <span className="muted small">{detail}</span>
      </span>
    </div>
  )
}

function LinkedInView({ c }: { c: LinkedInPost }) {
  const tags = list(c.hashtags).map((t) => `#${t}`).join(' ')
  const text = [...list(c.paragraphs).map((p) => p.text), tags].filter(Boolean).join('\n\n')
  return (
    <div className="stack gap-12">
      <article className="post-card" aria-label={t("LinkedIn post preview")}>
        <PostAuthor detail={t("Official page · just now")} />
        <div className="stack gap-10">
          {list(c.paragraphs).map((p, i) => (
            <G key={i} item={p} path={['paragraphs', i]} />
          ))}
          {tags && <p className="hashtags">{tags}</p>}
        </div>
      </article>
      <div className="row gap-10 wrap">
        <span className={text.length > 3000 ? 'small over-limit' : 'muted small'}>
          {t("{value} / 3,000 characters{value2}", { value: text.length.toLocaleString(locale()), value2: text.length > 3000 && t(" (too long)") })}</span>
        <div className="grow" />
        <CopyButton text={text} label={t("Copy")} />
      </div>
    </div>
  )
}

function XThreadView({ c }: { c: XThread }) {
  const tweets = list(c.tweets)
  const over = tweets.filter((t) => t.text.length > 280).length
  return (
    <div className="stack gap-12">
      <ol className="thread" aria-label={t("X thread preview")}>
        {tweets.map((tweet, i) => (
          <li key={i} className="thread-post">
            <span className="post-avatar" aria-hidden="true">
              <LogoSeal size={36} />
            </span>
            <div className="stack gap-4 grow">
              <div className="row gap-8 wrap">
                <strong>{t("[ORGANISATION NAME]")}</strong>
                <span className="mono muted small">
                  {i + 1}/{tweets.length}
                </span>
                <div className="grow" />
                <span className={tweet.text.length > 280 ? 'mono small over-limit' : 'mono small count-ok'}>
                  {tweet.text.length}/280{tweet.text.length > 280 && t(" too long")}
                </span>
              </div>
              <G item={tweet} path={['tweets', i]} />
            </div>
          </li>
        ))}
      </ol>
      <div className="row gap-10 wrap">
        <span className={over ? 'small over-limit' : 'small count-ok'}>
          {over ? t("{over} post{n} over 280 characters", { over: over, n: over === 1 ? ' is' : 's are' }) : t("All posts within 280 characters")}
        </span>
        <div className="grow" />
        <CopyButton text={tweets.map((t) => t.text).join('\n\n')} label={t("Copy thread")} />
      </div>
    </div>
  )
}

// ---- Executive summary (design 18) -----------------------------------------------------------

function ExecutiveSummaryView({ c, meta }: { c: ExecutiveSummary; meta: ViewMeta }) {
  const all = [c.title, c.bottom_line?.text ?? '', ...list(c.key_points).map((p) => p.text), ...list(c.actions_needed).map((p) => p.text)]
  const count = all.reduce((sum, t) => sum + words(t), 0)
  const seconds = Math.max(15, Math.round((count / 200) * 60 / 5) * 5) // about 200 words a minute
  const { linked, claims } = traced(meta.quality)
  return (
    <div className="summary-layout">
      <article className="doc-sheet" aria-label={t("Executive summary preview")}>
        <div className="doc-head">
          <LogoSeal size={36} />
          <span className="muted small grow">{t("[ORGANISATION NAME] · Executive briefing")}</span>
          {meta.tlp && <TlpLabel tlp={meta.tlp} />}
        </div>
        <div className="doc-rule" aria-hidden="true">
          <span />
          <span />
        </div>
        <h3 className="doc-title">
          <Traced path={['title']} text={c.title} />
        </h3>
        <p className="muted small">
          {t("{value} · {count} words · {seconds}-second read", { value: new Date().toLocaleDateString(locale(), { day: 'numeric', month: 'long', year: 'numeric' }), count: count, seconds: seconds })}</p>
        <h4 className="section-title">{t("What happened")}</h4>
        <G item={c.bottom_line} path={['bottom_line']} />
        <h4 className="section-title">{t("Key points")}</h4>
        <ul className="clean-list">
          {list(c.key_points).map((p, i) => (
            <G key={i} item={p} path={['key_points', i]} as="li" />
          ))}
        </ul>
        <div className="decision-box">
          <h4 className="decision-title">{t("Decision needed")}</h4>
          <ol className="clean-list numbered">
            {list(c.actions_needed).map((p, i) => (
              <G key={i} item={p} path={['actions_needed', i]} as="li" />
            ))}
          </ol>
        </div>
        <Footnote meta={meta} />
      </article>
      <dl className="facts-table" aria-label={t("About this summary")}>
        <div>
          <dt>{t("Audience")}</dt>
          <dd>{meta.audience}</dd>
        </div>
        <div>
          <dt>{t("Length")}</dt>
          <dd>{t("{count} words", { count: count })}</dd>
        </div>
        <div>
          <dt>{t("Reading time")}</dt>
          <dd>{t("{seconds} seconds", { seconds: seconds })}</dd>
        </div>
        <div>
          <dt>{t("Traced to source")}</dt>
          <dd>
            {t("{linked} of {claims} sentences", { linked: linked, claims: claims })}</dd>
        </div>
      </dl>
    </div>
  )
}

// ---- Infographic (design 17) --------------------------------------------------------------------

// A number tile is checked as one sentence ("42 hospitals disrupted"); clicking the tile traces it.
function NumberTile({ n, i }: { n: Infographic['key_numbers'][number]; i: number }) {
  const block = useTraceBlock(['key_numbers', i])
  const content = (
    <>
      <span className="number-value">{n.value}</span>
      <span className="number-label">{n.label}</span>
      <span>
        <TraceTags path={['key_numbers', i]} />
      </span>
    </>
  )
  if (!block.onClick) return <div className="number-tile">{content}</div>
  return (
    <button type="button" className={`number-tile ${block.className}`} onClick={block.onClick} aria-label={t("{value} {label}: show where this comes from", { value: n.value, label: n.label })}>
      {content}
    </button>
  )
}

const LAYOUTS: Record<string, string> = { vertical_steps: 'Steps', number_grid: 'Big numbers', timeline: 'Timeline' }

function InfographicView({ c }: { c: Infographic }) {
  return (
    <div className="stack gap-14">
      <div className="stack gap-6">
        <span className="section-label">{t("Layout")}</span>
        <div className="layout-options" role="list">
          {Object.entries(LAYOUTS).map(([key, label]) => (
            <span key={key} role="listitem" className={c.layout === key ? 'layout-option is-on' : 'layout-option'}>
              {c.layout === key && <Icon name="check" size={16} strokeWidth={2.4} />}
              {label}
              {c.layout === key && <span className="sr-only"> {t("(used)")}</span>}
            </span>
          ))}
        </div>
      </div>
      <div className="stack gap-6">
        <span className="section-label">{t("Headline")}</span>
        <p className="key-message">
          <Traced path={['headline']} text={c.headline} />
        </p>
        <span className="section-label">{t("Subheadline")}</span>
        <p className="key-message small">
          <Traced path={['subheadline']} text={c.subheadline} />
        </p>
      </div>
      <div className="stack gap-6">
        <span className="section-label">{t("Main numbers")}</span>
        <div className="number-tiles">
          {list(c.key_numbers).map((n, i) => (
            <NumberTile key={i} n={n} i={i} />
          ))}
        </div>
      </div>
      <div className="stack gap-6">
        <span className="section-label">{t("Do these things now")}</span>
        <ol className="clean-list numbered">
          {list(c.steps).map((s, i) => (
            <G key={i} item={s} path={['steps', i]} as="li" />
          ))}
        </ol>
      </div>
    </div>
  )
}

// ---- Advisory (design 13) ----------------------------------------------------------------------

function AdvisoryView({ c, meta }: { c: Advisory; meta: ViewMeta }) {
  const ind = c.indicators
  return (
    <div className="stack gap-12">
      <div className="row gap-10 wrap">
        <span className="mono muted">ADVISORY{meta.recordNo && ` · ${meta.recordNo}`}</span>
        <SeverityChip severity={c.severity} />
        {meta.tlp && <TlpLabel tlp={meta.tlp} />}
      </div>
      <h3 className="doc-title">
        <Traced path={['title']} text={c.title} />
      </h3>
      <h4 className="section-title">{t("Overview")}</h4>
      <G item={c.overview} path={['overview']} />
      <h4 className="section-title">{t("Who and what is affected")}</h4>
      <ul className="clean-list">
        {list(c.affected).map((a, i) => (
          <G key={i} item={a} path={['affected', i]} as="li" />
        ))}
      </ul>
      <h4 className="section-title">{t("How the attack works")}</h4>
      <G item={c.description} path={['description']} />
      <h4 className="section-title">{t("Impact")}</h4>
      <G item={c.impact} path={['impact']} />
      {ind && (ind.cves.length > 0 || ind.ips.length > 0 || ind.hashes.length > 0) && (
        <>
          <h4 className="section-title">{t("Indicators found in the source")}</h4>
          <IndicatorTable indicators={ind} />
        </>
      )}
      <h4 className="section-title">{t("Recommended actions")}</h4>
      <ol className="clean-list numbered">
        {list(c.recommendations).map((r, i) => (
          <G key={i} item={r} path={['recommendations', i]} as="li" />
        ))}
      </ol>
    </div>
  )
}

// ---- Presentation viewer (design 14) -------------------------------------------------------------

const MAX_SLIDE_WORDS = 60 // more than this reads as a wall of text

function PresentationView({ c, meta }: { c: Presentation; meta: ViewMeta }) {
  const slides = list(c.slides)
  const [index, setIndex] = useState(0)
  const at = Math.min(index, Math.max(0, slides.length - 1))
  const slide = slides[at]
  if (!slide) return <p className="muted">{t("No slides.")}</p>
  const sentences = (meta.quality?.sentences ?? []).filter((s) => s.path[0] === 'slides' && s.path[1] === at)
  const claims = sentences.filter((s) => s.status === 'linked' || s.status === 'unlinked' || s.status === 'unverified')
  const onSlide = words(slide.title) + list(slide.bullets).reduce((sum, b) => sum + words(b), 0)
  const number = (n: number) => String(n).padStart(2, '0')

  return (
    <div className="deck-layout">
      <ol className="deck-thumbs" aria-label={t("Slides")}>
        {slides.map((s, i) => (
          <li key={i}>
            <button
              type="button"
              className={i === at ? 'deck-thumb is-current' : 'deck-thumb'}
              aria-current={i === at ? 'true' : undefined}
              onClick={() => setIndex(i)}
            >
              <span className="deck-thumb-art" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <span className="deck-thumb-label">
                {i + 1}. {s.title}
              </span>
            </button>
          </li>
        ))}
      </ol>

      <div className="stack gap-14 deck-main">
        <div className="row gap-10 wrap">
          <span className="muted small grow">
            {t("Deck title:")} <Traced path={['title']} text={c.title} />
          </span>
          <button type="button" className="icon-btn icon-btn-sm" aria-label={t("Previous slide")} disabled={at === 0} onClick={() => setIndex(at - 1)}>
            <Icon name="chevronLeft" size={18} />
          </button>
          <span className="small" aria-live="polite">
            {t("Slide {value} of {length}", { value: at + 1, length: slides.length })}</span>
          <button type="button" className="icon-btn icon-btn-sm" aria-label={t("Next slide")} disabled={at >= slides.length - 1} onClick={() => setIndex(at + 1)}>
            <Icon name="chevronRight" size={18} />
          </button>
        </div>

        <section className="slide-frame" aria-label={t("Slide {n}: {title}", { n: at + 1, title: slide.title })}>
          <div className="slide-strip" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="slide-body">
            <span className="mono slide-count">
              {number(at + 1)} / {number(slides.length)} <span className="muted">{meta.title}</span>
            </span>
            {/* The title is a heading, not a claim: no fact chips here (they crowded the title). Numbers in
                it are still checked, and flagged in red if they are not in the source. */}
            <h3 className="slide-heading">
              <Traced path={['slides', at, 'title']} text={slide.title} />
            </h3>
            <ul className="slide-bullets">
              {list(slide.bullets).map((b, j) => (
                <li key={j} className="grounded">
                  <Traced path={['slides', at, 'bullets', j]} text={b} />
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="notes-card" aria-label={t("Speaker notes")}>
          <h4 className="notes-title">{t("Speaker notes")}</h4>
          <p className="grounded">
            <Traced path={['slides', at, 'speaker_notes']} text={slide.speaker_notes} />
          </p>
        </section>

        <dl className="facts-table facts-row" aria-label={t("This slide")}>
          <div>
            <dt>{t("Traced")}</dt>
            <dd>
              {t("{length} of {length2} sentences", { length: claims.filter((s) => s.status === 'linked').length, length2: claims.length })}</dd>
          </div>
          <div>
            <dt>{t("Words on slide")}</dt>
            <dd className={onSlide > MAX_SLIDE_WORDS ? 'over-limit' : undefined}>
              {onSlide} · {onSlide > MAX_SLIDE_WORDS ? t("too many") : t("within limit")}
            </dd>
          </div>
          <div>
            <dt>{t("Facts used")}</dt>
            <dd className="mono">{list(slide.fact_ids).join(', ') || '—'}</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}

// ---- Video package (design 15) -------------------------------------------------------------------

function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function VideoView({ c }: { c: VideoPackage }) {
  const scenes = list(c.scenes)
  const [index, setIndex] = useState(0)
  const at = Math.min(index, Math.max(0, scenes.length - 1))
  const scene = scenes[at]
  if (!scene) return <p className="muted">{t("No scenes.")}</p>
  const caption = scene.narration.split(/(?<=[.!?])\s/)[0]
  const total = c.duration_seconds || scenes.at(-1)?.end || 0

  return (
    <div className="stack gap-14">
      <div className="row gap-10 wrap">
        <h3 className="grow">
          <Traced path={['title']} text={c.title} />
        </h3>
        <span className="chip chip-neutral">{t("About {total} long · {length} scenes", { total: clock(total), length: scenes.length })}</span>
      </div>

      <div className="video-layout">
        <section className="video-frame" aria-label={t("Storyboard, scene {n}", { n: at + 1 })}>
          <span className="video-badge">
            {t("Scene {value} · {start}", { value: at + 1, start: clock(scene.start) })}</span>
          <div className="video-art">
            <span className="video-visual">{scene.visual}</span>
            <strong className="video-onscreen">{scene.on_screen_text}</strong>
          </div>
          <span className="video-caption">{caption}</span>
        </section>

        <section className="stack gap-10 scene-details" aria-label={t("Scene {n} details", { n: at + 1 })}>
          <h4 className="notes-title">{t("Scene {value}", { value: at + 1 })}</h4>
          <span className="section-label">{t("Narration")}</span>
          <p className="grounded">
            <Traced path={['scenes', at, 'narration']} text={scene.narration} />
          </p>
          <span className="section-label">{t("On screen")}</span>
          <p className="grounded">
            <Traced path={['scenes', at, 'on_screen_text']} text={scene.on_screen_text} />
          </p>
          <span className="section-label">{t("Visual note")}</span>
          <p className="grounded muted">
            <Traced path={['scenes', at, 'visual']} text={scene.visual} />
          </p>
        </section>
      </div>

      <div className="video-timeline" role="progressbar" aria-label={t("Position in the video")} aria-valuemin={0} aria-valuemax={Math.round(total)} aria-valuenow={Math.round(scene.start)} aria-valuetext={t("{n} of {n2}", { n: clock(scene.start), n2: clock(total) })}>
        <span className="mono small">
          {clock(scene.start)} / {clock(total)}
        </span>
        <span className="bar grow">
          <span className="bar-fill fill-fair" style={{ width: `${total ? (scene.end / total) * 100 : 0}%`, display: 'block' }} />
        </span>
      </div>

      <ol className="scene-strip" aria-label={t("Scenes")}>
        {scenes.map((s, i) => (
          <li key={i}>
            <button type="button" className={i === at ? 'scene-tile is-current' : 'scene-tile'} aria-current={i === at ? 'true' : undefined} onClick={() => setIndex(i)}>
              <span className={`scene-swatch swatch-${i % 4}`} aria-hidden="true" />
              <strong>
                {i + 1}. {s.on_screen_text}
              </strong>
              <span className="mono muted small">
                {clock(s.start)}–{clock(s.end)}
              </span>
            </button>
          </li>
        ))}
      </ol>

      <p className="muted small">{t("The video (.mp4) and the narration (.mp3) are made on this computer from these scenes: use “Make and watch the video” above, or the downloads below.")}</p>
      <details>
        <summary>{t("Subtitles ({length} lines)", { length: list(c.subtitles).length })}</summary>
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

const SEVERITY_WORDS: Record<string, string> = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' }

export function SeverityChip({ severity }: { severity: string }) {
  const tone = severity === 'critical' || severity === 'high' ? 'chip-red' : severity === 'medium' ? 'chip-saffron' : 'chip-neutral'
  return <span className={`chip ${tone}`}>{t("Severity")}: {t(SEVERITY_WORDS[severity] ?? severity)}</span>
}

export function IndicatorTable({ indicators }: { indicators: FactSheet['indicators'] }) {
  const rows: [string, string[]][] = [
    [t('Vulnerability (CVE)'), indicators.cves],
    [t('IP addresses'), indicators.ips],
    [t('File fingerprints'), indicators.hashes],
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
// Stage 8: the emergency alert as the text message people receive, with its length
function SmsView({ c }: { c: { message?: { text: string } } }) {
  const text = c.message?.text ?? ''
  const unicode = Array.from(text).some((ch) => ch.charCodeAt(0) > 127) // Indian scripts: UCS-2, 70 per SMS
  const limit = unicode ? 70 : 160
  const parts = text.length <= limit ? 1 : Math.ceil(text.length / (limit - 7))
  return (
    <div className="sms-view stack gap-8">
      <div className="sms-bubble">
        <Traced path={['message', 'text']} text={text} />
      </div>
      <span className={parts > 1 ? 'small over-limit' : 'small count-ok'}>
        {t("{length} / {limit} characters · {value}{value2}", { length: text.length, limit: limit, value: parts === 1 ? t("fits one SMS") : t("{parts} SMS parts", { parts: parts }), value2: unicode && t(" (Indian scripts: 70 characters in one SMS)") })}</span>
    </div>
  )
}

export function OutputBody({ type, content, meta }: { type: string; content: Record<string, unknown>; meta: ViewMeta }) {
  switch (type) {
    case 'sms':
      return <SmsView c={content as { message?: { text: string } }} />
    case 'x_thread':
      return <XThreadView c={content as XThread} />
    case 'linkedin_post':
      return <LinkedInView c={content as LinkedInPost} />
    case 'executive_summary':
      return <ExecutiveSummaryView c={content as ExecutiveSummary} meta={meta} />
    case 'infographic':
      return <InfographicView c={content as Infographic} />
    case 'advisory':
      return <AdvisoryView c={content as Advisory} meta={meta} />
    case 'presentation':
      return <PresentationView c={content as Presentation} meta={meta} />
    case 'video_package':
      return <VideoView c={content as VideoPackage} />
    default:
      return <pre className="json-box">{JSON.stringify(content, null, 2)}</pre>
  }
}
