# 打包成可执行文件

## 安装打包工具

```bash
pip install pyinstaller
```

## 打包步骤

### 方式一：直接使用 PyInstaller

```bash
pyinstaller --name "智能试卷视频生成器" --onefile --windowed --add-data "templates;templates" app.py
```

### 方式二：使用打包脚本（推荐）

```bash
python build_exe.py
```

## 打包参数说明

- `--name`: 应用名称
- `--onefile`: 打包成单个文件
- `--windowed` / `--noconsole`: 不显示控制台窗口（Windows）
- `--add-data`: 包含额外文件（模板目录）
- `--icon`: 指定图标文件

## 打包后的文件

### Windows
- 输出: `dist/智能试卷视频生成器.exe`
- 双击运行即可

### macOS
- 输出: `dist/智能试卷视频生成器.app`
- 双击运行即可

### Linux
- 输出: `dist/智能试卷视频生成器`
- 执行: `./智能试卷视频生成器`

## 注意事项

1. **首次运行**: 打包后的程序首次运行需要下载 OCR 模型，请确保网络连接
2. **文件大小**: 打包后的文件约 500MB-1GB（包含所有依赖）
3. **跨平台**: Windows 打包的 exe 只能在 Windows 运行，需要在其他平台运行需重新打包
4. **临时文件**: OCR 模型会下载到 `~/.EasyOCR/` 目录
5. **端口占用**: 默认使用 5010 端口，如果被占用需要修改源码中的端口号

## 自定义配置

### 修改端口号
编辑 `app.py` 最后一行：
```python
app.run(debug=True, host='0.0.0.0', port=5010)  # 改为你想要的端口
```

### 添加图标
准备一个 `.ico`（Windows）或 `.icns`（macOS）图标文件，修改 `build_exe.py`：
```python
ICON = "your_icon.ico"  # 或 your_icon.icns
```

## 分发

打包后的文件可以直接发送给其他用户使用，无需安装 Python 环境。

### Windows 用户
只需 `dist/智能试卷视频生成器.exe` 一个文件即可运行

### macOS 用户
需将 `dist/智能试卷视频生成器.app` 整个文件夹打包发送

## 常见问题

### Q: 打包失败？
A: 确保安装了所有依赖：`pip install -r requirements_build.txt`

### Q: 运行时找不到模板？
A: 检查 `--add-data` 参数是否正确，Windows 用分号 `;`，macOS/Linux 用冒号 `:`

### Q: OCR 模型下载失败？
A: 打包的程序首次运行需要联网，检查网络连接或代理设置
