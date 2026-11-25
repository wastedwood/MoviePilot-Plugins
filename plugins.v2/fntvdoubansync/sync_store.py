"""同步状态持久化层——基于 SQLite 的去重、状态追踪、日志"""

import logging
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
import time
from typing import Optional

try:
    from app.log import logger
except ImportError:  # 离线单测环境无 MoviePilot 宿主
    logger = logging.getLogger(__name__)

STORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_guid TEXT NOT NULL,
    item_guid TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK(media_type IN ('movie','episode')),
    series_guid TEXT,
    season_number INTEGER,
    series_title TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','doing','done','failed')),
    douban_subject_id TEXT,
    episode_number INTEGER,
    max_ep_watched INTEGER,
    total_episodes INTEGER,
    play_update_time INTEGER,
    last_synced_at INTEGER DEFAULT (unixepoch()),
    UNIQUE(user_guid, item_guid)
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    action TEXT NOT NULL,
    item_guid TEXT,
    series_title TEXT,
    detail TEXT,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS runtime_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_sync_state_series ON sync_state(user_guid, series_guid, season_number);
CREATE INDEX IF NOT EXISTS idx_sync_log_run ON sync_log(run_id);
CREATE INDEX IF NOT EXISTS idx_sync_state_status ON sync_state(status);
"""


class SyncStore:
    """同步状态管理"""

    def __init__(self, db_dir: str):
        self._db_path = Path(db_dir) / "sync_state.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with closing(self._connect()) as conn, conn:
            conn.executescript(STORE_SCHEMA)

    # ── Sync State ──────────────────────────────────

    def upsert_state(self, user_guid: str, item_guid: str, **kwargs):
        """插入或更新同步状态"""
        fields = ["user_guid", "item_guid", "media_type", "series_guid",
                   "season_number", "series_title", "status", "douban_subject_id",
                   "episode_number", "max_ep_watched", "total_episodes", "play_update_time"]
        data = {k: kwargs.get(k) for k in fields if k in kwargs}
        data["user_guid"] = user_guid
        data["item_guid"] = item_guid
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(f"{k}=excluded.{k}" for k in data)
        sql = (f"INSERT INTO sync_state ({cols}) VALUES ({placeholders}) "
               f"ON CONFLICT(user_guid, item_guid) DO UPDATE SET {updates}, last_synced_at=unixepoch()")
        with closing(self._connect()) as conn, conn:
            conn.execute(sql, list(data.values()))

    def get_state(self, user_guid: str, item_guid: str) -> dict | None:
        """获取单条同步状态"""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM sync_state WHERE user_guid=? AND item_guid=?",
                (user_guid, item_guid)
            ).fetchone()
            return dict(row) if row else None

    def get_series_status(self, user_guid: str, series_guid: str, season_number: int) -> str | None:
        """获取某剧某季的当前最高状态"""
        with closing(self._connect()) as conn:
            for st in ("done", "doing", "pending"):
                exists = conn.execute(
                    "SELECT 1 FROM sync_state WHERE user_guid=? AND series_guid=? AND season_number=? AND status=? LIMIT 1",
                    (user_guid, series_guid, season_number, st)
                ).fetchone()
                if exists:
                    return st
            return None

    def get_done_subjects(self, user_guid: str) -> list[dict]:
        """获取本地已记为看过的豆瓣条目，按 subject_id 去重"""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT douban_subject_id, MAX(COALESCE(series_title, '')) AS title
                   FROM sync_state
                   WHERE user_guid=? AND status='done'
                     AND douban_subject_id IS NOT NULL AND douban_subject_id != ''
                   GROUP BY douban_subject_id""",
                (user_guid,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_season_subjects(self, user_guid: str) -> list[dict]:
        """按 (剧集, 季, 豆瓣条目) 汇总已同步的电视剧季，status 取 done 优先"""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT series_guid, season_number, douban_subject_id,
                          MAX(COALESCE(series_title, '')) AS series_title,
                          MAX(max_ep_watched) AS max_ep_watched,
                          MAX(total_episodes) AS total_episodes,
                          CASE WHEN SUM(status='done') > 0 THEN 'done' ELSE 'doing' END AS status
                   FROM sync_state
                   WHERE user_guid=? AND media_type='episode' AND status IN ('done','doing')
                     AND douban_subject_id IS NOT NULL AND douban_subject_id != ''
                   GROUP BY series_guid, season_number, douban_subject_id""",
                (user_guid,)
            ).fetchall()
            return [dict(row) for row in rows]

    def update_season_subject(self, user_guid: str, series_guid: str, season_number: int,
                              old_subject_id: str, new_subject_id: str, status: str):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """UPDATE sync_state SET douban_subject_id=?, status=?, last_synced_at=unixepoch()
                   WHERE user_guid=? AND series_guid=? AND season_number=? AND douban_subject_id=?
                     AND status IN ('done','doing')""",
                (new_subject_id, status, user_guid, series_guid, season_number, old_subject_id)
            )

    def get_doing_movies(self, user_guid: str) -> list[dict]:
        """获取处于在看状态的电影记录"""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT item_guid, COALESCE(series_title, '') AS series_title,
                          COALESCE(douban_subject_id, '') AS douban_subject_id
                   FROM sync_state
                   WHERE user_guid=? AND media_type='movie' AND status='doing'""",
                (user_guid,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_doing_seasons(self, user_guid: str) -> list[dict]:
        """按 (剧集, 季) 汇总仍处于在看状态的电视剧季（排除已有 done 记录的季）"""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT series_guid, season_number,
                          MAX(COALESCE(series_title, '')) AS series_title,
                          MAX(COALESCE(douban_subject_id, '')) AS douban_subject_id,
                          MAX(COALESCE(max_ep_watched, 0)) AS max_ep_watched,
                          MAX(COALESCE(total_episodes, 0)) AS total_episodes
                   FROM sync_state s
                   WHERE s.user_guid=? AND s.media_type='episode' AND s.status='doing'
                     AND s.series_guid IS NOT NULL AND s.series_guid != ''
                     AND NOT EXISTS (
                         SELECT 1 FROM sync_state d
                         WHERE d.user_guid=s.user_guid AND d.series_guid=s.series_guid
                           AND d.season_number=s.season_number AND d.status='done'
                     )
                   GROUP BY s.series_guid, s.season_number""",
                (user_guid,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_protected_subject_ids(self, user_guid: str,
                                  exclude_guids: set[str] | None = None) -> set[str]:
        """返回不应移出豆瓣的 subject_id（已看完条目，及未在排除集合中的有效在看条目）"""
        exclude = set(exclude_guids or ())
        protected = set()
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT item_guid, COALESCE(series_guid, '') AS series_guid,
                          status, douban_subject_id
                   FROM sync_state
                   WHERE user_guid=? AND status IN ('done','doing')
                     AND douban_subject_id IS NOT NULL AND douban_subject_id != ''""",
                (user_guid,)
            ).fetchall()
            for r in rows:
                if r["status"] == "done":
                    protected.add(r["douban_subject_id"])
                elif r["item_guid"] not in exclude and r["series_guid"] not in exclude:
                    protected.add(r["douban_subject_id"])
        return protected

    def get_doing_log_subjects(self, item_guid: str) -> list[str]:
        """从 mark_doing 日志中解析实际标记为在看的豆瓣条目 ID（排除分段已标记为 done 的 ID）"""
        if not item_guid:
            return []
        sids = []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT detail FROM sync_log WHERE action='mark_doing' AND item_guid=?",
                (item_guid,)
            ).fetchall()
        for r in rows:
            detail = r["detail"] or ""
            done_ids = set(re.findall(r"(\d+)\(done\)", detail))
            for sid in re.findall(r"(\d+)\(doing\)", detail):
                if sid not in done_ids and sid not in sids:
                    sids.append(sid)
            m = re.search(r"豆瓣ID=(\d+)(?!\()", detail)
            if m and m.group(1) not in done_ids and m.group(1) not in sids:
                sids.append(m.group(1))
        return sids

    def mark_season_done(self, user_guid: str, series_guid: str, season_number: int,
                         subject_id: str, max_ep_watched: int, total_episodes: int):
        """将某季所有 doing 记录升级为 done"""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """UPDATE sync_state
                   SET status='done', douban_subject_id=?, max_ep_watched=?,
                       total_episodes=?, last_synced_at=unixepoch()
                   WHERE user_guid=? AND series_guid=? AND season_number=? AND status='doing'""",
                (subject_id, max_ep_watched, total_episodes, user_guid, series_guid, season_number)
            )

    def delete_item_doing_state(self, user_guid: str, item_guid: str):
        """删除已从飞牛库移除的电影 doing 记录"""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "DELETE FROM sync_state WHERE user_guid=? AND item_guid=? AND status='doing'",
                (user_guid, item_guid)
            )

    def delete_season_doing_state(self, user_guid: str, series_guid: str, season_number: int):
        """删除已从飞牛库移除的电视剧季 doing 记录"""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "DELETE FROM sync_state WHERE user_guid=? AND series_guid=? AND season_number=? AND status='doing'",
                (user_guid, series_guid, season_number)
            )

    def get_stats(self, user_guid: str) -> dict:
        """获取同步统计"""
        with closing(self._connect()) as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS total,
                          COALESCE(SUM(CASE WHEN status='done' THEN 1 ELSE 0 END), 0) AS done,
                          COALESCE(SUM(CASE WHEN status='doing' THEN 1 ELSE 0 END), 0) AS doing,
                          COALESCE(SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END), 0) AS failed
                   FROM sync_state WHERE user_guid=?""",
                (user_guid,)
            ).fetchone()
            return {
                "total": row["total"],
                "done": row["done"],
                "doing": row["doing"],
                "failed": row["failed"],
            }

    # ── 同步日志 ─────────────────────────────────────

    def log_action(self, run_id: str, action: str, item_guid: str = "",
                   series_title: str = "", detail: str = ""):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO sync_log (run_id, action, item_guid, series_title, detail) VALUES (?, ?, ?, ?, ?)",
                (run_id, action, item_guid, series_title, detail)
            )

    def _log_filters(self, action: str, keyword: str) -> tuple[str, list]:
        """组装 sync_log 过滤条件，返回 (WHERE 片段, 参数列表)"""
        where, params = [], []
        if action:
            where.append("action = ?")
            params.append(action)
        if keyword:
            where.append("(series_title LIKE ? OR detail LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        clause = f" WHERE {' AND '.join(where)}" if where else ""
        return clause, params

    def get_logs(self, limit: int = 50, offset: int = 0,
                 action: str = "", keyword: str = "") -> list[dict]:
        clause, params = self._log_filters(action, keyword)
        sql = f"SELECT * FROM sync_log{clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, [*params, limit, offset]).fetchall()
            return [dict(r) for r in rows]

    def count_logs(self, action: str = "", keyword: str = "") -> int:
        clause, params = self._log_filters(action, keyword)
        sql = f"SELECT COUNT(*) AS c FROM sync_log{clause}"
        with closing(self._connect()) as conn:
            return conn.execute(sql, params).fetchone()["c"]

    def get_last_sync_time(self) -> int:
        """读取最近一次同步游标（毫秒时间戳），未同步过返回 0"""
        try:
            return int(self.get_config("last_sync_time", "0") or 0)
        except (TypeError, ValueError):
            return 0

    def record_run_result(self, status: str, message: str, run_at_ms: Optional[int] = None):
        """记录最近一次同步任务的实际执行时间与结果摘要"""
        ts = int(time.time() * 1000) if run_at_ms is None else int(run_at_ms)
        with closing(self._connect()) as conn, conn:
            for key, val in (
                ("last_run_at", str(ts)),
                ("last_run_status", str(status or "")),
                ("last_run_message", str(message or "")),
            ):
                conn.execute(
                    "INSERT INTO runtime_config (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=unixepoch()",
                    (key, val),
                )

    def get_last_run(self) -> dict:
        """读取最近一次同步任务的实际执行时间、状态和摘要"""
        cfg = self.get_all_config()
        try:
            run_at = int(cfg.get("last_run_at") or 0)
        except (TypeError, ValueError):
            run_at = 0
        return {
            "last_run_at": run_at,
            "last_run_status": cfg.get("last_run_status", ""),
            "last_run_message": cfg.get("last_run_message", ""),
        }

    # ── 运行时配置 ───────────────────────────────────

    def get_config(self, key: str, default: str = "") -> str:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value FROM runtime_config WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_config(self, key: str, value: str):
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO runtime_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=unixepoch()",
                (key, value)
            )

    def get_all_config(self) -> dict:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT key, value FROM runtime_config").fetchall()
            return {r["key"]: r["value"] for r in rows}
