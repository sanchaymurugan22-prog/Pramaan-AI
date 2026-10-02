// One-time code change for Stage 8 (kept for new screens): wraps the interface text of every .tsx file in t()
// so it can be shown in Hindi.  Run:  node scripts/i18n-wrap.cjs  (then: node scripts/i18n-keys.cjs)
//   <h2>Outputs</h2>                 ->  <h2>{t("Outputs")}</h2>
//   placeholder="Search jobs"        ->  placeholder={t("Search jobs")}
// Code-like text (paths, commands, ALL-CAPS codes) and text inside <code>, <pre> and <kbd> is left alone.
const ts = require('typescript')
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, '..', 'src')
const ATTRS = new Set(['placeholder', 'aria-label', 'title', 'alt', 'label', 'detail'])
const RAW_TAGS = new Set(['code', 'pre', 'kbd', 'samp'])
const ENTITIES = { amp: '&', nbsp: ' ', lt: '<', gt: '>', quot: '"', apos: "'", rsquo: '’', lsquo: '‘',
  ldquo: '“', rdquo: '”', hellip: '…', middot: '·', mdash: '—', ndash: '–', times: '×', rarr: '→', larr: '←' }

const decode = (text) =>
  text.replace(/&(#x?[0-9a-fA-F]+|\w+);/g, (whole, name) => {
    if (name[0] === '#') return String.fromCodePoint(name[1] === 'x' ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10))
    return ENTITIES[name] ?? whole
  })

// code-like: one token with a dot, slash, underscore, colon, #, @ or digit (backend/.venv, TLP:AMBER, F3), or ALL CAPS
const codeLike = (text) => (/^[\w./:#@-]+$/.test(text) && /[./_:#@0-9]/.test(text)) || /^[A-Z0-9 :_·-]+$/.test(text)
const wanted = (text) => /[A-Za-z]{2}/.test(text) && !codeLike(text)

function files(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    if (fs.statSync(full).isDirectory()) files(full, out)
    else if (full.endsWith('.tsx')) out.push(full)
  }
  return out
}

let changedFiles = 0, wrapped = 0
for (const file of files(SRC)) {
  const code = fs.readFileSync(file, 'utf8')
  const source = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const edits = []
  const insideRawTag = (node) => {
    for (let p = node.parent; p; p = p.parent) {
      if (ts.isJsxElement(p) && RAW_TAGS.has(p.openingElement.tagName.getText())) return true
    }
    return false
  }
  const visit = (node) => {
    if (ts.isJsxText(node) && !insideRawTag(node)) {
      const raw = node.getText()
      const core = decode(raw).replace(/\s+/g, ' ').trim()
      if (core && wanted(core)) {
        const lead = raw.match(/^\s*/)[0]
        const trail = raw.match(/\s*$/)[0]
        edits.push([node.getStart(), node.getEnd(), `${lead}{t(${JSON.stringify(core)})}${trail}`])
      }
    }
    if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer) && ATTRS.has(node.name.getText())) {
      const text = node.initializer.text
      if (wanted(text)) edits.push([node.initializer.getStart(), node.initializer.getEnd(), `{t(${JSON.stringify(text)})}`])
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  if (!edits.length) continue
  let out = code
  for (const [start, end, text] of edits.sort((a, b) => b[0] - a[0])) out = out.slice(0, start) + text + out.slice(end)
  if (!/import \{[^}]*\bt\b[^}]*\} from '[./]*i18n'/.test(out)) {
    const relative = path.relative(path.dirname(file), path.join(SRC, 'i18n')).split(path.sep).join('/')
    const spec = relative.startsWith('.') ? relative : `./${relative}`
    const imports = [...out.matchAll(/^import .*$/gm)]
    const last = imports.length ? imports[imports.length - 1] : null
    // the last import may span lines: find the end of its statement
    let at = 0
    if (last) {
      const statementEnd = out.indexOf('\n', out.indexOf(" from '", last.index) + 1)
      at = statementEnd + 1
    }
    out = out.slice(0, at) + `import { t } from '${spec}'\n` + out.slice(at)
  }
  fs.writeFileSync(file, out)
  changedFiles++
  wrapped += edits.length
}
console.log(`Wrapped ${wrapped} texts in ${changedFiles} files.`)
