<template>
  <v-card elevation="0" class="fntv-page">
    <v-card-item class="pb-2">
      <template #prepend>
        <v-avatar color="primary" variant="tonal" size="36" rounded="lg">
          <v-icon size="20">mdi-history</v-icon>
        </v-avatar>
      </template>
      <v-card-title class="text-h6 font-weight-bold">飞牛影视豆瓣同步 · 同步记录</v-card-title>
      <v-card-subtitle>查看实时状态、同步摘要与历史处理明细</v-card-subtitle>
      <template #append>
        <v-btn
          v-if="canSwitch"
          class="mr-2"
          size="small"
          variant="tonal"
          color="info"
          prepend-icon="mdi-cog-outline"
          @click="emit('switch')"
        >
          插件配置
        </v-btn>
        <v-btn icon variant="text" color="secondary" size="small" @click="emit('close')">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </template>
    </v-card-item>

    <v-divider />

    <v-card-text class="pt-4">
      <!-- 状态概览卡片 -->
      <v-row dense class="mb-4">
        <v-col cols="6" md="3">
          <v-sheet border rounded="lg" class="pa-3 fntv-kpi">
            <div class="d-flex align-center justify-space-between mb-1">
              <span class="text-caption text-medium-emphasis">运行状态</span>
              <v-chip
                :color="syncing || status.running ? 'info' : status.enabled ? 'success' : 'secondary'"
                size="x-small"
                variant="tonal"
                label
              >
                {{ syncing || status.running ? '同步中' : status.enabled ? '已启用' : '已停用' }}
              </v-chip>
            </div>
            <div class="text-body-2 font-weight-bold text-truncate" :title="lastRunDisplay">
              {{ lastRunDisplay }}
            </div>
            <div class="text-caption text-medium-emphasis">最近执行时间</div>
          </v-sheet>
        </v-col>

        <v-col cols="6" md="3">
          <v-sheet border rounded="lg" class="pa-3 fntv-kpi">
            <div class="text-caption text-medium-emphasis mb-1">已看过</div>
            <div class="text-h5 font-weight-bold text-success">{{ status.stats?.done ?? 0 }}</div>
            <div class="text-caption text-medium-emphasis">累计同步完成</div>
          </v-sheet>
        </v-col>

        <v-col cols="6" md="3">
          <v-sheet border rounded="lg" class="pa-3 fntv-kpi">
            <div class="text-caption text-medium-emphasis mb-1">在看</div>
            <div class="text-h5 font-weight-bold text-info">{{ status.stats?.doing ?? 0 }}</div>
            <div class="text-caption text-medium-emphasis">追更 / 未看完</div>
          </v-sheet>
        </v-col>

        <v-col cols="6" md="3">
          <v-sheet border rounded="lg" class="pa-3 fntv-kpi">
            <div class="text-caption text-medium-emphasis mb-1">异常条目</div>
            <div class="text-h5 font-weight-bold" :class="{ 'text-error': (status.stats?.failed ?? 0) > 0 }">
              {{ status.stats?.failed ?? 0 }}
            </div>
            <div class="text-caption text-medium-emphasis">搜索或标记失败</div>
          </v-sheet>
        </v-col>
      </v-row>

      <!-- 操作栏 -->
      <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-4">
        <div class="d-flex align-center flex-wrap ga-2">
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
          <v-btn
            variant="tonal"
            color="secondary"
            prepend-icon="mdi-refresh"
            :loading="refreshing"
            @click="refreshAll"
          >
            刷新
          </v-btn>
        </div>
        <div class="d-flex align-center flex-wrap ga-2">
          <v-chip size="small" variant="tonal" color="secondary" prepend-icon="mdi-key-outline">
            Cookie：{{ sourceLabels[status.cookie_source] || '未配置' }}
          </v-chip>
        </div>
      </div>

      <!-- 引导与运行反馈 -->
      <v-alert v-if="!status.selected_user" type="warning" variant="tonal" density="compact" class="mb-4">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2">
          <span>尚未选择飞牛影视用户，请先在配置中连接数据库并选择用户后再同步。</span>
          <v-btn v-if="canSwitch" size="x-small" color="warning" variant="flat" @click="emit('switch')">
            前往配置
          </v-btn>
        </div>
      </v-alert>

      <v-alert
        v-if="feedbackAlert"
        :type="feedbackAlert.type"
        variant="tonal"
        density="compact"
        class="mb-4 fntv-multiline"
      >
        {{ feedbackAlert.message }}
      </v-alert>

      <!-- 日志筛选 -->
      <v-row dense class="align-center mb-3">
        <v-col cols="12" sm="4" md="3">
          <v-select
            v-model="filterAction"
            label="筛选动作"
            :items="actionItems"
            item-title="title"
            item-value="value"
            density="compact"
            variant="outlined"
            hide-details
            @update:model-value="reload"
          />
        </v-col>
        <v-col cols="12" sm="6" md="7">
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
        <v-col cols="12" sm="2" md="2">
          <v-btn block height="40" variant="tonal" color="primary" prepend-icon="mdi-magnify" @click="reload">
            查询
          </v-btn>
        </v-col>
      </v-row>

      <!-- 日志表 -->
      <v-sheet v-if="logs.length" border rounded="lg" class="fntv-table-wrap">
        <v-table hover density="compact">
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
              <td class="text-no-wrap text-caption text-medium-emphasis">{{ fmtSec(log.created_at) }}</td>
              <td class="text-no-wrap">
                <v-chip :color="actionColors[log.action] || 'default'" size="x-small" variant="tonal" label>
                  {{ actionLabels[log.action] || log.action }}
                </v-chip>
              </td>
              <td class="font-weight-medium">{{ log.series_title || '-' }}</td>
              <td class="text-medium-emphasis text-body-2">
                <template v-for="(part, idx) in parseDetailParts(log.detail)" :key="idx">
                  <a
                    v-if="part.href"
                    :href="part.href"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="fntv-link"
                  >
                    {{ part.text }}
                  </a>
                  <span v-else>{{ part.text }}</span>
                </template>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-sheet>

      <v-sheet v-else border rounded="lg" class="text-center text-medium-emphasis py-10">
        <v-icon size="36" class="mb-2">mdi-text-box-search-outline</v-icon>
        <div class="text-body-2">暂无符合条件的同步记录</div>
      </v-sheet>

      <!-- 分页 -->
      <div v-if="total > limit" class="d-flex align-center justify-center ga-2 mt-3">
        <v-btn size="small" variant="text" :disabled="offset === 0" @click="turnPage(-1)">
          <v-icon start>mdi-chevron-left</v-icon>上一页
        </v-btn>
        <span class="text-body-2 text-medium-emphasis">第 {{ page }} / {{ pageCount }} 页 · 共 {{ total }} 条</span>
        <v-btn size="small" variant="text" :disabled="offset + limit >= total" @click="turnPage(1)">
          下一页<v-icon end>mdi-chevron-right</v-icon>
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
  show_switch: { type: Boolean, default: false },
  pluginId: { type: String, default: 'FntvDoubanSync' },
})

const emit = defineEmits(['close', 'switch'])

const canSwitch = computed(() => props.showSwitch || props.show_switch)
const apiBase = computed(() => `plugin/${props.pluginId || 'FntvDoubanSync'}`)

const status = ref({
  running: false,
  enabled: false,
  selected_user: '',
  cookie_source: 'none',
  last_sync_time: 0,
  last_run_at: 0,
  last_run_status: '',
  last_run_message: '',
  stats: {},
})
const logs = ref([])
const total = ref(0)
const limit = 20
const offset = ref(0)
const filterAction = ref('')
const filterKeyword = ref('')
const syncing = ref(false)
const refreshing = ref(false)
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
  sync_error: '同步失败',
  auth_failed: 'Cookie 无效',
  no_new_records: '无新增播放',
  no_change_skip: '播放无变化',
  all_filtered: '进度均为 0',
  remove_wish: '移出想看',
  remove_doing: '移出在看（已删）',
  skip_deleted: '跳过（已从飞牛删除）',
  repair_subject: '修正豆瓣条目',
}

const actionColors = {
  mark_done: 'success',
  mark_doing: 'info',
  error_search: 'warning',
  error_api: 'warning',
  sync_error: 'error',
  auth_failed: 'error',
  remove_wish: 'info',
  remove_doing: 'info',
  repair_subject: 'info',
}

const sourceLabels = { manual: '手动 Cookie', cookiecloud: 'CookieCloud', none: '未配置' }

const actionItems = [
  { title: '全部动作', value: '' },
  ...Object.entries(actionLabels).map(([value, title]) => ({ title, value })),
]

const page = computed(() => Math.floor(offset.value / limit) + 1)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / limit)))

const lastRunDisplay = computed(() => {
  const ts = status.value.last_run_at || status.value.last_sync_time
  return fmtMs(ts) || '从未同步'
})

const feedbackAlert = computed(() => {
  if (syncMessage.value) {
    return { type: 'info', message: syncMessage.value }
  }
  if (status.value.last_run_message) {
    const map = { error: 'error', warning: 'warning', success: 'success' }
    return {
      type: map[status.value.last_run_status] || 'info',
      message: `最近同步结果：${status.value.last_run_message}`,
    }
  }
  return null
})

function fmtMs(ts) {
  return ts ? fmtSec(Math.floor(ts / 1000)) : ''
}

function fmtSec(ts) {
  return ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : ''
}

function parseDetailParts(detail) {
  const text = String(detail || '')
  if (!text) return [{ text: '-', href: '' }]
  const regex = /(豆瓣ID=|sid=)?(\d{6,10})(\((?:done|doing)\))?/g
  const parts = []
  let lastIndex = 0
  let match
  while ((match = regex.exec(text)) !== null) {
    if (!match[1] && !match[3]) continue
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index), href: '' })
    }
    const prefix = match[1] || ''
    const sid = match[2]
    const suffix = match[3] || ''
    if (prefix) parts.push({ text: prefix, href: '' })
    parts.push({ text: sid, href: `https://movie.douban.com/subject/${sid}/` })
    if (suffix) parts.push({ text: suffix, href: '' })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), href: '' })
  }
  return parts.length ? parts : [{ text, href: '' }]
}

async function loadStatus() {
  if (!props.api) return
  try {
    status.value = await props.api.get(`${apiBase.value}/status`)
    if (status.value.running) {
      syncing.value = true
      ensurePolling()
    } else {
      syncing.value = false
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
    const res = await props.api.get(`${apiBase.value}/logs?${params}`)
    logs.value = res.items || []
    total.value = res.total || 0
  } catch {
    /* 忽略瞬时网络错误 */
  }
}

async function refreshAll() {
  refreshing.value = true
  try {
    await Promise.all([loadStatus(), loadLogs()])
  } finally {
    refreshing.value = false
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
    const res = await props.api.post(`${apiBase.value}/sync/run`)
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
      status.value = await props.api.get(`${apiBase.value}/status`)
      if (!status.value.running) {
        stopPolling()
        syncing.value = false
        syncMessage.value = ''
        await loadLogs()
      }
    } catch {
      stopPolling()
      syncing.value = false
    }
  }, 1500)
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

<style scoped>
.fntv-kpi {
  height: 100%;
}
.fntv-table-wrap {
  overflow-x: auto;
}
.fntv-multiline {
  white-space: pre-line;
}
.fntv-link {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  font-weight: 500;
}
.fntv-link:hover {
  text-decoration: underline;
}
</style>
