// Pramaan Verify: the checking logic, with no page code (so the same file runs in Node tests).
// Everything happens in the browser. Nothing is uploaded, and there are no secrets here: only the
// published records (records.json) and the public key (public-key.pem).
//
// Signatures: ECDSA P-256 with SHA-256, raw r||s (64 bytes, base64).
// Web Crypto (crypto.subtle) checks them when the browser offers it. Browsers only offer it on
// https:// or localhost pages, NOT on a plain http:// address on the local Wi-Fi (how a phone reaches
// the demo laptop), so a small built-in SHA-256 and ECDSA P-256 check (below) is used there instead.

const encoder = new TextEncoder()
let useWebCrypto = Boolean(globalThis.crypto && globalThis.crypto.subtle)

// For tests: force the built-in code even where Web Crypto exists.
export function setUseWebCrypto(on) {
  useWebCrypto = on && Boolean(globalThis.crypto && globalThis.crypto.subtle)
}
export const usingWebCrypto = () => useWebCrypto

// ---- bytes ---------------------------------------------------------------------------------------

export function hex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

export function base64ToBytes(text) {
  const binary = atob(text)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

const toBytes = (data) => (typeof data === 'string' ? encoder.encode(data) : new Uint8Array(data))

// ---- SHA-256 -------------------------------------------------------------------------------------

export async function sha256Hex(data) {
  const bytes = toBytes(data)
  if (useWebCrypto) return hex(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
  return hex(sha256(bytes))
}

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
  0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
  0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
  0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
])

// Plain SHA-256 (FIPS 180-4), for pages where Web Crypto is not available.
export function sha256(bytes) {
  const length = bytes.length
  const padded = new Uint8Array(((length + 9 + 63) >> 6) << 6)
  padded.set(bytes)
  padded[length] = 0x80
  const view = new DataView(padded.buffer)
  view.setUint32(padded.length - 8, Math.floor((length * 8) / 2 ** 32))
  view.setUint32(padded.length - 4, (length * 8) >>> 0)
  const h = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19])
  const w = new Uint32Array(64)
  const rotr = (x, n) => (x >>> n) | (x << (32 - n))
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(offset + i * 4)
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3)
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10)
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, hh] = h
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) >>> 0
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0
      hh = g
      g = f
      f = e
      e = (d + t1) >>> 0
      d = c
      c = b
      b = a
      a = (t1 + t2) >>> 0
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh // prettier-ignore
  }
  const out = new Uint8Array(32)
  const outView = new DataView(out.buffer)
  h.forEach((value, i) => outView.setUint32(i * 4, value))
  return out
}

// ---- ECDSA P-256 ---------------------------------------------------------------------------------

const P = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffffn
const N = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551n
const B = 0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604bn
const G = {
  x: 0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296n,
  y: 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5n,
}

const mod = (a, m) => ((a % m) + m) % m
function power(base, exponent, m) {
  let result = 1n
  base = mod(base, m)
  while (exponent > 0n) {
    if (exponent & 1n) result = (result * base) % m
    base = (base * base) % m
    exponent >>= 1n
  }
  return result
}
const inverse = (a, m) => power(a, m - 2n, m) // m is prime
const bytesToBig = (bytes) => BigInt('0x' + (hex(bytes) || '0'))

// Points in Jacobian coordinates [X, Y, Z]; Z = 0 is "infinity".
function double([x, y, z]) {
  if (y === 0n || z === 0n) return [0n, 1n, 0n]
  const delta = (z * z) % P
  const gamma = (y * y) % P
  const beta = (x * gamma) % P
  const alpha = (3n * mod(x - delta, P) * ((x + delta) % P)) % P
  const x3 = mod(alpha * alpha - 8n * beta, P)
  const z3 = mod((y + z) ** 2n - gamma - delta, P)
  const y3 = mod(alpha * (4n * beta - x3) - 8n * gamma * gamma, P)
  return [x3, y3, z3]
}

function add(p1, p2) {
  if (p1[2] === 0n) return p2
  if (p2[2] === 0n) return p1
  const [x1, y1, z1] = p1
  const [x2, y2, z2] = p2
  const z1z1 = (z1 * z1) % P
  const z2z2 = (z2 * z2) % P
  const u1 = (x1 * z2z2) % P
  const u2 = (x2 * z1z1) % P
  const s1 = (y1 * z2 * z2z2) % P
  const s2 = (y2 * z1 * z1z1) % P
  if (u1 === u2) return s1 === s2 ? double(p1) : [0n, 1n, 0n]
  const h = mod(u2 - u1, P)
  const i = (4n * h * h) % P
  const j = (h * i) % P
  const r = mod(2n * (s2 - s1), P)
  const v = (u1 * i) % P
  const x3 = mod(r * r - j - 2n * v, P)
  const y3 = mod(r * (v - x3) - 2n * s1 * j, P)
  const z3 = mod(((z1 + z2) ** 2n - z1z1 - z2z2) * h, P)
  return [x3, y3, z3]
}

function multiply(k, point) {
  let result = [0n, 1n, 0n]
  for (let i = BigInt(k.toString(2).length) - 1n; i >= 0n; i--) {
    result = double(result)
    if ((k >> i) & 1n) result = add(result, point)
  }
  return result
}

function affineX([x, , z]) {
  const zInverse = inverse(z, P)
  return (x * zInverse * zInverse) % P
}

function onCurve({ x, y }) {
  return mod(y * y - (x * x * x - 3n * x + B), P) === 0n
}

// The ECDSA check itself (FIPS 186-4): built-in code for pages without Web Crypto.
export function ecdsaVerify(point, hashBytes, signature) {
  if (signature.length !== 64 || !onCurve(point)) return false
  const r = bytesToBig(signature.slice(0, 32))
  const s = bytesToBig(signature.slice(32))
  if (r <= 0n || r >= N || s <= 0n || s >= N) return false
  const e = bytesToBig(hashBytes)
  const w = inverse(s, N)
  const sum = add(multiply((e * w) % N, [G.x, G.y, 1n]), multiply((r * w) % N, [point.x, point.y, 1n]))
  if (sum[2] === 0n) return false
  return affineX(sum) % N === r
}

export function pemToDer(pem) {
  return base64ToBytes(pem.replace(/-----[^-]+-----/g, '').replace(/\s+/g, ''))
}

// The public key: the Web Crypto key when available, and always the point itself.
export async function importPublicKey(pem) {
  const der = pemToDer(pem)
  const raw = der.slice(der.length - 65) // an uncompressed P-256 point: 0x04 || X || Y
  if (raw[0] !== 4) throw new Error('Not an uncompressed P-256 public key')
  const point = { x: bytesToBig(raw.slice(1, 33)), y: bytesToBig(raw.slice(33)) }
  let cryptoKey = null
  if (useWebCrypto) {
    cryptoKey = await crypto.subtle.importKey('spki', der, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify'])
  }
  return { point, cryptoKey, keyId: (await sha256Hex(der)).slice(0, 16) }
}

export async function verifySignature(key, text, signatureBase64) {
  let signature
  try {
    signature = base64ToBytes(signatureBase64)
  } catch {
    return false
  }
  const data = toBytes(text)
  if (useWebCrypto && key.cryptoKey) {
    return crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, key.cryptoKey, signature, data)
  }
  return ecdsaVerify(key.point, sha256(data), signature)
}

// ---- the published record book -------------------------------------------------------------------

// Reads records.json. Only entries with a valid signature count. The signed index lists every
// entry, so a host cannot quietly drop one (for example a withdrawal).
export async function loadBook(data, key) {
  const records = new Map()
  let invalid = 0
  const problems = []
  const indexOk = data.index && (await verifySignature(key, data.index, data.index_signature))
  const index = indexOk ? JSON.parse(data.index) : null
  if (!indexOk) problems.push('index')
  const listed = new Set(index ? index.entries : [])

  for (const entry of data.entries || []) {
    let ok = false
    try {
      ok = await verifySignature(key, entry.manifest, entry.signature)
    } catch {
      ok = false
    }
    const manifest = ok ? JSON.parse(entry.manifest) : null
    if (!ok || manifest.record_no !== entry.record_no || manifest.kind !== entry.kind) {
      invalid++
      continue
    }
    listed.delete(await sha256Hex(entry.manifest))
    if (manifest.kind === 'issue') {
      records.set(manifest.record_no, { ...manifest, withdrawn: null, replaced_by: null })
    } else if (manifest.kind === 'withdraw' && records.has(manifest.record_no)) {
      records.get(manifest.record_no).withdrawn = manifest
    }
  }
  for (const record of records.values()) {
    if (record.replaces && records.has(record.replaces)) records.get(record.replaces).replaced_by = record.record_no
  }
  if (index && listed.size > 0) problems.push('missing')
  return { records, invalid, problems, index, keyId: key.keyId }
}

export function cleanRecordNo(text) {
  return String(text || '').trim().toUpperCase()
}

// genuine | replaced (still genuine, but a newer version exists) | withdrawn | not_found
export function lookup(book, recordNo) {
  const record = book.records.get(cleanRecordNo(recordNo))
  if (!record) return { status: 'not_found', record: null }
  if (record.withdrawn) return { status: 'withdrawn', record }
  if (record.replaced_by) return { status: 'replaced', record }
  return { status: 'genuine', record }
}

// Which records (if any) have a file with this fingerprint.
export function findFile(book, sha256) {
  const found = []
  for (const record of book.records.values()) {
    for (const file of record.files || []) if (file.sha256 === sha256) found.push({ record, file })
  }
  return found
}

// A dropped file: genuine (matches a record) | withdrawn | changed (not in the record asked for) | not_found
export async function checkFile(book, bytes, recordNo = '') {
  const sha256 = await sha256Hex(bytes)
  if (recordNo) {
    const { record } = lookup(book, recordNo)
    const file = record && (record.files || []).find((f) => f.sha256 === sha256)
    if (!record) return { status: 'not_found', sha256, record: null, file: null }
    if (!file) return { status: 'changed', sha256, record, file: null }
    return { status: record.withdrawn ? 'withdrawn' : 'genuine', sha256, record, file }
  }
  const [match] = findFile(book, sha256)
  if (!match) return { status: 'not_found', sha256, record: null, file: null }
  return { status: match.record.withdrawn ? 'withdrawn' : 'genuine', sha256, ...match }
}
