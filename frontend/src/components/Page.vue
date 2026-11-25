<template>
  <v-card elevation="0" class="fntv-shell">
    <!-- 固定顶栏 -->
    <div class="fntv-header px-4 py-3 d-flex align-center justify-space-between ga-3">
      <div class="d-flex align-center ga-3 fntv-min-0">
        <div class="fntv-icon-badge">
          <v-icon size="20">mdi-history</v-icon>
        </div>
        <div class="fntv-min-0">
          <div class="d-flex align-center flex-wrap ga-2">
            <span class="text-subtitle-1 font-weight-bold fntv-truncate">飞牛影视豆瓣同步</span>
            <span class="fntv-pill" :class="`fntv-pill--${runState.tone}`">
              {{ runState.label }}
            </span>
          </div>
          <div class="text-caption text-medium-emphasis fntv-truncate">
            实时状态、同步摘要与历史处理明细
          </div>
        </div>
      </div>

      <div class="d-flex align-center ga-2 flex-shrink-0">
        <v-btn
          v-if="canSwitch"
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-cog-outline"
          @click="emit('switch')"
        >
          插件配置
        </v-btn>
        <v-btn icon variant="text" color="secondary" size="small" @click="emit('close')">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </div>
    </div>

    <!-- 中间可滚动主体 -->
    <div class="fntv-body px-4 py-4">
      <!-- 4 列紧凑 KPI 网格 -->
      <div class="fntv-kpi-grid mb-3">
        <!-- 卡 1：最近同步 -->
        <div class="fntv-kpi">
          <div class="d-flex align-center justify-space-between ga-1 mb-1">
            <span class="text-caption text-medium-emphasis">最近同步</span>
            <span class="text-caption text-medium-emphasis">{{ sourceLabels[status.cookie_source] || '未配置' }}</span>
          </div>
          <div class="text-body-2 font-weight-bold fntv-tabular fntv-truncate" :title="lastRunFull">
            {{ lastRunShort }}
          </div>
          <div class="text-caption text-medium-emphasis fntv-truncate">
            {{ status.cron ? `定时 ${status.cron}` : '未配置周期' }}
          </div>
        </div>

        <!-- 卡 2：已看过（可下钻） -->
        <button
          type="button"
          class="fntv-kpi fntv-kpi--btn"
          :class="{ 'fntv-kpi--active': viewMode === 'items' && itemFilter === 'done' }"
          @click="drillToItems('done')"
        >
          <div class="d-flex align-center justify-space-between ga-1">
            <span class="text-caption text-medium-emphasis">已看过</span>
            <span class="text-caption text-medium-emphasis">查看 ›</span>
          </div>
          <div class="fntv-kpi-num text-success fntv-tabular">{{ displayStats.done }}</div>
          <div class="text-caption text-medium-emphasis">累计同步完成</div>
        </button>

        <!-- 卡 3：在看（可下钻） -->
        <button
          type="button"
          class="fntv-kpi fntv-kpi--btn"
          :class="{ 'fntv-kpi--active': viewMode === 'items' && itemFilter === 'doing' }"
          @click="drillToItems('doing')"
        >
          <div class="d-flex align-center justify-space-between ga-1">
            <span class="text-caption text-medium-emphasis">在看</span>
            <span class="text-caption text-medium-emphasis">查看 ›</span>
          </div>
          <div class="fntv-kpi-num text-info fntv-tabular">{{ displayStats.doing }}</div>
          <div class="text-caption text-medium-emphasis">追更 / 未看完</div>
        </button>

        <!-- 卡 4：异常条目（可下钻） -->
        <button
          type="button"
          class="fntv-kpi fntv-kpi--btn"
          :class="{ 'fntv-kpi--active': viewMode === 'items' && itemFilter === 'failed' }"
          @click="drillToItems('failed')"
        >
          <div class="d-flex align-center justify-space-between ga-1">
            <span class="text-caption text-medium-emphasis">异常条目</span>
            <span class="text-caption text-medium-emphasis">排查 ›</span>
          </div>
          <div
            class="fntv-kpi-num fntv-tabular"
            :class="displayStats.failed > 0 ? 'text-error' : 'text-medium-emphasis'"
          >
            {{ displayStats.failed }}
          </div>
          <div class="text-caption text-medium-emphasis">搜索或标记失败</div>
        </button>
      </div>

      <!-- 操作栏 + 主视图切换 -->
      <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
        <div class="d-flex align-center flex-wrap ga-2">
          <v-btn
            color="primary"
            variant="flat"
            size="small"
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
            size="small"
            prepend-icon="mdi-refresh"
            :loading="refreshing"
            @click="refreshAll"
          >
            刷新
          </v-btn>
        </div>

        <div class="fntv-segmented" role="tablist" aria-label="记录视图切换">
          <button
            type="button"
            class="fntv-seg-btn"
            :class="{ 'fntv-seg-btn--active': viewMode === 'logs' }"
            @click="switchMode('logs')"
          >
            同步日志
            <span class="fntv-seg-count fntv-tabular">{{ logTotalLabel }}</span>
          </button>
          <button
            type="button"
            class="fntv-seg-btn"
            :class="{ 'fntv-seg-btn--active': viewMode === 'items' }"
            @click="switchMode('items')"
          >
            条目总览
            <span class="fntv-seg-count fntv-tabular">{{ displayStats.total }}</span>
          </button>
        </div>
      </div>

      <!-- 未选择用户引导 -->
      <div v-if="!status.selected_user" class="fntv-banner fntv-banner--warning mb-3">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2">
          <div class="d-flex align-center ga-2">
            <v-icon size="16" color="warning">mdi-alert-outline</v-icon>
            <span>尚未选择飞牛影视用户，请先在配置中连接数据库并选择用户后再同步。</span>
          </div>
          <v-btn v-if="canSwitch" size="x-small" color="warning" variant="flat" @click="emit('switch')">
            前往配置
          </v-btn>
        </div>
      </div>

      <!-- 可折叠单行「最近同步结果」摘要条 -->
      <div v-if="feedbackBanner" class="fntv-banner mb-3" :class="`fntv-banner--${feedbackBanner.tone}`">
        <div class="d-flex align-center justify-space-between ga-2">
          <div class="d-flex align-center ga-2 fntv-min-0">
            <v-icon size="16" :color="feedbackBanner.iconColor">{{ feedbackBanner.icon }}</v-icon>
            <span class="font-weight-medium fntv-truncate">{{ feedbackBanner.summary }}</span>
          </div>
          <button
            v-if="feedbackBanner.sections.length"
            type="button"
            class="fntv-collapse-btn"
            @click="summaryOpen = !summaryOpen"
          >
            <span>{{ summaryOpen ? '收起明细' : '展开明细' }}</span>
            <v-icon size="16">{{ summaryOpen ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
          </button>
        </div>

        <div v-if="summaryOpen && feedbackBanner.sections.length" class="fntv-banner-details">
          <div v-for="(sec, idx) in feedbackBanner.sections" :key="idx" class="fntv-banner-sec">
            <div class="font-weight-bold mb-1">{{ sec.heading }}</div>
            <ul class="fntv-banner-list">
              <li v-for="(line, lIdx) in sec.items" :key="lIdx">{{ line }}</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- 单行紧凑筛选栏 -->
      <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
        <div class="d-flex align-center flex-wrap ga-1">
          <button
            v-for="chip in activeChips"
            :key="chip.value"
            type="button"
            class="fntv-chip"
            :class="{ 'fntv-chip--active': currentFilterValue === chip.value }"
            @click="selectChip(chip.value)"
          >
            {{ chip.label }}
          </button>
        </div>

        <div class="fntv-search-box">
          <v-icon size="15" class="text-medium-emphasis flex-shrink-0">mdi-magnify</v-icon>
          <input
            v-model="filterKeyword"
            type="text"
            class="fntv-search-input"
            placeholder="搜索片名或豆瓣 ID…"
            @input="onSearchInput"
            @keyup.enter="reload"
          />
          <button
            v-if="filterKeyword"
            type="button"
            class="fntv-search-clear"
            title="清空搜索"
            @click="clearSearch"
          >
            <v-icon size="14">mdi-close</v-icon>
          </button>
        </div>
      </div>

      <!-- 日志表格 -->
      <div v-if="viewMode === 'logs'" class="fntv-table-card">
        <div v-if="logs.length" class="fntv-table-scroll">
          <table class="fntv-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>动作</th>
                <th>条目</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs" :key="log.id">
                <td class="fntv-td-nowrap text-medium-emphasis fntv-tabular" :title="fmtSec(log.created_at)">
                  {{ fmtShortSec(log.created_at) }}
                </td>
                <td class="fntv-td-nowrap">
                  <span class="fntv-pill" :class="`fntv-pill--${actionTone(log.action)}`">
                    {{ actionLabels[log.action] || log.action }}
                  </span>
                </td>
                <td>
                  <div class="d-flex align-center flex-wrap ga-1">
                    <span class="font-weight-medium">{{ splitTitle(log.series_title, log.season_number).title }}</span>
                    <span
                      v-if="splitTitle(log.series_title, log.season_number).season"
                      class="fntv-tag"
                    >
                      {{ splitTitle(log.series_title, log.season_number).season }}
                    </span>
                  </div>
                </td>
                <td>
                  <div class="d-flex align-center flex-wrap ga-1">
                    <span v-if="parseLogDetail(log.detail, log.action).note" class="text-medium-emphasis">
                      {{ parseLogDetail(log.detail, log.action).note }}
                    </span>
                    <span v-if="parseLogDetail(log.detail, log.action).ep" class="fntv-tag fntv-tabular">
                      {{ parseLogDetail(log.detail, log.action).ep }}
                    </span>
                    <a
                      v-for="link in parseLogDetail(log.detail, log.action).links"
                      :key="link.key"
                      :href="link.href"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="fntv-douban-link"
                    >
                      {{ link.label }} ↗
                    </a>
                    <span
                      v-if="!parseLogDetail(log.detail, log.action).note && !parseLogDetail(log.detail, log.action).ep && !parseLogDetail(log.detail, log.action).links.length"
                      class="text-medium-emphasis"
                    >
                      -
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="fntv-empty">
          <v-icon size="32" class="mb-2 text-medium-emphasis">mdi-text-box-search-outline</v-icon>
          <div>暂无符合条件的同步记录</div>
        </div>
      </div>

      <!-- 条目总览表格 -->
      <div v-else class="fntv-table-card">
        <div v-if="items.length" class="fntv-table-scroll">
          <table class="fntv-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>条目</th>
                <th>进度 / 说明</th>
                <th>豆瓣条目</th>
                <th>最近同步</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="`${item.media_type}-${item.entry_guid}-${item.season_number}`">
                <td class="fntv-td-nowrap">
                  <span class="fntv-pill" :class="`fntv-pill--${itemStatusTone(item.status)}`">
                    {{ itemStatusLabel(item.status) }}
                  </span>
                </td>
                <td>
                  <div class="d-flex align-center flex-wrap ga-1">
                    <span class="font-weight-medium">{{ splitTitle(item.series_title, item.season_number).title }}</span>
                    <span
                      v-if="item.media_type === 'episode' && splitTitle(item.series_title, item.season_number).season"
                      class="fntv-tag"
                    >
                      {{ splitTitle(item.series_title, item.season_number).season }}
                    </span>
                    <span v-else-if="item.media_type === 'movie'" class="fntv-tag">电影</span>
                  </div>
                </td>
                <td>
                  <div v-if="item.status === 'doing' && item.total_episodes > 0" class="fntv-progress-wrap">
                    <div class="fntv-progress-track">
                      <div
                        class="fntv-progress-bar"
                        :style="{ width: `${Math.min(100, Math.round((item.max_ep_watched / item.total_episodes) * 100))}%` }"
                      />
                    </div>
                    <span class="fntv-tabular font-weight-medium">
                      {{ item.max_ep_watched }}/{{ item.total_episodes }} 集
                    </span>
                  </div>
                  <span
                    v-else-if="item.status === 'failed'"
                    class="text-error"
                  >
                    {{ formatFailureReason(item.last_detail) }}
                  </span>
                  <span v-else-if="item.media_type === 'episode' && item.total_episodes > 0" class="text-medium-emphasis fntv-tabular">
                    {{ item.max_ep_watched || item.total_episodes }}/{{ item.total_episodes }} 集
                  </span>
                  <span v-else class="text-medium-emphasis">
                    {{ item.media_type === 'movie' ? '电影已完成' : '-' }}
                  </span>
                </td>
                <td class="fntv-td-nowrap">
                  <a
                    v-if="item.douban_subject_id"
                    :href="`https://movie.douban.com/subject/${item.douban_subject_id}/`"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="fntv-douban-link"
                  >
                    豆瓣 {{ item.douban_subject_id }} ↗
                  </a>
                  <span v-else class="text-medium-emphasis">-</span>
                </td>
                <td class="fntv-td-nowrap text-medium-emphasis fntv-tabular" :title="fmtSec(item.last_synced_at)">
                  {{ fmtShortSec(item.last_synced_at) || '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="fntv-empty">
          <v-icon size="32" class="mb-2 text-medium-emphasis">mdi-movie-search-outline</v-icon>
          <div>暂无符合条件的同步条目</div>
        </div>
      </div>

      <!-- 紧凑分页条 -->
      <div v-if="currentTotal > 0" class="d-flex align-center justify-space-between flex-wrap ga-2 mt-3 text-caption text-medium-emphasis">
        <span class="fntv-tabular">第 {{ page }} / {{ pageCount }} 页 · 共 {{ currentTotal }} 条</span>
        <div v-if="currentTotal > limit" class="d-flex align-center ga-1">
          <v-btn size="x-small" variant="tonal" color="secondary" :disabled="offset === 0" @click="turnPage(-1)">
            上一页
          </v-btn>
          <v-btn size="x-small" variant="tonal" color="secondary" :disabled="offset + limit >= currentTotal" @click="turnPage(1)">
            下一页
          </v-btn>
        </div>
      </div>
    </div>
  </v-card>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

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
  cron: '',
  selected_user: '',
  cookie_source: 'none',
  last_sync_time: 0,
  last_run_at: 0,
  last_run_status: '',
  last_run_message: '',
  stats: {},
  item_stats: null,
})

const viewMode = ref('logs') // 'logs' | 'items'
const logs = ref([])
const logsTotal = ref(0)
const items = ref([])
const itemsTotal = ref(0)
const itemsSummary = ref(null)

const limit = 20
const offset = ref(0)
const filterAction = ref('')
const itemFilter = ref('')
const filterKeyword = ref('')
const syncing = ref(false)
const refreshing = ref(false)
const syncMessage = ref('')
const summaryOpen = ref(false)
let pollTimer = null
let searchTimer = null

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

const sourceLabels = { manual: '手动 Cookie', cookiecloud: 'CookieCloud', none: '未配置' }

const logChips = [
  { label: '全部', value: '' },
  { label: '看过', value: 'mark_done' },
  { label: '在看', value: 'mark_doing' },
  { label: '移出/修正', value: 'remove_doing,remove_wish,repair_subject' },
  { label: '失败异常', value: 'error_search,error_api,sync_error,auth_failed' },
  { label: '跳过', value: 'skip_done,skip_special,skip_middle,skip_deleted' },
]

const displayStats = computed(() => {
  const src = itemsSummary.value || status.value.item_stats || status.value.stats || {}
  return {
    total: Number(src.total || 0),
    done: Number(src.done || 0),
    doing: Number(src.doing || 0),
    failed: Number(src.failed || 0),
  }
})

const itemChips = computed(() => [
  { label: '全部', value: '' },
  { label: `在看 (${displayStats.value.doing})`, value: 'doing' },
  { label: `异常 (${displayStats.value.failed})`, value: 'failed' },
  { label: `已看过 (${displayStats.value.done})`, value: 'done' },
])

const activeChips = computed(() => (viewMode.value === 'logs' ? logChips : itemChips.value))
const currentFilterValue = computed(() => (viewMode.value === 'logs' ? filterAction.value : itemFilter.value))
const currentTotal = computed(() => (viewMode.value === 'logs' ? logsTotal.value : itemsTotal.value))
const logTotalLabel = computed(() => (logsTotal.value > 0 ? String(logsTotal.value) : ''))

const page = computed(() => Math.floor(offset.value / limit) + 1)
const pageCount = computed(() => Math.max(1, Math.ceil(currentTotal.value / limit)))

const runState = computed(() => {
  if (syncing.value || status.value.running) return { label: '同步中', tone: 'info' }
  if (status.value.enabled) return { label: '已启用', tone: 'success' }
  return { label: '已停用', tone: 'neutral' }
})

const lastRunTsSec = computed(() => {
  const ts = status.value.last_run_at || status.value.last_sync_time
  return ts ? Math.floor(ts / 1000) : 0
})

const lastRunFull = computed(() => fmtSec(lastRunTsSec.value) || '从未同步')
const lastRunShort = computed(() => fmtShortSec(lastRunTsSec.value) || '从未同步')

watch(
  () => status.value.last_run_status,
  val => {
    summaryOpen.value = val === 'error' || val === 'warning'
  },
  { immediate: true },
)

const feedbackBanner = computed(() => {
  if (syncMessage.value) {
    return {
      tone: 'info',
      icon: 'mdi-information-outline',
      iconColor: 'info',
      summary: syncMessage.value,
      sections: [],
    }
  }
  const raw = String(status.value.last_run_message || '').trim()
  if (!raw) return null

  const statusTone = status.value.last_run_status
  const tone = statusTone === 'error' ? 'error' : statusTone === 'warning' ? 'warning' : statusTone === 'success' ? 'success' : 'info'
  const icon = tone === 'error' ? 'mdi-alert-circle-outline' : tone === 'warning' ? 'mdi-alert-outline' : tone === 'success' ? 'mdi-check-circle-outline' : 'mdi-information-outline'

  const lines = raw.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
  if (lines.length <= 1) {
    return {
      tone,
      icon,
      iconColor: tone,
      summary: `最近同步：${raw}`,
      sections: [],
    }
  }

  const sections = []
  let footer = ''
  const sectionCounts = []
  let currentSec = null
  for (const line of lines) {
    if (line.startsWith('•')) {
      if (currentSec) currentSec.items.push(line.replace(/^•\s*/, ''))
    } else if (/^本次共处理/.test(line) || /^本次无/.test(line)) {
      footer = line
    } else {
      currentSec = { heading: line, items: [] }
      sections.push(currentSec)
      const cleaned = line.replace(/^[^\u4e00-\u9fa5A-Za-z0-9]+/, '').trim()
      const m = cleaned.match(/^(.+?)（(\d+)）$/)
      sectionCounts.push(m ? `${m[1]} ${m[2]}` : cleaned)
    }
  }
  const timePrefix = lastRunShort.value && lastRunShort.value !== '从未同步' ? `（${lastRunShort.value}）` : ''
  const summaryParts = [
    `最近同步${tone === 'error' ? '失败' : tone === 'warning' ? '有异常' : '完成'}${timePrefix}`,
    footer,
    sectionCounts.length ? sectionCounts.join(' · ') : '',
  ].filter(Boolean)

  return {
    tone,
    icon,
    iconColor: tone,
    summary: summaryParts.join(' · '),
    sections,
  }
})

function fmtSec(ts) {
  return ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : ''
}

function fmtShortSec(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const md = `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  return d.getFullYear() === now.getFullYear() ? md : `${d.getFullYear()}-${md}`
}

function actionTone(action) {
  if (action === 'mark_done') return 'success'
  if (action === 'mark_doing' || action === 'repair_subject') return 'info'
  if (action === 'remove_doing' || action === 'remove_wish') return 'neutral'
  if (action === 'error_search' || action === 'error_api' || action === 'sync_error' || action === 'auth_failed') return 'error'
  return 'muted'
}

function itemStatusTone(st) {
  if (st === 'done') return 'success'
  if (st === 'doing') return 'info'
  if (st === 'failed') return 'error'
  return 'neutral'
}

function itemStatusLabel(st) {
  if (st === 'done') return '已看过'
  if (st === 'doing') return '在看'
  if (st === 'failed') return '异常'
  return st || '-'
}

function splitTitle(rawTitle, seasonNumber) {
  const text = String(rawTitle || '').trim()
  if (!text) return { title: '-', season: '' }
  const trailing = text.match(/^(.*?)\s+S(\d+)$/i)
  if (trailing && trailing[1]) {
    return { title: trailing[1], season: `S${trailing[2]}` }
  }
  const sNum = Number(seasonNumber || 0)
  if (sNum > 0 && !/第\s*[一二三四五六七八九十\d]+\s*季|Season\s*\d+/i.test(text)) {
    return { title: text, season: `S${sNum}` }
  }
  return { title: text, season: '' }
}

function parseLogDetail(detail, action) {
  let text = String(detail || '').trim()
  if (!text) return { note: '', ep: '', links: [] }

  let ep = ''
  text = text.replace(/\bep=(\d+\/\d+)\b/, (_, val) => {
    ep = `${val} 集`
    return ''
  })

  const links = []
  let idx = 0
  text = text.replace(/(豆瓣ID=|sid=)?(\d{6,10})(\((?:done|doing)\))?/g, (full, prefix, sid, suffix) => {
    if (!prefix && !suffix && action !== 'repair_subject') return full
    idx += 1
    const suffixText = suffix === '(done)' ? ' 看过' : suffix === '(doing)' ? ' 在看' : ''
    links.push({
      key: `${sid}-${idx}`,
      label: `豆瓣 ${sid}${suffixText}`,
      href: `https://movie.douban.com/subject/${sid}/`,
    })
    return ' '
  })

  text = text.replace(/豆瓣ID\s*/g, '').replace(/[，,]\s*/g, ' ').replace(/\s{2,}/g, ' ').trim()
  if (action === 'remove_doing') {
    text = text.replace(/移出在看/g, '').trim()
  }
  if (action === 'repair_subject' && text === '→') {
    text = '条目已更新'
  } else {
    text = text.replace(/^→\s*|\s*→$/g, '').trim()
  }

  return { note: text, ep, links }
}

function formatFailureReason(detail) {
  const text = String(detail || '').trim()
  if (!text) return '搜索或标记失败'
  return text.replace(/\s*sid=\d+\b/g, '').trim() || text
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
    logsTotal.value = res.total || 0
  } catch {
    /* 忽略瞬时网络错误 */
  }
}

async function loadItems() {
  if (!props.api) return
  const params = new URLSearchParams({ limit, offset: offset.value })
  if (itemFilter.value) params.set('status', itemFilter.value)
  if (filterKeyword.value) params.set('keyword', filterKeyword.value)
  try {
    const res = await props.api.get(`${apiBase.value}/items?${params}`)
    items.value = res.items || []
    itemsTotal.value = res.total || 0
    if (res.summary) itemsSummary.value = res.summary
  } catch {
    /* 忽略瞬时网络错误 */
  }
}

function loadCurrentList() {
  return viewMode.value === 'logs' ? loadLogs() : loadItems()
}

async function refreshAll() {
  refreshing.value = true
  try {
    await Promise.all([loadStatus(), loadCurrentList()])
  } finally {
    refreshing.value = false
  }
}

function reload() {
  offset.value = 0
  loadCurrentList()
}

function switchMode(mode) {
  if (viewMode.value === mode) return
  viewMode.value = mode
  offset.value = 0
  loadCurrentList()
}

function drillToItems(targetStatus) {
  viewMode.value = 'items'
  itemFilter.value = itemFilter.value === targetStatus ? '' : targetStatus
  offset.value = 0
  loadItems()
}

function selectChip(val) {
  if (viewMode.value === 'logs') filterAction.value = val
  else itemFilter.value = val
  reload()
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 250)
}

function clearSearch() {
  clearTimeout(searchTimer)
  filterKeyword.value = ''
  reload()
}

function turnPage(dir) {
  offset.value = Math.max(0, Math.min(offset.value + dir * limit, Math.max(0, currentTotal.value - 1)))
  loadCurrentList()
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
        await Promise.all([loadLogs(), viewMode.value === 'items' ? loadItems() : Promise.resolve()])
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

onUnmounted(() => {
  stopPolling()
  clearTimeout(searchTimer)
})
</script>

<style scoped>
.fntv-shell {
  display: flex;
  flex-direction: column;
  max-height: min(88vh, 920px);
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
}
.fntv-header {
  flex-shrink: 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgb(var(--v-theme-surface));
}
.fntv-body {
  flex: 1 1 auto;
  overflow-y: auto;
  min-height: 0;
}
.fntv-min-0 {
  min-width: 0;
}
.fntv-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fntv-tabular {
  font-variant-numeric: tabular-nums;
}
.fntv-icon-badge {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
  border: 1px solid rgba(var(--v-theme-primary), 0.24);
}
.fntv-kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
@media (min-width: 560px) {
  .fntv-kpi-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.fntv-kpi {
  border-radius: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.025);
  text-align: left;
  min-width: 0;
  transition: border-color 150ms ease, background-color 150ms ease, box-shadow 150ms ease;
}
.fntv-kpi--btn {
  cursor: pointer;
}
.fntv-kpi--btn:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
  background: rgba(var(--v-theme-primary), 0.05);
}
.fntv-kpi--active {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.28);
}
.fntv-kpi-num {
  font-size: 1.4rem;
  line-height: 1.25;
  font-weight: 700;
  margin: 2px 0;
}
.fntv-segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.03);
  gap: 2px;
}
.fntv-seg-btn {
  border: 0;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.78rem;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: background-color 150ms ease, color 150ms ease;
}
.fntv-seg-btn--active {
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
.fntv-seg-count {
  font-size: 0.74rem;
  opacity: 0.7;
}
.fntv-banner {
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 0.8rem;
  border: 1px solid rgba(var(--v-theme-info), 0.28);
  background: rgba(var(--v-theme-info), 0.09);
}
.fntv-banner--success {
  border-color: rgba(var(--v-theme-success), 0.28);
  background: rgba(var(--v-theme-success), 0.09);
}
.fntv-banner--warning {
  border-color: rgba(var(--v-theme-warning), 0.34);
  background: rgba(var(--v-theme-warning), 0.11);
}
.fntv-banner--error {
  border-color: rgba(var(--v-theme-error), 0.3);
  background: rgba(var(--v-theme-error), 0.09);
}
.fntv-collapse-btn {
  border: 0;
  background: transparent;
  color: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0.9;
}
.fntv-banner-details {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.fntv-banner-list {
  margin: 0;
  padding-left: 16px;
  line-height: 1.55;
}
.fntv-chip {
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.76rem;
  font-weight: 500;
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.75);
  background: rgba(var(--v-theme-on-surface), 0.05);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  transition: all 140ms ease;
}
.fntv-chip:hover {
  border-color: rgba(var(--v-theme-primary), 0.4);
}
.fntv-chip--active {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
  border-color: rgba(var(--v-theme-primary), 0.36);
  font-weight: 600;
}
.fntv-search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.18);
  background: rgb(var(--v-theme-surface));
  min-width: 210px;
  flex: 1 1 210px;
  max-width: 280px;
}
.fntv-search-box:focus-within {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.16);
}
.fntv-search-input {
  border: 0;
  outline: none;
  background: transparent;
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.8rem;
  width: 100%;
  min-width: 0;
}
.fntv-search-clear {
  border: 0;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.55);
  cursor: pointer;
  display: inline-flex;
  padding: 0;
}
.fntv-table-card {
  border-radius: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
}
.fntv-table-scroll {
  overflow-x: auto;
}
.fntv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  text-align: left;
}
.fntv-table thead th {
  padding: 9px 12px;
  font-size: 0.76rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.65);
  background: rgba(var(--v-theme-on-surface), 0.03);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  white-space: nowrap;
}
.fntv-table tbody td {
  padding: 9px 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  vertical-align: middle;
}
.fntv-table tbody tr:last-child td {
  border-bottom: 0;
}
.fntv-table tbody tr:hover {
  background: rgba(var(--v-theme-on-surface), 0.03);
}
.fntv-td-nowrap {
  white-space: nowrap;
}
.fntv-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.35;
  white-space: nowrap;
}
.fntv-pill--success {
  color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.12);
  border: 1px solid rgba(var(--v-theme-success), 0.25);
}
.fntv-pill--info {
  color: rgb(var(--v-theme-info));
  background: rgba(var(--v-theme-info), 0.12);
  border: 1px solid rgba(var(--v-theme-info), 0.25);
}
.fntv-pill--error {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.12);
  border: 1px solid rgba(var(--v-theme-error), 0.25);
}
.fntv-pill--neutral {
  color: rgba(var(--v-theme-on-surface), 0.78);
  background: rgba(var(--v-theme-on-surface), 0.07);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
}
.fntv-pill--muted {
  color: rgba(var(--v-theme-on-surface), 0.62);
  background: rgba(var(--v-theme-on-surface), 0.045);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}
.fntv-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 5px;
  font-size: 0.74rem;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.75);
  background: rgba(var(--v-theme-on-surface), 0.06);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  white-space: nowrap;
}
.fntv-douban-link {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 5px;
  font-size: 0.75rem;
  font-weight: 500;
  text-decoration: none;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
  border: 1px solid rgba(var(--v-theme-primary), 0.22);
  white-space: nowrap;
}
.fntv-douban-link:hover {
  text-decoration: underline;
  background: rgba(var(--v-theme-primary), 0.16);
}
.fntv-progress-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 130px;
}
.fntv-progress-track {
  flex: 1 1 auto;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(var(--v-theme-info), 0.18);
}
.fntv-progress-bar {
  height: 100%;
  border-radius: 999px;
  background: rgb(var(--v-theme-info));
}
.fntv-empty {
  padding: 36px 16px;
  text-align: center;
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}
</style>
