// Collects every interface text that can be shown in Hindi, into src/i18n/keys.json (Stage 8):
//   - the first argument of every t("...") call
//   - label / title / detail / description / help fields of the lists in the code (shown with t(item.label))
//   - the fixed labels the backend sends (src/i18n/backend-keys.json, made by scripts/make-ui-hindi.py)
// Run:  node scripts/i18n-keys.cjs           (writes keys.json)
//       node scripts/i18n-keys.cjs --check   (fails if a key has no Hindi in hi.json; the backend tests run this)
const ts = require('typescript')
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, '..', 'src')
const FIELDS = new Set(['label', 'title', 'detail', 'description', 'help'])
const keys = new Set()

function files(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    if (fs.statSync(full).isDirectory()) { if (name !== 'i18n') files(full, out) }
    else if (/\.(tsx?|ts)$/.test(full)) out.push(full)
  }
  return out
}

const readable = (text) => /[A-Za-z]{2}/.test(text)
for (const file of files(SRC)) {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true,
    file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 't') {
      const first = node.arguments[0]
      if (first && (ts.isStringLiteral(first) || ts.isNoSubstitutionTemplateLiteral(first))) keys.add(first.text)
    }
    if (ts.isPropertyAssignment(node) && FIELDS.has(node.name.getText()) && ts.isStringLiteral(node.initializer)
        && readable(node.initializer.text)) keys.add(node.initializer.text)
    ts.forEachChild(node, visit)
  }
  visit(source)
}
const backend = path.join(SRC, 'i18n', 'backend-keys.json')
if (fs.existsSync(backend)) JSON.parse(fs.readFileSync(backend, 'utf8')).forEach((k) => keys.add(k))

const sorted = [...keys].sort()
if (process.argv.includes('--check')) {
  const hi = JSON.parse(fs.readFileSync(path.join(SRC, 'i18n', 'hi.json'), 'utf8'))
  const missing = sorted.filter((k) => !(k in hi))
  if (missing.length) {
    console.error(`${missing.length} interface texts have no Hindi in src/i18n/hi.json, e.g.:\n  ` + missing.slice(0, 10).join('\n  '))
    console.error('Run: backend/.venv/bin/python scripts/make-ui-hindi.py')
    process.exit(1)
  }
  console.log(`All ${sorted.length} interface texts have Hindi.`)
} else {
  fs.writeFileSync(path.join(SRC, 'i18n', 'keys.json'), JSON.stringify(sorted, null, 1) + '\n')
  console.log(`${sorted.length} interface texts in src/i18n/keys.json`)
}
