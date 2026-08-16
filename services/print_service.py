"""打印服务

封装 Windows GDI 打印机操作，支持：
- 图片打印（按物理尺寸缩放）
- PDF 页面渲染为 PIL Image
- 文字标签图片生成（自适应字体，居中排版）
- 打印机列表查询
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import ctypes

import win32con  # type: ignore[import-untyped]
import win32print  # type: ignore[import-untyped]
import win32ui  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont, ImageWin
from loguru import logger

from config import FONT_CANDIDATES
from utils.image_utils import scale_image, fit_to_size

if TYPE_CHECKING:
    pass


@dataclass
class PrintJob:
    """单次打印任务描述。"""

    printer: str
    orientation: str = "portrait"
    width_mm: int = 100
    height_mm: int = 100
    scale: float = 1.0
    copies: int = 1


# ── DEVMODE 结构（ctypes 定义，用于设置打印纸张）──────────────


class _DevModeW(ctypes.Structure):
    """Windows DEVMODEW 结构（公共部分，与 dmSize=220 对应）。"""

    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_ushort),
        ("dmDriverVersion", ctypes.c_ushort),
        ("dmSize", ctypes.c_ushort),
        ("dmDriverExtra", ctypes.c_ushort),
        ("dmFields", ctypes.c_uint),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_ushort),
        ("dmBitsPerPel", ctypes.c_uint),
        ("dmPelsWidth", ctypes.c_uint),
        ("dmPelsHeight", ctypes.c_uint),
        ("dmDisplayFlags", ctypes.c_uint),
        ("dmDisplayFrequency", ctypes.c_uint),
        ("dmICMMethod", ctypes.c_uint),
        ("dmICMIntent", ctypes.c_uint),
        ("dmMediaType", ctypes.c_uint),
        ("dmDitherType", ctypes.c_uint),
        ("dmReserved1", ctypes.c_uint),
        ("dmReserved2", ctypes.c_uint),
        ("dmPanningWidth", ctypes.c_uint),
        ("dmPanningHeight", ctypes.c_uint),
    ]


def _build_custom_paper_devmode(width_mm: int, height_mm: int) -> _DevModeW:
    """构建自定义纸张 DEVMODE（dmPaperWidth/dmPaperLength，0.1mm 单位）。"""
    dm = _DevModeW()
    dm.dmSize = ctypes.sizeof(_DevModeW)
    dm.dmFields = win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH
    dm.dmPaperWidth = int(width_mm * 10)
    dm.dmPaperLength = int(height_mm * 10)
    return dm


def _reset_dc_paper(hdc_value: int, dm) -> int:
    """调用 GDI ResetDCW 应用 DEVMODE（win32ui 未暴露 ResetDC）。

    Returns:
        新 DC 句柄；失败返回 0。
    """
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi32.ResetDCW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_DevModeW)]
    gdi32.ResetDCW.restype = ctypes.c_void_p
    return int(gdi32.ResetDCW(hdc_value, ctypes.byref(dm)) or 0)


class PrintService:
    """Windows GDI 打印服务。"""

    # PDF 渲染 scale：4.16 ≈ 300 DPI

    # 默认 DPI
    LABEL_DPI: int = 300

    # ─── 打印机查询 ────────────────────────────────────────────

    @staticmethod
    def list_printers() -> list[str]:
        """返回系统可用打印机列表。"""
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [info[2] for info in win32print.EnumPrinters(flags)]

    @staticmethod
    def get_printer_page_size_mm(printer_name: str) -> tuple[int, int]:
        """获取指定打印机的当前页面尺寸 (width_mm, height_mm)。

        通过 CreatePrinterDC 读取设备参数，不发起打印任务。
        失败时返回默认 100×100mm。
        """
        if not printer_name:
            return 100, 100
        try:
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)
            dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
            dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)
            page_w = hdc.GetDeviceCaps(win32con.HORZRES)
            page_h = hdc.GetDeviceCaps(win32con.VERTRES)
            hdc.DeleteDC()
            width_mm = int(page_w * 25.4 / dpi_x)
            height_mm = int(page_h * 25.4 / dpi_y)
            return width_mm, height_mm
        except Exception:
            logger.exception("获取打印机页面尺寸失败: {}", printer_name)
            return 100, 100

    @staticmethod
    def get_printer_forms(printer_name: str) -> list[tuple[str, int, int]]:
        """获取打印机支持的纸张列表（类似 Word 纸张大小下拉列表）。

        通过 DeviceCapabilities(DC_PAPERNAMES / DC_PAPERSIZE) 获取打印机
        驱动报告的纸张名称和尺寸。按尺寸去重，保留第一个名称。
        失败时降级为当前默认纸张单值。

        Returns:
            [(paper_name, width_mm, height_mm), ...] 按尺寸排序。
        """
        if not printer_name:
            return [("默认", 100, 100)]

        try:
            # 获取打印机端口名（DeviceCapabilities 需要）
            handle = win32print.OpenPrinter(printer_name)
            try:
                info = win32print.GetPrinter(handle, 2)
                port = info.get("pPortName", "")
            finally:
                win32print.ClosePrinter(handle)

            names = win32print.DeviceCapabilities(
                printer_name, port, win32con.DC_PAPERNAMES
            )
            sizes = win32print.DeviceCapabilities(
                printer_name, port, win32con.DC_PAPERSIZE
            )

            if not names or not sizes or len(names) != len(sizes):
                raise ValueError("DeviceCapabilities 返回数据异常")

            # 去重：同尺寸只保留第一个名称
            seen: set[tuple[int, int]] = set()
            forms: list[tuple[str, int, int]] = []
            for name, sz in zip(names, sizes, strict=True):
                w = int(sz["x"] / 10)  # 0.1mm → mm
                h = int(sz["y"] / 10)
                key = (w, h)
                if key not in seen:
                    seen.add(key)
                    forms.append((name, w, h))

            forms.sort(key=lambda x: (x[1] * x[2], x[1]))  # 按面积排序
            return forms

        except Exception:
            logger.exception("获取打印机纸张列表失败: {}", printer_name)
            # 降级：只返回当前默认纸张
            w, h = PrintService.get_printer_page_size_mm(printer_name)
            return [("默认", w, h)]

    # ─── 纸张尺寸应用 ──────────────────────────────────────────

    @staticmethod
    def _apply_paper_size(
        printer: str, width_mm: int, height_mm: int, hdc
    ) -> None:
        """把设置中的纸张尺寸通过 DEVMODE 应用到当前打印 DC。

        使用 dmPaperWidth / dmPaperLength（0.1mm 单位）设置自定义纸张，
        是标签打印机的标准做法；仅影响本次打印任务，不改系统默认。
        失败时仅记录警告，回退使用打印机当前纸张。
        """
        if not width_mm or not height_mm:
            return
        # 虚拟 PDF 打印机（Microsoft Print to PDF / WPS PDF 等）对自定义
        # 纸张支持异常，跳过设置，保持其默认页面（仅作测试输出用）
        _virtual_keywords = (
            "pdf", "wps", "print to pdf", "one note", "onenote", "xps", "fax",
        )
        if any(k in printer.lower() for k in _virtual_keywords):
            return
        try:
            dm = _build_custom_paper_devmode(width_mm, height_mm)
            hval = int(hdc.GetSafeHdc()) & 0xFFFFFFFF
            result = _reset_dc_paper(hval, dm)
            if not result:
                logger.warning(
                    f"应用纸张尺寸 {width_mm}×{height_mm}mm 失败，"
                    f"使用打印机当前纸张。"
                )
                return
            logger.info(
                f"已应用纸张尺寸: {width_mm}×{height_mm}mm → {printer}"
            )
        except Exception:
            logger.warning(
                f"应用纸张尺寸 {width_mm}×{height_mm}mm 异常，"
                f"使用打印机当前纸张。"
            )

    # ─── 图片打印 ───    # ─── 图片打印 ──────────────────────────────────────────────

    def print_image(
        self,
        image: Image.Image,
        job: PrintJob,
    ) -> tuple[bool, str]:
        """将 PIL Image 发送到打印机。

        Args:
            image: 要打印的 PIL Image。
            job: 打印任务参数。

        Returns:
            (True, "success") | (False, error_msg)
        """
        if not job.printer:
            return False, "打印错误: 未指定打印机名称"

        hdc = None
        try:
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(job.printer)

            # 把设置中的纸张尺寸真正应用到本次打印任务（DEVMODE 自定义纸张）
            self._apply_paper_size(job.printer, job.width_mm, job.height_mm, hdc)

            hdc.StartDoc("Label Print Job")
            hdc.StartPage()

            dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
            dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)
            page_w = hdc.GetDeviceCaps(win32con.HORZRES)
            page_h = hdc.GetDeviceCaps(win32con.VERTRES)

            if job.width_mm and job.height_mm:
                target_w = int(job.width_mm * dpi_x / 25.4)
                target_h = int(job.height_mm * dpi_y / 25.4)

                if job.scale < 1.0:
                    image = scale_image(image, job.scale)

                if job.orientation == "landscape" and target_w < target_h:
                    image = image.rotate(90, expand=True)
                    target_w, target_h = target_h, target_w

                # 等比缩放居中（不变形，白底填充）
                # 纸张设置生效后，可打印区可能小于目标尺寸（打印机硬件边距），
                # 等比缩放到可打印区内，避免内容被边缘裁剪
                draw_w = min(target_w, page_w)
                draw_h = min(target_h, page_h)
                image = fit_to_size(image, draw_w, draw_h)

                dib = ImageWin.Dib(image)
                dib.draw(hdc.GetSafeHdc(), (0, 0, draw_w, draw_h))
            else:
                # 自适应页面
                img_w, img_h = image.size
                scale_x = page_w / img_w
                scale_y = page_h / img_h
                fit = min(scale_x, scale_y)

                new_w = int(img_w * fit)
                new_h = int(img_h * fit)

                if job.orientation == "landscape" and new_w < new_h:
                    image = image.rotate(90, expand=True)
                    img_w, img_h = image.size
                    scale_x = page_w / img_w
                    scale_y = page_h / img_h
                    fit = min(scale_x, scale_y)
                    new_w = int(img_w * fit)
                    new_h = int(img_h * fit)

                dib = ImageWin.Dib(image)
                dib.draw(hdc.GetSafeHdc(), (0, 0, new_w, new_h))

            hdc.EndPage()
            hdc.EndDoc()
            return True, "打印成功"

        except Exception as e:
            return False, f"打印错误: {e}"
        finally:
            if hdc is not None:
                try:
                    hdc.DeleteDC()
                except Exception:
                    pass

    # ─── PDF 渲染 ─────────────────────────────────────────────

    # ─── 标签图片生成 ──────────────────────────────────────────

    def generate_label_image(
        self,
        text: str,
        width_mm: int,
        height_mm: int,
        *,
        font_size: int | None = None,
        min_font_size: int = 20,
        auto_wrap: bool = False,
        highlight: list[str] | None = None,
        fixed_line_sizes: dict[int, int] | None = None,
    ) -> Image.Image:
        """Generate a centered text label image with adaptive font sizes.

        Args:
            text: Label text (newline separated lines).
            width_mm: Label width in mm.
            height_mm: Label height in mm.
            font_size: Initial font size (default 92 for 30mm else 120).
            min_font_size: Minimum font size for shrink-to-fit.
            auto_wrap: Wrap long lines by character.
            highlight: Keywords rendered larger (+2) and bold.
            fixed_line_sizes: {line_index: max_font_size}; these lines keep
                their size (never enlarged or wrapped) but may shrink when
                content overflows.
        Returns:
            PIL Image with white background.
        """
        dpi = self.LABEL_DPI
        width_px = int(width_mm * dpi / 25.4)
        height_px = int(height_mm * dpi / 25.4)

        image = Image.new("RGB", (width_px, height_px), "white")
        draw = ImageDraw.Draw(image)

        # split lines, keep original indices for fixed-line mapping
        raw_lines = [ln for ln in text.split("\n") if ln.strip()]
        if not raw_lines:
            raw_lines = [text] if text else [""]
        fixed_map: dict[int, int] = {}
        if fixed_line_sizes:
            for idx, size in fixed_line_sizes.items():
                if size and 0 <= idx < len(raw_lines):
                    fixed_map[idx] = size

        if font_size is None:
            font_size = 92 if height_mm == 30 else 120
        padding = 40
        max_w = width_px - padding
        max_h = height_px - padding

        keywords = [kw for kw in (highlight or []) if kw]

        # build line groups: fixed lines stay single-line, wrap-able lines
        # re-wrap at their current size so wrapped lines span the full width
        fixed_min = 40
        groups: list[dict] = []
        for idx, raw in enumerate(raw_lines):
            if idx in fixed_map:
                groups.append({"text": raw, "size": fixed_map[idx], "fixed": True})
            else:
                groups.append({"text": raw, "size": font_size, "fixed": False})

        font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

        def _font(size: int):
            if size not in font_cache:
                font_cache[size] = self._load_font(size)
            return font_cache[size]

        def _segments(line: str) -> list[tuple[str, bool]]:
            if not keywords:
                return [(line, False)]
            segs: list[tuple[str, bool]] = []
            pos = 0
            while pos < len(line):
                best_start: int | None = None
                best_kw = ""
                for kw in keywords:
                    idx = line.find(kw, pos)
                    if idx != -1 and (best_start is None or idx < best_start):
                        best_start = idx
                        best_kw = kw
                if best_start is None:
                    segs.append((line[pos:], False))
                    break
                if best_start > pos:
                    segs.append((line[pos:best_start], False))
                segs.append((best_kw, True))
                pos = best_start + len(best_kw)
            return segs

        def _line_width(line: str, size: int) -> float:
            nf = _font(size)
            hf = _font(size + 2) if keywords else nf
            return sum(
                draw.textlength(t, font=hf if hl else nf)
                for t, hl in _segments(line)
            )

        def _line_height(line: str, size: int) -> int:
            nf = _font(size)
            hf = _font(size + 2) if keywords else nf
            measure = hf if any(kw in line for kw in keywords) else nf
            bbox = draw.textbbox((0, 0), line if line else "Tg", font=measure)
            return bbox[3] - bbox[1]

        def _wrap(text: str, size: int) -> list[str]:
            """Split text into lines that fit max_w at the given font size."""
            if _line_width(text, size) <= max_w:
                return [text]
            out: list[str] = []
            current = ""
            for ch in text:
                if current and _line_width(current + ch, size) > max_w:
                    out.append(current)
                    current = ch
                else:
                    current += ch
            if current:
                out.append(current)
            return out

        def _render() -> tuple[list[str], list[int]]:
            out_lines: list[str] = []
            out_sizes: list[int] = []
            for g in groups:
                if auto_wrap and not g["fixed"]:
                    wrapped = _wrap(g["text"], g["size"])
                    out_lines.extend(wrapped)
                    out_sizes.extend([g["size"]] * len(wrapped))
                else:
                    out_lines.append(g["text"])
                    out_sizes.append(g["size"])
            return out_lines, out_sizes

        # shrink-to-fit: resolve width overflow first (only the offending
        # lines), then total-height overflow (wrap-able lines first, fixed
        # lines as fallback)
        while True:
            lines, line_sizes = _render()
            width_ok = True
            offenders: list[dict] = []
            for g in groups:
                if g["fixed"] or not auto_wrap:
                    if _line_width(g["text"], g["size"]) > max_w:
                        offenders.append(g)
                        width_ok = False
            if width_ok:
                heights = [_line_height(line, size) for line, size in zip(lines, line_sizes)]
                spacing = int(max(line_sizes) * 0.05)
                total_h = sum(heights) + (len(lines) - 1) * spacing
                if total_h > max_h:
                    shrink = [
                        g for g in groups
                        if not g["fixed"] and g["size"] > min_font_size
                    ]
                    if not shrink:
                        shrink = [
                            g for g in groups
                            if g["fixed"] and g["size"] > fixed_min
                        ]
                    if not shrink:
                        break
                    for g in shrink:
                        g["size"] -= 5
                    continue
                break
            shrink = [
                g for g in offenders
                if not g["fixed"] and g["size"] > min_font_size
            ]
            if not shrink:
                shrink = [
                    g for g in offenders
                    if g["fixed"] and g["size"] > fixed_min
                ]
            if not shrink:
                break
            for g in shrink:
                g["size"] -= 5

        spacing = int(max(line_sizes) * 0.05)
        line_heights = [_line_height(line, size) for line, size in zip(lines, line_sizes)]
        total_h = sum(line_heights) + (len(lines) - 1) * spacing
        y = (height_px - total_h) / 2

        for i, line in enumerate(lines):
            size = line_sizes[i]
            nf = _font(size)
            hf = _font(size + 2) if keywords else nf
            w = _line_width(line, size)
            x = (width_px - w) / 2
            n_ascent = nf.getmetrics()[0]
            h_ascent = hf.getmetrics()[0] if keywords else n_ascent
            y_base = y + n_ascent
            for seg, is_hl in _segments(line):
                f = hf if is_hl else nf
                if is_hl:
                    draw.text(
                        (x, y_base - h_ascent), seg, font=f,
                        fill="black", stroke_width=3, stroke_fill="black",
                    )
                else:
                    draw.text((x, y_base - n_ascent), seg, font=f, fill="black")
                x += draw.textlength(seg, font=f)
            if i < len(lines) - 1:
                y += line_heights[i] + spacing

        return image

    def add_warehouse_header(self, image: Image.Image, warehouse_code: str) -> Image.Image:
        """在图片顶端居中叠加 FBA 仓库编码文字，尺寸不变，允许重叠。

        Args:
            image: 原始标签 PIL Image。
            warehouse_code: 仓库编码（如 "TPB6"）。

        Returns:
            同尺寸的新 PIL Image。
        """
        text = warehouse_code
        font_size = 96
        font = self._load_font(font_size)

        draw_temp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        bbox = draw_temp.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        padding = font_size // 3

        result = image.copy()
        draw = ImageDraw.Draw(result)
        x = (image.width - text_w) // 2
        draw.text((x, padding), text, fill="black", font=font)
        return result

    # ─── 内部 ──────────────────────────────────────────────────

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """按优先级加载中文字体。"""
        for name in FONT_CANDIDATES:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()


