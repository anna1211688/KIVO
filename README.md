# KIVO / KIVO

轻量级 Windows 桌面工具：管理多条文字复制记录、顺序粘贴，并提供截图、标注、贴图和 OCR 等功能。

> 当前仓库采用根目录布局，源码入口为 `main.py`。本文档按仓库当前结构编写。

## 主要功能

- **文字队列**：F6 将选中文字加入队列；F7 粘贴下一条；F8 粘贴全部；可配置粘贴后自动移除记录。
- **截图与贴图**：F1 区域截图并进入标注流程；F3 贴出剪贴板图片或文字便签。
- **标注与历史**：支持常见形状、箭头、画笔、文字、马赛克/模糊等标注，以及截图历史管理。
- **OCR 与扫码**：OCR 使用 RapidOCR；扫码能力可选安装 OpenCV。
- **辅助功能**：文字翻译、AI 图像功能、媒体链接下载等功能按应用内配置启用。

具体热键可在应用的「热键设置」中查看或修改；默认配置见 `Config.ini`。

## 运行（Windows）

建议使用 Python 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

全局热键依赖 `keyboard`（Windows）；OCR 依赖 `rapidocr-onnxruntime`。扫码为可选能力，需要时另行安装：

```powershell
pip install opencv-python-headless
```

## 构建 Windows EXE

仓库通过 GitHub Actions 工作流 `.github/workflows/build-exe.yml` 构建单文件 EXE。该工作流由 GitHub Actions 的 **Run workflow** 手动触发，使用 Python 3.12 和 PyInstaller。构建产物为 `KIVO.exe`。

## 项目结构

| 路径 | 用途 |
|---|---|
| `main.py` | 应用主程序 |
| `Config.ini` | 默认热键、界面及服务配置 |
| `Chinese.ini` / `English.ini` | 界面语言文件（源码运行时与打包版均支持） |
| `requirements.txt` | Python 运行依赖 |
| `KIVO.ico` | Windows 应用图标 |
| `ding.wav` | 提示音资源 |
| `.github/workflows/build-exe.yml` | Windows EXE 构建工作流 |

## 网络与隐私说明

- 基础的队列、截图、贴图和本地 OCR 功能可在本机完成。
- 翻译、AI 请求和媒体下载等联网功能会连接相应的第三方服务；使用 AI 图像功能时，所选图像/截图内容可能会发送到当前配置的 AI 服务处理。
- 服务 API Key 由应用保存到本机的 `Config.ini`。请妥善保护该文件，不要把包含真实密钥的配置提交到公开仓库。
- 下载或处理第三方平台内容前，请确认你拥有相应权限，并遵守平台条款及当地法律。

## 问题反馈

提交 Issue 时请注明 Windows 版本、Python 版本（如为源码运行）、复现步骤和相关日志。请先删除日志与配置中的个人信息、访问令牌和 API Key。
