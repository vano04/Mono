"use client"

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Activity, Archive, Copy, Database, FileText, FlaskConical, Search, ShieldCheck } from "lucide-react"
import { toast } from "sonner"

import { CreateExperimentDialog } from "@/components/create-experiment-dialog"
import { ProgressChart } from "@/components/progress-chart"
import { ProjectShell } from "@/components/project-shell"
import { RecordActions } from "@/components/record-actions"
import { RunDetailSheet } from "@/components/run-detail-sheet"
import { StatusBadge } from "@/components/status-badge"
import { TagFilter } from "@/components/tag-filter"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { runtrace } from "@/lib/api"
import type { Dashboard, ProgressData, Run, SearchResult } from "@/lib/types"

export type ProjectView = "dashboard" | "search" | "archive" | "settings"

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value)) : "—"
}

function latestMetric(run: Run, preferred: string) {
  const metrics = run.metrics ?? {}
  const entry = metrics[preferred] ?? Object.values(metrics)[0]
  return entry ? String(entry.latest) : "—"
}

function PageHeading({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-start"><div><h1 className="text-3xl font-semibold tracking-tight">{title}</h1>{description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p> : null}</div>{actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}</div>
}

function DashboardView({ data, progress, slug, reload, setProgress, openRun, onProgressQueryChange }: {
  data: Dashboard; progress: ProgressData; slug: string; reload: () => void; setProgress: (value: ProgressData) => void; openRun: (id: string) => void; onProgressQueryChange: (value: { metric: string; window: string; includeTags: string[]; excludeTags: string[] }) => void
}) {
  const [metric, setMetric] = useState(progress.metric)
  const [window, setWindow] = useState(progress.window)
  const [includeTags, setIncludeTags] = useState<string[]>([])
  const [excludeTags, setExcludeTags] = useState<string[]>([])
  const queue = useMemo(() => [...data.active_runs, ...data.experiments.filter((item) => ["proposed", "pending", "running"].includes(item.lifecycle))], [data])

  async function changeProgress(nextMetric: string, nextWindow: string, nextInclude = includeTags, nextExclude = excludeTags) {
    setMetric(nextMetric); setWindow(nextWindow)
    onProgressQueryChange({ metric: nextMetric, window: nextWindow, includeTags: nextInclude, excludeTags: nextExclude })
    try { setProgress(await runtrace.progress(slug, nextMetric, nextWindow, nextInclude, nextExclude)) }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not load progress") }
  }

  return <>
    <PageHeading title="Dashboard" description={data.project.description || "Add a durable research goal in Settings so every agent starts from the same objective."} actions={<CreateExperimentDialog slug={slug} onCreated={reload} />} />
    <Card className="mb-6 overflow-hidden py-0">
      <CardHeader className="flex flex-col gap-4 border-b py-5 sm:flex-row sm:items-start sm:justify-between">
        <div><CardTitle>Autoresearch progress</CardTitle><CardDescription>Strict best-so-far improvement over the first completed run in this window.</CardDescription></div>
        <div className="flex flex-wrap gap-2">
          <Select value={metric} onValueChange={(value) => value && changeProgress(String(value), window)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{Array.from(new Set([data.project.progress_metric_key, ...data.available_metrics])).map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectGroup></SelectContent></Select>
          <Select value={window} onValueChange={(value) => value && changeProgress(metric, String(value))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="7d">7 days</SelectItem><SelectItem value="30d">30 days</SelectItem><SelectItem value="all">All time</SelectItem></SelectGroup></SelectContent></Select>
          <TagFilter tags={data.available_tags} include={includeTags} exclude={excludeTags} onChange={(nextInclude, nextExclude) => { setIncludeTags(nextInclude); setExcludeTags(nextExclude); changeProgress(metric, window, nextInclude, nextExclude) }} />
        </div>
      </CardHeader>
      <CardContent className="p-4 sm:p-6"><ProgressChart data={progress} /></CardContent>
    </Card>

    <Card className="mb-8 py-0">
      <CardContent className="grid p-0 sm:grid-cols-[1.4fr_.65fr_.65fr_auto]">
        <div className="border-b p-5 sm:border-b-0 sm:border-r"><span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Current main baseline</span>{data.baseline ? <button className="mt-2 block text-left" onClick={() => openRun(data.baseline!.id)}><strong className="text-base">{data.baseline.display_id} · {data.baseline.name}</strong><span className="mt-1 block text-xs text-muted-foreground">Established {formatDate(data.baseline.finished_at)}</span></button> : <p className="mt-2 text-sm text-muted-foreground">No completed baseline yet.</p>}</div>
        <div className="border-r p-5"><span className="text-xs text-muted-foreground">Primary metric</span><strong className="mt-2 block font-mono text-lg">{data.baseline ? latestMetric(data.baseline, data.project.progress_metric_key) : "—"}</strong></div>
        <div className="p-5"><span className="text-xs text-muted-foreground">Connected workers</span><strong className="mt-2 block font-mono text-lg">{data.worker_count}</strong></div>
        <div className="flex items-center border-t px-5 py-4 sm:border-l sm:border-t-0"><Badge variant="secondary"><Database />Shared registry</Badge></div>
      </CardContent>
    </Card>

    <section className="mb-10">
      <div className="mb-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-lg font-semibold">Shared experiment queue</h2><p className="mt-1 text-sm text-muted-foreground">Workers claim proposals independently from this registry.</p></div><div className="flex flex-wrap gap-4 text-xs text-muted-foreground">{["proposed", "pending", "running", "kept", "discarded", "crashed"].map((value) => <span key={value} className="flex items-center gap-1.5"><span className={`status-dot status-${value}`} />{value} {data.counts[value] ?? 0}</span>)}</div></div>
      {queue.length ? <div className="overflow-hidden rounded-lg border"><Table><TableHeader><TableRow><TableHead className="w-28">ID</TableHead><TableHead>Status</TableHead><TableHead>Experiment</TableHead><TableHead className="hidden lg:table-cell">Worker / source</TableHead><TableHead className="hidden md:table-cell">Created</TableHead><TableHead className="w-12"><span className="sr-only">Actions</span></TableHead></TableRow></TableHeader><TableBody>{queue.map((item) => {
        const isRun = "change_summary" in item
        return <TableRow key={`${isRun ? "run" : "experiment"}-${item.id}`} className={isRun ? "cursor-pointer" : ""} onClick={() => isRun && openRun(item.id)}><TableCell className="font-mono text-xs">{item.display_id}</TableCell><TableCell><StatusBadge value={item.lifecycle} /></TableCell><TableCell><strong className="block max-w-lg truncate text-sm font-medium">{isRun ? item.name : item.title}</strong><span className="mt-1 block max-w-lg truncate text-xs text-muted-foreground">{item.hypothesis}</span></TableCell><TableCell className="hidden text-xs text-muted-foreground lg:table-cell">{isRun ? "active run" : item.claimed_by || item.source}</TableCell><TableCell className="hidden text-xs text-muted-foreground md:table-cell">{formatDate(isRun ? item.started_at : item.created_at)}</TableCell><TableCell onClick={(event) => event.stopPropagation()}><RecordActions slug={slug} id={item.id} type={isRun ? "run" : "experiment"} onChanged={reload} /></TableCell></TableRow>
      })}</TableBody></Table></div> : <Empty className="min-h-56 border"><EmptyHeader><EmptyMedia variant="icon"><FlaskConical /></EmptyMedia><EmptyTitle>The queue is empty</EmptyTitle><EmptyDescription>Propose an experiment here or let a planning agent add one through MCP.</EmptyDescription></EmptyHeader></Empty>}
    </section>

    <section>
      <div className="mb-4"><h2 className="text-lg font-semibold">Recent completed experiments</h2><p className="mt-1 text-sm text-muted-foreground">Durable evidence available to future agents.</p></div>
      {data.history.length ? <div className="overflow-hidden rounded-lg border"><Table><TableHeader><TableRow><TableHead>Run</TableHead><TableHead className="hidden md:table-cell">Finished</TableHead><TableHead>Result</TableHead><TableHead>Disposition</TableHead><TableHead className="w-12"><span className="sr-only">Actions</span></TableHead></TableRow></TableHeader><TableBody>{data.history.slice(0, 12).map((run) => <TableRow key={run.id} className="cursor-pointer" onClick={() => openRun(run.id)}><TableCell><span className="font-mono text-xs text-muted-foreground">{run.display_id}</span><strong className="mt-1 block max-w-sm truncate text-sm">{run.name}</strong></TableCell><TableCell className="hidden text-xs text-muted-foreground md:table-cell">{formatDate(run.finished_at)}</TableCell><TableCell className="max-w-xs truncate font-mono text-xs">{run.result_summary || latestMetric(run, data.project.progress_metric_key)}</TableCell><TableCell><StatusBadge value={run.lifecycle === "crashed" ? "crashed" : run.disposition} /></TableCell><TableCell onClick={(event) => event.stopPropagation()}><RecordActions slug={slug} id={run.id} type="run" canBaseline={run.lifecycle === "completed"} onChanged={reload} /></TableCell></TableRow>)}</TableBody></Table></div> : <Empty className="min-h-48 border"><EmptyHeader><EmptyMedia variant="icon"><Activity /></EmptyMedia><EmptyTitle>No completed runs</EmptyTitle><EmptyDescription>Tracked runs will appear here after an agent finishes or crashes them.</EmptyDescription></EmptyHeader></Empty>}
    </section>
  </>
}

function SearchView({ data, slug, reload, openRun }: { data: Dashboard; slug: string; reload: () => void; openRun: (id: string) => void }) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [searched, setSearched] = useState(false)
  const [pending, setPending] = useState(false)
  const [includeTags, setIncludeTags] = useState<string[]>([])
  const [excludeTags, setExcludeTags] = useState<string[]>([])
  async function runSearch(nextInclude = includeTags, nextExclude = excludeTags) { setPending(true); try { const response = await runtrace.search(slug, query, false, nextInclude, nextExclude); setResults(response.results); setSearched(true) } catch (error) { toast.error(error instanceof Error ? error.message : "Search failed") } finally { setPending(false) } }
  async function submit(event: FormEvent) { event.preventDefault(); await runSearch() }
  function filtersChanged(nextInclude: string[], nextExclude: string[]) { setIncludeTags(nextInclude); setExcludeTags(nextExclude); if (searched) runSearch(nextInclude, nextExclude) }
  function recordChanged() { reload(); runSearch() }
  return <><PageHeading title="Search" description={`Semantic and keyword retrieval across ${data.project.name} experiments, reasoning, configurations, outcomes, and conclusions.`} />
    <form onSubmit={submit} className="mb-4 flex gap-2"><label className="relative flex-1"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input className="h-11 pl-10" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="What has already been tried?" aria-label="Search experiment evidence" /></label><Button className="h-11" type="submit" disabled={pending || (!query.trim() && !includeTags.length && !excludeTags.length)}>{pending ? "Searching…" : "Search"}</Button></form>
    <div className="mb-8"><TagFilter tags={data.available_tags} include={includeTags} exclude={excludeTags} onChange={filtersChanged} /></div>
    {searched && !results.length ? <Empty className="min-h-64 border"><EmptyHeader><EmptyMedia variant="icon"><Search /></EmptyMedia><EmptyTitle>No matching evidence</EmptyTitle><EmptyDescription>Try a broader description, metric name, or implementation detail.</EmptyDescription></EmptyHeader></Empty> : null}
    <div className="divide-y border-y">{results.map((result) => <div key={`${result.kind}-${result.id}`} className="grid gap-3 py-5 sm:grid-cols-[1fr_auto]"><button type="button" onClick={() => result.kind === "run" && openRun(result.id)} className="min-w-0 text-left"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs text-muted-foreground">{result.display_id}</span><Badge variant="secondary">{result.kind}</Badge>{result.match_type ? <Badge variant="outline">{result.match_type}</Badge> : null}{result.tags.map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}</div><h2 className="mt-2 font-medium">{result.title}</h2><p className="mt-1 line-clamp-2 text-sm leading-6 text-muted-foreground">{result.conclusion || result.result_summary || result.hypothesis}</p></button><div className="flex items-start gap-2"><StatusBadge value={result.lifecycle === "completed" ? result.disposition : result.lifecycle} /><RecordActions slug={slug} id={result.id} type={result.kind} archived={result.archived} canBaseline={result.kind === "run" && result.lifecycle === "completed"} onChanged={recordChanged} /></div></div>)}</div>
  </>
}

function ArchiveView({ data, slug, reload, openRun }: { data: Dashboard; slug: string; reload: () => void; openRun: (id: string) => void }) {
  return <><PageHeading title="Archive" description="Archived records are excluded from active dashboards, claims, ordinary search, and default agent context." />
    {data.archived.length ? <div className="divide-y border-y">{data.archived.map((item) => { const isRun = "change_summary" in item; return <div key={item.id} className="grid grid-cols-[1fr_auto] items-center gap-5 py-5"><button className="text-left" onClick={() => isRun && openRun(item.id)}><span className="font-mono text-xs text-muted-foreground">{item.display_id}</span><strong className="mt-1 block text-sm">{isRun ? item.name : item.title}</strong><p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{item.hypothesis}</p></button><RecordActions slug={slug} id={item.id} type={isRun ? "run" : "experiment"} archived onChanged={reload} /></div> })}</div> : <Empty className="min-h-72 border"><EmptyHeader><EmptyMedia variant="icon"><Archive /></EmptyMedia><EmptyTitle>Nothing is archived</EmptyTitle><EmptyDescription>Archived experiments and runs remain restorable and auditable.</EmptyDescription></EmptyHeader></Empty>}
  </>
}

function SettingsView({ data, slug, reload }: { data: Dashboard; slug: string; reload: () => void }) {
  const [description, setDescription] = useState(data.project.description)
  const [program, setProgram] = useState(data.program.content)
  const [exclusions, setExclusions] = useState(data.exclusions.join("\n"))
  const [metric, setMetric] = useState(data.project.progress_metric_key)
  const [direction, setDirection] = useState(data.project.progress_metric_direction)
  const [pending, setPending] = useState(false)
  async function save(event: FormEvent) { event.preventDefault(); setPending(true); try { await Promise.all([runtrace.updateProject(slug, description), runtrace.updateProgram(slug, program), runtrace.updateExclusions(slug, exclusions.split("\n")), runtrace.updateSettings(slug, metric, direction)]); toast.success("Project settings saved"); reload() } catch (error) { toast.error(error instanceof Error ? error.message : "Could not save settings") } finally { setPending(false) } }
  const bootstrap = `runtrace.get_project_context({ project: "${slug}" })`
  return <form onSubmit={save}><PageHeading title="Settings" description="Durable research context returned to every agent that bootstraps this project." actions={<Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save changes"}</Button>} />
    <div className="flex flex-col gap-6">
      <Card><CardHeader><CardTitle>Project goal</CardTitle><CardDescription>Shown on the dashboard and used to orient human supervisors.</CardDescription></CardHeader><CardContent><Field><FieldLabel htmlFor="goal">Goal</FieldLabel><Textarea id="goal" value={description} onChange={(event) => setDescription(event.target.value)} /></Field></CardContent></Card>
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><FileText className="size-4" />program.md <Badge variant="secondary">v{data.program.version}</Badge></CardTitle><CardDescription>The objective, evaluation contract, implementation boundaries, and evidence required to keep a change.</CardDescription></CardHeader><CardContent><Field><FieldLabel htmlFor="program" className="sr-only">program.md</FieldLabel><Textarea id="program" className="min-h-72 font-mono text-xs leading-6" value={program} onChange={(event) => setProgram(event.target.value)} /></Field></CardContent></Card>
      <Card id="exclusions"><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="size-4" />Research exclusions</CardTitle><CardDescription>One durable constraint per line. These guide agents but do not control workers.</CardDescription></CardHeader><CardContent><Field><FieldLabel htmlFor="exclusions" className="sr-only">Research exclusions</FieldLabel><Textarea id="exclusions" className="min-h-32 font-mono text-xs leading-6" value={exclusions} onChange={(event) => setExclusions(event.target.value)} placeholder="Do not use…" /></Field></CardContent></Card>
      <Card><CardHeader><CardTitle>Progress metric</CardTitle><CardDescription>Use the exact metric name emitted by the SDK or agent.</CardDescription></CardHeader><CardContent><FieldGroup><Field><FieldLabel htmlFor="metric">Metric name</FieldLabel><Input id="metric" className="font-mono" value={metric} onChange={(event) => setMetric(event.target.value)} list="available-metrics" /><datalist id="available-metrics">{data.available_metrics.map((value) => <option value={value} key={value} />)}</datalist></Field><Field><FieldLabel>Direction</FieldLabel><Select value={direction} onValueChange={(value) => value && setDirection(String(value) as typeof direction)}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="lower_is_better">Lower is better</SelectItem><SelectItem value="higher_is_better">Higher is better</SelectItem></SelectGroup></SelectContent></Select></Field></FieldGroup></CardContent></Card>
      <Card><CardHeader><CardTitle>Agent bootstrap</CardTitle><CardDescription>Retrieve program.md, exclusions, baseline, metric definitions, proposals, and recent evidence in one call.</CardDescription></CardHeader><CardContent><div className="flex items-center gap-2 rounded-lg border bg-muted/50 p-3"><code className="min-w-0 flex-1 truncate text-xs">{bootstrap}</code><Button type="button" size="icon-sm" variant="ghost" aria-label="Copy bootstrap call" onClick={() => { navigator.clipboard.writeText(bootstrap); toast.success("Copied") }}><Copy /></Button></div><FieldDescription className="mt-3">Registry endpoint: {data.project.registry_endpoint}</FieldDescription></CardContent></Card>
    </div>
  </form>
}

export function ProjectWorkspace({ slug, view }: { slug: string; view: ProjectView }) {
  const [data, setData] = useState<Dashboard | null>(null)
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const progressQuery = useRef({ metric: "", window: "30d", includeTags: [] as string[], excludeTags: [] as string[] })
  const load = useCallback(async () => {
    const query = progressQuery.current
    try { const [dashboard, progressData] = await Promise.all([runtrace.dashboard(slug), runtrace.progress(slug, query.metric, query.window, query.includeTags, query.excludeTags)]); setData(dashboard); setProgress(progressData); setError(null) }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load project") }
  }, [slug])
  useEffect(() => {
    let active = true
    Promise.all([runtrace.dashboard(slug), runtrace.progress(slug)]).then(([dashboard, progressData]) => {
      if (!active) return
      setData(dashboard); setProgress(progressData); setError(null)
    }).catch((caught) => {
      if (active) setError(caught instanceof Error ? caught.message : "Could not load project")
    })
    return () => { active = false }
  }, [slug])
  useEffect(() => {
    if (!data?.active_runs.length) return
    const streams = data.active_runs.map((run) => { const source = new EventSource(`/api/v1/runs/${run.id}/stream`); source.addEventListener("status", (event) => { const status = JSON.parse((event as MessageEvent).data); if (status.lifecycle !== "running") load() }); source.addEventListener("metric", () => { const query = progressQuery.current; runtrace.progress(slug, query.metric, query.window, query.includeTags, query.excludeTags).then(setProgress).catch(() => undefined) }); return source })
    return () => streams.forEach((source) => source.close())
  }, [data?.active_runs, load, slug])

  if (error) return <main className="grid min-h-screen place-items-center p-6"><Empty className="max-w-lg border"><EmptyHeader><EmptyMedia variant="icon"><Database /></EmptyMedia><EmptyTitle>RunTrace API unavailable</EmptyTitle><EmptyDescription>{error}</EmptyDescription></EmptyHeader><Button onClick={load}>Try again</Button></Empty></main>
  if (!data || !progress) return <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]"><div className="hidden border-r bg-sidebar lg:block" /><main className="mx-auto w-full max-w-[1240px] p-8"><Skeleton className="h-10 w-64" /><Skeleton className="mt-8 h-80" /><Skeleton className="mt-6 h-36" /></main></div>
  return <ProjectShell project={data.project}>
    {view === "dashboard" ? <DashboardView data={data} progress={progress} slug={slug} reload={load} setProgress={setProgress} openRun={setSelectedRun} onProgressQueryChange={(value) => { progressQuery.current = value }} /> : null}
    {view === "search" ? <SearchView data={data} slug={slug} reload={load} openRun={setSelectedRun} /> : null}
    {view === "archive" ? <ArchiveView data={data} slug={slug} reload={load} openRun={setSelectedRun} /> : null}
    {view === "settings" ? <SettingsView key={data.project.updated_at + data.program.version} data={data} slug={slug} reload={load} /> : null}
    <RunDetailSheet runId={selectedRun} onClose={() => setSelectedRun(null)} />
  </ProjectShell>
}
