# -*- coding: utf-8 -*-
"""标签防火墙模块

检测上传的 Excel 数据中特殊字段内容，分两级提示：
- 透明标签 → warning 红色 + 弹窗
- 特殊备注（乐天/海外仓/需贴大小标等）→ info 蓝色日志
"""

from __future__ import annotations

from loguru import logger
from models.excel_data import ExcelData

from constants.label_constants import TRANSPARENT_KEYWORDS, SPECIAL_NOTE_KEYWORDS


def check_firewall(data: ExcelData) -> None:
    transparent_marks: dict[str, set[str]] = {}
    special_marks: dict[str, set[str]] = {}
    for row in data.rows:
        mark = str(row.get("箱唛", "")).strip()
        if not mark:
            continue
        for val in row.values():
            if val is None:
                continue
            s = str(val)
            for kw in TRANSPARENT_KEYWORDS:
                if kw in s:
                    transparent_marks.setdefault(mark, set()).add(kw)
            for kw in SPECIAL_NOTE_KEYWORDS:
                if kw in s:
                    special_marks.setdefault(mark, set()).add(kw)
    if transparent_marks:
        _report_transparent(transparent_marks)
    if special_marks:
        _report_special_notes(special_marks)


def _report_transparent(transparent_marks: dict[str, set[str]]) -> None:
    lines: list[str] = []
    for mark, kws in sorted(transparent_marks.items()):
        lines.append(f"  • 箱唛 [{mark}]  →  匹配: {', '.join(sorted(kws))}")
    mark_list = "\n".join(lines)
    msg = (
        "⚠️ 透明标签防火墙提醒\n\n"
        + "上传的指示文件中检测到「透明标签」相关内容，涉及以下箱唛：\n\n"
        + mark_list + "\n\n"
        + "请核对这些箱唛的标签是否完整，透明标签可能需要额外处理。"
    )
    logger.warning(
        "透明标签防火墙: 检测到 {} 个箱唛含透明标签内容\n{}",
        len(transparent_marks), mark_list
    )
    import tkinter.messagebox as tkmb
    tkmb.showwarning("⚠️ 透明标签防火墙", msg)


def _report_special_notes(special_marks: dict[str, set[str]]) -> None:
    lines: list[str] = []
    for mark, kws in sorted(special_marks.items()):
        lines.append(f"  • 箱唛 [{mark}]  →  匹配: {', '.join(sorted(kws))}")
    mark_list = "\n".join(lines)
    logger.info(
        "ℹ️ 标签防火墙 (特殊备注): 检测到 {} 个箱唛含特殊字段\n{}",
        len(special_marks), mark_list
    )

