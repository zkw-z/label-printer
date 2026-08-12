"""打印工具配置模块

管理默认打印参数、打印机设置的持久化存储、以及应用的路径解析。
支持 pyinstaller 打包后的运行目录。

配置存储统一使用 config_schema.AppConfig (pydantic 模型)。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from config_schema import AppConfig
from loguru import logger

# ─── 应用目录解析 ────────────────────────────────────────────


def get_app_dir() -> Path:
    """返回应用根目录（兼容 frozen 和脚本运行）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


APP_DIR: Path = get_app_dir()


# ─── 日志 ───────────────────────────────────────────────────

LOG_DIR: Path = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_RETENTION: str = "7 days"  # 日志保留天数
LOG_ROTATION: str = "10 MB"  # 日志轮转大小


# ─── 默认打印参数 ────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = AppConfig().to_dict()

# 数据库文件路径
DB_PATH: Path = APP_DIR / "sku_labels.db"

# 配置文件路径
CONFIG_FILE: Path = APP_DIR / "printer_config.json"

# 字体候选（按优先级）
FONT_CANDIDATES: list[str] = ["msyh.ttc", "msyh.ttf", "simhei.ttf", "arial.ttf"]


# ─── 配置读写（保持旧接口签名，底层使用 pydantic）────────────


def load_printer_config() -> dict[str, Any]:
    """从 printer_config.json 加载打印机配置，返回 dict（兼容旧调用方）。"""
    cfg = AppConfig.load(CONFIG_FILE)
    return cfg.to_dict()


def save_printer_config(config: dict[str, Any]) -> None:
    """将打印机配置写入 printer_config.json。

    只保留已知字段，过滤掉无效键以防止注入。
    """
    try:
        known = AppConfig.model_fields.keys()
        filtered = {k: v for k, v in config.items() if k in known}
        cfg = AppConfig(**filtered)
        cfg.save(CONFIG_FILE)
    except (ValueError, OSError):
        logger.exception('保存打印机配置失败')
