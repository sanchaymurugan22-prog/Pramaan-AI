// Small choices kept in THIS browser before anyone signs in (Stage 9B): whether the splash screen was
// seen, and the language picked on the language screen. Nothing secret. Browser storage can be missing
// (private windows), so every read and write is allowed to fail quietly.

const WELCOMED = 'pramaan.welcomed'
const LANGUAGE = 'pramaan.language'

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // not saved: the screen is simply shown again next time
  }
}

export const welcomed = () => read(WELCOMED) === 'yes'
export const markWelcomed = () => write(WELCOMED, 'yes')
export const storedLanguage = () => read(LANGUAGE)
export const storeLanguage = (code: string) => write(LANGUAGE, code)
