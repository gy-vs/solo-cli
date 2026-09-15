<script setup lang="ts">
import { lightTheme, NConfigProvider, NDialogProvider, NMessageProvider, NNotificationProvider, zhCN, dateZhCN } from 'naive-ui'
import { themeOverrides } from './theme'
import Shell from './components/Shell.vue'
</script>

<template>
  <NConfigProvider :theme="lightTheme" :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <NNotificationProvider placement="bottom-right">
      <NMessageProvider placement="top-right">
        <NDialogProvider>
          <Shell />
        </NDialogProvider>
      </NMessageProvider>
    </NNotificationProvider>
  </NConfigProvider>
</template>
