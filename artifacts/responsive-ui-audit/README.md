# RunTrace responsive UI audit

Audit date: 2026-07-14

## Scope

Primary Dense Optimizer dashboard at desktop (1440×900), mobile (390×844), and a 16:9 portrait monitor (1080×1920). The audit combines rendered screenshots with layout measurements from the running local app.

## Summary

The desktop dashboard has a clear hierarchy and consistent component language. Mobile reflow generally works, but charts and dense data tables rely heavily on horizontal scrolling. At 1080×1920, the page is 161 px wider than the visible document (1226 px content versus 1065 px client width), which reproduces the reported rightward scroll.

## Highest-impact findings

1. **Portrait-monitor page overflow.** The shell uses `lg:grid-cols-[248px_1fr]`. The `1fr` track keeps its automatic minimum, so wide dashboard content expands the main column to 978 px instead of the roughly 817 px available beside the sidebar. Use `lg:grid-cols-[248px_minmax(0,1fr)]` and add `min-w-0` to the main-column wrapper.
2. **Wide breakpoint activates too early for the full dashboard.** At 1080 px, the persistent 248 px sidebar leaves too little room for the four-column baseline summary, filters, and tables. Either delay the sidebar to `xl`, collapse it at portrait widths, or introduce a dedicated intermediate layout between roughly 1024 and 1279 px.
3. **Mobile chart is technically responsive but not comfortably usable.** The 620 px minimum SVG creates an internal horizontal scroller. This preserves chart legibility, but hides later dates and points until the user swipes. Prefer a true narrow chart mode with fewer ticks, a smaller left gutter, and a selected-point summary below the chart.
4. **Tables need a mobile presentation.** Horizontal scrolling prevents document overflow, but users must pan to understand a row. Keep tables for larger screens and render compact record cards on small screens, prioritizing ID/status, experiment name, result, and the action menu.
5. **Mobile controls are smaller than comfortable touch targets.** Default buttons and selects are 32 px tall, icon buttons are 32 px, and chart hit circles are 22 px. Preserve the compact desktop density but increase coarse-pointer targets toward 44 px.
6. **The recent-experiments region forces a viewport-height nested scroller on mobile.** Limit the `h-[calc(...)]` behavior to larger screens so the small-screen page uses natural document flow and avoids a scroll trap.

## Evidence

- `04-dashboard-desktop-viewport.png`
- `05-dashboard-mobile-viewport.png`
- `06-dashboard-portrait-viewport.png`
- Full-page captures are included as `01` through `03`.

## Verification limits

This pass covered the primary dashboard and responsive reflow. It did not fully exercise dialogs, search, settings, screen-reader output, browser zoom, or every keyboard focus state, so it is not a complete accessibility-conformance review.
