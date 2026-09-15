<script setup lang="ts">
import { NInput } from 'naive-ui'
import { computed } from 'vue'
import type { Evidence, Review, VerifyItem } from '../api'
import { DIM_LABEL, DIMS, LEVEL_HEX } from '../status'

const props = defineProps<{ review: Review; verifyItems: VerifyItem[]; readonly?: boolean }>()
const emit = defineEmits<{ (e: 'update', r: Review): void; (e: 'jump', step: number): void }>()

function setScore(dim: string, v: number) {
  if (props.readonly) return
  emit('update', { ...props.review, scores: { ...props.review.scores, [dim]: v } })
}
function setDesc(dim: string, v: string) {
  emit('update', { ...props.review, descs: { ...props.review.descs, [dim]: v } })
}
function setOther(v: string) { emit('update', { ...props.review, other_issues: v }) }

const itemsByDim = computed(() => {
  const m: Record<string, VerifyItem[]> = {}
  for (const it of props.verifyItems || []) (m[it.dim || 'global'] ||= []).push(it)
  return m
})
function worst(dim: string): 'ok' | 'warn' | 'block' {
  const items = itemsByDim.value[dim] || []
  if (items.some((i) => i.level === 'block')) return 'block'
  if (items.some((i) => i.level === 'warn')) return 'warn'
  return 'ok'
}
const color = (l: string) => LEVEL_HEX[l] || LEVEL_HEX.ok
function evLabel(ev: Evidence) {
  return [ev.step ? `#${ev.step}` : '', ev.file ? ev.file.split('/').pop() : ''].filter(Boolean).join(' ') || (ev.quote || '').slice(0, 20)
}
function highlightWords(dim: string): string[] {
  return (itemsByDim.value[dim] || []).flatMap((i) => i.words || [])
}
const len = (s: string) => (s || '').trim().length
</script>

<template>
  <div class="space-y-3">
    <div v-for="dim in DIMS" :key="dim" class="card p-4 space-y-3">
      <div class="flex items-center gap-3">
        <span class="dot" :style="{ background: color(worst(dim)) }" :title="(itemsByDim[dim] || []).map(i => i.message).join('\n')" />
        <div class="text-fg0 font-medium w-24">{{ DIM_LABEL[dim] }}</div>
        <div class="flex gap-1">
          <button v-for="n in 5" :key="n" class="w-8 h-7 rounded-md mono text-xs border transition-colors"
            :class="review.scores[dim] === n ? 'bg-accent text-white border-accent font-semibold' : 'border-line text-fg1 hover:border-accent/50 hover:text-fg0'"
            :disabled="readonly" @click="setScore(dim, n)">{{ n }}</button>
        </div>
        <div class="ml-auto flex items-center gap-2 mono text-[12px] text-fg2 nums">
          <span :class="len(review.descs[dim]) < 30 ? 'text-warn' : ''">{{ len(review.descs[dim]) }} 字</span>
        </div>
      </div>
      <NInput type="textarea" :value="review.descs[dim] || ''" :autosize="{ minRows: 3, maxRows: 10 }" :readonly="readonly"
        placeholder="用我的口吻写看到的现象：第几步、哪个文件、什么报错、哪条需求没做。不要表情、不要列表、不要结构词。"
        class="mono" @update:value="(v) => setDesc(dim, v)" />
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="label mr-1">证据</span>
        <button v-for="(ev, i) in (review.evidence?.[dim] || [])" :key="i"
          class="pill h-5 text-[12px] mono border-accent/30 text-accent hover:bg-accent/10" :title="ev.quote || ''"
          @click="ev.step && emit('jump', ev.step)">{{ evLabel(ev) }}</button>
        <span v-if="!(review.evidence?.[dim] || []).length" class="text-[12px] text-fg2">无</span>
        <template v-if="highlightWords(dim).length">
          <span class="label ml-3">命中词</span>
          <span v-for="w in highlightWords(dim)" :key="w" class="pill h-5 text-[12px] border-warn/40 text-warn">{{ w }}</span>
        </template>
      </div>
    </div>
    <div class="card p-4 space-y-2">
      <div class="flex items-center gap-3">
        <span class="dot" :style="{ background: color(worst('other')) }" />
        <div class="text-fg0 font-medium">其他问题</div>
        <span class="ml-auto mono text-[12px] text-fg2">可空</span>
      </div>
      <NInput type="textarea" :value="review.other_issues || ''" :autosize="{ minRows: 2, maxRows: 6 }" :readonly="readonly"
        placeholder="五维之外的问题，没有就留空" class="mono" @update:value="setOther" />
    </div>
  </div>
</template>
