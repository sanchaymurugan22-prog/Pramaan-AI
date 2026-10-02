// Renames local variables called "t" (they hide the t() of i18n) in the given files, using the TypeScript checker
// so only that variable and its uses change.  node scripts/rename-local-t.cjs <file> <new name> [<file> <new name> ...]
const ts = require('typescript')
const fs = require('fs')
const args = process.argv.slice(2)
for (let i = 0; i < args.length; i += 2) {
  const file = args[i], name = args[i + 1]
  const code = fs.readFileSync(file, 'utf8')
  const source = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  // every declaration of a local "t" (const t / parameter t), and the identifiers in its scope that refer to it
  const edits = []
  const scopes = []
  const visit = (node) => {
    if ((ts.isVariableDeclaration(node) || ts.isParameter(node)) && ts.isIdentifier(node.name) && node.name.text === 't') {
      const scope = ts.isParameter(node) ? node.parent : node.parent.parent.parent // the function / the block
      scopes.push([scope.getStart(), scope.getEnd(), node.name.getStart()])
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  const isCall = (id) => ts.isCallExpression(id.parent) && id.parent.expression === id && id.parent.arguments.length >= 1 &&
    (ts.isStringLiteral(id.parent.arguments[0]) || ts.isNoSubstitutionTemplateLiteral(id.parent.arguments[0]))
  const rename = (node) => {
    if (ts.isIdentifier(node) && node.text === 't' && !isCall(node) && !(ts.isPropertyAccessExpression(node.parent) && node.parent.name === node)
        && !ts.isImportSpecifier(node.parent) && !(ts.isPropertyAssignment(node.parent) && node.parent.name === node)) {
      if (scopes.some(([a, b]) => node.getStart() >= a && node.getEnd() <= b)) edits.push(node.getStart())
    }
    ts.forEachChild(node, rename)
  }
  rename(source)
  let out = code
  for (const at of [...new Set(edits)].sort((a, b) => b - a)) out = out.slice(0, at) + name + out.slice(at + 1)
  fs.writeFileSync(file, out)
  console.log(file, edits.length, 'renamed')
}
