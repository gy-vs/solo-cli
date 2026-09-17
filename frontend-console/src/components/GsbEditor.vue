<script setup lang="ts">
/** GSB 结论编辑。分析先填好，人工只是复核和微调，改完保存立刻重新自检。 */
import { NInput } from 'naive-ui'
import { computed } from 'vue'
import { SIDES, type Gsb, type Side, type Startup, type Verdict } from '../api'
import { SIDE_HEX, VERDICT_LABEL, VERDICTS } from '../status'

const props = defineProps<{ gsb: Gsb; readonly?: boolean }>()
const emit = defineEmits<{ (e: 'update', g: Gsb): void; (e: 'jump', p: { side?: string; step: number }): void }>()

function patch(part: Partial<Gsb>) {
  if (props.readonly) return
  emit('update', { ...props.gsb, ...part })
}
const startupKey = (s: Side) => (s === 'A' ? 'a_startup' : 'b_startup') as 'a_startup' | 'b_startup'
const findingsKey = (s: Side) => (s === 'A' ? 'a_findings' : 'b_findings') as 'a_findings' | 'b_findings'
const startup = (s: Side): Startup => props.gsb[startupKey(s)] || { steps: [], commands: [], note: '' }
const findings = (s: Side) => props.gsb[findingsKey(s)] || { good: [], bad: [] }

/** 理由是平台唯一看的正文，字数不够会被判无效。按平台口径算：去掉所有空白再数 */
const reasonLen = computed(() => (props.gsb.reason || '').replace(/\s/g, '').length)
/** Same 要论证两边确实等价，比选边更费笔墨，门槛也更高 */
const reasonFloor = computed(() => (props.gsb.verdict === 'Same' ? 150 : 60))
const reasonTooShort = computed(() => reasonLen.value > 0 && reasonLen.value < reasonFloor.value)

function setStartup(s: Side, part: Partial<Startup>) {
  patch({ [startupKey(s)]: { ...startup(s), ...part } } as Partial<Gsb>)
}
const asText = (lines: string[]) => (lines || []).join('\n')
const asLines = (v: string) => v.split('\n').map((x) => x.trim()).filter(Boolean)

function evLabel(ev: { side?: string; step?: number; file?: string; quote?: string }) {
  return [ev.side, ev.step ? `#${ev.step}` : '', ev.file ? ev.file.split('/').pop() : '']
    .filter(Boolean).join(' ') || (ev.quote || '').slice(0, 24)
}
</script>

<template>
  <div class="space-y-3">
    <div class="card p-4 space-y-3">
      <div class="flex items-center gap-3">
        <div class="h2">GSB 结论</div>
        <div class="flex gap-1">
          <button v-for="v in VERDICTS" :key="v"
            class="h-7 px-3 rounded-md text-xs border transition-colors"
            :class="gsb.verdict === v ? 'text-white font-semibold' : 'border-line text-fg1 hover:text-fg0'"
            :style="gsb.verdict === v ? { background: SIDE_HEX[v as Side] || '#475569', borderColor: 'transparent' } : {}"
            :disabled="readonly" @click="patch({ verdict: v as Verdict })">{{ VERDICT_LABEL[v] }}</button>
        </div>
        <div class="ml-auto mono text-[12px] nums" :class="reasonTooShort ? 'text-warn' : 'text-fg2'">
          理由 {{ reasonLen }} / {{ reasonFloor }} 字
        </div>
      </div>
      <NInput type="textarea" :value="gsb.reason || ''" :autosize="{ minRows: 6, maxRows: 24 }" :readonly="readonly"
        placeholder="以我的口吻写为什么偏向这一侧：哪个需求没做、哪个文件报什么错、页面上看到什么。不要提第几步、不要表情、不要列表和标题。"
        class="mono" @update:value="(v) => patch({ reason: v })" />
      <div v-if="gsb.evidence?.length" class="flex flex-wrap items-center gap-1.5">
        <span class="label mr-1">证据</span>
        <button v-for="(ev, i) in gsb.evidence" :key="i"
          class="pill h-5 text-[12px] mono border-accent/30 text-accent hover:bg-accent/10" :title="ev.quote || ''"
          @click="ev.step && emit('jump', { side: ev.side, step: ev.step })">{{ evLabel(ev) }}</button>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div v-for="s in SIDES" :key="s" class="card p-4 space-y-2">
        <div class="flex items-center gap-2">
          <span class="mono text-[12px] font-semibold w-5 h-5 inline-flex items-center justify-center rounded"
            :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
          <div class="text-fg0 font-medium text-sm">这一侧的表现</div>
        </div>
        <div class="space-y-1">
          <div v-for="(t, i) in findings(s).good" :key="'g' + i" class="flex items-start gap-2 text-xs">
            <span class="dot mt-1.5 shrink-0 bg-ok" /><span class="text-fg0">{{ t }}</span>
          </div>
          <div v-for="(t, i) in findings(s).bad" :key="'b' + i" class="flex items-start gap-2 text-xs">
            <span class="dot mt-1.5 shrink-0 bg-err" /><span class="text-fg0">{{ t }}</span>
          </div>
          <div v-if="!findings(s).good.length && !findings(s).bad.length" class="text-xs text-fg2">分析未给出要点</div>
        </div>
        <div class="pt-2 border-t border-line space-y-2">
          <div class="label">录屏启动步骤</div>
          <NInput type="textarea" :value="asText(startup(s).steps)" :autosize="{ minRows: 2, maxRows: 8 }" :readonly="readonly"
            placeholder="一行一步" class="mono text-[12px]" @update:value="(v) => setStartup(s, { steps: asLines(v) })" />
          <div class="label">命令</div>
          <NInput type="textarea" :value="asText(startup(s).commands)" :autosize="{ minRows: 1, maxRows: 6 }" :readonly="readonly"
            placeholder="一行一条命令" class="mono text-[12px]" @update:value="(v) => setStartup(s, { commands: asLines(v) })" />
          <div v-if="startup(s).note" class="text-[12px] text-warn break-all">{{ startup(s).note }}</div>
        </div>
      </div>
    </div>

    <div class="card p-4 space-y-2">
      <div class="flex items-center gap-3">
        <div class="text-fg0 font-medium text-sm">备注</div>
        <span class="ml-auto mono text-[12px] text-fg2">不上传，只给自己看</span>
      </div>
      <NInput type="textarea" :value="gsb.remark || ''" :autosize="{ minRows: 2, maxRows: 6 }" :readonly="readonly"
        placeholder="没有就留空" class="mono" @update:value="(v) => patch({ remark: v })" />
    </div>
  </div>
</template>
