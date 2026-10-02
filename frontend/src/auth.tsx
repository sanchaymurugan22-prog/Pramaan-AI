// Who is signed in, shared with every page. App.tsx fills it in from /api/auth/status.
// This is only for showing the right screens and buttons: the backend checks the role on
// every request, so hiding a button here protects nothing by itself.
import { createContext, useContext } from 'react'
import type { Role, User } from './api'

type Auth = {
  user: User
  setUser: (user: User) => void
  signOut: () => Promise<void>
}

export const AuthContext = createContext<Auth | null>(null)

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth() used outside the signed-in app')
  return auth
}

// Role colours from the design: Operator saffron, Reviewer green, Admin navy
export const ROLE_TONE: Record<Role, 'saffron' | 'green' | 'navy'> = {
  operator: 'saffron',
  reviewer: 'green',
  admin: 'navy',
}

// "Priya Sharma" -> "PS". A part in brackets and anything that does not start with a letter are left out
// (v1.2: "Test Operator (Claude)" gave "T(", now "TO").
export function initials(name: string): string {
  const parts = name.replace(/\([^)]*\)?/g, ' ').split(/\s+/).filter((w) => /^\p{L}/u.test(w))
  const first = (word: string | undefined) => (word ? Array.from(word)[0] : '')
  return (first(parts[0]) + (parts.length > 1 ? first(parts[parts.length - 1]) : '')).toUpperCase()
}

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name
}
