<script setup lang="ts">
/** 题库列表上的快捷录屏入口：不进详情页也能把两侧跑起来、录完、传掉。 */
import { NButton, NModal, useMessage } from 'naive-ui'
import { onMounted, ref, watch } from 'vue'
import { api, SIDES, type Side, type TaskBrief } from '../api'
import { refreshHost, refreshTasks } from '../store'
import { SIDE_HEX } from '../status'
import SideLauncher from './SideLauncher.vue'

const props = defineProps<{ show: boolean; task: TaskBrief | null }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void }>()

const msg = useMessage()
/** 停录后落下的文件路径，等着换成链接 */
const files = ref<Record<Side, string>>({ A: '', B: '' })
const busy = ref('')

onMounted(refreshHost)
watch(() => props.show, (v) => { if (v) { files.value = { A: '', B: '' }; refreshHost() } })

async function upload(side: Side) {
  if (!props.task || !files.value[side]) return
  busy.value = side
  try {
    const r = await api.uploadScreencast(props.task.id, side, files.value[side])
    if (!r.ok) return msg.error(r.message)
    msg.success(`${side} 侧录屏已上传，链接已回填`)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busy.value = '' }
}
</script>

<template>
  <NModal :show="show" preset="card" class="!w-[680px]" :title="`题 ${task?.task_no} · 启动与录屏`"
    @update:show="(v: boolean) => emit('update:show', v)">
    <div v-if="task" class="space-y-3">
      <div class="text-xs text-fg1">
        两侧分别跑起来各录一段。录完这里就能直接传，也可以到详情页的录屏页签补链接。
      </div>
      <div v-for="s in SIDES" :key="s" class="inner p-3 space-y-2">
        <div class="flex items-center gap-2">
          <span class="mono text-[12px] font-semibold w-5 h-5 inline-flex items-center justify-center rounded"
            :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
          <span class="mono text-[11px] text-fg2 truncate">workspace/{{ task.task_no }}/{{ s }}</span>
          <span v-if="task.screencast?.[s]" class="pill text-[11px] text-ok border-ok/40 ml-auto">已有链接</span>
        </div>
        <SideLauncher :task-id="task.id" :task-no="task.task_no" :side="s"
          @recorded="(p) => (files = { ...files, [s]: p })" />
        <div v-if="files[s]" class="flex items-center gap-2">
          <span class="mono text-[11px] text-fg2 truncate flex-1" :title="files[s]">{{ files[s] }}</span>
          <NButton size="tiny" type="primary" secondary :loading="busy === s" @click="upload(s)">上传换链接</NButton>
        </div>
      </div>
    </div>
  </NModal>
</template>
