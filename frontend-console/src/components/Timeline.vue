<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch } from 'vue'
import type { RunEvent } from '../api'
import { fmtTime, HEX } from '../status'

const props = defineProps<{ events: RunEvent[]; follow?: boolean; highlightStep?: number | null }>()
const open = shallowRef<Set<number>>(new Set())
const box = ref<HTMLElement | null>(null)
const filter = ref<'all' | 'tools' | 'text' | 'errors'>('all')

const KIND_COLOR: Record<string, string> = {
  assistant: HEX.accent, user: HEX.fg1, system: HEX.fg2, result: HEX.ok, stderr: HEX.err, lifecycle: HEX.info, stdout: HEX.fg2,
}
function color(e: RunEvent) {
  if (e.kind === 'result' && (e.payload?.is_error || e.payload?.subtype !== 'success')) return HEX.err
  if (e.kind === 'user' && e.payload?.message?.content?.some?.((b: any) => b.is_error)) return HEX.warn
  if (e.kind === 'assistant' && e.payload?.message?.content?.some?.((b: any) => b.type === 'tool_use')) return HEX.run
  return KIND_COLOR[e.kind] || HEX.fg1
}
function isToolUse(e: RunEvent) { return e.kind === 'assistant' && e.payload?.message?.content?.some?.((b: any) => b.type === 'tool_use') }

/** 每条事件的分类只判一次。
 *
 * 上色、筛选、计数问的都是同一件事，而答案要往 payload 里翻好几层。事件流最多留八百条，
 * 不缓存的话每来一条新事件，这八百条就要被翻上好几遍 —— 模型手快的时候页面直接没法滚。
 * 挂在事件对象上（WeakMap），事件被挤出列表后自动跟着回收。
 */
type Mark = { color: string; tool: boolean; err: boolean }
const marks = new WeakMap<RunEvent, Mark>()
function mark(e: RunEvent): Mark {
  let m = marks.get(e)
  if (!m) {
    const c = color(e)
    m = { color: c, tool: !!isToolUse(e), err: c === HEX.err || c === HEX.warn }
    marks.set(e, m)
  }
  return m
}

const shown = computed(() => {
  const f = filter.value
  if (f === 'all') return props.events
  return props.events.filter((e) => {
    const m = mark(e)
    if (f === 'tools') return m.tool || e.kind === 'user'
    if (f === 'text') return e.kind === 'assistant' && !m.tool
    return m.err
  })
})

function toggle(seq: number) {
  const s = new Set(open.value)
  s.has(seq) ? s.delete(seq) : s.add(seq)
  open.value = s
}
function detail(e: RunEvent): string {
  const p = e.payload || {}
  if (e.kind === 'assistant' || e.kind === 'user') {
    const blocks = p.message?.content
    if (Array.isArray(blocks)) {
      return blocks.map((b: any) => {
        if (b.type === 'tool_use') return `▶ ${b.name}\n${JSON.stringify(b.input, null, 2)}`
        if (b.type === 'tool_result') return `◀ result${b.is_error ? ' (error)' : ''}\n${typeof b.content === 'string' ? b.content : JSON.stringify(b.content, null, 2)}`
        if (b.type === 'text') return b.text
        return JSON.stringify(b, null, 2)
      }).join('\n\n')
    }
    if (typeof blocks === 'string') return blocks
  }
  return JSON.stringify(p, null, 2)
}

watch(() => props.events.length, async () => {
  if (!props.follow) return
  await nextTick()
  if (box.value) box.value.scrollTop = box.value.scrollHeight
})

const counts = computed(() => {
  let tools = 0
  let errors = 0
  for (const e of props.events) {
    const m = mark(e)
    if (m.tool) tools++
    if (m.err) errors++
  }
  return { all: props.events.length, tools, errors }
})
</script>

<template>
  <div class="flex flex-col h-full min-h-0">
    <div class="flex items-center gap-1 mb-2 text-xs">
      <button v-for="f in (['all', 'tools', 'text', 'errors'] as const)" :key="f"
        class="px-2 h-6 rounded-md transition-colors" :class="filter === f ? 'bg-accent/15 text-accent' : 'text-fg1 hover:text-fg0'"
        @click="filter = f">
        {{ { all: '全部', tools: '工具调用', text: '文字', errors: '错误' }[f] }}
        <span class="mono text-[11px] ml-1 opacity-70">{{ f === 'text' ? '' : counts[f as 'all' | 'tools' | 'errors'] }}</span>
      </button>
      <span class="ml-auto mono text-[12px] text-fg2">{{ shown.length }} / {{ events.length }}</span>
    </div>
    <div ref="box" class="flex-1 min-h-0 overflow-auto pr-1">
      <div v-if="!events.length" class="empty">暂无事件</div>
      <!-- 一行的样子只跟它自己和展开与否有关，所以新事件进来时其余的行整块跳过重排 -->
      <div v-for="e in shown" :key="e.seq" v-memo="[open.has(e.seq)]" class="relative pl-6 pb-3 animate-slidein">
        <div class="absolute left-[7px] top-2 bottom-0 w-px bg-line" />
        <span class="absolute left-1 top-1.5 dot" :style="{ background: mark(e).color }" />
        <div class="inner px-3 py-2 cursor-pointer hover:bg-bg3/80 transition-colors" @click="toggle(e.seq)">
          <div class="flex items-center gap-2 text-[12px] mono text-fg2">
            <span>{{ String(e.seq).padStart(3, '0') }}</span>
            <span :style="{ color: mark(e).color }">{{ e.kind }}</span>
            <span class="ml-auto">{{ fmtTime(e.ts) }}</span>
          </div>
          <div class="text-fg0 text-xs mt-0.5 break-words" :class="open.has(e.seq) ? '' : 'line-clamp-2'">{{ e.summary }}</div>
          <pre v-if="open.has(e.seq)" class="mono text-[12px] text-fg1 mt-2 whitespace-pre-wrap break-all max-h-[420px] overflow-auto bg-white border border-line rounded p-2">{{ detail(e) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
