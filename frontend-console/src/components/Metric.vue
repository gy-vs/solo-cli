<script setup lang="ts">
defineProps<{ label: string; value: string | number; tone?: string; sub?: string }>()
</script>

<template>
  <div class="card p-4">
    <div class="label">{{ label }}</div>
    <div class="mono nums text-[32px] leading-9 mt-1 font-semibold" :style="{ color: tone || '#0F172A' }">{{ value }}</div>
    <div v-if="sub" class="text-xs text-fg2 mt-1">{{ sub }}</div>
  </div>
</template>
