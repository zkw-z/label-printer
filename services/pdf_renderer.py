"""PDF 渲染服务

使用 pypdfium2 将 PDF 页面渲染为 PIL Image
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from loguru import logger
from PIL import Image

from utils.image_utils import scale_image


class PdfRenderer:
    """PDF 页面 -> PIL Image 渲染器。"""

    DEFAULT_RENDER_SCALE: float = 4.16

    def render_page(self, pdf_path, page_number, scale=None):
        render_scale = scale if scale is not None else self.DEFAULT_RENDER_SCALE
        try:
            with pdfium.PdfDocument(str(pdf_path)) as pdf:
                page = pdf.get_page(page_number - 1)
                try:
                    bitmap = page.render(scale=render_scale)
                    result = bitmap.to_pil()
                    return True, result
                finally:
                    page.close()
        except Exception as e:
            logger.exception("PDF render failed: {}", pdf_path)
            return False, f"PDF render error: {e}"

    def render_page_scaled(self, pdf_path, page_number, content_scale=1.0):
        success, result = self.render_page(pdf_path, page_number)
        if not success:
            return success, result
        assert isinstance(result, Image.Image)
        if content_scale < 1.0:
            result = scale_image(result, content_scale)
        return True, result


