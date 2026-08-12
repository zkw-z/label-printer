"""下部日志面板

带颜色标记的滚动日志视图——错误(红)、警告(橙)、成功(绿)、信息(青)。
支持 loguru 日志路由（通过自定义 sink）和直接调用两种方式。
科技感深色主题。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext

from loguru import logger

from ui.progress_bar import ProgressBar
from ui.widgets import Theme

# ─── loguru → GUI sink ──────────────────────────────────────


class _LoguruTextSink:
    """将 loguru 日志消息路由到 LowerSection 的 ScrolledText 控件。"""

    def __init__(self, widget: LowerSection) -> None:
        self._widget = widget

    def write(self, message: str) -> None:
        if message.strip():
            self._widget.log(message.rstrip("\n"))

    def flush(self) -> None:
        pass


class LowerSection(tk.Frame):
    """操作日志面板。同时作为 loguru sink 接收结构化日志。"""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, bg=Theme.BG_MAIN)
        self.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # 子组件占位（app.py 注入）
        self.progress: ProgressBar | None = None

        outer = tk.Frame(self, bg=Theme.SHADOW, highlightthickness=0)
        outer.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(
            outer,
            bg=Theme.BG_CARD,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
        )
        card.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)

        top_border = tk.Frame(card, bg=Theme.ACCENT, height=2)
        top_border.pack(fill=tk.X, side=tk.TOP)

        # 标题栏
        title_frame = tk.Frame(card, bg=Theme.BG_CARD, height=32)
        title_frame.pack(fill=tk.X, padx=15, pady=(8, 4))
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="📡  操作日志",
            bg=Theme.BG_CARD,
            fg=Theme.TEXT_PRIMARY,
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            title_frame,
            text="● LIVE",
            bg=Theme.BG_CARD,
            fg=Theme.SUCCESS,
            font=("Consolas", 8, "bold"),
        ).pack(side=tk.RIGHT)

        divider = tk.Frame(card, bg=Theme.BORDER, height=1)
        divider.pack(fill=tk.X, padx=12, pady=(0, 4))

        # 日志区域
        log_frame = tk.Frame(card, bg=Theme.BG_CARD)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.text = scrolledtext.ScrolledText(
            log_frame,
            state="disabled",
            bg=Theme.BG_INPUT,
            fg=Theme.TEXT_PRIMARY,
            insertbackground=Theme.ACCENT,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            font=("Consolas", 9),
        )
        self.text.pack(fill=tk.BOTH, expand=True)

        # 颜色标签
        self.text.tag_config("error", foreground=Theme.DANGER, font=("Consolas", 9, "bold"))
        self.text.tag_config("warning", foreground=Theme.WARNING, font=("Consolas", 9, "bold"))
        self.text.tag_config("success", foreground=Theme.SUCCESS, font=("Consolas", 9, "bold"))
        self.text.tag_config("info", foreground=Theme.ACCENT)

        # 注册为 loguru sink
        self._sink = _LoguruTextSink(self)
        logger.add(
            self._sink,
            format="{message}",
            level="INFO",
            colorize=False,
        )

    def log(self, message: str) -> None:
        """追加日志消息，根据关键词自动着色。"""
        self.text.config(state="normal")

        msg_lower = message.lower()
        tag = None

        if any(k in msg_lower for k in ["错误", "error", "失败", "failed", "异常", "exception", "透明标签"]):
            tag = "error"
        elif any(k in msg_lower for k in ["警告", "warning", "注意", "caution", "缺失", "未匹配"]):
            tag = "warning"
        elif any(k in msg_lower for k in ["成功", "success", "完成", "completed", "✓", "✅"]):
            tag = "success"
        elif any(k in msg_lower for k in ["试用", "trial", "⏰", "乐天", "海外仓", "需贴", "特殊备注"]):
            tag = "info"

        if tag:
            self.text.insert(tk.END, message + "\n", tag)
        else:
            self.text.insert(tk.END, message + "\n")

        self.text.see(tk.END)
        self.text.config(state="disabled")
