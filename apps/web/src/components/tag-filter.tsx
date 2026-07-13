"use client"

import { Filter, MinusCircle, PlusCircle, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuGroup, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

export function TagFilter({ tags, include, exclude, onChange }: {
  tags: string[]
  include: string[]
  exclude: string[]
  onChange: (include: string[], exclude: string[]) => void
}) {
  const toggleInclude = (tag: string, checked: boolean) => onChange(
    checked ? [...include, tag] : include.filter((value) => value !== tag),
    checked ? exclude.filter((value) => value !== tag) : exclude,
  )
  const toggleExclude = (tag: string, checked: boolean) => onChange(
    checked ? include.filter((value) => value !== tag) : include,
    checked ? [...exclude, tag] : exclude.filter((value) => value !== tag),
  )
  const active = include.length + exclude.length

  return (
    <div className="flex flex-wrap items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button type="button" variant="outline" size="sm" />}>
          <Filter data-icon="inline-start" />Tags{active ? ` (${active})` : ""}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {tags.length ? <>
            <DropdownMenuGroup>
              <DropdownMenuLabel>Include all selected</DropdownMenuLabel>
              {tags.map((tag) => <DropdownMenuCheckboxItem key={`include-${tag}`} checked={include.includes(tag)} onCheckedChange={(checked) => toggleInclude(tag, checked === true)}><PlusCircle />{tag}</DropdownMenuCheckboxItem>)}
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuLabel>Exclude any selected</DropdownMenuLabel>
              {tags.map((tag) => <DropdownMenuCheckboxItem key={`exclude-${tag}`} checked={exclude.includes(tag)} onCheckedChange={(checked) => toggleExclude(tag, checked === true)}><MinusCircle />{tag}</DropdownMenuCheckboxItem>)}
            </DropdownMenuGroup>
          </> : <DropdownMenuGroup><DropdownMenuLabel>No tags recorded</DropdownMenuLabel></DropdownMenuGroup>}
        </DropdownMenuContent>
      </DropdownMenu>
      {include.map((tag) => <Badge key={`included-${tag}`} variant="secondary">+ {tag}<button type="button" aria-label={`Remove included tag ${tag}`} onClick={() => toggleInclude(tag, false)}><X /></button></Badge>)}
      {exclude.map((tag) => <Badge key={`excluded-${tag}`} variant="outline">− {tag}<button type="button" aria-label={`Remove excluded tag ${tag}`} onClick={() => toggleExclude(tag, false)}><X /></button></Badge>)}
      {active ? <Button type="button" size="sm" variant="ghost" onClick={() => onChange([], [])}>Clear</Button> : null}
    </div>
  )
}
