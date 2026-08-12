"""标签打印工具 — 程序入口

亚马逊 FBA 卖家标签打印工作流工具。
用法: python main.py
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

from loguru import logger

from config import LOG_DIR, LOG_RETENTION, LOG_ROTATION

# ── 日志初始化 ────────────────────────────────────────────────


def _init_logging() -> None:
    """配置 loguru：移除默认 handler，添加文件输出。"""
    logger.remove()
    log_file = LOG_DIR / "app_{time:YYYY-MM-DD}.log"
    logger.add(
        log_file,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        encoding="utf-8",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    )
    logger.info(f"日志系统已初始化，日志目录: {LOG_DIR}")


# ── 依赖自动检查与安装 ──────────────────────────────────────

# {import_name: pip_package_name}
_REQUIRED_DEPS: dict[str, str] = {
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
    "pypdfium2": "pypdfium2",
    "PIL": "Pillow",
    "win32print": "pywin32",
    "fitz": "PyMuPDF",
    "pikepdf": "pikepdf",
    "reportlab": "reportlab",
    "loguru": "loguru",
    "pydantic": "pydantic",
}


def _check_missing_deps() -> list[str]:
    """返回缺失的依赖列表（仅检测 import，不触发安装）。"""
    missing: list[str] = []
    for mod_name, pkg_name in _REQUIRED_DEPS.items():
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(pkg_name)
    return missing


def _install_deps(packages: list[str]) -> bool:
    """尝试通过 pip 安装缺失的依赖。返回 True 表示全部成功。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", *packages],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _ensure_deps() -> bool:
    """确保所有依赖可用。返回 True 表示全部就绪。"""
    if getattr(sys, "frozen", False):
        return True

    missing = _check_missing_deps()
    if not missing:
        return True

    root_tmp = tk.Tk()
    root_tmp.withdraw()
    choice = messagebox.askyesno(
        "依赖缺失",
        "检测到以下依赖未安装：\n\n"
        + "\n".join(f"  • {p}" for p in missing)
        + "\n\n是否自动安装？（需要网络连接）",
    )
    root_tmp.destroy()

    if not choice:
        messagebox.showerror(
            "依赖缺失",
            f"缺少必要依赖，程序无法启动。\n\n请手动运行：pip install {' '.join(missing)}",
        )
        return False

    success = _install_deps(missing)
    if not success:
        messagebox.showerror(
            "安装失败",
            f"自动安装失败，请检查网络连接后手动运行：\n\npip install {' '.join(missing)}",
        )
        return False

    still_missing = _check_missing_deps()
    if still_missing:
        messagebox.showerror(
            "安装不完整",
            "以下依赖仍未安装：\n\n"
            + "\n".join(f"  • {p}" for p in still_missing)
            + "\n\n请手动安装后重试。",
        )
        return False

    messagebox.showinfo("安装完成", "所有依赖已就绪，程序即将启动。")
    return True


# ── 入口 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    _init_logging()

    if not _ensure_deps():
        sys.exit(1)

    # 抑制 PyMuPDF 非关键语法警告（如 "unknown keyword: 'qq'"）
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)

    from ui.app import LabelPrinterApp

    root = tk.Tk()
    app = LabelPrinterApp(root)
    root.mainloop()
