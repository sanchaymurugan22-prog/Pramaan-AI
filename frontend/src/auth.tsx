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

// "Priya Sharma" -> "PS"
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name
}
