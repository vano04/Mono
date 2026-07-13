import { ProjectWorkspace } from "@/components/project-workspace"

export default async function SettingsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <ProjectWorkspace slug={slug} view="settings" />
}
