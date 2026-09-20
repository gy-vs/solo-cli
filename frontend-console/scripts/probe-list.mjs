// 题目列表页冒烟：五个状态栏各渲染什么、A/B 用时与步数在不在、批量勾选与分页通不通。
// 用法：node scripts/probe-list.mjs [baseUrl]
import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import puppeteer from 'puppeteer-core'

const BASE = process.argv[2] || 'http://localhost:5173'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const SHOTS = '/tmp/solo-shots'
const profile = mkdtempSync(join(tmpdir(), 'solo-list-'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--remote-debugging-port=9223', `--user-data-dir=${profile}`, '--window-size=1560,1100',
], { stdio: ['ignore', 'ignore', 'pipe'] })

let ws = ''
await new Promise((resolve, reject) => {
  const t = setTimeout(() => reject(new Error('chrome 启动超时')), 20000)
  chrome.stderr.on('data', (b) => {
    const m = String(b).match(/ws:\/\/[^\s]+/)
    if (m && !ws) { ws = m[0]; clearTimeout(t); resolve() }
  })
})

const browser = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: { width: 1560, height: 1100 } })
const page = await browser.newPage()
const logs = []
page.on('console', (m) => { if (m.type() === 'error') logs.push(`[console] ${m.text()}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))

const results = []
const check = (name, ok, extra = '') => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? ' · ' + extra : ''}`)
const text = () => page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | '))
const has = async (s) => (await text()).includes(s)
/** 状态栏按钮：只认 tab 那排 */
const tab = (label) => page.evaluate((t) => {
  const el = [...document.querySelectorAll('button')]
    .filter((e) => e.className.includes('rounded-inner'))
    .find((e) => e.textContent.trim().startsWith(t))
  if (!el) return false
  el.click()
  return true
}, label)
const click = (t) => page.evaluate((s) => {
  const el = [...document.querySelectorAll('button')].find((e) => e.textContent.trim().startsWith(s))
  if (!el) return false
  el.click()
  return true
}, t)
/** 列表行数：表头与分页条不算 */
const rowCount = () => page.evaluate(() => document.querySelectorAll('.card > .grid.items-center').length - 1)
/** 每行的操作按钮文字，用来核对「每个状态该有哪些动作」 */
const rowActions = () => page.evaluate(() => {
  const rows = [...document.querySelectorAll('.card > .grid.items-center')].slice(1)
  return rows.slice(0, 3).map((r) => [...r.querySelectorAll('button')].map((b) => b.textContent.trim()).join('/'))
})
/** A/B 那一列的原文，核对用时与步数都落到了行上 */
const sideCells = () => page.evaluate(() => {
  const rows = [...document.querySelectorAll('.card > .grid.items-center')].slice(1)
  return rows.slice(0, 3).map((r) => (r.children[r.children.length - 3]?.innerText || '').replace(/\n/g, ' ／ '))
})

await page.goto(`${BASE}/list`, { waitUntil: 'domcontentloaded' })
await sleep(2500)

// 1. 导航与默认栏
check('侧边栏有题目列表入口', await page.evaluate(() =>
  [...document.querySelectorAll('aside a')].some((a) => a.textContent.includes('题目列表'))))
check('默认停在运行中栏', await has('运行中'))
check('表头点出用时与步数列', await has('A / B 用时 · 工具步数'))
check('运行中栏有行', (await rowCount()) > 0, `${await rowCount()} 行`)
check('运行中栏有停止与废弃', (await rowActions()).every((a) => a.includes('废弃')), (await rowActions()).join(' | '))
await page.screenshot({ path: `${SHOTS}/list-running.png` })

// 2. 失败栏：单条重跑 + 批量
check('切到失败栏', await tab('失败'))
await sleep(800)
check('失败栏有行', (await rowCount()) > 0, `${await rowCount()} 行`)
const failedActions = await rowActions()
check('失败栏给出重跑按钮', failedActions.some((a) => a.includes('重跑')), failedActions.join(' | '))
check('失败栏每行都有废弃', failedActions.every((a) => a.includes('废弃')))
check('失败栏显示转人工的原因', (await has('重跑次数已用尽')) || (await has('人工停止')) || (await has('推产物失败')))
check('失败栏的行带 A/B 用时与步数', (await sideCells()).every((c) => c.includes('步')), (await sideCells())[0])
await page.screenshot({ path: `${SHOTS}/list-failed.png` })

// 勾选：先勾本页全部，再看批量条
await page.evaluate(() => document.querySelectorAll('.n-checkbox')[0]?.click())
await sleep(500)
check('勾选表头选中本页', await has('已选'))
check('批量条给出批量重跑', await has('批量重跑'))
await page.screenshot({ path: `${SHOTS}/list-failed-picked.png` })
await click('清空选择')
await sleep(400)
check('清空选择后批量条收起', !(await has('已选')))

// 3. 待分析栏：单条分析 + 批量 + 一键全选
check('切到待分析栏', await tab('待分析'))
await sleep(800)
const pendingActions = await rowActions()
check('待分析栏有分析产物并提交', pendingActions.some((a) => a.includes('分析产物并提交')), pendingActions.join(' | '))
check('待分析栏每行都有废弃', pendingActions.every((a) => a.includes('废弃')))
check('待分析栏的行带 A/B 用时与步数', (await sideCells()).every((c) => c.includes('步')), (await sideCells())[0])
await page.evaluate(() => document.querySelectorAll('.n-checkbox')[1]?.click())
await sleep(500)
check('待分析栏可勾选单条', await has('已选'))
check('批量条给出批量分析', await has('批量分析并提交产物'))
await page.screenshot({ path: `${SHOTS}/list-pending.png` })

// 4. 待录屏栏
check('切到待录屏栏', await tab('待录屏'))
await sleep(800)
const shotActions = await rowActions()
check('待录屏栏有启动/录屏与提交', shotActions.some((a) => a.includes('启动 / 录屏') && a.includes('提交')), shotActions.join(' | '))
check('待录屏栏每行都有废弃', shotActions.every((a) => a.includes('废弃')))
check('待录屏栏说明缺哪侧录屏', (await has('侧录屏')) || (await has('可提交')))
await page.screenshot({ path: `${SHOTS}/list-screencast.png` })

// 5. 已提交栏
check('切到已提交栏', await tab('已提交'))
await sleep(800)
check('已提交栏有行', (await rowCount()) > 0, `${await rowCount()} 行`)
check('已提交栏每行都有废弃', (await rowActions()).every((a) => a.includes('废弃')), (await rowActions()).join(' | '))
check('已提交栏显示提交号', await has('已提交 #'))
await page.screenshot({ path: `${SHOTS}/list-submitted.png` })

// 6. 废弃确认弹窗：已提交的题要额外说明平台那份不受影响
await click('废弃')
await sleep(700)
check('废弃有二次确认', await has('确认废弃'))
check('已提交的题点明平台那份不受影响', await has('solo2'))
await page.screenshot({ path: `${SHOTS}/list-discard-dialog.png` })
await click('取消')
await sleep(400)

console.log(results.join('\n'))
console.log('--- console errors ---')
console.log(logs.length ? logs.join('\n') : '(无)')

await browser.close()
chrome.kill()
