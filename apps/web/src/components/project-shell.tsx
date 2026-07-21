"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Archive, ArrowLeft, BookOpen, LayoutDashboard, Menu, Search, Settings } from "lucide-react"

import { MonoLogo } from "@/components/mono-logo"
import { AccountMenu } from "@/components/account-menu"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import type { Project } from "@/lib/types"
import { projectCapabilities, type ProjectAccessRole } from "@/lib/project-access"
import { useI18n } from "@/components/i18n-provider"

const navItems = [
  { label: "Dashboard" as const, suffix: "", icon: LayoutDashboard },
  { label: "Search" as const, suffix: "/search", icon: Search },
  { label: "Archive" as const, suffix: "/archive", icon: Archive },
  { label: "Settings" as const, suffix: "/settings", icon: Settings },
]

function ProjectNavigation({ project, accessRole, mobile = false }: { project: Project; accessRole: ProjectAccessRole; mobile?: boolean }) {
  const pathname = usePathname()
  const { t } = useI18n()
  const base = `/projects/${project.slug}`
  const { canEdit } = projectCapabilities(accessRole)
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-20 items-center border-b px-5"><MonoLogo /></div>
      <div className="border-b px-3 py-4">
        <Button variant="ghost" className="w-full justify-start" render={<Link href="/" />} nativeButton={false}><ArrowLeft data-icon="inline-start" /><span className="truncate">{project.name}</span></Button>
      </div>
      <nav className="flex flex-col gap-1 p-3" aria-label={t("Project navigation")}>
        {navItems.map(({ label, suffix, icon: Icon }) => {
          if (label === "Settings" && !canEdit) return null
          const href = `${base}${suffix}`
          const active = suffix ? pathname === href : pathname === base
          return (
            <Button key={label} variant={active ? "secondary" : "ghost"} className={cn("justify-start", active && "font-medium")} render={<Link href={href} />} nativeButton={false}>
              <Icon data-icon="inline-start" />{t(label)}
            </Button>
          )
        })}
      </nav>
      <div className="mt-auto border-t p-3">
        <Button variant="ghost" className="w-full justify-start" render={<Link href="/docs" />} nativeButton={false}><BookOpen data-icon="inline-start" />{t("Docs")}</Button>
        <div className="mt-1"><AccountMenu /></div>
        {mobile ? <p className="px-3 pt-2 text-xs text-muted-foreground">Mono v0.1</p> : null}
      </div>
    </div>
  )
}

export function ProjectShell({ project, accessRole, children }: { project: Project; accessRole: ProjectAccessRole; children: React.ReactNode }) {
  const { t } = useI18n()
  return (
    <div className="min-h-screen bg-background xl:grid xl:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="fixed inset-y-0 left-0 hidden w-[248px] border-r bg-sidebar xl:block"><ProjectNavigation project={project} accessRole={accessRole} /></aside>
      <div className="min-w-0 xl:col-start-2">
        <div className="flex h-16 items-center border-b px-4 xl:hidden">
          <Sheet>
            <SheetTrigger render={<Button variant="ghost" size="icon" aria-label={t("Open navigation")} />}><Menu /></SheetTrigger>
            <SheetContent side="left" className="w-[280px] p-0">
              <SheetHeader className="sr-only"><SheetTitle>{t("Project navigation")}</SheetTitle><SheetDescription>{t("Navigate Mono project views.")}</SheetDescription></SheetHeader>
              <ProjectNavigation project={project} accessRole={accessRole} mobile />
            </SheetContent>
          </Sheet>
          <div className="ml-2 truncate text-sm font-medium">{project.name}</div>
        </div>
        <main className="mx-auto w-full min-w-0 max-w-[1240px] px-4 py-7 sm:px-8 sm:py-10 xl:px-12">{children}</main>
      </div>
    </div>
  )
}
