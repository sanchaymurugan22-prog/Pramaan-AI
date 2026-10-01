// Pramaan Verify: the page. The checking itself is in verify.js.
//   ./?r=PRM-2026-000001   what a QR code opens: is this record genuine, withdrawn or unknown?
//   #scan                  scan with the camera here (where the browser can read QR codes), or with the
//                          phone's own camera app, which opens the ?r= address
//   #file                  drop a file: its SHA-256 is worked out here and compared with the records
//   #message               paste a forwarded message: genuine, changed, or signs of a scam
// Labels in English and Hindi (the button at the top right). Nothing is uploaded anywhere.
import {
  checkFile, checkMessage, cleanRecordNo, importPublicKey, loadBook, lookup, publishedRecords, usingWebCrypto,
} from './verify.js'

// ---- words -------------------------------------------------------------------------------------

const WORDS = {
  en: {
    brandSub: 'प्रमाण · Is this real?',
    langButton: 'हिं',
    langLabel: 'हिन्दी में देखें',
    title: 'Is this real?',
    lead: 'Check any government alert or advisory before you trust it or share it.',
    scanTitle: 'Scan the QR code',
    scanNote: 'On the printed or shared document',
    fileTitle: 'Upload the file',
    fileNote: 'PDF, image or Word file',
    privacy: 'Checks happen on your phone. Nothing is uploaded.',
    helplineTitle: 'Cyber fraud? Call 1930',
    helplineNote: 'National cybercrime helpline · cybercrime.gov.in',
    footerNote: 'Checks happen on your device. Nothing you check is uploaded. Works offline once loaded.',
    back: 'Back',
    scanPageTitle: 'Scan the QR code',
    scanSteps: [
      'Open your phone’s camera app.',
      'Point it at the QR code on the document, then tap the link that appears.',
      'This page opens and shows whether the document is genuine.',
    ],
    orType: 'Or type the record number printed under the QR code',
    cameraOpen: 'Scan with this phone’s camera',
    cameraHint: 'Point at the QR code on the document',
    cameraStop: 'Stop the camera',
    cameraNo: 'This browser cannot read QR codes here. Use your phone’s camera app instead:',
    cameraDenied: 'The camera could not be opened. Allow camera access, or use your phone’s camera app:',
    cameraNotOurs: 'This QR code is not from Pramaan Verify: {value}',
    changedSince: 'Changed since?',
    no: 'No',
    warn: 'Warn my family and friends',
    warnText: 'Warning: a message going around is a scam. Do not click its links, share OTPs or reply. Check messages at {url} and report fraud on 1930.',
    recordPlaceholder: 'PRM-2026-000001',
    check: 'Check',
    genuine: 'Genuine',
    genuineText: 'This was issued and signed by a real office and has not been changed.',
    replaced: 'Genuine, but replaced',
    replacedText: 'This was genuine, but a newer version was issued: record {next}.',
    withdrawn: 'Withdrawn',
    withdrawnText: 'The issuing office withdrew this on {date}. Do not rely on it or share it.',
    notFound: 'Not found',
    notFoundText: 'We have no signed record {no}. Treat it as unverified.',
    restricted: 'Restricted',
    restrictedText: 'This is a restricted document: only its record number, date and fingerprints are published.',
    reason: 'Reason',
    record: 'Record',
    titleLabel: 'Title',
    issuedBy: 'Issued by',
    signedBy: 'Signed by',
    signedOn: 'Signed on',
    sharing: 'Sharing label',
    files: 'Files and fingerprints',
    file: 'File',
    fileDrop: 'Drop the file here, or tap to choose it',
    fileDropNote: 'Its fingerprint (SHA-256) is worked out on this device and compared with the signed records.',
    fileCheckRecord: 'Check a copy against this record',
    fileGenuine: 'Genuine file',
    fileGenuineText: 'This file is exactly “{name}” from record {no}.',
    fileChanged: 'Changed or different file',
    fileChangedText: 'This file is not one of the signed files of record {no}. It may have been changed.',
    fileUnknown: 'Not found',
    fileUnknownText: 'This file does not match any signed record. Treat it as unverified.',
    fileWithdrawn: 'Withdrawn',
    fileWithdrawnText: 'This file belongs to record {no}, which was withdrawn on {date}.',
    fingerprint: 'Fingerprint',
    share: 'Share this result',
    copied: 'Link copied',
    noData: 'The list of signed records is not available on this page yet.',
    badData: 'Some published records could not be checked (a signature did not match, or the list was incomplete), so they were ignored.',
    builtIn: 'Checked with this page’s built-in code (Web Crypto needs a secure https:// page).',
    role_Reviewer: 'Reviewer',
    messageTitle: 'Paste a message',
    messageNote: 'From WhatsApp, SMS or email',
    messagePageTitle: 'Paste the message',
    messageLabel: 'Message you received',
    weCheck: 'We check for',
    checkList: ['A digital signature from a real office', 'Suspicious or look-alike links', 'Requests for OTPs, passwords or payments', 'Pressure words like “act within 1 hour”'],
    checkMessage: 'Check message',
    msgGenuine: 'Genuine',
    msgGenuineText: 'This message matches signed record {no} exactly.',
    msgReplaced: 'Genuine, but outdated',
    msgReplacedText: 'This matches record {no}, but a newer version was issued: {next}.',
    msgWithdrawn: 'Withdrawn',
    msgWithdrawnText: 'This matches record {no}, which the office withdrew. Do not rely on it or share it.',
    msgChanged: 'Changed',
    msgChangedText: 'This looks like record {no}, but it was changed. Do not trust the changed parts.',
    msgScam: 'Not genuine',
    msgScamText: 'This looks like a scam. Do not click, call or reply.',
    msgUnknown: 'Not found',
    msgUnknownText: 'No signed record matches this message. Treat it as unverified.',
    seeRecord: 'See record {no}',
    changes: 'What was changed',
    legendAdded: 'added or changed',
    legendRemoved: 'missing from the message',
    why: 'Why we think so',
    noSignature: 'No digital signature from any real office.',
    sign_asks_secret: 'Asks for your OTP, password or PIN.',
    sign_asks_payment: 'Asks you to pay or send money.',
    sign_urgent: 'Pressure words or threats:',
    sign_install_app: 'Asks you to install an app or share your screen:',
    sign_unknown_link: 'Suspicious link:',
    sign_unknown_phone: 'Phone number not in any signed record:',
    'note_not a government website': 'is not a government website.',
    'note_made to look official': 'is made to look official, but is not a government website.',
    report: 'Report it: call 1930',
    reportText: 'Report cyber fraud: call 1930 or visit cybercrime.gov.in',
  },
  hi: {
    brandSub: 'प्रमाण · क्या यह असली है?',
    langButton: 'EN',
    langLabel: 'View in English',
    title: 'क्या यह असली है?',
    lead: 'किसी भी सरकारी चेतावनी या सलाह पर भरोसा करने या उसे आगे भेजने से पहले उसकी जाँच करें।',
    scanTitle: 'QR कोड स्कैन करें',
    scanNote: 'छपे या भेजे गए दस्तावेज़ पर',
    fileTitle: 'फ़ाइल अपलोड करें',
    fileNote: 'PDF, चित्र या Word फ़ाइल',
    privacy: 'जाँच आपके फ़ोन पर ही होती है। कुछ भी अपलोड नहीं होता।',
    helplineTitle: 'साइबर धोखाधड़ी? 1930 पर कॉल करें',
    helplineNote: 'राष्ट्रीय साइबर अपराध हेल्पलाइन · cybercrime.gov.in',
    footerNote: 'जाँच आपके उपकरण पर होती है। कुछ भी अपलोड नहीं होता। एक बार खुलने के बाद बिना इंटरनेट के भी चलता है।',
    back: 'वापस',
    scanPageTitle: 'QR कोड स्कैन करें',
    scanSteps: [
      'अपने फ़ोन का कैमरा ऐप खोलें।',
      'दस्तावेज़ पर बने QR कोड की ओर कैमरा करें, फिर दिखने वाले लिंक पर टैप करें।',
      'यह पेज खुलेगा और बताएगा कि दस्तावेज़ असली है या नहीं।',
    ],
    orType: 'या QR कोड के नीचे छपा रिकॉर्ड नंबर लिखें',
    cameraOpen: 'इस फ़ोन के कैमरे से स्कैन करें',
    cameraHint: 'दस्तावेज़ पर बने QR कोड की ओर रखें',
    cameraStop: 'कैमरा बंद करें',
    cameraNo: 'यह ब्राउज़र यहाँ QR कोड नहीं पढ़ सकता। अपने फ़ोन का कैमरा ऐप इस्तेमाल करें:',
    cameraDenied: 'कैमरा नहीं खुल सका। कैमरे की अनुमति दें, या फ़ोन का कैमरा ऐप इस्तेमाल करें:',
    cameraNotOurs: 'यह QR कोड Pramaan Verify का नहीं है: {value}',
    changedSince: 'तब से बदला गया?',
    no: 'नहीं',
    warn: 'परिवार और दोस्तों को सावधान करें',
    warnText: 'सावधान: एक संदेश धोखाधड़ी है। उसके लिंक न खोलें, OTP न दें, जवाब न दें। संदेश {url} पर जाँचें और धोखाधड़ी की शिकायत 1930 पर करें।',
    recordPlaceholder: 'PRM-2026-000001',
    check: 'जाँचें',
    genuine: 'असली',
    genuineText: 'यह एक असली कार्यालय द्वारा जारी और हस्ताक्षरित है, और इसमें कोई बदलाव नहीं हुआ है।',
    replaced: 'असली, पर बदला गया',
    replacedText: 'यह असली था, पर इसका नया संस्करण जारी हुआ है: रिकॉर्ड {next}।',
    withdrawn: 'वापस लिया गया',
    withdrawnText: 'जारी करने वाले कार्यालय ने इसे {date} को वापस ले लिया। इस पर भरोसा न करें और इसे आगे न भेजें।',
    notFound: 'नहीं मिला',
    notFoundText: '{no} नाम का कोई हस्ताक्षरित रिकॉर्ड नहीं है। इसे असत्यापित मानें।',
    restricted: 'प्रतिबंधित',
    restrictedText: 'यह प्रतिबंधित दस्तावेज़ है: केवल रिकॉर्ड नंबर, तिथि और फ़िंगरप्रिंट प्रकाशित हैं।',
    reason: 'कारण',
    record: 'रिकॉर्ड',
    titleLabel: 'शीर्षक',
    issuedBy: 'जारीकर्ता',
    signedBy: 'हस्ताक्षरकर्ता',
    signedOn: 'हस्ताक्षर की तिथि',
    sharing: 'साझा करने का लेबल',
    files: 'फ़ाइलें और फ़िंगरप्रिंट',
    file: 'फ़ाइल',
    fileDrop: 'फ़ाइल यहाँ छोड़ें, या चुनने के लिए टैप करें',
    fileDropNote: 'इसका फ़िंगरप्रिंट (SHA-256) इसी उपकरण पर बनता है और हस्ताक्षरित रिकॉर्ड से मिलाया जाता है।',
    fileCheckRecord: 'इस रिकॉर्ड से एक प्रति मिलाएँ',
    fileGenuine: 'असली फ़ाइल',
    fileGenuineText: 'यह फ़ाइल रिकॉर्ड {no} की “{name}” ही है।',
    fileChanged: 'बदली हुई या अलग फ़ाइल',
    fileChangedText: 'यह फ़ाइल रिकॉर्ड {no} की हस्ताक्षरित फ़ाइलों में नहीं है। इसमें बदलाव हो सकता है।',
    fileUnknown: 'नहीं मिला',
    fileUnknownText: 'यह फ़ाइल किसी हस्ताक्षरित रिकॉर्ड से मेल नहीं खाती। इसे असत्यापित मानें।',
    fileWithdrawn: 'वापस लिया गया',
    fileWithdrawnText: 'यह फ़ाइल रिकॉर्ड {no} की है, जिसे {date} को वापस ले लिया गया।',
    fingerprint: 'फ़िंगरप्रिंट',
    share: 'यह परिणाम साझा करें',
    copied: 'लिंक कॉपी हो गया',
    noData: 'हस्ताक्षरित रिकॉर्ड की सूची अभी इस पेज पर उपलब्ध नहीं है।',
    badData: 'कुछ प्रकाशित रिकॉर्ड की जाँच नहीं हो सकी (हस्ताक्षर मेल नहीं खाया या सूची अधूरी थी), इसलिए उन्हें छोड़ दिया गया।',
    builtIn: 'इस पेज के अपने कोड से जाँचा गया (Web Crypto के लिए सुरक्षित https:// पेज चाहिए)।',
    role_Reviewer: 'समीक्षक',
    messageTitle: 'संदेश चिपकाएँ',
    messageNote: 'WhatsApp, SMS या ईमेल से',
    messagePageTitle: 'संदेश चिपकाएँ',
    messageLabel: 'आपको मिला संदेश',
    weCheck: 'हम जाँचते हैं',
    checkList: ['किसी असली कार्यालय का डिजिटल हस्ताक्षर', 'संदिग्ध या नकली दिखने वाले लिंक', 'OTP, पासवर्ड या भुगतान की माँग', '“1 घंटे में करें” जैसे दबाव वाले शब्द'],
    checkMessage: 'संदेश जाँचें',
    msgGenuine: 'असली',
    msgGenuineText: 'यह संदेश हस्ताक्षरित रिकॉर्ड {no} से पूरी तरह मेल खाता है।',
    msgReplaced: 'असली, पर पुराना',
    msgReplacedText: 'यह रिकॉर्ड {no} से मेल खाता है, पर इसका नया संस्करण जारी हुआ है: {next}।',
    msgWithdrawn: 'वापस लिया गया',
    msgWithdrawnText: 'यह रिकॉर्ड {no} से मेल खाता है, जिसे कार्यालय ने वापस ले लिया है। इस पर भरोसा न करें और इसे आगे न भेजें।',
    msgChanged: 'बदला हुआ',
    msgChangedText: 'यह रिकॉर्ड {no} जैसा दिखता है, पर इसमें बदलाव किया गया है। बदले हुए हिस्सों पर भरोसा न करें।',
    msgScam: 'असली नहीं',
    msgScamText: 'यह धोखाधड़ी लगती है। किसी लिंक पर क्लिक न करें, कॉल या जवाब न दें।',
    msgUnknown: 'नहीं मिला',
    msgUnknownText: 'कोई हस्ताक्षरित रिकॉर्ड इस संदेश से मेल नहीं खाता। इसे असत्यापित मानें।',
    seeRecord: 'रिकॉर्ड {no} देखें',
    changes: 'क्या बदला गया',
    legendAdded: 'जोड़ा या बदला गया',
    legendRemoved: 'संदेश में नहीं है',
    why: 'हम ऐसा क्यों मानते हैं',
    noSignature: 'किसी असली कार्यालय का डिजिटल हस्ताक्षर नहीं है।',
    sign_asks_secret: 'आपका OTP, पासवर्ड या PIN माँगता है।',
    sign_asks_payment: 'भुगतान करने या पैसे भेजने को कहता है।',
    sign_urgent: 'दबाव या धमकी वाले शब्द:',
    sign_install_app: 'ऐप डाउनलोड करने या स्क्रीन साझा करने को कहता है:',
    sign_unknown_link: 'संदिग्ध लिंक:',
    sign_unknown_phone: 'ऐसा फ़ोन नंबर जो किसी हस्ताक्षरित रिकॉर्ड में नहीं है:',
    'note_not a government website': 'सरकारी वेबसाइट नहीं है।',
    'note_made to look official': 'सरकारी जैसा दिखता है, पर सरकारी वेबसाइट नहीं है।',
    report: 'शिकायत करें: 1930 पर कॉल करें',
    reportText: 'साइबर धोखाधड़ी की शिकायत: 1930 पर कॉल करें या cybercrime.gov.in पर जाएँ',
  },
}

let lang = 'en'
try {
  lang = localStorage.getItem('pramaan-verify-lang') === 'hi' ? 'hi' : 'en'
} catch {
  // storage blocked (private mode): English
}
const t = (key, values = {}) => String(WORDS[lang][key] ?? WORDS.en[key] ?? key).replace(/\{(\w+)\}/g, (_, k) => values[k] ?? '')

const escapeHtml = (text) =>
  String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

const ICONS = {
  check: '<path d="m5 12 5 5L20 7"/>',
  cross: '<path d="M6 6l12 12M18 6 6 18"/>',
  question: '<path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7v.5M12 17h.01"/>',
  warning: '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4M12 17h.01"/>',
  scan: '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M7 12h10"/>',
  upload: '<path d="M12 16V4"/><path d="m6 10 6-6 6 6"/><path d="M4 20h16"/>',
  clipboard: '<path d="M9 4h6v3H9z"/><path d="M8 5H6v15h12V5h-2"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  share: '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>',
  lock: '<path d="M6 11h12v10H6z"/><path d="M9 11V8a3 3 0 0 1 6 0v3"/>',
}
const icon = (name, size = 24, width = 2) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`

// ---- data --------------------------------------------------------------------------------------

let book = null // null = no records.json published here
const ready = (async () => {
  try {
    const [records, key] = await Promise.all([fetch('records.json', { cache: 'no-cache' }), fetch('public-key.pem', { cache: 'no-cache' })])
    if (!records.ok || !key.ok) return
    book = await loadBook(await records.json(), await importPublicKey(await key.text()))
  } catch (error) {
    console.error('Could not load the published records', error)
  }
})()

function dataNotes() {
  if (!book) return `<p class="note warn">${icon('warning')}<span>${t('noData')}</span></p>`
  if (book.invalid > 0 || book.problems.length) return `<p class="note warn">${icon('warning')}<span>${t('badData')}</span></p>`
  return ''
}

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : ''
const shortHash = (hash) => `${hash.slice(0, 8)} … ${hash.slice(-8)}`

// ---- pieces ------------------------------------------------------------------------------------

function resultCard(tone, iconName, title, text) {
  return `<section class="result ${tone}" role="status" aria-live="polite">
    <div class="result-icon">${icon(iconName, 56, 3)}</div>
    <h2>${escapeHtml(title)}</h2>
    <p>${escapeHtml(text)}</p>
  </section>`
}

function recordDetails(record, matchedSha = '', unchanged = false) {
  const rows = []
  if (record.restricted) {
    rows.push(`<p class="note info">${icon('lock')}<span><strong>${t('restricted')}.</strong> ${t('restrictedText')}</span></p>`)
  }
  const list = [
    [t('record'), `<span class="mono">${escapeHtml(record.record_no)}</span>`],
    !record.restricted && [t('titleLabel'), escapeHtml(record.title)],
    !record.restricted && [t('issuedBy'), escapeHtml(record.issuing_office)],
    !record.restricted && [t('signedBy'), escapeHtml(t('role_' + record.approved_by?.role))],
    [t('signedOn'), escapeHtml(formatDate(record.issued_at))],
    !record.restricted && record.tlp && [t('sharing'), `TLP:${escapeHtml(record.tlp)}`],
    unchanged && [t('changedSince'), `<strong>${t('no')}</strong>`],
  ].filter(Boolean)
  rows.push(`<dl class="details">${list.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`)
  const files = (record.files || [])
    .map(
      (f, i) => `<li class="${f.sha256 === matchedSha ? 'match' : ''}">
        <strong>${escapeHtml(f.name || `${t('file')} ${i + 1}`)}</strong><br />
        <span class="mono muted">${t('fingerprint')}: ${escapeHtml(f.sha256)}</span>
      </li>`,
    )
    .join('')
  return `<section class="card">${rows.join('')}
    <h3 class="card-title" style="margin-top:16px">${t('files')}</h3><ul class="files">${files}</ul></section>`
}

function dropZone(id, title) {
  return `<label class="drop" id="${id}">
    ${icon('upload', 32)}
    <strong>${escapeHtml(title)}</strong>
    <span class="muted small">${t('fileDropNote')}</span>
    <input type="file" />
  </label>`
}

function wireDropZone(id, onFile) {
  const zone = document.getElementById(id)
  if (!zone) return
  const input = zone.querySelector('input')
  const read = (file) => file && file.arrayBuffer().then((bytes) => onFile(file, bytes))
  input.addEventListener('change', () => read(input.files[0]))
  zone.addEventListener('dragover', (e) => {
    e.preventDefault()
    zone.classList.add('is-over')
  })
  zone.addEventListener('dragleave', () => zone.classList.remove('is-over'))
  zone.addEventListener('drop', (e) => {
    e.preventDefault()
    zone.classList.remove('is-over')
    read(e.dataTransfer.files[0])
  })
}

function fileResult(result) {
  const no = result.record?.record_no ?? ''
  const date = formatDate(result.record?.withdrawn?.withdrawn_at)
  const card = {
    genuine: () => resultCard('genuine', 'check', t('fileGenuine'), t('fileGenuineText', { name: result.file.name || t('file'), no })),
    withdrawn: () => resultCard('bad', 'cross', t('fileWithdrawn'), t('fileWithdrawnText', { no, date })),
    changed: () => resultCard('bad', 'cross', t('fileChanged'), t('fileChangedText', { no })),
    not_found: () => resultCard('unknown', 'question', t('fileUnknown'), t('fileUnknownText')),
  }[result.status]()
  return `${card}<p class="small muted">${t('fingerprint')}: <span class="mono">${escapeHtml(result.sha256)}</span></p>
    ${result.record ? recordDetails(result.record, result.sha256) : ''}`
}

function shareButton() {
  return `<button type="button" class="btn btn-outline" id="share">${icon('share')} ${t('share')}</button>`
}

function wireShare() {
  const button = document.getElementById('share')
  if (!button) return
  button.addEventListener('click', async () => {
    const url = location.href
    try {
      if (navigator.share) await navigator.share({ title: document.title, url })
      else {
        await navigator.clipboard.writeText(url)
        button.textContent = t('copied')
      }
    } catch {
      // cancelled
    }
  })
}

// "Warn my family and friends": a short warning (not the scam message itself) to share or copy
function wireWarn() {
  const button = document.getElementById('warn')
  if (!button) return
  button.addEventListener('click', async () => {
    const text = t('warnText', { url: location.origin + location.pathname })
    try {
      if (navigator.share) await navigator.share({ text })
      else {
        await navigator.clipboard.writeText(text)
        button.textContent = t('copied')
      }
    } catch {
      // cancelled
    }
  })
}

// ---- camera scanning (scan view) ----------------------------------------------------------------

let stream = null
function stopCamera() {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
}

function wireCamera() {
  const open = document.getElementById('camera-open')
  if (!open) return
  const box = document.getElementById('camera')
  const video = document.getElementById('camera-video')
  const note = document.getElementById('camera-note')
  const show = (message) => {
    note.textContent = message
    note.hidden = false
  }
  document.getElementById('camera-stop').addEventListener('click', () => {
    stopCamera()
    box.hidden = true
    open.hidden = false
  })
  open.addEventListener('click', async () => {
    note.hidden = true
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
    } catch {
      show(t('cameraDenied'))
      return
    }
    video.srcObject = stream
    await video.play()
    box.hidden = false
    open.hidden = true
    const detector = new window.BarcodeDetector({ formats: ['qr_code'] })
    const look = async () => {
      if (!stream) return
      try {
        const [code] = await detector.detect(video)
        if (code) {
          let recordNo = ''
          try {
            recordNo = new URL(code.rawValue, location.href).searchParams.get('r') || ''
          } catch {
            recordNo = ''
          }
          if (recordNo) {
            stopCamera()
            history.pushState(null, '', `?r=${encodeURIComponent(cleanRecordNo(recordNo))}`)
            render()
            return
          }
          show(t('cameraNotOurs', { value: code.rawValue.slice(0, 80) }))
        }
      } catch {
        // a frame that could not be read: try the next one
      }
      setTimeout(look, 300)
    }
    look()
  })
}

// ---- views -------------------------------------------------------------------------------------

const VIEWS = {
  home() {
    return `<section class="hero"><h1>${t('title')}</h1><p>${t('lead')}</p></section>
      <a class="choice" href="#scan"><span class="choice-icon tone-saffron">${icon('scan', 28)}</span>
        <span><strong>${t('scanTitle')}</strong><span class="muted">${t('scanNote')}</span></span><span class="chev">${icon('chevron')}</span></a>
      <a class="choice" href="#file"><span class="choice-icon tone-navy">${icon('upload', 28)}</span>
        <span><strong>${t('fileTitle')}</strong><span class="muted">${t('fileNote')}</span></span><span class="chev">${icon('chevron')}</span></a>
      <a class="choice" href="#message"><span class="choice-icon tone-green">${icon('clipboard', 28)}</span>
        <span><strong>${t('messageTitle')}</strong><span class="muted">${t('messageNote')}</span></span><span class="chev">${icon('chevron')}</span></a>
      <p class="note good">${icon('lock')}<span>${t('privacy')}</span></p>`
  },

  scan() {
    const steps = WORDS[lang].scanSteps.map((s) => `<li>${escapeHtml(s)}</li>`).join('')
    // Live scanning where the browser can read QR codes (BarcodeDetector, e.g. Chrome on Android) and a
    // camera is allowed (https:// or localhost). Elsewhere: the phone's camera app, as before.
    const canScan = 'BarcodeDetector' in window && navigator.mediaDevices?.getUserMedia && window.isSecureContext
    return `<h1 class="page-title">${t('scanPageTitle')}</h1>
      ${canScan ? `<button type="button" class="btn btn-saffron" id="camera-open">${icon('scan')} ${t('cameraOpen')}</button>
      <div class="camera" id="camera" hidden>
        <video id="camera-video" playsinline muted aria-label="${t('cameraHint')}"></video>
        <span class="camera-frame" aria-hidden="true"></span>
        <span class="camera-hint">${t('cameraHint')}</span>
        <button type="button" class="btn btn-outline camera-stop" id="camera-stop">${t('cameraStop')}</button>
      </div>
      <p class="note warn" id="camera-note" hidden></p>` : `<p class="small muted">${t('cameraNo')}</p>`}
      <section class="card"><ol class="steps">${steps}</ol></section>
      <form class="field" id="record-form">
        <label for="record-no">${t('orType')}</label>
        <input class="input mono" id="record-no" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="${t('recordPlaceholder')}" required />
        <button class="btn btn-navy" type="submit">${t('check')}</button>
      </form>`
  },

  file() {
    return `<h1 class="page-title">${t('fileTitle')}</h1>${dataNotes()}${dropZone('file-drop', t('fileDrop'))}<div id="file-result"></div>`
  },

  message() {
    const checks = WORDS[lang].checkList.map((c) => `<li><span class="mark good">${icon('check', 16, 3)}</span><span>${escapeHtml(c)}</span></li>`).join('')
    return `<h1 class="page-title">${t('messagePageTitle')}</h1>${dataNotes()}
      <form class="field" id="message-form">
        <label for="message-text">${t('messageLabel')}</label>
        <textarea class="input" id="message-text" required></textarea>
        <section class="card"><h2 class="card-title">${t('weCheck')}</h2><ul class="list-x">${checks}</ul></section>
        <button class="btn btn-navy" type="submit">${icon('check')} ${t('checkMessage')}</button>
      </form>
      <div id="message-result" tabindex="-1"></div>`
  },

  record(recordNo) {
    if (!book) return dataNotes()
    const { status, record } = lookup(book, recordNo)
    const no = cleanRecordNo(recordNo)
    const card = {
      genuine: () => resultCard('genuine', 'check', t('genuine'), t('genuineText')),
      replaced: () => resultCard('warn', 'warning', t('replaced'), t('replacedText', { next: record.replaced_by })),
      withdrawn: () => resultCard('bad', 'cross', t('withdrawn'), t('withdrawnText', { date: formatDate(record.withdrawn.withdrawn_at) })),
      not_found: () => resultCard('unknown', 'question', t('notFound'), t('notFoundText', { no })),
    }[status]()
    const reason = status === 'withdrawn' ? `<p class="note bad"><span><strong>${t('reason')}:</strong> ${escapeHtml(record.withdrawn.reason)}</span></p>` : ''
    const replacedLink =
      status === 'replaced' ? `<a class="btn btn-navy" href="?r=${encodeURIComponent(record.replaced_by)}">${t('record')} ${escapeHtml(record.replaced_by)}</a>` : ''
    return `${dataNotes()}${card}${reason}${replacedLink}
      ${record ? recordDetails(record, '', status === 'genuine') : ''}
      ${record ? dropZone('record-drop', t('fileCheckRecord')) + '<div id="file-result"></div>' : ''}
      ${!usingWebCrypto() ? `<p class="small muted">${t('builtIn')}</p>` : ''}
      ${shareButton()}`
  },
}

function messageResult(result) {
  const no = result.record_no
  const cards = {
    genuine: ['genuine', 'check', t('msgGenuine'), t('msgGenuineText', { no })],
    replaced: ['warn', 'warning', t('msgReplaced'), t('msgReplacedText', { no, next: result.replaced_by })],
    withdrawn: ['bad', 'cross', t('msgWithdrawn'), t('msgWithdrawnText', { no })],
    changed: ['warn', 'warning', t('msgChanged'), t('msgChangedText', { no })],
    scam: ['bad', 'cross', t('msgScam'), t('msgScamText')],
    not_found: ['unknown', 'question', t('msgUnknown'), t('msgUnknownText')],
  }
  const parts = [resultCard(...cards[result.verdict])]
  if (no) parts.push(`<a class="btn btn-outline" href="?r=${encodeURIComponent(no)}">${t('seeRecord', { no: escapeHtml(no) })}</a>`)
  if (result.diff) {
    const words = result.diff.map((d) => (d.kind === 'same' ? escapeHtml(d.text) : `<span class="${d.kind}">${escapeHtml(d.text)}</span>`)).join(' ')
    parts.push(`<section class="card"><h2 class="card-title">${t('changes')}</h2><p class="diff">${words}</p>
      <p class="small muted"><span class="diff"><span class="added">${t('legendAdded')}</span></span> ·
      <span class="diff"><span class="removed">${t('legendRemoved')}</span></span></p></section>`)
  }
  const reasons = []
  if (result.verdict === 'scam' || result.verdict === 'not_found') reasons.push(['bad', t('noSignature'), ''])
  for (const sign of result.signs) {
    const detail = sign.kind === 'unknown_link' ? `${escapeHtml(sign.detail)} ${t('note_' + sign.note)}` : sign.kind.startsWith('asks') ? '' : `“${escapeHtml(sign.detail)}”`
    reasons.push(['bad', t('sign_' + sign.kind), detail])
  }
  if (reasons.length && result.verdict !== 'genuine') {
    const items = reasons.map(([tone, label, detail]) => `<li><span class="mark ${tone}">${icon('cross', 16, 3)}</span><span><strong>${label}</strong> ${detail}</span></li>`).join('')
    parts.push(`<section class="card"><h2 class="card-title">${t('why')}</h2><ul class="list-x">${items}</ul></section>`)
  }
  parts.push(`<a class="btn btn-red" href="tel:1930">${t('report')}</a><p class="small muted" style="margin:0;text-align:center">${t('reportText')}</p>`)
  if (result.verdict === 'scam' || result.verdict === 'changed' || result.verdict === 'withdrawn') {
    parts.push(`<button type="button" class="btn btn-outline" id="warn">${icon('share')} ${t('warn')}</button>`)
  }
  return parts.join('')
}

// ---- routing -----------------------------------------------------------------------------------

function currentView() {
  const recordNo = new URLSearchParams(location.search).get('r')
  const hash = location.hash.replace('#', '')
  if (hash && VIEWS[hash] && hash !== 'record') return { name: hash }
  if (recordNo) return { name: 'record', recordNo }
  return { name: 'home' }
}

async function render() {
  await ready
  const view = currentView()
  const main = document.getElementById('main')
  document.documentElement.lang = lang
  document.querySelectorAll('[data-t]').forEach((el) => (el.textContent = t(el.dataset.t)))
  document.getElementById('lang-label').textContent = t('langButton')
  document.getElementById('lang').setAttribute('aria-label', t('langLabel'))
  document.getElementById('back').hidden = view.name === 'home'
  document.getElementById('back').setAttribute('aria-label', t('back'))
  stopCamera() // leaving the scan view switches the camera off
  main.innerHTML = VIEWS[view.name](view.recordNo)

  wireShare()
  wireCamera()
  const form = document.getElementById('record-form')
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault()
      const no = cleanRecordNo(document.getElementById('record-no').value)
      history.pushState(null, '', `?r=${encodeURIComponent(no)}`)
      render()
    })
  }
  const showFile = async (file, bytes) => {
    if (!book) return
    const result = await checkFile(book, new Uint8Array(bytes), view.name === 'record' ? view.recordNo : '')
    document.getElementById('file-result').innerHTML = fileResult(result)
  }
  wireDropZone('file-drop', showFile)
  wireDropZone('record-drop', showFile)
  const messageForm = document.getElementById('message-form')
  if (messageForm) {
    messageForm.addEventListener('submit', async (e) => {
      e.preventDefault()
      const result = await checkMessage(document.getElementById('message-text').value, book ? publishedRecords(book) : [])
      const box = document.getElementById('message-result')
      box.innerHTML = messageResult(result)
      wireWarn()
      box.focus()
      box.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }
}

document.getElementById('lang').addEventListener('click', () => {
  lang = lang === 'en' ? 'hi' : 'en'
  try {
    localStorage.setItem('pramaan-verify-lang', lang)
  } catch {
    // storage blocked: the choice lasts until the page is closed
  }
  render()
})
document.getElementById('back').addEventListener('click', () => {
  if (location.hash) history.back()
  else {
    history.pushState(null, '', location.pathname)
    render()
  }
})
window.addEventListener('hashchange', render)
window.addEventListener('popstate', render)

// Offline: keep a copy of the page (only where browsers allow it: https:// or localhost)
if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('sw.js').catch(() => {})
}

render()
