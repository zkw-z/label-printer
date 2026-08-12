"""SKU 数据库 单元测试"""

from __future__ import annotations

import os
import tempfile

import pytest
from PIL import Image

from models.sku_database import SKUDatabase


@pytest.fixture
def db() -> SKUDatabase:
    """每个测试使用独立的临时数据库"""
    tmp = tempfile.mktemp(suffix=".db")
    database = SKUDatabase(tmp)
    yield database
    database.clear_all()
    del database
    try:
        os.unlink(tmp)
    except (PermissionError, FileNotFoundError):
        pass


def _make_png_bytes(size: tuple[int, int] = (100, 100)) -> bytes:
    """生成测试用 PNG 字节数据"""
    img = Image.new("RGB", size, "white")
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestSKUDatabase:
    """SKU 数据库 CRUD 操作"""

    def test_save_and_get(self, db: SKUDatabase):
        png = _make_png_bytes()
        ok, msg = db.save("TEST-SKU-001", png, 1, "test.pdf")
        assert ok
        assert "TEST-SKU-001" in msg

        data, page = db.get("TEST-SKU-001")
        assert data == png
        assert page == 1

    def test_exists(self, db: SKUDatabase):
        assert not db.exists("NONEXISTENT")
        png = _make_png_bytes()
        db.save("EXISTENT-SKU", png, 1, "test.pdf")
        assert db.exists("EXISTENT-SKU")

    def test_delete(self, db: SKUDatabase):
        png = _make_png_bytes()
        db.save("TO-DELETE", png, 1, "test.pdf")
        assert db.exists("TO-DELETE")
        db.delete("TO-DELETE")
        assert not db.exists("TO-DELETE")

    def test_list_all(self, db: SKUDatabase):
        assert db.list_all() == []
        png = _make_png_bytes()
        db.save("SKU-A", png, 1, "a.pdf")
        db.save("SKU-B", png, 2, "b.pdf")
        items = db.list_all()
        assert len(items) == 2

    def test_get_nonexistent(self, db: SKUDatabase):
        data, page = db.get("GHOST-SKU")
        assert data is None
        assert page is None

    def test_compound_key(self, db: SKUDatabase):
        png = _make_png_bytes()
        db.save("SKU|||IDENTIFIER1", png, 1, "test.pdf")
        db.save("SKU|||IDENTIFIER2", png, 2, "test.pdf")

        data1, page1 = db.get("SKU|||IDENTIFIER1")
        assert page1 == 1

        data2, page2 = db.get("SKU|||IDENTIFIER2")
        assert page2 == 2

    def test_compound_fallback(self, db: SKUDatabase):
        """测试 exists_compound 和 get_compound 的回退逻辑"""
        png = _make_png_bytes()
        db.save("PURE-SKU", png, 1, "test.pdf")

        # 纯 SKU 应匹配
        assert db.exists_compound("PURE-SKU")
        data, page = db.get_compound("PURE-SKU")
        assert page == 1

        # 不存在的 key 不应匹配
        assert not db.exists_compound("NOT-PURE-SKU")
        data, page = db.get_compound("NOT-PURE-SKU")
        assert data is None

    def test_stats(self, db: SKUDatabase):
        stats = db.stats()
        assert stats["total_skus"] == 0
        assert stats["total_size_bytes"] == 0

        png = _make_png_bytes()
        db.save("STATS-SKU", png, 1, "test.pdf")
        stats = db.stats()
        assert stats["total_skus"] == 1
        assert stats["total_size_bytes"] > 0
