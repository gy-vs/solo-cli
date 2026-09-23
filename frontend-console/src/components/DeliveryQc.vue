<script setup lang="ts">
/** 质检报告里交付完整性那一段。两道质检共用：事实核验报 problems，措辞质检报 issues。 */
import { computed } from 'vue'
import { SIDES, type DeliveryQc } from '../api'
import { SIDE_HEX } from '../status'

const props = defineProps<{ report?: DeliveryQc }>()

const STATUS_TEXT = { ok: '通过', fixed: '已订正', fail: '未通过' } as const
const STATUS_CLS = { ok: 'text-ok border-ok/40', fixed: 'text-accent border-accent/40', fail: 'text-err border-err/40' } as const
const sides = computed(() => SIDES.filter((s) => props.report?.sides?.[s]))
</script>

<template>
  <div v-if="report && sides.length" class="pt-1 border-t border-line space-y-2">
    <div class="label">交付完整性</div>
    <div v-for="s in sides" :key="s" class="inner p-3 space-y-1.5">
      <div class="flex items-center gap-2">
        <span class="mono text-[12px] font-semibold w-5 h-5 inline-flex items-center justify-center rounded"
          :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
        <span v-if="report.sides[s]!.score" class="mono text-[12px] text-fg1">{{ report.sides[s]!.score }} 分</span>
        <span class="pill h-5 text-[12px] ml-auto" :class="STATUS_CLS[report.sides[s]!.status]">
          {{ STATUS_TEXT[report.sides[s]!.status] }}
        </span>
      </div>
      <div v-for="(n, i) in report.sides[s]!.notes || []" :key="'n' + i"
        class="text-xs text-fg0 leading-6 bg-ok/5 border-l-2 border-ok/50 pl-2.5 py-1 break-all">{{ n }}</div>
      <template v-if="report.sides[s]!.status === 'fail'">
        <div v-for="(p, i) in report.sides[s]!.problems || []" :key="'p' + i" class="text-xs leading-6 break-all">
          <span class="text-err">{{ p.quote || '评分' }}</span>
          <span v-if="p.fact" class="text-fg1"> —— 轨迹里实际是：{{ p.fact }}</span>
        </div>
        <div v-for="(it, i) in report.sides[s]!.issues || []" :key="'i' + i" class="text-xs leading-6 break-all">
          <span class="text-err">{{ it.quote }}</span>
          <span class="text-fg1"> —— {{ it.kind }}{{ it.suggest ? `，建议：${it.suggest}` : '' }}</span>
        </div>
        <div v-for="(d, i) in report.sides[s]!.local_defects || []" :key="'d' + i"
          class="text-xs text-warn leading-6 break-all">{{ d }}</div>
        <div v-if="report.sides[s]!.rewrite_dropped" class="text-[12px] text-fg2 leading-5 break-all">
          自动改写没采用：{{ report.sides[s]!.rewrite_dropped }}
        </div>
      </template>
      <div v-if="report.sides[s]!.desc_after" class="text-[12px] text-fg2 leading-5 break-all">
        改写前：{{ report.sides[s]!.desc_before }}
      </div>
    </div>
  </div>
</template>
