import { useEffect, useState } from 'react'
import { checkWatchNow, getWatch, makeWatchFolder, updateWatch, type WatchActivity, type WatchState, type WatchUpdate } from '../api'
import { useCounts } from '../counts'
import { Icon, type IconName } from '../components/Icon'
import { StatusChip } from '../components/StatusChip'
import { Toggle } from '../components/Toggle'
import { links } from '../router'
import { shortTime } from './format'
import { t } from '../i18n'

// Design "23 · Watch folder (auto-drafts)". New .txt / .pdf / .docx files in the chosen folder (inside
// data/watch/) become DRAFT jobs that wait at the Safety check. Nothing is written by the AI, and nothing
// is sent, until a person has checked the draft and pressed Generate. (backend/app/watch.py)

const KITS: { label: string; outputs: string[] }[] = [
  { label: 'Cyber advisory kit (advisory, summary, slides)', outputs: ['advisory', 'executive_summary', 'presentation'] },
  { label: 'Public awareness kit (LinkedIn, X, infographic)', outputs: ['linkedin_post', 'x_thread', 'infographic'] },
  { label: 'Quick social posts (X thread, LinkedIn)', outputs: ['x_thread', 'linkedin_post'] },
  { label: 'Executive brief (summary only)', outputs: ['executive_summary'] },
  {
    label: 'Full kit (all 7 outputs)',
    outputs: ['x_thread', 'linkedin_post', 'executive_summary', 'infographic', 'advisory', 'presentation', 'video_package'],
  },
]

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.includes(x))

const FILE_ICON: Record<string, IconName> = { pdf: 'file', docx: 'file', txt: 'file' }

function ActivityRow({ item }: { item: WatchActivity }) {
  const ext = item.filename.split('.').pop()?.toLowerCase() ?? ''
  const waiting = item.status === 'drafted' && item.job_status === 'draft'
  return (
    <li className="activity-row">
      <span className={`activity-icon ${item.status === 'drafted' ? 'tone-saffron' : 'tone-neutral'}`} aria-hidden="true">
        <Icon name={FILE_ICON[ext] ?? 'file'} size={20} />
      </span>
      <span className="stack gap-2 grow activity-text">
        <span className="activity-name">{item.filename}</span>
        <span className="activity-detail">
          {t("Found {found_at} · {detail}", { found_at: shortTime(item.found_at), detail: t(item.detail) })}</span>
      </span>
      {waiting && <span className="chip chip-saffron">{t("Ready for you")}</span>}
      {item.status === 'drafted' && !waiting && item.job_status && <StatusChip status={item.job_status} />}
      {item.status === 'skipped' && <span className="chip chip-neutral">{t("Skipped")}</span>}
      {item.status === 'failed' && (
        <span className="chip chip-red">
          <Icon name="warning" size={14} strokeWidth={2.2} />
          {t("Could not read")}
        </span>
      )}
      {item.job_id && item.status === 'drafted' && (
        <a className="btn btn-sm btn-saffron-outline" href={waiting ? links.safety(item.job_id) : links.job(item.job_id)}>
          {t("Open")}<span className="sr-only"> {item.filename}</span>
        </a>
      )}
    </li>
  )
}

export function WatchFolder() {
  const { refresh } = useCounts()
  const [state, setState] = useState<WatchState | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [checking, setChecking] = useState(false)
  const [newName, setNewName] = useState<string | null>(null) // null = not making a folder

  useEffect(() => {
    let stopped = false
    let timer: number | undefined
    async function load() {
      try {
        const next = await getWatch()
        if (stopped) return
        setState(next)
        if (next.enabled) timer = window.setTimeout(load, 10000) // new drafts appear without reloading
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : t("Could not load the watch folder."))
      }
    }
    load()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [state?.enabled])

  async function change(update: WatchUpdate, message = '') {
    setError('')
    try {
      setState(await updateWatch(update))
      setNotice(message)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not save."))
    }
  }

  async function makeFolder() {
    if (!newName?.trim()) return
    try {
      const made = await makeWatchFolder(newName.trim())
      setNewName(null)
      await change({ folder: made.folder }, `Made data/watch/${made.folder}.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not make the folder."))
    }
  }

  async function checkNow() {
    setChecking(true)
    setError('')
    try {
      const next = await checkWatchNow()
      setState(next)
      setNotice(next.new ? t("{new} new file{n} found.", { new: next.new, n: next.new === 1 ? '' : 's' }) : t("No new files."))
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not check the folder."))
    } finally {
      setChecking(false)
    }
  }

  if (!state) {
    return <main className="page">{error ? <div className="alert alert-red">{error}</div> : <p className="muted">{t("Loading…")}</p>}</main>
  }
  const kit = KITS.find((k) => sameSet(k.outputs, state.outputs))
  const fullPath = `${state.root}/${state.folder}`
  const today = state.activity.filter((a) => new Date(a.found_at).toDateString() === new Date().toDateString()).length

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">{t("Automation")}</div>
          <h1>{t("Watch folder")}</h1>
          <p className="muted page-lead">{t("Drop reports into a folder and drafts are prepared for you. Nothing is sent without approval.")}</p>
        </div>
        <div className="grow" />
        <span className={state.enabled ? 'chip chip-green' : 'chip chip-neutral'}>
          <Icon name={state.enabled ? 'eye' : 'eyeOff'} size={14} strokeWidth={2.2} />
          {state.enabled ? t("On · watching") : t("Off")}
        </span>
      </div>

      <div className="alert alert-saffron row gap-10" style={{ marginBottom: '16px', alignItems: 'center' }}>
        <Icon name="shieldCheck" size={18} />
        <span><strong>Web Mode: Cloud Watch Dropzone</strong> — Monitors cloud storage dropzones &amp; file uploads. (Desktop mode monitors local PC folders).</span>
      </div>

      {error && <div className="alert alert-red" role="alert">{error}</div>}
      <p className="sr-only" role="status">{notice}</p>

      <div className="watch-grid">
        <section className="card card-pad stack gap-16" aria-label={t("Watch folder settings")}>
          <Toggle
            label={t("Watch folder is on")}
            detail={t("Checks for new files every {n}", { n: Math.round(state.interval_seconds) >= 60 ? `${Math.round(state.interval_seconds / 60)} minute${state.interval_seconds >= 120 ? 's' : ''}` : `${state.interval_seconds} seconds` })}
            on={state.enabled}
            onChange={(on) => change({ enabled: on }, on ? 'The watch folder is on.' : 'The watch folder is off.')}
          />
          <div className="divider" />

          <div className="field">
            <label className="field-label" htmlFor="watch-folder">{t("Folder on this computer")}</label>
            <div className="row gap-10">
              <select
                id="watch-folder"
                className="input grow"
                value={state.folder}
                onChange={(e) => change({ folder: e.target.value })}
              >
                {state.folders.map((f) => (
                  <option key={f} value={f}>data/watch/{f}</option>
                ))}
              </select>
              <button type="button" className="btn btn-outline" onClick={() => setNewName(newName === null ? '' : null)} aria-expanded={newName !== null}>
                {t("New folder")}
              </button>
            </div>
            <span className="field-help mono break-all">{fullPath}</span>
            {newName !== null && (
              <div className="row gap-10 mt-8">
                <label htmlFor="new-folder" className="sr-only">{t("New folder name")}</label>
                <input
                  id="new-folder"
                  className="input grow"
                  placeholder={t("e.g. cert-reports")}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && makeFolder()}
                />
                <button type="button" className="btn btn-saffron" onClick={makeFolder} disabled={!newName.trim()}>
                  {t("Make folder")}
                </button>
              </div>
            )}
          </div>

          <div className="field">
            <label className="field-label" htmlFor="watch-kit">{t("Kit to prepare")}</label>
            <select
              id="watch-kit"
              className="input"
              value={kit?.label ?? 'custom'}
              onChange={(e) => {
                const chosen = KITS.find((k) => k.label === e.target.value)
                if (chosen) change({ outputs: chosen.outputs })
              }}
            >
              {!kit && <option value="custom">{t("Custom ({length} outputs)", { length: state.outputs.length })}</option>}
              {KITS.map((k) => (
                <option key={k.label} value={k.label}>{t(k.label)}</option>
              ))}
            </select>
            <span className="field-help">{t("Ticked in advance on step 3. You can still change them before generating.")}</span>
          </div>

          <div className="field">
            <span className="field-label" id="watch-languages">{t("Languages")}</span>
            <div className="row gap-8 wrap" role="group" aria-labelledby="watch-languages">
              <span className="pill is-on">
                <Icon name="check" size={16} strokeWidth={2.4} />
                {t("English")}
              </span>
              <span className="field-help">
                {t("Plus your default output languages (Profile & settings), ticked in advance on step 3 of each draft.")}
              </span>
            </div>
          </div>

          <div className="hint">
            {t("The sharing level (TLP) is chosen by you at the Safety check of each draft, after you have seen what the scanner found. It is never set automatically.")}
          </div>

          <Toggle label={t("Notify me when drafts are ready")} on={state.notify} onChange={(on) => change({ notify: on })} />
          <Toggle
            label={t("Skip duplicates of earlier jobs")}
            detail={t("A file that is exactly the same as an earlier job's source is listed, not drafted again")}
            on={state.skip_duplicates}
            onChange={(on) => change({ skip_duplicates: on })}
          />
        </section>

        <section className="card card-pad stack gap-14" aria-labelledby="activity-title">
          <div className="row gap-10 wrap">
            <h2 id="activity-title">{t("Recent activity")}</h2>
            <div className="grow" />
            <span className="muted small">
              {t("{value} · {today} today", { value: state.last_check ? t("Checked {n}", { n: shortTime(state.last_check) }) : t("Not checked yet"), today: today })}</span>
            <button type="button" className="btn btn-outline btn-sm" onClick={checkNow} disabled={!state.enabled || checking}>
              <Icon name="refresh" size={16} strokeWidth={2} />
              {checking ? t("Checking…") : t("Check now")}
            </button>
          </div>
          {state.activity.length === 0 && (
            <p className="muted">
              {state.enabled
                ? t("No files yet. Copy a .txt, .pdf or .docx report into {fullPath} and it appears here within a minute.", { fullPath: fullPath })
                : t("Switch the watch folder on to start.")}
            </p>
          )}
          <ul className="clean-list-plain activity-list">
            {state.activity.map((item) => (
              <ActivityRow key={item.id} item={item} />
            ))}
          </ul>
        </section>
      </div>
    </main>
  )
}
