#!/usr/bin/env python3
"""下载 PaddleOCR 模型"""
import os
import urllib.request
import zipfile
from pathlib import Path

# 配置
MODEL_DIR = os.path.expanduser("~/.paddleocr/whl/det/ch/ch_pp-ocr_v4_det_infer")
REC_MODEL_DIR = os.path.expanduser("~/.paddleocr/whl/rec/ch/ch_pp-ocr_v4_rec_infer")
CLS_MODEL_DIR = os.path.expanduser("~/.paddleocr/whl/cls/ch_pp-ocr_mobile_v2.0_cls_infer")

BASE_URL = "https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese"

def download_file(url, dest):
    """下载文件"""
    print(f"下载: {url}")
    print(f"保存到: {dest}")
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"✓ 下载完成")

def extract_zip(zip_path, extract_dir):
    """解压文件"""
    print(f"解压: {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    print(f"✓ 解压完成")

print("=" * 60)
print("下载 PaddleOCR 模型")
print("=" * 60)

# 下载检测模型
det_url = f"{BASE_URL}/ch_PP-OCRv4_det_infer.tar"
det_zip = "/tmp/ch_PP-OCRv4_det_infer.tar"
det_extract_dir = os.path.expanduser("~/.paddleocr/whl/det/ch")

# 下载识别模型
rec_url = f"{BASE_URL}/ch_PP-OCRv4_rec_infer.tar"
rec_zip = "/tmp/ch_PP-OCRv4_rec_infer.tar"
rec_extract_dir = os.path.expanduser("~/.paddleocr/whl/rec/ch")

# 下载方向分类模型
cls_url = f"{BASE_URL}/ch_ppocr_mobile_v2.0_cls_infer.tar"
cls_zip = "/tmp/ch_ppocr_mobile_v2.0_cls_infer.tar"
cls_extract_dir = os.path.expanduser("~/.paddleocr/whl/cls")

try:
    # 创建目录
    Path(det_extract_dir).mkdir(parents=True, exist_ok=True)
    Path(rec_extract_dir).mkdir(parents=True, exist_ok=True)
    Path(cls_extract_dir).mkdir(parents=True, exist_ok=True)

    print("\n1/3 下载检测模型...")
    download_file(det_url, det_zip)

    print("\n2/3 下载识别模型...")
    download_file(rec_url, rec_zip)

    print("\n3/3 下载方向分类模型...")
    download_file(cls_url, cls_zip)

    print("\n" + "=" * 60)
    print("所有模型下载完成！")
    print("=" * 60)

except Exception as e:
    print(f"\n✗ 下载失败: {e}")
    sys.exit(1)
