"""MoviePilot 宿主轻量化测试桩

在 sys.modules 中注入最小宿主模块（app.*），并把桩包 app.plugins 的
__path__ 指向仓库 plugins.v2/ 目录——与 MoviePilot 宿主 ModuleHelper 的
加载方式一致（插件以 app.plugins.<pid> 包名导入），使插件包无需完整
MoviePilot 后端源码即可离线运行 pytest。
"""

import logging
import sqlite3
import sys
import tempfile
import types
from enum import Enum
from pathlib import Path

# 测试以宿主同款包名导入插件，关闭字节码写入避免在 plugins.v2/ 下留下 __pycache__
# （插件目录会被 MoviePilot 整目录复制，隔离门禁不允许缓存存在）
sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[3]


def _mk_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _install_host_stubs():
    if "app" in sys.modules and getattr(sys.modules["app"], "__dbsync_stub__", False):
        return

    app_pkg = _mk_module("app")
    app_pkg.__path__ = []
    app_pkg.__dbsync_stub__ = True

    # ── app.log ──────────────────────────────────────
    log_mod = _mk_module("app.log")
    log_mod.logger = logging.getLogger("moviepilot-test")
    logging.getLogger("moviepilot-test").setLevel(logging.DEBUG)

    # ── app.core.config ──────────────────────────────
    core_pkg = _mk_module("app.core")
    core_pkg.__path__ = []

    class _SettingsStub:
        TZ = "Asia/Shanghai"

    config_mod = _mk_module("app.core.config")
    config_mod.settings = _SettingsStub()

    # ── app.core.event ───────────────────────────────
    class EventStub:
        """事件桩：event_data 为普通 dict"""

        def __init__(self, event_type=None, event_data=None, priority=10):
            self.event_type = event_type
            self.event_data = event_data if event_data is not None else {}
            self.priority = priority

    class _EventManagerStub:
        def register(self, etype):
            def deco(func):
                return func
            return deco

        def disable_events_hander(self, pid):
            pass

        def enable_events_hander(self, pid):
            pass

    event_mod = _mk_module("app.core.event")
    event_mod.Event = EventStub
    event_mod.eventmanager = _EventManagerStub()

    # ── app.schemas.types ────────────────────────────
    schemas_pkg = _mk_module("app.schemas")
    schemas_pkg.__path__ = []

    class EventTypeStub:
        PluginAction = "plugin.action"

    class NotificationTypeStub(Enum):
        Plugin = "插件"

    types_mod = _mk_module("app.schemas.types")
    types_mod.EventType = EventTypeStub
    types_mod.NotificationType = NotificationTypeStub

    # ── app.plugins._PluginBase ──────────────────────
    class _PluginBaseStub:
        """内存化宿主插件基类：get_config / update_config / get_data_path /
        post_message / save_data / get_data 全部可在离线测试中断言"""

        def __init__(self):
            self.__configs = {}
            self.__data = {}
            self.__data_paths = {}
            # 记录 post_message 调用，供测试断言
            self.post_messages = []

        def get_config(self, plugin_id=None):
            pid = plugin_id or self.__class__.__name__
            return self.__configs.get(pid)

        def update_config(self, config: dict, plugin_id=None) -> bool:
            pid = plugin_id or self.__class__.__name__
            self.__configs[pid] = config
            return True

        def get_data_path(self, plugin_id=None) -> Path:
            pid = plugin_id or self.__class__.__name__
            if pid not in self.__data_paths:
                self.__data_paths[pid] = Path(tempfile.mkdtemp(prefix=f"mpplug-{pid}-"))
            return self.__data_paths[pid]

        def save_data(self, key, value, plugin_id=None):
            pid = plugin_id or self.__class__.__name__
            self.__data[(pid, key)] = value

        def get_data(self, key=None, plugin_id=None):
            pid = plugin_id or self.__class__.__name__
            return self.__data.get((pid, key))

        def post_message(self, channel=None, mtype=None, title=None, text=None,
                         image=None, link=None, userid=None):
            self.post_messages.append({
                "channel": channel, "mtype": mtype, "title": title,
                "text": text, "userid": userid,
            })

    plugins_mod = _mk_module("app.plugins")
    plugins_mod._PluginBase = _PluginBaseStub
    # 与宿主一致：插件包按 app.plugins.<pid> 加载，插件目录挂在 __path__ 上
    plugins_mod.__path__ = [str(REPO_ROOT / "plugins.v2")]

    # ── app.helper.cookiecloud ───────────────────────
    helper_pkg = _mk_module("app.helper")
    helper_pkg.__path__ = []

    class CookieCloudHelperStub:
        """测试可控桩：默认「未配置」；用例 monkeypatch result / 读取 calls"""

        calls = 0
        result = (None, "CookieCloud参数不正确")

        def __init__(self):
            pass

        def download(self):
            type(self).calls += 1
            return type(self).result

    cookiecloud_mod = _mk_module("app.helper.cookiecloud")
    cookiecloud_mod.CookieCloudHelper = CookieCloudHelperStub

    # 手工构造的模块不走导入机制，需补齐父包属性（monkeypatch 按属性链解析）
    for name, mod in list(sys.modules.items()):
        if name.startswith("app.") and "." in name:
            parent_name, _, child_name = name.rpartition(".")
            parent = sys.modules.get(parent_name)
            if parent is not None and not hasattr(parent, child_name):
                setattr(parent, child_name, mod)


_install_host_stubs()

# 暴露桩对象供 fixture / 用例引用
CookieCloudHelper = sys.modules["app.helper.cookiecloud"].CookieCloudHelper
EventStub = sys.modules["app.core.event"].Event


import pytest


@pytest.fixture
def plugin():
    """未初始化的插件实例（各用例自行 init_plugin）"""
    from app.plugins.fntvdoubansync import FntvDoubanSync
    return FntvDoubanSync()


@pytest.fixture
def fntv_db_file(tmp_path):
    """构造最小飞牛影视数据库（1 用户 + 1 电影 + 1 条已看播放记录），返回路径"""
    return make_fntv_db(tmp_path / "trimmedia.db")


@pytest.fixture
def cookiecloud_stub(monkeypatch):
    """CookieCloud 桩：默认「未配置」，用例可改 result 并断言 calls"""
    monkeypatch.setattr(CookieCloudHelper, "calls", 0)
    monkeypatch.setattr(CookieCloudHelper, "result", (None, "CookieCloud参数不正确"))
    return CookieCloudHelper


def make_fntv_db(path) -> Path:
    """构造最小可用的飞牛影视 trimmedia.db：1 用户 + 1 电影 + 1 条已看播放记录"""
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript("""
            CREATE TABLE user (
                guid TEXT PRIMARY KEY, username TEXT, status INTEGER);
            CREATE TABLE item (
                guid TEXT PRIMARY KEY, parent_guid TEXT, season_number INTEGER,
                episode_number INTEGER, title TEXT, original_title TEXT,
                runtime INTEGER, imdb_id TEXT);
            CREATE TABLE item_user_play (
                item_guid TEXT, user_guid TEXT, ts REAL, watched INTEGER,
                visible INTEGER, update_time INTEGER);
        """)
        conn.execute(
            "INSERT INTO user VALUES ('u1', '测试用户', 1)")
        conn.execute(
            "INSERT INTO item VALUES ('movie-1', '', 0, 0, '测试电影', 'Test Movie', 100, 'tt0000001')")
        conn.execute(
            "INSERT INTO item_user_play VALUES ('movie-1', 'u1', 5700, 1, 1, 1000)")
        conn.commit()
    finally:
        conn.close()
    return Path(path)
