# 飞牛影视豆瓣同步（FntvDoubanSync）

只读解析飞牛影视（FNTV / fnOS 影视）的观看记录数据库，把电影与剧集的「在看」「看过」状态增量同步到豆瓣。迁移自独立项目 [wastedwood/DouBanSync](https://github.com/wastedwood/DouBanSync)，作为 MoviePilot v2 插件运行。

插件界面为 Vue 3 模块联邦远程组件（`./Config`、`./Page`、`./Dashboard`）：无需保存即可测试数据库连接、动态读取飞牛用户列表、一键诊断豆瓣 Cookie、实时轮询同步状态、按动作与片名筛选分页日志。构建产物位于插件目录 `dist/assets/`；如需改动界面，在仓库根 `frontend/` 执行 `npm run build`（内部会先 `vite build` 再过滤拷贝产物）。

## 一、准备：只读挂载飞牛数据库

飞牛影视的媒体库是 SQLite 数据库 `trimmedia.db`（飞牛 OS 路径 `/usr/local/apps/@appdata/trim.media/database/trimmedia.db`）。MoviePilot 与飞牛影视通常不在同一容器，需要把该文件**只读挂载**进 MoviePilot 容器。

在 MoviePilot 的 `docker-compose.yml` 中增加挂载：

```yaml
volumes:
  - /usr/local/apps/@appdata/trim.media/database/trimmedia.db:/fntv-db/trimmedia.db:ro
```

> **注意**：必须挂载**文件**而不是目录；若宿主机路径不存在，Docker 会自动创建同名**目录**导致插件报「路径是目录」错误，请确认飞牛影视已初始化媒体库。
> 插件对数据库全程只读（自动复制临时副本后访问，不写入、不加锁）。

## 二、插件配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| 启用定时同步 | 关 | 启用后按 Cron 周期自动同步 |
| 发送同步通知 | 开 | 通过 MoviePilot 消息渠道推送同步摘要 |
| 立即运行一次 | 关 | 保存后 3 秒触发一次同步（触发后自动复位） |
| 同步周期 | `0 3 * * *` | 5 位 Cron 表达式 |
| 飞牛影视数据库路径 | `/fntv-db/trimmedia.db` | 容器内只读挂载路径 |
| 飞牛影视用户 | — | 路径可读时自动变为下拉列表 |
| Cookie 为空时用 CookieCloud | 关 | 手动 Cookie 为空时，从宿主 CookieCloud 取 `douban.com` 的 Cookie |
| 豆瓣 Cookie | — | 手动填写，**优先于** CookieCloud |
| 电影观看阈值（%） | 90 | 播放进度达到阈值标记「看过」，0 表示有进度即算看完 |
| 豆瓣标记仅自己可见 | 开 | 豆瓣隐私标记 |
| 同步时清理豆瓣「想看」 | 关 | 飞牛库已有的影片自动移出豆瓣想看列表 |

## 三、豆瓣 Cookie

二选一：

1. **手动**：浏览器登录豆瓣后导出 Cookie（必须包含 `ck` 与 `dbcl2`），粘贴到「豆瓣 Cookie」输入框。
2. **CookieCloud**：MoviePilot 宿主已配置 CookieCloud 时打开开关即可，插件自动取 `douban.com` 的 Cookie。

手动 Cookie 非空时优先生效；两者都没有时同步会失败并在日志中提示。Cookie 失效时同步摘要会给出「Cookie 无效」警报。

## 四、同步规则

- **增量**：按播放记录的 `update_time` 游标增量拉取，只处理上次同步之后的新播放；豆瓣暂时不可用（超时 / 5xx / 限流）时游标停在失败前，下次自动重试。
- **电影**：播放进度达到阈值 → 豆瓣标记「看过」；有进度但未达阈值 → 标记「在看」。
- **剧集**：按季分组增量同步，看到最后一集（含刮削到的计划集数，取大值）才标记「看过」，中间集只更新状态不重复调用豆瓣；第 0 季（特别篇）不同步。
- **多季匹配**：优先按飞牛季标题（如「最终季」「飙马野郎篇」）在豆瓣对齐条目，并把豆瓣按 Part.1/Part.2 拆分的季按集数累计对齐；季标题匹配不到时按「剧名 + 第 N 季」搜索，宁可失败也不误标第一季。
- **想看清理**：开启后，豆瓣「想看」中已在飞牛库里的影片（IMDb 或中文名/原名精确匹配）自动移出想看，在看/看过不动。

## 五、远程命令

对话渠道（微信 / Telegram / Slack 等）发送：

```
/fntv_douban_sync
```

插件回复开始提示，完成后定向回复同步结果摘要。

## 六、数据与路径

插件所有运行数据（同步状态库 `sync_state.db`、数据库临时副本 `trimmedia_tmp.db`）都存放在 MoviePilot 插件数据目录 `config/plugins/FntvDoubanSync/` 下，卸载重装不产生残留冲突。

## 致谢

- 原项目：[wastedwood/DouBanSync](https://github.com/wastedwood/DouBanSync)
- 官方插件规范参考：[jxxghp/MoviePilot-Plugins](https://github.com/jxxghp/MoviePilot-Plugins)
