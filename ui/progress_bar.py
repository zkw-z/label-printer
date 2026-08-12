"""操作进度条组件

在日志面板底部显示操作进度，支持确定和不确定两种模式。
长耗时操作（打印、PDF 处理）时自动显示，完成后自动隐藏。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.widgets import Theme


class ProgressBar(tk.Frame):
    """操作进度条，内嵌于 LowerSection 底部。"""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, bg=Theme.BG_CARD, height=28)
        self.pack_propagate(False)

        self._label = tk.Label(
            self,
            text="",
            bg=Theme.BG_CARD,
            fg=Theme.TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 8),
            anchor="w",
        )
        self._label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 5))

        self._bar = ttk.Progressbar(
            self,
            mode="indeterminate",
            length=150,
        )
        self._bar.pack(side=tk.RIGHT, padx=(0, 10))

        self._is_visible = False

    def show(self, text: str = "处理中...", determinate: bool = False, maximum: int = 100) -> None:
        """显示进度条。

        Args:
            text: 进度文本。
            determinate: True 为确定进度，False 为不确定进度。
            maximum: 确定模式下的最大值。
        """
        if not self._is_visible:
            self.pack(fill=tk.X, padx=0, pady=(0, 0), before=self.master.winfo_children()[-1])
            self._is_visible = True

        self._label.config(text=text)

        if determinate:
            self._bar.config(mode="determinate", maximum=maximum, value=0)
        else:
            self._bar.config(mode="indeterminate")
            self._bar.start(10)

    def update(self, value: int, text: str | None = None) -> None:
        """更新确定模式进度。

        Args:
            value: 当前进度值。
            text: 可选，更新文本。
        """
        self._bar.config(value=value)
        if text is not None:
            self._label.config(text=text)

    def hide(self) -> None:
        """隐藏进度条。"""
        if self._is_visible:
            self._bar.stop()
            self.pack_forget()
            self._is_visible = False
            self._label.config(text="")

    @property
    def visible(self) -> bool:
        return self._is_visible
