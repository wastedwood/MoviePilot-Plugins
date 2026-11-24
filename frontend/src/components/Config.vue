<template>
  <v-card elevation="0" class="fntv-config">
    <v-card-item>
      <v-card-title>飞牛影视豆瓣同步 · 配置</v-card-title>
      <template #append>
        <v-btn icon variant="text" color="primary" @click="emit('close')">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </template>
    </v-card-item>

    <v-card-text>
      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4">
        {{ error }}
      </v-alert>

      <!-- 基本设置 -->
      <div class="text-subtitle-1 font-weight-bold mb-2">基本设置</div>
      <v-row>
        <v-col cols="12" md="4">
          <v-switch v-model="config.enabled" label="启用定时同步" color="primary" inset hide-details />
        </v-col>
        <v-col cols="12" md="4">
          <v-switch v-model="config.notify" label="发送同步通知" color="primary" inset hide-details />
        </v-col>
        <v-col cols="12" md="4">
          <v-switch v-model="config.onlyonce" label="立即运行一次" color="primary" inset hide-details />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            v-model="config.cron"
            label="同步周期"
            placeholder="0 3 * * *"
            hint="5 位 cron 表达式"
            persistent-hint
            :error-messages="cronError"
          />
        </v-col>
        <v-col cols="12" md="6" class="pt-6">
          <v-slider
            v-model="config.watch_threshold_percent"
            label="电影观看阈值（%）"
            min="0"
            max="100"
            step="1"
            thumb-label
            color="primary"
            hint="播放进度达到阈值标记「看过」，0 表示有进度即算看完"
            persistent-hint
          />
        </v-col>
      </v-row>

      <!-- 飞牛影视 -->
      <div class="text-subtitle-1 font-weight-bold mt-6 mb-2">飞牛影视</div>
      <v-row>
        <v-col cols="12">
          <v-text-field
            v-model="config.fntv_db_path"
            label="数据库路径"
            placeholder="/fntv-db/trimmedia.db"
            hint="MoviePilot 容器内只读挂载的 trimmedia.db"
            persistent-hint
          >
            <template #append>
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                :loading="testingDb"
                @click="testDb"
              >
                测试连接并读取用户
              </v-btn>
            </template>
          </v-text-field>
        </v-col>
        <v-col cols="12">
          <v-select
            v-if="userItems.length"
            v-model="config.selected_user"
            label="飞牛影视用户"
            :items="userItems"
            item-title="username"
            item-value="guid"
            hint="来自飞牛影视数据库的活跃用户"
            persistent-hint
          />
          <v-text-field
            v-else
            v-model="config.selected_user"
            label="飞牛影视用户 GUID"
            placeholder="点击上方按钮读取，或直接填写 GUID"
            persistent-hint
            hint="测试连接成功后自动变为下拉列表"
          />
        </v-col>
      </v-row>
      <v-alert
        v-if="dbResult"
        :type="dbResult.ok ? 'success' : 'warning'"
        variant="tonal"
        density="compact"
        class="mb-2"
      >
        {{ dbResult.message }}
      </v-alert>

      <!-- 豆瓣 -->
      <div class="text-subtitle-1 font-weight-bold mt-6 mb-2">豆瓣账号</div>
      <v-row>
        <v-col cols="12" md="12">
          <v-switch
            v-model="config.use_cookiecloud"
            label="Cookie 为空时从宿主 CookieCloud 获取（douban.com）"
            color="primary"
            inset
            hide-details
          />
        </v-col>
        <v-col cols="12">
          <v-textarea
            v-model="config.douban_cookie"
            label="豆瓣 Cookie（手动填写，优先于 CookieCloud）"
            placeholder='ck=xxxx; dbcl2="12345:xxxx"; ...'
            rows="3"
            auto-grow
          >
            <template #append>
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                :loading="checkingCookie"
                @click="checkCookie"
              >
                检查 Cookie 有效性
              </v-btn>
            </template>
          </v-textarea>
        </v-col>
      </v-row>
      <v-alert
        v-if="cookieResult"
        :type="cookieResult.ok ? 'success' : 'warning'"
        variant="tonal"
        density="compact"
        class="mb-2"
      >
        {{ cookieResult.message }}
      </v-alert>

      <v-expansion-panels variant="accordion" class="mt-2">
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon start size="small">mdi-help-circle-outline</v-icon>
            如何获取豆瓣 Cookie（只需一次，过期后按相同步骤重新获取）
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-list density="compact" class="py-0">
              <v-list-item
                v-for="(step, i) in cookieSteps"
                :key="i"
                :prepend-avatar="String(i + 1)"
                :title="step.title"
                :subtitle="step.text"
              />
            </v-list>
            <v-alert type="warning" variant="tonal" density="compact" class="mt-2">
              Cookie 等同于账号的临时登录凭证，请勿截图、发送或提交给他人。
            </v-alert>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>

      <!-- 隐私 -->
      <div class="text-subtitle-1 font-weight-bold mt-6 mb-2">同步规则</div>
      <v-row>
        <v-col cols="12" md="4">
          <v-switch v-model="config.private" label="豆瓣标记仅自己可见" color="primary" inset hide-details />
        </v-col>
        <v-col cols="12" md="8">
          <v-switch
            v-model="config.clean_wish"
            label="同步时将飞牛库已有影片移出豆瓣「想看」"
            color="primary"
            inset
            hide-details
          />
        </v-col>
      </v-row>
      <v-alert type="info" variant="tonal" density="compact" class="mt-2">
        电影按播放进度阈值标记「在看/看过」；剧集按季增量同步、最后一集看完才标记「看过」，第 0
        季特别篇不同步；多季条目按季标题与集数对齐豆瓣分部。挂载示例：
        <code>- /usr/local/apps/@appdata/trim.media/database/trimmedia.db:/fntv-db/trimmedia.db:ro</code>
      </v-alert>
    </v-card-text>

    <v-divider />
    <v-card-actions class="px-4 py-3">
      <v-btn
        color="info"
        variant="tonal"
        prepend-icon="mdi-database-eye-outline"
        @click="emit('switch')"
      >
        查看同步记录
      </v-btn>
      <v-spacer />
      <v-btn color="primary" variant="flat" prepend-icon="mdi-content-save" :loading="saving" @click="save">
        保存
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => null },
})

const emit = defineEmits(['save', 'close', 'switch'])

const defaults = {
  enabled: false,
  notify: true,
  onlyonce: false,
  cron: '0 3 * * *',
  fntv_db_path: '/fntv-db/trimmedia.db',
  selected_user: '',
  use_cookiecloud: false,
  douban_cookie: '',
  watch_threshold_percent: 90,
  private: true,
  clean_wish: false,
}

const config = reactive({ ...defaults })
const error = ref(null)
const saving = ref(false)
const testingDb = ref(false)
const checkingCookie = ref(false)
const dbResult = ref(null)
const cookieResult = ref(null)
const userItems = ref([])

const cookieSteps = [
  { title: '登录豆瓣', text: '在电脑浏览器打开 movie.douban.com，登录需要同步的账号。' },
  { title: '打开开发者工具', text: '按键盘 F12（Mac 为 Command + Option + I）。' },
  { title: '选择网络面板', text: '点击 Network（网络），刷新豆瓣页面，找到 document 类型的请求。' },
  { title: '复制 Cookie', text: '打开请求详情，在 Request Headers 中找到 Cookie，右键复制完整值。' },
  { title: '粘贴并验证', text: '回到本页粘贴 Cookie，点击「检查 Cookie 有效性」，通过后保存配置。' },
]

const cronError = computed(() => {
  const parts = String(config.cron || '').trim().split(/\s+/)
  return parts.length === 5 ? '' : '请输入 5 位 cron 表达式'
})

onMounted(() => {
  if (props.initialConfig) {
    for (const [key, value] of Object.entries(props.initialConfig)) {
      if (key in config) {
        config[key] = key === 'watch_threshold_percent' ? Number(value) : value
      }
    }
  }
})

async function testDb() {
  if (!props.api || !config.fntv_db_path) return
  testingDb.value = true
  dbResult.value = null
  try {
    const res = await props.api.get(
      `plugin/FntvDoubanSync/fntv/users?db_path=${encodeURIComponent(config.fntv_db_path)}`)
    if (res.ok) {
      userItems.value = res.users || []
      dbResult.value = {
        ok: true,
        message: userItems.value.length
          ? `连接成功，读取到 ${userItems.value.length} 个用户`
          : '连接成功，但数据库中没有活跃用户',
      }
    } else {
      dbResult.value = { ok: false, message: `连接失败：${res.error}` }
    }
  } catch (e) {
    dbResult.value = { ok: false, message: `请求失败：${e.message || e}` }
  } finally {
    testingDb.value = false
  }
}

async function checkCookie() {
  if (!props.api) return
  checkingCookie.value = true
  cookieResult.value = null
  try {
    const res = await props.api.post('plugin/FntvDoubanSync/douban/check-cookie', {
      cookie: config.douban_cookie || '',
      use_cookiecloud: !!config.use_cookiecloud,
    })
    cookieResult.value = { ok: !!res.ok, message: res.message }
  } catch (e) {
    cookieResult.value = { ok: false, message: `请求失败：${e.message || e}` }
  } finally {
    checkingCookie.value = false
  }
}

function save() {
  if (cronError.value) {
    error.value = cronError.value
    return
  }
  error.value = null
  saving.value = true
  try {
    emit('save', { ...config, watch_threshold_percent: Number(config.watch_threshold_percent) })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.fntv-config :deep(code) {
  font-size: 0.75rem;
  opacity: 0.85;
}
</style>
