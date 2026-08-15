# -*- coding: utf-8 -*-
"""打印居中定位纯函数回归测试。

验证 _compute_centered_origin：标签内容以打印机物理纸张中心为基准
定位，并正确处理可打印区域偏移 / 裁剪。
"""

from __future__ import annotations

from services.print_service import PrintService


class TestCenteredOrigin:
    def test_label_fills_page_no_offset(self):
        """标签=纸张、无偏移：原点不变 (0,0)，不裁剪。"""
        x, y, w, h, cl, ct = PrintService._compute_centered_origin(
            target_w=1181, target_h=1181,
            printable_w=1181, printable_h=1181,
            phys_w=1181, phys_h=1181, off_x=0, off_y=0,
        )
        assert (x, y, w, h, cl, ct) == (0, 0, 1181, 1181, 0, 0)

    def test_label_smaller_than_paper_centered(self):
        """50mm 标签在 100mm 纸张上：水平垂直居中（±1px 取整容差）。"""
        x, y, w, h, cl, ct = PrintService._compute_centered_origin(
            target_w=591, target_h=354,
            printable_w=1181, printable_h=1181,
            phys_w=1181, phys_h=1181, off_x=0, off_y=0,
        )
        assert abs(x - (1181 - 591) / 2) <= 1
        assert abs(y - (1181 - 354) / 2) <= 1
        assert (w, h, cl, ct) == (591, 354, 0, 0)

    def test_printable_origin_offset_compensated(self):
        """可打印区原点偏右 100px：绘制起点左移抵消，内容仍居中。"""
        x, y, w, h, cl, ct = PrintService._compute_centered_origin(
            target_w=591, target_h=354,
            printable_w=1081, printable_h=1181,
            phys_w=1181, phys_h=1181, off_x=100, off_y=0,
        )
        assert x == 195
        assert abs(y - (1181 - 354) / 2) <= 1
        assert (w, h, cl, ct) == (591, 354, 0, 0)

    def test_label_larger_than_printable_scaled_down(self):
        """标签大于可打印区（驱动边距）：等比缩小到可打印区内。"""
        x, y, w, h, cl, ct = PrintService._compute_centered_origin(
            target_w=1181, target_h=1181,
            printable_w=1100, printable_h=1100,
            phys_w=1181, phys_h=1181, off_x=40, off_y=40,
        )
        assert w == h == 1100  # 缩小到可打印区
        assert cl == 0 and ct == 0
        assert x == 0 and y == 0

    def test_phys_size_unavailable_fallback(self):
        """物理纸尺寸不可用(0)：用 偏移+可打印区 推断中心。"""
        x, y, w, h, cl, ct = PrintService._compute_centered_origin(
            target_w=591, target_h=354,
            printable_w=1181, printable_h=1181,
            phys_w=0, phys_h=0, off_x=50, off_y=50,
        )
        # 推断中心 = (50+1181)/2 = 615.5 → 左缘 615.5-295.5-50 = 270
        assert x == 270
        assert y == round((50 + 1181) / 2 - 354 / 2 - 50)
        assert (w, h, cl, ct) == (591, 354, 0, 0)

    def test_origin_offset_left_crops_image(self):
        """原点大幅偏右导致起点为负：裁剪图片左侧，绘制起点归零。"""
        x, y, w, h, cl, ct = PrintService._compute_centered_origin(
            target_w=591, target_h=354,
            printable_w=1081, printable_h=1181,
            phys_w=1181, phys_h=1181, off_x=600, off_y=0,
        )
        # 590.5 - 295.5 - 600 = -305
        assert x == 0
        assert cl == 305
        assert w == 591 - 305
        assert ct == 0

    def test_origin_offset_right_crops_image(self):
        """原点偏左导致起点靠右：裁剪图片右侧。"""
        x, y, w, h, cl, ct = PrintService._compute_centered_origin(
            target_w=591, target_h=354,
            printable_w=1081, printable_h=1181,
            phys_w=1181, phys_h=1181, off_x=-600, off_y=0,
        )
        # 590.5 - 295.5 + 600 = 895 → 右缘 895+591=1486 > 1081 → 右侧裁 405
        assert x == 895
        assert cl == 0
        assert w == 591 - 405
        assert ct == 0
