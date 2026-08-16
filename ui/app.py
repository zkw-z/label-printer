"""主应用窗口

组装 UI 组件、注册回调、对接 WorkflowService。
管理线程调度（pywin32 COM 初始化）、键盘快捷键。
"""

from __future__ import annotations

# ─── UI 布局常量 ─────────────────────────────────────────
WINDOW_WIDTH: int = 750
WINDOW_HEIGHT: int = 640
TOP_BAR_HEIGHT: int = 30
UPPER_FRAME_HEIGHT: int = 380
RESIZABLE_WIDTH: bool = False
RESIZABLE_HEIGHT: bool = False

import atexit
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from typing import Any

from loguru import logger

from config import CONFIG_FILE
from models.recent_files import add_recent_file
from services.com_thread import COMThreadPool
from services.edit_service import run_fba_edit, run_sku_edit
from services.print_service import PrintService
from services.workflow_service import WorkflowService
from ui.about_dialog import show_about
from ui.lower_section import LowerSection
from ui.progress_bar import ProgressBar
from ui.settings_dialog import ExcelColumnSettingsDialog, SettingsDialog
from ui.upper_section import UpperSection
from ui.widgets import Theme


class LabelPrinterApp:
    """标签打印工具主窗口。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("🏷️ 标签打印工具")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(RESIZABLE_WIDTH, RESIZABLE_HEIGHT)
        self.root.configure(bg=Theme.BG_MAIN)

        self.print_service = PrintService()
        self._thread_pool = COMThreadPool(max_workers=3)
        atexit.register(self._thread_pool.shutdown, wait=False)

        # 先初始化 UI（日志面板先就绪，Loguru sink 注册）
        self._init_ui()

        # 延迟初始化工作流（日志面板已就绪）
        self._init_workflow()

        # 全局快捷键
        self.root.bind("<Down>", self._on_down_key)

        logger.info("应用程序已启动。按 '↓' 下键可依次填入箱唛，'Enter' 回车键开始打印。")
        logger.info(
            f"FBA 打印机: {self.workflow.state.fba_printer} (缩放: {self.workflow.state.fba_scale})"
        )
        logger.info(f"SKU 打印机: {self.workflow.state.sku_printer}")

        # 自动清理 30 天前数据
        ok, count = self.workflow.sku_db.cleanup(30)
        if ok and count > 0:
            logger.info(f"🧹 已自动清理 {count} 条 30 天前的旧数据记录")

    # ─── UI 构造 ───────────────────────────────────────────────

    def _init_ui(self) -> None:
        # 顶部栏
        top_bar = tk.Frame(self.root, bg=Theme.BG_MAIN, height=TOP_BAR_HEIGHT)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)

        tk.Button(
            top_bar,
            text="指示表列名",
            font=("Microsoft YaHei UI", 9),
            bg=Theme.PRIMARY,
            fg=Theme.TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            command=self._open_excel_col_settings,
            padx=12,
            pady=5,
        ).pack(side=tk.RIGHT, padx=0, pady=3)

        tk.Button(
            top_bar,
            text="ℹ️ 关于",
            font=("Microsoft YaHei UI", 9),
            bg=Theme.PRIMARY,
            fg=Theme.TEXT_LIGHT,
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: show_about(self.root, "."),
            padx=12,
            pady=5,
        ).pack(side=tk.RIGHT, padx=15, pady=3)

        # 上部功能区
        upper_frame = tk.Frame(self.root, height=UPPER_FRAME_HEIGHT, bg=Theme.BG_MAIN)
        upper_frame.pack(fill=tk.X, expand=False)
        upper_frame.pack_propagate(False)

        self.ui_upper = UpperSection(upper_frame, self._make_callbacks())

        # 日志面板（同时注册 loguru sink）
        self.ui_lower = LowerSection(self.root)

        # 进度条（嵌入日志面板下方）
        self._progress = ProgressBar(self.ui_lower)
        self.ui_lower.progress = self._progress

    def _make_callbacks(self) -> dict[str, Any]:
        """注册 UI 回调 → 业务方法。"""
        return {
            "upload_excel": lambda: self._upload_excel(),
            "upload_fba": lambda: self._upload_fba(),
            "upload_sku": lambda: self._upload_sku(),
            "print_fba_all": lambda mark: self._run_thread(
                self.workflow.batch_print_fba, mark, True
            ),
            "print_fba_only": lambda mark: self._run_thread(
                self.workflow.batch_print_fba, mark, False
            ),
            "print_sku": lambda mark: self._run_thread(self.workflow.batch_print_sku, mark),
            "single_print": lambda sku, qty: self._run_thread(self._single_print, sku, qty),
            "settings": lambda t: self._open_settings(t),
            "clear_db": lambda: self._clear_database(),
            "fba_edit": lambda: self._fba_edit(),
            "sku_edit": lambda: self._sku_edit(),
            "upload_standalone_fba": lambda: self._upload_standalone_fba(),
            "direct_fba_print": lambda fba, addr, qty: self._run_thread(
                self.workflow.direct_print_fba, fba, addr, qty
            ),
        }

    def _init_workflow(self) -> None:
        """延迟初始化业务层（日志面板已就绪）。"""
        self.workflow = WorkflowService()

    # ─── 线程管理 ──────────────────────────────────────────────

    def _run_thread(self, func: Any, *args: Any) -> None:
        """在后台线程池中执行耗时操作，自动管理 COM 环境。"""

        def _on_fba_done() -> None:
            self.root.after(0, lambda: self.ui_upper.box_mark_entry.delete(0, tk.END))

        on_done = None
        if getattr(func, "__func__", None) is WorkflowService.batch_print_fba:
            on_done = _on_fba_done
        self._thread_pool.submit(func, *args, on_done=on_done)

    # ─── 文件上传回调 ──────────────────────────────────────────

    def _upload_excel(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Excel 文件", "*.xlsx;*.xls")])
        if path:
            add_recent_file(path)
            self._run_thread(self.workflow.upload_excel, path)

    def _upload_fba(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF 文件", "*.pdf")])
        if path:
            if self.workflow.state.excel_data is None:
                logger.warning("错误：请先上传 Excel 文件以验证 FBA 番号。")
                return
            add_recent_file(path)
            self._run_thread(self.workflow.upload_fba_pdf, path)

    def _upload_sku(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF 文件", "*.pdf")])
        if not path:
            return

        single_sku = self.ui_upper.single_sku_entry.get().strip()
        if single_sku:
            confirm = messagebox.askyesno(
                "保存单个 SKU",
                f"检测到您在右侧输入了单个 SKU '{single_sku}'。\n"
                "是否将当前上传的 PDF 保存为该 SKU 的标签？",
                parent=self.root,
            )
            if confirm:
                self._run_thread(self.workflow.upload_sku_pdf, path, single_sku)
                return

        # 无 Excel：尝试单页自动命名
        if self.workflow.state.excel_data is None:
            try:
                import pypdfium2 as pdfium

                pdf = pdfium.PdfDocument(path)
                if len(pdf) == 1:
                    name = simpledialog.askstring(
                        "输入 SKU 名称",
                        "未检测到 Excel 派送表。当前 PDF 只有 1 页，请输入要保存的 SKU 名称：",
                        parent=self.root,
                    )
                    if name:
                        self._run_thread(self.workflow.upload_sku_pdf, path, name.strip())
                        return
            except Exception as e:
                logger.warning(f"读取 PDF 页数失败: {e}")

        add_recent_file(path)
        self._run_thread(self.workflow.upload_sku_pdf, path)

    # ─── 单 SKU 打印 ──────────────────────────────────────────

    def _single_print(self, sku: str, qty: str) -> None:
        try:
            qty_int = int(qty)
        except (ValueError, TypeError):
            logger.warning("错误：数量必须是数字。")
            return
        self.workflow.single_print_sku(sku.strip(), qty_int)
        self.root.after(0, lambda: self.ui_upper.single_sku_entry.delete(0, tk.END))

    # ─── 清空数据库 ────────────────────────────────────────────

    def _upload_standalone_fba(self) -> None:
        """独立上传 FBA PDF——无需 Excel，自动发现 FBA 编号。"""
        path = filedialog.askopenfilename(filetypes=[("PDF 文件", "*.pdf")])
        if path:
            add_recent_file(path)
            self._run_thread(self.workflow.upload_fba_standalone, path)

    def _clear_database(self) -> None:
        stats = self.workflow.sku_db.stats()
        if stats["total_skus"] == 0:
            messagebox.showinfo("提示", "数据库已经是空的。")
            return

        confirm = messagebox.askyesno(
            "确认清空",
            f"确定要清空 SKU 数据库吗？\n\n"
            f"当前数据库包含:\n"
            f"• {stats['total_skus']} 个 SKU\n"
            f"• 总大小: {stats['total_size_mb']} MB\n\n"
            "此操作无法撤销！",
        )
        if confirm:
            ok, msg = self.workflow.sku_db.clear_all()
            logger.info(msg)
            if ok:
                messagebox.showinfo("成功", "SKU 数据库已清空。")
            else:
                messagebox.showerror("错误", msg)

    # ─── FBA/SKU 编辑 ──────────────────────────────────────────

    def _fba_edit(self) -> None:
        """FBA编辑 — 选择目录后执行 PDF 合并裁剪。"""
        path = filedialog.askdirectory(
            title="选择包含 FBA 标签 PDF 的源目录",
            mustexist=True,
        )
        if path:
            logger.info(f"FBA编辑 — 开始处理: {path}")
            self._run_thread(run_fba_edit, path)

    def _sku_edit(self) -> None:
        """SKU编辑 — 选择目录后执行 FNSKU 提取与标签生成。"""
        path = filedialog.askdirectory(
            title="选择包含 SKU 标签 PDF 的源目录",
            mustexist=True,
        )
        if path:
            logger.info(f"SKU编辑 — 开始处理: {path}")
            self._run_thread(run_sku_edit, path)

    # ─── 设置 ──────────────────────────────────────────────────

    def _open_excel_col_settings(self) -> None:
        """打开"指示表自定义列名"设置窗口。"""
        from config_schema import AppConfig

        state = self.workflow.state

        def _save(mapping: dict[str, str], match_mode: str, priority: bool) -> None:
            state.excel_col_mapping = mapping
            state.excel_col_match_mode = match_mode
            state.excel_col_priority = priority
            logger.info(
                f"指示表列名设置已保存：{len(mapping)} 个字段，"
                f"匹配方式={match_mode}，优先自定义={priority}"
            )
            # 持久化：从 AppState 构建 AppConfig 写入
            cfg = AppConfig(
                **{f: getattr(state, f) for f in AppConfig.model_fields}
            )
            cfg.save(CONFIG_FILE)

        ExcelColumnSettingsDialog(
            self.root,
            mapping=state.excel_col_mapping,
            match_mode=state.excel_col_match_mode,
            priority=state.excel_col_priority,
            save_cb=_save,
        )

    def _open_settings(self, type_: str) -> None:
        printers = self.print_service.list_printers()
        state = self.workflow.state

        if type_ == "FBA":
            cur_printer = state.fba_printer
            cur_orient = state.fba_orientation
            cur_width = state.fba_width
            cur_height = state.fba_height
        else:
            cur_printer = state.sku_printer
            cur_orient = state.sku_orientation
            cur_width = state.sku_width
            cur_height = state.sku_height

        def _save(printer: str, orientation: str, width: int, height: int) -> None:
            from config_schema import AppConfig

            if type_ == "FBA":
                state.fba_printer = printer
                state.fba_orientation = orientation
                state.fba_width = width
                state.fba_height = height
                logger.info(
                    f"FBA 设置已保存: {printer}, {orientation}, {width}×{height}mm"
                )
            else:
                state.sku_printer = printer
                state.sku_orientation = orientation
                state.sku_width = width
                state.sku_height = height
                logger.info(f"SKU 设置已保存: {printer}, {orientation}")

            # 持久化：从 AppState 构建 AppConfig 写入
            cfg = AppConfig(
                **{f: getattr(state, f) for f in AppConfig.model_fields}
            )
            cfg.save(CONFIG_FILE)

        # 构建纸张列表获取回调（FBA / SKU 共用）
        fetch_size = self.print_service.get_printer_page_size_mm
        fetch_forms = self.print_service.get_printer_forms

        SettingsDialog(
            self.root, printers,
            cur_printer, cur_orient, cur_width, cur_height,
            _save, type_,
            fetch_page_size=fetch_size,
            fetch_forms=fetch_forms,
        )

    # ─── 键盘快捷键 ────────────────────────────────────────────

    def _on_down_key(self, event: tk.Event) -> None:
        current = self.ui_upper.box_mark_entry.get().strip()
        mark, idx, total = self.workflow.get_next_box_mark(current)
        if mark:
            self.ui_upper.box_mark_entry.delete(0, tk.END)
            self.ui_upper.box_mark_entry.insert(0, mark)
            self.ui_upper.box_mark_entry.focus_set()
            logger.info(f"👉 已自动填入第 {idx}/{total} 个箱唛: {mark}")
        else:
            logger.info("提示：请先上传指示文件 (Excel) 以获取箱唛列表。")
