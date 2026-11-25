<template>
  <v-card :flat="!config?.attrs?.border" class="fntv-dashboard">
    <v-card-item class="pb-2">
      <template #prepend>
        <div class="fntv-dash-icon">
          <v-icon size="16">mdi-sync</v-icon>
        </div>
      </template>
      <v-card-title class="text-subtitle-1 font-weight-bold">
        {{ config?.attrs?.title || '飞牛影视豆瓣同步' }}
      </v-card-title>
      <template #append>
        <v-chip
          :color="status.running ? 'info' : status.enabled ? 'success' : 'secondary'"
          size="x-small"
          variant="tonal"
          label
          class="mr-1"
        >
          {{ status.running ? '同步中' : status.enabled ? '已启用' : '已停用' }}
        </v-chip>
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

    <v-card-text class="pt-1">
      <div v-if="loading && !initialized" class="d-flex justify-center py-6">
        <v-progress-circular indeterminate color="primary" size="24" />
      </div>
      <div v-else>
        <div class="fntv-dash-grid mb-3">
          <div class="fntv-dash-kpi">
            <div class="text-caption text-medium-emphasis">看过</div>
            <div class="text-h6 font-weight-bold text-success fntv-tabular">{{ dashStats.done }}</div>
          </div>
          <div class="fntv-dash-kpi">
            <div class="text-caption text-medium-emphasis">在看</div>
            <div class="text-h6 font-weight-bold text-info fntv-tabular">{{ dashStats.doing }}</div>
          </div>
          <div class="fntv-dash-kpi">
            <div class="text-caption text-medium-emphasis">异常</div>
            <div
              class="text-h6 font-weight-bold fntv-tabular"
              :class="dashStats.failed > 0 ? 'text-error' : 'text-medium-emphasis'"
            >
              {{ dashStats.failed }}
            </div>
          </div>
        </div>

        <div class="d-flex align-center justify-space-between text-caption mb-1">
          <span class="text-medium-emphasis">最近同步</span>
          <span class="font-weight-medium" :title="fullRunTime">
            {{ shortRunTime || '从未同步' }}
          </span>
        </div>
        <div class="d-flex align-center justify-space-between text-caption ga-2">
          <span class="text-medium-emphasis text-no-wrap">最近动态</span>
          <span class="text-truncate font-weight-medium" :title="recentText || '暂无记录'">
            {{ recentText || '暂无记录' }}
          </span>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: true },
  api: { type: Object, default: () => null },
  pluginId: { type: String, default: 'FntvDoubanSync' },
})

const apiBase = computed(() => `plugin/${props.pluginId || 'FntvDoubanSync'}`)

const status = ref({
  running: false,
  enabled: false,
  last_sync_time: 0,
  last_run_at: 0,
  stats: {},
  item_stats: null,
})
const recentText = ref('')
const loading = ref(false)
const initialized = ref(false)
let refreshTimer = null

const actionLabels = {
  mark_done: '标记看过',
  mark_doing: '标记在看',
  error_search: '搜索无结果',
  error_api: '标记失败',
  sync_error: '同步失败',
  auth_failed: 'Cookie 无效',
  remove_wish: '移出想看',
  remove_doing: '移出在看',
  skip_deleted: '跳过已删除',
  repair_subject: '修正条目',
}

const dashStats = computed(() => {
  const src = status.value.item_stats || status.value.stats || {}
  return {
    done: Number(src.done || 0),
    doing: Number(src.doing || 0),
    failed: Number(src.failed || 0),
  }
})

const lastTs = computed(() => status.value.last_run_at || status.value.last_sync_time || 0)

const fullRunTime = computed(() => {
  return lastTs.value ? new Date(lastTs.value).toLocaleString('zh-CN', { hour12: false }) : ''
})

const shortRunTime = computed(() => {
  const ts = lastTs.value
  if (!ts) return ''
  const diffSec = Math.max(0, Math.floor((Date.now() - ts) / 1000))
  if (diffSec < 60) return '刚刚'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
})

function formatRecentDetail(detail) {
  const raw = String(detail || '').trim()
  if (!raw) return ''
  const epMatch = raw.match(/\bep=(\d+\/\d+)\b/)
  const sidMatch = raw.match(/(?:豆瓣ID=|sid=)(\d{6,10})/)
  const parts = []
  if (epMatch) parts.push(`${epMatch[1]} 集`)
  if (sidMatch) parts.push(`豆瓣 ${sidMatch[1]}`)
  if (parts.length) return parts.join(' · ')
  return raw
}

async function load() {
  if (!props.api) return
  loading.value = true
  try {
    status.value = await props.api.get(`${apiBase.value}/status`)
    const res = await props.api.get(`${apiBase.value}/logs?limit=1`)
    const recent = res.items?.[0]
    if (recent) {
      const label = actionLabels[recent.action] || recent.action
      const detail = formatRecentDetail(recent.detail)
      recentText.value = [label, recent.series_title, detail].filter(Boolean).join(' · ')
    } else {
      recentText.value = ''
    }
  } catch {
    /* 静默保持上次数据 */
  } finally {
    loading.value = false
    initialized.value = true
  }
}

onMounted(() => {
  load()
  const sec = Number(props.config?.attrs?.refresh || 0)
  if (props.allowRefresh && sec > 0) {
    refreshTimer = setInterval(load, sec * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.fntv-dashboard {
  width: 100%;
}
.fntv-dash-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
  border: 1px solid rgba(var(--v-theme-primary), 0.24);
}
.fntv-dash-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.fntv-dash-kpi {
  border-radius: 8px;
  padding: 8px 6px;
  text-align: center;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.025);
}
.fntv-tabular {
  font-variant-numeric: tabular-nums;
}
</style>
