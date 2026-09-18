<script setup lang="ts">
/** 容器终端。两个视图，看的是同一个容器的两面：
 *
 * 「终端」是真终端 —— 后端 `docker exec -it` 开一个伪终端接到 xterm 上，能敲命令。
 * 想知道模型此刻把工作区改成了什么样，只有进去 git status 亲眼看一遍才算数：那份账
 * 要等收尾才记得上，跑着的时候界面上并不存在。
 *
 * 「日志」是 `docker logs -f` 的原样回放，只能看。跟事件流的分工在于，事件流是解析、
 * 过滤、落库之后的结果，噪声事件被丢掉了，采集一断就什么都没有；日志是容器此刻真正
 * 往外写的每一行，采集断了它照样有 —— 判断「还在不在动」只能看这个。
 */
import { NButton, NDrawer, NDrawerContent, NSwitch, useMessage } from 'naive-ui'
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { api, SIDES, type Side } from '../api'
import { HEX, SIDE_HEX } from '../status'
import { nowMs } from '../store'
import ContainerShell from './ContainerShell.vue'

const show = defineModel<boolean>('show', { default: false })
const side = defineModel<Side>('side', { default: 'A' })
const props = defineProps<{ taskId: number; taskNo: string }>()
const msg = useMessage()

type Mode = 'shell' | 'logs'
const MODES: { k: Mode; label: string }[] = [{ k: 'shell', label: '终端' }, { k: 'logs', label: '日志' }]
/** 默认进真终端：点开这个抽屉多半是想动手查现场，只看输出的话事件流已经在页面上了 */
const mode = ref<Mode>('shell')
const shellState = ref({ connected: false, message: '' })

const MAX_LINES = 2000
/** 一行日志连着它显示成什么样。
 *
 * 格式化结果跟着行一起存下来，是这块面板最要命的一处：从前它是个 computed，凡有新行
 * 进来就把在场的两千行重新解析一遍 JSON —— 行数涨上去以后，容器每写一行，浏览器要
 * 白干两千次解析。所以「刚打开还流畅，看一会儿就越来越卡」。现在每行只在进来时算一次。
 */
type Line = { n: number; raw: string; text: string; color: string }
/** shallow：这些行只整体换，不改单条，没必要为两千个对象各建一层代理 */
const lines = shallowRef<Line[]>([])
const container = ref('')
const state = ref('')
const connected = ref(false)
const closed = ref('')
const pretty = ref(true)
const follow = ref(true)
const thinking = ref(0)
const thinkingAt = ref(0)
const body = ref<HTMLElement | null>(null)
let es: EventSource | null = null
let seq = 0

function close() {
  es?.close()
  es = null
  connected.value = false
}
/** 问一句这一侧的容器叫什么、还在不在。两个视图都要：容器名是人进本机终端时的凭据，
 *  而容器跑完推完产物就自动销毁了，不先问一句，界面上只会换回一个没头没尾的
 *  「连接断开」，人分不清是自己网断了还是容器早没了。 */
async function probe(): Promise<boolean> {
  try {
    const c = (await api.containers(props.taskId)).items.find((x) => x.side === side.value)
    container.value = c?.name || ''
    state.value = c?.status || ''
    return !c || c.exists
  } catch {
    return true  // 探不到就照常连，让流自己去报错
  }
}

async function open() {
  close()
  clearLines()
  seq = 0
  thinking.value = 0
  thinkingAt.value = 0
  closed.value = ''
  if (!(await probe())) {
    closed.value = `容器 ${container.value} 已销毁（两侧跑完推完产物后会自动销毁），没有实时日志；完整过程看轨迹 jsonl`
    return
  }
  es = new EventSource(api.containerLogUrl(props.taskId, side.value))
  es.onopen = () => { connected.value = true }
  es.onmessage = (e) => {
    let d: any
    try { d = JSON.parse(e.data) } catch { return }
    if (d.type === 'hello') {
      container.value = d.container
      state.value = d.state
    } else if (d.type === 'line') {
      push(d.text)
    } else if (d.type === 'eof' || d.type === 'error') {
      closed.value = d.message || '流已结束'
      close()
    }
  }
  es.onerror = () => {
    connected.value = false
    // 容器销毁后后端会返回 404，重连只会一直失败，交给人点「重连」
    closed.value = closed.value || '连接断开'
    close()
  }
}
/** 思考 token 每个都发一条，几万条挤进列表只会把浏览器拖死。
 *
 * 但也不能干脆丢掉：模型思考起来能好几分钟不出别的声音，那段时间里这些行是唯一的
 * 动静，全过滤掉终端就是一片空白，看着跟卡死了一样。所以折成末尾一行原地刷新。
 */
function push(text: string) {
  const m = /"subtype":"thinking_tokens".*?"estimated_tokens":(\d+)/.exec(text)
  if (m) {
    thinking.value = Number(m[1])
    thinkingAt.value = Date.now()
    if (follow.value) nextTick(scrollToEnd)
    return
  }
  pending.push({ n: ++seq, raw: text, ...fmt(text) })
  if (flushTimer === null) flushTimer = window.setTimeout(flushLines, 120)
}
/** 攒一小会儿再一起铺上去。容器一忙起来一秒能写几十行，一行一次重排的话滚都滚不动 */
let pending: Line[] = []
let flushTimer: number | null = null
function flushLines() {
  flushTimer = null
  if (!pending.length) return
  const next = lines.value.concat(pending)
  pending = []
  lines.value = next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
  if (follow.value) nextTick(scrollToEnd)
}
function clearLines() {
  pending = []
  if (flushTimer !== null) { clearTimeout(flushTimer); flushTimer = null }
  lines.value = []
}
onBeforeUnmount(() => { if (flushTimer !== null) clearTimeout(flushTimer) })
function scrollToEnd() {
  const el = body.value
  if (el) el.scrollTop = el.scrollHeight
}
/** 人往上翻就自动松开跟随，翻回底部再自动跟上 */
function onScroll() {
  const el = body.value
  if (!el) return
  follow.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

/** 日志流只在真看着它的时候连。开着终端还在后台挂一条 `docker logs -f`，白占一条
 *  SSE 和一个读日志的子进程，而那些行谁都没在看。 */
watch([show, side, mode], () => {
  if (show.value && mode.value === 'logs') open()
  else {
    close()
    if (show.value) probe()
  }
})

/** 压成一行。工具结果动辄几百行文本，原样铺开一条就占半屏，翻都翻不动 */
const oneLine = (s: string, n = 500) => s.replace(/\s+/g, ' ').trim().slice(0, n)

/** 精简视图：把一行 stream-json 折成人能扫的一句。原始视图直接给 JSON 原文 */
function fmt(raw: string): { text: string; color: string } {
  if (!pretty.value) return { text: raw, color: HEX.fg1 }
  const r = summarize(raw)
  return { text: oneLine(r.text), color: r.color }
}

/** 读整份文件那种行会超过后端的单行上限，截断后 JSON 就解析不出来了。
 *  这时靠正则从残缺的前半段里抠出「谁干了什么」，总比贴一段断掉的 JSON 好认。 */
function rough(raw: string): { text: string; color: string } {
  const type = /"type":"(\w+)"/.exec(raw)?.[1] || ''
  const tool = /"name":"(\w+)"/.exec(raw)?.[1]
  const target = /"(?:file_path|command|pattern)":"([^"]{0,160})/.exec(raw)?.[1]
  const body = /"(?:text|content)":"([^"]{0,200})/.exec(raw)?.[1]
  const isErr = raw.includes('"is_error":true')
  if (type === 'assistant' && tool) return { text: `▸ ${tool} ${target || ''}（超长，已截断）`, color: HEX.fg0 }
  if (type === 'user') {
    return { text: `${isErr ? '✕ 工具报错' : '✓ 工具结果'} ${body || ''}（超长，已截断）`, color: isErr ? HEX.err : HEX.fg1 }
  }
  return { text: `· ${type || '未知行'} ${body || raw.slice(0, 200)}（超长，已截断）`, color: HEX.fg2 }
}

function summarize(raw: string): { text: string; color: string } {
  let o: any
  try {
    o = JSON.parse(raw)
  } catch {
    return rough(raw)
  }
  const t = o?.type
  if (t === 'system') {
    if (o.subtype === 'init') return { text: `● 会话初始化 · model=${o.model || ''} · cwd=${o.cwd || ''}`, color: HEX.accent }
    if (o.subtype === 'api_retry') {
      return { text: `⟳ API 重试 ${o.attempt}/${o.max_retries} · HTTP ${o.error_status} ${o.error || ''}`, color: HEX.warn }
    }
    return { text: `● system/${o.subtype || ''}`, color: HEX.fg2 }
  }
  if (t === 'assistant') {
    const parts: string[] = []
    for (const b of o.message?.content || []) {
      if (b?.type === 'tool_use') {
        const i = b.input || {}
        parts.push(`▸ ${b.name} ${String(i.file_path || i.command || i.pattern || '').slice(0, 200)}`.trim())
      } else if (b?.type === 'text' && String(b.text || '').trim()) {
        parts.push(String(b.text).trim().slice(0, 400))
      } else if (b?.type === 'thinking') {
        parts.push(`… ${String(b.thinking || '').trim().slice(0, 200)}`)
      }
    }
    return { text: parts.join(' | ') || '(assistant)', color: HEX.fg0 }
  }
  if (t === 'user') {
    for (const b of o.message?.content || []) {
      if (b?.type === 'tool_result') {
        const c = b.content
        const txt = typeof c === 'string' ? c : Array.isArray(c) ? c.map((x: any) => x?.text || '').join(' ') : ''
        return { text: `${b.is_error ? '✕ 工具报错' : '✓ 工具结果'} ${txt.slice(0, 300)}`, color: b.is_error ? HEX.err : HEX.fg1 }
      }
    }
    return { text: '(user)', color: HEX.fg1 }
  }
  if (t === 'result') {
    return {
      text: `■ 结束 · ${o.subtype} · turns=${o.num_turns} · ${Math.round((o.duration_ms || 0) / 1000)}s · cost=$${(o.total_cost_usd || 0).toFixed(2)}`,
      color: o.is_error ? HEX.err : HEX.ok,
    }
  }
  return { text: raw, color: HEX.fg2 }
}

/** 切精简/原始只是换个看法，这时才需要把在场的行重算一遍 */
watch(pretty, () => {
  lines.value = lines.value.map((l) => ({ n: l.n, raw: l.raw, ...fmt(l.raw) }))
})

/** 思考那一行离现在多久，用来确认它是在涨还是停了 */
const thinkingAgo = computed(() => {
  if (!thinkingAt.value) return ''
  const s = Math.max(0, Math.round((nowMs.value - thinkingAt.value) / 1000))
  return s < 2 ? '刚刚' : `${s}s 前`
})

/** 状态条。两个视图各有各的连接，显示的永远是眼下在看的那一个 */
const live = computed(() => (mode.value === 'shell' ? shellState.value.connected : connected.value))
const liveText = computed(() => {
  if (mode.value === 'shell') return shellState.value.connected ? '已进入容器' : shellState.value.message || '未连接'
  return connected.value ? '实时跟随' : closed.value || '未连接'
})

const cmds = computed(() => [
  `docker logs -f --tail 100 ${container.value || '-'}`,
  `docker exec -it ${container.value || '-'} bash`,
])
function copy(text: string) { navigator.clipboard?.writeText(text); msg.success('已复制，粘到本机终端里跑') }
</script>

<template>
  <NDrawer v-model:show="show" height="72vh" placement="bottom" :trap-focus="false" :block-scroll="false">
    <!-- 高度要一层层给到底：内部那块日志区靠 h-full 撑满，中间任何一层没有高度它就塌成一行 -->
    <NDrawerContent body-style="padding:0;height:100%;overflow:hidden"
      body-content-style="padding:0;height:100%">
      <template #header>
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-sm font-medium text-fg0">容器终端</span>
          <span class="mono text-xs px-2 h-6 inline-flex items-center rounded-md bg-bg3 border border-line">#{{ taskNo }}</span>
          <div class="flex rounded-md border border-line overflow-hidden">
            <button v-for="m in MODES" :key="m.k" class="px-2.5 h-6 text-[12px] transition-colors"
              :class="mode === m.k ? 'bg-bg3 text-fg0 font-medium' : 'text-fg2 hover:text-fg0'"
              @click="mode = m.k">{{ m.label }}</button>
          </div>
          <div class="flex gap-1">
            <button v-for="s in SIDES" :key="s" class="w-7 h-6 rounded-md mono text-[12px] border transition-colors"
              :class="side === s ? 'text-white font-semibold border-transparent' : 'border-line text-fg1 hover:text-fg0'"
              :style="side === s ? { background: SIDE_HEX[s] } : {}" @click="side = s">{{ s }}</button>
          </div>
          <span class="mono text-[12px] text-fg2">{{ container || '—' }}</span>
          <span class="pill h-6 text-[12px]" :class="live ? 'text-run border-run/50' : 'text-fg2 border-line'">
            <span class="dot" :class="live ? 'bg-run animate-breathe' : 'bg-fg2'" />
            {{ liveText }}
          </span>
          <span v-if="mode === 'logs' && thinking" class="mono text-[12px] text-run">思考 {{ thinking }} tokens</span>
          <div v-if="mode === 'logs'" class="ml-auto flex items-center gap-2">
            <NSwitch v-model:value="pretty" size="small" /><span class="text-[12px] text-fg1">精简</span>
            <NSwitch v-model:value="follow" size="small" @update:value="(v: boolean) => v && scrollToEnd()" />
            <span class="text-[12px] text-fg1">跟随</span>
            <NButton size="tiny" tertiary @click="clearLines">清屏</NButton>
            <NButton size="tiny" secondary :disabled="connected" @click="open">重连</NButton>
          </div>
          <div v-else class="ml-auto flex items-center gap-2">
            <!-- 想在自己的终端里开一个（多开几个窗口、跑长命令）时照样拿得到凭据 -->
            <NButton size="tiny" tertiary :disabled="!container" @click="copy(cmds[1])">
              复制 docker exec 命令
            </NButton>
          </div>
        </div>
      </template>
      <!-- 换侧要换容器，终端得重开一个；key 变了让组件整个重建，省得自己去管拆连接 -->
      <ContainerShell v-if="mode === 'shell'" :key="`${taskId}-${side}`" :task-id="taskId" :side="side"
        @state="shellState = $event" />
      <div v-else class="h-full flex flex-col bg-[#0B1220]">
        <div ref="body" class="flex-1 min-h-0 overflow-auto px-4 py-3 font-mono text-[12px] leading-5"
          @scroll="onScroll">
          <div v-if="!lines.length" class="text-[#64748B]">
            {{ connected ? '已连上容器，等下一行输出…' : closed || '正在连接容器日志…' }}
          </div>
          <div v-for="l in lines" :key="l.n" class="flex gap-3 break-all"
            :class="pretty ? 'truncate' : 'whitespace-pre-wrap'">
            <span class="text-[#334155] select-none shrink-0 nums">{{ String(l.n).padStart(5, '0') }}</span>
            <span :class="pretty ? 'truncate' : ''" :title="l.text"
              :style="{ color: l.color === HEX.fg0 ? '#E2E8F0' : l.color === HEX.fg1 ? '#94A3B8' : l.color }">{{ l.text }}</span>
          </div>
          <!-- 思考期间容器只刷这一种行，折成一行原地更新，不然终端看着像卡死了 -->
          <div v-if="thinking" class="flex gap-3">
            <span class="text-[#334155] select-none shrink-0">·····</span>
            <span class="text-[#D97706]">… 思考中 · {{ thinking }} tokens · {{ thinkingAgo }}</span>
          </div>
        </div>
        <div class="shrink-0 px-4 py-2 border-t border-[#1E293B] flex items-center gap-3 flex-wrap">
          <span class="mono text-[11px] text-[#64748B]">{{ lines.length }} 行（最多留 {{ MAX_LINES }}）· 容器状态 {{ state || '—' }}</span>
          <div class="ml-auto flex items-center gap-2">
            <button v-for="c in cmds" :key="c" class="mono text-[11px] text-[#94A3B8] hover:text-white px-2 py-1 rounded border border-[#1E293B]"
              :title="'点击复制：' + c" @click="copy(c)">{{ c.startsWith('docker logs') ? '复制 docker logs 命令' : '复制 docker exec 命令' }}</button>
          </div>
        </div>
      </div>
    </NDrawerContent>
  </NDrawer>
</template>
