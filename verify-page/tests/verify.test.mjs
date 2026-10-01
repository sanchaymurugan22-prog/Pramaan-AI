// Tests of verify.js, run by backend/tests/test_verify_page.py with a real published site:
//   VERIFY_SITE=<folder with records.json + public-key.pem>  VERIFY_FIXTURE=<fixture.json>  node --test verify-page/tests/
// Everything runs twice: with Web Crypto, and with the page's built-in SHA-256 / ECDSA code
// (what a phone uses on a plain http:// Wi-Fi address).
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'
import * as verify from '../verify.js'

const site = process.env.VERIFY_SITE
const fixture = JSON.parse(readFileSync(process.env.VERIFY_FIXTURE, 'utf8'))
const records = () => JSON.parse(readFileSync(join(site, 'records.json'), 'utf8'))
const pem = readFileSync(join(site, 'public-key.pem'), 'utf8')
const file = (name) => new Uint8Array(readFileSync(join(fixture.files_dir, name)))

for (const webCrypto of [true, false]) {
  const mode = webCrypto ? 'Web Crypto' : 'built-in code'
  const load = async (data = records()) => {
    verify.setUseWebCrypto(webCrypto)
    return verify.loadBook(data, await verify.importPublicKey(pem))
  }

  test(`${mode}: SHA-256 matches the standard`, async () => {
    verify.setUseWebCrypto(webCrypto)
    assert.equal(await verify.sha256Hex('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    assert.equal(await verify.sha256Hex(''), 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
    const big = new Uint8Array(200_003).map((_, i) => (i * 31) % 251)
    assert.equal(verify.hex(verify.sha256(big)), fixture.big_sha256)
  })

  test(`${mode}: every published record has a valid signature`, async () => {
    const book = await load()
    assert.equal(book.invalid, 0)
    assert.deepEqual(book.problems, [])
    assert.equal(book.records.size, fixture.issued)
  })

  test(`${mode}: genuine, replaced, withdrawn, not found`, async () => {
    const book = await load()
    assert.equal(verify.lookup(book, fixture.genuine).status, 'genuine')
    assert.equal(verify.lookup(book, fixture.genuine.toLowerCase() + ' ').status, 'genuine') // typed by hand
    assert.equal(verify.lookup(book, fixture.replaced).status, 'replaced')
    assert.equal(verify.lookup(book, fixture.replaced).record.replaced_by, fixture.replacement)
    const withdrawn = verify.lookup(book, fixture.withdrawn)
    assert.equal(withdrawn.status, 'withdrawn')
    assert.equal(withdrawn.record.withdrawn.reason, fixture.withdraw_reason)
    assert.equal(verify.lookup(book, 'PRM-1999-000001').status, 'not_found')
  })

  test(`${mode}: TLP:RED publishes no title`, async () => {
    const { record } = verify.lookup(await load(), fixture.restricted)
    assert.equal(record.restricted, true)
    assert.equal(record.title, undefined)
    assert.ok(record.files.every((f) => Object.keys(f).join() === 'sha256'))
  })

  test(`${mode}: a signed file is genuine; one changed byte is not`, async () => {
    const book = await load()
    const original = file(fixture.signed_file)
    const genuine = await verify.checkFile(book, original, fixture.genuine)
    assert.equal(genuine.status, 'genuine')
    assert.equal(genuine.file.name, fixture.signed_file)
    assert.equal((await verify.checkFile(book, original)).status, 'genuine') // found without a record number
    const changed = original.slice()
    changed[Math.floor(changed.length / 2)] ^= 1
    assert.equal((await verify.checkFile(book, changed, fixture.genuine)).status, 'changed')
    assert.equal((await verify.checkFile(book, changed)).status, 'not_found')
    assert.equal((await verify.checkFile(book, file(fixture.withdrawn_file))).status, 'withdrawn')
  })

  test(`${mode}: an edited record is rejected`, async () => {
    const data = records()
    const entry = data.entries.find((e) => e.record_no === fixture.genuine && e.kind === 'issue')
    entry.manifest = entry.manifest.replace('"restricted":false', '"restricted":false,"title":"Forged title"')
    const book = await load(data)
    assert.equal(book.invalid, 1)
    assert.equal(verify.lookup(book, fixture.genuine).status, 'not_found')
  })

  test(`${mode}: a dropped withdrawal is noticed`, async () => {
    const data = records()
    data.entries = data.entries.filter((e) => !(e.kind === 'withdraw' && e.record_no === fixture.withdrawn))
    const book = await load(data)
    assert.ok(book.problems.includes('missing'))
    assert.equal(verify.lookup(book, fixture.withdrawn).status, 'genuine') // which is why the page warns
  })

  test(`${mode}: a forged index or a bad signature fails`, async () => {
    const data = records()
    data.index = data.index.replace('"count":', '"count":1')
    assert.ok((await load(data)).problems.includes('index'))
    verify.setUseWebCrypto(webCrypto)
    const key = await verify.importPublicKey(pem)
    assert.equal(await verify.verifySignature(key, 'hello', 'not base64!'), false)
    assert.equal(await verify.verifySignature(key, 'hello', btoa('x'.repeat(64))), false)
  })
}

// ---- the message checker: the same answers as backend/app/signing/messages.py -------------------

test('normalising and text fingerprints match Python', async () => {
  for (const c of fixture.normalise) {
    assert.equal(verify.normalise(c.text), c.normalised, JSON.stringify(c.text))
    assert.equal(await verify.textHash(c.text), c.sha256, JSON.stringify(c.text))
  }
})

for (const webCrypto of [true, false]) {
  test(`message checker gives the same answers as Python (${webCrypto ? 'Web Crypto' : 'built-in code'})`, async () => {
    verify.setUseWebCrypto(webCrypto)
    const book = await verify.loadBook(records(), await verify.importPublicKey(pem))
    const published = verify.publishedRecords(book)
    for (const c of fixture.messages) {
      const result = await verify.checkMessage(c.text, published)
      const label = c.text.slice(0, 50)
      assert.equal(result.verdict, c.verdict, label)
      assert.equal(result.record_no, c.record_no, label)
      assert.deepEqual(result.signs.map((s) => s.kind).sort(), c.signs, label)
      assert.deepEqual(result.signs.map((s) => s.detail).sort(), c.sign_details, label)
      assert.deepEqual((result.diff || []).map((d) => [d.kind, d.text]), c.diff, label)
      if (c.similarity !== null) assert.ok(Math.abs(result.similarity - c.similarity) < 0.0002, label)
      assert.equal(result.helpline, 'Report cyber fraud: call 1930 or visit cybercrime.gov.in')
    }
  })
}

test('the cases cover every kind of answer', () => {
  const verdicts = new Set(fixture.messages.map((c) => c.verdict))
  // an exact match (genuine / replaced / withdrawn: the newest record with that text decides), a changed copy,
  // a scam and an unknown message
  assert.ok(['genuine', 'replaced', 'withdrawn'].some((v) => verdicts.has(v)), 'an exact match')
  for (const v of ['changed', 'scam', 'not_found']) assert.ok(verdicts.has(v), v)
})
