---
name: fnsku-extractor
description: |
  FNSKU和商品描述提取工具 V5（稳定版本）。
  从PDF文件中提取FNSKU及其下方的Description，输出为.xlsx格式，支持自动生成50×30mm条形码标签PDF。
  触发关键词："提取FNSKU"、"识别FNSKU"、"提取商品描述"、"PDF标签识别"、"整理SKU"、"整理FNSKU"、
  "生成标签"、"条形码标签"、"打印标签"。
agent_created: true
version: "V5"
---

# FNSKU & Description 提取工具 V5（稳定版本）

⚠️ **此为 V5 稳定版本，非特殊指令不得修改任何逻辑。**

从 FBA 标签 PDF 中提取 FNSKU 编码及其下方商品描述，输出 .xlsx 文件。逐页独立处理，文本页提取数据，图片页转为 PNG 供 OCR 识别。支持自动生成 50×30mm PDF 条形码标签，可直接打印贴于商品上。

## 特性

- **逐页智能分类** — 同一 PDF 的文本页提取 FNSKU，图片页转 PNG，不互相排斥
- **精准 FNSKU 匹配** — 二次过滤，只保留以 X00/B0 开头的有效编码，减少噪音
- **多行描述提取** — 自动收集 FNSKU 下方连续多行日文描述（直到遇空行或下一编码）
- **图片全量保留 + OCR 识别** — 图片页全部转 PNG，使用文件索引防重名；自动对扫描件 PNG 运行 Tesseract OCR（日语+英语），提取 FNSKU 和商品描述，与文本页结果一同输出
- **xlsx 格式化输出** — 带表头样式、交替行底色、自动筛选、冻结首行，Excel 双击即用
- **条形码标签生成** — 自动生成 50×30mm PDF 标签，Code128 条形码 + FNSKU 文字 + 商品描述，CJK 自适应字号

## 依赖

```bash
# 基础依赖（xlsx 输出）
pip install PyMuPDF openpyxl

# 标签生成（可选，使用 --labels 时需要）
pip install reportlab

# OCR 识别（可选，扫描件 PDF 自动识别）
pip install pytesseract Pillow
# 需安装 Tesseract-OCR（v5+）并下载日语语言包 jpn.traineddata
```

## 使用方法

### 一键提取 + 生成标签（推荐）

```bash
python scripts/extract_fnsku.py \
  --source <PDF源目录> \
  --labels
```

### 仅提取 xlsx

```bash
python scripts/extract_fnsku.py \
  --source <PDF源目录> \
  --output <输出xlsx路径> \
  --png-dir <PNG输出目录> \
  --dpi <分辨率倍数>
```

### 参数

| 参数 | 必填 | 默认值 | 说明 |
|------|:--:|--------|------|
| `--source` / `-s` | ✅ | — | PDF 源目录（递归搜索） |
| `--output` / `-o` | — | `fnsku_result.xlsx` | 输出 xlsx（相对路径则放在源目录下） |
| `--png-dir` / `-p` | — | `ocr_images` | 图片页 PNG 输出目录 |
| `--dpi` / `-d` | — | `4` | PNG 分辨率倍数（4 ≈ 300DPI） |
| `--labels` / `-l` | — | `False` | 自动生成 50×30mm 条形码标签 PDF |

### 快速示例

```bash
# 基础用法（仅 xlsx）
python scripts/extract_fnsku.py -s "D:\桌面\PASU5164708410-629CT 标签"

# 提取并生成标签
python scripts/extract_fnsku.py -s ./labels --labels

# 指定所有参数
python scripts/extract_fnsku.py -s ./labels -o result.xlsx -p png_output -d 3 --labels
```

### 独立生成标签

也可以对已有的 xlsx 文件单独生成标签：

```bash
python scripts/generate_labels.py \
  --input <xlsx文件路径> \
  --output <输出PDF路径>
```

| 参数 | 必填 | 默认值 | 说明 |
|------|:--:|--------|------|
| `--input` / `-i` | ✅ | — | 输入 xlsx 路径 |
| `--output` / `-o` | — | `*_labels.pdf` | 输出 PDF 路径 |

## 筛选条件

- 文件名 **包含** `X00` 或 `B0`
- 文件名 **不包含** `FBA`

## 处理流程

```
源目录
  │
  ▼
[扫描] 递归搜索 .pdf 文件 ──► 按文件名条件筛选
  │
  ▼
[逐页处理] ─┬─ 文本页 → 正则匹配 FNSKU → 二次过滤 → 提取多行描述
             │
             └─ 图片页 → 转为 PNG 保存 → OCR 识别（Tesseract jpn+eng）
                            → 提取 FNSKU（优先文件名）+ 商品描述
  │
  ▼
[去重] 相同 (FNSKU + Description) 仅保留一条
  │
  ▼
[输出] xlsx + PNG 目录
  │
  ▼ (--labels 时)
[标签] Code128 条形码 → Helvetica 9pt FNSKU → CJK 8→7→6pt 描述 (HeiseiKakuGo-W5) ──► PDF
```

## 输出格式

### xlsx（文本页提取结果）

三列：`#`（序号）、`FNSKU`、`Description`

| # | FNSKU | Description |
|---|-------|-------------|
| 1 | B09F9CW7XL | 伸縮はしご はし子 持ち込み便利 |
| 2 | X000P70ZVH | 20M CAT6A 屋外 パレーター 防水 ブラック 新品 |

xlsx 特性：
- 蓝色表头 + 白字加粗
- 交替行灰色底色，便于阅读
- FNSKU 列使用等宽字体（Consolas）
- 冻结首行 + 自动筛选
- 双击即可用 Excel 打开，无需担心编码问题

### 条形码标签 PDF（--labels 时）

每个标签独立一页，页面尺寸即标签尺寸 50×30mm，可直接打印到标签纸上。

**单个标签布局**：
```
┌──────────────────────────────────┐
│  ║║║║║║║║ BARCODE ║║║║║║║║║║    │ ← 条形码高度 9mm
│           X001234567              │ ← FNSKU 文字 (Helvetica 11pt)，距条形码 1mm
│  Product Description Text Here   │ ← 产品描述 (HeiseiMin-W3 9→8→7pt 自适应)
│  中文/日本語 自动换行             │
└──────────────────────────────────┘
  上边距 3mm / 下边距 1mm / 左右边距各 2.5mm
```

- 条形码：Code128 编码，高度 9mm
- FNSKU 文字：Helvetica 11pt，居中，距条形码底边视觉间距 1mm
- 商品描述：CJK 字体 (HeiseiMin-W3)，自动尝试 8pt → 7pt → 6pt 以适配可用空间，逐字符智能换行

### PNG（图片页输出）

- 文件名格式：`原PDF名_[文件索引]_页码.png`
- 文件索引确保同名 PDF 不互相覆盖
- **全部保留，不做去重**

## OCR 识别（可选）

图片页 PNG 可使用以下服务识别：

- [onlineocr.jp](https://onlineocr.jp/)
- [onlineocr.net](https://www.onlineocr.net/)

或安装 Tesseract + 日语语言包进行本地 OCR。

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **V5（稳定版）** | 2026-06-16 | **修复三处问题**：① `_extract_description` 搜索范围从 5 行扩大到 15 行，修复描述截断/数字丢失（如 X00185OGPV）；② 新增 OCR 回退逻辑——文本页提取到 FNSKU 但描述为空时，自动渲染整页 PNG 并跑 OCR 补识别，修复矢量图形描述丢失（如 X0015IY7FP）；③ `_clean_desc` 新增带圈数字清理规则 `[\u2460-\u24FF]`（①②③④⑤等），修复 OCR 输出中的圈号残留；同时修复 `_clean_desc` 中变量名拼写错误 |
| **V4（稳定版）** | 2026-06-07 | **新增 OCR 识别**：扫描件 PDF 自动 Tesseract OCR（日语+英语），提取 FNSKU+描述并一同生成标签；恢复 (FNSKU+Description) 联合去重；移除 --no-filter 参数 |
| 3.0 | 2026-05-26 | 新增 50×30mm PDF 条形码标签生成：`--labels` 一键生成标签；独立 `generate_labels.py` CLI；新增依赖 reportlab |
| 2.1 | 2026-05-26 | 输出格式从 CSV 改为 xlsx；带格式化样式（表头、交替行底色、冻结首行、自动筛选）；新增序号列；依赖增加 openpyxl |
| 2.0 | 2026-05-26 | 逐页独立处理（混合 PDF 不遗漏）；FNSKU 二次过滤；多行描述提取；移除静默异常；移除无意义 gc |
| 1.0 | 2026-03-27 | 初始版本 |
