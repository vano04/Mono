export type ProjectAccessRole = "owner" | "editor" | "viewer"

export interface ProjectCapabilities {
  canEdit: boolean
  canManage: boolean
}

export function projectCapabilities(role: ProjectAccessRole): ProjectCapabilities {
  return {
    canEdit: role === "owner" || role === "editor",
    canManage: role === "owner",
  }
}
