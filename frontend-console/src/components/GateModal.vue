<script setup lang="ts">
import { NButton, NModal, useDialog, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { api, type GateReport, type TaskBrief } from '../api'
import GateChecks from './GateChecks.vue'

const props = defineProps<{ show: boolean; task: TaskBrief | null; report: GateReport | null }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void; (e: 'queued'): void; (e: 'recheck'): void }>()
const msg = useMessage()
const dialog = useDialog()
const busy = ref(false)

function forceStart() {
  if (!props.task) return
  dialog.error({
    title: '强制启动',
    content: '门禁未通过仍启动，可能导致轨迹泄漏、初始环境不一致，产出的数据可能不可用。确认继续？',
    positiveText: '仍然启动',
    negativeText: '取消',
    onPositiveClick: async () => {
      busy.value = true
      try {
        await api.claim(props.task!.id, true)
        msg.success('已强制加入队列')
        emit('queued')
        emit('update:show', false)
      } catch (e: any) { msg.error(e.message) } finally { busy.value = false }
    },
  })
}
</script>

<template>
  <NModal :show="show" @update:show="(v) => emit('update:show', v)" preset="card" :title="`启动门禁 · 题 ${task?.task_no ?? ''}`"
    style="width: 680px" :bordered="false" size="small">
    <GateChecks :task="task" :report="report" @recheck="emit('recheck')" />
    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <NButton size="small" tertiary @click="emit('update:show', false)">关闭</NButton>
        <NButton v-if="report && !report.passed" size="small" type="error" secondary :loading="busy" @click="forceStart">仍然强制启动</NButton>
      </div>
    </template>
  </NModal>
</template>
