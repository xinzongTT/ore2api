<template>
  <div class="space-y-5">
    <PagePanel>
      <PanelHeader title="调试中心">
        <template #copy>
          <p class="mt-1 text-xs text-muted-foreground">当前 Oreate-only 构建只保留模型、图片生成和视频生成接口。</p>
        </template>
      </PanelHeader>
    </PagePanel>

    <PagePanel>
      <PanelHeader title="可用接口" />
      <div class="grid gap-3 lg:grid-cols-3">
        <SurfaceBox v-for="item in availableEndpoints" :key="item.path" density="compact">
          <p class="text-xs font-semibold text-foreground">{{ item.title }}</p>
          <p class="mt-2 font-mono text-xs text-muted-foreground">{{ item.method }} {{ item.path }}</p>
        </SurfaceBox>
      </div>
    </PagePanel>

    <PagePanel>
      <PanelHeader title="已移除接口" />
      <div class="grid gap-3 md:grid-cols-2">
        <SurfaceBox v-for="item in removedEndpoints" :key="item" density="compact">
          <p class="font-mono text-xs text-muted-foreground">{{ item }}</p>
          <p class="mt-2 text-xs text-muted-foreground">HTTP 410 Gone</p>
        </SurfaceBox>
      </div>
    </PagePanel>
  </div>
</template>

<script setup lang="ts">
import PagePanel from '@/components/ai/PagePanel.vue'
import PanelHeader from '@/components/ai/PanelHeader.vue'
import SurfaceBox from '@/components/ai/SurfaceBox.vue'

const availableEndpoints = [
  { title: '模型列表', method: 'GET', path: '/v1/models' },
  { title: '图片生成', method: 'POST', path: '/v1/images/generations' },
  { title: '视频生成', method: 'POST', path: '/v1/video/generations' },
]

const removedEndpoints = [
  '/v1/chat/completions',
  '/v1/responses',
  '/v1/messages',
  '/v1/search',
  '/v1/images/edits',
  '/v1/editable-file-tasks',
  '/v1/ppt/generations',
  '/v1/psd/generations',
  '/files/*',
]
</script>
