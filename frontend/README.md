# FntvDoubanSync 前端（Vue 3 模块联邦）

MoviePilot v2 宿主在运行时通过 `@originjs/vite-plugin-federation` 加载本工程暴露的三个远程组件：

| 暴露名 | 组件 | 宿主容器 |
| --- | --- | --- |
| `./Config` | `src/components/Config.vue` | 插件配置弹窗（props: `initial-config`、`api`；events: `save`/`close`/`switch`） |
| `./Page` | `src/components/Page.vue` | 插件详情弹窗（props: `api`、`show_switch`；events: `close`/`switch`） |
| `./Dashboard` | `src/components/Dashboard.vue` | 仪表板卡片（props: `config`、`allow-refresh`、`api`） |

组件内一律通过 `props.api` 调用插件 HTTP API（`plugin/FntvDoubanSync/...`，宿主挂载于 `/api/v1/`）。Vue 与 Vuetify 复用宿主实例（shared `generate: false`），PostCSS 过滤全部 `.v-`/`.mdi-` 全局规则。

## 开发与构建

```bash
npm install        # 或 pnpm install
npm run dev        # 本地预览（src/App.vue 内置 mock api，无需 MoviePilot）
npm run build      # vite build + scripts/sync-dist.mjs 过滤拷贝
```

构建后仅将 `remoteEntry.js`、`__federation_*`、`_plugin-vue_export-helper-*`
复制到 `plugins.v2/fntvdoubansync/dist/assets/`（随插件下发）；`index-*`、`date-*`、
`runtime-*` 与 `__federation_shared_*` 为开发壳产物，严禁下发（官方模块联邦指南要求）。
