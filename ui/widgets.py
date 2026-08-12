"""UI 基础组件

Quiet Light 柔和浅色主题色彩系统和静态圆角按钮控件。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable


class Theme:
    """Quiet Light 柔和浅色主题。"""

    BG_MAIN = "#f8fafc"
    BG_CARD = "#ffffff"
    BG_CARD_HOVER = "#f1f5f9"
    BG_INPUT = "#f1f5f9"

    ACCENT = "#3b82f6"
    ACCENT_DARK = "#2563eb"
    ACCENT_LIGHT = "#60a5fa"

    PRIMARY = "#3b82f6"
    PRIMARY_DARK = "#2563eb"
    PRIMARY_LIGHT = "#60a5fa"

    SUCCESS = "#10b981"
    SUCCESS_DARK = "#059669"
    WARNING = "#f59e0b"
    DANGER = "#ef4444"
    DANGER_DARK = "#dc2626"
    SECONDARY = "#64748b"
    SECONDARY_DARK = "#475569"

    TEXT_PRIMARY = "#1e293b"
    TEXT_SECONDARY = "#64748b"
    TEXT_TERTIARY = "#94a3b8"
    TEXT_LIGHT = "#ffffff"
    TEXT_ACCENT = "#2563eb"

    BORDER = "#e2e8f0"
    BORDER_LIGHT = "#f1f5f9"
    BORDER_ACCENT = "#93c5fd"
    SHADOW = "#e2e8f0"


class ModernButton(tk.Canvas):
    """静态科技感圆角按钮。

    无动态效果，只绘制一次。
    """

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        bg_color: str | None = None,
        width: int = 0,
        height: int = 36,
    ) -> None:
        self.base_color = bg_color or Theme.PRIMARY
        self._text = text
        self._command = command

        canvas_bg = parent.cget("bg") if hasattr(parent, "cget") else Theme.BG_CARD

        if width == 0:
            super().__init__(
                parent,
                height=height,
                bg=canvas_bg,
                highlightthickness=0,
            )
        else:
            super().__init__(
                parent,
                width=width,
                height=height,
                bg=canvas_bg,
                highlightthickness=0,
            )

        # 只绑定点击事件
        self.bind("<Button-1>", lambda e: self._on_click())
        self.config(cursor="hand2")

        # 绑定 Configure 事件，只绘制一次
        self.bind("<Configure>", self._on_configure, add="+")
        self._drawn = False

    def _on_configure(self, event: tk.Event) -> None:
        if not self._drawn:
            w = self.winfo_width()
            h = self.winfo_height()
            if w > 1 and h > 1:
                self._drawn = True
                self._draw_static(w, h)

    def _draw_static(self, w: int, h: int) -> None:
        """绘制静态按钮。"""
        radius = 8

        # 绘制圆角矩形背景
        points = self._rounded_points(0, 0, w, h, radius)
        self.create_polygon(
            points,
            fill=self.base_color,
            outline=self.base_color,
            smooth=True,
        )

        # 绘制文字
        self.create_text(
            w // 2,
            h // 2,
            text=self._text,
            fill=Theme.TEXT_LIGHT,
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def _rounded_points(self, x: int, y: int, w: int, h: int, r: int) -> list[int]:
        """生成圆角矩形的坐标点。"""
        return [
            x + r, y,
            x + w - r, y,
            x + w, y,
            x + w, y + r,
            x + w, y + h - r,
            x + w, y + h,
            x + w - r, y + h,
            x + r, y + h,
            x, y + h,
            x, y + h - r,
            x, y + r,
            x, y,
        ]

    def _on_click(self) -> None:
        if self._command:
            self._command()


def create_card(parent: tk.Widget, title: str, icon: str) -> tuple[tk.Frame, tk.Frame]:
    """创建科技感深色卡片。

    Returns:
        (shadow_frame, card_frame)
    """
    outer = tk.Frame(parent, bg=Theme.SHADOW, highlightthickness=0)

    card = tk.Frame(
        outer,
        bg=Theme.BG_CARD,
        highlightthickness=1,
        highlightbackground=Theme.BORDER,
    )
    card.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)

    # 顶部装饰条
    top_border = tk.Frame(card, bg=Theme.ACCENT, height=2)
    top_border.pack(fill=tk.X, side=tk.TOP)

    # 标题栏
    title_frame = tk.Frame(card, bg=Theme.BG_CARD, height=40)
    title_frame.pack(fill=tk.X, padx=15, pady=(10, 6))
    title_frame.pack_propagate(False)

    tk.Label(
        title_frame,
        text=f"{icon}  {title}",
        bg=Theme.BG_CARD,
        fg=Theme.TEXT_PRIMARY,
        font=("Microsoft YaHei UI", 11, "bold"),
        anchor="w",
    ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # 状态指示点
    tk.Label(
        title_frame,
        text="●",
        bg=Theme.BG_CARD,
        fg=Theme.ACCENT,
        font=("Arial", 8),
    ).pack(side=tk.RIGHT)

    # 分隔线
    tk.Frame(card, bg=Theme.BORDER, height=1).pack(fill=tk.X, padx=12, pady=(0, 8))

    return outer, card