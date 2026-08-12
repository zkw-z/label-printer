"""打印机设置对话框

FBA 模式下提供打印机 + 方向 + 纸张大小下拉列表（类似 Word 打印界面）。
纸张列表从打印机驱动通过 DeviceCapabilities 自动获取。
SKU 模式保持手动输入不变。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ui.widgets import Theme


class SettingsDialog:
    """打印机选择 + 方向 + 纸张尺寸的设置窗口。"""

    def __init__(
        self,
        parent: tk.Toplevel | tk.Tk,
        printers: list[str],
        current_printer: str,
        current_orientation: str,
        current_width: int,
        current_height: int,
        save_cb: Callable[[str, str, int, int], None],
        type_label: str,
        fetch_page_size: Callable[[str], tuple[int, int]] | None = None,
        fetch_forms: Callable[[str], list[tuple[str, int, int]]] | None = None,
    ) -> None:
        self._is_fba = type_label == "FBA"
        self._save_cb = save_cb
        self._fetch_page_size = fetch_page_size
        self._fetch_forms = fetch_forms

        h = 300 if self._is_fba else 200

        win = tk.Toplevel(parent)
        win.title(f"设置 - {type_label}")
        win.geometry(f"340x{h}")
        win.resizable(False, False)
        win.transient(parent)
        win.grab_set()

        # ── 打印机 ──────────────────────────────────────────────

        tk.Label(win, text="选择打印机:").pack(pady=(8, 2))

        printer_var = tk.StringVar(value=current_printer)
        cb = ttk.Combobox(win, textvariable=printer_var, values=printers, state="readonly")
        cb.pack(pady=(0, 5))

        # ── 方向 ────────────────────────────────────────────────

        tk.Label(win, text="方向:").pack(pady=(5, 2))
        orient_var = tk.StringVar(value=current_orientation)
        orient_frame = tk.Frame(win)
        orient_frame.pack()
        ttk.Radiobutton(orient_frame, text="纵向", variable=orient_var, value="portrait").pack(
            side=tk.LEFT, padx=10
        )
        ttk.Radiobutton(orient_frame, text="横向", variable=orient_var, value="landscape").pack(
            side=tk.LEFT, padx=10
        )

        # ── 纸张尺寸 ────────────────────────────────────────────

        width_var = tk.StringVar(value=str(current_width))
        height_var = tk.StringVar(value=str(current_height))

        if self._is_fba and fetch_forms:
            _build_fba_forms_section(
                win, printer_var, width_var, height_var, fetch_forms, fetch_page_size,
                current_width, current_height,
            )
        elif self._is_fba and fetch_page_size:
            _build_fba_single_section(win, printer_var, width_var, height_var, fetch_page_size)
        else:
            _build_manual_size_section(win, width_var, height_var)

        # ── 保存 ────────────────────────────────────────────────

        def _save() -> None:
            try:
                w = int(width_var.get())
                h_val = int(height_var.get())
            except ValueError:
                w, h_val = current_width, current_height
            self._save_cb(printer_var.get(), orient_var.get(), w, h_val)
            win.destroy()

        tk.Button(
            win,
            text="保存",
            font=("Microsoft YaHei UI", 10),
            bg=Theme.PRIMARY,
            fg=Theme.TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            command=_save,
            padx=30,
            pady=6,
        ).pack(pady=15)

        # 动态计算实际所需高度，避免内容溢出导致保存按钮被遮挡（高 DPI 下尤其明显）
        win.update_idletasks()
        req_h = win.winfo_reqheight()
        win.geometry(f"340x{req_h}")
        x = (win.winfo_screenwidth() // 2) - (340 // 2)
        y = (win.winfo_screenheight() // 2) - (req_h // 2)
        win.geometry(f"+{x}+{y}")


# ── FBA 纸张下拉列表（Word 风格）──────────────────────────────────


def _build_fba_forms_section(
    win: tk.Toplevel,
    printer_var: tk.StringVar,
    width_var: tk.StringVar,
    height_var: tk.StringVar,
    fetch_forms: Callable[[str], list[tuple[str, int, int]]],
    fetch_page_size: Callable[[str], tuple[int, int]] | None,
    current_width: int,
    current_height: int,
) -> None:
    """构建 FBA 纸张大小下拉列表（Combobox）区域。"""

    tk.Frame(win, height=8).pack()

    tk.Label(
        win,
        text="📐 纸张大小",
        font=("Microsoft YaHei UI", 9, "bold"),
        fg=Theme.TEXT_SECONDARY,
    ).pack(anchor="w", padx=10, pady=(5, 4))

    # 显示当前选中尺寸
    info_var = tk.StringVar()
    info_label = tk.Label(
        win,
        textvariable=info_var,
        font=("Microsoft YaHei UI", 9),
        fg=Theme.PRIMARY,
    )
    info_label.pack(pady=(0, 4))

    # 纸张下拉列表
    paper_names: list[str] = []
    paper_map: dict[str, tuple[int, int]] = {}  # display_name → (w, h)

    paper_combo = ttk.Combobox(
        win,
        values=[],
        state="readonly",
        font=("Microsoft YaHei UI", 10),
    )
    paper_combo.pack(fill=tk.X, padx=20, pady=(0, 8))

    def _refresh_paper_list(*_args) -> None:
        """刷新纸张下拉列表。"""
        nonlocal paper_names, paper_map
        printer = printer_var.get()
        if not printer:
            return

        forms = fetch_forms(printer)
        paper_names = []
        paper_map = {}

        # 构建显示名称（去重 + 格式化）
        seen: set[tuple[int, int]] = set()
        for name, w, h in forms:
            key = (w, h)
            if key in seen:
                continue
            seen.add(key)
            display = f"{w} × {h} mm  —  {name}" if name else f"{w} × {h} mm"
            paper_names.append(display)
            paper_map[display] = (w, h)

        paper_combo["values"] = paper_names

        # 预选：优先匹配当前设置值，否则用打印机默认
        default_w, default_h = current_width, current_height
        if fetch_page_size:
            from contextlib import suppress
            with suppress(Exception):
                default_w, default_h = fetch_page_size(printer)

        best_match = _find_best_match(paper_map, default_w, default_h)
        if best_match:
            paper_combo.set(best_match)
            _on_paper_selected()
        elif paper_names:
            paper_combo.set(paper_names[0])
            _on_paper_selected()

    def _on_paper_selected(*_args) -> None:
        """纸张选中时更新宽高变量。"""
        selected = paper_combo.get()
        if selected in paper_map:
            w, h = paper_map[selected]
            width_var.set(str(w))
            height_var.set(str(h))
            info_var.set(f"当前选择: {w} × {h} mm")
        else:
            info_var.set("")

    paper_combo.bind("<<ComboboxSelected>>", _on_paper_selected)

    # 打印机切换时自动刷新
    printer_var.trace_add("write", lambda *a: win.after(50, _refresh_paper_list))

    # 首次加载
    win.after(100, _refresh_paper_list)


def _find_best_match(
    paper_map: dict[str, tuple[int, int]], target_w: int, target_h: int
) -> str | None:
    """在纸张列表中找最接近目标尺寸的项。"""
    best_name = None
    best_diff = float("inf")
    for name, (w, h) in paper_map.items():
        diff = abs(w - target_w) + abs(h - target_h)
        if diff < best_diff:
            best_diff = diff
            best_name = name
    return best_name


# ── FBA 降级：单值获取 ────────────────────────────────────────────


def _build_fba_single_section(
    win: tk.Toplevel,
    printer_var: tk.StringVar,
    width_var: tk.StringVar,
    height_var: tk.StringVar,
    fetch_page_size: Callable[[str], tuple[int, int]],
) -> None:
    """构建单值自动获取区（无 DeviceCapabilities 时的降级方案）。"""
    tk.Frame(win, height=8).pack()

    header = tk.Frame(win)
    header.pack(fill=tk.X, padx=0, pady=(5, 4))
    tk.Label(header, text="📐 页面尺寸（从打印机获取）", font=("Microsoft YaHei UI", 9, "bold"),
             fg=Theme.TEXT_SECONDARY).pack(side=tk.LEFT, padx=4)
    refresh_btn = tk.Button(header, text="🔄 刷新", font=("Microsoft YaHei UI", 8),
                            bg=Theme.SECONDARY, fg=Theme.TEXT_LIGHT, relief=tk.FLAT,
                            cursor="hand2", padx=8, pady=2)
    refresh_btn.pack(side=tk.RIGHT, padx=4)

    def _refresh() -> None:
        w, h = fetch_page_size(printer_var.get())
        width_var.set(str(w))
        height_var.set(str(h))
    refresh_btn.config(command=_refresh)
    printer_var.trace_add("write", lambda *a: _refresh())

    size_frame = tk.Frame(win)
    size_frame.pack(pady=(4, 2))
    tk.Label(size_frame, text="宽度:", font=("Microsoft YaHei UI", 10),
             fg=Theme.TEXT_PRIMARY).pack(side=tk.LEFT, padx=(0, 5))
    tk.Label(size_frame, textvariable=width_var, font=("Microsoft YaHei UI", 12, "bold"),
             fg=Theme.PRIMARY, width=5, anchor="center").pack(side=tk.LEFT)
    tk.Label(size_frame, text="mm", font=("Microsoft YaHei UI", 10),
             fg=Theme.TEXT_SECONDARY).pack(side=tk.LEFT, padx=(2, 20))
    tk.Label(size_frame, text="高度:", font=("Microsoft YaHei UI", 10),
             fg=Theme.TEXT_PRIMARY).pack(side=tk.LEFT, padx=(0, 5))
    tk.Label(size_frame, textvariable=height_var, font=("Microsoft YaHei UI", 12, "bold"),
             fg=Theme.PRIMARY, width=5, anchor="center").pack(side=tk.LEFT)
    tk.Label(size_frame, text="mm", font=("Microsoft YaHei UI", 10),
             fg=Theme.TEXT_SECONDARY).pack(side=tk.LEFT, padx=(2, 0))
    win.after(100, _refresh)


# ── 手动输入（SKU 模式 / FBA 完全降级）───────────────────────────


def _build_manual_size_section(
    win: tk.Toplevel,
    width_var: tk.StringVar,
    height_var: tk.StringVar,
) -> None:
    """构建手动输入宽度/高度区域。"""
    tk.Frame(win, height=8).pack()
    tk.Label(win, text="📐 手动输入尺寸", font=("Microsoft YaHei UI", 9, "bold"),
             fg=Theme.TEXT_SECONDARY).pack(anchor="w", padx=4, pady=(5, 4))
    size_frame = tk.Frame(win)
    size_frame.pack(pady=(2, 2))
    tk.Label(size_frame, text="宽度 (mm):").pack(side=tk.LEFT, padx=(0, 5))
    tk.Entry(size_frame, textvariable=width_var, width=6, justify="center",
             font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
    size_frame2 = tk.Frame(win)
    size_frame2.pack(pady=(2, 5))
    tk.Label(size_frame2, text="高度 (mm):").pack(side=tk.LEFT, padx=(0, 5))
    tk.Entry(size_frame2, textvariable=height_var, width=6, justify="center",
             font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)


# ─────────────────────────────────────────────────────
# 指示表自定义列名设置对话框
# ─────────────────────────────────────────────────────

# 标准字段（顺序展示用），必须与 excel_data.CUSTOM_REQUIRED / CUSTOM_OPTIONAL 一致
CUSTOM_FIELD_LABELS: list[tuple[str, str, bool]] = [
    ("箱唛", "箱唛", True),
    ("FBA番号", "FBA番号", True),
    ("箱数", "箱数", True),
    ("SKU", "SKU", True),
    ("SKU数量", "SKU数量", True),
    ("贴标顺序", "贴标顺序", True),
    ("FBA仓库编码", "FBA仓库编码", True),
    ("FBA序列号", "FBA序列号", True),
    ("对应SKU标识", "对应SKU标识", False),
    ("份数", "份数", False),
    ("备注", "备注", False),
]


class ExcelColumnSettingsDialog:
    """指示表自定义列名设置窗口。

    允许用户为上传的指示文件配置列名映射，保存后下次启动自动加载。
    """

    def __init__(
        self,
        parent: tk.Toplevel | tk.Tk,
        mapping: dict[str, str],
        match_mode: str = "contains",
        priority: bool = False,
        save_cb: Callable[[dict[str, str], str, bool], None] | None = None,
    ) -> None:
        self._mapping = dict(mapping or {})
        self._match_mode = match_mode
        self._priority = bool(priority)
        self._save_cb = save_cb

        win = tk.Toplevel(parent)
        self._win = win
        win.title("设置 - 指示表自定义列名")
        win.geometry("480x620")
        win.resizable(False, False)
        win.transient(parent)
        win.grab_set()
        win.configure(bg=Theme.BG_MAIN)

        # ── 说明 ──
        tk.Label(
            win,
            text="为上传的指示文件配置列名对应关系（* 为必填字段）",
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=Theme.BG_MAIN,
            fg=Theme.TEXT_SECONDARY,
        ).pack(pady=(10, 2))

        # ── 匹配方式 + 优先开关 ──
        opt_frame = tk.Frame(win, bg=Theme.BG_MAIN)
        opt_frame.pack(fill=tk.X, padx=16, pady=(6, 2))

        self._match_var = tk.StringVar(value="exact" if self._match_mode == "exact" else "contains")
        tk.Label(opt_frame, text="匹配方式:", bg=Theme.BG_MAIN, fg=Theme.TEXT_PRIMARY,
                 font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT)
        match_cb = ttk.Combobox(
            opt_frame, textvariable=self._match_var, state="readonly", width=14,
            values=["contains", "exact"],
            font=("Microsoft YaHei UI", 9),
        )
        match_cb.pack(side=tk.LEFT, padx=(4, 14))
        match_cb.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_match_mode_change(),
        )

        self._priority_var = tk.BooleanVar(value=self._priority)
        ttk.Checkbutton(
            opt_frame,
            text="优先使用自定义列名匹配",
            variable=self._priority_var,
        ).pack(side=tk.LEFT)

        # ── 列名输入区 ──
        body = tk.Frame(win, bg=Theme.BG_MAIN)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        self._entry_vars: dict[str, tk.StringVar] = {}
        for std_name, label, required in CUSTOM_FIELD_LABELS:
            row = tk.Frame(body, bg=Theme.BG_MAIN)
            row.pack(fill=tk.X, pady=2)
            star = " *" if required else ""
            tk.Label(
                row, text=f"{label}{star}:", width=14, anchor="w",
                bg=Theme.BG_MAIN, fg=Theme.TEXT_PRIMARY,
                font=("Microsoft YaHei UI", 9),
            ).pack(side=tk.LEFT)
            var = tk.StringVar(value=self._mapping.get(std_name, ""))
            self._entry_vars[std_name] = var
            tk.Entry(
                row, textvariable=var, width=32,
                font=("Microsoft YaHei UI", 9),
            ).pack(side=tk.LEFT, padx=(4, 0))

        self._mode_hint = tk.Label(
            win, text="", bg=Theme.BG_MAIN, fg=Theme.TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        )
        self._mode_hint.pack(pady=(2, 2))
        self._update_mode_hint()

        # ── 按钮区 ──
        btn_frame = tk.Frame(win, bg=Theme.BG_MAIN)
        btn_frame.pack(fill=tk.X, padx=16, pady=(6, 12))

        tk.Button(
            btn_frame, text="保存", width=10, bg=Theme.PRIMARY, fg=Theme.TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", command=self._on_save,
        ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(
            btn_frame, text="取消", width=10, bg=Theme.BG_CARD, fg=Theme.TEXT_PRIMARY,
            relief=tk.FLAT, cursor="hand2", command=win.destroy,
        ).pack(side=tk.LEFT)

    def _on_match_mode_change(self) -> None:
        self._update_mode_hint()

    def _update_mode_hint(self) -> None:
        mode = self._match_var.get()
        if mode == "exact":
            self._mode_hint.config(text="完全等于：表头必须与关键字完全一致")
        else:
            self._mode_hint.config(text="包含关键字：表头含有关键字即匹配（不区分大小写）")

    def _on_save(self) -> None:
        mapping: dict[str, str] = {}
        for std_name, var in self._entry_vars.items():
            val = var.get().strip()
            if val:
                mapping[std_name] = val
        mode = self._match_var.get()
        priority = self._priority_var.get()
        if self._save_cb is not None:
            self._save_cb(mapping, mode, priority)
        self._win.destroy()
