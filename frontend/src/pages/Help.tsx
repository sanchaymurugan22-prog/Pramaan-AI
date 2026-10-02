// Help (Stage 9B): a short guide that works offline, written for the role that is signed in, and the
// friendly page for addresses a role may not open ("You don't have access") or that do not exist.
import type { ReactNode } from 'react'
import type { Role } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/Icon'
import { links } from '../router'
import { t } from '../i18n'

const HOME: Record<Role, { href: string; label: string }> = {
  operator: { href: links.dashboard, label: 'Go to your dashboard' },
  reviewer: { href: links.review, label: 'Go to the review queue' },
  admin: { href: links.adminHome, label: 'Go to the overview' },
}

function Topic({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="card card-pad help-topic">
      <summary>{title}</summary>
      <div className="stack gap-8 help-body">{children}</div>
    </details>
  )
}

export function Help() {
  const { user } = useAuth()
  return (
    <main className="page">
      <div className="page-head">
        <div className="stack gap-2">
          <div className="eyebrow">{t("Help")}</div>
          <h1>{t("How Pramaan AI works")}</h1>
          <p className="muted page-lead">{t("Everything here works offline. Nothing you do leaves this computer.")}</p>
        </div>
      </div>

      <section className="card card-pad stack gap-10" aria-label={t("In short")}>
        <h2>{t("In short")}</h2>
        <ol className="clean-list">
          <li>{t("An Operator adds a report. A safety check finds private data and hidden instructions before any AI reads it.")}</li>
          <li>{t("The AI reads the report once and writes a fact sheet; every output is written from that fact sheet.")}</li>
          <li>{t("Every sentence is linked to the place in the report it comes from. Anything not found there is marked.")}</li>
          <li>{t("A Reviewer checks the outputs, then approves and signs them. Signed files get a QR code and a record number.")}</li>
          <li>{t("Anyone can check a document or a forwarded message on the “Is this real?” page.")}</li>
        </ol>
      </section>

      <div className="stack gap-10">
        {user.role === 'operator' && (
          <>
            <Topic title={t("Making a transformation")}>
              <p>
                <a href={links.newJob}>{t("New transformation")}</a>{t(": add text or files (.txt, .pdf, .docx) → the Safety check (choose what to hide and the sharing label, TLP) → choose the outputs → Generate. You can leave the progress page; a notification says when it is done.")}
              </p>
            </Topic>
            <Topic title={t("Yellow and red marks in the results")}>
              <p>
                {t("Click any sentence to see its source on the right.")} <strong>{t("Not linked to a fact")}</strong> {t("(yellow) means the sentence uses no fact from the fact sheet: edit it or remove it.")} <strong>{t("Not in source")}</strong> {t("(red) marks a number, date or name that is not in the report. The quality score counts these.")}
              </p>
            </Topic>
            <Topic title={t("Watch folder and emergency alerts")}>
              <p>
                {t("Files dropped in your")} <a href={links.watch}>{t("watch folder")}</a> {t("become drafts that wait at the Safety check: nothing is written until you start it. An")} <a href={links.emergency}>{t("emergency alert")}</a> {t("goes to the Reviewers on duty first.")}
              </p>
            </Topic>
          </>
        )}
        {user.role === 'reviewer' && (
          <>
            <Topic title={t("Reviewing a kit")}>
              <p>
                {t("Open a job from the")} <a href={links.review}>{t("review queue")}</a>{t(". Click a sentence to see its source and to comment on it. The automatic checks on the right say what the app already checked.")}
              </p>
            </Topic>
            <Topic title={t("Approving and signing")}>
              <p>
                <strong>{t("Approve & sign")}</strong> {t("seals every file: each gets a QR code, and the job gets a numbered entry in the record book. Signed files cannot be changed; a change needs a new version and a new signature. You cannot review a job you worked on.")}
              </p>
            </Topic>
            <Topic title={t("Sending back")}>
              <p>{t("Pick the reasons, keep your line comments, and write a note. The Operator sees each comment next to its sentence.")}</p>
            </Topic>
          </>
        )}
        {user.role === 'admin' && (
          <>
            <Topic title={t("Accounts")}>
              <p>
                <a href={links.users}>{t("Users & access")}</a>{t(": add people (they get a temporary password, shown once), approve access requests, reset passwords. Admins do not see job content.")}
              </p>
            </Topic>
            <Topic title={t("Security, letterhead, backups")}>
              <p>
                <a href={links.security}>{t("Security & policies")}</a> {t("changes what the scanner looks for and the sign-in rules (all changes are in the audit trail).")} <a href={links.templates}>{t("Templates")}</a> {t("sets the office name and logo on every file.")}{' '}
                <a href={links.backup}>{t("Updates & backup")}</a> {t("makes an encrypted backup: keep a copy of .env separately, it holds the key.")}
              </p>
            </Topic>
            <Topic title={t("Record book and the public page")}>
              <p>
                {t("The")} <a href={links.recordBook}>{t("record book")}</a> {t("lists every signed document; withdraw a record if an advisory is withdrawn. To update the public verify page, export the update file on")} <a href={links.publicPage}>{t("Public verify page")}</a> {t("and copy it by USB.")}
              </p>
            </Topic>
          </>
        )}
        <Topic title={t("Keyboard")}>
          <ul className="clean-list">
            <li>{t("Tab moves between controls; the first Tab shows “Skip to main content”.")}</li>
            <li>{t("In the results, the arrow keys move between output tabs.")}</li>
            <li>{t("In the search box: type, then ↓ ↑ and Enter; Escape closes the list.")}</li>
            <li>{t("Escape closes dialogs and the menu.")}</li>
          </ul>
        </Topic>
        <Topic title={t("Something is wrong")}>
          <p>
            {t("If the AI does not answer, the Admin can run a speed test on the AI models page. If you forgot your password, use “Forgot password?” on the sign-in page: your Admin gives you a one-time password.")}
          </p>
        </Topic>
      </div>
    </main>
  )
}

export function NoAccess({ notFound = false }: { notFound?: boolean }) {
  const { user } = useAuth()
  const home = HOME[user.role]
  return (
    <main className="page">
      <section className="card card-pad stack gap-14 center-items center no-access" aria-labelledby="no-access-title">
        <span className="no-access-icon" aria-hidden="true">
          <Icon name={notFound ? 'search' : 'lock'} size={36} color="var(--navy)" />
        </span>
        <h1 id="no-access-title">{notFound ? t("This page does not exist") : t("You don’t have access to this page")}</h1>
        <p className="muted">
          {notFound
            ? t("The address may be mistyped, or the page has moved.")
            : t("This page is for another role. You are signed in as {role_label}. If you need it, ask your Admin.", { role_label: t(user.role_label) })}
        </p>
        <a className="btn btn-navy" href={home.href}>
          <Icon name="arrowLeft" size={18} strokeWidth={2} />
          {t(home.label)}
        </a>
      </section>
    </main>
  )
}
