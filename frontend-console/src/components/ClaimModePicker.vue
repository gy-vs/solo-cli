<script setup lang="ts">
import { NRadioButton, NRadioGroup } from 'naive-ui'
import { computed } from 'vue'
import { claimMode, MODE_TEXT, store } from '../store'

const quota = computed(() => store.status?.dual_quota)
const TIPS = computed<Record<string, string>>(() => {
  const [d, s] = quota.value?.cycle || [3, 6]
  return {
    auto: `先标成待定，第一个容器出闸时才定：每天开跑的题按先 ${d} 道双模型、再 ${s} 道单模型循环`,
    single: 'A、B 两侧用镜像里同一个模型各跑一次',
    dual: 'A 侧用镜像自带模型，B 侧用设置里填的新模型',
  }
})
</script>

<template>
  <div class="flex items-center gap-2">
    <NRadioGroup v-model:value="claimMode" size="small">
      <NRadioButton v-for="m in (['auto', 'single', 'dual'] as const)" :key="m" :value="m" :title="TIPS[m]">
        {{ MODE_TEXT[m] }}
      </NRadioButton>
    </NRadioGroup>
    <span v-if="quota" class="mono text-[12px] text-fg2 nums whitespace-nowrap"
      :title="`今日（${quota.date}）已开跑、未废弃 ${quota.total} 道，其中双模型 ${quota.dual} 道；`
        + `循环为先 ${quota.cycle[0]} 双、再 ${quota.cycle[1]} 单`">
      今日开跑 双 {{ quota.dual }} / 单 {{ quota.total - quota.dual }}
      · 下一道<span :class="quota.next === 'dual' ? 'text-accent' : 'text-fg1'">{{ MODE_TEXT[quota.next] }}</span>
    </span>
  </div>
</template>
