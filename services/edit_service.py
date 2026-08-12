# -*- coding: utf-8 -*-
"""PDF 编辑服务

集成 pdf-merge-trim（FBA 合并裁剪）和 fnsku-extractor（SKU 提取标签生成）。
在后台线程中执行，通过 loguru 实时输出进度。
"""

from __future__ import annotations

import gc
import os
import sys
import time
import traceback
from pathlib import Path

from loguru import logger

from constants.label_constants import TRANSPARENT_KEYWORDS

# ── 脚本路径注册 ──────────────────────────────────────────────

_SERVICE_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SERVICE_DIR.parent

if getattr(sys, "frozen", False):
    # PyInstaller 打包后，脚本在 sys._MEIPASS 下
    _BASE = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    _BASE = _PROJECT_DIR

_MT_SCRIPT = str(_BASE / "pdf-merge-trim" / "scripts")
_FE_SCRIPT = str(_BASE / "fnsku-extractor" / "scripts")

for _p in [_MT_SCRIPT, _FE_SCRIPT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── FBA 编辑（merge_trim）─────────────────────────────────────


def run_fba_edit(source_dir: str) -> None:
    """执行 PDF 合并裁剪：筛选含 "FBA" 的 PDF，裁剪白边，统一 100×100mm 合并。

    Args:
        source_dir: PDF 源目录（递归搜索子目录）。
    """
    from merge_trim import (
        _HAVE_PIKEPDF,
        _extract_fba_number,
        find_pdf_files,
        merge_with_fitz,
        merge_with_pikepdf,
        process_file,
    )

    source_dir = os.path.abspath(source_dir)
    if not os.path.isdir(source_dir):
        logger.error(f"错误：目录不存在 - {source_dir}")
        return

    keyword = "FBA"
    target_w_mm, target_h_mm = 100, 100
    dpi, threshold = 150, 240
    margin_pct = 0.01
    max_size_mb = 200
    no_trim = False
    add_fba_text = True  # 对纯图片页面添加隐藏 FBA 文字（可选中复制）
    preserve_native = True  # 已是 100×100 的成品页原样保留（不裁剪），防止位置偏移

    MM_TO_PT = 72 / 25.4
    target_w = target_w_mm * MM_TO_PT
    target_h = target_h_mm * MM_TO_PT

    output_pdf = os.path.join(
        source_dir,
        f"{keyword}_{int(target_w_mm)}x{int(target_h_mm)}mm.pdf",
    )

    logger.info("=" * 50)
    logger.info("  FBA 编辑 — 智能合并与白边裁剪")
    logger.info("=" * 50)
    logger.info(f"源目录  : {source_dir}")
    logger.info(f"关键词  : {keyword}")
    logger.info(f"目标尺寸: {target_w_mm}x{target_h_mm} mm")
    logger.info(f"裁白边  : {'是' if not no_trim else '否'}")
    logger.info(f"原生100×100: {'原样保留（不裁剪）' if preserve_native else '仍按白边裁剪（旧行为）'}")
    logger.info(f"FBA 文字: {'自动添加（图片页）' if add_fba_text else '禁用'}")
    logger.info(f"合并引擎: {'pikepdf' if _HAVE_PIKEPDF else 'fitz（pikepdf 未安装）'}")
    logger.info("")

    files = find_pdf_files(
        source_dir,
        keyword,
        max_size_mb=max_size_mb,
        exclude_filenames={os.path.basename(output_pdf)},
    )
    if not files:
        logger.warning("未找到任何符合条件的 PDF 文件。")
        return
    logger.info(f"找到 {len(files)} 个符合条件的 PDF")

    # Step 1: 逐文件处理
    logger.info("\n[1/3] 逐文件裁剪白边并调整尺寸...")
    processed_files = []
    total_pages, failed = 0, 0

    for i, fp in enumerate(files, 1):
        fname = os.path.basename(fp)
        t0 = time.time()
        try:
            fba_no = _extract_fba_number(fp) if add_fba_text else None
            tmp_path, page_count, was_modified = process_file(
                fp,
                target_w,
                target_h,
                no_trim=no_trim,
                preserve_native=preserve_native,
                dpi=dpi,
                threshold=threshold,
                margin_pct=margin_pct,
                add_fba_text=add_fba_text,
                fba_number=fba_no,
            )
            total_pages += page_count
            processed_files.append((tmp_path, was_modified))
            elapsed = time.time() - t0
            mode = "裁剪/缩放" if was_modified else "原样"
            logger.info(f"  [{i}/{len(files)}] {fname} — {page_count}页, {elapsed:.1f}s, {mode}")
        except Exception:
            logger.error(f"  [错误] {fname}: {traceback.format_exc()}")
            failed += 1
        gc.collect()

    # Step 2: 合并
    logger.info("\n[2/3] 合并所有处理后的文件...")
    try:
        if _HAVE_PIKEPDF:
            merge_with_pikepdf(processed_files, output_pdf)
        else:
            merge_with_fitz(processed_files, output_pdf)
    except Exception:
        logger.error(f"  [错误] 合并失败: {traceback.format_exc()}")
        for path, is_tmp in processed_files:
            if is_tmp:
                try:
                    os.remove(path)
                except OSError:
                    pass
        return

    # Step 3: 汇总
    final_size_kb = os.path.getsize(output_pdf) // 1024
    logger.info("\n[3/3] 完成！")
    logger.info(f"  处理文件: {len(files)} 个（失败 {failed} 个）")
    logger.info(f"  总页数  : {total_pages} 页")
    logger.info(f"  文件大小: {final_size_kb} KB")
    logger.info(f"  输出文件: {output_pdf}")


# ── SKU 编辑（fnsku_extractor）───────────────────────────────


def _find_transparent_label_files(source_dir: str) -> set[str]:
    """扫描源目录中文件名含'透明标签/透明签/透明'的文件，返回所在目录集合。"""
    dirs: set[str] = set()
    for root, _dirs, fns in os.walk(source_dir):
        for fn in fns:
            if any(kw in fn for kw in TRANSPARENT_KEYWORDS):
                dirs.add(os.path.abspath(root))
    return dirs


def _scan_excel_for_transparent(source_dir: str) -> dict[str, list[str]]:
    """扫描源目录中 Excel 文件（.xlsx/.xls）内容是否含透明标签关键词。

    返回: {文件路径: [匹配的Sheet名称列表]}
    """
    matches: dict[str, list[str]] = {}
    for root, _dirs, fns in os.walk(source_dir):
        for fn in fns:
            lower_fn = fn.lower()
            if not (lower_fn.endswith(".xlsx") or lower_fn.endswith(".xls")):
                continue
            fp = os.path.join(root, fn)
            # 跳过临时文件和脚本输出
            if fn.startswith("~$") or "fnsku_result" in fn:
                continue
            try:
                matched_sheets = _scan_single_excel(fp, TRANSPARENT_KEYWORDS)
                if matched_sheets:
                    matches[fp] = matched_sheets
            except Exception:
                pass  # 损坏/加密文件静默跳过
    return matches


def _scan_single_excel(fp: str, keywords: tuple[str, ...]) -> list[str]:
    """扫描单个 Excel 文件所有 sheet 的所有 cell，检查是否含关键词。

    返回: [匹配的Sheet名称列表]
    """
    import re

    matched_sheets: list[str] = []
    suffix = os.path.splitext(fp)[1].lower()

    if suffix == ".xls":
        import xlrd

        wb = xlrd.open_workbook(fp)
        for sheet in wb.sheets():
            for r in range(sheet.nrows):
                for c in range(sheet.ncols):
                    val = str(sheet.cell_value(r, c))
                    if any(kw in val for kw in keywords):
                        matched_sheets.append(sheet.name)
                        break
                else:
                    continue
                break  # 该 sheet 已匹配，跳到下一个 sheet
        return matched_sheets

    # .xlsx: openpyxl read_only 模式
    import openpyxl

    wb = openpyxl.load_workbook(fp, read_only=True, data_only=True)
    for sheet in wb:
        for row in sheet.iter_rows(values_only=True):
            for val in row:
                if val is None:
                    continue
                if any(kw in str(val) for kw in keywords):
                    matched_sheets.append(sheet.title)
                    break
            else:
                continue
            break  # 该 sheet 已匹配，跳到下一个 sheet
    wb.close()
    return matched_sheets


def _detect_2d_barcode_in_pdf(pdf_path: str) -> tuple[bool, list[str]]:
    """检测 PDF 是否为透明标签（通过页码特征判定）。

    透明标签 PDF 每页有数字序号（首页文本首行为纯数字 "1"，且 1 ≤ 总页数），
    这是 Amazon Transparency 标签在排版上的固有特征。普通 FNSKU 标签首页首行是
    SKU 文本（如 "X001TEST"），不存在此特征。

    Args:
        pdf_path: PDF 文件路径。

    Returns:
        (detected, [命中原因]) — 如 (True, ['页码特征: 首页=1/总页数=60'])
    """
    reasons: list[str] = []
    try:
        import pypdfium2 as pdfium

        with pdfium.PdfDocument(pdf_path) as pdf:
            total = len(pdf)
            if total == 0:
                return False, []

            page = pdf[0]
            textpage = page.get_textpage()
            try:
                text = textpage.get_text_range().strip()
            finally:
                textpage.close()
            page.close()

        # ── 页码检测：透明标签每页有序号（可能在首行或末行，取决于排版）──
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if lines and total >= 3:
            # 首行和末行都可能包含页码（页眉/页脚位置不确定）
            candidates = []
            if lines[0].isdigit():
                candidates.append(int(lines[0]))
            if len(lines) > 1 and lines[-1].isdigit():
                candidates.append(int(lines[-1]))
            for page_num in candidates:
                if 1 <= page_num <= total:
                    reasons.append(f"页码特征: 首页={page_num}/总页数={total}")
                    return True, reasons

        # ── 兜底: 文本关键词 "Transparency" ──
        if "transparency" in text.lower():
            reasons.append("文本含 'Transparency'")

        return bool(reasons), reasons

    except ImportError:
        return False, []
    except Exception:
        return False, []


def run_sku_edit(source_dir: str) -> None:
    """执行 FNSKU 提取 + 条形码标签生成。

    逐页处理 PDF：文本页提取 FNSKU+描述，图片页转 PNG+OCR。
    输出 .xlsx 和 50×30mm 条形码标签 PDF。

    Args:
        source_dir: PDF 源目录（递归搜索子目录）。
    """
    from extract_fnsku import _save_xlsx, find_sku_files, process_pdf

    source_dir = os.path.abspath(source_dir)
    if not os.path.isdir(source_dir):
        logger.error(f"错误：目录不存在 - {source_dir}")
        return

    dpi = 4
    output_xlsx = os.path.join(source_dir, "fnsku_result.xlsx")
    png_dir = os.path.join(source_dir, "ocr_images")

    os.makedirs(png_dir, exist_ok=True)

    logger.info("=" * 50)
    logger.info("  SKU 编辑 — FNSKU 提取与标签生成")
    logger.info("=" * 50)
    logger.info(f"源目录  : {source_dir}")
    logger.info(f"输出 xlsx: {output_xlsx}")
    logger.info("")

    files = find_sku_files(source_dir)
    logger.info(f"找到 {len(files)} 个符合条件的 PDF")

    # 扫描透明标签文件（文件名 + Excel 内容 + 二维码）
    transparent_dirs = _find_transparent_label_files(source_dir)
    transparent_excels = _scan_excel_for_transparent(source_dir)
    # 二维码检测结果（第三道防线——弥补纯文本关键词检测的盲区）
    qr_detected_files: list[str] = []

    if not files:
        logger.warning("未找到符合条件的 PDF（文件名需包含 X00 或 B0 且不含 FBA）。")
        return

    # Step 1: 逐文件逐页处理
    logger.info("\n[1/4] 逐页处理（文本 → FNSKU / 图片 → PNG）...")
    all_results = []
    total_png, total_errors = 0, 0
    skipped_by_qr = 0  # 因二维码检测而跳过的文件数

    for i, fp in enumerate(files, 1):
        fname = os.path.basename(fp)
        # 二维码检测（第三道防线——透明标签通常带有二维码，检测到则跳过 SKU 整理）
        has_2d, barcode_types = _detect_2d_barcode_in_pdf(fp)
        if has_2d:
            qr_detected_files.append(
                f"{fp}  →  检测到: {', '.join(barcode_types)}"
            )
            logger.warning(
                f"  🚫 透明标签拦截: {fname} — {'; '.join(barcode_types)}，已跳过 SKU 整理"
            )
            skipped_by_qr += 1
            continue
        results, pngs, errors = process_pdf(fp, png_dir, i, dpi)
        all_results.extend(results)
        total_png += pngs
        total_errors += errors

        parts = []
        if results:
            parts.append(f"FNSKU {len(results)}条")
        if pngs:
            parts.append(f"PNG {pngs}页")
        if errors:
            parts.append(f"错误 {errors}处")
        msg = " | ".join(parts) if parts else ""
        logger.info(
            f"  [{i}/{len(files)}] {fname} → {msg}" if msg else f"  [{i}/{len(files)}] {fname}"
        )

    # Step 2: 去重
    logger.info("\n[2/4] FNSKU 去重...")
    seen: set[tuple[str, str]] = set()
    unique_results = []
    for fnsku, desc in all_results:
        key = (fnsku, desc)
        if key not in seen:
            seen.add(key)
            unique_results.append((fnsku, desc))
    logger.info(f"  原始 {len(all_results)} 条 → 去重后 {len(unique_results)} 条")

    # Step 3: 保存 xlsx
    logger.info("\n[3/4] 保存 xlsx...")
    os.makedirs(os.path.dirname(output_xlsx), exist_ok=True)
    _save_xlsx(output_xlsx, unique_results)
    xlsx_kb = os.path.getsize(output_xlsx) // 1024
    logger.info(f"  已保存: {output_xlsx} ({xlsx_kb} KB)")

    # Step 4: 生成条形码标签
    logger.info("\n[4/4] 生成 50×30mm 条形码标签 PDF...")
    label_pdf = None
    try:
        from generate_labels import generate_labels as gen_labels

        result = gen_labels(output_xlsx)
        if result:
            label_pdf, label_count = result
            label_kb = os.path.getsize(label_pdf) // 1024
            logger.info(f"  已生成: {label_pdf} ({label_count} 个标签, {label_kb} KB)")
        else:
            logger.warning("  [警告] 未生成任何标签")
    except ImportError as e:
        err_msg = str(e)
        logger.warning(f"  [提示] reportlab 条码模块导入失败，跳过标签生成: {err_msg}")
        logger.warning("  [修复] 请确保 reportlab 完整安装: pip install --force-reinstall reportlab")
    except Exception:
        logger.error(f"  [错误] 标签生成失败: {traceback.format_exc()}")

    # 汇总
    logger.info("\n" + "=" * 50)
    logger.info("  处理完成")
    if skipped_by_qr:
        logger.warning(f"  ⚠️ 二维码拦截: 跳过 {skipped_by_qr} 个含二维码的文件")
    logger.info(f"  PDF 文件 : {len(files)} 个（实际处理 {len(files) - skipped_by_qr} 个）")
    logger.info(f"  FNSKU    : {len(all_results)} 条（去重后 {len(unique_results)} 条）")
    logger.info(f"  图片 PNG : {total_png} 张")
    logger.info(f"  输出 xlsx: {output_xlsx}")
    if label_pdf:
        logger.info(f"  标签 PDF : {label_pdf}")
    if total_errors:
        logger.warning(f"  错误     : {total_errors} 处")
    if transparent_dirs or transparent_excels or qr_detected_files:
        parts = []
        if transparent_dirs:
            parts.append("▸ 文件名匹配（目录）：\n" + "\n".join(f"    • {d}" for d in sorted(transparent_dirs)))
        if transparent_excels:
            excel_lines = []
            for fp, sheets in sorted(transparent_excels.items()):
                excel_lines.append(f"    • {fp}  →  [{', '.join(sheets)}]")
            parts.append("▸ Excel 内容匹配：\n" + "\n".join(excel_lines))
        if qr_detected_files:
            parts.append(
                "▸ 透明标签特征检测（文本/图片模式/二维码）：\n"
                + "\n".join(f"    • {f}" for f in qr_detected_files)
            )
        transparent_msg = (
            "检测到透明标签相关文件，请核对：\n\n" + "\n\n".join(parts)
        )
        logger.error("⚠️ 透明标签提醒：\n" + transparent_msg.replace("\n", "\n    "))
        import tkinter.messagebox as tkmb
        tkmb.showwarning("⚠️ 透明标签提醒", transparent_msg)
    logger.info("=" * 50)
