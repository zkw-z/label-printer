"""图像处理工具函数

提供统一的图像缩放、等比适配等功能，避免在多个模块中重复实现。
"""

from __future__ import annotations

from PIL import Image


def scale_image(image: Image.Image, scale: float) -> Image.Image:
    """将图像缩放并置于原尺寸白底画布中央（实现缩小效果）。

    Args:
        image: 原始 PIL Image。
        scale: 缩放比例（0.0~1.0）。

    Returns:
        同尺寸的新 PIL Image，缩小后的图像居中，空白处填充白色。
    """
    img_w, img_h = image.size
    scaled_w = int(img_w * scale)
    scaled_h = int(img_h * scale)

    new_image = Image.new("RGB", (img_w, img_h), "white")
    scaled = image.resize((scaled_w, scaled_h), Image.Resampling.BICUBIC)

    ox = (img_w - scaled_w) // 2
    oy = (img_h - scaled_h) // 2
    new_image.paste(scaled, (ox, oy))
    return new_image


def fit_to_size(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """等比缩放图片使其完整放入目标区域，居中，白底填充。

    Args:
        img: 原始 PIL Image。
        target_w: 目标宽度（像素）。
        target_h: 目标高度（像素）。

    Returns:
        目标尺寸的新 PIL Image，图片等比缩放居中，空白处填充白色。
    """
    img_w, img_h = img.size
    ratio = min(target_w / img_w, target_h / img_h)
    new_w, new_h = int(img_w * ratio), int(img_h * ratio)
    img = img.resize((new_w, new_h), Image.Resampling.BICUBIC)

    canvas = Image.new("RGB", (target_w, target_h), "white")
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(img, (offset_x, offset_y))
    return canvas