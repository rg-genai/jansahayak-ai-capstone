import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'jansahayak-theme'
const listeners = new Set<() => void>()

function readInitialTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // Storage can be unavailable (e.g. blocked cookies); fall back to the OS preference.
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  document.documentElement.style.colorScheme = theme
}

let currentTheme: Theme = readInitialTheme()
applyTheme(currentTheme)

function setTheme(theme: Theme) {
  currentTheme = theme
  try {
    window.localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Persisting is best-effort; the in-memory theme still applies.
  }
  applyTheme(theme)
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, () => currentTheme, (): Theme => 'light')
  const toggleTheme = () => setTheme(currentTheme === 'dark' ? 'light' : 'dark')
  return { theme, toggleTheme }
}
