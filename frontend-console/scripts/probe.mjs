// 交互冒烟：题库 → 详情 → 废弃 → 已废弃 tab → 恢复。
// 用法：node scripts/probe.mjs [baseUrl]
import { spawn } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import puppeteer from 'puppeteer-core'

const BASE = process.argv[2] || 'http://localhost:8788'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const profile = mkdtempSync(join(tmpdir(), 'solo-probe-'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--remote-debugging-port=9222', `--user-data-dir=${profile}`, '--window-size=1440,1000',
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
const logs = []
page.on('console', (m) => { if (m.type() === 'error') logs.push(`[console] ${m.text()}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))

const click = (text) => page.evaluate((t) => {
  const el = [...document.querySelectorAll('button, a')].find((e) => e.textContent.trim().startsWith(t))
  if (!el) return false
  el.click()
  return true
}, text)
/** 状态 tab：只点 tab 那排按钮，不能用文本前缀匹配（「全部」会撞上「全部领取并启动」） */
const tab = (label) => page.evaluate((t) => {
  const el = [...document.querySelectorAll('button')]
    .filter((e) => e.className.includes('rounded-inner'))
    .find((e) => e.textContent.trim().startsWith(t))
  if (!el) return false
  el.click()
  return true
}, label)
const tabLabels = () => page.evaluate(() => [...document.querySelectorAll('button')]
  .filter((e) => e.className.includes('rounded-inner'))
  .map((e) => e.textContent.trim().replace(/\s+/g, '')))
/** 侧边栏导航：链接文本带图标前缀，不能用 startsWith 匹配 */
const nav = (label) => page.evaluate((t) => {
  const el = [...document.querySelectorAll('aside a')].find((e) => e.textContent.includes(t))
  if (!el) return false
  el.click()
  return true
}, label)
const text = () => page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | '))
const has = async (s) => (await text()).includes(s)

const results = []
const check = (name, ok, extra = '') => { results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? ' · ' + extra : ''}`) }

const cardCount = () => page.evaluate(() => document.querySelectorAll('.card.card-hover').length)

// 1. 题库 → 详情
await page.goto(`${BASE}/bank`, { waitUntil: 'domcontentloaded' })
await sleep(1000)
check('题库渲染题卡', await has('领取并启动'))
const cardsBefore = await cardCount()
await click('详情')
await sleep(1500)
check('详情路由跳转', page.url().includes('/tasks/'), page.url())
check('详情页显示提交参数', await has('提交参数'))
check('详情页显示运行前检查', await has('运行前检查'))
check('详情页有废弃按钮', await has('废弃'))
await page.screenshot({ path: '/tmp/solo-shots/probe-detail.png' })

// 2. 门禁检查
await click('执行门禁检查')
await sleep(6000)
check('门禁结果渲染', (await has('通过')) || (await has('阻断')))
await page.screenshot({ path: '/tmp/solo-shots/probe-gate.png' })

// 3. 废弃
await click('废弃')
await sleep(600)
await click('确认废弃')
await sleep(1500)
check('废弃后状态更新', await has('已废弃'))
await page.screenshot({ path: '/tmp/solo-shots/probe-discarded.png' })

// 4. 题库默认不显示废弃题
await page.goto(`${BASE}/bank`, { waitUntil: 'domcontentloaded' })
await sleep(1200)
const cardsAfter = await cardCount()
check('题库隐藏废弃题', cardsAfter === cardsBefore - 1, `废弃前 ${cardsBefore} 张，废弃后 ${cardsAfter} 张`)
await tab('已废弃')
await sleep(600)
check('已废弃 tab 显示该题', await has('恢复'))
await page.screenshot({ path: '/tmp/solo-shots/probe-bank-discarded.png' })

// 5. 恢复
await click('恢复')
await sleep(1500)
await tab('待领取')
await sleep(600)
check('恢复后回到待领取', await has('领取并启动'))

// 5b. 按状态分的 tab：点过领取但没跑的题得有地方能看到
const labels = await tabLabels()
check('题库有全部状态 tab', labels.length >= 8, `${labels.length} 个：${labels.join(' ')}`)
const countResetBtns = () => page.evaluate(() =>
  [...document.querySelectorAll('.card.card-hover')].filter((c) => c.innerText.includes('还原')).length)

await tab('全部')
await sleep(700)
const allCards = await cardCount()
check('全部 tab 覆盖各状态', allCards >= cardsAfter, `${allCards} 张`)
// 跑过或动过的题才给还原按钮
check('跑过的题卡有还原按钮', (await countResetBtns()) > 0, `${await countResetBtns()} 张卡可还原`)

await tab('已领取未跑')
await sleep(700)
check('已领取未跑的题不再消失', (await cardCount()) > 0, `${await cardCount()} 张`)

await tab('待领取')
await sleep(700)
check('待领取的题不给还原按钮', (await countResetBtns()) === 0)

// 5c. 共用项目标注：同一个仓库的题不能同时跑，列表得点名
await tab('全部')
await sleep(700)
check('题库汇总共用项目', await has('共用同一个项目的题'))
check('题卡点名同项目的题', await has('共用项目'))

// 6. 队列管理台（走侧边栏，整页重载会等上设置页的模型探测）
check('侧边栏有队列入口', await nav('队列'))
await sleep(1200)
check('队列页渲染', await has('并发上限'))
check('队列页有自动流水线区', await has('自动流水线'))
check('队列页说明自动补位', await has('自动补位'))
check('队列页说明一项目一并发', await has('一个项目同时只跑一道题'))
await page.screenshot({ path: '/tmp/solo-shots/probe-queue.png' })

// 7. 设计题目
check('侧边栏有设计入口', await nav('设计题目'))
await sleep(1500)
check('设计页渲染', await has('题目数量'))
check('设计页显示前置检查', (await has('Cursor CLI')) && (await has('查重通道')))
check('设计页有开始按钮', await has('开始设计'))
await page.screenshot({ path: '/tmp/solo-shots/probe-design.png' })

// 8. 设置页的新分组与开关
check('侧边栏有设置入口', await nav('设置'))
await sleep(2500)
check('设置页有自动流水线分组', await has('自动流水线'))
check('设置页有质检分组', await has('solo-qa 质检'))
check('设置页有出题分组', await has('题目设计'))
const switches = await page.evaluate(() => document.querySelectorAll('.n-switch').length)
check('开关型设置渲染成 Switch', switches >= 5, `${switches} 个`)
await page.screenshot({ path: '/tmp/solo-shots/probe-settings.png' })

console.log(results.join('\n'))
console.log('--- console errors ---')
console.log(logs.length ? logs.join('\n') : '(无)')

await browser.close()
chrome.kill()
