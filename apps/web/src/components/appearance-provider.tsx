"use client"

import { createContext, useContext, useEffect, useMemo, useState } from "react"
import { ThemeProvider } from "next-themes"

const STORAGE_KEY = "runtrace:appearance:v1"
const DEFAULT_ACCENT = "#4f46e5"

type AppearancePreferences = {
  accent: string
  compactRows: boolean
}

type AppearanceContextValue = AppearancePreferences & {
  setAccent: (value: string) => void
  setCompactRows: (value: boolean) => void
  resetAppearance: () => void
}

const AppearanceContext = createContext<AppearanceContextValue | null>(null)

function readPreferences(): AppearancePreferences {
  if (typeof window === "undefined") {
    return { accent: DEFAULT_ACCENT, compactRows: false }
  }

  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}") as Partial<AppearancePreferences>
    return {
      accent: /^#[0-9a-f]{6}$/i.test(saved.accent ?? "") ? saved.accent! : DEFAULT_ACCENT,
      compactRows: saved.compactRows === true,
    }
  } catch {
    return { accent: DEFAULT_ACCENT, compactRows: false }
  }
}

function foregroundFor(background: string) {
  const red = Number.parseInt(background.slice(1, 3), 16) / 255
  const green = Number.parseInt(background.slice(3, 5), 16) / 255
  const blue = Number.parseInt(background.slice(5, 7), 16) / 255
  const linear = [red, green, blue].map((channel) => channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
  const luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
  return luminance > 0.45 ? "#171717" : "#ffffff"
}

function faviconFor(accent: string) {
  const foreground = foregroundFor(accent)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="${accent}"/><g fill="none" stroke="${foreground}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5"><path d="M19.75 9.25a11.25 11.25 0 0 0-11.25 11.25V5.5"/><circle cx="23.5" cy="9.25" r="3.75"/><circle cx="8.5" cy="24.25" r="3.75"/></g></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

function AppearanceState({ children }: { children: React.ReactNode }) {
  const [preferences, setPreferences] = useState<AppearancePreferences>(readPreferences)

  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty("--primary", preferences.accent)
    root.style.setProperty("--primary-foreground", foregroundFor(preferences.accent))
    root.style.setProperty("--ring", preferences.accent)
    root.style.setProperty("--sidebar-primary", preferences.accent)
    root.dataset.density = preferences.compactRows ? "compact" : "comfortable"

    let favicon = document.querySelector<HTMLLinkElement>('link[data-runtrace-icon]')
    if (!favicon) {
      favicon = document.createElement("link")
      favicon.rel = "icon"
      favicon.type = "image/svg+xml"
      favicon.dataset.runtraceIcon = ""
      document.head.appendChild(favicon)
    }
    favicon.href = faviconFor(preferences.accent)

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
  }, [preferences])

  const value = useMemo<AppearanceContextValue>(() => ({
    ...preferences,
    setAccent: (accent) => setPreferences((current) => ({ ...current, accent })),
    setCompactRows: (compactRows) => setPreferences((current) => ({ ...current, compactRows })),
    resetAppearance: () => setPreferences({ accent: DEFAULT_ACCENT, compactRows: false }),
  }), [preferences])

  return <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>
}

export function AppearanceProvider({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <AppearanceState>{children}</AppearanceState>
    </ThemeProvider>
  )
}

export function useAppearance() {
  const value = useContext(AppearanceContext)
  if (!value) throw new Error("useAppearance must be used within AppearanceProvider")
  return value
}
