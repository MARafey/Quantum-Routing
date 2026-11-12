// Records the "Country-scale disasters" tab: all three disaster cases, run one after another.
// Needs the frontend dev server running (npm run dev). Usage: node scripts/record-country.mjs
import { chromium } from 'playwright-core'
import { mkdirSync, readdirSync, renameSync, rmSync } from 'node:fs'
import { join } from 'node:path'

const URL = process.env.DEMO_URL || 'http://localhost:5173/'
const OUT = new globalThis.URL('../../docs/media/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const TMP = join(OUT, '_rec')
mkdirSync(TMP, { recursive: true })

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, recordVideo: { dir: TMP, size: { width: 1600, height: 900 } } })
const page = await context.newPage()
const wait = (ms) => page.waitForTimeout(ms)
await page.goto(URL, { waitUntil: 'networkidle' })
await page.getByRole('button', { name: 'Country-scale disasters' }).click()
await wait(2000)
const rows = page.locator('[role="radio"]')
const names = ['country_sindh', 'country_pakistan_3hubs', 'country_turkiye_syria']
for (let i = 0; i < await rows.count(); i++) {
  await rows.nth(i).click()
  await wait(1800)
  await page.getByRole('button', { name: 'Run comparison' }).click()
  await wait(7500)
  await page.screenshot({ path: join(OUT, `${names[i]}.png`) })
  await page.locator('.country').first().evaluate(() => {
    const el = document.querySelector('.country aside, .country .panel, .country [class*="panel"]')
    el?.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  })
  await wait(2500)
  await page.locator('.country').first().evaluate(() => {
    const el = document.querySelector('.country aside, .country .panel, .country [class*="panel"]')
    el?.scrollTo({ top: 0, behavior: 'smooth' })
  })
  await wait(800)
}
await context.close()
await browser.close()
const vid = readdirSync(TMP).find((f) => f.endsWith('.webm'))
if (vid) renameSync(join(TMP, vid), join(OUT, 'country.webm'))
rmSync(TMP, { recursive: true, force: true })
console.log('saved to', OUT)
