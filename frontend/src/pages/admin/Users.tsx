// Designs 31 · Users and access requests, 32 · Add or edit user (dialog). Admin only.
// Temporary passwords are shown ONCE, here, to the Admin (only their hash is stored). The person must
// choose their own password at their next sign-in.
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  addUser,
  approveAccountRequest,
  changeUser,
  getFormOptions,
  listAccountRequests,
  listUsers,
  rejectAccountRequest,
  resetUserPassword,
  type AccountRequest,
  type AdminUser,
  type Role,
} from '../../api'
import { initials, ROLE_TONE, useAuth } from '../../auth'
import { Icon } from '../../components/Icon'
import { shortTime } from '../format'
import { t } from '../../i18n'

type Tab = 'users' | 'requests' | 'roles'
type Dialog = { kind: 'add' } | { kind: 'edit'; user: AdminUser } | null

export function Users() {
  const [tab, setTab] = useState<Tab>('users')
  const [users, setUsers] = useState<AdminUser[]>([])
  const [requests, setRequests] = useState<AccountRequest[]>([])
  const [dialog, setDialog] = useState<Dialog>(null)
  const [error, setError] = useState('')
  const [loads, setLoads] = useState(0) // bump to load the lists again after a change
  const reload = () => setLoads((n) => n + 1)

  useEffect(() => {
    let stopped = false
    Promise.all([listUsers(), listAccountRequests()])
      .then(([u, r]) => {
        if (stopped) return
        setUsers(u)
        setRequests(r)
      })
      .catch((e) => setError(e instanceof Error ? e.message : t("Could not load users.")))
    return () => {
      stopped = true
    }
  }, [loads])

  const pending = requests.filter((r) => r.status === 'pending')
  const pendingAccess = pending.filter((r) => r.kind === 'access')
  const pendingResets = pending.filter((r) => r.kind === 'reset')

  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-4">
          <div className="eyebrow eyebrow-navy">{t("Admin")}</div>
          <h1>{t("Users & access")}</h1>
        </div>
        <div className="grow" />
        <button type="button" className="btn btn-navy" onClick={() => setDialog({ kind: 'add' })}>
          <Icon name="plus" size={18} strokeWidth={2} />
          {t("Add user")}
        </button>
      </div>

      <div className="segmented segmented-wide" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'users'} className={tab === 'users' ? 'is-on' : ''} onClick={() => setTab('users')}>
          {t("All users ({length})", { length: users.length })}</button>
        <button type="button" role="tab" aria-selected={tab === 'requests'} className={tab === 'requests' ? 'is-on' : ''} onClick={() => setTab('requests')}>
          {t("Requests ({length})", { length: pending.length })}</button>
        <button type="button" role="tab" aria-selected={tab === 'roles'} className={tab === 'roles' ? 'is-on' : ''} onClick={() => setTab('roles')}>
          {t("Roles and permissions")}
        </button>
      </div>

      {error && <div className="alert alert-red">{error}</div>}
      {pending.length > 0 && tab !== 'requests' && (
        <div className="waiting-banner">
          <Icon name="user" size={20} color="var(--saffron-dark)" />
          <span className="grow">
            {pendingAccess.length > 0 && (
              <>
                <strong>
                  {t("{length} {value} waiting for access:", { length: pendingAccess.length, value: pendingAccess.length === 1 ? t("person is") : t("people are") })}</strong>{' '}
                {pendingAccess.map((r) => `${r.full_name} (${r.role_label})`).join(', ')}.{' '}
              </>
            )}
            {pendingResets.length > 0 && (
              <strong>
                {t("{length} forgot-password request{value}.", { length: pendingResets.length, value: pendingResets.length === 1 ? '' : 's' })}</strong>
            )}
          </span>
          <button type="button" className="btn btn-saffron-outline btn-xs" onClick={() => setTab('requests')}>
            {t("Review requests")}
          </button>
        </div>
      )}

      {tab === 'users' && <UsersTable users={users} onEdit={(user) => setDialog({ kind: 'edit', user })} />}
      {tab === 'requests' && <Requests requests={requests} users={users} onChanged={reload} />}
      {tab === 'roles' && <RolesTable />}

      {dialog && <UserDialog dialog={dialog} onClose={() => setDialog(null)} onChanged={reload} />}
    </main>
  )
}

function RoleChip({ role, label }: { role: Role; label: string }) {
  return <span className={`chip chip-xs chip-${ROLE_TONE[role]}`}>{label}</span>
}

function StatusCell({ user }: { user: AdminUser }) {
  if (!user.is_active) return <span className="chip chip-xs chip-neutral">{t("Switched off")}</span>
  if (user.locked) return <span className="chip chip-xs chip-red">{t("Locked")}</span>
  if (user.must_change_password) return <span className="chip chip-xs chip-yellow">{t("Temporary password")}</span>
  return <span className="chip chip-xs chip-green">{t("Active")}</span>
}

function UsersTable({ users, onEdit }: { users: AdminUser[]; onEdit: (user: AdminUser) => void }) {
  return (
    <section className="card card-pad table-scroll">
      <table className="data-table">
        <caption className="sr-only">{t("All users")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("Name")}</th>
            <th scope="col">{t("Employee ID")}</th>
            <th scope="col">{t("Role")}</th>
            <th scope="col">{t("Division")}</th>
            <th scope="col">DSC</th>
            <th scope="col">{t("Status")}</th>
            <th scope="col">{t("Last active")}</th>
            <th scope="col">
              <span className="sr-only">{t("Actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>
                <span className="row gap-10">
                  <span className={`avatar avatar-sm avatar-${ROLE_TONE[u.role]}`} aria-hidden="true">
                    {initials(u.full_name)}
                  </span>
                  <span className="stack">
                    <strong>{u.full_name}</strong>
                    <span className="muted small">{u.email ?? u.username}</span>
                  </span>
                </span>
              </td>
              <td className="mono">{u.employee_id ?? '—'}</td>
              <td>
                <RoleChip role={u.role} label={t(u.role_label)} />
              </td>
              <td>{u.division || '—'}</td>
              <td>{u.dsc_holder ? t("Class 3") : '—'}</td>
              <td>
                <StatusCell user={u} />
                {u.emergency_duty && (
                  <span className="chip chip-xs chip-saffron mt-4">
                    <Icon name="siren" size={12} strokeWidth={2.2} />
                    {t("On duty")}
                  </span>
                )}
              </td>
              <td className="muted">{u.last_login ? shortTime(u.last_login) : t("Never")}</td>
              <td className="right">
                <button type="button" className="btn btn-outline btn-xs" onClick={() => onEdit(u)}>
                  <Icon name="pencil" size={14} strokeWidth={2} />
                  {t("Edit")}<span className="sr-only"> {u.full_name}</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Requests({ requests, users, onChanged }: { requests: AccountRequest[]; users: AdminUser[]; onChanged: () => void }) {
  const [error, setError] = useState('')
  const [shown, setShown] = useState<{ name: string; password: string } | null>(null)
  const [roles, setRoles] = useState<Record<number, Role>>({})
  const pending = requests.filter((r) => r.status === 'pending')
  const handled = requests.filter((r) => r.status !== 'pending').slice(0, 20)

  async function act(action: () => Promise<unknown>) {
    setError('')
    try {
      await action()
      onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("That did not work."))
    }
  }

  async function resetFor(request: AccountRequest) {
    const user = users.find((u) => u.username === request.username)
    if (!user) return
    if (!window.confirm(t("Have you checked in person that this is {full_name}? A new temporary password will be made.", { full_name: user.full_name }))) return
    await act(async () => {
      const result = await resetUserPassword(user.id)
      setShown({ name: user.full_name, password: result.temporary_password })
    })
  }

  return (
    <section className="card card-pad stack gap-14">
      <h2>{t("Waiting")}</h2>
      {error && <div className="alert alert-red">{error}</div>}
      {shown && <TemporaryPassword name={shown.name} password={shown.password} onDone={() => setShown(null)} />}
      {pending.length === 0 && <p className="muted">{t("No requests are waiting.")}</p>}
      {pending.map((r) => (
        <article key={r.id} className="request-row">
          <div className="stack gap-4 grow">
            <div className="row gap-10 wrap">
              <strong>{r.kind === 'access' ? r.full_name : r.username}</strong>
              {r.kind === 'access' ? (
                <>
                  <span className="mono muted small">{r.employee_id ?? r.username}</span>
                  <span className="chip chip-xs chip-neutral">{t("Access request · {role_label}", { role_label: t(r.role_label) })}</span>
                  {r.division && <span className="muted small">{r.division}</span>}
                  {r.email && <span className="muted small">{r.email}</span>}
                </>
              ) : (
                <span className="chip chip-xs chip-yellow">{t("Forgot password")}</span>
              )}
              <span className="muted small">{shortTime(r.created_at)}</span>
            </div>
            {r.reason && <span className="muted small">“{r.reason}”</span>}
            {r.kind === 'reset' && !r.user_exists && <span className="small form-error">{t("No user has this username.")}</span>}
          </div>
          {r.kind === 'access' ? (
            <div className="row gap-8">
              <select
                className="input input-sm"
                aria-label={t("Role")}
                value={roles[r.id] ?? r.role ?? 'operator'}
                onChange={(e) => setRoles((all) => ({ ...all, [r.id]: e.target.value as Role }))}
              >
                <option value="operator">{t("Operator")}</option>
                <option value="reviewer">{t("Reviewer")}</option>
              </select>
              <button type="button" className="btn btn-outline btn-xs" onClick={() => act(() => rejectAccountRequest(r.id))}>
                {t("Reject")}
              </button>
              <button type="button" className="btn btn-green btn-xs" onClick={() => act(() => approveAccountRequest(r.id, roles[r.id] ?? r.role ?? undefined))}>
                <Icon name="check" size={14} strokeWidth={2.4} />
                {t("Approve")}
              </button>
            </div>
          ) : (
            <div className="row gap-8">
              <button type="button" className="btn btn-outline btn-xs" onClick={() => act(() => rejectAccountRequest(r.id))}>
                {t("Dismiss")}
              </button>
              {r.user_exists && (
                <button type="button" className="btn btn-navy btn-xs" onClick={() => resetFor(r)}>
                  <Icon name="key" size={14} strokeWidth={2} />
                  {t("Reset password")}
                </button>
              )}
            </div>
          )}
        </article>
      ))}
      {handled.length > 0 && (
        <>
          <h3 className="mt-8">{t("Handled")}</h3>
          {handled.map((r) => (
            <div key={r.id} className="row gap-10 muted small">
              <span className={`chip chip-xs ${r.status === 'rejected' ? 'chip-red' : 'chip-green'}`}>{r.status}</span>
              <span>
                {r.kind === 'access' ? t("{full_name} ({username}) as {role_label}", { full_name: r.full_name, username: r.username, role_label: t(r.role_label) }) : t("Forgot password: {username}", { username: r.username })}
              </span>
              <span>
                · {r.decided_by} · {r.decided_at ? shortTime(r.decided_at) : ''}
              </span>
            </div>
          ))}
        </>
      )}
    </section>
  )
}

// What the backend enforces (Stage 6B, signing Stage 7, Stage 9B). Admins never see job content.
const PERMISSIONS: [string, boolean, boolean, boolean][] = [
  ['Verify a document or check a message (“Is this real?”)', true, true, true],
  ['Create and edit content, safety check, regenerate', true, false, false],
  ['Use emergency mode (send an alert for fast-track review)', true, false, false],
  ['Comment on lines, approve and sign (not your own job)', false, true, false],
  ['Withdraw signed records', false, false, true],
  ['Manage users, templates and the letterhead', false, false, true],
  ['Change security rules, see the audit trail', false, false, true],
  ['Update the public verify page, make backups', false, false, true],
]

function RolesTable() {
  return (
    <section className="card card-pad stack gap-12">
      <div className="row">
        <h2>{t("What each role can do")}</h2>
        <div className="grow" />
        <span className="muted small">{t("Checked by the backend on every request")}</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>{t("Permission")}</th>
            <th>{t("Operator")}</th>
            <th>{t("Reviewer")}</th>
            <th>{t("Admin")}</th>
          </tr>
        </thead>
        <tbody>
          {PERMISSIONS.map(([label, ...allowed]) => (
            <tr key={label}>
              <td>{label}</td>
              {allowed.map((yes, i) => (
                <td key={i}>{yes ? <Icon name="check" size={18} strokeWidth={2.4} color="var(--green-dark)" /> : <span className="muted">—</span>}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function TemporaryPassword({ name, password, onDone }: { name: string; password: string; onDone?: () => void }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="temp-password">
      <div className="stack gap-2 grow">
        <span className="muted small">{t("Temporary password for {name} · shown only now", { name: name })}</span>
        <span className="mono temp-password-value">{password}</span>
        <span className="muted small">{t("Give it to them in person. They must choose their own at the next sign-in.")}</span>
      </div>
      <button type="button" className="btn btn-outline btn-xs" onClick={copy}>
        {copied ? t("Copied") : t("Copy")}
      </button>
      {onDone && (
        <button type="button" className="btn btn-link btn-xs" onClick={onDone}>
          {t("Done")}
        </button>
      )}
    </div>
  )
}

const ROLE_CARDS: { role: Role; title: string; note: string; icon: 'pencil' | 'shieldCheck' | 'sliders' }[] = [
  { role: 'operator', title: 'Operator', note: 'Creates content', icon: 'pencil' },
  { role: 'reviewer', title: 'Reviewer', note: 'Approves content', icon: 'shieldCheck' },
  { role: 'admin', title: 'Admin', note: 'Manages the system', icon: 'sliders' },
]

function UserDialog({ dialog, onClose, onChanged }: { dialog: NonNullable<Dialog>; onClose: () => void; onChanged: () => void }) {
  const { user: me } = useAuth()
  const editing = dialog.kind === 'edit' ? dialog.user : null
  const [fullName, setFullName] = useState(editing?.full_name ?? '')
  const [username, setUsername] = useState('')
  const [employeeId, setEmployeeId] = useState(editing?.employee_id ?? '')
  const [email, setEmail] = useState(editing?.email ?? '')
  const [division, setDivision] = useState(editing?.division || 'Cyber operations')
  const [divisions, setDivisions] = useState<string[]>(['Cyber operations'])
  const [dsc, setDsc] = useState(editing?.dsc_holder ?? false)
  const [duty, setDuty] = useState(editing?.emergency_duty ?? false)
  const [role, setRole] = useState<Role>(editing?.role ?? 'operator')
  const [active, setActive] = useState(editing?.is_active ?? true)
  const [error, setError] = useState('')
  const [temporary, setTemporary] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getFormOptions()
      .then((o) => setDivisions(o.divisions))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await action()
      onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("That did not work."))
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (editing) {
      run(async () => {
        await changeUser(editing.id, {
          full_name: fullName, role, is_active: active, employee_id: employeeId, email, division,
          dsc_holder: role === 'reviewer' && dsc, emergency_duty: duty,
        })
        onClose()
      })
    } else {
      run(async () =>
        setTemporary(
          (await addUser({ username, full_name: fullName, role, employee_id: employeeId, email, division, dsc_holder: role === 'reviewer' && dsc, emergency_duty: duty }))
            .temporary_password,
        ),
      )
    }
  }

  let body: ReactNode
  if (temporary) {
    body = (
      <>
        <TemporaryPassword name={fullName} password={temporary} />
        <div className="row">
          <div className="grow" />
          <button type="button" className="btn btn-navy" onClick={onClose}>
            {t("Done")}
          </button>
        </div>
      </>
    )
  } else {
    body = (
      <form className="stack gap-14" onSubmit={submit}>
        {error && <div className="alert alert-red">{error}</div>}
        <div className="form-grid-2">
          <label className="field">
            <span className="field-label">{t("Full name")}</span>
            <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} required autoFocus />
          </label>
          <label className="field">
            <span className="field-label">{t("Employee ID")}</span>
            <input
              className="input"
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              autoCapitalize="characters"
              spellCheck={false}
              placeholder={t("e.g. EMP-11820")}
              required={!editing}
            />
          </label>
          <label className="field">
            <span className="field-label">{t("Official email")}</span>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@org.gov.in" />
          </label>
          <label className="field">
            <span className="field-label">{t("Division")}</span>
            <select className="input" value={division} onChange={(e) => setDivision(e.target.value)}>
              {[...new Set([...divisions, division])].map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">{t("Username {value}", { value: editing ? '' : t("(optional)") })}</span>
            {editing ? (
              <input className="input mono" value={editing.username} disabled />
            ) : (
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoCapitalize="none"
                spellCheck={false}
                placeholder={t("else the employee ID")}
              />
            )}
          </label>
        </div>
        <fieldset className="field role-fieldset">
          <legend className="field-label">{t("Role")}</legend>
          <div className="role-cards">
            {ROLE_CARDS.map((card) => (
              <label key={card.role} className={`role-option role-${card.role}${role === card.role ? ' is-checked' : ''}`}>
                <input type="radio" name="role" value={card.role} checked={role === card.role} onChange={() => setRole(card.role)} />
                <span className="role-option-icon">
                  <Icon name={card.icon} size={18} />
                </span>
                <span className="stack">
                  <strong>{t(card.title)}</strong>
                  <span className="muted small">{card.note}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <label className="row gap-10 toggle-row">
          <input type="checkbox" checked={role === 'reviewer' && dsc} disabled={role !== 'reviewer'} onChange={(e) => setDsc(e.target.checked)} />
          <span className="stack">
            <strong>{t("Holds a Class 3 DSC token")}</strong>
            <span className="muted small">{t("Reviewers only: needed to sign documents with a token")}</span>
          </span>
        </label>
        <label className="row gap-10 toggle-row">
          <input type="checkbox" checked={duty} onChange={(e) => setDuty(e.target.checked)} />
          <span className="stack">
            <strong>{t("On the emergency duty roster")}</strong>
            <span className="muted small">{t("Reviewers on duty are told first about emergency alerts")}</span>
          </span>
        </label>
        {editing && (
          <>
            <label className="row gap-10 toggle-row">
              <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} disabled={editing.id === me.id} />
              <span className="stack">
                <strong>{t("Account switched on")}</strong>
                <span className="muted small">{t("Switching it off signs the person out straight away.")}</span>
              </span>
            </label>
            <div className="row gap-10 wrap">
              {editing.locked && (
                <button
                  type="button"
                  className="btn btn-outline btn-xs"
                  disabled={busy}
                  onClick={() => run(async () => void (await changeUser(editing.id, { unlock: true })))}
                >
                  <Icon name="lock" size={14} strokeWidth={2} />
                  {t("Unlock now")}
                </button>
              )}
              {editing.id !== me.id && (
                <button
                  type="button"
                  className="btn btn-outline btn-xs"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm(t("Make a new temporary password for {full_name}? They will be signed out.", { full_name: editing.full_name })))
                      run(async () => setTemporary((await resetUserPassword(editing.id)).temporary_password))
                  }}
                >
                  <Icon name="key" size={14} strokeWidth={2} />
                  {t("Reset password")}
                </button>
              )}
            </div>
          </>
        )}
        <div className="row gap-10">
          <button type="button" className="btn btn-outline" onClick={onClose}>
            {t("Cancel")}
          </button>
          <div className="grow" />
          <button type="submit" className="btn btn-navy" disabled={busy}>
            <Icon name="check" size={18} strokeWidth={2.4} />
            {editing ? t("Save changes") : t("Create user")}
          </button>
        </div>
      </form>
    )
  }

  return (
    <div className="dialog-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <section className="card dialog" role="dialog" aria-modal="true" aria-labelledby="user-dialog-title">
        <div className="row gap-14">
          <span className="setup-card-icon">
            <Icon name="user" size={22} color="var(--navy)" />
          </span>
          <div className="stack gap-2 grow">
            <h2 id="user-dialog-title">{editing ? t("Edit {full_name}", { full_name: editing.full_name }) : t("Add a user")}</h2>
            <span className="muted small">
              {editing ? `@${editing.username}` : t("They will sign in with a temporary password and then set their own.")}
            </span>
          </div>
          <button type="button" className="icon-btn icon-btn-sm" aria-label={t("Close")} onClick={onClose}>
            <Icon name="cross" size={18} />
          </button>
        </div>
        {body}
      </section>
    </div>
  )
}
