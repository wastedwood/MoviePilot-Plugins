<template>
  <v-card elevation="0" class="fntv-page">
    <v-card-item>
      <v-card-title>飞牛影视豆瓣同步 · 同步记录</v-card-title>
      <template #append>
        <v-btn
          v-if="showSwitch"
          class="mr-2"
          size="small"
          variant="tonal"
          color="info"
          prepend-icon="mdi-cog-outline"
          @click="emit('switch')"
        >
          查看配置
        </v-btn>
        <v-btn icon variant="text" color="primary" @click="emit('close')">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </template>
    </v-card-item>

    <v-card-text>
      <!-- 状态概览 -->
      <v-row dense class="mb-4">
        <v-col cols="6" md="2">
          <div class="text-caption text-medium-emphasis">运行状态</div>
          <div class="text-body-1 font-weight-bold">
            <v-chip :color="status.enabled ? 'success' : 'grey'" size="small" label>
              {{ status.enabled ? '已启用' : '已停用' }}
            </v-chip>
          </div>
        </v-col>
        <v-col cols="6" md="3">
          <div class="text-caption text-medium-emphasis">上次同步</div>
          <div class="text-body-1 font-weight-bold">{{ fmtMs(status.last_sync_time) || '从未同步' }}</div>
        </v-col>
        <v-col cols="6" md="2">
          <div class="text-caption text-medium-emphasis">Cookie 来源</div>
          <div class="text-body-1 font-weight-bold">{{ sourceLabels[status.cookie_source] || '未配置' }}</div>
        </v-col>
        <v-col cols="3" md="2">
          <div class="text-caption text-medium-emphasis">已完成</div>
          <div class="text-body-1 font-weight-bold text-success">{{ status.stats?.done ?? 0 }}</div>
        </v-col>
        <v-col cols="3" md="3" class="text-right">
          <div class="text-caption text-medium-emphasis">失败</div>
          <div class="text-body-1 font-weight-bold" :class="{ 'text-error': (status.stats?.failed ?? 0) > 0 }">
            {{ status.stats?.failed ?? 0 }}
          </div>
        </v-col>
      </v-row>

      <!-- 同步操作 -->
      <div class="d-flex align-center mb-4">
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-sync"
          :loading="syncing"
          :disabled="!status.selected_user"
          @click="syncNow"
        >
          {{ syncing ? '同步中…' : '立即同步' }}
        </v-btn>
        <span v-if="syncMessage" class="ml-4 text-body-2 text-medium-emphasis">{{ syncMessage }}</span>
      </div>

      <!-- 日志筛选 -->
      <v-row dense class="align-center mb-2">
        <v-col cols="12" md="3">
          <v-select
            v-model="filterAction"
            label="动作"
            :items="actionItems"
            item-title="title"
            item-value="value"
            density="compact"
            variant="outlined"
            hide-details
            @update:model-value="reload"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            v-model="filterKeyword"
            label="按片名或详情搜索"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @keyup.enter="reload"
            @click:clear="reload"
          />
        </v-col>
        <v-col cols="12" md="3" class="text-md-right">
          <v-btn size="small" variant="tonal" prepend-icon="mdi-magnify" @click="reload">查询</v-btn>
        </v-col>
      </v-row>

      <!-- 日志表 -->
      <v-table v-if="logs.length" hover density="compact">
        <thead>
          <tr>
            <th class="text-left">时间</th>
            <th class="text-left">动作</th>
            <th class="text-left">条目</th>
            <th class="text-left">详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td class="text-no-wrap">{{ fmtSec(log.created_at) }}</td>
            <td class="text-no-wrap">
              <v-chip :color="actionColors[log.action] || 'default'" size="small" label>
                {{ actionLabels[log.action] || log.action }}
              </v-chip>
            </td>
            <td>{{ log.series_title || '-' }}</td>
            <td class="text-medium-emphasis">{{ log.detail || '' }}</td>
          </tr>
        </tbody>
      </v-table>
      <div v-else class="text-center text-medium-emphasis py-8">暂无同步记录</div>

      <!-- 分页 -->
      <div v-if="total > limit" class="d-flex align-center justify-center mt-2">
        <v-btn size="small" variant="text" :disabled="offset === 0" @click="turnPage(-1)">
          <v-icon>mdi-chevron-left</v-icon>上一页
        </v-btn>
        <span class="mx-2 text-body-2">{{ page }} / {{ pageCount }} 页 · 共 {{ total }} 条</span>
        <v-btn size="small" variant="text" :disabled="offset + limit >= total" @click="turnPage(1)">
          下一页<v-icon>mdi-chevron-right</v-icon>
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  api: { type: Object, default: () => null },
  showSwitch: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'switch'])

const status = ref({ running: false, enabled: false, selected_user: '', cookie_source: 'none', last_sync_time: 0, stats: {} })
const logs = ref([])
const total = ref(0)
const limit = 20
const offset = ref(0)
const filterAction = ref('')
const filterKeyword = ref('')
const syncing = ref(false)
const syncMessage = ref('')
let pollTimer = null

const actionLabels = {
  mark_done: '标记看过',
  mark_doing: '标记在看',
  skip_done: '跳过（已同步）',
  skip_special: '跳过（特别篇）',
  skip_middle: '跳过（中间集）',
  error_search: '失败（搜索无结果）',
  error_api: '失败（标记失败）',
  auth_failed: 'Cookie 无效',
  no_new_records: '无新增播放',
  no_change_skip: '播放无变化',
  all_filtered: '进度均为 0',
  remove_wish: '移出想看',
  repair_subject: '修正豆瓣条目',
}

const actionColors = {
  mark_done: 'success',
  mark_doing: 'info',
  error_search: 'warning',
  error_api: 'warning',
  auth_failed: 'error',
  remove_wish: 'info',
}

const sourceLabels = { manual: '手动 Cookie', cookiecloud: 'CookieCloud', none: '未配置' }

const actionItems = [
  { title: '全部动作', value: '' },
  ...Object.entries(actionLabels).map(([value, title]) => ({ title, value })),
]

const page = computed(() => Math.floor(offset.value / limit) + 1)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / limit)))

function fmtMs(ts) {
  return ts ? fmtSec(Math.floor(ts / 1000)) : ''
}

function fmtSec(ts) {
  return ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : ''
}

async function loadStatus() {
  if (!props.api) return
  try {
    status.value = await props.api.get('plugin/FntvDoubanSync/status')
    if (status.value.running) {
      syncing.value = true
      ensurePolling()
    }
  } catch {
    /* 宿主不可达时保持上次状态 */
  }
}

async function loadLogs() {
  if (!props.api) return
  const params = new URLSearchParams({ limit, offset: offset.value })
  if (filterAction.value) params.set('action', filterAction.value)
  if (filterKeyword.value) params.set('keyword', filterKeyword.value)
  try {
    const res = await props.api.get(`plugin/FntvDoubanSync/logs?${params}`)
    logs.value = res.items || []
    total.value = res.total || 0
  } catch {
    /* 忽略瞬时网络错误 */
  }
}

function reload() {
  offset.value = 0
  loadLogs()
}

function turnPage(dir) {
  offset.value = Math.max(0, Math.min(offset.value + dir * limit, Math.max(0, total.value - 1)))
  loadLogs()
}

async function syncNow() {
  if (!props.api) return
  syncMessage.value = ''
  try {
    const res = await props.api.post('plugin/FntvDoubanSync/sync/run')
    if (!res.ok) {
      syncMessage.value = res.message || '同步正在进行中'
      return
    }
    syncing.value = true
    ensurePolling()
  } catch (e) {
    syncMessage.value = `请求失败：${e.message || e}`
  }
}

function ensurePolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    try {
      status.value = await props.api.get('plugin/FntvDoubanSync/status')
      if (!status.value.running) {
        stopPolling()
        syncing.value = false
        await loadLogs()
      }
    } catch {
      stopPolling()
      syncing.value = false
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  loadStatus()
  loadLogs()
})

onUnmounted(stopPolling)
</script>
