// Drives the real UI in headless Chrome and records the walkthrough (video + screenshots).
// Needs both servers running:  uv run qroute-server  (backend)  and  npm run dev  (frontend).
// Usage: node scripts/record-demo.mjs [--no-video]
import { chromium } from 'playwright-core'
import { mkdirSync, readdirSync, renameSync, rmSync } from 'node:fs'
import { join } from 'node:path'

const URL = process.env.DEMO_URL || 'http://localhost:5173/'
const OUT = new globalThis.URL('../../docs/media/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const VIDEO = !process.argv.includes('--no-video')
mkdirSync(OUT, { recursive: true })
for (const f of readdirSync(OUT)) if (f.endsWith('.webm')) rmSync(join(OUT, f))

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  ...(VIDEO ? { recordVideo: { dir: OUT, size: { width: 1600, height: 900 } } } : {}),
})
const page = await context.newPage()
const wait = (ms) => page.waitForTimeout(ms)
const shot = (name) => page.screenshot({ path: join(OUT, name) })
const add = async (name) => { await page.selectOption('select[aria-label="Add a Karachi place"]', name); await wait(700) }
const runAndWatch = async (snap) => {
  await page.getByRole('button', { name: /Plan route|Plan again/ }).click()
  await page.getByRole('button', { name: 'Replay', exact: true }).waitFor({ timeout: 60000 }) // results arrived
  await wait(3500); if (snap) await shot(snap + '_race.png')
  await wait(4000); if (snap) await shot(snap + '_orders.png')
  await page.getByRole('button', { name: 'Plan again', exact: true }).waitFor({ timeout: 30000 }) // playback finished
  await wait(1500); if (snap) await shot(snap + '_done.png')
}

await page.goto(URL, { waitUntil: 'networkidle' })
await wait(2000)
await shot('00_empty.png')

// 1) A -> B: depot at Saddar, one shelter
await add('Saddar')
await add('Gulshan')
await runAndWatch('01_a_to_b')

// 2) Multi-stop: add more shelters plus one point clicked straight on the map
await add('North Nazimabad')
await add('Malir')
await add('Jauhar')
const box = await page.locator('.race-map').first().boundingBox()
await page.mouse.click(box.x + box.width * 0.62, box.y + box.height * 0.22) // a point near Sohrab Goth
await wait(900)
await shot('02_multi_input.png')
await runAndWatch('03_multi')
await page.locator('.panel').evaluate((el) => el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }))
await wait(3000)
await shot('04_results.png')

await context.close()
await browser.close()
if (VIDEO) {
  const vid = readdirSync(OUT).find((f) => f.endsWith('.webm'))
  if (vid) renameSync(join(OUT, vid), join(OUT, 'demo.webm'))
}
console.log('saved to', OUT)
