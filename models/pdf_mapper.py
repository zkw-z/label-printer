"""PDF 页面映射器

解析 FBA/SKU PDF 文件，将页面文字与 Excel 提取的编号进行匹配，
建立 {编号: [页码]} 的映射关系。同时支持将指定页面渲染为 PNG 供打印使用。
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pypdfium2 as pdfium


class PDFMapper:
    """管理 FBA PDF 和 SKU PDF 的页面映射。"""

    def __init__(self) -> None:
        self.fba_map: dict[str, list[int]] = {}
        self.sku_map: dict[str, list[int]] = {}
        self.fba_path: Path | None = None
        self.sku_path: Path | None = None

    # ─── FBA PDF ──────────────────────────────────────────────

    def parse_fba(self, file_path: str | Path, expected_fbas: list[str]) -> str:
        """解析 FBA PDF，建立 FBA番号 → 页码 的映射。"""
        file_path = Path(file_path)
        if not file_path.exists():
            return "文件未找到。"

        self.fba_path = file_path
        self.fba_map.clear()
        missing = set(expected_fbas)

        try:
            with pdfium.PdfDocument(str(file_path)) as pdf:
                total_pages = len(pdf)
                for idx, page in enumerate(pdf):
                    text = self._page_text(page)
                    if not text:
                        continue
                    for fba in expected_fbas:
                        if str(fba) in text:
                            self.fba_map.setdefault(fba, []).append(idx + 1)
                            missing.discard(fba)



            if missing:
                return "FBA PDF 已加载。未匹配或缺失 FBA: " + ", ".join(map(str, missing))
            return "FBA PDF 加载成功。所有 FBA 已找到。"

        except Exception as e:
            return f"解析 FBA PDF 出错: {e}"

    def parse_fba_standalone(self, file_path: str | Path) -> str:
        """独立解析 FBA PDF（不依赖 Excel），自动发现所有 FBA 号码。

        FBA 格式：FBA + 10 位大写字母/数字（如 FBA15GC09XVM）。
        仅在原始文本中精确匹配，不合并空白，避免粘连后缀。
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return "文件未找到。"

        self.fba_path = file_path
        self.fba_map.clear()
        discovered: set[str] = set()

        FBA_RE = re.compile(r"FBA[A-Z0-9]{9}")

        try:
            with pdfium.PdfDocument(str(file_path)) as pdf:
                total_pages = len(pdf)
                for idx, page in enumerate(pdf):
                    raw = self._page_text(page)
                    if not raw:
                        continue
                    # 确保同一页同一 FBA 只加一次（一页可能有多个标签）
                    page_fbas = set()
                    for match in FBA_RE.finditer(raw):
                        fba_no = match.group(0)
                        page_fbas.add(fba_no)
                        discovered.add(fba_no)
                    for fba_no in page_fbas:
                        self.fba_map.setdefault(fba_no, []).append(idx + 1)


            if discovered:
                fba_list = ", ".join(sorted(discovered)[:10])
                more = f" ... 等共 {len(discovered)} 个" if len(discovered) > 10 else ""
                return f"FBA PDF 独立加载成功。发现: {fba_list}{more}"
            return "FBA PDF 独立加载成功。未自动发现 FBA 编号。"
        except Exception as e:
            return f"解析 FBA PDF 出错: {e}"

    def get_fba_pages(self, fba: str) -> list[int]:
        """返回指定 FBA番号 对应的页码列表。"""
        return self.fba_map.get(fba, [])

    # ─── SKU PDF ──────────────────────────────────────────────

    def parse_sku(
        self,
        file_path: str | Path,
        compound_info: list[dict[str, str]],
    ) -> str:
        """解析 SKU PDF，建立 SKU/复合键 → 页码 的映射。

        两层匹配：
          - 验证层：只按 SKU 检查是否存在（原有逻辑，报告 SKU 缺失）。
          - 打印层：当 identifier 非空时，页面必须同时包含 SKU 和
            identifier 才算精确匹配，存入复合键。这样打印时能区分
            同一 SKU 的不同标识。

        sku_map 同时存储纯 SKU（回退用）和复合键（精确匹配用）。

        Args:
            file_path: PDF 文件路径。
            compound_info: [{"sku", "identifier", "compound_key"}, ...]

        Returns:
            状态消息（仅按 SKU 层面报告缺失）。
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return "文件未找到。"

        self.sku_path = file_path
        self.sku_map.clear()

        # 唯 SKU 列表（验证层）
        unique_skus = sorted({info["sku"] for info in compound_info})
        missing_skus = set(unique_skus)

        try:
            with pdfium.PdfDocument(str(file_path)) as pdf:
                for idx, page in enumerate(pdf):
                    raw_text = self._page_text(page)
                    if not raw_text:
                        continue
                    page_num = idx + 1

                    # 紧凑文本（去空白），应对 PDF 内换行打断标识符字符串
                    text_flat = re.sub(r"\s+", "", raw_text)

                    # ── 验证层：记录所有匹配的 SKU ──
                    for sku in unique_skus:
                        if str(sku) in raw_text:
                            self.sku_map.setdefault(sku, []).append(page_num)
                            missing_skus.discard(sku)

                    # ── 打印层：带标识符的精确复合匹配（用紧凑文本）──
                    for info in compound_info:
                        identifier = info["identifier"]
                        if not identifier:
                            continue  # 无标识符时，纯 SKU 已足够
                        if info["sku"] in raw_text and str(identifier) in text_flat:
                            self.sku_map.setdefault(info["compound_key"], []).append(page_num)

            if missing_skus:
                return "SKU PDF 已加载。缺失 SKU: " + ", ".join(sorted(missing_skus))
            return "SKU PDF 加载成功。所有 SKU 已找到。"

        except Exception as e:
            return f"解析 SKU PDF 出错: {e}"

    def parse_sku_all(self, file_path: str | Path) -> str:
        """解析 SKU PDF 全部页面（无 Excel 验证时自动提取 SKU）。"""
        file_path = Path(file_path)
        if not file_path.exists():
            return "文件未找到。"

        self.sku_path = file_path
        self.sku_map.clear()

        try:
            with pdfium.PdfDocument(str(file_path)) as pdf:
                for idx, page in enumerate(pdf):
                    text = self._page_text(page)
                    sku = self._extract_sku_from_text(text) if text else None
                    if not sku:
                        sku = f"PAGE_{idx + 1}"
                    self.sku_map.setdefault(sku, []).append(idx + 1)

            return f"SKU PDF 加载成功。找到 {len(self.sku_map)} 个页面。"

        except Exception as e:
            return f"解析 SKU PDF 出错: {e}"

    def get_sku_pages(self, sku: str) -> list[int]:
        """返回指定 SKU 对应的页码列表。"""
        return self.sku_map.get(sku, [])

    # ─── 页面渲染 ─────────────────────────────────────────────

    @staticmethod
    def extract_page_as_png(file_path: str | Path, page_number: int) -> tuple[bool, bytes | str]:
        """将 PDF 指定页面渲染为 PNG 字节数据（用于数据库存储）。

        Args:
            file_path: PDF 文件路径。
            page_number: 1-based 页码。

        Returns:
            (True, png_bytes) 成功；(False, error_message) 失败。
        """
        file_path = Path(file_path)
        try:
            with pdfium.PdfDocument(str(file_path)) as pdf:
                page = pdf.get_page(page_number - 1)
                try:
                    bitmap = page.render(scale=4.16)  # ≈300 DPI
                    pil_image = bitmap.to_pil()

                    buf = io.BytesIO()
                    pil_image.save(buf, format="PNG")
                    buf.seek(0)
                    return True, buf.read()
                finally:
                    page.close()
        except Exception as e:
            return False, f"提取 PDF 页面失败: {e}"

    # ─── 内部辅助 ─────────────────────────────────────────────

    @staticmethod
    def _page_text(page: pdfium.PdfPage) -> str:
        """提取页面的全部文字。"""
        textpage = page.get_textpage()
        try:
            return textpage.get_text_range()
        finally:
            textpage.close()

    @staticmethod
    def _extract_sku_from_text(text: str) -> str | None:
        """从页面文字中提取 SKU/FNSKU。"""
        if not text:
            return None

        # 模式1：Amazon FNSKU（X 或 B 开头 + 9 位大写字母数字）
        m = re.search(r"\b([XB][A-Z0-9]{9})\b", text)
        if m:
            return m.group(1)

        # 模式2：大写字母数字组合（排除常见无效词）
        ignore = {"MADE", "CHINA", "NEW", "ITEM", "LABEL", "PRINT", "PACK", "QTY", "PCS", "AMAZON"}
        words = re.findall(r"\b([A-Z0-9_\-./]{5,30})\b", text)
        candidates = [w for w in words if w not in ignore and not w.isdigit()]
        if candidates:
            return candidates[0]

        # 回退：取前 50 个字符
        return text.split("\n")[0][:50] if text else None

