# -*- coding: utf-8 -*-
"""Excel 列名映射回归测试。

修复：列匹配用"子串包含"时，"SKU" 误命中 "对应SKU标识" 列，
导致 762.xlsx 类文件（对应SKU标识 + SKU 并存）箱唛丢失、SKU 读错列。
"""

from __future__ import annotations

from models.excel_data import DELIVERY_COLUMN_MAPPING, _match_columns


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
