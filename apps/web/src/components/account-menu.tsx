"use client"

import Link from "next/link"
import { LogOut, Settings, ShieldCheck } from "lucide-react"
import { toast } from "sonner"

import { useAuth } from "@/components/auth-provider"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useI18n } from "@/components/i18n-provider"

export function AccountMenu() {
  const { identity, signOut, status } = useAuth()
  const { t } = useI18n()
  const initials = identity.username.slice(0, 2).toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="ghost" className="gap-2 px-2" />}>
        <span className="grid size-7 place-items-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">{initials}</span>
        <span className="hidden max-w-36 truncate sm:inline">{identity.username}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel><span className="block truncate text-foreground">{identity.username}</span><span className="block font-normal capitalize">{status.dev ? t("Dev · no auth") : identity.role}</span></DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem render={<Link href="/access" />}><ShieldCheck />{identity.role === "member" ? t("Agent tokens") : t("Access")}</DropdownMenuItem>
        <DropdownMenuItem render={<Link href="/account" />}><Settings />{t("Settings")}</DropdownMenuItem>
        {!status.dev ? <><DropdownMenuSeparator /><DropdownMenuItem variant="destructive" onClick={() => signOut().catch(() => toast.error(t("Could not sign out")))}><LogOut />{t("Sign out")}</DropdownMenuItem></> : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
