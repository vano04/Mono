"use client"

import { useState } from "react"

import type { ProgressData } from "@/lib/types"

function formatTick(value: string, showTime: boolean) {
  return new Intl.DateTimeFormat(undefined, showTime ? { hour: "numeric", minute: "2-digit" } : { month: "short", day: "numeric" }).format(new Date(value))
}

function formatDetailDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value))
}

export function ProgressChart({ data }: { data: ProgressData }) {
  const [hovered, setHovered] = useState<number | null>(null)
  const [pinned, setPinned] = useState<number | null>(null)
  if (!data.series.length) {
    return <div className="grid h-64 place-items-center text-center text-sm text-muted-foreground">Complete runs with the selected metric and tags to see progress.</div>
  }
  const width = 940, height = 300, padLeft = 58, padRight = 24, padTop = 30, padBottom = 48
  const observed = data.series.flatMap((point) => [point.improvement, point.best_improvement])
  const min = Math.min(0, ...observed), max = Math.max(0, ...observed)
  const span = max - min || 1
  const plotWidth = width - padLeft - padRight
  const x = (index: number) => padLeft + index * (plotWidth / Math.max(1, data.series.length - 1))
  const y = (value: number) => padTop + (max - value) / span * (height - padTop - padBottom)
  const stepPath = data.series.reduce((path, point, index) => {
    const px = x(index), py = y(point.best_improvement)
    if (index === 0) return `M ${px} ${py}`
    return `${path} H ${px} V ${py}`
  }, "")
  const tickStride = Math.max(1, Math.ceil((data.series.length - 1) / 5))
  const tickIndexes = new Set(data.series.map((_, index) => index).filter((index) => index % tickStride === 0))
  tickIndexes.add(data.series.length - 1)
  const pointStride = Math.max(1, Math.ceil(data.series.length / 40))
  const visibleIndexes = new Set(data.series.map((point, index) => index).filter((index) => index % pointStride === 0 || data.series[index].is_improvement))
  visibleIndexes.add(data.series.length - 1)
  const timeSpan = new Date(data.series.at(-1)!.timestamp).getTime() - new Date(data.series[0].timestamp).getTime()
  const showTickTime = timeSpan < 24 * 60 * 60 * 1000
  const activeIndex = hovered ?? pinned
  const activePoint = activeIndex === null ? null : data.series[activeIndex]
  const detailWidth = 218, detailHeight = activePoint?.tags.length ? 112 : 92
  const detailGap = 16
  const activeX = activeIndex === null ? 0 : x(activeIndex)
  const activeY = activePoint === null ? 0 : y(activePoint.improvement)
  const hasRoomOnRight = width - padRight - activeX >= detailWidth + detailGap
  const detailX = activeIndex === null
    ? 0
    : hasRoomOnRight
      ? activeX + detailGap
      : activeX - detailWidth - detailGap
  const detailY = activePoint === null
    ? 0
    : Math.min(height - padBottom - detailHeight, Math.max(5, activeY - detailHeight / 2))

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="progress-title progress-description" className="min-w-[620px]">
        <title id="progress-title">{data.label} improvement over time</title>
        <desc id="progress-description">Best observed improvement is {data.series.at(-1)?.best_improvement.toFixed(2)} percent over the first matching run. Points are shown at intervals and for every new best. Hover or focus a point for details; click to keep it open.</desc>
        {[0, .25, .5, .75, 1].map((fraction) => {
          const value = max - fraction * span
          return <g key={fraction}><line x1={padLeft} x2={width - padRight} y1={y(value)} y2={y(value)} className="stroke-border" /><text x={padLeft - 10} y={y(value) + 4} textAnchor="end" className="fill-muted-foreground text-[10px] font-mono">{value.toFixed(1)}%</text></g>
        })}
        <path d={stepPath} fill="none" className="stroke-primary" strokeWidth="3" strokeLinejoin="round" />
        {Array.from(tickIndexes).map((index) => <g key={`tick-${index}`}><line x1={x(index)} x2={x(index)} y1={height - padBottom + 5} y2={height - padBottom + 10} className="stroke-border" /><text x={x(index)} y={height - 17} textAnchor="middle" className="fill-muted-foreground text-[10px] font-mono">{formatTick(data.series[index].timestamp, showTickTime)}</text></g>)}
        {data.series.map((point, index) => visibleIndexes.has(index) ? (
          <g key={point.run_id} role="button" tabIndex={0} aria-label={`${point.display_id}, ${point.raw_value}, ${point.improvement.toFixed(2)} percent`} className="cursor-pointer outline-none" onMouseEnter={() => setHovered(index)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(index)} onBlur={() => setHovered(null)} onClick={() => setPinned(pinned === index ? null : index)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setPinned(pinned === index ? null : index) } }}>
            <circle cx={x(index)} cy={y(point.improvement)} r="11" className="fill-transparent" />
            <circle cx={x(index)} cy={y(point.improvement)} r={activeIndex === index ? "6.5" : "5"} className={point.is_improvement ? "fill-background stroke-primary" : "fill-muted-foreground stroke-background"} strokeWidth="2" />
          </g>
        ) : null)}
        {activePoint ? <foreignObject x={detailX} y={detailY} width={detailWidth} height={detailHeight} className="pointer-events-none overflow-visible">
          <div className="rounded-lg border bg-popover p-3 text-xs text-popover-foreground shadow-lg">
            <div className="flex items-center justify-between gap-3"><strong className="font-mono">{activePoint.display_id}</strong><span className="text-muted-foreground">{formatDetailDate(activePoint.timestamp)}</span></div>
            <div className="mt-1 truncate font-medium">{activePoint.name}</div>
            <div className="mt-2 grid grid-cols-2 gap-2 font-mono"><span>{activePoint.raw_value}{data.unit ? ` ${data.unit}` : ""}</span><span className="text-right">{activePoint.improvement >= 0 ? "+" : ""}{activePoint.improvement.toFixed(2)}%</span></div>
            <div className="mt-1 flex justify-between text-muted-foreground"><span>{activePoint.final_step === null ? "No step" : `Step ${activePoint.final_step.toLocaleString()}`}</span><span>{activePoint.is_improvement ? "New best" : "Observed"}</span></div>
            {activePoint.tags.length ? <div className="mt-2 truncate text-muted-foreground">{activePoint.tags.join(" · ")}</div> : null}
          </div>
        </foreignObject> : null}
      </svg>
      <p className="mt-1 text-center text-xs text-muted-foreground">{data.series.length} matching runs · {visibleIndexes.size} interval/new-best points shown · click a point to pin details</p>
    </div>
  )
}
