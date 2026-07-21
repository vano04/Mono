import assert from "node:assert/strict"
import test from "node:test"

import { projectCapabilities } from "../src/lib/project-access.ts"

test("viewers are read-only", () => {
  assert.deepEqual(projectCapabilities("viewer"), { canEdit: false, canManage: false })
})

test("editors can change project data without managing ownership", () => {
  assert.deepEqual(projectCapabilities("editor"), { canEdit: true, canManage: false })
})

test("owners can edit and manage project access", () => {
  assert.deepEqual(projectCapabilities("owner"), { canEdit: true, canManage: true })
})
