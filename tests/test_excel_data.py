# -*- coding: utf-8 -*-
"""Excel 列名映射回归测试。

修复：列匹配用"子串包含"时，"SKU" 误命中 "对应SKU标识" 列，
导致 762.xlsx 类文件（对应SKU标识 + SKU 并存）箱唛丢失、SKU 读错列。
"""

from __future__ import annotations

from models.excel_data import DELIVERY_COLUMN_MAPPING, ExcelLoader, _match_columns, extract_copies_from_item_no


def _headers_762_like() -> list[str]:
    """模拟 762.xlsx 的表头（27 列，含 对应SKU标识 + SKU 并存）。"""
    headers = [""] * 27
    headers[2] = "箱唛"
    headers[3] = "贴标顺序"
    headers[6] = "对应SKU标识"
    headers[9] = "SKU"
    headers[10] = "FBA序列号"
    headers[11] = "FBA番号"
    headers[13] = "FBA仓库编码"
    headers[14] = "箱数"
    headers[16] = "SKU数量"
    headers[26] = "备注"
    return headers


class TestColumnMapping:
    def test_sku_maps_to_exact_column_not_contains(self):
        """SKU 必须匹配精确列，不能命中 对应SKU标识。"""
        col_idx = _match_columns(_headers_762_like(), DELIVERY_COLUMN_MAPPING)
        assert col_idx["SKU"] == 9
        assert col_idx["对应SKU标识"] == 6
        assert col_idx["箱唛"] == 2
        assert col_idx["贴标顺序"] == 3
        assert col_idx["FBA番号"] == 11
        assert col_idx["箱数"] == 14
        assert col_idx["SKU数量"] == 16
        assert col_idx["FBA仓库编码"] == 13
        assert col_idx["FBA序列号"] == 10

    def test_contains_fallback_still_works(self):
        """没有精确列时，子串包含兜底仍应命中（兼容旧文件）。"""
        headers = ["箱唛号", "操作箱数", "更新FNSKU"]
        col_idx = _match_columns(headers, DELIVERY_COLUMN_MAPPING)
        assert col_idx["箱唛"] == 0
        assert col_idx["箱数"] == 1
        assert col_idx["SKU"] == 2

class TestCopiesDefaultOne:
    """份数默认 1 张：指示中没有份数，或备注中未找到 FBA贴N张。"""

    def test_extract_copies_explicit_patterns(self):
        """明确的 FBA每箱贴N张 / 每箱贴N张 仍然生效。"""
        assert extract_copies_from_item_no("FBA每箱贴3张")[0] == 3
        assert extract_copies_from_item_no("每箱贴2张")[0] == 2

    def test_extract_copies_no_digit_fallback(self):
        """不再回退取最后一个数字（单号/日期等不得误当份数）。"""
        copies, desc = extract_copies_from_item_no("寄出透明标签单号：10006392")
        assert copies == 0
        assert "默认" in desc

    @staticmethod
    def _parse_762_like(rows):
        headers = [
            "箱唛", "贴标顺序", "对应SKU标识", "SKU", "FBA序列号",
            "FBA番号", "FBA仓库编码", "箱数", "SKU数量", "备注",
        ]
        col_idx = {
            "箱唛": 0, "贴标顺序": 1, "对应SKU标识": 2, "SKU": 3,
            "FBA序列号": 4, "FBA番号": 5, "FBA仓库编码": 6,
            "箱数": 7, "SKU数量": 8,
        }
        return ExcelLoader._parse_rows(
            rows, col_idx, headers, header_idx=0,
            copies_source="item_no", sku_qty_source="column",
        )

    def test_no_copies_info_defaults_to_one(self):
        """762 类文件：备注列只有透明标签单号 → 所有行份数默认为 1。"""
        rows = [
            ["箱唛", "贴标顺序", "对应SKU标识", "SKU", "FBA序列号",
             "FBA番号", "FBA仓库编码", "箱数", "SKU数量", "备注"],
            ["YL0703376", "YL0703376U001-4", None, "X0017QM06N",
             "FBA15GFB5ZX7U000001-4", "FBA15GFB5ZX7", "XJE1", 4, 200, None],
            [None, "YL0703376U005-8", None, "X0017QVUCN",
             "FBA15GFB5ZX7U000005-8", "FBA15GFB5ZX7", "XJE1", 4, 200,
             "寄出透明标签单号：10006392"],
            ["YL0703380", "YL0703380U001-12", None, "X001DLDKK7",
             "FBA15GDRR8R4U000001-12", "FBA15GDRR8R4", "XJE1", 12, 144,
             "需要贴透明标签\n寄出透明标签单号  ：10006392"],
        ]
        result = self._parse_762_like(rows)
        assert len(result) == 3
        assert all(r["份数"] == 1 for r in result)

    def test_copies_inherit_in_box_but_reset_between_boxes(self):
        """同箱唛合并单元格继承份数；新箱唛无份数信息时重置为 1。"""
        rows = [
            ["箱唛", "贴标顺序", "SKU", "备注"],
            ["A", "A-U1", "X001", "FBA每箱贴2张"],
            [None, "A-U2", "X002", None],
            ["B", "B-U1", "X003", "寄出透明标签单号：10006392"],
            [None, "B-U2", "X004", None],
        ]
        headers = ["箱唛", "贴标顺序", "SKU", "备注"]
        col_idx = {"箱唛": 0, "贴标顺序": 1, "SKU": 2}
        result = ExcelLoader._parse_rows(
            rows, col_idx, headers, header_idx=0,
            copies_source="item_no", sku_qty_source="column",
        )
        assert [r["份数"] for r in result] == [2, 2, 1, 1]
