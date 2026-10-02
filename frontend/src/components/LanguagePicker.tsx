// Stage 8: choose the languages of a job (design 11 · Outputs and settings): English is always made; Hindi,
// Tamil and Bengali are shown first, "+ 19 more" opens the other Eighth Schedule languages. Each is a pill
// button (aria-pressed). Languages this computer cannot translate into are switched off, with the reason.
import { useState } from 'react'
import type { LanguagesInfo } from '../api'
import { Icon } from './Icon'
import { t } from '../i18n'

const FIRST = ['hi', 'ta', 'bn']

type Props = {
  info: LanguagesInfo | null
  selected: string[] // Indian language codes (English is implied)
  onChange: (codes: string[]) => void
  label?: string
  showVoices?: boolean // a small speaker icon for languages that can be read aloud
}

export function LanguagePicker({ info, selected, onChange, label = 'Languages', showVoices = false }: Props) {
  const [open, setOpen] = useState(() => selected.some((c) => !FIRST.includes(c)))
  if (!info) return <p className="muted small">{t("Loading languages…")}</p>
  const indian = info.languages.filter((l) => l.code !== 'en')
  const shown = open ? indian : indian.filter((l) => FIRST.includes(l.code) || selected.includes(l.code))
  const hidden = indian.length - shown.length
  const ready = info.translation.ready

  function toggle(code: string) {
    onChange(selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code])
  }

  return (
    <div className="field">
      <span className="field-label" id="language-picker-label">
        {label}
      </span>
      <div className="row gap-8 wrap" role="group" aria-labelledby="language-picker-label">
        <button type="button" className="pill is-on" aria-pressed="true" aria-disabled="true" title={t("English is always made")}>
          <Icon name="check" size={14} strokeWidth={2.6} />
          {t("English")}
        </button>
        {shown.map((lang) => {
          const on = selected.includes(lang.code)
          return (
            <button
              key={lang.code}
              type="button"
              className={on ? 'pill is-on' : 'pill'}
              aria-pressed={on}
              disabled={!ready}
              lang={lang.code}
              dir={lang.rtl ? 'rtl' : undefined}
              title={`${lang.name}${showVoices ? (lang.voice ? ` · voice: ${lang.voice}` : ' · no voice yet: text only') : ''}`}
              onClick={() => toggle(lang.code)}
            >
              {on && <Icon name="check" size={14} strokeWidth={2.6} />}
              <span>{lang.native}</span>
              <span className="sr-only"> ({lang.name})</span>
              {showVoices && lang.voice && <Icon name="volume" size={14} strokeWidth={2} />}
            </button>
          )
        })}
        {hidden > 0 && (
          <button type="button" className="pill pill-more" onClick={() => setOpen(true)} disabled={!ready}>
            {t("+ {hidden} more", { hidden: hidden })}</button>
        )}
      </div>
      {!ready && <span className="field-help">{t("Translation is not available on this computer: {detail}", { detail: t(info.translation.detail) })}</span>}
    </div>
  )
}
