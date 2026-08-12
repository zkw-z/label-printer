"""标签相关常量定义

统一管理透明标签检测关键词、特殊备注关键词等，避免在多个模块中重复定义。
"""

from __future__ import annotations

# 透明标签检测关键词（红色警告级别）
TRANSPARENT_KEYWORDS: tuple[str, ...] = (
    "透明标签",
    "透明签",
    "透明",
)

# 特殊备注关键词（蓝色提示级别）
SPECIAL_NOTE_KEYWORDS: tuple[str, ...] = (
    "乐天",
    "海外仓",
    "需贴大小标",
    "需要贴大小标",
    "需贴大标",
    "需要贴大标",
    "需贴小标",
    "需要贴小标",
)