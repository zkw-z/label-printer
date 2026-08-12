"""最近文件管理

持久化最近使用的 Excel/PDF 文件路径记录，提供快捷访问。
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from config import APP_DIR

_RECENT_FILE = APP_DIR / "recent_files.json"
_MAX_RECENT = 10


def load_recent_files() -> list[str]:
    """加载最近文件列表（最新在前）。"""
    try:
        if _RECENT_FILE.exists():
            data = json.loads(_RECENT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(p) for p in data[:_MAX_RECENT] if Path(p).exists()]
    except (json.JSONDecodeError, OSError):
        logger.exception("加载最近文件失败")
    return []


def add_recent_file(path: str) -> None:
    """添加文件到最近列表（去重，最新在前）。"""
    recent = load_recent_files()
    path = str(Path(path).resolve())

    # 去重
    recent = [p for p in recent if p != path]
    recent.insert(0, path)
    recent = recent[:_MAX_RECENT]

    try:
        _RECENT_FILE.write_text(
            json.dumps(recent, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug(f"最近文件已更新: {Path(path).name}")
    except OSError:
        logger.exception("保存最近文件失败")
