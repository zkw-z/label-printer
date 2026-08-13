# -*- coding: utf-8 -*-
"""FNSKU 提取回归测试。

修复：PDF 文本层 FNSKU 中间被插入空格（如 "X00 1C40HN3"）时提取不到，
导致 SKU 编辑漏识别整个文件。
"""

from __future__ import annotations

import os
import sys

import fitz

_FE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "fnsku-extractor", "scripts")
)
if _FE_DIR not in sys.path:
    sys.path.insert(0, _FE_DIR)

from extract_fnsku import _extract_fnsku_from_ocr, process_pdf  # noqa: E402


def _make_label_pdf(path, sku_text: str) -> None:
    """生成单页标签 PDF（文本层可人为插入空格）。"""
    doc = fitz.open()
    page = doc.new_page(width=283.5, height=170.1)  # 约 100x60mm
    page.insert_text((30, 50), sku_text, fontsize=14)
    page.insert_text((30, 80), "NEW-TATIU PRODUCT (WHITE)", fontsize=10)
    page.insert_text((30, 100), "TU120-W Made in China", fontsize=10)
    doc.save(str(path))
    doc.close()


class TestExtractFnsku:
    def test_fnsku_with_space_in_text_layer(self, tmp_path):
        """文本层 'X00 1C40HN3' 应提取为 X001C40HN3。"""
        pdf = tmp_path / "X001C40HN3+内标80个.pdf"
        _make_label_pdf(pdf, "X00 1C40HN3")
        png_dir = tmp_path / "png"
        png_dir.mkdir()
        results, pngs, errors = process_pdf(str(pdf), str(png_dir), 1, 2)
        assert errors == 0
        fnskus = [f for f, _ in results]
        assert "X001C40HN3" in fnskus

    def test_fnsku_without_space_still_works(self, tmp_path):
        """无空格文本不受影响。"""
        pdf = tmp_path / "X001C41I2H+内标.pdf"
        _make_label_pdf(pdf, "X001C41I2H")
        png_dir = tmp_path / "png2"
        png_dir.mkdir()
        results, _, _ = process_pdf(str(pdf), str(png_dir), 1, 2)
        assert "X001C41I2H" in [f for f, _ in results]

    def test_ocr_loose_match(self):
        """OCR 文本中的空格也应容错。"""
        assert _extract_fnsku_from_ocr("X00 1C40HN3\nsome text") == "X001C40HN3"
        assert _extract_fnsku_from_ocr("X001C41I2H") == "X001C41I2H"
