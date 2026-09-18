// 性能探测：数长连接、量空闲开销。
//
// 两个指标直接对应「窗口一多就越来越卡」：
//   1) 同时开着的 SSE 长连接数 —— 浏览器对同一个域只给六个，被长连接占满之后所有普通
//      请求都在排队，界面就没反应了。列表页 + 详情页 + 终端全开的情况下必须还有余量。
//   2) 空闲时每秒的样式重算与渲染耗时 —— 没有任何事件进来时，页面本该是静的。不静就说明
//      有东西在每秒把整个列表重画一遍。
//
// 用法：node scripts/probe-perf.mjs [baseUrl]
import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import puppeteer from 'puppeteer-core'

const BASE = process.argv[2] || 'http://localhost:8788'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const profile = mkdtempSync(join(tmpdir(), 'solo-perf-'))
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

// 页面自己数活着的 EventSource。比从外面看请求准：导航之后旧文档的连接是浏览器收走的，
// 外面不一定收到收尾事件，看着就像连接翻了倍。
await page.evaluateOnNewDocument(() => {
  window.__es = { opened: [], live: [] }
  const Orig = EventSource
  window.EventSource = function (...args) {
    const es = new Orig(...args)
    const url = String(args[0])
    window.__es.opened.push(url)
    window.__es.live.push(url)
    const close = es.close.bind(es)
    es.close = () => {
      const i = window.__es.live.indexOf(url)
      if (i >= 0) window.__es.live.splice(i, 1)
      close()
    }
    return es
  }
  window.EventSource.prototype = Orig.prototype
})
const inPage = () => page.evaluate(() => ({
  活着: [...window.__es.live].sort(),
  开过: window.__es.opened.length,
  可见性: document.visibilityState,
}))

/** 还没结束的 eventsource 请求就是此刻占着的长连接 */
const open = new Map()
page.on('request', (r) => {
  if (r.resourceType() === 'eventsource') open.set(r, r.url().replace(BASE, ''))
})
page.on('requestfinished', (r) => open.delete(r))
page.on('requestfailed', (r) => open.delete(r))
const streams = () => [...open.values()].sort()

/** 空闲一段时间里页面到底忙不忙 */
async function idleCost(seconds) {
  const a = await page.metrics()
  await sleep(seconds * 1000)
  const b = await page.metrics()
  return {
    样式重算: b.RecalcStyleCount - a.RecalcStyleCount,
    布局: b.LayoutCount - a.LayoutCount,
    脚本毫秒: Math.round((b.ScriptDuration - a.ScriptDuration) * 1000),
    渲染毫秒: Math.round((b.LayoutDuration + b.RecalcStyleDuration - a.LayoutDuration - a.RecalcStyleDuration) * 1000),
  }
}

const lines = []
const report = (label, extra) => lines.push(`${label}: ${JSON.stringify(extra, null, 0)}`)

// 1. 运行舱：列表页卡片最多的地方
await page.goto(`${BASE}/runs`, { waitUntil: 'domcontentloaded' })
await sleep(3000)
const cards = await page.evaluate(() => document.querySelectorAll('.card.card-hover').length)
report('运行舱', { 卡片数: cards, 连接: await inPage() })
report('运行舱空闲 10 秒', await idleCost(10))

// 2. 详情页：从前它会自己再开一条公共流
const id = await page.evaluate(async (base) => {
  const r = await fetch(`${base}/api/tasks?include_discarded=true`)
  const d = await r.json()
  const t = d.items.find((x) => x.runs?.length) || d.items[0]
  return t?.id
}, BASE)
await page.goto(`${BASE}/tasks/${id}`, { waitUntil: 'domcontentloaded' })
await sleep(3000)
report(`详情页 #${id}`, { 连接: await inPage() })
report('详情页空闲 10 秒', await idleCost(10))

// 3. 再把终端抽屉打开 —— 这是「窗口」开到最多的状态
const opened = await page.evaluate(() => {
  const b = [...document.querySelectorAll('button')].find((e) => e.textContent.trim() === '打开终端')
  if (!b) return false
  b.click()
  return true
})
await sleep(2500)
if (opened) {
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((e) => e.textContent.trim() === '日志')
    b?.click()
  })
  await sleep(2500)
}
report('详情页 + 终端日志', { 打开终端: opened, 连接: await inPage() })
report('全开着空闲 10 秒', await idleCost(10))

console.log(lines.join('\n'))
const last = await inPage()
console.log(`\n峰值同时长连接: ${last.活着.length} 条（浏览器同域上限 6）· 页面可见性 ${last.可见性}`)

await browser.close()
chrome.kill()
