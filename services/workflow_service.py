"""工作流编排服务

组合 ExcelData + PDFMapper + SKUDatabase + PrintService，
实现完整的 FBA / SKU 批量打印、单个 SKU 打印的业务流程。

本模块不依赖 UI，可在后台线程中调用。所有结果通过 loguru 输出。
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger
from PIL import Image

from config import CONFIG_FILE
from models.excel_data import ExcelData, ExcelLoader, extract_tail_number
from models.pdf_mapper import PDFMapper
from models.sku_database import SKUDatabase
from services.label_firewall import check_firewall
from services.pdf_renderer import PdfRenderer
from services.print_service import PrintJob, PrintService

# ─── 数据结构 ────────────────────────────────────────────────


@dataclass
class AppState:
    """应用全局状态——打印配置 + 数据集引用。"""

    # 打印配置
    fba_printer: str = ""
    fba_orientation: str = "portrait"
    fba_scale: float = 0.98
    fba_width: int = 100
    fba_height: int = 100
    sku_printer: str = ""
    sku_orientation: str = "portrait"
    sku_width: int = 50
    sku_height: int = 30

    # 数据
    excel_data: ExcelData | None = None
    all_box_marks: list[str] | None = None
    current_mark_index: int = -1

    # 指示表自定义列名映射
    excel_col_mapping: dict[str, str] = field(default_factory=dict)
    excel_col_match_mode: str = "contains"
    excel_col_priority: bool = False


class WorkflowService:
    """FBA / SKU 标签打印工作流编排。

    Usage:
        ws = WorkflowService()
        ws.upload_excel(path)
        ws.upload_fba_pdf(path)
        ws.batch_print_fba("箱唛001")
    """

    def __init__(self) -> None:
        self.excel_loader = ExcelLoader()
        self.pdf_mapper = PDFMapper()
        self.sku_db = SKUDatabase()
        self.print_service = PrintService()
        self.pdf_renderer = PdfRenderer()

        self.state = AppState()

        # 加载保存的配置
        self._restore_config()

    # ─── 配置 ──────────────────────────────────────────────────

    def _restore_config(self) -> None:
        """从 AppConfig 加载持久化配置到 AppState。

        使用 pydantic 模型替代裸 dict，字段变更时自动同步，无需手动逐字段赋值。
        """
        from config_schema import AppConfig

        cfg = AppConfig.load(CONFIG_FILE)
        printers = self.print_service.list_printers()
        default = printers[0] if printers else ""

        for field_name in AppConfig.model_fields:
            value = getattr(cfg, field_name)
            if field_name in ("fba_printer", "sku_printer") and not value:
                value = default
            setattr(self.state, field_name, value)

    # ─── 文件上传 ──────────────────────────────────────────────

    def upload_excel(self, path: str) -> bool:
        """上传并解析 Excel 指示文件。"""
        logger.info(f"正在加载 Excel: {path}...")
        data, msg = self.excel_loader.parse(
            path,
            custom_mapping=self.state.excel_col_mapping,
            match_mode=self.state.excel_col_match_mode,
            custom_priority=self.state.excel_col_priority,
        )
        logger.info(msg)

        if data is not None:
            self.state.excel_data = data
            self.state.all_box_marks = data.box_marks
            self.state.current_mark_index = -1
            logger.info(
                f"找到 {len(self.state.all_box_marks)} 个箱唛。"
                "按 '↓' 下键可依次自动填入，'Enter' 回车打印。"
            )
            # ── 透明标签防火墙 ──────────────────────────────
            check_firewall(data)
            return True
        return False

    def upload_fba_pdf(self, path: str) -> bool:
        """上传 FBA PDF 并校验页数。"""
        if self.state.excel_data is None:
            logger.warning("错误：请先上传 Excel 文件以验证 FBA 番号。")
            return False

        expected_fbas = self.state.excel_data.unique_values("FBA番号")
        logger.info(f"正在加载 FBA PDF: {path}...")
        msg = self.pdf_mapper.parse_fba(path, expected_fbas)
        logger.info(msg)

        # 校验箱数 vs 页数（按 FBA 番号分组汇总）
        # 当多个箱唛共享同一 FBA PDF 时，汇总箱数后统一校验
        from collections import defaultdict
        fba_box_totals = defaultdict(int)
        fba_box_marks = defaultdict(list)
        for mark in self.state.all_box_marks or []:
            info = self.state.excel_data.get_fba_info(mark)
            if not info:
                continue
            fba_no = str(info.get("FBA番号", ""))
            if fba_no:
                box_count = self.state.excel_data.get_box_count_for_mark(mark)
                fba_box_totals[fba_no] += box_count
                fba_box_marks[fba_no].append(mark)
        for fba_no, total_expected in fba_box_totals.items():
            actual_pages = self.pdf_mapper.get_fba_pages(fba_no)
            actual = len(actual_pages)
            if total_expected != actual:
                marks_list = ", ".join(fba_box_marks[fba_no])
                logger.warning(
                    f"警告：FBA '{fba_no}' (箱唛: {marks_list}) "
                    f"箱数合计 ({total_expected}) 与 "
                    f"FBA PDF 页数 ({actual}) 不匹配"
                )
        return True

    def upload_sku_pdf(self, path: str, single_sku: str = "") -> bool:
        """上传 SKU PDF，支持单个 SKU 命名保存。"""
        # 单个 SKU 快速路径
        if single_sku:
            logger.info(f"正在保存单个 SKU: {single_sku} ...")
            success, png_data = self.pdf_mapper.extract_page_as_png(path, 1)
            if success:
                assert isinstance(png_data, bytes)
                ok, msg = self.sku_db.save(single_sku, png_data, 1, Path(path).name)
                logger.info(msg)
                if ok:
                    logger.info(f"✓ SKU '{single_sku}' 已成功保存到数据库")
                    self.pdf_mapper.sku_path = Path(path)
                    self.pdf_mapper.sku_map[single_sku] = [1]
            else:
                logger.error(f"错误：{png_data}")
            self._log_db_stats()
            return True

        # 批量解析
        if self.state.excel_data is not None:
            compound_info = self.state.excel_data.get_all_compound_sku_info()
            logger.info(f"正在加载 SKU PDF: {path}...")
            msg = self.pdf_mapper.parse_sku(path, compound_info)
            logger.info(msg)
        else:
            logger.info("正在加载 SKU PDF（无 Excel 验证）...")
            logger.info("提示：将尝试从 PDF 中自动解析并保存所有页面")
            msg = self.pdf_mapper.parse_sku_all(path)
            logger.info(msg)

        # 保存到数据库
        self._save_all_skus_to_db()
        self._log_db_stats()
        return True

    def _save_all_skus_to_db(self) -> None:
        """将当前 PDF 中所有 SKU 页面保存到数据库。

        策略：复合键优先，跳过存在复合键变体的纯 SKU（避免回退到
        歧义条目——纯 SKU 对应多个页面时，pages[0] 不可靠）。
        """
        if not self.pdf_mapper.sku_path:
            return

        # 收集所有拥有复合键变体的 SKU（这些 SKU 有多个标识符版本）
        skus_with_compounds: set[str] = set()
        for key in self.pdf_mapper.sku_map:
            if "|||" in key:
                skus_with_compounds.add(key.split("|||")[0])

        logger.info("正在保存 SKU 到数据库...")
        if skus_with_compounds:
            logger.info(
                f"检测到 {len(skus_with_compounds)} 个 SKU 含有标识符变体"
                f"（{', '.join(sorted(skus_with_compounds)[:5])}"
                f"{'...' if len(skus_with_compounds) > 5 else ''}），"
                "将跳过纯 SKU 仅保存复合键"
            )

        saved_items = []
        skipped = 0
        for key, pages in self.pdf_mapper.sku_map.items():
            # 跳过存在复合键变体的纯 SKU（存储歧义，回退时可能取错页面）
            if "|||" not in key and key in skus_with_compounds:
                skipped += 1
                continue
            if pages:
                success, png_data = self.pdf_mapper.extract_page_as_png(
                    self.pdf_mapper.sku_path, pages[0]
                )
                if success:
                    assert isinstance(png_data, bytes)
                    saved_items.append((key, png_data, pages[0], self.pdf_mapper.sku_path.name))

        if saved_items:
            ok, msg = self.sku_db.save_batch(saved_items)
            logger.info(msg)
            saved = len(saved_items)
        else:
            saved = 0

        logger.info(f"已保存 {saved} 个 SKU 到数据库（跳过 {skipped} 个纯 SKU 歧义条目）")

    def _log_db_stats(self) -> None:
        stats = self.sku_db.stats()
        logger.info(f"数据库统计: {stats['total_skus']} 个 SKU, {stats['total_size_mb']} MB")

    # ─── FBA 批量打印 ─────────────────────────────────────────

    # ─── 独立 FBA 上传（无 Excel） ────────────────────────────────

    def upload_fba_standalone(self, path: str) -> bool:
        """独立上传 FBA PDF——不依赖 Excel，自动发现所有 FBA 号码。"""
        logger.info(f"正在独立加载 FBA PDF: {path}...")
        msg = self.pdf_mapper.parse_fba_standalone(path)
        logger.info(msg)
        return True

    # ─── FBA 直接打印 ─────────────────────────────────────────

    def direct_print_fba(
        self, fba_no: str, warehouse: str = "", copies: int = 1
    ) -> None:
        """根据 FBA 编号在已上传 PDF 中直接打印指定页面。

        不依赖 Excel 数据，仅需独立上传的 FBA PDF。
        每页按 copies 份数发送到打印机。

        Args:
            fba_no: FBA 编号（如 "FBA15GCK8TVJ"）。
            warehouse: FBA 仓库编码（叠加到标签顶端，可选）。
            copies: 每页打印份数（默认 1）。
        """
        fba_no = fba_no.strip().upper()
        if not fba_no:
            logger.warning("错误：FBA 号为空。")
            return

        if not self.pdf_mapper.fba_path:
            logger.warning("错误：请先上传 FBA PDF 文件。")
            return

        pages = self.pdf_mapper.get_fba_pages(fba_no)
        if not pages:
            logger.warning(f"错误：PDF 中未找到 FBA 编号 '{fba_no}'。")
            return

        logger.info(
            f"正在直接打印 FBA: {fba_no}, "
            f"页数: {len(pages)}, 份数: {copies}"
            f"{', 仓库: ' + warehouse if warehouse else ''}"
        )

        rendered = 0
        print_success = 0
        render_failures: list[str] = []
        print_failures: list[str] = []

        for page_num in pages:
            success, result = self.pdf_renderer.render_page_scaled(
                str(self.pdf_mapper.fba_path),
                page_num,
                content_scale=self.state.fba_scale,
            )
            if not success:
                render_failures.append(str(page_num))
                continue
            rendered += 1

            if warehouse:
                result = self.print_service.add_warehouse_header(result, warehouse)

            job = PrintJob(
                printer=self.state.fba_printer,
                orientation=self.state.fba_orientation,
                width_mm=self.state.fba_width,
                height_mm=self.state.fba_height,
            )
            for i in range(copies):
                ok, msg = self.print_service.print_image(result, job)
                if ok:
                    print_success += 1
                else:
                    print_failures.append(f"第{page_num}页第{i + 1}份")

        if render_failures:
            logger.warning(f"FBA 页面渲染失败 {len(render_failures)} 页")
        total_sheets = len(pages) * copies
        if print_success == total_sheets:
            logger.success(f"FBA 标签打印完成：{total_sheets} 张，全部成功")
        elif print_success > 0:
            logger.warning(f"FBA 标签打印完成：成功 {print_success}/{total_sheets} 张")


    def batch_print_fba(self, mark: str, auto_sku: bool = True) -> None:
        """批量打印指定箱唛的 FBA 标签 + 贴标顺序汇总。

        Args:
            mark: 箱唛。
            auto_sku: True 时打完 FBA 自动接 SKU（Enter 键）；False 时只打 FBA（按钮）。
        """

        mark = mark.strip()
        if not mark:
            logger.warning("错误：箱唛为空。")
            return

        if self.state.all_box_marks and mark in self.state.all_box_marks:
            self.state.current_mark_index = self.state.all_box_marks.index(mark)

        data = self.state.excel_data
        if data is None:
            logger.warning("错误：未加载 Excel 数据。")
            return

        info = data.get_fba_info(mark)
        if not info:
            logger.warning(f"错误：Excel 中未找到箱唛 '{mark}'。")
            return

        fba_no = str(info["FBA番号"])
        copies = int(info["份数"])
        warehouse = str(info.get("FBA仓库编码", ""))

        logger.info(f"正在打印 FBA: {fba_no}, 份数: {copies}")

        pages = self.pdf_mapper.get_fba_pages(fba_no)
        # 用箱数限制打印页数：当 PDF 页数超出箱数时，截取前 N 页
        # （避免单票指示中共享 FBA PDF 打印全部页面）
        box_count = int(info.get("箱数", 0)) if info.get("箱数") else 0
        if box_count > 0 and len(pages) > box_count:
            pages = pages[:box_count]
        if pages:
            logger.info(f"找到 {len(pages)} 页 FBA 标签")
            if copies <= 0:
                logger.warning(f"警告：箱唛 '{mark}' 的 '份数' 为 0，不打印 FBA 标签。")
            else:
                rendered = 0
                render_failures: list[str] = []
                print_success = 0
                print_failures: list[str] = []

                for page_num in pages:
                    success, result = self.pdf_renderer.render_page_scaled(
                        str(self.pdf_mapper.fba_path) if self.pdf_mapper.fba_path else "",
                        page_num,
                        content_scale=self.state.fba_scale,
                    )
                    if not success:
                        render_failures.append(str(page_num))
                        continue
                    rendered += 1

                    # 叠加仓库编码到标签顶端
                    if warehouse:
                        result = self.print_service.add_warehouse_header(
                            result,
                            warehouse,  # type: ignore[arg-type]
                        )

                    job = PrintJob(
                        printer=self.state.fba_printer,
                        orientation=self.state.fba_orientation,
                        width_mm=self.state.fba_width,
                        height_mm=self.state.fba_height,
                    )
                    for i in range(copies):
                        ok, msg = self.print_service.print_image(result, job)  # type: ignore[arg-type]
                        if ok:
                            print_success += 1
                        else:
                            print_failures.append(f"第{page_num}页第{i + 1}份")

                # 汇总
                if render_failures:
                    logger.warning(
                        f"FBA 页面渲染失败 {len(render_failures)} 页: "
                        f"{', '.join(render_failures[:5])}"
                        f"{'...' if len(render_failures) > 5 else ''}"
                    )
                total_sheets = len(pages) * copies
                if print_success == total_sheets:
                    logger.success(
                        f"FBA 标签打印完成：共 {len(pages)} 页 × {copies} 份 "
                        f"= {total_sheets} 张，全部发送成功"
                    )
                elif print_success > 0:
                    logger.warning(
                        f"FBA 标签打印完成：共 {len(pages)} 页 × {copies} 份 "
                        f"= {total_sheets} 张，成功 {print_success} 张，"
                        f"失败 {total_sheets - print_success} 张"
                    )
        elif str(fba_no).startswith("FBA"):
            logger.warning(
                f"提示：PDF 中未找到 FBA '{fba_no}'，跳过 FBA 标签打印，继续打印贴标顺序。"
            )
        else:
            logger.error(f"错误：PDF 中未找到 FBA '{fba_no}'。")
            return

        # 贴标顺序汇总
        sticker_info = data.get_sticker_orders_with_fba(mark)
        order_lines = [f"箱唛: {mark}"]
        if warehouse:
            order_lines.append(f"FBA仓库: {warehouse}")
        if sticker_info["all_match"]:
            order_lines.append("贴标顺序:")
            order_lines.extend(item["sticker"] for item in sticker_info["items"])
        else:
            import re
            order_lines.append("贴标  序列:")
            for item in sticker_info["items"]:
                fba_num = extract_tail_number(item["fba_seq"])
                order_lines.append(f'{item["sticker"]:>8}  {fba_num}')

        logger.info("正在打印贴标顺序汇总")
        img = self.print_service.generate_label_image(
            "\n".join(order_lines), self.state.fba_width, self.state.fba_height
        )
        job = PrintJob(
            printer=self.state.fba_printer,
            orientation=self.state.fba_orientation,
            width_mm=self.state.fba_width,
            height_mm=self.state.fba_height,
        )
        ok, msg = self.print_service.print_image(img, job)
        if not ok:
            logger.warning(msg)
        else:
            logger.success("FBA 标签和汇总表打印完成。")

        # ── 打印 FBA 备注（item no.）──
        item_no = str(info.get("item_no", "") or "").strip()
        if item_no:
            logger.info("正在打印 FBA 备注（item no.）")
            note_img = self.print_service.generate_label_image(
                "\n".join([f"箱唛: {mark}", f"FBA: {fba_no}", f"备注: {item_no}"]),
                self.state.fba_width,
                self.state.fba_height,
                font_size=160,
                min_font_size=120,
                auto_wrap=True,
                fixed_line_sizes={0: 120, 1: 120},
                highlight=["透明标签", "暂存"],
            )
            note_job = PrintJob(
                printer=self.state.fba_printer,
                orientation=self.state.fba_orientation,
                width_mm=self.state.fba_width,
                height_mm=self.state.fba_height,
            )
            note_ok, note_msg = self.print_service.print_image(note_img, note_job)
            if not note_ok:
                logger.warning(note_msg)
            else:
                logger.success("FBA 备注已打印。")
        else:
            logger.info("该箱唛无 item no. 备注，跳过备注打印。")

        # 自动 SKU 打印（仅 Enter 键触发时）
        if auto_sku:
            logger.info("FBA 打印数据已全部发送。等待接口处理 (2秒)...")
            time.sleep(2)
            logger.info(f">>> 自动开始打印箱唛 '{mark}' 的 SKU 标签...")
            self.batch_print_sku(mark)

    # ─── SKU 批量打印 ─────────────────────────────────────────

    def batch_print_sku(self, mark: str) -> None:
        """批量打印指定箱唛的所有 SKU 标签。"""
        mark = mark.strip()
        if not mark:
            logger.warning("错误：箱唛为空。")
            return

        if self.state.all_box_marks and mark in self.state.all_box_marks:
            self.state.current_mark_index = self.state.all_box_marks.index(mark)

        data = self.state.excel_data
        if data is None:
            logger.warning("错误：未加载 Excel 数据。")
            return

        skus = data.get_skus_for_mark(mark)
        if not skus:
            logger.info(f"提示：箱唛 '{mark}' 没有需要打印的 SKU 标签。")
            return

        logger.info(f"找到 {len(skus)} 个 SKU (箱唛 '{mark}')。开始打印...")

        # ── 每个 SKU 打印完后都跟一次贴标顺序 ──
        # 合并单元格兼容：当贴标顺序为空时，沿用上一个非空值
        last_sticker_order = ""

        for item in skus:
            compound_key = item.get("复合键", str(item["SKU"]))
            sku = str(item["SKU"])
            qty = int(item["SKU数量"])
            sticker_order = str(item.get("贴标顺序", "")).strip()
            if not sticker_order:
                sticker_order = last_sticker_order
            else:
                last_sticker_order = sticker_order

            pil_image = self._load_sku_image(compound_key, plain_sku=sku)
            if pil_image is None:
                logger.warning(f"警告：数据库和当前 PDF 中均未找到 SKU '{compound_key}'。跳过。")
                continue

            # 打印 SKU 标签
            logger.info(f"正在打印 SKU: {compound_key} x {qty}")
            job = PrintJob(
                printer=self.state.sku_printer,
                orientation=self.state.sku_orientation,
                width_mm=self.state.sku_width,
                height_mm=self.state.sku_height,
            )
            for _ in range(qty):
                ok, msg = self.print_service.print_image(pil_image, job)
                if not ok:
                    logger.warning(msg)
                    return

            # 打印贴标顺序（每个 SKU 后都跟一次，含数量+标识）
            if sticker_order:
                logger.info(f"正在打印 SKU 顺序: {sticker_order}")
                # 构建含 SKU 总数和对应标识的标签文本
                label_lines = [str(sticker_order)]
                label_lines.append(f"数量: {qty}")
                raw_id = str(item.get("对应SKU标识", "")).strip()
                if raw_id:
                    label_lines.append(f"标识: {raw_id}")
                label_text = "\n".join(label_lines)
                label_img = self.print_service.generate_label_image(
                    label_text, self.state.sku_width, self.state.sku_height
                )
                ok, msg = self.print_service.print_image(label_img, job)
                if not ok:
                    logger.warning(msg)
                    return

        logger.success("SKU 批量打印完成。")

    # ─── 单个 SKU 打印 ────────────────────────────────────────

    def single_print_sku(self, sku: str, qty: int) -> None:
        """打印单个 SKU 指定数量。

        支持复合键：如果传入的 sku 包含 "|||" 则视为复合键；
        否则同时尝试复合键回退查找（纯 SKU 也可能匹配到复合键条目）。
        """
        if not sku:
            logger.warning("错误：缺少 SKU。")
            return

        pil_image = self._load_sku_image(sku, plain_sku=sku)
        if pil_image is None:
            logger.error(f"错误：数据库和当前 PDF 中均未找到 SKU '{sku}'。")
            return

        logger.info(f"正在打印单个 SKU: {sku} x {qty}")
        job = PrintJob(
            printer=self.state.sku_printer,
            orientation=self.state.sku_orientation,
            width_mm=self.state.sku_width,
            height_mm=self.state.sku_height,
        )
        for _ in range(qty):
            ok, msg = self.print_service.print_image(pil_image, job)
            if not ok:
                logger.warning(msg)
                return
        logger.success("单个打印完成。")

    # ─── 内部 ──────────────────────────────────────────────────

    def _load_sku_image(self, compound_key: str, plain_sku: str = "") -> Image.Image | None:
        """从数据库或当前 PDF 加载 SKU 图片。

        查找策略：
          1. 数据库：仅查复合键（精确匹配，不回退歧义纯 SKU）
          2. 当前 PDF：按复合键渲染精确页面

        注意：不回退数据库中的纯 SKU，因为存在多个标识符变体时
        纯 SKU 条目可能对应错误页面。

        Args:
            compound_key: 复合键（如 "SKU|||IDENTIFIER"）。
            plain_sku: 纯 SKU（仅用于 PDF 回退渲染）。
        """
        # 1. 数据库：只查复合键，不回退纯 SKU（避免歧义）
        if self.sku_db.exists(compound_key):
            logger.info(f"从数据库加载 SKU: {compound_key}")
            png_data, _ = self.sku_db.get(compound_key)
            if png_data:
                try:
                    return Image.open(io.BytesIO(png_data))
                except OSError as e:
                    logger.warning(f"从数据库解析 SKU '{compound_key}' 图像失败: {e}")

        # 2. 当前 PDF：复合键优先，回退纯 SKU
        pages = self.pdf_mapper.get_sku_pages(compound_key)
        if not pages and plain_sku:
            pages = self.pdf_mapper.get_sku_pages(plain_sku)
        if pages and self.pdf_mapper.sku_path:
            lookup_key = compound_key if self.pdf_mapper.get_sku_pages(compound_key) else plain_sku
            logger.info(f"正在从当前 PDF 渲染 SKU: {lookup_key}...")
            success, result = self.pdf_renderer.render_page(
                str(self.pdf_mapper.sku_path), pages[0]
            )
            if success:
                assert isinstance(result, Image.Image)
                return result
            logger.warning(f"SKU '{lookup_key}' 页面渲染失败: {result}")

        return None

    def get_next_box_mark(self, current_text: str) -> tuple[str, int, int]:
        """获取下一个箱唛（↓ 键循环）。"""
        marks = self.state.all_box_marks or []
        if not marks:
            return "", 0, 0

        if current_text and current_text in marks:
            idx = marks.index(current_text)
        else:
            idx = self.state.current_mark_index

        idx = (idx + 1) % len(marks)
        self.state.current_mark_index = idx
        return marks[idx], idx + 1, len(marks)
