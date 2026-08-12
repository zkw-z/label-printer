# -*- coding: utf-8 -*-
"""pdf-merge-trim 页面处理 单元测试

覆盖方案 C：已是目标尺寸（100×100）的页面视为成品，默认原样保留（不重排），
避免打印内容偏移；越出页面的出血/裁切标记内容同样原样保留（打印时按页边裁切）；
大页面 + CropBox 网格切块（如 A4 上切出 105×99 标签格）按格子区域等比缩放居中，
内容相对格子位置不变、不放大；仅普通尺寸不符的页面才裁剪居中；
旧行为（带白边仍裁剪）可通过 preserve_native=False 保留。
"""

from __future__ import annotations

import os
import sys

import fitz
import pytest

_MT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "pdf-merge-trim", "scripts")
)
if _MT_DIR not in sys.path:
    sys.path.insert(0, _MT_DIR)

from merge_trim import detect_content_bbox, find_pdf_files, process_file  # noqa: E402

MM = 72 / 25.4
TARGET = 100 * MM


def _make_pdf(path: str, pages: list[tuple[float, float, str]]) -> None:
    doc = fitz.open()
    for w_mm, h_mm, kind in pages:
        page = doc.new_page(width=w_mm * MM, height=h_mm * MM)
        if kind == "imgonly_100":
            # 纯图形页（无文字层）：整页浅底 + 一个位于固定坐标的特征框
            page.draw_rect(
                fitz.Rect(0, 0, page.rect.width, page.rect.height),
                color=None, fill=(0.92, 0.92, 0.92),
            )
            page.draw_rect(fitz.Rect(20, 30, 80, 70), color=(0, 0, 0), width=2)
        elif kind == "text100":
            # 有文字层、内容占比 >= 90% 的 100×100 页
            page.draw_rect(
                fitz.Rect(2, 2, page.rect.width - 2, page.rect.height - 2),
                color=(0, 0, 0), width=1,
            )
            page.insert_text((40, 100), "FBA-TEXT-100", fontsize=12)
        elif kind == "bordered100":
            # 有明显白边（内容占比 ~62% < 90%）的 100×100 页
            page.draw_rect(
                fitz.Rect(30, 30, page.rect.width - 30, page.rect.height - 30),
                color=(0, 0, 0), width=2,
            )
            page.insert_text((40, 80), "FBA-BORDERED", fontsize=12)
    doc.save(path)
    doc.close()


class TestMergeTrimNativePreserved:
    """方案 B：已是目标尺寸的页面不被重排"""

    def test_image_only_100mm_copied_as_is(self, tmp_path):
        """100×100 纯图形页（需隐藏文字）→ 原样复制，特征框位置不变，隐藏 FBA 文字已添加"""
        src = str(tmp_path / "FBA15G7J3241-100.pdf")
        _make_pdf(src, [(100, 100, "imgonly_100")])
        out, pages, modified = process_file(
            src, TARGET, TARGET, add_fba_text=True, fba_number="FBA15G7J3241"
        )
        assert modified is True  # 因需添加隐藏 FBA 文字而输出新文件
        assert pages == 1
        doc = fitz.open(out)
        page = doc[0]
        try:
            assert abs(page.rect.width - TARGET) < 0.01
            assert abs(page.rect.height - TARGET) < 0.01
            rects = [r["rect"] for r in page.get_drawings() if r.get("rect")]
            assert any(
                abs(r.x0 - 20) < 0.01 and abs(r.y0 - 30) < 0.01
                and abs(r.x1 - 80) < 0.01 and abs(r.y1 - 70) < 0.01
                for r in rects
            ), "特征框位置被移动"
            assert "FBA15G7J3241" in page.get_text(), "隐藏 FBA 文字未添加"
        finally:
            doc.close()

    def test_mixed_pages(self, tmp_path):
        """100×100 纯图形页原样 + 120×120 页裁剪到 100×100"""
        src = str(tmp_path / "FBA99ABC1-mixed.pdf")
        _make_pdf(src, [(100, 100, "imgonly_100"), (120, 120, "bordered100")])
        out, pages, modified = process_file(
            src, TARGET, TARGET, add_fba_text=True, fba_number="FBA99ABC1"
        )
        assert modified is True
        assert pages == 2
        doc = fitz.open(out)
        try:
            assert all(
                abs(doc[i].rect.width - TARGET) < 0.01
                and abs(doc[i].rect.height - TARGET) < 0.01
                for i in range(doc.page_count)
            )
            assert "FBA99ABC1" in doc[0].get_text()  # 第 1 页隐藏文字
            assert "FBA-BORDERED" in doc[1].get_text()  # 第 2 页内容保留
        finally:
            doc.close()

    def test_text_page_as_is_no_reprocess(self, tmp_path):
        """有文字层且内容占比 >= 90% 的 100×100 页 → 整体原样返回，不生成临时文件"""
        src = str(tmp_path / "FBA77XYZ2-text100.pdf")
        _make_pdf(src, [(100, 100, "text100")])
        out, pages, modified = process_file(
            src, TARGET, TARGET, add_fba_text=True, fba_number="FBA77XYZ2"
        )
        assert modified is False
        assert pages == 1
        assert os.path.abspath(out) == os.path.abspath(src)

    def test_bordered_page_native_preserved(self, tmp_path):
        """100×100 但有明显白边的页（成品规格）→ 默认原样保留，不裁剪不重排"""
        src = str(tmp_path / "FBA12BORDER-100.pdf")
        _make_pdf(src, [(100, 100, "bordered100")])
        out, pages, modified = process_file(
            src, TARGET, TARGET, add_fba_text=True, fba_number="FBA12BORDER"
        )
        assert modified is False
        assert pages == 1
        assert os.path.abspath(out) == os.path.abspath(src)

    def test_bordered_page_trimmed_when_preserve_native_false(self, tmp_path):
        """preserve_native=False（旧行为）时，带白边的 100×100 页仍裁剪放大铺满"""
        src = str(tmp_path / "FBA12BORDER-100.pdf")
        _make_pdf(src, [(100, 100, "bordered100")])
        out, pages, modified = process_file(
            src, TARGET, TARGET, add_fba_text=True, fba_number="FBA12BORDER",
            preserve_native=False,
        )
        assert modified is True
        doc = fitz.open(out)
        try:
            bbox = detect_content_bbox(doc[0])
            ratio = (bbox.width * bbox.height) / (doc[0].rect.width * doc[0].rect.height)
            assert ratio > 0.98
        finally:
            doc.close()

    def test_native_page_overflow_preserved(self, tmp_path):
        """100×100 页内容越出页面（出血/裁切标记）→ 原样保留，不缩放不重排"""
        src = str(tmp_path / "FBA88OVER-100.pdf")
        doc = fitz.open()
        page = doc.new_page(width=TARGET, height=TARGET)
        page.draw_rect(fitz.Rect(-16.54, -16.54, 300, 300), color=(0, 0, 0), width=2)
        doc.save(src)
        doc.close()
        out, pages, modified = process_file(src, TARGET, TARGET)
        assert modified is False
        assert pages == 1
        assert os.path.abspath(out) == os.path.abspath(src)

    def test_merged_output_excluded_from_search(self, tmp_path):
        """合并输出文件（如 FBA_100x100mm.pdf）不会被二次处理"""
        src = str(tmp_path / "FBA_100x100mm.pdf")
        _make_pdf(src, [(100, 100, "text100")])
        other = str(tmp_path / "FBA15G7J3241-100.pdf")
        _make_pdf(other, [(100, 100, "text100")])
        files = find_pdf_files(
            str(tmp_path), "FBA",
            exclude_filenames={os.path.basename(src)},
        )
        assert [os.path.basename(f) for f in files] == ["FBA15G7J3241-100.pdf"]

    def test_cropbox_grid_offset_clip(self, tmp_path):
        """CropBox ?????A4 ????/???? ????????????????"""
        src = str(tmp_path / "FBA44GRID-offset.pdf")
        doc = fitz.open()
        page = doc.new_page(width=595.27, height=841.68)
        page.set_cropbox(fitz.Rect(297.635, 561.12, 595.27, 840.68))
        # PyMuPDF ?????????????? CropBox ???
        page.draw_rect(fitz.Rect(30, 30, 200, 200), color=(0, 0, 0), width=2)
        page.insert_text((60, 100), "FBA-GRID-OFFSET", fontsize=12)
        doc.save(src)
        doc.close()
        out, pages, modified = process_file(src, TARGET, TARGET)
        assert modified is True
        assert pages == 1
        src_doc = fitz.open(src)
        src_page = src_doc[0]
        bbox = detect_content_bbox(src_page, margin_pct=0.01, region=src_page.rect)
        scale = min(TARGET / bbox.width, TARGET / bbox.height)
        ox = (TARGET - bbox.width * scale) / 2
        oy = (TARGET - bbox.height * scale) / 2
        src_doc.close()
        doc = fitz.open(out)
        try:
            page = doc[0]
            assert abs(page.rect.width - TARGET) < 0.01
            assert abs(page.rect.height - TARGET) < 0.01
            out_bbox = detect_content_bbox(page, margin_pct=0.0)
            # ???? (30,30,200,200)?????????????????????
            exp = fitz.Rect(
                ox + (30 - bbox.x0) * scale, oy + (30 - bbox.y0) * scale,
                ox + (200 - bbox.x0) * scale, oy + (200 - bbox.y0) * scale,
            )
            assert abs(out_bbox.x0 - exp.x0) < 1.0
            assert abs(out_bbox.y0 - exp.y0) < 1.0
            assert abs(out_bbox.x1 - exp.x1) < 1.0
            assert abs(out_bbox.y1 - exp.y1) < 1.0
        finally:
            doc.close()

    def test_cropbox_grid_scaled_to_target(self, tmp_path):
        """A4 ??? + CropBox ???105?99 ???? ????????????????????"""
        src = str(tmp_path / "FBA33GRID-105x99.pdf")
        doc = fitz.open()
        page = doc.new_page(width=595.27, height=841.68)
        page.set_cropbox(fitz.Rect(0, 0, 297.635, 280.56))
        page.draw_rect(fitz.Rect(30, 30, 200, 200), color=(0, 0, 0), width=2)
        page.insert_text((60, 100), "FBA-GRID", fontsize=12)
        doc.save(src)
        doc.close()
        out, pages, modified = process_file(src, TARGET, TARGET)
        assert modified is True
        assert pages == 1
        src_doc = fitz.open(src)
        src_page = src_doc[0]
        bbox = detect_content_bbox(src_page, margin_pct=0.01, region=src_page.rect)
        scale = min(TARGET / bbox.width, TARGET / bbox.height)
        ox = (TARGET - bbox.width * scale) / 2
        oy = (TARGET - bbox.height * scale) / 2
        src_doc.close()
        doc = fitz.open(out)
        try:
            page = doc[0]
            assert abs(page.rect.width - TARGET) < 0.01
            assert abs(page.rect.height - TARGET) < 0.01
            out_bbox = detect_content_bbox(page, margin_pct=0.0)
            exp = fitz.Rect(
                ox + (30 - bbox.x0) * scale, oy + (30 - bbox.y0) * scale,
                ox + (200 - bbox.x0) * scale, oy + (200 - bbox.y0) * scale,
            )
            assert abs(out_bbox.x0 - exp.x0) < 1.0
            assert abs(out_bbox.y0 - exp.y0) < 1.0
            assert abs(out_bbox.x1 - exp.x1) < 1.0
            assert abs(out_bbox.y1 - exp.y1) < 1.0
        finally:
            doc.close()
