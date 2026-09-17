<script setup lang="ts">
/** 上传前的自检结果。红项没清掉后端会拒绝上传，这里把原因摊开。 */
import { computed } from 'vue'
import type { VerifyReport } from '../api'
import { LEVEL_HEX } from '../status'

const props = defineProps<{ report: VerifyReport | null | undefined }>()
const has = computed(() => !!props.report && 'overall' in props.report)
const items = computed(() => {
  const order = { block: 0, warn: 1, ok: 2 }
  return [...(props.report?.items || [])].sort((a, b) => order[a.level] - order[b.level])
})
const color = (l: string) => LEVEL_HEX[l] || LEVEL_HEX.ok
const OVERALL_TEXT = { ok: '可以上传', warn: '有提醒', block: '存在红项' }
</script>

<template>
  <div class="card p-4 space-y-3">
    <div class="flex items-center gap-3">
      <div class="h2">上传自检</div>
      <template v-if="has && report">
        <span class="pill" :style="{ color: color(report.overall), borderColor: color(report.overall) + '55' }">
          {{ OVERALL_TEXT[report.overall] }}
        </span>
        <div class="ml-auto flex items-center gap-4 mono text-xs nums">
          <span class="text-err">红项 {{ report.blocked }}</span>
          <span class="text-warn">提醒 {{ report.warnings }}</span>
        </div>
      </template>
      <span v-else class="text-fg2 text-xs">保存 GSB 结论后自动自检</span>
    </div>
    <div v-if="has && items.length" class="space-y-1">
      <div v-for="(it, i) in items" :key="i" class="inner px-3 py-2 flex items-start gap-2 text-xs">
        <span class="dot mt-1.5 shrink-0" :style="{ background: color(it.level) }" />
        <div class="min-w-0">
          <span class="mono text-[11px] text-fg2 mr-2">{{ it.name }}</span>
          <span class="text-fg0 break-all">{{ it.message }}</span>
        </div>
      </div>
    </div>
    <div v-else-if="has" class="text-xs text-ok">结论、理由与两侧产物均符合平台要求。</div>
  </div>
</template>
