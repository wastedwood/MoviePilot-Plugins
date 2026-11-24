<template>
  <v-app>
    <v-main>
      <v-container max-width="960">
        <v-tabs v-model="tab" class="mb-4">
          <v-tab value="config">Config（配置）</v-tab>
          <v-tab value="page">Page（同步记录）</v-tab>
          <v-tab value="dashboard">Dashboard（仪表板）</v-tab>
        </v-tabs>

        <v-window v-model="tab">
          <v-window-item value="config">
            <Config
              :initial-config="mockConfig"
              :api="mockApi"
              @save="c => onEvent('save', c)"
              @close="onEvent('close')"
              @switch="onEvent('switch')"
            />
          </v-window-item>
          <v-window-item value="page">
            <Page :api="mockApi" :show-switch="true" @close="onEvent('close')" @switch="onEvent('switch')" />
          </v-window-item>
          <v-window-item value="dashboard">
            <v-sheet max-width="420">
              <Dashboard :config="{ attrs: { title: '飞牛影视豆瓣同步', border: true } }" :allow-refresh="true" :api="mockApi" />
            </v-sheet>
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
import { ref } from 'vue'
import Config from './components/Config.vue'
import Page from './components/Page.vue'
import Dashboard from './components/Dashboard.vue'

const tab = ref('config')
const lastEvent = ref('')

const mockConfig = {
  enabled: true,
  notify: true,
  onlyonce: false,
  cron: '0 3 * * *',
  fntv_db_path: '/fntv-db/trimmedia.db',
  selected_user: 'u1',
  use_cookiecloud: false,
  douban_cookie: 'ck=dev; dbcl2="1:abc"',
  watch_threshold_percent: 90,
  private: true,
  clean_wish: false,
}

const now = Math.floor(Date.now() / 1000)
const mockLogs = {
  total: 3,
  items: [
    { id: 3, action: 'mark_done', series_title: '庆余年 第二季', detail: '豆瓣ID=26647117 ep=36/36', created_at: now - 3600 },
    { id: 2, action: 'skip_special', series_title: '进击的巨人', detail: '特别篇不同步', created_at: now - 7200 },
    { id: 1, action: 'error_search', series_title: '未知影片', detail: '豆瓣搜索无结果', created_at: now - 86400 },
  ],
}

// 模拟宿主 api（axios 风格，自动解包 data）
const mockApi = {
  async get(url) {
    if (url.includes('fntv/users')) {
      return { ok: true, users: [{ guid: 'u1', username: '测试用户' }, { guid: 'u2', username: '家人' }], error: '' }
    }
    if (url.includes('douban/check-cookie')) {
      return { ok: true, reason: '', message: 'Cookie 有效', source: 'manual' }
    }
    if (url.includes('status')) {
      return {
        running: false, enabled: true, selected_user: 'u1',
        cookie_source: 'manual', last_sync_time: Date.now() - 3600_000,
        stats: { total: 12, done: 10, failed: 1 },
      }
    }
    if (url.includes('logs')) {
      return mockLogs
    }
    return {}
  },
  async post(url, data) {
    if (url.includes('sync/run')) {
      return { ok: true, running: true, message: '同步已开始' }
    }
    return {}
  },
}

function onEvent(name, payload) {
  lastEvent.value = name + (payload !== undefined ? ` → ${JSON.stringify(payload).slice(0, 80)}` : '')
}
</script>
