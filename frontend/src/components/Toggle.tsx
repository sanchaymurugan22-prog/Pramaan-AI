import { t } from '../i18n'
// Stage 9A/9B: shared by the Watch folder, Profile and Admin pages.
// An on/off switch that says what it does (role="switch", read as "on" / "off")
export function Toggle({ label, detail, on, onChange, disabled }: {
  label: string
  detail?: string
  on: boolean
  onChange: (on: boolean) => void
  disabled?: boolean
}) {
  return (
    <div className="toggle-row">
      <span className="stack gap-1 grow">
        <span className="toggle-label">{label}</span>
        {detail && <span className="toggle-detail">{detail}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={label}
        className={on ? 'switch is-on' : 'switch'}
        onClick={() => onChange(!on)}
        disabled={disabled}
      >
        <span className="switch-knob" />
        <span className="switch-text" aria-hidden="true">{on ? t("On") : t("Off")}</span>
      </button>
    </div>
  )
}
