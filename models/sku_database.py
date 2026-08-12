"""SKU 标签数据库

使用 SQLite 持久化存储 SKU 对应的 PDF 页面图像（PNG 格式），
便于后续直接从数据库加载打印，无需重复上传 PDF。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from loguru import logger
from pathlib import Path
from typing import Any

from config import DB_PATH



class SKUDatabase:
    """管理 SKU 标签的 SQLite 存储。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._init_table()

    def _init_table(self) -> None:
        """创建数据库表与索引（如不存在）。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sku_labels (
                    sku          TEXT PRIMARY KEY,
                    pdf_data     BLOB,
                    page_number  INTEGER,
                    created_at   TIMESTAMP,
                    source_file  TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sku_labels_created_at ON sku_labels (created_at)"
            )

    # ─── CRUD ─────────────────────────────────────────────────

    def save(
        self, sku: str, pdf_data: bytes, page_number: int, source_file: str
    ) -> tuple[bool, str]:
        """保存或更新 SKU 页面数据。"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO sku_labels
                       (sku, pdf_data, page_number, created_at, source_file)
                       VALUES (?, ?, ?, ?, ?)""",
                    (sku, pdf_data, page_number, datetime.now().isoformat(sep=' ', timespec='seconds'), source_file),
                )
            return True, f"SKU '{sku}' 已保存到数据库"
        except Exception as e:
            return False, f"保存 SKU '{sku}' 失败: {e}"

    def save_batch(
        self, items: list[tuple[str, bytes, int, str]]
    ) -> tuple[bool, str]:
        """在单一事务中批量保存或更新 SKU 页面数据。

        Args:
            items: 元素为 (sku, pdf_data, page_number, source_file) 的元组列表。
        """
        if not items:
            return True, "没有需要保存的 SKU 数据"
        try:
            created_at = datetime.now().isoformat(sep=' ', timespec='seconds')
            rows = [(sku, pdf_data, page_number, created_at, source_file) for sku, pdf_data, page_number, source_file in items]
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("BEGIN TRANSACTION;")
                conn.executemany(
                    """INSERT OR REPLACE INTO sku_labels
                       (sku, pdf_data, page_number, created_at, source_file)
                       VALUES (?, ?, ?, ?, ?)""",
                    rows,
                )
                conn.commit()
            return True, f"已成功批量保存 {len(items)} 个 SKU 到数据库"
        except Exception as e:
            return False, f"批量保存 SKU 失败: {e}"


    def get(self, sku: str) -> tuple[bytes | None, int | None]:
        """获取 SKU 的 PNG 数据和页码。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT pdf_data, page_number FROM sku_labels WHERE sku = ?",
                (sku,),
            ).fetchone()
        if row:
            return row[0], row[1]
        return None, None

    def exists(self, sku: str) -> bool:
        """检查 SKU 是否已存在于数据库。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            (count,) = conn.execute(
                "SELECT COUNT(*) FROM sku_labels WHERE sku = ?", (sku,)
            ).fetchone()
        return count > 0

    def exists_compound(self, compound_key: str, plain_sku: str = "") -> bool:
        """检查是否存在（先查复合键，回退纯 SKU）。

        用于兼容既有旧数据（纯 SKU）又有新数据（复合键）的场景。
        """
        if self.exists(compound_key):
            return True
        if plain_sku:
            return self.exists(plain_sku)
        return False

    def get_compound(
        self, compound_key: str, plain_sku: str = ""
    ) -> tuple[bytes | None, int | None]:
        """获取 SKU 的 PNG 数据和页码，支持复合键回退。

        Args:
            compound_key: 复合键（如 "SKU|||IDENTIFIER"）。
            plain_sku: 纯 SKU 作为回退查找键。

        Returns:
            (png_data, page_number) 或 (None, None)。
        """
        png_data, page_num = self.get(compound_key)
        if png_data is not None:
            return png_data, page_num

        if plain_sku:
            return self.get(plain_sku)

        return None, None

    def list_all(self) -> list[tuple[str, str, str]]:
        """列出所有 SKU（名称、创建时间、来源文件）。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            return conn.execute(
                "SELECT sku, created_at, source_file FROM sku_labels ORDER BY created_at DESC"
            ).fetchall()

    def delete(self, sku: str) -> bool:
        """删除指定 SKU。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM sku_labels WHERE sku = ?", (sku,))
            return conn.total_changes > 0

    def clear_all(self) -> tuple[bool, str]:
        """清空数据库。"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM sku_labels")
                return True, f"已清空数据库，删除了 {conn.total_changes} 条记录"
        except Exception as e:
            return False, f"清空数据库失败: {e}"

    def stats(self) -> dict[str, Any]:
        """获取数据库统计信息。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(LENGTH(pdf_data)), 0) FROM sku_labels"
            ).fetchone()
        count = row[0] or 0
        total_bytes = row[1] or 0
        return {
            "total_skus": count,
            "total_size_bytes": total_bytes,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        }

    def cleanup(self, days: int = 30) -> tuple[bool, int]:
        """删除指定天数之前的旧数据，并 VACUUM 压缩。"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "DELETE FROM sku_labels WHERE created_at < ?",
                    (cutoff.isoformat(sep=" ", timespec="seconds"),),
                )
                conn.commit()
            # VACUUM 用 isolation_level=None 确保无事务模式
            conn2 = sqlite3.connect(str(self.db_path), isolation_level=None)
            try:
                conn2.execute("VACUUM")
            except Exception:
                pass  # VACUUM 是优化，失败不影响主功能
            finally:
                conn2.close()
            return True, 0
        except Exception as e:
            logger.exception("数据库清理失败: {}", e)
            return False, 0
