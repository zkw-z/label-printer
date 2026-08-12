"""关于对话框"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from ui.widgets import Theme


def show_about(parent: tk.Toplevel | tk.Tk, app_dir: str | Path) -> None:
    """显示关于窗口。"""
    about = tk.Toplevel(parent)
    about.title("关于")
    about.geometry("400x550")
    about.resizable(False, False)
    about.configure(bg=Theme.BG_MAIN)

    about.update_idletasks()
    x = (about.winfo_screenwidth() // 2) - (400 // 2)
    y = (about.winfo_screenheight() // 2) - (550 // 2)
    about.geometry(f"+{x}+{y}")

    content = tk.Frame(
        about,
        bg=Theme.BG_CARD,
        highlightthickness=1,
        highlightbackground=Theme.BORDER,
    )
    content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    tk.Label(
        content,
        text="🏷️ 标签打印工具",
        bg=Theme.BG_CARD,
        fg=Theme.TEXT_PRIMARY,
        font=("Microsoft YaHei UI", 16, "bold"),
    ).pack(pady=(20, 10))

    tk.Label(
        content,
        text="Version 1.2.0",
        bg=Theme.BG_CARD,
        fg=Theme.TEXT_SECONDARY,
        font=("Microsoft YaHei UI", 10),
    ).pack(pady=5)

    tk.Frame(content, bg=Theme.BORDER, height=1).pack(fill=tk.X, padx=30, pady=8)

    # 更新日志
    changelog = tk.Label(
        content,
        text=(
            "更新日志\n"
            "────────────────────────\n"
            "v1.2.0 — 独立FBA打印\n"
            "        纸张大小下拉\n"
            "        配置统一升级\n"
            "v1.1.0 — 打印等比缩放\n"
            "        换纸不换标签\n"
            "        设置面板宽/高\n"
            "v1.0.0 — 初始版本"
        ),
        bg=Theme.BG_CARD,
        fg=Theme.TEXT_SECONDARY,
        font=("Microsoft YaHei UI", 8),
        justify=tk.LEFT,
    )
    changelog.pack(pady=(0, 10))

    tk.Frame(content, bg=Theme.BORDER, height=1).pack(fill=tk.X, padx=30, pady=15)

    tk.Label(
        content,
        text="开发者",
        bg=Theme.BG_CARD,
        fg=Theme.TEXT_PRIMARY,
        font=("Microsoft YaHei UI", 11, "bold"),
    ).pack(pady=(10, 5))

    tk.Label(
        content,
        text="阿文",
        bg=Theme.BG_CARD,
        fg=Theme.PRIMARY,
        font=("Microsoft YaHei UI", 14, "bold"),
    ).pack(pady=5)

    tk.Frame(content, bg=Theme.BORDER, height=1).pack(fill=tk.X, padx=30, pady=15)

    tk.Label(
        content,
        text="联系方式",
        bg=Theme.BG_CARD,
        fg=Theme.TEXT_PRIMARY,
        font=("Microsoft YaHei UI", 11, "bold"),
    ).pack(pady=(10, 5))

    tk.Label(
        content,
        text="扫描二维码添加微信",
        bg=Theme.BG_CARD,
        fg=Theme.TEXT_SECONDARY,
        font=("Microsoft YaHei UI", 9),
    ).pack(pady=5)

    # 尝试显示二维码图片
    try:
        from PIL import Image, ImageTk

        base = Path(app_dir)
        qr_paths = [base / "wechat_qr.png", Path("wechat_qr.png")]
        qr_img = None
        for p in qr_paths:
            if p.exists():
                qr_img = Image.open(p)
                break

        if qr_img:
            qr_img = qr_img.resize((200, 200), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(qr_img)
            lbl = tk.Label(content, image=photo, bg=Theme.BG_CARD)
            lbl.image = photo
            lbl.pack(pady=10)
        else:
            tk.Label(
                content,
                text="二维码图片未找到",
                bg=Theme.BG_CARD,
                fg=Theme.TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 9),
            ).pack(pady=10)
    except Exception:
        tk.Label(
            content,
            text="加载二维码失败",
            bg=Theme.BG_CARD,
            fg=Theme.DANGER,
            font=("Microsoft YaHei UI", 9),
        ).pack(pady=10)

    tk.Button(
        about,
        text="关闭",
        font=("Microsoft YaHei UI", 10),
        bg=Theme.PRIMARY,
        fg=Theme.TEXT_LIGHT,
        relief=tk.FLAT,
        cursor="hand2",
        command=about.destroy,
        padx=30,
        pady=8,
    ).pack(pady=(0, 20))
