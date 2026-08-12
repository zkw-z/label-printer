"""上部功能区 — 三栏布局

左栏：文件上传（Excel / FBA PDF / SKU PDF / 清空数据库）
中栏：批量打印（箱唛输入 + FBA打印 + SKU打印）
右栏：单个 SKU 打印（SKU输入 + 数量 + 打印按钮）
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

from ui.widgets import ModernButton, Theme, create_card


def _make_entry_row(parent: tk.Widget, label_text: str, width: int = 0) -> tk.Entry:
    """创建一个紧凑的标签+输入框行，返回 Entry 控件。"""
    row = tk.Frame(parent, bg=Theme.BG_CARD)
    row.pack(fill=tk.X, padx=12, pady=1)

    tk.Label(row, text=label_text, bg=Theme.BG_CARD, fg=Theme.TEXT_SECONDARY,
             font=("Microsoft YaHei UI", 7), width=4, anchor="e").pack(side=tk.LEFT, padx=(0, 4))

    kwargs: dict = dict(
        bg=Theme.BG_INPUT, fg=Theme.TEXT_PRIMARY,
        insertbackground=Theme.ACCENT, relief=tk.FLAT,
        font=("Microsoft YaHei UI", 9),
        highlightthickness=1, highlightbackground=Theme.BORDER,
        highlightcolor=Theme.ACCENT, borderwidth=0,
    )
    if width > 0:
        kwargs["width"] = width

    entry = tk.Entry(row, **kwargs)
    entry.pack(side=tk.LEFT, fill=tk.X if width == 0 else tk.NONE, expand=(width == 0))
    return entry


class UpperSection(tk.Frame):
    """上部三栏功能区。"""

    def __init__(self, parent: tk.Widget, callbacks: dict[str, Callable[..., Any]]) -> None:
        super().__init__(parent, bg=Theme.BG_MAIN)
        self.cb = callbacks
        self.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self.columnconfigure(0, weight=1, uniform="col")
        self.columnconfigure(1, weight=1, uniform="col")
        self.columnconfigure(2, weight=1, uniform="col")
        self.rowconfigure(0, weight=1)

        self._build_left()
        self._build_center()
        self._build_right()

    # ── 左栏：文件上传 ────────────────────────────────────────

    def _build_left(self) -> None:
        shadow, card = create_card(self, "文件上传", "📁")
        shadow.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        container = tk.Frame(card, bg=Theme.BG_CARD)
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        ModernButton(container, "📄 指示文件 (Excel)", self.cb["upload_excel"], height=32).pack(
            fill=tk.X, pady=3
        )
        ModernButton(container, "📦 FBA PDF", self.cb["upload_fba"], height=32).pack(
            fill=tk.X, pady=3
        )
        ModernButton(container, "🏷️ SKU PDF", self.cb["upload_sku"], height=32).pack(
            fill=tk.X, pady=3
        )

        tk.Frame(container, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=6)

        ModernButton(
            container, "✂️ FBA编辑", self.cb["fba_edit"], bg_color=Theme.SUCCESS, height=32
        ).pack(fill=tk.X, pady=3)
        ModernButton(
            container, "🔍 SKU编辑", self.cb["sku_edit"], bg_color=Theme.WARNING, height=32
        ).pack(fill=tk.X, pady=3)

        tk.Frame(container, bg=Theme.BORDER, height=1).pack(fill=tk.X, pady=6)

        ModernButton(
            container, "🗑️ 清空数据库", self.cb["clear_db"], bg_color=Theme.DANGER, height=32
        ).pack(fill=tk.X, pady=3)

    # ── 中栏：批量打印 ────────────────────────────────────────

    def _build_center(self) -> None:
        shadow, card = create_card(self, "批量打印", "🖨️")
        shadow.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # 箱唛输入
        input_frame = tk.Frame(card, bg=Theme.BG_CARD)
        input_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        tk.Label(
            input_frame,
            text="箱唛:",
            bg=Theme.BG_CARD,
            fg=Theme.TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.box_mark_entry = tk.Entry(
            input_frame,
            bg=Theme.BG_INPUT,
            fg=Theme.TEXT_PRIMARY,
            insertbackground=Theme.ACCENT,
            relief=tk.FLAT,
            font=("Microsoft YaHei UI", 10),
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT,
            borderwidth=0,
        )
        self.box_mark_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.box_mark_entry.bind(
            "<Return>", lambda e: self.cb["print_fba_all"](self.box_mark_entry.get())
        )

        # FBA 打印行
        fba_row = tk.Frame(card, bg=Theme.BG_CARD)
        fba_row.pack(fill=tk.X, padx=12, pady=4)
        ModernButton(
            fba_row,
            "⚙",
            lambda: self.cb["settings"]("FBA"),
            bg_color=Theme.SECONDARY,
            width=32,
            height=32,
        ).pack(side=tk.RIGHT)
        ModernButton(
            fba_row, "📦 打印 FBA", self._on_fba_print, bg_color=Theme.PRIMARY, height=32
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # SKU 打印行
        sku_row = tk.Frame(card, bg=Theme.BG_CARD)
        sku_row.pack(fill=tk.X, padx=12, pady=(6, 2))
        ModernButton(
            sku_row,
            "⚙",
            lambda: self.cb["settings"]("SKU"),
            bg_color=Theme.SECONDARY,
            width=32,
            height=32,
        ).pack(side=tk.RIGHT)
        ModernButton(
            sku_row, "🏷️ 打印 SKU", self._on_sku_print, bg_color=Theme.SUCCESS, height=32
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── 独立 FBA 打印区（紧凑单列）───────────────────────────

        tk.Frame(card, bg=Theme.BORDER, height=1).pack(fill=tk.X, padx=12, pady=(4, 1))

        # 地址
        self.fba_addr_entry = _make_entry_row(card, "地址", width=0)
        self.fba_addr_entry.pack_configure(fill=tk.X, expand=True)

        # FBA号
        self.fba_no_entry = _make_entry_row(card, "FBA号", width=0)
        self.fba_no_entry.pack_configure(fill=tk.X, expand=True)
        self.fba_no_entry.bind("<Return>", lambda e: self._on_direct_fba_print())

        # 份数
        row_qty = tk.Frame(card, bg=Theme.BG_CARD)
        row_qty.pack(fill=tk.X, padx=12, pady=(2, 6))

        tk.Label(row_qty, text="份数", bg=Theme.BG_CARD, fg=Theme.TEXT_SECONDARY,
                 font=("Microsoft YaHei UI", 7)).pack(side=tk.LEFT, padx=(0, 2))

        self.fba_qty_var = tk.StringVar(value="1")
        tk.Button(row_qty, text="−", font=("Arial", 9, "bold"),
                  bg=Theme.SECONDARY, fg=Theme.TEXT_LIGHT, relief=tk.FLAT,
                  cursor="hand2", width=2, height=1,
                  command=lambda: self._adjust_qty(-1)).pack(side=tk.LEFT)
        self.fba_qty_entry = tk.Entry(
            row_qty, textvariable=self.fba_qty_var, bg=Theme.BG_INPUT,
            fg=Theme.TEXT_PRIMARY, insertbackground=Theme.ACCENT,
            relief=tk.FLAT, font=("Microsoft YaHei UI", 9),
            highlightthickness=1, highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT, borderwidth=0,
            width=4, justify="center",
        )
        self.fba_qty_entry.pack(side=tk.LEFT, padx=1)
        tk.Button(row_qty, text="+", font=("Arial", 9, "bold"),
                  bg=Theme.SECONDARY, fg=Theme.TEXT_LIGHT, relief=tk.FLAT,
                  cursor="hand2", width=2, height=1,
                  command=lambda: self._adjust_qty(1)).pack(side=tk.LEFT)

        # 上传 + 打印按钮（独立一行，两列等宽）
        row_action = tk.Frame(card, bg=Theme.BG_CARD)
        row_action.pack(fill=tk.X, padx=12, pady=(4, 8))
        row_action.columnconfigure(0, weight=1, uniform="btn")
        row_action.columnconfigure(1, weight=1, uniform="btn")

        ModernButton(row_action, "📂 上传", self._on_upload_standalone_fba,
                     bg_color=Theme.SECONDARY, height=32).grid(row=0, column=0, sticky="ew", padx=2)
        ModernButton(row_action, "▶ 打印", self._on_direct_fba_print,
                     bg_color=Theme.DANGER, height=32).grid(row=0, column=1, sticky="ew", padx=2)

    # ── 右栏：单个 SKU ────────────────────────────────────────

    def _build_right(self) -> None:
        shadow, card = create_card(self, "单 SKU 打印", "🔖")
        shadow.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

        tk.Label(
            card,
            text="SKU:",
            bg=Theme.BG_CARD,
            fg=Theme.TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=12, pady=(0, 4))

        self.single_sku_entry = tk.Entry(
            card,
            bg=Theme.BG_INPUT,
            fg=Theme.TEXT_PRIMARY,
            insertbackground=Theme.ACCENT,
            relief=tk.FLAT,
            font=("Microsoft YaHei UI", 10),
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT,
            borderwidth=0,
        )
        self.single_sku_entry.pack(fill=tk.X, padx=12, pady=2)
        self.single_sku_entry.bind("<Return>", lambda e: self._on_single_print())
        self.single_sku_entry.bind("<Control-v>", self._on_sku_paste)
        self.single_sku_entry.bind("<Button-3>", self._on_sku_right_click)

        tk.Label(
            card,
            text="数量:",
            bg=Theme.BG_CARD,
            fg=Theme.TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=12, pady=(10, 4))

        self.single_qty_entry = tk.Entry(
            card,
            bg=Theme.BG_INPUT,
            fg=Theme.TEXT_PRIMARY,
            insertbackground=Theme.ACCENT,
            relief=tk.FLAT,
            font=("Microsoft YaHei UI", 10),
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT,
            borderwidth=0,
        )
        self.single_qty_entry.insert(0, "1")
        self.single_qty_entry.pack(fill=tk.X, padx=12, pady=2)
        self.single_qty_entry.bind("<Return>", lambda e: self._on_single_print())

        btn_row = tk.Frame(card, bg=Theme.BG_CARD)
        btn_row.pack(fill=tk.X, padx=12, pady=(8, 8))
        ModernButton(
            btn_row,
            "⚙",
            lambda: self.cb["settings"]("Single"),
            bg_color=Theme.SECONDARY,
            width=32,
            height=32,
        ).pack(side=tk.RIGHT)
        ModernButton(
            btn_row, "▶ 开始打印", self._on_single_print, bg_color=Theme.WARNING, height=32
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ── 事件处理 ──────────────────────────────────────────────

    def _on_fba_print(self) -> None:
        self.cb["print_fba_only"](self.box_mark_entry.get())

    def _on_sku_print(self) -> None:
        self.cb["print_sku"](self.box_mark_entry.get())

    def _on_single_print(self) -> None:
        self.cb["single_print"](self.single_sku_entry.get(), self.single_qty_entry.get())

    # ── 独立 FBA 打印事件 ──────────────────────────────────────

    def _on_upload_standalone_fba(self) -> None:
        self.cb["upload_standalone_fba"]()

    def _on_direct_fba_print(self) -> None:
        fba_no = self.fba_no_entry.get()
        addr = self.fba_addr_entry.get()
        try:
            qty = int(self.fba_qty_var.get())
        except (ValueError, TypeError):
            qty = 1
        self.cb["direct_fba_print"](fba_no, addr, qty)

    def _adjust_qty(self, delta: int) -> None:
        try:
            cur = int(self.fba_qty_var.get())
        except (ValueError, TypeError):
            cur = 1
        cur = max(1, cur + delta)
        self.fba_qty_var.set(str(cur))

    def _on_sku_paste(self, event: tk.Event) -> None:
        self.after(10, self._trim_sku)
        return None

    def _on_sku_right_click(self, event: tk.Event) -> None:
        self.after(10, self._trim_sku)

    def _trim_sku(self) -> None:
        try:
            text = self.single_sku_entry.get()
            trimmed = text.replace(" ", "").replace("\t", "").replace("\n", "").strip()
            if text != trimmed:
                self.single_sku_entry.delete(0, tk.END)
                self.single_sku_entry.insert(0, trimmed)
        except Exception:
            # Entry 可能在 tkinter 销毁后被访问，非关键路径直接忽略
            pass
