"""FntvDoubanSync 插件集成测试（离线，宿主以桩替换）"""

import unittest
from unittest.mock import MagicMock

from app.core.event import Event
from app.helper.cookiecloud import CookieCloudHelper
from app.plugins.fntvdoubansync import FntvDoubanSync
from app.plugins.fntvdoubansync.sync_store import SyncStore

MANUAL_COOKIE = 'ck=test; dbcl2="1:abc"'
CLOUD_COOKIE = "ck=cloud; dbcl2=cloud"

BASE_CONFIG = {
    "enabled": True,
    "notify": True,
    "onlyonce": False,
    "cron": "0 3 * * *",
    "fntv_db_path": "",
    "selected_user": "u1",
    "use_cookiecloud": False,
    "douban_cookie": MANUAL_COOKIE,
    "watch_threshold_percent": 90,
    "private": True,
    "clean_wish": False,
}


def config_with(db_path, **extra):
    return {**BASE_CONFIG, "fntv_db_path": str(db_path), **extra}


def douban_client_mock(monkeypatch):
    """把同步引擎中的 DoubanClient 替换为可控假件，返回 (类 mock, 实例 mock)"""
    client_cls = MagicMock(name="DoubanClient")
    client = client_cls.return_value
    client.check_auth.return_value = True
    client.error_count = 0
    client.search_subject.return_value = ("测试电影", "100")
    client.mark_interest.return_value = True
    monkeypatch.setattr("app.plugins.fntvdoubansync.sync_engine.DoubanClient", client_cls)
    return client_cls, client


# ── 配置与生命周期 ───────────────────────────────────


class PluginConfigTests(unittest.TestCase):

    def setUp(self):
        self.plugin = FntvDoubanSync()

    def test_init_plugin_loads_config(self):
        self.plugin.init_plugin(config_with("/db/trimmedia.db"))
        self.assertTrue(self.plugin._enabled)
        self.assertEqual(self.plugin._cron, "0 3 * * *")
        self.assertEqual(self.plugin._fntv_db_path, "/db/trimmedia.db")
        self.assertEqual(self.plugin._selected_user, "u1")
        self.assertEqual(self.plugin._douban_cookie, MANUAL_COOKIE)
        self.assertEqual(self.plugin._watch_threshold_percent, 90)

    def test_watch_threshold_clamped(self):
        self.plugin.init_plugin({**BASE_CONFIG, "watch_threshold_percent": 150})
        self.assertEqual(self.plugin._watch_threshold_percent, 100)
        self.plugin.init_plugin({**BASE_CONFIG, "watch_threshold_percent": -5})
        self.assertEqual(self.plugin._watch_threshold_percent, 0)
        self.plugin.init_plugin({**BASE_CONFIG, "watch_threshold_percent": "abc"})
        self.assertEqual(self.plugin._watch_threshold_percent, 90)

    def test_get_state_follows_enabled(self):
        self.plugin.init_plugin({**BASE_CONFIG, "enabled": False})
        self.assertFalse(self.plugin.get_state())
        self.plugin.init_plugin({**BASE_CONFIG, "enabled": True})
        self.assertTrue(self.plugin.get_state())

    def test_get_service_registers_cron(self):
        from apscheduler.triggers.cron import CronTrigger

        self.plugin.init_plugin({**BASE_CONFIG, "enabled": False})
        self.assertEqual(self.plugin.get_service(), [])

        self.plugin.init_plugin({**BASE_CONFIG})
        services = self.plugin.get_service()
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]["id"], f"{self.plugin.__class__.__name__}.sync")
        self.assertEqual(services[0]["name"], "飞牛影视豆瓣同步")
        self.assertEqual(services[0]["func"], self.plugin.sync)
        self.assertIsInstance(services[0]["trigger"], CronTrigger)
        trigger_str = str(services[0]["trigger"])
        self.assertIn("hour='3'", trigger_str)
        self.assertIn("minute='0'", trigger_str)

    def test_stop_service_clears_scheduler(self):
        self.plugin.init_plugin({**BASE_CONFIG, "onlyonce": True})
        self.assertIsNotNone(self.plugin._scheduler)
        # 一次性开关自动复位并持久化
        self.assertFalse(self.plugin._onlyonce)
        self.assertFalse(self.plugin.get_config()["onlyonce"])
        self.plugin.stop_service()
        self.assertIsNone(self.plugin._scheduler)

    def test_get_command_registers_action(self):
        commands = self.plugin.get_command()
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["cmd"], "/fntv_douban_sync")
        self.assertEqual(commands[0]["category"], "插件")
        self.assertEqual(commands[0]["data"]["action"], "fntv_douban_sync")

    def test_get_api_registers_all_routes(self):
        paths = {(api["path"], m) for api in self.plugin.get_api() for m in api["methods"]}
        expected = {
            ("/status", "GET"), ("/fntv/test-db", "POST"), ("/fntv/users", "GET"),
            ("/douban/check-cookie", "POST"), ("/sync/run", "POST"), ("/logs", "GET"),
            ("/config", "GET"), ("/config", "POST"),
        }
        self.assertTrue(expected.issubset(paths))
        for api in self.plugin.get_api():
            self.assertEqual(api["auth"], "bear")

    def test_get_form_returns_config_model_for_vue(self):
        """Vue 模式：get_form 只提供配置模型，界面由联邦组件渲染"""
        self.plugin.init_plugin(config_with("/db/trimmedia.db"))
        conf, model = self.plugin.get_form()
        self.assertEqual(conf, [])
        self.assertEqual(model, self.plugin._current_config())
        self.assertEqual(model["cron"], "0 3 * * *")
        self.assertEqual(model["watch_threshold_percent"], 90)
        self.assertEqual(model["douban_cookie"], MANUAL_COOKIE)

    def test_get_render_mode_declares_vue_federation(self):
        render_mode, dist_path = self.plugin.get_render_mode()
        self.assertEqual(render_mode, "vue")
        self.assertEqual(dist_path, "dist/assets")


# ── Cookie 解析优先级 ───────────────────────────────


def test_manual_cookie_takes_priority_over_cookiecloud(plugin, fntv_db_file,
                                                       cookiecloud_stub, monkeypatch):
    client_cls, client = douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file, use_cookiecloud=True))
    result = plugin.sync()
    assert "已看完" in result
    assert cookiecloud_stub.calls == 0
    client_cls.assert_called_once_with(MANUAL_COOKIE)


def test_cookiecloud_used_when_manual_empty(plugin, fntv_db_file, monkeypatch, cookiecloud_stub):
    cookiecloud_stub.result = ({"douban.com": CLOUD_COOKIE, "movie.douban.com": "x=1"}, "")
    douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file, douban_cookie="",
                                   use_cookiecloud=True))
    result = plugin.sync()
    assert "已看完" in result
    assert cookiecloud_stub.calls == 1


def test_cookiecloud_error_fails_gracefully(plugin, fntv_db_file, monkeypatch, cookiecloud_stub):
    cookiecloud_stub.result = (None, "CookieCloud参数不正确")
    douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file, douban_cookie="",
                                   use_cookiecloud=True))
    result = plugin.sync()
    assert "豆瓣 Cookie 未配置或获取失败" in result
    assert plugin.post_messages and "Cookie" in plugin.post_messages[-1]["text"]


def test_no_cookie_does_not_construct_client(plugin, fntv_db_file, monkeypatch):
    client_cls, _ = douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file, douban_cookie=""))
    plugin.sync()
    client_cls.assert_not_called()


# ── 同步主流程 ───────────────────────────────────────


def test_full_sync_marks_movie_done(plugin, fntv_db_file, monkeypatch):
    client_cls, client = douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file))
    result = plugin.sync()

    assert "已看完" in result
    # 豆瓣标记为「看过」，且带隐私参数
    client.mark_interest.assert_called_once_with("100", "done", True)
    # 状态落库
    store = SyncStore(plugin.get_data_path())
    state = store.get_state("u1", "movie-1")
    assert state["status"] == "done"
    assert state["douban_subject_id"] == "100"
    # 临时副本与状态库都在插件数据目录内
    data_path = plugin.get_data_path()
    assert (data_path / "trimmedia_tmp.db").exists()
    assert (data_path / "sync_state.db").exists()
    # notify=True → 推送一条同步完成摘要
    assert any("同步完成" in m["title"] for m in plugin.post_messages)


def test_notify_disabled_silences_summary(plugin, fntv_db_file, monkeypatch):
    douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file, notify=False))
    plugin.sync()
    assert plugin.post_messages == []


def test_missing_user_alerts_without_sync(plugin, fntv_db_file, monkeypatch):
    client_cls, _ = douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file, selected_user=""))
    plugin.sync()
    client_cls.assert_not_called()
    assert any("未选择" in m["text"] for m in plugin.post_messages)


def test_sync_run_api_runs_in_background(plugin, fntv_db_file, monkeypatch):
    douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file))
    ret = plugin.api_sync_run()
    assert ret == {"ok": True, "running": True, "message": "同步已开始"}
    assert plugin._sync_thread is not None
    plugin._sync_thread.join(timeout=30)
    assert SyncStore(plugin.get_data_path()).get_state("u1", "movie-1")["status"] == "done"


def test_sync_run_api_rejects_when_running(plugin, fntv_db_file, monkeypatch):
    engine = MagicMock()
    engine.is_running = True
    plugin._engine = engine
    assert plugin.api_sync_run() == {
        "ok": False, "running": True, "message": "同步正在进行中，请稍候",
    }


# ── 远程命令 ─────────────────────────────────────────


def test_command_event_triggers_sync_and_replies(plugin, fntv_db_file, monkeypatch):
    douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file))
    event = Event(event_data={
        "action": "fntv_douban_sync", "channel": "telegram", "user": "user-9",
    })
    plugin.sync_by_command(event)

    titles = [m["title"] for m in plugin.post_messages]
    assert "开始同步飞牛影视观看记录 ..." in titles
    # 结果定向回复命令发起者
    reply = plugin.post_messages[-1]
    assert reply["channel"] == "telegram"
    assert reply["userid"] == "user-9"
    assert "已看完" in reply["text"]
    assert SyncStore(plugin.get_data_path()).get_state("u1", "movie-1")["status"] == "done"


def test_command_event_ignores_other_actions(plugin, fntv_db_file, monkeypatch):
    client_cls, _ = douban_client_mock(monkeypatch)
    plugin.init_plugin(config_with(fntv_db_file))
    plugin.sync_by_command(Event(event_data={"action": "douban_sync"}))
    client_cls.assert_not_called()
    assert plugin.post_messages == []


# ── 插件 API ─────────────────────────────────────────


def test_api_status(plugin, fntv_db_file):
    plugin.init_plugin(config_with(fntv_db_file))
    status = plugin.api_status()
    assert status["running"] is False
    assert status["enabled"] is True
    assert status["fntv_db_path"] == str(fntv_db_file)
    assert status["selected_user"] == "u1"
    assert status["cookie_source"] == "manual"
    assert status["last_sync_time"] == 0
    assert status["last_run_at"] == 0
    assert status["last_run_status"] == ""
    assert status["last_run_message"] == ""
    assert status["stats"] == {"total": 0, "done": 0, "doing": 0, "failed": 0}


def test_init_plugin_empty_preserves_default_db_path(plugin):
    plugin.init_plugin({})
    assert plugin._fntv_db_path == "/fntv-db/trimmedia.db"


def test_invalid_cron_handled_safely(plugin, fntv_db_file):
    plugin.init_plugin(config_with(fntv_db_file, cron="invalid cron"))
    assert plugin.get_service() == []
    ret = plugin.api_save_config({"cron": "bad"})
    assert ret["ok"] is False
    assert "Cron" in ret["message"]


def test_preflight_failure_logs_sync_error_and_last_run(plugin, fntv_db_file):
    plugin.init_plugin(config_with(fntv_db_file, selected_user=""))
    msg = plugin.sync()
    assert "未选择" in msg
    status = plugin.api_status()
    assert status["last_run_at"] > 0
    assert status["last_run_status"] == "error"
    assert "未选择" in status["last_run_message"]
    logs = plugin.api_logs(action="sync_error")
    assert logs["total"] == 1
    assert "未选择" in logs["items"][0]["detail"]


def test_api_status_reports_running_and_cookiecloud_source(plugin, fntv_db_file):
    engine = MagicMock()
    engine.is_running = True
    plugin._engine = engine
    plugin.init_plugin(config_with(fntv_db_file, douban_cookie="", use_cookiecloud=True))
    status = plugin.api_status()
    assert status["running"] is True
    assert status["cookie_source"] == "cookiecloud"


def test_api_test_db(plugin, fntv_db_file):
    ret = plugin.api_test_db({"db_path": str(fntv_db_file)})
    assert ret == {"ok": True, "error": ""}
    ret = plugin.api_test_db({"db_path": "/not/exist/trimmedia.db"})
    assert ret["ok"] is False


def test_api_fntv_users(plugin, fntv_db_file):
    plugin.init_plugin(config_with(fntv_db_file))
    ret = plugin.api_fntv_users()
    assert ret["ok"] is True
    assert ret["users"] == [{"guid": "u1", "username": "测试用户"}]

    ret = plugin.api_fntv_users(db_path=str(fntv_db_file))
    assert ret["ok"] is True

    plugin.init_plugin(config_with(fntv_db_file, fntv_db_path=""))
    ret = plugin.api_fntv_users()
    assert ret["ok"] is False
    assert "未配置数据库路径" in ret["error"]


def test_api_check_cookie_manual(plugin, monkeypatch):
    client_cls = MagicMock(name="DoubanClient")
    client_cls.return_value.check_auth_detail.return_value = {
        "ok": True, "reason": "", "message": "Cookie 有效"}
    monkeypatch.setattr("app.plugins.fntvdoubansync.DoubanClient", client_cls)

    ret = plugin.api_check_cookie({"cookie": MANUAL_COOKIE, "use_cookiecloud": False})
    assert ret == {"ok": True, "reason": "", "message": "Cookie 有效", "source": "manual"}
    client_cls.assert_called_once_with(MANUAL_COOKIE)


def test_api_check_cookie_cookiecloud(plugin, monkeypatch, cookiecloud_stub):
    cookiecloud_stub.result = ({"douban.com": CLOUD_COOKIE}, "")
    client_cls = MagicMock(name="DoubanClient")
    client_cls.return_value.check_auth_detail.return_value = {
        "ok": False, "reason": "cookie_expired", "message": "Cookie 已过期"}
    monkeypatch.setattr("app.plugins.fntvdoubansync.DoubanClient", client_cls)

    ret = plugin.api_check_cookie({"cookie": "", "use_cookiecloud": True})
    assert ret["source"] == "cookiecloud"
    assert ret["ok"] is False
    client_cls.assert_called_once_with(CLOUD_COOKIE)


def test_api_check_cookie_cookiecloud_failed(plugin, cookiecloud_stub):
    cookiecloud_stub.result = ({}, "远程同步CookieCloud失败，错误码：500")
    ret = plugin.api_check_cookie({"cookie": "", "use_cookiecloud": True})
    assert ret["ok"] is False
    assert ret["source"] == "cookiecloud"
    assert "500" in ret["message"]


def test_api_check_cookie_empty(plugin, cookiecloud_stub):
    ret = plugin.api_check_cookie({"cookie": "", "use_cookiecloud": False})
    assert ret == {"ok": False, "reason": "no_cookie",
                   "message": "请填写豆瓣 Cookie 或开启 CookieCloud", "source": "none"}


def test_api_logs_pagination_and_filters(plugin):
    store = plugin._get_store()
    store.log_action("run1", "mark_done", "m1", "测试电影", "豆瓣ID=100")
    store.log_action("run1", "error_search", "m2", "未知影片", "豆瓣搜索无结果")
    store.log_action("run2", "mark_done", "m3", "另一部", "豆瓣ID=200")

    ret = plugin.api_logs()
    assert ret["total"] == 3
    assert len(ret["items"]) == 3

    ret = plugin.api_logs(action="mark_done")
    assert ret["total"] == 2
    assert all(item["action"] == "mark_done" for item in ret["items"])

    ret = plugin.api_logs(keyword="未知影片")
    assert ret["total"] == 1
    assert ret["items"][0]["action"] == "error_search"

    ret = plugin.api_logs(limit=1, offset=1)
    assert len(ret["items"]) == 1


def test_api_config_roundtrip(plugin, fntv_db_file):
    plugin.init_plugin({**BASE_CONFIG, "watch_threshold_percent": 120})
    conf = plugin.api_get_config()
    assert conf["watch_threshold_percent"] == 100
    assert conf["douban_cookie"] == MANUAL_COOKIE

    ret = plugin.api_save_config({
        "fntv_db_path": str(fntv_db_file),
        "douban_cookie": "ck=new",
        "watch_threshold_percent": 50,
    })
    assert ret["ok"] is True
    # 合并保存：未提交字段保留原值
    assert plugin._douban_cookie == "ck=new"
    assert plugin._fntv_db_path == str(fntv_db_file)
    assert plugin._watch_threshold_percent == 50
    assert plugin._selected_user == "u1"
    # 配置已持久化（宿主桩的 update_config）
    assert plugin.get_config()["douban_cookie"] == "ck=new"


# ── 页面与仪表板（Vue 联邦契约） ─────────────────────


def test_get_page_empty_in_vue_mode(plugin, fntv_db_file):
    """Vue 模式：详情页数据由远程 Page 组件经插件 API 自行获取"""
    plugin.init_plugin(config_with(fntv_db_file))
    assert plugin.get_page() == []


def test_get_dashboard_returns_layout_only(plugin, fntv_db_file):
    plugin.init_plugin(config_with(fntv_db_file))
    cols, attrs, elements = plugin.get_dashboard()
    assert cols == {"cols": 12, "md": 6}
    assert attrs["title"] == "飞牛影视豆瓣同步"
    assert attrs["refresh"] == 60
    assert attrs["border"] is True
    assert elements is None


def test_get_dashboard_hidden_when_disabled(plugin):
    plugin.init_plugin({**BASE_CONFIG, "enabled": False})
    assert plugin.get_dashboard() is None


if __name__ == "__main__":
    unittest.main()
