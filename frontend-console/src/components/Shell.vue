<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useGlobalEvents } from '../sse'
import { refreshStatus, refreshTasks, scheduleRefresh, store } from '../store'

const route = useRoute()
const nav = [
  { to: '/', label: '总览', key: 'overview', glyph: '◉' },
  { to: '/design', label: '设计题目', key: 'design', glyph: '✎' },
  { to: '/bank', label: '题库', key: 'bank', glyph: '▤' },
  { to: '/queue', label: '队列', key: 'queue', glyph: '≡' },
  { to: '/runs', label: '运行舱', key: 'runs', glyph: '▶' },
  { to: '/settings', label: '设置', key: 'settings', glyph: '⚙' },
]
const { connected } = useGlobalEvents(() => scheduleRefresh())
onMounted(() => { refreshStatus(); refreshTasks(); setInterval(refreshStatus, 15000) })

const crumb = computed(() => {
  const t = route.meta.title as string
  if (route.name === 'task') {
    const id = Number(route.params.id)
    const task = store.tasks.find((x) => x.id === id)
    return task ? `题目 · ${task.task_no}` : '题目'
  }
  return t
})
/** 详情页归属：没跑过的题算题库，其余算运行舱 */
const taskOwner = computed(() => {
  if (route.name !== 'task') return ''
  const t = store.tasks.find((x) => x.id === Number(route.params.id))
  if (!t) return 'runs'
  return ['AVAILABLE', 'CLAIMED', 'DISCARDED'].includes(t.status) ? 'bank' : 'runs'
})
const slots = computed(() => store.status?.scheduler)
const probes = computed(() => {
  const s = store.status
  return [
    { label: 'Docker', ok: !!s?.docker.ok },
    { label: '镜像', ok: !!s?.image.present },
    { label: '网关 Key', ok: !!s?.configured['cc.api_key'] },
    { label: 'solo-qa', ok: !!(s?.configured['qa.session_cookie'] && s?.configured['qa.csrf_token']) },
    { label: 'Cursor', ok: !!s?.configured['cursor.api_key'] },
  ]
})
</script>

<template>
  <div class="h-full flex">
    <aside class="w-[224px] shrink-0 bg-bg1 border-r border-line flex flex-col">
      <div class="h-14 px-5 flex items-center gap-3 border-b border-line">
        <div class="w-7 h-7 rounded-lg bg-accent/20 border border-accent/40 grid place-items-center">
          <span class="mono text-accent text-xs font-semibold">S</span>
        </div>
        <div>
          <div class="text-fg0 font-semibold leading-4">Solo CLI</div>
          <div class="text-[11px] text-fg2 leading-3 tracking-wider uppercase">Mission Control</div>
        </div>
      </div>
      <nav class="p-3 space-y-1">
        <RouterLink v-for="n in nav" :key="n.key" :to="n.to"
          class="flex items-center gap-3 px-3 h-10 rounded-inner text-[15px] text-fg1 hover:text-fg0 hover:bg-bg3/60 transition-colors"
          :class="{ '!bg-accent/15 !text-accent font-medium': route.name === n.key || n.key === taskOwner }">
          <span class="mono text-xs w-4 text-center opacity-80">{{ n.glyph }}</span>
          <span>{{ n.label }}</span>
          <span v-if="n.key === 'runs' && slots && slots.running" class="ml-auto mono text-[12px] text-run">{{ slots.running }}</span>
          <span v-else-if="n.key === 'queue' && slots?.queued" class="ml-auto mono text-[12px] text-run">{{ slots.queued }}</span>
          <span v-else-if="n.key === 'design' && store.status?.design.running.length" class="ml-auto dot bg-run animate-breathe" />
        </RouterLink>
      </nav>
      <div class="mt-auto p-4 border-t border-line space-y-1.5">
        <div v-for="p in probes" :key="p.label" class="flex items-center gap-2 text-xs text-fg1">
          <span class="dot" :class="p.ok ? 'bg-ok' : 'bg-err'" />
          <span>{{ p.label }}</span>
          <span class="ml-auto mono text-[11px]" :class="p.ok ? 'text-fg2' : 'text-err'">{{ p.ok ? 'ok' : 'miss' }}</span>
        </div>
      </div>
    </aside>

    <div class="flex-1 min-w-0 flex flex-col">
      <header class="h-14 shrink-0 px-6 flex items-center gap-4 bg-bg1/80 backdrop-blur border-b border-line">
        <div class="text-fg0 font-medium">{{ crumb }}</div>
        <div class="ml-auto flex items-center gap-4">
          <div class="flex items-center gap-2 text-xs text-fg1">
            <span class="dot" :class="connected ? 'bg-ok' : 'bg-err animate-breathe'" />
            {{ connected ? '实时连接' : '重连中' }}
          </div>
          <div class="inner px-3 h-8 flex items-center gap-2 text-xs">
            <span class="text-fg1">槽位</span>
            <span class="mono nums text-fg0">{{ slots?.running ?? 0 }} / {{ slots?.max_parallel ?? '-' }}</span>
          </div>
        </div>
      </header>
      <main class="flex-1 min-h-0 overflow-auto">
        <RouterView v-slot="{ Component }">
          <component :is="Component" :key="route.fullPath" />
        </RouterView>
      </main>
    </div>
  </div>
</template>
