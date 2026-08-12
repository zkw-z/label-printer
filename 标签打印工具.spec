# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

app_dir = Path(SPECPATH)
datas = []
qr_path = app_dir / "wechat_qr.png"
if qr_path.exists():
    datas.append((str(qr_path), "."))

a = Analysis(
    ['main.py'],
    pathex=[
        str(app_dir / 'pdf-merge-trim' / 'scripts'),
        str(app_dir / 'fnsku-extractor' / 'scripts'),
    ],
    binaries=[],
    datas=datas + [
        (str(app_dir / 'tessdata' / 'jpn.traineddata'), 'tessdata'),
        (str(app_dir / 'tessdata' / 'eng.traineddata'), 'tessdata'),
        (str(app_dir / 'pdf-merge-trim' / 'scripts' / 'merge_trim.py'), 'pdf-merge-trim/scripts'),
        (str(app_dir / 'fnsku-extractor' / 'scripts' / 'extract_fnsku.py'), 'fnsku-extractor/scripts'),
        (str(app_dir / 'fnsku-extractor' / 'scripts' / 'generate_labels.py'), 'fnsku-extractor/scripts'),
    ],
    hiddenimports=[
        'loguru', 'pydantic',
        'win32print', 'win32ui', 'win32con', 'win32api', 'pythoncom',
        'openpyxl', 'xlrd',
        'pypdfium2', 'pypdfium2_raw',
        'PIL._imagingtk', 'PIL._tkinter_finder',
        'fitz', 'pikepdf',
        'reportlab.lib.units', 'reportlab.pdfbase', 'reportlab.pdfgen', 'pytesseract',
        'services.com_thread',
        'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext',
    ] + collect_submodules('reportlab.graphics.barcode'),
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'pandas', 'scipy', 'numpy',
        'sqlalchemy', 'tensorflow', 'tensorboard',
        'sympy', 'matplotlib', 'plotly',
        'modelscope', 'transformers',
        'PIL.ImageQt',
        'notebook', 'jupyter',
        'bokeh', 'dask', 'distributed',
        'cv2', 'opencv',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LabelPrintTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
