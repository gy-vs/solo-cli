import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: () => import('./pages/Overview.vue'), meta: { title: '总览' } },
    { path: '/design', name: 'design', component: () => import('./pages/Design.vue'), meta: { title: '设计题目' } },
    { path: '/bank', name: 'bank', component: () => import('./pages/Bank.vue'), meta: { title: '题库' } },
    { path: '/list', name: 'list', component: () => import('./pages/Pipeline.vue'), meta: { title: '题目列表' } },
    { path: '/queue', name: 'queue', component: () => import('./pages/Queue.vue'), meta: { title: '队列' } },
    { path: '/runs', name: 'runs', component: () => import('./pages/Runs.vue'), meta: { title: '运行舱' } },
    { path: '/tasks/:id', name: 'task', component: () => import('./pages/TaskDetail.vue'), meta: { title: '题目' } },
    { path: '/settings', name: 'settings', component: () => import('./pages/Settings.vue'), meta: { title: '设置' } },
  ],
})
