<script setup lang="ts">
/** 质检结果：走 solo-qa 的完整质检链路，只取结论，不写它的库。 */
import { NButton, NTag, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { api, type TaskDetail } from '../api'
import { QC_LABEL, fmtTime } from '../status'

const props = defineProps<{ task: TaskDetail }>()
const emit = defineEmits<{ (e: 'done'): void }>()
const msg = useMessage()
const busy = ref(false)
const expanded = ref<Record<string, boolean>>({})

const qc = computed(() => props.task.qc as any)
const running = computed(() => props.task.qc_status === 'RUNNING')
const conclusion = computed(() => qc.value?.conclusion || '')
const checks = computed<any[]>(() => qc.value?.checks || [])
const failed = computed<any[]>(() => qc.value?.failed_checks || [])
const passedCount = computed(() => checks.value.filter((c) => c.passed).length)

async function run() {
  busy.value = true
  try {
    await api.qc(props.task.id)
    msg.info('质检已启动，含模型判定的那几项要跑一会儿')
    emit('done')
  } catch (e: any) { msg.error(e.message) } finally { busy.value = false }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center gap-3">
      <div>
        <div class="h2">质检</div>
        <div class="text-fg1 text-xs mt-0.5">调 solo-qa 的质检链路（硬校验 + 查重 + 描述判定），只读结论，不写它的库</div>
      </div>
      <NButton class="ml-auto" size="small" type="primary" secondary :loading="busy || running" @click="run">
        {{ qc?.conclusion || qc?.error ? '重新质检' : '开始质检' }}
      </NButton>
    </div>

    <div v-if="running" class="card empty">质检进行中 · 描述判定要调模型，通常 30 秒左右</div>

    <div v-else-if="task.qc_status === 'FAILED' && !conclusion" class="card p-4 space-y-1">
      <div class="text-err text-sm font-medium">质检没跑完</div>
      <div class="text-fg1 text-xs leading-5">{{ qc?.error || task.auto_error || '未知原因' }}</div>
      <div class="text-fg2 text-[12px]">没跑完不代表通过，修掉原因后重跑。</div>
    </div>

    <div v-else-if="!conclusion" class="card empty">还没质检过 · 五维评审完成后可以跑</div>

    <template v-else>
      <div class="card p-4 space-y-3">
        <div class="flex items-center gap-3 flex-wrap">
          <NTag size="small" :bordered="false"
            :type="conclusion === 'PASS' ? 'success' : conclusion === 'INCOMPLETE' ? 'warning' : 'error'">
            {{ QC_LABEL[conclusion] || conclusion }}
          </NTag>
          <span class="text-xs text-fg1">{{ passedCount }} / {{ checks.length }} 项通过</span>
          <span v-if="qc.hit_rule" class="text-xs text-err">命中 {{ qc.hit_rule }}</span>
          <span v-if="qc.confidence != null" class="text-xs text-fg2 mono">置信 {{ qc.confidence }}</span>
          <span class="ml-auto text-[12px] text-fg2 mono">
            {{ fmtTime(task.qc_at) }} · 耗时 {{ Math.round((qc.elapsed_ms || 0) / 1000) }}s
            <template v-if="qc.llm_ms">（模型 {{ Math.round(qc.llm_ms / 1000) }}s）</template>
          </span>
        </div>
        <div v-if="qc.summary" class="text-sm text-fg0 leading-6 whitespace-pre-wrap">{{ qc.summary }}</div>
      </div>

      <div v-if="failed.length" class="card">
        <div class="px-4 pt-4 pb-2 flex items-center gap-3">
          <div class="h2">未通过的项</div><span class="text-xs text-err">{{ failed.length }}</span>
        </div>
        <div v-for="c in failed" :key="c.name" class="px-4 py-3 border-t border-line space-y-1.5">
          <div class="flex items-start gap-2">
            <span class="dot bg-err mt-1.5" />
            <div class="min-w-0 flex-1">
              <div class="text-sm text-fg0">{{ c.name }}</div>
              <div class="text-xs text-fg1 leading-5 mt-0.5">{{ c.summary }}</div>
              <div v-if="expanded[c.name]" class="mt-2 inner p-3 text-[12px] text-fg1 leading-5 whitespace-pre-wrap">{{ c.detail }}</div>
            </div>
            <NButton v-if="c.detail" size="tiny" quaternary @click="expanded[c.name] = !expanded[c.name]">
              {{ expanded[c.name] ? '收起' : '展开' }}
            </NButton>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="px-4 pt-4 pb-2 flex items-center gap-3">
          <div class="h2">全部检查项</div><span class="text-xs text-fg2">{{ checks.length }}</span>
        </div>
        <div class="px-4 pb-4 pt-1 flex flex-wrap gap-2">
          <span v-for="c in checks" :key="c.name"
            class="inner px-2.5 py-1 text-[12px] flex items-center gap-1.5"
            :class="c.passed ? 'text-fg1' : 'text-err'" :title="c.summary">
            <span class="dot" :class="c.passed ? 'bg-ok' : 'bg-err'" />{{ c.name }}
          </span>
        </div>
      </div>
    </template>
  </div>
</template>
