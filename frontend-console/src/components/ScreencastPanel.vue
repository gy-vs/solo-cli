<script setup lang="ts">
/** 录屏环节。流程里唯一等人的地方：两侧链接都填上才让上传。 */
import { NButton, NInput, useMessage } from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { api, SIDES, type Gsb, type Side, type TaskDetail } from '../api'
import { refreshHost } from '../store'
import { SIDE_HEX } from '../status'
import SideLauncher from './SideLauncher.vue'

const props = defineProps<{ task: TaskDetail; gsb: Gsb }>()
const emit = defineEmits<{ (e: 'saved'): void }>()
const msg = useMessage()

const urls = ref<Record<Side, string>>({ A: '', B: '' })
const paths = ref<Record<Side, string>>({ A: '', B: '' })
const busy = ref('')
const saving = ref(false)

watch(() => props.task.screencast, (v) => {
  urls.value = { A: v?.A || '', B: v?.B || '' }
}, { immediate: true, deep: true })
onMounted(refreshHost)

const dirty = computed(() => SIDES.some((s) => urls.value[s] !== (props.task.screencast?.[s] || '')))
const filled = computed(() => SIDES.every((s) => !!urls.value[s].trim()))
const startup = (s: Side) => (s === 'A' ? props.gsb.a_startup : props.gsb.b_startup) || { steps: [], commands: [], note: '' }

async function save() {
  saving.value = true
  try {
    await api.saveScreencast(props.task.id, { A: urls.value.A.trim(), B: urls.value.B.trim() })
    msg.success('已保存录屏链接')
    emit('saved')
  } catch (e: any) { msg.error(e.message) } finally { saving.value = false }
}

/** 本地文件走后端转存，省得自己传一遍再复制链接 */
async function upload(side: Side) {
  const p = paths.value[side].trim()
  if (!p) return msg.warning('先填录屏文件在本机的路径')
  busy.value = side
  try {
    const r = await api.uploadScreencast(props.task.id, side, p)
    if (!r.ok) return msg.error(r.message)
    urls.value = { ...urls.value, [side]: r.url }
    msg.success(`${side} 侧录屏已上传`)
    emit('saved')
  } catch (e: any) { msg.error(e.message) } finally { busy.value = '' }
}
</script>

<template>
  <div class="card p-4 space-y-3">
    <div class="flex items-center gap-3">
      <div class="h2">录屏</div>
      <span class="pill" :class="filled ? 'text-ok border-ok/40' : 'text-warn border-warn/40'">
        {{ filled ? '两侧齐了' : '等录屏链接' }}
      </span>
      <NButton v-if="dirty" size="small" type="primary" class="ml-auto" :loading="saving" @click="save">保存链接</NButton>
    </div>
    <div class="text-xs text-fg1">
      点「启动项目」会在本机开一个终端窗口，装依赖的命令自动跑掉，剩下的放进历史按 ↑ 调出来。
      录屏按 720p 存到这道题的产物目录，停录后路径自动填好，点上传就能换回链接。
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div v-for="s in SIDES" :key="s" class="inner p-3 space-y-2">
        <div class="flex items-center gap-2">
          <span class="mono text-[12px] font-semibold w-5 h-5 inline-flex items-center justify-center rounded"
            :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
          <span class="mono text-[11px] text-fg2 truncate">workspace/{{ task.task_no }}/{{ s }}</span>
        </div>
        <SideLauncher :task-id="task.id" :task-no="task.task_no" :side="s"
          @recorded="(p) => (paths = { ...paths, [s]: p })" />
        <ol v-if="startup(s).steps.length" class="text-[12px] text-fg1 space-y-0.5 list-decimal pl-4">
          <li v-for="(st, i) in startup(s).steps" :key="i">{{ st }}</li>
        </ol>
        <pre v-if="startup(s).commands.length"
          class="mono text-[11px] text-fg0 bg-white border border-line rounded p-2 whitespace-pre-wrap break-all">{{ startup(s).commands.join('\n') }}</pre>
        <NInput :value="urls[s]" size="small" placeholder="录屏链接" class="mono text-[12px]"
          @update:value="(v) => (urls = { ...urls, [s]: v })" />
        <div class="flex items-center gap-1.5">
          <NInput :value="paths[s]" size="tiny" placeholder="或填本机文件路径，代传" class="mono text-[11px]"
            @update:value="(v) => (paths = { ...paths, [s]: v })" />
          <NButton size="tiny" secondary :loading="busy === s" @click="upload(s)">上传</NButton>
        </div>
      </div>
    </div>
  </div>
</template>
