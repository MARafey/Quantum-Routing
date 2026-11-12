// Drives the planner in headless Chrome and records a demo video plus screenshots.
// Needs both servers running: `uv run qroute-server` (backend) and `npm run dev` (frontend).
// Usage: node scripts/record-demo.mjs      (Chrome must be installed; run `npx playwright-core install ffmpeg` once)
import { chromium } from 'playwright-core'
import { mkdirSync, readdirSync, renameSync, rmSync } from 'node:fs'
import { join } from 'node:path'

const URL = process.env.DEMO_URL || 'http://localhost:5173/'
const OUT = new globalThis.URL('../../docs/media/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const TMP = join(OUT, '_rec')
const RUNS = 3
mkdirSync(TMP, { recursive: true })

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, recordVideo: { dir: TMP, size: { width: 1600, height: 900 } } })
const page = await context.newPage()
const wait = (ms) => page.waitForTimeout(ms)
// Pin "Random stops" to seeded scenarios (1, 2 and 3 convoys) so the recording is reproducible
// and road geometry comes from the OSRM cache. Override with DEMO_SEEDS=4,9,10.
const SEEDS = (process.env.DEMO_SEEDS || '2,7,5').split(',')
let seedIdx = 0
await page.route('**/api/random**', (route) => {
  const u = new globalThis.URL(route.request().url())
  u.searchParams.set('seed', SEEDS[seedIdx++ % SEEDS.length])
  route.continue({ url: u.toString() })
})
await page.goto(URL, { waitUntil: 'networkidle' })
await wait(2000)
for (let i = 1; i <= RUNS; i++) {
  await page.getByRole('button', { name: /Random stops/ }).click()
  await wait(2200)
  if (i === 1) await page.screenshot({ path: join(OUT, 'planner_stops.png') })
  await page.getByRole('button', { name: /^Run$/ }).click()
  await page.waitForResponse((r) => r.url().includes('/api/run'), { timeout: 90000 })
  await wait(1500)
  if (i === 1) await page.screenshot({ path: join(OUT, 'planner_search.png') })
  await wait(4500)
  await page.screenshot({ path: join(OUT, `planner_result_${i}.png`) })
  await wait(2500)
}
await context.close()
await browser.close()
const vid = readdirSync(TMP).find((f) => f.endsWith('.webm'))
if (vid) renameSync(join(TMP, vid), join(OUT, 'planner.webm'))
rmSync(TMP, { recursive: true, force: true })
console.log('saved to', OUT)
