import { GitBranch } from "lucide-react"

export function RunTraceLogo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
        <GitBranch aria-hidden="true" className="size-4" />
      </span>
      {compact ? null : <span>RunTrace</span>}
    </div>
  )
}
