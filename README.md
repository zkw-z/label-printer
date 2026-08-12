# 🏷️ 标签打印工具 v1.2.1

Amazon FBA 卖家标签打印工作流工具 — 一站式 Excel 解析 → PDF 匹配 → 打印输出。

---

## 📥 下载

- **Windows 便携版 exe（免安装，双击即用）**：[点击下载最新版](https://github.com/zkw-z/label-printer/releases/latest)
- 历史版本：[Releases 页面](https://github.com/zkw-z/label-printer/releases)

---

## 一、功能优点

### 1. 智能格式识别
- 自动识别三种 Excel 指示文件格式：
  - **标准指示文件**（旧格式，固定 8 列）
  - **派送表**（新格式，模糊列名映射 + item no. 提取份数/数量）
  - **贴标指示表**（第三种格式，专用列映射 + 备注列提取）
- 中文数字识别：「每箱贴两张」→ 自动提取份数 2
- FBA 编号自动清洗（去 `U01-25` 后缀）

### 2. 复合键精确匹配
- 同一 SKU 对应不同标识符（如 `-ID1`/`-ID2`）时，精确区分 PDF 页面
- 复合键格式：`SKU|||标识符`，打印时不会取错页面
- 支持 PDF 内容换行打断标识符（去空白紧凑匹配）

### 3. 标签防火墙
- 上传指示文件时自动扫描，双层提醒：
  - **红色弹窗**：透明标签相关（需要人工核对）
  - **蓝色日志**：乐天仓、海外仓、需贴大小标等特殊备注
- 未映射列值（备注列/item no.列）全覆盖扫描
- 换箱唛自动重置贴标顺序，防止跨唛误报

### 4. 完整 PDF 编辑工具链
- **FBA 编辑**：智能白边裁剪 + 多 PDF 合并，统一 100×100mm 输出
- **SKU 编辑**：FNSKU 文本+图片 OCR 提取，生成 50×30mm 条形码标签 PDF，输出 xlsx 明细

### 5. SQLite 标签数据库
- PDF 页面渲染为 PNG 存入本地数据库
- 支持复合键精确查询，避免纯 SKU 歧义回退
- 自动清理 30 天前旧数据 + VACUUM 压缩

### 6. Windows 原生打印
- pywin32 GDI 打印接口，支持图片等比缩放居中
- 纸张尺寸自适应，FBA 标签 + 仓库编码叠加
- 打印机纸张列表自动获取（类 Word 下拉选纸）

### 7. 线程池 + 进度反馈
- COM 感知线程池（3 worker），打印/PDF 处理不阻塞 UI
- 实时日志着色（error 红 / warning 橙 / success 绿 / info 蓝）
- 进度条支持确定/不确定模式

### 8. 便捷操作
- 键盘 `↓` 循环切换箱唛 → `Enter` 一键打印 FBA+
- 独立 FBA 打印模式（无需 Excel，自动发现 FBA 编号）
- 单个 SKU 快速保存/打印
- 最近文件历史（最多 10 个）
- PyInstaller 打包为独立 `.exe`，自动检测安装缺失依赖

---

## 二、操作说明

### 🚀 从源码运行

```bash
# 环境要求：Windows 10/11 + Python 3.10+
pip install -r requirements.txt

# 启动
python main.py
```

> OCR（SKU 编辑）依赖 Tesseract 语言数据：程序默认从 `tessdata/` 目录加载，可从
> [tesseract-ocr/tessdata](https://github.com/tesseract-ocr/tessdata) 下载 `chi_sim.traineddata` 等文件放入即可；
> 该目录因体积较大不随源码仓库提交。

### 🚀 打包为 exe

```bash
pip install pyinstaller
pyinstaller 标签打印工具.spec
```

产物输出到 `dist/` 目录。

### 🚀 启动


```
双击「标签打印工具.exe」即可启动。
首次启动如缺少依赖，程序会自动弹窗询问是否安装。
```

### 📁 左栏：文件上传

| 按钮 | 操作 |
|------|------|
| 📄 指示文件 (Excel) | 选择 `.xlsx`/`.xls` 文件。上传后自动触发标签防火墙 |
| 📦 FBA PDF | 选择含 FBA 标签的 PDF（需先上传 Excel） |
| 🏷️ SKU PDF | 选择含 SKU 标签的 PDF。无 Excel 时支持自动命名保存 |

### 🖨️ 中栏：批量打印

```
1. 在「箱唛」输入框输入唛头 → 按 Enter 一键打印
2. 或按 ↓ 键依次自动填入下一个箱唛
3. 打印 FBA：打印该箱唛的 FBA 标签 + 贴标顺序汇总
4. 打印 SKU：打印该箱唛下所有 SKU 标签

独立 FBA 打印区：
  • 输入 FBA 号 + 地址 + 份数 → 点击「打印」
  • 点击「上传」可独立上传 FBA PDF（无需 Excel）
```

### 🔖 右栏：单个 SKU

```
• 输入 SKU 名称 + 数量 → 点击「打印」
• 先点击「🏷️ SKU PDF」上传单页 PDF → 弹窗确认保存
```

### ⚙️ 纸张设置

```
点击批量打印区打印机旁的「⚙」按钮：
  • 选择打印机 → 设定方向（纵向/横向）
  • FBA 模式：下拉选纸张大小（自动从打印机驱动读取）
  • 保存设置
```

### ✂️ FBA/SKU 编辑

```
FBA 编辑：选择含 FBA PDF 的目录 → 自动裁剪白边合并为 100×100mm
SKU 编辑：选择含 SKU PDF 的目录 → 提取 FNSKU + 生成条形码标签
```

### 🧹 维护

```
• 清空数据库：删除所有已缓存的 SKU 标签图像
• 自动清理：启动时自动删除 30 天前的旧数据
```

### 🛡️ 标签防火墙

```
上传 Excel 时自动运行，无需手动操作：
• 透明标签 → 弹窗提示 + 红色日志
• 乐天/海外仓/需贴大小标 → 蓝色日志提示
• 提示具体箱唛信息，方便核对
```

### 📊 日志面板

```
底部面板实时显示操作日志，按类型自动着色：
  🔴 红色 — 错误/失败/透明标签
  🟠 橙色 — 警告/缺失
  🟢 绿色 — 成功/完成
  🔵 蓝色 — 提示/特殊备注
```

---

## 三、技术架构

```
label_printer/
├── main.py              # 程序入口，依赖检测与自动安装
├── config.py            # 路径解析、配置持久化、日志
├── config_schema.py     # Pydantic 配置模型
├── models/
│   ├── excel_data.py    # Excel 解析（三种格式 + 复合键 + ffill）
│   ├── pdf_mapper.py    # PDF 页面映射（FBA/SKU）
│   ├── sku_database.py  # SQLite 标签图像存储
│   └── recent_files.py  # 最近文件管理
├── services/
│   ├── workflow_service.py  # 工作流编排 + 标签防火墙
│   ├── print_service.py     # Windows GDI 打印服务
│   ├── edit_service.py      # FBA/SKU 编辑（合并裁剪/FNSKU提取）
│   └── com_thread.py        # COM 感知线程池
├── ui/
│   ├── app.py              # 主窗口，键盘快捷键
│   ├── upper_section.py    # 三栏布局（上传/批量打印/单SKU）
│   ├── lower_section.py    # 日志面板（着色）
│   ├── settings_dialog.py  # 打印机设置对话框
│   ├── about_dialog.py     # 关于对话框
│   ├── widgets.py          # UI 基础组件（主题/按钮/卡片）
??? fnsku-extractor/     # FNSKU ?????
??? pdf-merge-trim/      # PDF ???????
??? tessdata/            # Tesseract OCR ????????????
??? tests/               # pytest ????
??? ??????.spec       # PyInstaller ????
├── tests/               # pytest 单元测试
```

### 核心依赖

| 用途 | 依赖 |
|------|------|
| Excel 解析 | `openpyxl`, `xlrd` |
| PDF 处理 | `PyMuPDF`, `pikepdf`, `pypdfium2` |
| 图像处理 | `Pillow` |
| 打印 | `pywin32` |
| 标签生成 | `reportlab` |
| 配置校验 | `pydantic` |
| 日志 | `loguru` |
| OCR | `pytesseract` |
| 打包 | `PyInstaller` |

---

**开发者**：阿文 | **版本**：v1.2.1
