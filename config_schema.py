"""配置 Schema 定义

使用 pydantic 进行配置校验和序列化。
AppConfig 是应用唯一的配置模型，config.py 和 workflow 层均通过它读写配置。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from loguru import logger


class AppConfig(BaseModel):
    """应用全局配置 — 唯一配置模型。

    字段与 AppState dataclass 保持 1:1 对应。
    """

    fba_printer: str = ""
    fba_orientation: str = Field(default="portrait", pattern=r"^(portrait|landscape)$")
    fba_scale: float = Field(default=0.98, ge=0.5, le=1.0)
    fba_width: int = Field(default=100, ge=10, le=500)
    fba_height: int = Field(default=100, ge=10, le=500)
    sku_printer: str = ""
    sku_orientation: str = Field(default="portrait", pattern=r"^(portrait|landscape)$")
    sku_width: int = Field(default=50, ge=10, le=500)
    sku_height: int = Field(default=30, ge=10, le=500)

    # ── 指示表自定义列名映射 ─────────────────────────────
    excel_col_mapping: dict[str, str] = Field(default_factory=dict)
    excel_col_match_mode: str = Field(default="contains", pattern=r"^(contains|exact)$")
    excel_col_priority: bool = False

    # ── 持久化 ────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> AppConfig:
        """从 JSON 文件加载配置，缺失或损坏时返回默认值。"""
        path = Path(path)
        try:
            if path.exists():
                data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
                known = cls.model_fields.keys()
                filtered = {k: v for k, v in data.items() if k in known}
                return cls(**filtered)
        except (json.JSONDecodeError, OSError, ValueError):
            logger.exception("加载配置文件失败: {}", path)
        return cls()

    def save(self, path: Path) -> None:
        """将配置写入 JSON 文件。"""
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("保存配置文件失败: {}", path)

    def to_dict(self) -> dict[str, Any]:
        """转为字典（兼容旧 config.py 接口）。"""
        return self.model_dump()
