"use client"

import { Laptop, Moon, RotateCcw, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { toast } from "sonner"

import { useAppearance } from "@/components/appearance-provider"
import { useAuth } from "@/components/auth-provider"
import { useI18n } from "@/components/i18n-provider"
import { Button } from "@/components/ui/button"
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { AppearanceTheme } from "@/lib/auth"

const THEME_OPTIONS = [
  { value: "light", label: "Light" as const, icon: Sun },
  { value: "dark", label: "Dark" as const, icon: Moon },
  { value: "system", label: "Auto" as const, icon: Laptop },
]

export function AppearanceSettings() {
  const { theme, setTheme } = useTheme()
  const { identity, updatePreferences } = useAuth()
  const { t } = useI18n()
  const { accent, compactRows, setAccent, setCompactRows, resetAppearance } = useAppearance()
  const reportError = (error: unknown) => toast.error(error instanceof Error ? error.message : t("Action failed"))

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      <div>
        <h2 className="text-xl font-semibold">{t("Appearance")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("Your appearance preferences follow your account across devices. Project data is not affected.")}</p>
      </div>
      <FieldGroup className="mt-6">
        <Field>
          <ToggleGroup
            aria-label={t("Appearance")}
            variant="outline"
            value={[theme ?? "system"]}
            onValueChange={(values) => {
              const next = values[0] as AppearanceTheme | undefined
              if (!next || next === theme) return
              const previous = (theme ?? "system") as AppearanceTheme
              setTheme(next)
              void updatePreferences({ theme: next }).catch((error) => { setTheme(previous); reportError(error) })
            }}
            className="w-full"
            spacing={2}
          >
            {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
              <ToggleGroupItem key={value} value={value} className="flex-1">
                <Icon data-icon="inline-start" />
                {t(label)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </Field>
        <Field orientation="horizontal">
          <FieldContent>
            <FieldLabel htmlFor="accent-color">{t("Accent color")}</FieldLabel>
            <FieldDescription>{t("Used for primary actions, focus rings, and progress.")}</FieldDescription>
          </FieldContent>
          <div className="flex items-center gap-2">
            <Input
              id="accent-color"
              type="color"
              value={accent}
              onChange={(event) => setAccent(event.target.value)}
              onBlur={() => {
                if (accent === identity.accent_color) return
                const previous = identity.accent_color
                void updatePreferences({ accent_color: accent }).catch((error) => { setAccent(previous); reportError(error) })
              }}
              className="size-10 p-1"
              aria-label={t("Accent color")}
            />
            <code className="min-w-18 text-xs text-muted-foreground">{accent.toUpperCase()}</code>
          </div>
        </Field>
        <Field orientation="horizontal">
          <FieldContent>
            <FieldLabel htmlFor="compact-rows">{t("Compact rows")}</FieldLabel>
            <FieldDescription>{t("Fit more projects and experiment records on screen.")}</FieldDescription>
          </FieldContent>
          <Switch id="compact-rows" checked={compactRows} onCheckedChange={(next) => {
            const previous = compactRows
            setCompactRows(next)
            void updatePreferences({ compact_rows: next }).catch((error) => { setCompactRows(previous); reportError(error) })
          }} />
        </Field>
      </FieldGroup>
      <div className="mt-6 flex justify-end">
        <Button type="button" variant="outline" onClick={() => {
          const previous = { theme: (theme ?? "system") as AppearanceTheme, accent, compactRows }
          resetAppearance()
          setTheme("system")
          void updatePreferences({ theme: "system", accent_color: "#4f46e5", compact_rows: false }).catch((error) => {
            setTheme(previous.theme)
            setAccent(previous.accent)
            setCompactRows(previous.compactRows)
            reportError(error)
          })
        }}>
          <RotateCcw data-icon="inline-start" />
          {t("Reset defaults")}
        </Button>
      </div>
    </div>
  )
}
