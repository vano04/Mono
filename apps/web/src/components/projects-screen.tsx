"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { ArrowRight, BookOpen, FolderKanban, Search } from "lucide-react"
import { toast } from "sonner"

import { CreateProjectDialog } from "@/components/create-project-dialog"
import { RunTraceLogo } from "@/components/runtrace-logo"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { runtrace } from "@/lib/api"
import type { Project } from "@/lib/types"

export function ProjectsScreen() {
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [query, setQuery] = useState("")

  useEffect(() => {
    runtrace.projects().then(setProjects).catch((error) => {
      toast.error(error instanceof Error ? error.message : "Could not load projects")
      setProjects([])
    })
  }, [])

  const filtered = useMemo(() => (projects ?? []).filter((project) =>
    `${project.name} ${project.slug} ${project.description}`.toLowerCase().includes(query.toLowerCase())), [projects, query])

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 sm:px-8">
      <header className="flex h-20 items-center justify-between border-b">
        <RunTraceLogo />
        <Button variant="ghost" render={<Link href="/docs" />}><BookOpen data-icon="inline-start" />Docs</Button>
      </header>
      <section className="py-12 sm:py-16">
        <div className="mb-9 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Projects</h1>
            <p className="max-w-xl text-muted-foreground">Shared experiment registries for people and autonomous research agents.</p>
          </div>
          <CreateProjectDialog onCreated={(project) => setProjects((current) => [...(current ?? []), project])} />
        </div>

        {projects === null ? (
          <div className="flex flex-col gap-3"><Skeleton className="h-12 w-full" /><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></div>
        ) : projects.length === 0 ? (
          <Empty className="min-h-80 border">
            <EmptyHeader>
              <EmptyMedia variant="icon"><FolderKanban /></EmptyMedia>
              <EmptyTitle>No projects yet</EmptyTitle>
              <EmptyDescription>Create your first registry, then connect an agent through the SDK, CLI, HTTP API, or MCP.</EmptyDescription>
            </EmptyHeader>
            <EmptyContent><CreateProjectDialog onCreated={(project) => setProjects([project])} /></EmptyContent>
          </Empty>
        ) : (
          <div className="flex flex-col gap-5">
            <label className="relative block">
              <Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-11 pl-10" placeholder="Search projects" aria-label="Search projects" />
            </label>
            <div className="divide-y border-y">
              {filtered.map((project) => (
                <Link href={`/projects/${project.slug}`} key={project.id} className="group grid min-h-24 grid-cols-[auto_1fr_auto] items-center gap-4 px-2 transition-colors hover:bg-muted/50 sm:grid-cols-[auto_1fr_80px_80px_auto]">
                  <span className="grid size-10 place-items-center rounded-lg bg-primary/8 text-primary"><FolderKanban className="size-5" /></span>
                  <span className="min-w-0"><strong className="block truncate text-sm font-medium">{project.name}</strong><small className="mt-1 block truncate text-muted-foreground">{project.description || "No project goal yet"}</small></span>
                  <span className="hidden text-center sm:block"><strong className="block font-mono text-sm">{project.active_runs ?? 0}</strong><small className="text-muted-foreground">active</small></span>
                  <span className="hidden text-center sm:block"><strong className="block font-mono text-sm">{project.experiment_count ?? 0}</strong><small className="text-muted-foreground">records</small></span>
                  <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                </Link>
              ))}
              {filtered.length === 0 ? <p className="py-12 text-center text-sm text-muted-foreground">No projects match “{query}”.</p> : null}
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
