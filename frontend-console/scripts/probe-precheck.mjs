// 提交前质检的界面冒烟：列表页的质检栏、详情页的质检页签、人工确认区。
// 用法：node scripts/probe-precheck.mjs <有质检结论的 taskId> [baseUrl]
import { spawn } from 'node:child_process'
import { mkdirSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import puppeteer from 'puppeteer-core'

const ID = process.argv[2] || '206'
const BASE = process.argv[3] || 'http://localhost:8788'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const SHOTS = '/tmp/solo-shots'
mkdirSync(SHOTS, { recursive: true })
const profile = mkdtempSync(join(tmpdir(), 'solo-precheck-'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--remote-debugging-port=9224', `--user-data-dir=${profile}`, '--window-size=1560,1200',
], { stdio: ['ignore', 'ignore', 'pipe'] })

let ws = ''
await new Promise((resolve, reject) => {
  const t = setTimeout(() => reject(new Error('chrome 启动超时')), 20000)
  chrome.stderr.on('data', (b) => {
    const m = String(b).match(/ws:\/\/[^\s]+/)
    if (m && !ws) { ws = m[0]; clearTimeout(t); resolve() }
  })
})

const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: { width: 1560, height: 1200 } })
const page = await browser.newPage()
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(`[console] ${m.text()}`) })
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`))

const out = []
const check = (name, ok, extra = '') => out.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? ' · ' + extra : ''}`)
const body = () => page.evaluate(() => document.body.innerText)
const clickTab = (prefix) => page.evaluate((p) => {
  const el = [...document.querySelectorAll('button')].find((e) => e.textContent.trim().startsWith(p))
  if (el) el.click()
  return !!el
}, prefix)

// ---------------- 列表页 ----------------
await page.goto(`${BASE}/list`, { waitUntil: 'networkidle2' })
await sleep(1200)
const hasQcTab = await clickTab('质检')
check('列表页有「质检」栏', hasQcTab)
await sleep(900)
const listText = await body()
check('质检栏说清了发起方式只在对话里', /app\.cli precheck/.test(listText))
check('质检栏表头换成了质检列', /提交前质检/.test(listText))
await page.screenshot({ path: `${SHOTS}/precheck-list.png` })

// ---------------- 详情页 ----------------
await page.goto(`${BASE}/tasks/${ID}`, { waitUntil: 'networkidle2' })
await sleep(1500)
const hasPanelTab = await clickTab('提交前质检')
check('详情页有「提交前质检」页签', hasPanelTab)
await sleep(900)
const detail = await body()
check('挑出的问题带类别标签', /冒号夹注|转述材料|句子生硬|随口俚语|动作化动词|拟人化评价/.test(detail))
check('每处给了原句和改法', /改成：/.test(detail))
check('给了整段改写建议并能填进理由', /整段改写建议/.test(detail) && /填进理由/.test(detail))
check('有人工确认区', /人工确认/.test(detail))
const confirmEnabled = await page.evaluate(() => {
  const b = [...document.querySelectorAll('button')].find((e) => /确认放行|重新确认/.test(e.textContent))
  return b ? !b.disabled : null
})
check('确认按钮可点', confirmEnabled === true, `disabled=${confirmEnabled === null ? '按钮没找到' : !confirmEnabled}`)
await page.screenshot({ path: `${SHOTS}/precheck-panel.png`, fullPage: true })

// 没跑过质检的题要告诉人命令怎么敲，而不是给一个不存在的按钮
await page.goto(`${BASE}/tasks/208`, { waitUntil: 'networkidle2' })
await sleep(1500)
await clickTab('提交前质检')
await sleep(700)
const idle = await body()
check('没质检过的题给出命令而不是按钮', /python -m app\.cli precheck/.test(idle))
await page.screenshot({ path: `${SHOTS}/precheck-idle.png` })

console.log(out.join('\n'))
console.log(`\n页面报错：${errors.length ? errors.join(' / ') : '(无)'}`)
console.log(`截图：${SHOTS}/precheck-list.png, precheck-panel.png, precheck-idle.png`)

await browser.close()
chrome.kill()
