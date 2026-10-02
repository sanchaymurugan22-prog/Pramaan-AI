// Fourth code change for Stage 8: a sentence made of text and values is one text to translate, not several
// pieces (Hindi puts words in another order).
//   <p>{count} {t("items need")} {who} {t("attention")}</p>
//     -> <p>{t("{count} items need {who} attention", { count, who })}</p>
// Only children that are text, t("...") and values (no elements inside), with at least one of each.
const ts = require('typescript')
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, '..', 'src')

function files(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name)
    if (fs.statSync(full).isDirectory()) files(full, out)
    else if (full.endsWith('.tsx')) out.push(full)
  }
  return out
}

const isTLiteral = (e) => e && ts.isCallExpression(e) && ts.isIdentifier(e.expression) && e.expression.text === 't'
  && e.arguments.length === 1 && ts.isStringLiteral(e.arguments[0])
const hasJsx = (node) => {
  let found = false
  const walk = (n) => { if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n)) found = true; else ts.forEachChild(n, walk) }
  walk(node)
  return found
}
const nameOf = (expr) => {
  if (ts.isIdentifier(expr)) return expr.text
  if (ts.isPropertyAccessExpression(expr)) return expr.name.text
  if (ts.isCallExpression(expr) && expr.arguments[0]) return nameOf(expr.arguments[0])
  return 'value'
}

let total = 0
for (const file of files(SRC)) {
  const code = fs.readFileSync(file, 'utf8')
  const source = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const edits = []
  const visit = (node) => {
    if (ts.isJsxElement(node)) {
      const kids = node.children
      const parts = []
      let texts = 0, values = 0, ok = kids.length > 1
      for (const kid of kids) {
        if (!ok) break
        if (ts.isJsxText(kid)) {
          if (/^\s*$/.test(kid.text) && kid.text.includes('\n')) continue // dropped by JSX
          parts.push({ text: kid.text.replace(/\s+/g, ' ') })
        } else if (ts.isJsxExpression(kid) && kid.expression) {
          const e = kid.expression
          if (ts.isStringLiteral(e) && /^\s+$/.test(e.text)) parts.push({ text: ' ' }) // {' '}
          else if (isTLiteral(e)) { parts.push({ text: e.arguments[0].text }); texts++ }
          else if (hasJsx(e) || (ts.isStringLiteral(e))) ok = false
          else { parts.push({ expr: e }); values++ }
        } else ok = false // an element inside: left as it is
      }
      if (ok && texts > 0 && values > 0) {
        const used = new Set()
        let key = ''
        const args = []
        for (const part of parts) {
          if ('text' in part) key += part.text
          else {
            let name = nameOf(part.expr).replace(/\W/g, '') || 'value'
            let unique = name, i = 2
            while (used.has(unique)) unique = `${name}${i++}`
            used.add(unique)
            key += `{${unique}}`
            args.push(`${unique}: ${part.expr.getText()}`)
          }
        }
        key = key.replace(/\s+/g, ' ').trim()
        const first = kids[0]
        edits.push([first.getFullStart() > node.openingElement.getEnd() ? node.openingElement.getEnd() : first.getStart(),
                    node.closingElement.getStart(), `{t(${JSON.stringify(key)}, { ${args.join(', ')} })}`])
        return // nothing to do inside
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  if (!edits.length) continue
  let out = code
  for (const [start, end, text] of edits.sort((a, b) => b[0] - a[0])) out = out.slice(0, start) + text + out.slice(end)
  fs.writeFileSync(file, out)
  total += edits.length
}
console.log(`Merged ${total} sentences.`)
