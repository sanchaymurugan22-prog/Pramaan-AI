// Second one-time code change for Stage 8: labels shown from lists and API answers, e.g. {item.label},
// {card.title}, {check.detail}, become {t(item.label)}. Content (outputs, sources, job and record titles) is
// left alone: the output views are skipped, and so are c.*, content.*, job.*, record.*, source.*, scene.*.
const ts = require('typescript')
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, '..', 'src')
const PROPS = new Set(['label', 'title', 'detail', 'description'])
const SKIP_FILES = new Set(['OutputViews.tsx', 'trace.tsx', 'TracePanels.tsx', 'VersionCompare.tsx'])
const CONTENT = new Set(['c', 'content', 'job', 'record', 'source', 'scene', 'slide', 'comment', 'entry', 'note',
  'found', 'sentence', 'fact', 'viewed', 'version', 'user', 'u', 'request', 'r'])
const ATTRS = new Set(['aria-label', 'title', 'placeholder', 'alt', 'label', 'detail'])

function files(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    if (fs.statSync(full).isDirectory()) files(full, out)
    else if (full.endsWith('.tsx') && !SKIP_FILES.has(name)) out.push(full)
  }
  return out
}

let total = 0
for (const file of files(SRC)) {
  const code = fs.readFileSync(file, 'utf8')
  const source = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const edits = []
  const wanted = (expr) => {
    if (!expr || !ts.isPropertyAccessExpression(expr) || !PROPS.has(expr.name.text)) return false
    let root = expr.expression
    while (ts.isPropertyAccessExpression(root) || ts.isNonNullExpression(root)) root = root.expression
    return !(ts.isIdentifier(root) && CONTENT.has(root.text))
  }
  const visit = (node) => {
    if (ts.isJsxExpression(node) && node.expression && wanted(node.expression)) {
      const parent = node.parent
      const inAttribute = ts.isJsxAttribute(parent)
      if (!inAttribute || ATTRS.has(parent.name.getText())) {
        edits.push([node.expression.getStart(), node.expression.getEnd(), `t(${node.expression.getText()})`])
      }
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
    const last = imports[imports.length - 1]
    const at = out.indexOf('\n', out.indexOf(" from '", last.index) + 1) + 1
    out = out.slice(0, at) + `import { t } from '${spec}'\n` + out.slice(at)
  }
  fs.writeFileSync(file, out)
  total += edits.length
}
console.log(`Wrapped ${total} labels.`)
