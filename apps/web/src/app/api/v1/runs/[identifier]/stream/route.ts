import type { NextRequest } from "next/server"


export const dynamic = "force-dynamic"
export const runtime = "nodejs"


export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ identifier: string }> },
) {
  const { identifier } = await params
  const apiBaseUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000"
  const upstreamUrl = new URL(
    `/api/v1/runs/${encodeURIComponent(identifier)}/stream`,
    apiBaseUrl,
  )
  upstreamUrl.search = request.nextUrl.search

  const upstreamHeaders = new Headers({ Accept: "text/event-stream" })
  for (const name of ["authorization", "cookie", "last-event-id"]) {
    const value = request.headers.get(name)
    if (value) upstreamHeaders.set(name, value)
  }

  let upstream: Response
  try {
    upstream = await fetch(upstreamUrl, {
      cache: "no-store",
      headers: upstreamHeaders,
      signal: request.signal,
    })
  } catch {
    return Response.json(
      { detail: "Run stream is temporarily unavailable" },
      { status: 502 },
    )
  }

  const responseHeaders = new Headers()
  for (const name of ["content-type", "cache-control", "www-authenticate"]) {
    const value = upstream.headers.get(name)
    if (value) responseHeaders.set(name, value)
  }
  responseHeaders.set("Cache-Control", "no-cache, no-transform")
  responseHeaders.set("Connection", "keep-alive")
  responseHeaders.set("X-Accel-Buffering", "no")

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  })
}
