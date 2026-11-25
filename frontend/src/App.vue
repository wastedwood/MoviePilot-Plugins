<template>
  <v-app>
    <v-main>
      <v-container class="py-6 mx-auto" style="max-width: 1040px">
        <v-sheet border rounded="lg" class="pa-3 mb-4 d-flex align-center justify-space-between flex-wrap ga-3">
          <div class="d-flex align-center ga-3">
            <v-tabs v-model="tab" density="compact" color="primary">
              <v-tab value="config">Config（配置页）</v-tab>
              <v-tab value="page">Page（同步记录）</v-tab>
              <v-tab value="dashboard">Dashboard（仪表板）</v-tab>
            </v-tabs>
          </div>

          <div class="d-flex align-center ga-2 flex-wrap">
            <v-btn-toggle v-model="scenario" mandatory density="compact" variant="outlined" color="primary">
              <v-btn value="configured" size="small">已配置</v-btn>
              <v-btn value="fresh" size="small">首次安装</v-btn>
              <v-btn value="expired" size="small">Cookie 失效</v-btn>
            </v-btn-toggle>

            <v-btn
              size="small"
              variant="tonal"
              :prepend-icon="isDark ? 'mdi-weather-sunny' : 'mdi-weather-night'"
              @click="toggleTheme"
            >
              {{ isDark ? '浅色' : '深色' }}
            </v-btn>
          </div>
        </v-sheet>

        <v-window v-model="tab" :key="scenarioKey">
          <v-window-item value="config">
            <v-sheet border rounded="lg">
              <Config
                :initial-config="activeConfig"
                :api="mockApi"
                @save="onSaveConfig"
                @close="onEvent('close')"
                @switch="tab = 'page'"
              />
            </v-sheet>
          </v-window-item>

          <v-window-item value="page">
            <v-sheet border rounded="lg">
              <Page
                :api="mockApi"
                :show-switch="true"
                @close="onEvent('close')"
                @switch="tab = 'config'"
              />
            </v-sheet>
          </v-window-item>

          <v-window-item value="dashboard">
            <v-row>
              <v-col cols="12" md="6">
                <Dashboard
                  :config="{ attrs: { title: '飞牛影视豆瓣同步', border: true, refresh: 60 } }"
                  :allow-refresh="true"
                  :api="mockApi"
                />
              </v-col>
            </v-row>
          </v-window-item>
        </v-window>

        <v-alert v-if="lastEvent" type="info" variant="tonal" density="compact" class="mt-4">
          最近事件：{{ lastEvent }}
        </v-alert>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useTheme } from 'vuetify'
import Config from './components/Config.vue'
import Page from './components/Page.vue'
import Dashboard from './components/Dashboard.vue'

const theme = useTheme()
const tab = ref('config')
const scenario = ref('configured')
const scenarioKey = ref(0)
const lastEvent = ref('')
const isDark = computed(() => theme.global.current.value.dark)

function toggleTheme() {
  theme.global.name.value = isDark.value ? 'light' : 'dark'
}

const nowSec = Math.floor(Date.now() / 1000)

const state = reactive({
  config: {
    enabled: true,
    notify: true,
    onlyonce: false,
    cron: '0 3 * * *',
    fntv_db_path: '/fntv-db/trimmedia.db',
    selected_user: 'u1',
    use_cookiecloud: false,
    douban_cookie: 'ck=dev; dbcl2="12345:abc"',
    watch_threshold_percent: 90,
    private: true,
    clean_wish: false,
  },
  running: false,
  lastRunAt: Date.now() - 1800_000,
  lastRunStatus: 'success',
  lastRunMessage: '✅ 已看完（2）\n• 庆余年 第二季\n• 沙丘 2\n本次共处理 3 项',
  stats: { total: 16, done: 12, doing: 3, failed: 1 },
  itemStats: { total: 12, done: 8, doing: 3, failed: 1 },
  items: [
    { media_type: 'episode', entry_guid: 'tv-1', season_number: 2, series_title: '庆余年', status: 'done', douban_subject_id: '26647117', max_ep_watched: 36, total_episodes: 36, last_synced_at: nowSec - 1800, last_detail: '豆瓣ID=26647117(done) ep=36/36' },
    { media_type: 'episode', entry_guid: 'tv-2', season_number: 1, series_title: '葬送的芙莉莲', status: 'doing', douban_subject_id: '35494922', max_ep_watched: 12, total_episodes: 28, last_synced_at: nowSec - 3600, last_detail: '豆瓣ID=35494922(doing) ep=12/28' },
    { media_type: 'movie', entry_guid: 'm-1', season_number: 0, series_title: '测试冷门短片', status: 'failed', douban_subject_id: '', max_ep_watched: 0, total_episodes: 0, last_synced_at: nowSec - 86400, last_detail: '豆瓣搜索无结果' },
  ],
  logs: [
    { id: 4, action: 'mark_done', series_title: '庆余年 S2', season_number: 2, detail: '豆瓣ID=26647117(done) ep=36/36', created_at: nowSec - 1800 },
    { id: 3, action: 'mark_doing', series_title: '葬送的芙莉莲 S1', season_number: 1, detail: '豆瓣ID=35494922(doing) ep=12/28', created_at: nowSec - 3600 },
    { id: 2, action: 'skip_special', series_title: '进击的巨人', season_number: null, detail: '特别篇不同步', created_at: nowSec - 7200 },
    { id: 1, action: 'error_search', series_title: '测试冷门短片', season_number: null, detail: '豆瓣搜索无结果', created_at: nowSec - 86400 },
  ],
})

const activeConfig = computed(() => ({ ...state.config }))

watch(scenario, val => {
  if (val === 'configured') {
    Object.assign(state.config, {
      enabled: true,
      fntv_db_path: '/fntv-db/trimmedia.db',
      selected_user: 'u1',
      douban_cookie: 'ck=dev; dbcl2="12345:abc"',
      use_cookiecloud: false,
    })
    state.lastRunAt = Date.now() - 1800_000
    state.lastRunStatus = 'success'
    state.lastRunMessage = '✅ 已看完（2）\n• 庆余年 第二季\n• 沙丘 2\n本次共处理 3 项'
    state.stats = { total: 16, done: 12, doing: 3, failed: 1 }
  } else if (val === 'fresh') {
    Object.assign(state.config, {
      enabled: false,
      fntv_db_path: '/fntv-db/trimmedia.db',
      selected_user: '',
      douban_cookie: '',
      use_cookiecloud: false,
    })
    state.lastRunAt = 0
    state.lastRunStatus = ''
    state.lastRunMessage = ''
    state.stats = { total: 0, done: 0, doing: 0, failed: 0 }
  } else if (val === 'expired') {
    Object.assign(state.config, {
      enabled: true,
      fntv_db_path: '/fntv-db/trimmedia.db',
      selected_user: 'u1',
      douban_cookie: 'ck=old; dbcl2="1:expired"',
      use_cookiecloud: false,
    })
    state.lastRunAt = Date.now() - 600_000
    state.lastRunStatus = 'error'
    state.lastRunMessage = '豆瓣 Cookie 已失效，请在插件配置中更新'
    state.stats = { total: 16, done: 12, doing: 3, failed: 2 }
  }
  scenarioKey.value += 1
})

const mockApi = {
  async get(url) {
    if (url.includes('fntv/users')) {
      if (scenario.value === 'fresh' && url.includes('bad')) {
        return { ok: false, users: [], error: '文件不存在: /bad/trimmedia.db' }
      }
      return {
        ok: true,
        users: [
          { guid: 'u1', username: '主账号' },
          { guid: 'u2', username: '客厅电视' },
        ],
        error: '',
      }
    }
    if (url.includes('status')) {
      return {
        running: state.running,
        enabled: state.config.enabled,
        cron: state.config.cron,
        fntv_db_path: state.config.fntv_db_path,
        selected_user: state.config.selected_user,
        cookie_source: state.config.douban_cookie
          ? 'manual'
          : state.config.use_cookiecloud
            ? 'cookiecloud'
            : 'none',
        last_sync_time: state.lastRunAt,
        last_run_at: state.lastRunAt,
        last_run_status: state.lastRunStatus,
        last_run_message: state.lastRunMessage,
        stats: state.stats,
        item_stats: state.itemStats,
      }
    }
    if (url.includes('items')) {
      if (scenario.value === 'fresh') {
        return { total: 0, summary: { total: 0, done: 0, doing: 0, failed: 0 }, items: [] }
      }
      const query = url.split('?')[1] || ''
      const params = new URLSearchParams(query)
      const st = params.get('status') || ''
      const keyword = (params.get('keyword') || '').trim().toLowerCase()
      const limit = Number(params.get('limit') || 20)
      const offset = Number(params.get('offset') || 0)
      const filtered = state.items.filter(item => {
        if (st && item.status !== st) return false
        if (keyword) {
          const hay = `${item.series_title} ${item.douban_subject_id}`.toLowerCase()
          if (!hay.includes(keyword)) return false
        }
        return true
      })
      return {
        total: filtered.length,
        summary: state.itemStats,
        items: filtered.slice(offset, offset + limit),
      }
    }
    if (url.includes('logs')) {
      if (scenario.value === 'fresh') {
        return { total: 0, items: [] }
      }
      const query = url.split('?')[1] || ''
      const params = new URLSearchParams(query)
      const actions = (params.get('action') || '').split(',').map(s => s.trim()).filter(Boolean)
      const keyword = (params.get('keyword') || '').trim().toLowerCase()
      const limit = Number(params.get('limit') || 20)
      const offset = Number(params.get('offset') || 0)
      const filtered = state.logs.filter(item => {
        if (actions.length && !actions.includes(item.action)) return false
        if (keyword) {
          const hay = `${item.series_title} ${item.detail}`.toLowerCase()
          if (!hay.includes(keyword)) return false
        }
        return true
      })
      return {
        total: filtered.length,
        items: filtered.slice(offset, offset + limit),
      }
    }
    return {}
  },
  async post(url, data) {
    if (url.includes('douban/check-cookie')) {
      const ck = String(data?.cookie || '').trim()
      if (!ck && !data?.use_cookiecloud) {
        return { ok: false, reason: 'no_cookie', message: '请填写豆瓣 Cookie 或开启 CookieCloud', source: 'none' }
      }
      if (scenario.value === 'expired' || ck.includes('expired')) {
        return { ok: false, reason: 'cookie_expired', message: 'Cookie 已过期，被重定向到登录页面', source: 'manual' }
      }
      if (!ck.includes('dbcl2')) {
        return { ok: false, reason: 'no_dbcl2', message: 'Cookie 中缺少 dbcl2（登录凭证），请确认已登录豆瓣', source: 'manual' }
      }
      return { ok: true, reason: '', message: 'Cookie 有效（预览模拟验证通过）', source: ck ? 'manual' : 'cookiecloud' }
    }
    if (url.includes('sync/run')) {
      if (state.running) {
        return { ok: false, running: true, message: '同步正在进行中，请稍候' }
      }
      state.running = true
      setTimeout(() => {
        state.running = false
        state.lastRunAt = Date.now()
        state.lastRunStatus = 'success'
        state.lastRunMessage = '✅ 已看完（1）\n• 电影：星际穿越\n本次共处理 1 项'
        state.stats = { ...state.stats, total: state.stats.total + 1, done: state.stats.done + 1 }
        state.logs.unshift({
          id: Date.now(),
          action: 'mark_done',
          series_title: '星际穿越',
          detail: '豆瓣ID=1889243',
          created_at: Math.floor(Date.now() / 1000),
        })
      }, 1500)
      return { ok: true, running: true, message: '同步已开始' }
    }
    return {}
  },
}

function onSaveConfig(payload) {
  Object.assign(state.config, payload)
  onEvent('save', payload)
}

function onEvent(name, payload) {
  lastEvent.value = name + (payload !== undefined ? ` → ${JSON.stringify(payload).slice(0, 100)}` : '')
}
</script>
