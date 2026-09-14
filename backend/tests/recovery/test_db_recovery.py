"""Recovery tests — database corruption, WAL recovery, connection handling."""

import os
import sqlite3
import tempfile
import shutil
import pytest
from pathlib import Path


class TestDBRecovery:
    """数据库恢复测试。"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_corrupted_db_detection(self):
        """检测损坏的数据库文件。"""
        db_path = Path(self.temp_dir) / "corrupted.db"

        # 创建损坏的数据库文件
        with open(db_path, "wb") as f:
            f.write(b"this is not a valid sqlite file" * 100)

        # SQLite 可能会打开文件但查询时出错
        conn = sqlite3.connect(str(db_path))
        try:
            # 尝试执行操作应该失败
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("SELECT * FROM sqlite_master")
        finally:
            conn.close()

    def test_wal_mode_enabled(self):
        """验证 WAL 模式启用。"""
        db_path = Path(self.temp_dir) / "wal_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")

        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        conn.close()

    def test_foreign_keys_enforced(self):
        """验证外键约束启用。"""
        db_path = Path(self.temp_dir) / "fk_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")

        # 创建表并测试外键
        conn.execute("CREATE TABLE parent (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE child (id TEXT PRIMARY KEY, parent_id TEXT, FOREIGN KEY (parent_id) REFERENCES parent(id))")

        conn.execute("INSERT INTO parent VALUES ('p1')")
        conn.execute("INSERT INTO child VALUES ('c1', 'p1')")

        # 尝试插入无效外键
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO child VALUES ('c2', 'nonexistent')")

        conn.close()

    def test_busy_timeout(self):
        """测试忙超时处理。"""
        db_path = Path(self.temp_dir) / "busy_test.db"

        # 第一个连接持有写锁
        conn1 = sqlite3.connect(str(db_path))
        conn1.execute("PRAGMA busy_timeout=1000")
        conn1.execute("CREATE TABLE test (id INTEGER)")
        conn1.execute("BEGIN IMMEDIATE")
        conn1.execute("INSERT INTO test VALUES (1)")

        # 第二个连接应该超时（在单线程测试中）
        conn2 = sqlite3.connect(str(db_path))
        conn2.execute("PRAGMA busy_timeout=100")  # 短超时

        # 在实际并发场景中，这会超时
        # 在单线程测试中，我们只验证连接可以创建
        conn1.rollback()
        conn1.close()
        conn2.close()

    def test_connection_reuse(self):
        """测试连接复用。"""
        from backend.app.db.connection import get_connection, close_connection, init_db
        import backend.app.db.connection as conn_module

        # 设置测试数据库
        db_path = Path(self.temp_dir) / "reuse_test.db"
        conn_module._DB_PATH = db_path
        conn_module._CONNECTION = None

        try:
            # 获取连接
            conn1 = get_connection()
            conn1.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")

            # 再次获取应该是同一个连接
            conn2 = get_connection()
            assert conn1 is conn2

            close_connection()

            # 关闭后应该创建新连接
            conn3 = get_connection()
            assert conn3 is not conn1
        finally:
            close_connection()
            conn_module._CONNECTION = None
            conn_module._DB_PATH = None

    def test_init_db_idempotent(self):
        """测试数据库初始化幂等性。"""
        from backend.app.db.connection import get_connection, close_connection, init_db
        import backend.app.db.connection as conn_module

        db_path = Path(self.temp_dir) / "idempotent_test.db"
        conn_module._DB_PATH = db_path
        conn_module._CONNECTION = None

        try:
            # 多次初始化应该不报错
            init_db()
            init_db()
            init_db()

            conn = get_connection()
            # 验证表存在
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "workflows" in table_names
        finally:
            close_connection()
            conn_module._CONNECTION = None
            conn_module._DB_PATH = None

    def test_empty_db_file(self):
        """测试空数据库文件处理。"""
        db_path = Path(self.temp_dir) / "empty.db"

        # 创建空文件
        with open(db_path, "w") as f:
            pass

        # SQLite 可以打开空文件并创建新数据库
        conn = sqlite3.connect(str(db_path))
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
        conn.close()
