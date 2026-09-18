<script setup lang="ts">
/** 容器 shell：xterm.js 接后端 `docker exec -it` 开的伪终端，是一个真终端。
 *
 * 跟同一个抽屉里的「日志」分工：日志是 `docker logs -f` 的只读回放，看得见模型在
 * 往外写什么，但问不了任何问题；这里能敲命令、有颜色和光标，vim、top、git log 这类
 * 认终端的程序都照常用。要确认模型此刻把工作区改成了什么样，只有进去 git status 亲眼
 * 看一遍才算数 —— 那份账要等收尾才记得上，跑着的时候界面上并不存在。
 */
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import type { Side } from '../api'

const props = defineProps<{ taskId: number; side: Side }>()
const emit = defineEmits<{ (e: 'state', v: { connected: boolean; message: string }): void }>()

const host = ref<HTMLElement | null>(null)
const term = shallowRef<Terminal | null>(null)
const fit = shallowRef<FitAddon | null>(null)
const closed = ref('')
const connected = ref(false)
let ws: WebSocket | null = null
let observer: ResizeObserver | null = null
/** 上一次报给后端的行列数。不去重的话，抽屉动画每一帧都会发一条 resize */
let reported = ''

function sync() {
  emit('state', { connected: connected.value, message: closed.value })
}

/** 终端是按字符网格排版的，尺寸必须两头一致：这边按容器像素算出行列数，
 *  再报给后端 ioctl 到容器的终端上，否则容器里的程序按旧宽度折行，满屏错位。 */
function resize() {
  if (!fit.value || !term.value || !host.value?.clientHeight) return
  fit.value.fit()
  const { rows, cols } = term.value
  const key = `${rows}x${cols}`
  if (key === reported) return
  reported = key
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'resize', rows, cols }))
}

function wsUrl(): string {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  const { rows = 30, cols = 100 } = term.value || {}
  return `${scheme}://${location.host}/api/tasks/${props.taskId}/container/exec`
    + `?side=${props.side}&rows=${rows}&cols=${cols}`
}

function connect() {
  const t = term.value
  if (!t) return
  closed.value = ''
  t.write('\x1b[2J\x1b[H\x1b[90m正在进入容器…\x1b[0m\r\n')
  ws = new WebSocket(wsUrl())
  ws.onopen = () => {
    connected.value = true
    sync()
    reported = ''
    resize()
  }
  ws.onmessage = (e) => {
    let d: any
    try { d = JSON.parse(e.data) } catch { return }
    if (d.type === 'stdout') {
      t.write(d.data)
    } else if (d.type === 'hello') {
      t.write(`\x1b[90m已进入 ${d.container}，工作目录 ${d.cwd}\x1b[0m\r\n`)
    } else if (d.type === 'exit') {
      closed.value = d.message || '终端已结束'
      t.write(`\r\n\x1b[33m${closed.value}\x1b[0m\r\n`)
    }
  }
  ws.onclose = () => {
    connected.value = false
    closed.value = closed.value || '连接已断开'
    sync()
  }
  ws.onerror = () => {
    // 具体原因后端会在 exit 消息里说明，这里只负责别让状态停在「正在进入」
    closed.value = closed.value || '连不上后端终端'
  }
}

function reconnect() {
  ws?.close()
  ws = null
  connect()
}

onMounted(() => {
  const t = new Terminal({
    fontSize: 12,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
    lineHeight: 1.25,
    cursorBlink: true,
    scrollback: 5000,
    // 容器里跑 git、vim 的输出都带 ANSI 颜色，配色跟日志面板保持一套
    theme: {
      background: '#0B1220', foreground: '#E2E8F0', cursor: '#D97706',
      selectionBackground: '#334155', black: '#0B1220', brightBlack: '#475569',
      red: '#E11D48', green: '#059669', yellow: '#D97706', blue: '#4F6BED',
      magenta: '#A855F7', cyan: '#0284C7', white: '#E2E8F0',
    },
  })
  const f = new FitAddon()
  t.loadAddon(f)
  t.open(host.value!)
  t.onData((d) => {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'stdin', data: d }))
  })
  term.value = t
  fit.value = f
  // 抽屉是带展开动画的，挂载这一刻容器高度还是 0，量出来会是 1 行 1 列。
  // 交给 ResizeObserver：动画每变一次尺寸它就来一次，定下来自然就对了。
  observer = new ResizeObserver(() => resize())
  observer.observe(host.value!)
  connect()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  ws?.close()
  ws = null
  term.value?.dispose()
})

defineExpose({ reconnect, focus: () => term.value?.focus() })
</script>

<template>
  <div class="h-full flex flex-col bg-[#0B1220]">
    <div ref="host" class="shell flex-1 min-h-0 px-3 py-2" />
    <div class="shrink-0 px-4 py-2 border-t border-[#1E293B] flex items-center gap-3 flex-wrap">
      <span class="mono text-[11px] text-[#64748B]">
        真终端 · docker exec -it · 工作目录 /workspace
      </span>
      <!-- 这是众测的现场：在跑着的容器里动手会连着改掉工作区和轨迹，得先说清楚 -->
      <span class="mono text-[11px] text-[#D97706]">
        题还在跑时请只读不写，改动会进产物
      </span>
      <div class="ml-auto flex items-center gap-2">
        <span v-if="closed" class="mono text-[11px] text-[#E11D48]">{{ closed }}</span>
        <button v-if="!connected"
          class="mono text-[11px] text-[#94A3B8] hover:text-white px-2 py-1 rounded border border-[#1E293B]"
          @click="reconnect">重新进入</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* xterm 自带的滚动条是浏览器默认样式，压在深色终端上是一道亮痕 */
.shell :deep(.xterm-viewport)::-webkit-scrollbar {
  width: 8px;
}
.shell :deep(.xterm-viewport)::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 4px;
}
.shell :deep(.xterm-viewport)::-webkit-scrollbar-track {
  background: transparent;
}
</style>
