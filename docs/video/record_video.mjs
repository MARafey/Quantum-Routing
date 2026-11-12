// Records the submission video's picture: animated scenes (scenes.html) and a live demo of the planner.
// Needs: frontend dev server (npm run dev) + backend (uv run qroute-server), Chrome, playwright-core.
// Usage (after npm install in frontend/):  node docs/video/record_video.mjs <outDir> s1=16.64 s2=20.24 s3=27.04 s5=15.12
import { chromium } from '../../frontend/node_modules/playwright-core/index.mjs'
import { mkdirSync, readdirSync, renameSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const out = process.argv[2]
const durations = Object.fromEntries(process.argv.slice(3).filter((a) => a.includes('=')).map((a) => a.split('=')).map(([k, v]) => [k, parseFloat(v)]))
const SCENES = new globalThis.URL('./scenes.html', import.meta.url).href
const VIEW = { width: 1600, height: 900 }
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })

async function record(name, fn) {
  const tmp = join(out, '_' + name)
  rmSync(tmp, { recursive: true, force: true })
  const ctx = await browser.newContext({ viewport: VIEW, recordVideo: { dir: tmp, size: VIEW } })
  const page = await ctx.newPage()
  await fn(page)
  await ctx.close()
  renameSync(join(tmp, readdirSync(tmp)[0]), join(out, name + '.webm'))
  rmSync(tmp, { recursive: true, force: true })
  console.log('recorded', name)
}

for (const s of ['s1', 's2', 's3', 's5']) {
  if (!durations[s]) continue
  await record(s, async (page) => {
    await page.goto(`${SCENES}?scene=${s.slice(1)}`)
    await page.waitForTimeout((durations[s] + 1.2) * 1000)
  })
}

const SKIP_DEMO = process.argv.includes('--no-demo')
// Live demo: Pakistan run, then a cross-border run. Random stops are pinned to seeds for reproducibility.
if (!SKIP_DEMO) await record('demo', async (page) => {
  const seeds = { pakistan: 7, 'turkiye-syria': 3 }
  await page.route('**/api/random**', (route) => {
    const u = new globalThis.URL(route.request().url())
    u.searchParams.set('seed', seeds[u.searchParams.get('region') || 'pakistan'] ?? 1)
    route.continue({ url: u.toString() })
  })
  const wait = (ms) => page.waitForTimeout(ms)
  await page.goto(process.env.DEMO_URL || 'http://localhost:5173/', { waitUntil: 'networkidle' })
  await wait(1500)
  const runOnce = async (beforeRun, hold) => {
    await page.getByRole('button', { name: /Random stops/ }).click()
    await wait(beforeRun)
    await page.getByRole('button', { name: /^Run$/ }).click()
    await page.waitForResponse((r) => r.url().includes('/api/run'), { timeout: 120000 })
    await wait(hold)
  }
  await runOnce(7200, 15000) // long hold: narration explains the ranked results here
  await page.getByRole('radio', { name: 'Other regions' }).click()
  await wait(1500)
  await runOnce(2200, 8000)
})
await browser.close()
