<template>
  <v-card :flat="!config?.attrs?.border" class="fntv-dashboard">
    <v-card-item>
      <v-card-title class="text-subtitle-1">
        {{ config?.attrs?.title || '飞牛影视豆瓣同步' }}
      </v-card-title>
      <template #append>
        <v-btn
          v-if="allowRefresh"
          icon
          size="small"
          variant="text"
          :loading="loading"
          @click="load"
        >
          <v-icon size="small">mdi-refresh</v-icon>
        </v-btn>
      </template>
    </v-card-item>

    <v-card-text class="pt-0">
      <div v-if="loading" class="d-flex justify-center py-4">
        <v-progress-circular indeterminate color="primary" size="24" />
      </div>
      <div v-else>
        <v-row dense>
          <v-col cols="6" md="6">
            <div class="text-caption text-medium-emphasis">运行状态</div>
            <div class="text-body-2 font-weight-bold">
              <v-chip :color="status.enabled ? 'success' : 'grey'" size="x-small" label>
                {{ status.enabled ? '已启用' : '已停用' }}
              </v-chip>
            </div>
          </v-col>
          <v-col cols="6" md="6">
            <div class="text-caption text-medium-emphasis">上次同步</div>
            <div class="text-body-2 font-weight-bold">{{ fmtMs(status.last_sync_time) || '从未同步' }}</div>
          </v-col>
          <v-col cols="6" md="6" class="pt-2">
            <div class="text-caption text-medium-emphasis">已完成 / 失败</div>
            <div class="text-body-2 font-weight-bold">
              <span class="text-success">{{ status.stats?.done ?? 0 }}</span>
              /
              <span :class="{ 'text-error': (status.stats?.failed ?? 0) > 0 }">
                {{ status.stats?.failed ?? 0 }}
              </span>
            </div>
          </v-col>
          <v-col cols="6" md="6" class="pt-2">
            <div class="text-caption text-medium-emphasis">最近记录</div>
            <div class="text-body-2 text-truncate" :title="recentText">{{ recentText || '暂无' }}</div>
          </v-col>
        </v-row>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: false },
  api: { type: Object, default: () => null },
})

const status = ref({ enabled: false, last_sync_time: 0, stats: {} })
const recentText = ref('')
const loading = ref(false)

const actionLabels = {
  mark_done: '标记看过',
  mark_doing: '标记在看',
  error_search: '搜索无结果',
  error_api: '标记失败',
  remove_wish: '移出想看',
  repair_subject: '修正豆瓣条目',
}

function fmtMs(ts) {
  return ts ? new Date(ts).toLocaleString('zh-CN', { hour12: false }) : ''
}

async function load() {
  if (!props.api) return
  loading.value = true
  try {
    status.value = await props.api.get('plugin/FntvDoubanSync/status')
    const res = await props.api.get('plugin/FntvDoubanSync/logs?limit=1')
    const recent = res.items?.[0]
    if (recent) {
      const label = actionLabels[recent.action] || recent.action
      recentText.value = [label, recent.series_title, recent.detail]
        .filter(Boolean).join(' · ')
    } else {
      recentText.value = ''
    }
  } catch {
    /* 静默保持上次数据 */
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.fntv-dashboard {
  width: 100%;
}
</style>
