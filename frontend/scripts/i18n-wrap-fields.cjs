// Fifth code change for Stage 8: text given to the screen through fields and small variables INSIDE functions
// (worked out while drawing, so t() sees the current language):
//   { label: 'Hours saved (est.)', note: 'Compared with manual writing' }  -> { label: t('...'), note: t('...') }
//   const word = ok ? 'OK' : 'Not checked'                              -> const word = ok ? t('OK') : t('Not checked')
//   <JobsTable caption="Recent jobs" />                                 -> caption={t("Recent jobs")}
// Module-level lists are left alone (they are translated where they are shown: t(item.label)).
const ts = require('typescript')
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, '..', 'src')
const FIELDS = new Set(['note', 'caption', 'hint', 'help', 'label', 'title', 'detail', 'description', 'message', 'word', 'heading', 'summary', 'tip', 'lead', 'reason'])
const SKIP_FILES = new Set(['OutputViews.tsx', 'trace.tsx', 'TracePanels.tsx', 'VersionCompare.tsx'])
const codeLike = (text) => (/^[\w./:#@-]+$/.test(text) && /[./_:#@0-9]/.test(text)) || /^[A-Z0-9 :_·-]+$/.test(text)
const readable = (text) => /[A-Za-z]{2}/.test(text) && !codeLike(text.trim()) && !/^#\/|https?:|^(chip|btn|alert|tone|is-|card)\b/.test(text)

function files(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    if (fs.statSync(full).isDirectory()) files(full, out)
    else if (full.endsWith('.tsx') && !SKIP_FILES.has(name)) out.push(full)
  }
  return out
}

const insideFunction = (node) => {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isFunctionDeclaration(p) || ts.isArrowFunction(p) || ts.isFunctionExpression(p) || ts.isMethodDeclaration(p)) return true
  }
  return false
}

let total = 0
for (const file of files(SRC)) {
  const code = fs.readFileSync(file, 'utf8')
  const source = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const edits = []
  const isT = (n) => n && ts.isCallExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === 't'
  const wrap = (node) => {
    if (!node || isT(node.parent)) return
    if (ts.isParenthesizedExpression(node)) return wrap(node.expression)
    if (ts.isConditionalExpression(node)) return (wrap(node.whenTrue), wrap(node.whenFalse))
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
        let name = ts.isIdentifier(span.expression) ? span.expression.text
          : ts.isPropertyAccessExpression(span.expression) ? span.expression.name.text : 'n'
        let unique = name, i = 2
        while (used.has(unique)) unique = `${name}${i++}`
        used.add(unique)
        key += `{${unique}}` + span.literal.text
        values.push(`${unique}: ${span.expression.getText()}`)
      }
      edits.push([node.getStart(), node.getEnd(), `t(${JSON.stringify(key)}, { ${values.join(', ')} })`])
    }
  }
  const visit = (node) => {
    if (ts.isPropertyAssignment(node) && FIELDS.has(node.name.getText()) && insideFunction(node)) wrap(node.initializer)
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && FIELDS.has(node.name.text) && node.initializer && insideFunction(node)) wrap(node.initializer)
    if (ts.isJsxAttribute(node) && node.name.getText() === 'caption' && node.initializer) {
      if (ts.isStringLiteral(node.initializer) && readable(node.initializer.text)) {
        edits.push([node.initializer.getStart(), node.initializer.getEnd(), `{t(${JSON.stringify(node.initializer.text)})}`])
      } else if (ts.isJsxExpression(node.initializer)) wrap(node.initializer.expression)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  if (!edits.length) continue
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
console.log(`Wrapped ${total} fields.`)
