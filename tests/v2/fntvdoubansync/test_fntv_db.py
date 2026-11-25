import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.plugins.fntvdoubansync.fntv_db import FntvDb, ItemCategory


class ItemClassificationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """CREATE TABLE item (
                guid TEXT PRIMARY KEY,
                parent_guid TEXT,
                season_number INTEGER,
                episode_number INTEGER,
                title TEXT
            )"""
        )

    def tearDown(self):
        self.conn.close()

    def test_zero_season_episode_and_empty_parent_is_movie(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("movie-1", "", 0, 0, "电影1"),
        )

        self.assertEqual(
            FntvDb.classify_item(self.conn, "movie-1"),
            ItemCategory.MOVIE,
        )

    def test_positive_episode_number_is_episode(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("episode-1", "season-1", 1, 1, "第1集"),
        )

        self.assertEqual(
            FntvDb.classify_item(self.conn, "episode-1"),
            ItemCategory.EPISODE,
        )

    def test_series_hierarchy_extracts_season_from_episode_when_season_null(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("series-1", None, None, None, "曼达洛人"),
        )
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("season-1", "series-1", None, None, "Season 2"),
        )
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("episode-1", "season-1", 2, 1, "第1集"),
        )

        fntv = FntvDb.__new__(FntvDb)
        info = fntv.get_series_hierarchy(self.conn, "episode-1")
        self.assertIsNotNone(info)
        self.assertEqual(info["season_number"], 2)
        self.assertEqual(info["series_title"], "曼达洛人")

    def test_flat_structure_preserves_season_number(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("series-2", None, None, None, "怪奇物语 第二季"),
        )
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("episode-2", "series-2", 2, 1, "第1集"),
        )

        fntv = FntvDb.__new__(FntvDb)
        flat = fntv.get_series_for_episode_flat(self.conn, "episode-2")
        self.assertIsNotNone(flat)
        self.assertEqual(flat["season_number"], 2)

    def test_season_skips_empty_season_nodes(self):
        rows = [
            ("aot", None, None, None, "进击的巨人"),
            ("s4-old", "aot", 4, None, "第 4 季"),  # 重新刮削遗留，下面没有单集
            ("s4", "aot", 4, None, "最终季"),
            ("ep-1", "s4", 4, 1, "第1集"),
        ]
        self.conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?)", rows)

        fntv = FntvDb.__new__(FntvDb)
        self.assertEqual(fntv.get_season(self.conn, "aot", 4), {"guid": "s4", "title": "最终季"})
        self.assertIsNone(fntv.get_season(self.conn, "aot", 5))

    def test_library_titles_list_movies_and_series_with_seasons(self):
        self.conn.execute("ALTER TABLE item ADD COLUMN original_title TEXT")
        self.conn.execute("ALTER TABLE item ADD COLUMN imdb_id TEXT")
        rows = [
            ("movie", None, None, None, "赴汤蹈火", "Hell or High Water", "tt2582782"),
            ("tv", "", None, None, "信号", "시그널", None),
            ("tv-s1", "tv", 1, 16, "第 1 季", None, None),
            ("tv-s1-e1", "tv-s1", 1, 1, "", None, None),
            ("tv-s2", "tv", 2, 16, "第 2 季", None, None),  # 没有单集，不算在库
        ]
        self.conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?, ?, ?)", rows)

        fntv = FntvDb.__new__(FntvDb)
        library = {e["title"]: e for e in fntv.get_library_titles(self.conn)}
        self.assertEqual(set(library), {"赴汤蹈火", "信号"})
        self.assertEqual(library["赴汤蹈火"]["imdb_id"], "tt2582782")
        self.assertEqual(library["信号"]["seasons"], {1})
        self.assertEqual(library["信号"]["imdb_id"], "")

    def test_season_total_uses_planned_episodes_for_ongoing_season(self):
        # 季节点的 episode_number 是刮削到的计划集数
        rows = [
            ("jojo-6", "jojo", 6, 12, "飙马野郎篇"),
            ("ep-1", "jojo-6", 6, 1, "第1集"),
            ("ep-2", "jojo-6", 6, 2, "第2集"),
            ("mds-1", "mds", 1, 27, "第 1 季"),
        ] + [(f"mds-ep-{i}", "mds-1", 1, i, "") for i in range(1, 30)]
        self.conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?)", rows)

        fntv = FntvDb.__new__(FntvDb)
        self.assertEqual(fntv.get_season_total_episodes(self.conn, "jojo-6"), 12)
        # 本地集数多于计划集数时以本地为准
        self.assertEqual(fntv.get_season_total_episodes(self.conn, "mds-1"), 29)


class FntvDbPathTests(unittest.TestCase):
    """validate 误判提示与临时副本路径隔离"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_db(self) -> Path:
        db = self.tmp / "trimmedia.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE item (guid TEXT PRIMARY KEY, parent_guid TEXT)")
        conn.commit()
        conn.close()
        return db

    def test_validate_ok(self):
        db = self._make_db()
        ok, msg = FntvDb(str(db)).validate()
        self.assertTrue(ok, msg)

    def test_validate_missing_file(self):
        ok, msg = FntvDb(str(self.tmp / "missing.db")).validate()
        self.assertFalse(ok)
        self.assertIn("文件不存在", msg)

    def test_validate_directory_hints_docker_mistake(self):
        # Docker volume 挂载时源文件不存在会自动创建同名目录，需给出明确提示
        ok, msg = FntvDb(str(self.tmp)).validate()
        self.assertFalse(ok)
        self.assertIn("目录", msg)

    def test_tmp_copy_lands_in_cache_dir(self):
        db = self._make_db()
        cache = self.tmp / "plugin-data"
        fntv = FntvDb(str(db), cache_dir=cache)
        with fntv.get_conn() as conn:
            conn.execute("SELECT COUNT(*) FROM item").fetchone()
        self.assertTrue((cache / "trimmedia_tmp.db").exists())

    def test_cache_dir_defaults_to_system_tmp(self):
        db = self._make_db()
        fntv = FntvDb(str(db))
        self.assertEqual(fntv._tmp_path.parent, Path(tempfile.gettempdir()))
        with fntv.get_conn() as conn:
            conn.execute("SELECT COUNT(*) FROM item").fetchone()
        self.assertTrue(Path(tempfile.gettempdir(), "trimmedia_tmp.db").exists())

    def test_wal_sidecars_copied_and_cleaned(self):
        db = self._make_db()
        cache = self.tmp / "wal-cache"
        wal = Path(f"{db}-wal")
        shm = Path(f"{db}-shm")
        wal.write_bytes(b"wal-bytes")
        shm.write_bytes(b"shm-bytes")

        fntv = FntvDb(str(db), cache_dir=cache)
        fntv._copy_db()
        self.assertTrue((cache / "trimmedia_tmp.db-wal").exists())
        self.assertTrue((cache / "trimmedia_tmp.db-shm").exists())

        # 删除源附属文件并强制过期缓存，临时目录内的旧附属文件应被清理
        wal.unlink()
        shm.unlink()
        fntv._last_copy = 0.0
        fntv._copy_db()
        self.assertFalse((cache / "trimmedia_tmp.db-wal").exists())
        self.assertFalse((cache / "trimmedia_tmp.db-shm").exists())


if __name__ == "__main__":
    unittest.main()
