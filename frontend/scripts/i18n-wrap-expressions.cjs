// Third one-time code change for Stage 8: text inside expressions.
//   {done ? 'Saved' : 'Not saved'}           -> {done ? t('Saved') : t('Not saved')}
//   {`${count} outputs ready`}               -> {t('{count} outputs ready', { count })}
//   setError('Could not save.') / confirm(`Delete ${name}?`) / save(..., 'Saved.')  -> messages through t()
// Only in what is shown: JSX children, the attributes people read (aria-label, title, placeholder ...), and the
// messages above. Class names, links and code-like text are left alone.
const ts = require('typescript')
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, '..', 'src')
const ATTRS = new Set(['placeholder', 'aria-label', 'title', 'alt', 'label', 'detail', 'aria-valuetext'])
const MESSAGES = new Set(['setError', 'setNotice', 'setMessage', 'confirm'])
const SKIP_FILES = new Set(['trace.tsx'])

const codeLike = (text) => (/^[\w./:#@-]+$/.test(text) && /[./_:#@0-9]/.test(text)) || /^[A-Z0-9 :_·-]+$/.test(text)
const readable = (text) => /[A-Za-z]{2}/.test(text) && !codeLike(text.trim()) && !/^#\/|https?:|\.(svg|png|json)\b/.test(text)

function files(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    if (fs.statSync(full).isDirectory()) files(full, out)
    else if (full.endsWith('.tsx') && !SKIP_FILES.has(name)) out.push(full)
  }
  return out
}

function placeholderName(expr, used) {
  let name = ts.isIdentifier(expr) ? expr.text
    : ts.isPropertyAccessExpression(expr) ? expr.name.text
    : 'n'
  if (!/^\w+$/.test(name)) name = 'n'
  let unique = name, i = 2
  while (used.has(unique)) unique = `${name}${i++}`
  used.add(unique)
  return unique
}

let total = 0
for (const file of files(SRC)) {
  const code = fs.readFileSync(file, 'utf8')
  const source = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const edits = []
  const isTCall = (node) => ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 't'

  // wrap one value (a literal, a template, or the text branches of a condition)
  const wrap = (node) => {
    if (!node || (node.parent && isTCall(node.parent))) return
    if (ts.isParenthesizedExpression(node)) return wrap(node.expression)
    if (ts.isConditionalExpression(node)) return (wrap(node.whenTrue), wrap(node.whenFalse))
    if (ts.isBinaryExpression(node)) {
      const op = node.operatorToken.kind
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return wrap(node.right)
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return (wrap(node.left), wrap(node.right))
      return
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      if (readable(node.text)) edits.push([node.getStart(), node.getEnd(), `t(${JSON.stringify(node.text)})`])
      return
    }
    if (ts.isTemplateExpression(node)) {
      const statics = [node.head.text, ...node.templateSpans.map((s) => s.literal.text)].join(' ')
      if (!readable(statics)) return
      const used = new Set()
      let key = node.head.text
      const values = []
      for (const span of node.templateSpans) {
        const name = placeholderName(span.expression, used)
        key += `{${name}}` + span.literal.text
        values.push(`${name}: ${span.expression.getText()}`)
      }
      edits.push([node.getStart(), node.getEnd(), `t(${JSON.stringify(key)}, { ${values.join(', ')} })`])
    }
  }

  const visit = (node) => {
    if (ts.isJsxExpression(node) && node.expression) {
      const parent = node.parent
      if (ts.isJsxElement(parent) || ts.isJsxFragment(parent)) wrap(node.expression)
      else if (ts.isJsxAttribute(parent) && ATTRS.has(parent.name.getText())) wrap(node.expression)
    }
    if (ts.isCallExpression(node)) {
      const callee = node.expression
      const name = ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : ''
      if (MESSAGES.has(name) && node.arguments[0]) wrap(node.arguments[0])
      if (name === 'save' && node.arguments[1]) wrap(node.arguments[1]) // Profile: save(change, 'Saved.')
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  if (!edits.length) continue
  // inner edits first would break outer ones: keep only edits not inside another edit
  edits.sort((a, b) => a[0] - b[0] || b[1] - a[1])
  const kept = []
  for (const e of edits) if (!kept.some((k) => e[0] >= k[0] && e[1] <= k[1])) kept.push(e)
  let out = code
  for (const [start, end, text] of kept.sort((a, b) => b[0] - a[0])) out = out.slice(0, start) + text + out.slice(end)
  if (!/import \{[^}]*\bt\b[^}]*\} from '[./]*i18n'/.test(out)) {
    const relative = path.relative(path.dirname(file), path.join(SRC, 'i18n')).split(path.sep).join('/')
    const spec = relative.startsWith('.') ? relative : `./${relative}`
    const imports = [...out.matchAll(/^import .*$/gm)]
    const last = imports[imports.length - 1]
    const at = last ? out.indexOf('\n', out.indexOf(" from '", last.index) + 1) + 1 : 0
    out = out.slice(0, at) + `import { t } from '${spec}'\n` + out.slice(at)
  }
  fs.writeFileSync(file, out)
  total += kept.length
}
console.log(`Wrapped ${total} expressions.`)
