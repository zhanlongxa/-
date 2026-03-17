#!/usr/bin/env python3
"""
macOS Application Packaging Script
Packages the Smart Caption Video Generator into a standalone .app bundle
"""

import PyInstaller.__main__
import os
import sys
import shutil

# Configuration
APP_NAME = "Smart Caption Studio"
MAIN_SCRIPT = "launcher.py"  # Use launcher instead of app.py directly
ICON = None  # Can specify .icns file if available

print("=" * 60)
print(f"📦 Packaging {APP_NAME} for macOS")
print("=" * 60)

# Step 1: Check dependencies
print("\n[1/4] Checking PyInstaller installation...")
try:
    import PyInstaller
    print(f"✓ PyInstaller {PyInstaller.__version__} found")
except ImportError:
    print("✗ PyInstaller not found. Installing...")
    os.system("pip3 install pyinstaller")

# Step 2: Prepare data files
print("\n[2/4] Preparing data files...")

# Find EasyOCR model directory
home = os.path.expanduser("~")
easyocr_model_dir = os.path.join(home, ".EasyOCR", "model")
paddleocr_model_dir = os.path.join(home, ".paddleocr")

data_files = []

# Add templates
if os.path.exists("templates"):
    data_files.append(("templates", "templates"))
    print("✓ Templates directory found")

# Add EasyOCR models if available
if os.path.exists(easyocr_model_dir):
    data_files.append((easyocr_model_dir, ".EasyOCR/model"))
    print(f"✓ EasyOCR models found: {easyocr_model_dir}")
else:
    print("⚠ EasyOCR models not found - will download on first run")

# Add PaddleOCR models if available
if os.path.exists(paddleocr_model_dir):
    data_files.append((paddleocr_model_dir, ".paddleocr"))
    print(f"✓ PaddleOCR models found: {paddleocr_model_dir}")

# Step 3: Build PyInstaller arguments
print("\n[3/4] Configuring PyInstaller...")

args = [
    MAIN_SCRIPT,
    '--name', APP_NAME,
    '--onedir',  # Create .app bundle (better for large apps)
    '--clean',  # Clean build
    '--noconfirm',  # Overwrite without asking
]

# Add data files
for src, dst in data_files:
    args.extend(['--add-data', f'{src}:{dst}'])

# Add hidden imports for OCR and dependencies
hidden_imports = [
    'easyocr',
    'paddleocr',
    'PIL._tkinter_finder',
    'sklearn.utils._cython_blas',
    'sklearn.neighbors.typedefs',
    'sklearn.neighbors.quad_tree',
    'sklearn.tree._utils',
    'moviepy.config',
    'moviepy.video.io.ffmpeg_reader',
    'edge_tts',
]

for imp in hidden_imports:
    args.extend(['--hidden-import', imp])

# Copy metadata for packages that need it (fixes importlib.metadata errors)
metadata_packages = [
    'imageio',
    'imageio-ffmpeg',
    'moviepy',
    'pillow',
    'numpy',
]

for pkg in metadata_packages:
    args.extend(['--copy-metadata', pkg])

# Add icon if available
if ICON and os.path.exists(ICON):
    args.extend(['--icon', ICON])

# Step 4: Run PyInstaller
print("\n[4/4] Building application...")
print("This may take several minutes...\n")

try:
    PyInstaller.__main__.run(args)
    
    print("\n" + "=" * 60)
    print("✅ Build completed successfully!")
    print("=" * 60)
    print(f"\n📍 Application location:")
    print(f"   dist/{APP_NAME}.app")
    print(f"\n🚀 To run:")
    print(f"   open dist/{APP_NAME}.app")
    print(f"\n📦 To distribute:")
    print(f"   1. Test the app: open dist/{APP_NAME}.app")
    print(f"   2. Create DMG: hdiutil create -volname '{APP_NAME}' -srcfolder dist/{APP_NAME}.app -ov -format UDZO {APP_NAME}.dmg")
    print(f"   3. Share the DMG file")
    
except Exception as e:
    print("\n" + "=" * 60)
    print("❌ Build failed!")
    print("=" * 60)
    print(f"Error: {e}")
    sys.exit(1)
