<script setup lang="ts">
/** 录屏文档的渲染。
 *
 * 文档只有几种块：标题、段落、编号步骤、PowerShell 代码块，不值得为它引一个 markdown 库。
 * 自己切块还有一个好处：不走 v-html，文档里的内容（作答仓库的界面文案、接口响应）
 * 原样当文本显示，不会被当成标签执行。
 */
import { useMessage } from 'naive-ui'
import { computed } from 'vue'

const props = defineProps<{ source: string }>()
const msg = useMessage()

type Block =
  | { kind: 'h'; level: number; text: string }
  | { kind: 'p'; text: string }
  | { kind: 'ol' | 'ul'; items: string[] }
  | { kind: 'code'; lang: string; text: string }

const blocks = computed<Block[]>(() => {
  const out: Block[] = []
  const lines = props.source.replace(/\r\n/g, '\n').split('\n')
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const fence = line.match(/^```(\w*)\s*$/)
    if (fence) {
      const body: string[] = []
      i++
      while (i < lines.length && !/^```\s*$/.test(lines[i])) body.push(lines[i++])
      i++
      out.push({ kind: 'code', lang: fence[1] || '', text: body.join('\n') })
      continue
    }
    if (/^<!--.*-->\s*$/.test(line) || !line.trim()) { i++; continue }
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    if (h) { out.push({ kind: 'h', level: h[1].length, text: h[2] }); i++; continue }
    if (/^\s*\d+[.)]\s+/.test(line) || /^\s*[-*]\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line)
      const items: string[] = []
      while (i < lines.length && (ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*]\s+/).test(lines[i])) {
        items.push(lines[i].replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*]\s+/, ''))
        i++
        // 续行（缩进的下一行）并进同一条
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*(\d+[.)]|[-*])\s+/.test(lines[i])) {
          items[items.length - 1] += ' ' + lines[i].trim()
          i++
        }
      }
      out.push({ kind: ordered ? 'ol' : 'ul', items })
      continue
    }
    const para: string[] = [line]
    i++
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|\s*\d+[.)]\s|\s*[-*]\s|<!--)/.test(lines[i])) {
      para.push(lines[i++])
    }
    out.push({ kind: 'p', text: para.join('\n') })
  }
  return out
})

/** 行内只认 `code` 与 **粗体**，切成片段交给模板，不拼 HTML */
function inline(text: string): { t: string; code?: boolean; bold?: boolean }[] {
  const parts: { t: string; code?: boolean; bold?: boolean }[] = []
  const re = /`([^`]+)`|\*\*([^*]+)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push({ t: text.slice(last, m.index) })
    parts.push(m[1] !== undefined ? { t: m[1], code: true } : { t: m[2], bold: true })
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push({ t: text.slice(last) })
  return parts
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    msg.success('已复制')
  } catch {
    msg.error('复制失败，浏览器没给剪贴板权限')
  }
}
</script>

<template>
  <div class="space-y-3 text-sm text-fg0 leading-6">
    <template v-for="(b, idx) in blocks" :key="idx">
      <div v-if="b.kind === 'h'" :class="b.level <= 2 ? 'text-base font-semibold pt-1' : 'text-sm font-semibold pt-1 text-fg0'">
        <template v-for="(s, j) in inline(b.text)" :key="j">
          <code v-if="s.code" class="mono text-[12px] px-1 py-0.5 rounded bg-bg3">{{ s.t }}</code>
          <b v-else-if="s.bold">{{ s.t }}</b>
          <template v-else>{{ s.t }}</template>
        </template>
      </div>
      <p v-else-if="b.kind === 'p'" class="whitespace-pre-wrap break-words text-fg1">
        <template v-for="(s, j) in inline(b.text)" :key="j">
          <code v-if="s.code" class="mono text-[12px] px-1 py-0.5 rounded bg-bg3 text-fg0">{{ s.t }}</code>
          <b v-else-if="s.bold" class="text-fg0">{{ s.t }}</b>
          <template v-else>{{ s.t }}</template>
        </template>
      </p>
      <component :is="b.kind" v-else-if="b.kind === 'ol' || b.kind === 'ul'"
        class="space-y-1.5 pl-5 text-fg1" :class="b.kind === 'ol' ? 'list-decimal' : 'list-disc'">
        <li v-for="(it, j) in b.items" :key="j" class="break-words pl-1">
          <template v-for="(s, k) in inline(it)" :key="k">
            <code v-if="s.code" class="mono text-[12px] px-1 py-0.5 rounded bg-bg3 text-fg0">{{ s.t }}</code>
            <b v-else-if="s.bold" class="text-fg0">{{ s.t }}</b>
            <template v-else>{{ s.t }}</template>
          </template>
        </li>
      </component>
      <div v-else-if="b.kind === 'code'" class="rounded-inner border border-line overflow-hidden">
        <div class="h-8 px-3 flex items-center gap-2 bg-bg3 border-b border-line">
          <span class="mono text-[11px] uppercase tracking-wider text-fg2">{{ b.lang || 'text' }}</span>
          <button class="ml-auto text-[12px] text-accent hover:underline" @click="copy(b.text)">复制</button>
        </div>
        <pre class="mono text-[12px] leading-5 px-3 py-2.5 overflow-x-auto bg-[#0F172A] text-[#E2E8F0]">{{ b.text }}</pre>
      </div>
    </template>
  </div>
</template>
