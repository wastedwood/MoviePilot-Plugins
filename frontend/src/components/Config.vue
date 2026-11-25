<template>
  <v-card elevation="0" class="fntv-config">
    <v-card-item class="pb-2">
      <template #prepend>
        <v-avatar color="primary" variant="tonal" size="36" rounded="lg">
          <v-icon size="20">mdi-sync</v-icon>
        </v-avatar>
      </template>
      <v-card-title class="text-h6 font-weight-bold">飞牛影视豆瓣同步</v-card-title>
      <v-card-subtitle>只读解析飞牛观看记录，增量同步在看与看过状态到豆瓣</v-card-subtitle>
      <template #append>
        <v-btn icon variant="text" color="secondary" size="small" @click="emit('close')">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </template>
    </v-card-item>

    <v-divider />

    <v-card-text class="pt-4">
      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4" closable @click:close="error = null">
        {{ error }}
      </v-alert>

      <!-- 基本设置 -->
      <v-sheet border rounded="lg" class="pa-4 mb-4 fntv-section">
        <div class="d-flex align-center mb-3">
          <v-icon size="18" color="primary" class="mr-2">mdi-tune-variant</v-icon>
          <span class="text-subtitle-1 font-weight-bold">基本设置</span>
        </div>

        <v-row dense>
          <v-col cols="12" sm="4">
            <v-switch v-model="config.enabled" label="启用定时同步" color="primary" inset hide-details density="compact" />
          </v-col>
          <v-col cols="12" sm="4">
            <v-switch v-model="config.notify" label="发送同步通知" color="primary" inset hide-details density="compact" />
          </v-col>
          <v-col cols="12" sm="4">
            <v-switch v-model="config.onlyonce" label="立即运行一次" color="primary" inset hide-details density="compact" />
          </v-col>
        </v-row>

        <v-row class="mt-2">
          <v-col cols="12" md="6">
            <v-text-field
              v-model="config.cron"
              label="同步周期（5 位 Cron）"
              placeholder="0 3 * * *"
              variant="outlined"
              density="compact"
              :error-messages="cronError"
              hide-details="auto"
            />
            <div class="d-flex flex-wrap align-center ga-2 mt-2">
              <span class="text-caption text-medium-emphasis">快捷预设：</span>
              <v-chip
                v-for="preset in cronPresets"
                :key="preset.value"
                size="x-small"
                variant="tonal"
                :color="config.cron === preset.value ? 'primary' : 'default'"
                @click="config.cron = preset.value"
              >
                {{ preset.label }}
              </v-chip>
            </div>
          </v-col>

          <v-col cols="12" md="6">
            <div class="d-flex align-center justify-space-between mb-1">
              <span class="text-body-2 font-weight-medium">电影观看阈值</span>
              <v-chip size="x-small" color="primary" variant="tonal" class="font-weight-bold">
                {{ config.watch_threshold_percent }}%
              </v-chip>
            </div>
            <v-slider
              v-model="config.watch_threshold_percent"
              min="0"
              max="100"
              step="1"
              color="primary"
              thumb-label
              hide-details
            />
            <div class="text-caption text-medium-emphasis mt-1">
              播放进度达到 {{ config.watch_threshold_percent }}% 标记「看过」，0% 表示有进度即算看完
            </div>
          </v-col>
        </v-row>
      </v-sheet>

      <!-- 飞牛影视 -->
      <v-sheet border rounded="lg" class="pa-4 mb-4 fntv-section">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
          <div class="d-flex align-center">
            <v-icon size="18" color="primary" class="mr-2">mdi-database-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">飞牛影视数据库</span>
          </div>
          <v-chip
            size="x-small"
            variant="tonal"
            :color="dbStatusChip.color"
            :prepend-icon="dbStatusChip.icon"
          >
            {{ dbStatusChip.text }}
          </v-chip>
        </div>

        <v-row dense>
          <v-col cols="12" sm="8">
            <v-text-field
              v-model="config.fntv_db_path"
              label="数据库路径"
              placeholder="/fntv-db/trimmedia.db"
              hint="MoviePilot 容器内只读挂载的 trimmedia.db 路径"
              persistent-hint
              variant="outlined"
              density="compact"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-btn
              block
              height="40"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-connection"
              :loading="testingDb"
              @click="testDb"
            >
              测试连接并读取用户
            </v-btn>
          </v-col>

          <v-col cols="12" class="mt-2">
            <v-select
              v-if="userItems.length"
              v-model="config.selected_user"
              label="飞牛影视用户"
              :items="userItems"
              item-title="username"
              item-value="guid"
              hint="来自飞牛影视数据库的活跃用户"
              persistent-hint
              variant="outlined"
              density="compact"
              clearable
            >
              <template #item="{ props: itemProps, item }">
                <v-list-item v-bind="itemProps" :subtitle="item.raw.guid" />
              </template>
            </v-select>
            <v-text-field
              v-else
              v-model="config.selected_user"
              label="飞牛影视用户 GUID"
              placeholder="请先点击右上按钮连接数据库并选择用户，或手动填写 GUID"
              hint="连接数据库成功后会自动切换为用户名下拉菜单"
              persistent-hint
              variant="outlined"
              density="compact"
            />
          </v-col>
        </v-row>

        <v-alert
          v-if="dbResult"
          :type="dbResult.ok ? 'success' : 'warning'"
          variant="tonal"
          density="compact"
          class="mt-3"
        >
          {{ dbResult.message }}
        </v-alert>

        <v-expansion-panels variant="accordion" class="mt-3">
          <v-expansion-panel>
            <v-expansion-panel-title class="text-body-2">
              <v-icon start size="small" color="info">mdi-docker</v-icon>
              首次配置：如何把飞牛影视数据库挂载进 MoviePilot 容器
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-2">
              <div class="mb-3">
                <div class="font-weight-medium mb-1">方式一：Docker Compose（推荐，直接挂载单文件）</div>
                <v-sheet border rounded class="pa-2 d-flex align-center ga-2 fntv-code-box">
                  <code class="fntv-code">- /usr/local/apps/@appdata/trim.media/database/trimmedia.db:/fntv-db/trimmedia.db:ro</code>
                  <v-btn
                    size="x-small"
                    variant="tonal"
                    color="primary"
                    class="flex-shrink-0"
                    :prepend-icon="copiedKey === 'compose' ? 'mdi-check' : 'mdi-content-copy'"
                    @click="copyText('/usr/local/apps/@appdata/trim.media/database/trimmedia.db:/fntv-db/trimmedia.db:ro', 'compose')"
                  >
                    {{ copiedKey === 'compose' ? '已复制' : '复制' }}
                  </v-btn>
                </v-sheet>
              </div>

              <div class="mb-3">
                <div class="font-weight-medium mb-1">方式二：飞牛 Docker 图形界面（若界面仅支持选文件夹）</div>
                <div class="text-caption text-medium-emphasis mb-1">
                  宿主机目录选 <code>/usr/local/apps/@appdata/trim.media/database</code>，容器装载路径填 <code>/fntv-db</code>，权限选「只读」；上方路径同样填 <code>/fntv-db/trimmedia.db</code>。
                </div>
              </div>

              <v-alert type="info" variant="tonal" density="compact">
                若宿主机源文件尚未生成（飞牛影视未建库），Docker 单文件挂载会自动创建同名目录导致报错；请确保飞牛影视已初始化媒体库后重启 MoviePilot 容器。
              </v-alert>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-sheet>

      <!-- 豆瓣账号 -->
      <v-sheet border rounded="lg" class="pa-4 mb-4 fntv-section">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
          <div class="d-flex align-center">
            <v-icon size="18" color="primary" class="mr-2">mdi-account-key-outline</v-icon>
            <span class="text-subtitle-1 font-weight-bold">豆瓣账号</span>
          </div>
          <v-chip
            size="x-small"
            variant="tonal"
            :color="cookieStatusChip.color"
            :prepend-icon="cookieStatusChip.icon"
          >
            {{ cookieStatusChip.text }}
          </v-chip>
        </div>

        <v-switch
          v-model="config.use_cookiecloud"
          label="手动 Cookie 为空时，自动从宿主 CookieCloud 获取（douban.com）"
          color="primary"
          inset
          hide-details
          density="compact"
          class="mb-3"
        />

        <v-textarea
          v-model="config.douban_cookie"
          label="豆瓣 Cookie（手动填写，优先于 CookieCloud）"
          placeholder='ck=xxxx; dbcl2="12345:xxxx"; ...'
          rows="3"
          auto-grow
          variant="outlined"
          density="compact"
          hide-details
        />

        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mt-3">
          <span class="text-caption text-medium-emphasis">
            {{ cookieSourceHint }}
          </span>
          <v-btn
            variant="tonal"
            color="primary"
            prepend-icon="mdi-shield-check-outline"
            :loading="checkingCookie"
            @click="checkCookie"
          >
            检查 Cookie 有效性
          </v-btn>
        </div>

        <v-alert
          v-if="cookieResult"
          :type="cookieResult.ok ? 'success' : 'warning'"
          variant="tonal"
          density="compact"
          class="mt-3"
        >
          {{ cookieResult.message }}
        </v-alert>

        <v-expansion-panels variant="accordion" class="mt-3">
          <v-expansion-panel>
            <v-expansion-panel-title class="text-body-2">
              <v-icon start size="small" color="info">mdi-help-circle-outline</v-icon>
              如何获取豆瓣 Cookie（只需一次，过期后按相同步骤重新获取）
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-list density="compact" class="py-0">
                <v-list-item
                  v-for="(step, i) in cookieSteps"
                  :key="i"
                  :title="step.title"
                  :subtitle="step.text"
                >
                  <template #prepend>
                    <v-avatar size="24" color="primary" variant="tonal" class="text-caption font-weight-bold mr-3">
                      {{ i + 1 }}
                    </v-avatar>
                  </template>
                </v-list-item>
              </v-list>
              <v-alert type="warning" variant="tonal" density="compact" class="mt-2">
                Cookie 等同于账号的临时登录凭证（需包含 <code>ck</code> 与 <code>dbcl2</code>），请勿截图、发送或提交给他人。
              </v-alert>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-sheet>

      <!-- 同步规则 -->
      <v-sheet border rounded="lg" class="pa-4 fntv-section">
        <div class="d-flex align-center mb-3">
          <v-icon size="18" color="primary" class="mr-2">mdi-playlist-check</v-icon>
          <span class="text-subtitle-1 font-weight-bold">同步规则</span>
        </div>

        <v-row dense>
          <v-col cols="12" sm="5">
            <v-switch v-model="config.private" label="豆瓣标记仅自己可见" color="primary" inset hide-details density="compact" />
          </v-col>
          <v-col cols="12" sm="7">
            <v-switch
              v-model="config.clean_wish"
              label="同步时将飞牛库已有影片移出豆瓣「想看」"
              color="primary"
              inset
              hide-details
              density="compact"
            />
          </v-col>
        </v-row>

        <v-alert type="info" variant="tonal" density="compact" class="mt-3">
          电影按播放进度阈值标记「在看 / 看过」；剧集按季增量同步，看到最后一集才标记「看过」，第 0 季特别篇自动跳过；多季与拆分条目按季标题与集数对齐豆瓣条目。
        </v-alert>
      </v-sheet>
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
        保存配置
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => null },
  pluginId: { type: String, default: 'FntvDoubanSync' },
})

const emit = defineEmits(['save', 'close', 'switch'])

const apiBase = computed(() => `plugin/${props.pluginId || 'FntvDoubanSync'}`)

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
const copiedKey = ref('')

const cronPresets = [
  { label: '每天 03:00', value: '0 3 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '每小时', value: '0 * * * *' },
]

const cookieSteps = [
  { title: '登录豆瓣', text: '在电脑浏览器打开 movie.douban.com，登录需要同步的账号。' },
  { title: '打开开发者工具', text: '按键盘 F12（Mac 为 Command + Option + I）。' },
  { title: '选择网络面板', text: '点击 Network（网络），刷新豆瓣页面，找到 document 类型的请求。' },
  { title: '复制 Cookie', text: '打开请求详情，在 Request Headers 中找到 Cookie，右键复制完整值。' },
  { title: '粘贴并验证', text: '回到本页粘贴 Cookie，点击「检查 Cookie 有效性」，通过后保存配置。' },
]

const cronError = computed(() => {
  const parts = String(config.cron || '').trim().split(/\s+/).filter(Boolean)
  return parts.length === 5 ? '' : '请输入 5 位 Cron 表达式（分 时 日 月 周）'
})

const dbStatusChip = computed(() => {
  if (dbResult.value) {
    return dbResult.value.ok
      ? { color: 'success', icon: 'mdi-check-circle-outline', text: `已连接 · ${userItems.value.length} 位用户` }
      : { color: 'warning', icon: 'mdi-alert-circle-outline', text: '连接失败' }
  }
  if (userItems.value.length) {
    return { color: 'success', icon: 'mdi-check-circle-outline', text: `已加载 · ${userItems.value.length} 位用户` }
  }
  return { color: 'secondary', icon: 'mdi-help-circle-outline', text: '待测试' }
})

const cookieStatusChip = computed(() => {
  if (cookieResult.value) {
    return cookieResult.value.ok
      ? { color: 'success', icon: 'mdi-check-circle-outline', text: '验证有效' }
      : { color: 'warning', icon: 'mdi-alert-circle-outline', text: '无效或未配置' }
  }
  if (String(config.douban_cookie || '').trim()) {
    return { color: 'info', icon: 'mdi-key-outline', text: '已填手动 Cookie' }
  }
  if (config.use_cookiecloud) {
    return { color: 'info', icon: 'mdi-cloud-outline', text: '已开启 CookieCloud' }
  }
  return { color: 'secondary', icon: 'mdi-help-circle-outline', text: '未配置' }
})

const cookieSourceHint = computed(() => {
  if (String(config.douban_cookie || '').trim()) {
    return '当前将优先使用手动填写的豆瓣 Cookie'
  }
  if (config.use_cookiecloud) {
    return '手动 Cookie 为空，将从宿主 CookieCloud 读取 douban.com'
  }
  return '请填写手动 Cookie 或开启 CookieCloud'
})

onMounted(async () => {
  if (props.initialConfig) {
    for (const [key, value] of Object.entries(props.initialConfig)) {
      if (!(key in config) || value === undefined || value === null) continue
      if (key === 'fntv_db_path' && value === '' && !props.initialConfig.selected_user) {
        continue
      }
      config[key] = key === 'watch_threshold_percent' ? Number(value) : value
    }
  }
  if (config.fntv_db_path && props.api) {
    await fetchUsers({ silent: true })
  }
})

async function fetchUsers({ silent = false } = {}) {
  const path = String(config.fntv_db_path || '').trim()
  if (!path) {
    if (!silent) {
      dbResult.value = { ok: false, message: '请先填写容器内的 trimmedia.db 路径（例如 /fntv-db/trimmedia.db）' }
    }
    return
  }
  if (!props.api) return
  if (!silent) {
    testingDb.value = true
    dbResult.value = null
  }
  try {
    const res = await props.api.get(`${apiBase.value}/fntv/users?db_path=${encodeURIComponent(path)}`)
    if (res.ok) {
      userItems.value = res.users || []
      if (!config.selected_user && userItems.value.length === 1) {
        config.selected_user = userItems.value[0].guid
      }
      if (!silent) {
        dbResult.value = {
          ok: true,
          message: userItems.value.length
            ? `连接成功，读取到 ${userItems.value.length} 个活跃用户`
            : '连接成功，但数据库中没有活跃用户',
        }
      }
    } else if (!silent) {
      userItems.value = []
      dbResult.value = { ok: false, message: `连接失败：${res.error}` }
    }
  } catch (e) {
    if (!silent) {
      dbResult.value = { ok: false, message: `请求失败：${e.message || e}` }
    }
  } finally {
    if (!silent) {
      testingDb.value = false
    }
  }
}

function testDb() {
  return fetchUsers({ silent: false })
}

async function checkCookie() {
  if (!props.api) return
  checkingCookie.value = true
  cookieResult.value = null
  try {
    const res = await props.api.post(`${apiBase.value}/douban/check-cookie`, {
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

async function copyText(text, key) {
  try {
    await navigator.clipboard?.writeText(text)
    copiedKey.value = key
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = ''
    }, 1800)
  } catch {
    /* 无剪贴板权限时静默忽略 */
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
    emit('save', {
      ...config,
      fntv_db_path: String(config.fntv_db_path || '').trim(),
      cron: String(config.cron || '').trim(),
      watch_threshold_percent: Number(config.watch_threshold_percent),
    })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.fntv-code-box {
  min-width: 0;
}
.fntv-code {
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
  white-space: nowrap;
}
.fntv-section :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
}
</style>
