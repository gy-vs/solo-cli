// 单题详情页的加载与响应性检查：跑完的题事件量可能很大，这里量渲染耗时与主线程是否还活着。
// 用法：node scripts/probe-task.mjs <taskId> [baseUrl]
import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import puppeteer from 'puppeteer-core'

const ID = process.argv[2] || '4'
const BASE = process.argv[3] || 'http://localhost:8788'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const profile = mkdtempSync(join(tmpdir(), 'solo-probe-'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--remote-debugging-port=9223', `--user-data-dir=${profile}`, '--window-size=1440,1000',
], { stdio: ['ignore', 'ignore', 'pipe'] })

let ws = ''
await new Promise((resolve, reject) => {
  const t = setTimeout(() => reject(new Error('chrome 启动超时')), 20000)
  chrome.stderr.on('data', (b) => {
    const m = String(b).match(/ws:\/\/[^\s]+/)
    if (m && !ws) { ws = m[0]; clearTimeout(t); resolve() }
  })
})

const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: { width: 1440, height: 1000 } })
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))

const t0 = Date.now()
await page.goto(`${BASE}/tasks/${ID}`, { waitUntil: 'domcontentloaded', timeout: 60000 })
await sleep(3000)

// 主线程还能响应就说明没被渲染卡死
const ping0 = Date.now()
const title = await page.evaluate(() => document.querySelector('header .text-fg0')?.textContent?.trim() || '')
const responseMs = Date.now() - ping0
const body = await page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | '))
// Timeline 的每条事件是一个 .animate-slidein 块
const timelineRows = await page.evaluate(() => document.querySelectorAll('.animate-slidein').length)

console.log(`加载+渲染 ${Date.now() - t0}ms · evaluate 往返 ${responseMs}ms`)
console.log(`标题: ${title}`)
console.log(`事件流提示: ${(body.match(/共 \d+ 条事件[^|]*/) || ['(未截断)'])[0]}`)
console.log(`时间线行数: ${timelineRows}`)

// 质检结论在「质检」页签里，要点开才在 DOM 上
const hasQcTab = await page.evaluate(() => {
  const tab = [...document.querySelectorAll('button, [role=tab]')].find((e) => e.textContent.trim().startsWith('质检'))
  if (tab) tab.click()
  return !!tab
})
await sleep(600)
const qcText = await page.evaluate(() => document.body.innerText)
console.log(`质检页签: ${hasQcTab ? (/质检通过|质检打回|建议废弃|信息不全|尚未质检/.test(qcText) ? '有结论' : '无结论文本') : '(无)'}`)
console.log(`页面报错: ${errors.length ? errors.join(' / ') : '(无)'}`)
await page.screenshot({ path: `/tmp/solo-shots/task-${ID}.png`, fullPage: false })

await browser.close()
chrome.kill()
