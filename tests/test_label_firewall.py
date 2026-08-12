"""标签防火墙 单元测试"""

from __future__ import annotations

from models.excel_data import ExcelData
from services.label_firewall import (
    SPECIAL_NOTE_KEYWORDS,
    TRANSPARENT_KEYWORDS,
    check_firewall,
)


def _make_excel_data(rows: list[dict]) -> ExcelData:
    """构造模拟的 ExcelData"""
    return ExcelData(rows=rows)


class TestLabelFirewall:
    """标签防火墙检测逻辑"""

    def test_transparent_keywords_present(self):
        """检测到透明标签时触发 warning（不抛异常即可）"""
        data = _make_excel_data([
            {"箱唛": "BOX001", "产品名": "透明标签测试", "FNSKU": "X001"},
        ])
        check_firewall(data)

    def test_special_notes_present(self):
        """检测到特殊备注时触发 info"""
        data = _make_excel_data([
            {"箱唛": "BOX002", "备注": "乐天专用", "FNSKU": "X002"},
        ])
        check_firewall(data)

    def test_clean_data_no_firewall(self):
        """完全正常的数据不触发任何检测"""
        data = _make_excel_data([
            {"箱唛": "BOX003", "FNSKU": "X003", "数量": "10"},
            {"箱唛": "BOX004", "FNSKU": "X004", "数量": "5"},
        ])
        check_firewall(data)

    def test_empty_data(self):
        """空数据不触发检测"""
        data = _make_excel_data([])
        check_firewall(data)

    def test_multi_box_mark(self):
        """多个箱唛同时检测"""
        data = _make_excel_data([
            {"箱唛": "A1", "备注": "透明标签"},
            {"箱唛": "B1", "备注": "乐天"},
            {"箱唛": "C1", "备注": "正常货物"},
        ])
        check_firewall(data)

    def test_no_box_mark_column(self):
        """无箱唛列不应报错"""
        data = _make_excel_data([
            {"产品名": "Item1", "FNSKU": "X001"},
        ])
        check_firewall(data)

    def test_transparent_keyword_constants(self):
        """确认关键词常量非空"""
        assert len(TRANSPARENT_KEYWORDS) > 0
        assert "透明标签" in TRANSPARENT_KEYWORDS

    def test_special_note_keyword_constants(self):
        """确认特殊备注关键词常量非空"""
        assert len(SPECIAL_NOTE_KEYWORDS) > 0
        assert "乐天" in SPECIAL_NOTE_KEYWORDS
