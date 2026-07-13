import { ProjectWorkspace } from "@/components/project-workspace"

export default async function SearchPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <ProjectWorkspace slug={slug} view="search" />
}
