<script setup lang="ts">
import { NButton, NInput, NSelect, NSwitch, useMessage } from 'naive-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { api, type SettingItem } from '../api'
import { refreshStatus, store } from '../store'

const msg = useMessage()
const items = ref<SettingItem[]>([])
const form = reactive<Record<string, string>>({})
const reveal = reactive<Record<string, boolean>>({})
const saving = ref(false)
const models = ref<string[]>([])
const modelsSource = ref('')
const loadingModels = ref(false)

const GROUP_PROBE: Record<string, { key: 'qa' | 'gateway' | 'cursor' | 'docker' | 'qc'; label: string }> = {
  'solo-qa 身份': { key: 'qa', label: '测试 solo-qa 身份' },
  'Claude Code 容器': { key: 'docker', label: '检查 Docker 与镜像' },
  'Cursor CLI 分析': { key: 'cursor', label: '测试 Cursor（pong）' },
  'solo-qa 质检': { key: 'qc', label: '测试质检通道' },
}
const probes = reactive<Record<string, { busy: boolean; ok: boolean | null; message: string; at: string }>>({})

const groups = computed(() => {
  const m: Record<string, SettingItem[]> = {}
  for (const it of items.value) (m[it.group] ||= []).push(it)
  return m
})

async function load() {
  const r = await api.settings()
  items.value = r.items
  for (const it of r.items) form[it.key] = it.value
}
onMounted(async () => { await load(); loadModels() })

async function loadModels() {
  loadingModels.value = true
  try {
    const r = await api.models()
    models.value = r.models
    modelsSource.value = r.source
  } catch { /* 静默 */ } finally { loadingModels.value = false }
}

async function save() {
  saving.value = true
  try {
    const values: Record<string, string> = {}
    for (const it of items.value) {
      // 密钥未改动时前端持有的是掩码，提交上去会把真值覆盖掉，这里直接不提交
      if (isMasked(it)) continue
      values[it.key] = form[it.key] ?? ''
    }
    const r = await api.saveSettings(values)
    items.value = r.items
    for (const it of r.items) form[it.key] = it.value
    msg.success(`已保存 ${r.written.length} 项`)
    await refreshStatus()
  } catch (e: any) { msg.error(e.message) } finally { saving.value = false }
}

async function probe(group: string) {
  const p = GROUP_PROBE[group]
  if (!p) return
  probes[group] = { busy: true, ok: null, message: '', at: '' }
  try {
    const r = await api.probe(p.key)
    probes[group] = { busy: false, ok: r.ok, message: r.message, at: new Date().toLocaleTimeString() }
  } catch (e: any) {
    probes[group] = { busy: false, ok: false, message: e.message, at: new Date().toLocaleTimeString() }
  }
}
function isMasked(it: SettingItem) { return it.secret && form[it.key]?.startsWith('••••') }
function clearSecret(it: SettingItem) { form[it.key] = ''; reveal[it.key] = true }
</script>

<template>
  <div class="page">
    <div class="flex items-center gap-3">
      <div>
        <div class="h1">设置</div>
        <div class="text-fg1 text-xs mt-0.5">所有值加密存于 <span class="mono">./data</span>，密钥只显示末 4 位；保存后立即生效，无需重启</div>
      </div>
      <NButton class="ml-auto" type="primary" size="small" :loading="saving" @click="save">保存全部</NButton>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <div v-for="(list, group) in groups" :key="group" class="card p-4 space-y-3">
        <div class="flex items-center gap-3">
          <div class="h2">{{ group }}</div>
          <template v-if="GROUP_PROBE[group as string]">
            <span v-if="probes[group as string]?.ok != null" class="dot" :class="probes[group as string].ok ? 'bg-ok' : 'bg-err'" />
            <span v-else-if="probes[group as string]?.busy" class="dot bg-run animate-breathe" />
            <NButton size="tiny" tertiary class="ml-auto" :loading="probes[group as string]?.busy" @click="probe(group as string)">
              {{ GROUP_PROBE[group as string].label }}
            </NButton>
          </template>
        </div>
        <div v-if="probes[group as string]?.message" class="inner px-3 py-2 text-xs flex gap-3" :class="probes[group as string].ok ? 'text-ok' : 'text-err'">
          <span class="flex-1 break-all">{{ probes[group as string].message }}</span>
          <span class="mono text-fg2 shrink-0">{{ probes[group as string].at }}</span>
        </div>

        <div v-for="it in list" :key="it.key" class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="text-xs text-fg0">{{ it.label }}</span>
            <span class="mono text-[11px] text-fg2">{{ it.key }}</span>
            <span v-if="it.secret" class="ml-auto text-[11px]" :class="it.configured ? 'text-ok' : 'text-err'">{{ it.configured ? '已配置' : '未配置' }}</span>
          </div>
          <template v-if="it.kind === 'bool'">
            <div class="flex items-center gap-3">
              <NSwitch size="small" :value="form[it.key] !== '0' && form[it.key] !== ''"
                @update:value="(v: boolean) => form[it.key] = v ? '1' : '0'" />
              <span class="text-[12px] text-fg2">{{ it.help || (form[it.key] !== '0' && form[it.key] !== '' ? '开启' : '关闭') }}</span>
            </div>
          </template>
          <template v-else-if="it.kind === 'select' && it.key === 'cursor.model'">
            <div class="flex gap-2">
              <NSelect v-model:value="form[it.key]" :options="models.map(m => ({ label: m, value: m }))" filterable tag size="small" :loading="loadingModels"
                placeholder="选择或输入模型 slug" />
              <NButton size="small" tertiary :loading="loadingModels" @click="loadModels">刷新</NButton>
            </div>
            <div class="text-[12px] text-fg2">{{ modelsSource === 'live' ? '列表来自 Cursor CLI 实时探测' : '实时探测不可用，显示内置列表；可直接输入 slug' }}</div>
          </template>
          <template v-else-if="it.secret">
            <div class="flex gap-2">
              <NInput v-model:value="form[it.key]" size="small" :type="reveal[it.key] ? 'text' : 'password'" :placeholder="it.help || it.label"
                class="mono" :readonly="isMasked(it)" />
              <NButton v-if="isMasked(it)" size="small" tertiary @click="clearSecret(it)">更换</NButton>
              <NButton v-else size="small" tertiary @click="reveal[it.key] = !reveal[it.key]">{{ reveal[it.key] ? '隐藏' : '显示' }}</NButton>
            </div>
          </template>
          <NInput v-else v-model:value="form[it.key]" size="small" :placeholder="it.default || it.help" class="mono" />
          <div v-if="it.help && !['select', 'bool'].includes(it.kind)" class="text-[12px] text-fg2">{{ it.help }}</div>
        </div>
      </div>

      <div class="card p-4 space-y-2">
        <div class="h2">路径（由 docker-compose 环境决定）</div>
        <div class="inner px-3 py-2 text-xs"><div class="label">宿主机 coder 根目录</div><div class="mono text-fg0 break-all">{{ store.status?.paths.coder_root_host }}</div></div>
        <div class="inner px-3 py-2 text-xs"><div class="label">后端容器内挂载</div><div class="mono text-fg0 break-all">{{ store.status?.paths.coder_root_mount }}</div></div>
        <div class="inner px-3 py-2 text-xs"><div class="label">题库文件</div><div class="mono break-all" :class="store.status?.paths.prompt_exists ? 'text-fg0' : 'text-err'">{{ store.status?.paths.prompt_file }} {{ store.status?.paths.prompt_exists ? '' : '（不存在）' }}</div></div>
        <div class="text-[12px] text-fg2">修改路径请编辑 <span class="mono">.env</span> 中的 <span class="mono">CODER_ROOT</span> 后重新 <span class="mono">docker compose up</span>。</div>
      </div>
    </div>
  </div>
</template>
