// Stage 8: the 23 languages and what this computer can do in each (GET /api/languages), loaded once.
import { useEffect, useState } from 'react'
import { getLanguages, type LanguageInfo, type LanguagesInfo } from './api'

let cached: Promise<LanguagesInfo> | null = null

export function loadLanguages(): Promise<LanguagesInfo> {
  cached ??= getLanguages().catch((e) => {
    cached = null // try again next time
    throw e
  })
  return cached
}

export function useLanguages(): LanguagesInfo | null {
  const [info, setInfo] = useState<LanguagesInfo | null>(null)
  useEffect(() => {
    let current = true
    loadLanguages()
      .then((loaded) => current && setInfo(loaded))
      .catch(() => {})
    return () => {
      current = false
    }
  }, [])
  return info
}

export function languageByCode(info: LanguagesInfo | null, code: string): LanguageInfo | undefined {
  return info?.languages.find((l) => l.code === code)
}

// "हिन्दी" for Indian languages, "English" for English
export function nativeName(info: LanguagesInfo | null, code: string): string {
  return languageByCode(info, code)?.native ?? code
}
