<script setup lang="ts">
import { computed } from 'vue'
import type { VerifyItem, VerifyReport } from '../api'
import { DIM_LABEL, LEVEL_HEX } from '../status'

const props = defineProps<{ report: VerifyReport | null | undefined }>()
const has = computed(() => !!props.report && 'overall' in props.report)
const grouped = computed(() => {
  const out: Record<string, VerifyItem[]> = {}
  for (const it of props.report?.items || []) {
    const k = it.dim || 'global'
    ;(out[k] ||= []).push(it)
  }
  return out
})
const color = (l: string) => LEVEL_HEX[l] || LEVEL_HEX.ok
</script>

<template>
  <div class="card p-4 space-y-3">
    <div class="flex items-center gap-3">
      <div class="h2">交叉核验</div>
      <template v-if="has && report">
        <span class="pill" :style="{ color: color(report.overall === 'pass' ? 'ok' : report.overall), borderColor: color(report.overall === 'pass' ? 'ok' : report.overall) + '55' }">
          {{ report.overall === 'pass' ? '通过' : report.overall === 'warn' ? '有提醒' : '存在红项' }}
        </span>
        <div class="ml-auto flex items-center gap-4 mono text-xs nums">
          <span class="text-ok">通过 {{ Math.max(0, report.evidence_hit) }}</span>
          <span class="text-warn">标黄 {{ report.warns }}</span>
          <span class="text-err">标红 {{ report.blocks }}</span>
          <span class="text-fg2">证据命中 {{ report.evidence_hit_rate == null ? '—' : Math.round(report.evidence_hit_rate * 100) + '%' }}</span>
        </div>
      </template>
      <span v-else class="text-fg2 text-xs">保存评审后自动核验</span>
    </div>
    <div v-if="has && report && report.items.length" class="space-y-2">
      <div v-for="(items, dim) in grouped" :key="dim" class="inner p-3">
        <div class="mono text-[12px] text-fg2 mb-1">{{ DIM_LABEL[dim as string] || (dim === 'other' ? '其他问题' : '整体') }}</div>
        <div v-for="(it, i) in items" :key="i" class="flex items-start gap-2 text-xs py-0.5">
          <span class="dot mt-1.5 shrink-0" :style="{ background: color(it.level) }" />
          <span class="text-fg0">{{ it.message }}</span>
        </div>
      </div>
    </div>
    <div v-else-if="has" class="text-xs text-ok">五维描述与证据均可在轨迹中定位，未发现风格问题。</div>
  </div>
</template>
