# MoviePilot-Plugins（个人插件市场）

本仓库是 [MoviePilot](https://github.com/jxxghp/MoviePilot) **v2** 的个人插件市场仓库，托管插件按 MoviePilot V2 规范存放在 `plugins.v2/` 下，通过 `package.v2.json` 索引发布。

## 插件清单

| 插件 | 说明 |
| --- | --- |
| [FntvDoubanSync](plugins.v2/fntvdoubansync/README.md) | 飞牛影视豆瓣同步：只读解析飞牛影视观看记录，增量同步在看/看过状态到豆瓣 |

## 接入 MoviePilot

1. 在 MoviePilot 的环境变量 `PLUGIN_MARKET` 中追加本仓库地址（多个仓库用英文逗号分隔）：

   ```yaml
   environment:
     - PLUGIN_MARKET=https://github.com/jxxghp/MoviePilot-Plugins,https://github.com/wastedwood/MoviePilot-Plugins
   ```

   > 仓库需为公开 GitHub 仓库，且默认分支为 `main`。

2. 重启 MoviePilot，在「设定 → 插件市场」中即可看到本仓库的插件，点击安装。

3. 插件更新：本仓库更新 `package.v2.json` 中的 `version` 与 `plugins.v2/<插件>/` 代码后，插件市场会提示升级。

## 仓库约定

- 插件目录名 = 插件类名全小写（如 `FntvDoubanSync` → `plugins.v2/fntvdoubansync/`）。
- `package.v2.json` 中的顶层 Key 必须与插件类名完全一致，`version` 与代码内 `plugin_version` 严格同步。
- 测试一律放在 `tests/v2/<插件名>/`，**严禁**放进 `plugins.v2/<插件>/`（MoviePilot 安装时会整目录复制插件目录）。
- Vue 联邦界面源码放在仓库根 `frontend/`，构建产物经 `scripts/sync-dist.mjs` 过滤后进入 `plugins.v2/<插件>/dist/assets/`（随插件下发）。
- 发布前请运行门禁：`python scripts/check_plugin.py`，插件测试：`pytest tests/v2/<插件名> -v`。

## 许可

跟随各插件原始项目的开源许可；本仓库结构参照 [jxxghp/MoviePilot-Plugins](https://github.com/jxxghp/MoviePilot-Plugins)。
