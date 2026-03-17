#!/usr/bin/env python3
"""
将 Flask 应用打包成独立的可执行文件

支持的平台：
- Windows: .exe
- macOS: .app
- Linux: 可执行文件
"""

import PyInstaller.__main__
import os
import sys

# 配置
APP_NAME = "智能试卷视频生成器"
MAIN_SCRIPT = "app.py"
ICON = None  # 可以指定图标文件路径

# PyInstaller 参数
args = [
    MAIN_SCRIPT,
    '--name', APP_NAME,
    '--onefile',  # 打包成单个文件
    '--windowed',  # 不显示控制台窗口（Windows）
    '--noconsole',  # 不显示控制台（Windows）
    '--clean',  # 清理临时文件
    '--add-data', 'templates:templates',  # 包含模板目录
    '--add-data', 'requirements.txt:.',  # 包含依赖列表
]

# 如果有图标
if ICON and os.path.exists(ICON):
    args.extend(['--icon', ICON])

# 添加 Python 路径
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    # 在虚拟环境中
    args.extend(['--paths', sys.prefix])

# 平台特定配置
if sys.platform == 'darwin':  # macOS
    args.append('--onedir')  # macOS 推荐 .app 格式

print("=" * 60)
print(f"正在打包 {APP_NAME}...")
print("=" * 60)

# 执行打包
PyInstaller.__main__.run(args)

print("\n" + "=" * 60)
print("打包完成！")
print("=" * 60)
print("可执行文件位置:")
if sys.platform == 'win32':
    print(f"  dist/{APP_NAME}.exe")
elif sys.platform == 'darwin':
    print(f"  dist/{APP_NAME}.app/Contents/MacOS/{APP_NAME}")
else:
    print(f"  dist/{APP_NAME}")
