"use client"

import { useState } from "react"
import { Download, Ellipsis, Eye, EyeOff, FileJson, Pencil, Plus, Sparkles, Trash2, Upload } from "lucide-react"
import { toast } from "sonner"

import { VisualizationRenderer } from "@/components/visualization-renderer"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { runtrace } from "@/lib/api"
import type { RTVisSpec, Visualization, VisualizationDocument } from "@/lib/types"

const NEW_WIDGET: RTVisSpec = {
  $schema: "https://runtrace.dev/schemas/rtvis/v1.json",
  version: 1,
  title: "Custom widget",
  description: "A portable interactive RunTrace widget",
  datasets: { data: { source: "inline", rows: [] } },
  view: {
    type: "javascript",
    title: "Custom widget",
    height: 320,
    markup: '<div class="card"><span class="badge">Interactive</span><h2>Custom widget</h2><p id="summary" class="muted"></p><button id="action" class="btn btn-primary">Update</button></div>',
    styles: "h2 { margin: 12px 0 4px; font-size: 20px; } #summary { margin: 0 0 16px; }",
    script: "const rows = window.runtrace.datasets.data || [];\nconst summary = document.getElementById('summary');\nsummary.textContent = `${rows.length} data rows available`;\ndocument.getElementById('action').addEventListener('click', () => { summary.textContent = 'Widget interaction works'; });",
  },
}

function downloadDocument(document: VisualizationDocument) {
  const blob = new Blob([JSON.stringify(document, null, 2)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const anchor = window.document.createElement("a")
  anchor.href = url
  anchor.download = `${document.visualization.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "visualization"}.rtvis.json`
  anchor.click()
  URL.revokeObjectURL(url)
}

function SpecEditor({ slug, visualization, open, onOpenChange, onSaved }: { slug: string; visualization: Visualization; open: boolean; onOpenChange: (open: boolean) => void; onSaved: () => void }) {
  const [value, setValue] = useState(() => JSON.stringify(visualization.spec, null, 2))
  const [pending, setPending] = useState(false)

  async function save() {
    setPending(true)
    try {
      const spec = JSON.parse(value) as RTVisSpec
      await runtrace.updateVisualization(slug, visualization.id, { spec })
      toast.success("Visualization updated")
      onOpenChange(false)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update visualization")
    } finally { setPending(false) }
  }

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-3xl">
      <DialogHeader><DialogTitle>Edit {visualization.name}</DialogTitle><DialogDescription>Edit the portable RTVis JSON. JavaScript widgets run in an isolated, network-disabled frame and receive RunTrace theme tokens.</DialogDescription></DialogHeader>
      <FieldGroup><Field><FieldLabel htmlFor="visualization-spec">RTVis JSON</FieldLabel><Textarea id="visualization-spec" className="min-h-64 font-mono text-xs sm:min-h-96" value={value} onChange={(event) => setValue(event.target.value)} spellCheck={false} /><FieldDescription>Revision {visualization.revision} · schema version {visualization.spec_version}</FieldDescription></Field></FieldGroup>
      <DialogFooter showCloseButton><Button type="button" onClick={save} disabled={pending}>{pending ? "Saving…" : "Save visualization"}</Button></DialogFooter>
    </DialogContent>
  </Dialog>
}

function NewVisualizationDialog({ slug, onCreated }: { slug: string; onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("Custom widget")
  const [description, setDescription] = useState("")
  const [value, setValue] = useState(JSON.stringify(NEW_WIDGET, null, 2))
  const [pending, setPending] = useState(false)

  async function create() {
    setPending(true)
    try {
      await runtrace.createVisualization(slug, { name: name.trim(), description: description.trim(), spec: JSON.parse(value) as RTVisSpec })
      toast.success("Visualization created")
      setOpen(false)
      setName("Custom widget"); setDescription(""); setValue(JSON.stringify(NEW_WIDGET, null, 2))
      onCreated()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create visualization")
    } finally { setPending(false) }
  }

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger render={<Button type="button" size="sm" />}><Plus data-icon="inline-start" />New</DialogTrigger>
    <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-3xl">
      <DialogHeader><DialogTitle>New visualization</DialogTitle><DialogDescription>Start with a portable JavaScript widget or replace the template with ShadCN-backed RTVis nodes.</DialogDescription></DialogHeader>
      <FieldGroup><Field><FieldLabel htmlFor="visualization-name">Name</FieldLabel><Input id="visualization-name" value={name} onChange={(event) => setName(event.target.value)} /></Field><Field><FieldLabel htmlFor="visualization-description">Description</FieldLabel><Input id="visualization-description" value={description} onChange={(event) => setDescription(event.target.value)} /></Field><Field><FieldLabel htmlFor="new-visualization-spec">RTVis JSON</FieldLabel><Textarea id="new-visualization-spec" className="min-h-72 font-mono text-xs sm:min-h-96" value={value} onChange={(event) => setValue(event.target.value)} spellCheck={false} /><FieldDescription>The template can use <code>window.runtrace.datasets</code>, <code>window.runtrace.theme</code>, and the included ShadCN-like utility classes.</FieldDescription></Field></FieldGroup>
      <DialogFooter showCloseButton><Button type="button" onClick={create} disabled={pending || !name.trim()}>{pending ? "Creating…" : "Create visualization"}</Button></DialogFooter>
    </DialogContent>
  </Dialog>
}

function ImportDialog({ slug, onImported }: { slug: string; onImported: () => void }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState("")
  const [pending, setPending] = useState(false)
  async function importDocument() {
    setPending(true)
    try {
      await runtrace.importVisualization(slug, JSON.parse(value) as VisualizationDocument)
      toast.success("Visualization imported"); setValue(""); setOpen(false); onImported()
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not import visualization") }
    finally { setPending(false) }
  }
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger render={<Button type="button" variant="outline" size="sm" />}><Upload data-icon="inline-start" />Import</DialogTrigger>
    <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl">
      <DialogHeader><DialogTitle>Import visualization</DialogTitle><DialogDescription>Paste a complete versioned RunTrace visualization export.</DialogDescription></DialogHeader>
      <Field><FieldLabel htmlFor="visualization-import">Export document</FieldLabel><Textarea id="visualization-import" className="min-h-80 font-mono text-xs" value={value} onChange={(event) => setValue(event.target.value)} placeholder='{"format":"runtrace-visualization","version":1,…}' spellCheck={false} /></Field>
      <DialogFooter showCloseButton><Button type="button" onClick={importDocument} disabled={pending || !value.trim()}>{pending ? "Importing…" : "Import"}</Button></DialogFooter>
    </DialogContent>
  </Dialog>
}

export function ProjectVisualizationWidgets({ visualizations }: { visualizations: Visualization[] }) {
  const visible = visualizations.filter((item) => item.visible)
  if (!visible.length) return null
  return <section className="mb-10"><div className="mb-4"><h2 className="text-lg font-semibold">Custom visualizations</h2><p className="mt-1 text-sm text-muted-foreground">Project-specific views configured in Settings.</p></div><div className="flex flex-col gap-8">{visible.map((item) => <VisualizationRenderer key={item.id} visualization={item} />)}</div></section>
}

export function VisualizationSettings({ slug, visualizations, reload }: { slug: string; visualizations: Visualization[]; reload: () => void }) {
  const [editTarget, setEditTarget] = useState<Visualization | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Visualization | null>(null)

  async function toggle(item: Visualization) {
    try { await runtrace.updateVisualization(slug, item.id, { visible: !item.visible }); toast.success(item.visible ? "Visualization hidden" : "Visualization shown"); reload() }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not update visualization") }
  }
  async function exportItem(item: Visualization) {
    try { downloadDocument(await runtrace.exportVisualization(slug, item.id)) }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not export visualization") }
  }
  async function remove() {
    if (!deleteTarget) return
    try { await runtrace.deleteVisualization(slug, deleteTarget.id); toast.success("Visualization deleted"); setDeleteTarget(null); reload() }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not delete visualization") }
  }

  return <>
    <Card>
      <CardHeader><CardTitle>Custom visualizations</CardTitle><CardDescription>Portable project widgets generated through MCP or configured manually.</CardDescription><CardAction><div className="flex gap-2"><ImportDialog slug={slug} onImported={reload} /><NewVisualizationDialog slug={slug} onCreated={reload} /></div></CardAction></CardHeader>
      <CardContent>
        {visualizations.length ? <div className="divide-y rounded-lg border">{visualizations.map((item) => <div key={item.id} className="flex items-center gap-4 p-4"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><strong className="truncate text-sm font-medium">{item.name}</strong><Badge variant={item.visible ? "secondary" : "outline"}>{item.visible ? "Visible" : "Hidden"}</Badge><Badge variant="outline">RTVis v{item.spec_version}</Badge></div><p className="mt-1 truncate text-xs text-muted-foreground">{item.description || item.spec.description || "No description"}</p></div><DropdownMenu><DropdownMenuTrigger render={<Button type="button" variant="ghost" size="icon-sm" aria-label={`Actions for ${item.name}`} />}><Ellipsis /></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuGroup><DropdownMenuItem onClick={() => setEditTarget(item)}><Pencil />Edit</DropdownMenuItem><DropdownMenuItem onClick={() => exportItem(item)}><Download />Export</DropdownMenuItem><DropdownMenuItem onClick={() => toggle(item)}>{item.visible ? <EyeOff /> : <Eye />}{item.visible ? "Hide" : "Show"}</DropdownMenuItem></DropdownMenuGroup><DropdownMenuSeparator /><DropdownMenuItem variant="destructive" onClick={() => setDeleteTarget(item)}><Trash2 />Delete</DropdownMenuItem></DropdownMenuContent></DropdownMenu></div>)}</div> : <Empty className="min-h-52 border"><EmptyHeader><EmptyMedia variant="icon"><Sparkles /></EmptyMedia><EmptyTitle>No custom visualizations</EmptyTitle><EmptyDescription>Create one manually, ask Codex to generate one through MCP, or import a portable JSON document.</EmptyDescription></EmptyHeader><EmptyContent><Badge variant="secondary"><FileJson />Portable JSON + JavaScript</Badge></EmptyContent></Empty>}
      </CardContent>
    </Card>
    {editTarget ? <SpecEditor key={editTarget.id} slug={slug} visualization={editTarget} open onOpenChange={(open) => { if (!open) setEditTarget(null) }} onSaved={reload} /> : null}
    <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}><AlertDialogContent size="sm"><AlertDialogHeader><AlertDialogTitle>Delete {deleteTarget?.name}?</AlertDialogTitle><AlertDialogDescription>The widget will be removed from this project. Export it first if you want a portable copy.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction variant="destructive" onClick={remove}>Delete</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </>
}
