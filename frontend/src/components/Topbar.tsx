import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { search, type Health, type SearchResults } from '../api'
import { useAuth } from '../auth'
import { useCounts } from '../counts'
import { aiLabel, jobNo, LANGUAGE_NAMES } from '../pages/format'
import { links, navigate } from '../router'
import { Icon } from './Icon'
import { StatusChip } from './StatusChip'

type Props = {
  // undefined = still checking, null = backend not reachable
  health: Health | null | undefined
  onMenu: () => void
  menuOpen: boolean
}

// Shows which AI is in use, read live from /api/health.
function ModelChip({ health }: { health: Props['health'] }) {
  if (health === undefined) return <span className="chip chip-neutral">Checking…</span>
  if (health === null)
    return (
      <span className="chip chip-red">
        <Icon name="warning" size={14} strokeWidth={2.2} />
        Backend offline
      </span>
    )
  return (
    <span className={health.ai_mode === 'mock' ? 'chip chip-saffron' : 'chip chip-navy'} title="The AI that writes the outputs">
      <Icon name="chip" size={14} strokeWidth={2.2} />
      {aiLabel(health.ai_mode)}
    </span>
  )
}

type Option = { key: string; group: string; label: string; detail: string; href: string; chip?: ReactNode }

// One list of options from the three groups of results, in the order they are shown.
function optionsFrom(found: SearchResults, role: string): Option[] {
  const options: Option[] = []
  for (const job of found.jobs) {
    options.push({
      key: `job-${job.id}`, group: 'Jobs', label: job.title, detail: `${jobNo(job.id)} · v${job.version}`,
      href: job.status === 'draft' && role === 'operator' ? links.safety(job.id) : links.job(job.id),
      chip: <StatusChip status={job.status} />,
    })
  }
  for (const source of found.sources) {
    options.push({
      key: `source-${source.job_id}-${source.id}`, group: 'Sources', label: source.filename,
      detail: `${source.id} of ${jobNo(source.job_id)} · ${source.job_title}`, href: links.job(source.job_id),
    })
  }
  for (const record of found.records) {
    const href = role === 'admin' ? links.recordBook : role === 'reviewer' ? links.records : record.job_id ? links.job(record.job_id) : links.jobs
    options.push({
      key: `record-${record.record_no}`, group: 'Records', label: record.record_no,
      detail: `${record.title}${record.withdrawn ? ' · withdrawn' : ''}`, href,
    })
  }
  return options
}

// The search box: jobs, sources and records (backend/app/routes/search.py). A combobox: type, then
// use the arrow keys and Enter, or click a result. Escape closes the list.
function SearchBox() {
  const { user } = useAuth()
  const [text, setText] = useState('')
  const [found, setFound] = useState<SearchResults | null>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const listId = useId()
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const q = text.trim()
    if (q.length < 2) {
      setFound(null)
      return
    }
    const timer = window.setTimeout(() => {
      search(q)
        .then((result) => {
          setFound(result)
          setActive(-1)
        })
        .catch(() => setFound({ jobs: [], sources: [], records: [] }))
    }, 250)
    return () => window.clearTimeout(timer)
  }, [text])

  // Close the list when focus or a click goes elsewhere
  useEffect(() => {
    const onDown = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const options = found ? optionsFrom(found, user.role) : []
  const showList = open && text.trim().length >= 2 && found !== null

  function go(option: Option) {
    navigate(option.href)
    setOpen(false)
    setText('')
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown' && options.length) {
      e.preventDefault()
      setOpen(true)
      setActive((a) => (a + 1) % options.length)
    } else if (e.key === 'ArrowUp' && options.length) {
      e.preventDefault()
      setActive((a) => (a <= 0 ? options.length - 1 : a - 1))
    } else if (e.key === 'Enter' && active >= 0 && options[active]) {
      e.preventDefault()
      go(options[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  let lastGroup = ''
  return (
    <div className="search" ref={box}>
      <span className="search-icon">
        <Icon name="search" size={18} strokeWidth={1.8} />
      </span>
      <input
        type="search"
        role="combobox"
        aria-label="Search jobs, sources and records"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
        placeholder="Search jobs, documents, records"
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
      />
      {showList && (
        <div className="search-results" id={listId} role="listbox" aria-label="Search results">
          {options.length === 0 && (
            <p className="muted small search-empty" role="status">
              Nothing found for “{text.trim()}”. Titles, job numbers, file names and record numbers are searched.
            </p>
          )}
          {options.map((option, index) => {
            const heading = option.group !== lastGroup ? option.group : null
            lastGroup = option.group
            return (
              <div key={option.key} role="presentation">
                {heading && (
                  <div className="search-group" role="presentation">
                    {heading}
                  </div>
                )}
                <div
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  className={index === active ? 'search-option is-active' : 'search-option'}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => go(option)}
                  onMouseEnter={() => setActive(index)}
                >
                  <span className="stack grow search-option-text">
                    <span className="search-option-label">{option.label}</span>
                    <span className="search-option-detail">{option.detail}</span>
                  </span>
                  {option.chip}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function Topbar({ health, onMenu, menuOpen }: Props) {
  const { counts } = useCounts()
  const { user } = useAuth()
  const language = user.language || 'en'
  const unread = counts.unread
  return (
    <header className="topbar">
      <button
        type="button"
        className="icon-btn menu-btn"
        aria-label="Menu"
        aria-expanded={menuOpen}
        aria-controls="main-menu"
        onClick={onMenu}
      >
        <Icon name="menu" size={20} />
      </button>
      <SearchBox />
      <div className="grow" />
      <ModelChip health={health} />
      <a href={links.profile} className="btn btn-outline btn-sm topbar-lang" aria-label={`Language: ${LANGUAGE_NAMES[language] ?? language}. Change it in Profile and settings`}>
        <Icon name="globe" size={16} color="var(--muted)" strokeWidth={1.8} />
        <span lang={language}>{LANGUAGE_NAMES[language] ?? language}</span>
      </a>
      <a
        href={links.notifications}
        className="icon-btn"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications, none unread'}
      >
        <Icon name="bell" size={20} strokeWidth={1.8} />
        {unread > 0 && (
          <span className="bell-count" aria-hidden="true">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </a>
    </header>
  )
}
