# SPST — 复制粘贴、截图贴图与效率工具

SPST（原 SnapPaste）是一个 Windows 桌面效率工具，将文本复制队列、截图标注、贴图和多种辅助工具整合到一个程序中。主程序目前为根目录的 `main.py`。

## 主要功能

- **文本队列**：多次复制、顺序粘贴、全部粘贴、分割导入、去重、锁定、常用语、文字转换。
- **截图与贴图**：区域截图、窗口吸附、截图历史、贴图缩放/移动/透明度、旋转和保存。
- **标注**：矩形、椭圆、箭头、线条、画笔、文字、马赛克/模糊，支持撤销。
- **OCR / 扫码**：识别图片文字或二维码/条码，结果可复制、翻译或加入文本队列。
- **辅助功能**：翻译、AI 图像翻译/智能回复、计算器、汇率、世界时钟、媒体下载等。
- **热键**：可自定义，设置界面可查看及修改。默认热键以软件当前配置为准。

## Windows 使用

### 直接运行 EXE
从 GitHub Releases 下载 `SPST.exe`，双击运行。Windows SmartScreen 若提示风险，请先确认文件来源可信，再决定是否运行。

### 从源码运行
建议使用 Python 3.12：

```powershell
py -3.12 -m venv .venv
.venv\\Scripts\\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

部分依赖/功能具有平台限制：全局热键主要面向 Windows；OCR、扫码、媒体下载等功能依赖对应组件。可选扫码引擎安装：

```powershell
pip install opencv-python-headless
```

## 从源码打包

仓库提供 GitHub Actions workflow：`.github/workflows/build-exe.yml`。在 GitHub Actions 页面手动触发 **Build SnapPaste EXE**，产物为 Windows 单文件程序。也可以本地安装 PyInstaller 后按 workflow 中的命令构建。

## 配置与数据

- `Config.ini`：默认配置模板。
- `Chinese.ini` / `English.ini`：界面语言文件；源码运行可从仓库根目录加载，打包程序使用内置资源。
- 截图、记录和其他用户数据会保存在应用数据目录中（具体路径由程序运行模式决定）。

**备份提醒：** 配置和备份可能包含你填写的 API Key、AI 对话及其他私人数据。请不要公开分享配置文件或备份文件。使用 AI/在线翻译/媒体下载等联网功能时，相关内容会发送到你选择的服务或网站；请先确认内容和服务的隐私政策。

## 项目文件

```
main.py
Config.ini
Chinese.ini
English.ini
requirements.txt
SPST.ico
ding.wav
.github/workflows/build-exe.yml
```

## 问题反馈

提交 Issue 时请附上软件版本、操作步骤和错误信息。请先移除日志、截图或配置中可能包含的个人信息、API Key、访问令牌等敏感内容。
