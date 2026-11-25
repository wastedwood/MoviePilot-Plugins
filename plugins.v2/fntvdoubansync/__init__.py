"""飞牛影视（FNTV）观看记录 → 豆瓣同步插件

只读挂载飞牛影视 SQLite 数据库（trimmedia.db），增量识别电影与剧集的
「在看」「看过」状态并同步到豆瓣；支持 CookieCloud 自动获取 Cookie、
定时同步、远程命令与原生消息通知。
"""

import datetime
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.event import Event, eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

from .douban_client import DoubanClient
from .fntv_db import FntvDb
from .sync_engine import SyncEngine
from .sync_store import SyncStore


class FntvDoubanSync(_PluginBase):
    """飞牛影视豆瓣同步插件"""

    # 插件名称
    plugin_name = "飞牛影视豆瓣同步"
    # 插件描述
    plugin_desc = "只读解析飞牛影视（FNTV）观看记录，增量同步电影与剧集的在看/看过状态到豆瓣。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wastedwood/MoviePilot-Plugins/main/icons/fntvdoubansync.png"
    # 插件版本
    plugin_version = "1.1.2"
    # 插件作者
    plugin_author = "wastedwood"
    # 作者主页
    author_url = "https://github.com/wastedwood"
    # 插件配置项ID前缀
    plugin_config_prefix = "fntvdoubansync_"
    # 加载顺序
    plugin_order = 20
    # 可使用的用户级别
    auth_level = 1

    # 私有变量
    _scheduler: Optional[BackgroundScheduler] = None
    _store: Optional[SyncStore] = None
    _engine: Optional[SyncEngine] = None
    _sync_thread: Optional[threading.Thread] = None

    def __init__(self):
        super().__init__()
        self._sync_lock = threading.Lock()
        self._syncing = False

    # 配置属性
    _enabled: bool = False
    _onlyonce: bool = False
    _notify: bool = True
    _cron: str = "0 3 * * *"
    _fntv_db_path: str = "/fntv-db/trimmedia.db"
    _selected_user: str = ""
    _use_cookiecloud: bool = False
    _douban_cookie: str = ""
    _watch_threshold_percent: int = 90
    _private: bool = True
    _clean_wish: bool = False

    # ── 配置解析 ─────────────────────────────────────

    @staticmethod
    def _as_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "on", "yes")

    def _normalize_config(self, config: dict | None) -> dict:
        """归一化配置：补全缺失项、修正类型并夹紧阈值"""
        config = config or {}
        try:
            threshold = int(config.get("watch_threshold_percent", 90))
        except (TypeError, ValueError):
            threshold = 90
        raw_db_path = config.get("fntv_db_path", "/fntv-db/trimmedia.db")
        if raw_db_path is None:
            raw_db_path = "/fntv-db/trimmedia.db"
        return {
            "enabled": self._as_bool(config.get("enabled"), False),
            "notify": self._as_bool(config.get("notify"), True),
            "onlyonce": self._as_bool(config.get("onlyonce"), False),
            "cron": str(config.get("cron") or "0 3 * * *").strip(),
            "fntv_db_path": str(raw_db_path).strip(),
            "selected_user": str(config.get("selected_user") or "").strip(),
            "use_cookiecloud": self._as_bool(config.get("use_cookiecloud"), False),
            "douban_cookie": str(config.get("douban_cookie") or "").strip(),
            "watch_threshold_percent": max(0, min(100, threshold)),
            "private": self._as_bool(config.get("private"), True),
            "clean_wish": self._as_bool(config.get("clean_wish"), False),
        }

    @staticmethod
    def _validate_cron(cron: str) -> Tuple[bool, str]:
        """校验 5 位 Cron 表达式"""
        expr = str(cron or "").strip()
        if not expr:
            return False, "Cron 表达式不能为空"
        try:
            CronTrigger.from_crontab(expr)
            return True, ""
        except ValueError as e:
            return False, str(e)

    def _current_config(self) -> dict:
        """当前生效配置（供 API 与命令回显）"""
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "onlyonce": self._onlyonce,
            "cron": self._cron,
            "fntv_db_path": self._fntv_db_path,
            "selected_user": self._selected_user,
            "use_cookiecloud": self._use_cookiecloud,
            "douban_cookie": self._douban_cookie,
            "watch_threshold_percent": self._watch_threshold_percent,
            "private": self._private,
            "clean_wish": self._clean_wish,
        }

    # ── 生命周期 ─────────────────────────────────────

    def init_plugin(self, config: dict = None):
        """生效配置信息"""
        # 停止现有任务
        self.stop_service()
        # 读取配置
        if config is not None:
            conf = self._normalize_config(config)
            self._enabled = conf["enabled"]
            self._notify = conf["notify"]
            self._onlyonce = conf["onlyonce"]
            self._cron = conf["cron"]
            self._fntv_db_path = conf["fntv_db_path"]
            self._selected_user = conf["selected_user"]
            self._use_cookiecloud = conf["use_cookiecloud"]
            self._douban_cookie = conf["douban_cookie"]
            self._watch_threshold_percent = conf["watch_threshold_percent"]
            self._private = conf["private"]
            self._clean_wish = conf["clean_wish"]
            logger.info(
                f"{self.plugin_name}：配置已加载（启用={self._enabled}，周期={self._cron}，Cookie来源={self._cookie_source_label()}）"
            )

        # 立即运行一次
        if self._onlyonce:
            logger.info(f"{self.plugin_name}：立即运行一次")
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(
                func=self.sync, trigger="date",
                run_date=datetime.datetime.now(
                    tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3),
            )
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()
            # 关闭一次性开关
            self._onlyonce = False
            # 保存配置
            self.__update_config()

    def __update_config(self):
        """保存配置（分身友好：按 self.__class__.__name__ 读写）"""
        self.update_config(self._current_config())

    def get_state(self) -> bool:
        return bool(self._enabled)

    def stop_service(self):
        """停止插件服务"""
        try:
            if self._scheduler and self._scheduler.running:
                self._scheduler.shutdown(wait=False)
        except Exception as e:
            logger.error(f"{self.plugin_name}：停止定时任务失败：{e}")
        finally:
            self._scheduler = None

    def get_service(self) -> List[Dict[str, Any]]:
        """注册插件公共服务（CronTrigger 定时同步）"""
        if not self._enabled or not self._cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except ValueError as e:
            logger.error(f"{self.plugin_name}：Cron 表达式无效 ({self._cron})：{e}")
            return []
        return [{
            "id": f"{self.__class__.__name__}.sync",
            "name": "飞牛影视豆瓣同步",
            "trigger": trigger,
            "func": self.sync,
            "kwargs": {},
        }]

    # ── 远程命令 ─────────────────────────────────────

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程控制命令"""
        return [{
            "cmd": "/fntv_douban_sync",
            "event": EventType.PluginAction,
            "desc": "同步飞牛影视观看记录到豆瓣",
            "category": "插件",
            "data": {
                "action": "fntv_douban_sync",
            },
        }]

    @eventmanager.register(EventType.PluginAction)
    def sync_by_command(self, event: Event = None):
        """命令触发同步：先提示开始，结束后定向回复结果"""
        reply_to = None
        if event:
            event_data = event.event_data or {}
            if not event_data or event_data.get("action") != "fntv_douban_sync":
                return
            reply_to = {"channel": event_data.get("channel"), "user": event_data.get("user")}
            logger.info("收到命令，开始同步飞牛影视观看记录到豆瓣 ...")
            self.post_message(channel=reply_to.get("channel"), mtype=NotificationType.Plugin,
                              title="开始同步飞牛影视观看记录 ...", userid=reply_to.get("user"))
        result = self._do_sync(reply_to=reply_to)
        logger.info(f"命令同步完成：{result}")

    # ── 同步编排 ─────────────────────────────────────

    def sync(self) -> str:
        """定时任务 / 一次性任务入口，返回结果摘要"""
        return self._do_sync()

    def _get_store(self) -> SyncStore:
        """本地同步状态库（落在插件数据目录）"""
        if self._store is None:
            self._store = SyncStore(self.get_data_path())
        return self._store

    def _get_effective_cookie(self) -> Tuple[str, str]:
        """解析豆瓣 Cookie：手动值优先于 CookieCloud，均无返回 ("", "none")

        返回 (cookie, source)，source 为 "manual" / "cookiecloud" / "none"。
        CookieCloudHelper 按域名最后两级聚合，douban.com 汇总所有豆瓣子域 Cookie。
        """
        if self._douban_cookie:
            return self._douban_cookie, "manual"
        if self._use_cookiecloud:
            try:
                from app.helper.cookiecloud import CookieCloudHelper
                cookies, err = CookieCloudHelper().download()
            except Exception as e:
                logger.error(f"CookieCloud 调用异常：{e}")
                return "", "none"
            if err:
                logger.warning(f"CookieCloud 获取豆瓣 Cookie 失败：{err}")
                return "", "none"
            cookie = (cookies or {}).get("douban.com", "")
            if cookie:
                return cookie, "cookiecloud"
            logger.warning("CookieCloud 中未找到 douban.com 的 Cookie")
        return "", "none"

    def _cookie_source_label(self) -> str:
        """状态展示用的 Cookie 来源（不触发 CookieCloud 请求）"""
        if self._douban_cookie:
            return "manual"
        if self._use_cookiecloud:
            return "cookiecloud"
        return "none"

    def _reply_or_notify(self, title: str, text: str, reply_to: Optional[dict]):
        """命令触发的同步定向回复；定时/手动触发受 notify 开关控制"""
        if reply_to is not None:
            self.post_message(channel=reply_to.get("channel"), mtype=NotificationType.Plugin,
                              title=title, text=text, userid=reply_to.get("user"))
        elif self._notify:
            self.post_message(mtype=NotificationType.Plugin, title=title, text=text)

    def _is_running(self) -> bool:
        return bool(self._syncing or (self._engine and self._engine.is_running))

    def _record_run_safely(self, status: str, message: str, log_error: bool = False):
        try:
            store = self._get_store()
            if log_error:
                store.log_action(uuid.uuid4().hex[:12], "sync_error", detail=message)
            store.record_run_result(status, message)
        except Exception as e:
            logger.error(f"{self.plugin_name}：记录运行状态失败：{e}")

    def _do_sync(self, reply_to: Optional[dict] = None, already_locked: bool = False) -> str:
        """执行一次同步，返回人类可读的结果摘要"""
        if not already_locked:
            if not self._sync_lock.acquire(blocking=False):
                logger.warning("同步正在执行中，本次跳过")
                return "已有同步任务正在执行，本次跳过"
            if self._is_running():
                self._sync_lock.release()
                logger.warning("同步正在执行中，本次跳过")
                return "已有同步任务正在执行，本次跳过"
            self._syncing = True

        try:
            def _fail(msg: str) -> str:
                logger.error(f"{self.plugin_name}：{msg}")
                self._record_run_safely("error", msg, log_error=True)
                self._reply_or_notify(self.plugin_name, f"⚠️ {msg}", reply_to)
                return msg

            if not self._fntv_db_path:
                return _fail("未配置飞牛影视数据库路径")
            if not self._selected_user:
                return _fail("未选择飞牛影视同步用户")
            cookie, _source = self._get_effective_cookie()
            if not cookie:
                return _fail("豆瓣 Cookie 未配置或获取失败")

            try:
                fntv = FntvDb(self._fntv_db_path, self.get_data_path())
                ok, err = fntv.validate()
                if not ok:
                    return _fail(f"飞牛影视数据库不可用：{err}")
            except Exception as e:
                return _fail(f"飞牛影视数据库不可用：{e}")

            captured = []

            def on_summary(title: str, body: str):
                captured.append((title, body))
                self._reply_or_notify(title, body, reply_to)

            engine = SyncEngine(fntv, self._get_store(), cookie,
                                watch_threshold_percent=self._watch_threshold_percent,
                                private=self._private,
                                clean_wish=self._clean_wish,
                                notify_callback=on_summary)
            self._engine = engine
            run_id = engine.run(self._selected_user)
            if not run_id:
                logger.warning("同步正在执行中，本次跳过")
                return "已有同步任务正在执行，本次跳过"
            outcome_status, outcome_msg = engine.last_outcome
            summary_text = outcome_msg or (captured[0][1] if captured else "同步完成，本次无状态变更")
            self._record_run_safely(outcome_status, summary_text)
            if captured:
                return captured[0][1]
            return summary_text
        finally:
            self._syncing = False
            self._sync_lock.release()

    def _do_sync_locked_entry(self):
        self._do_sync(already_locked=True)

    # ── 飞牛数据库辅助 ───────────────────────────────

    def _get_fntv_users(self) -> Tuple[List[dict], bool, str]:
        """尝试读取飞牛用户列表，返回 (users, ok, error)"""
        if not self._fntv_db_path:
            return [], False, ""
        try:
            fntv = FntvDb(self._fntv_db_path, self.get_data_path())
            ok, err = fntv.validate()
            if not ok:
                return [], False, err
            return fntv.get_users(), True, ""
        except Exception as e:
            return [], False, str(e)

    # ── 插件 API ─────────────────────────────────────

    def get_api(self) -> List[Dict[str, Any]]:
        """注册插件 API，宿主挂载于 /api/v1/plugin/FntvDoubanSync/..."""
        return [
            {"path": "/status", "endpoint": self.api_status, "methods": ["GET"],
             "auth": "bear", "summary": "获取同步状态与统计"},
            {"path": "/fntv/test-db", "endpoint": self.api_test_db, "methods": ["POST"],
             "auth": "bear", "summary": "测试飞牛数据库路径"},
            {"path": "/fntv/users", "endpoint": self.api_fntv_users, "methods": ["GET"],
             "auth": "bear", "summary": "获取飞牛用户列表"},
            {"path": "/douban/check-cookie", "endpoint": self.api_check_cookie, "methods": ["POST"],
             "auth": "bear", "summary": "校验豆瓣 Cookie"},
            {"path": "/sync/run", "endpoint": self.api_sync_run, "methods": ["POST"],
             "auth": "bear", "summary": "立即同步一次"},
            {"path": "/logs", "endpoint": self.api_logs, "methods": ["GET"],
             "auth": "bear", "summary": "分页查询同步日志"},
            {"path": "/config", "endpoint": self.api_get_config, "methods": ["GET"],
             "auth": "bear", "summary": "读取插件配置"},
            {"path": "/config", "endpoint": self.api_save_config, "methods": ["POST"],
             "auth": "bear", "summary": "保存插件配置"},
        ]

    def api_status(self) -> dict:
        """GET /status：状态与统计概览"""
        stats = {"total": 0, "done": 0, "doing": 0, "failed": 0}
        last_run = {"last_run_at": 0, "last_run_status": "", "last_run_message": ""}
        try:
            store = self._get_store()
            if self._selected_user:
                stats = store.get_stats(self._selected_user)
            last_sync_time = store.get_last_sync_time()
            last_run = store.get_last_run()
        except Exception as e:
            logger.error(f"读取同步状态失败：{e}")
            last_sync_time = 0
        return {
            "running": self._is_running(),
            "enabled": bool(self._enabled),
            "fntv_db_path": self._fntv_db_path,
            "selected_user": self._selected_user,
            "cookie_source": self._cookie_source_label(),
            "last_sync_time": last_sync_time,
            "last_run_at": last_run["last_run_at"],
            "last_run_status": last_run["last_run_status"],
            "last_run_message": last_run["last_run_message"],
            "stats": stats,
        }

    def api_test_db(self, data: dict) -> dict:
        """POST /fntv/test-db：校验数据库路径可读性及 item 表"""
        db_path = (data or {}).get("db_path", "")
        try:
            fntv = FntvDb(db_path, self.get_data_path())
            ok, err = fntv.validate()
            return {"ok": ok, "error": "" if ok else err}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def api_fntv_users(self, db_path: str = "") -> dict:
        """GET /fntv/users：读取飞牛活跃用户列表"""
        db_path = db_path or self._fntv_db_path
        if not db_path:
            return {"ok": False, "users": [], "error": "未配置数据库路径"}
        try:
            fntv = FntvDb(db_path, self.get_data_path())
            ok, err = fntv.validate()
            if not ok:
                return {"ok": False, "users": [], "error": err}
            return {"ok": True, "users": fntv.get_users(), "error": ""}
        except Exception as e:
            return {"ok": False, "users": [], "error": str(e)}

    def api_check_cookie(self, data: dict) -> dict:
        """POST /douban/check-cookie：实时校验手动或 CookieCloud 豆瓣 Cookie"""
        data = data or {}
        cookie = str(data.get("cookie") or "")
        if not cookie and self._as_bool(data.get("use_cookiecloud")):
            try:
                from app.helper.cookiecloud import CookieCloudHelper
                cookies, err = CookieCloudHelper().download()
            except Exception as e:
                return {"ok": False, "reason": "cookiecloud_error",
                        "message": f"CookieCloud 调用异常：{e}", "source": "cookiecloud"}
            cookie = (cookies or {}).get("douban.com", "")
            if not cookie:
                return {"ok": False, "reason": "cookiecloud_failed",
                        "message": err or "CookieCloud 中未找到 douban.com 的 Cookie",
                        "source": "cookiecloud"}
            return {**self._check_cookie_detail(cookie), "source": "cookiecloud"}
        if not cookie:
            return {"ok": False, "reason": "no_cookie",
                    "message": "请填写豆瓣 Cookie 或开启 CookieCloud", "source": "none"}
        return {**self._check_cookie_detail(cookie), "source": "manual"}

    @staticmethod
    def _check_cookie_detail(cookie: str) -> dict:
        try:
            return DoubanClient(cookie).check_auth_detail()
        except Exception as e:
            return {"ok": False, "reason": "error", "message": str(e)}

    def api_sync_run(self) -> dict:
        """POST /sync/run：后台线程异步触发一次同步"""
        if not self._sync_lock.acquire(blocking=False):
            return {"ok": False, "running": True, "message": "同步正在进行中，请稍候"}
        if self._is_running():
            self._sync_lock.release()
            return {"ok": False, "running": True, "message": "同步正在进行中，请稍候"}
        self._syncing = True
        try:
            self._sync_thread = threading.Thread(
                target=self._do_sync_locked_entry,
                name=f"{self.__class__.__name__}-sync",
                daemon=True,
            )
            self._sync_thread.start()
        except Exception:
            self._syncing = False
            self._sync_lock.release()
            raise
        return {"ok": True, "running": True, "message": "同步已开始"}

    def api_logs(self, limit: int = 50, offset: int = 0,
                 action: str = "", keyword: str = "") -> dict:
        """GET /logs：分页查询 sync_log"""
        limit = max(1, min(200, limit))
        offset = max(0, offset)
        store = self._get_store()
        return {
            "total": store.count_logs(action=action, keyword=keyword),
            "items": store.get_logs(limit=limit, offset=offset,
                                    action=action, keyword=keyword),
        }

    def api_get_config(self) -> dict:
        """GET /config：读取当前完整配置"""
        return self._current_config()

    def api_save_config(self, data: dict) -> dict:
        """POST /config：校验并保存配置"""
        conf = self._normalize_config({**self._current_config(), **(data or {})})
        ok, err = self._validate_cron(conf["cron"])
        if not ok:
            return {"ok": False, "message": f"Cron 表达式无效：{err}"}
        self.update_config(conf)
        self.init_plugin(conf)
        return {"ok": True, "message": "配置已保存并生效"}

    # ── Vue 联邦前端 ─────────────────────────────────

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦组件渲染插件界面（构建产物位于 dist/assets）"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """Vue 配置组件只需接收当前配置模型（宿主以 initial-config 传入）"""
        return [], self._current_config()

    def get_page(self) -> List[dict]:
        """Vue 详情组件自行通过插件 API 获取数据"""
        return []

    def get_dashboard(self, key: str = None, **kwargs) -> Tuple[Dict[str, Any], Dict[str, Any], None]:
        """仪表板由 Vue 组件渲染，此处仅返回布局与全局配置"""
        if not self.get_state():
            return None
        cols = {"cols": 12, "md": 6}
        attrs = {
            "title": "飞牛影视豆瓣同步",
            "refresh": 60,
            "border": True,
        }
        return cols, attrs, None
