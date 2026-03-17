import os
import uuid
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ImageOps
import numpy as np
from moviepy.editor import ImageClip, CompositeVideoClip, AudioFileClip
from moviepy.audio.AudioClip import AudioArrayClip
import edge_tts
import subprocess
import sys

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'pdf'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 关键优化：限制 CPU 线程数，防止 OCR 占满所有核导致系统卡顿
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# 初始化 OCR 引擎
print("\n" + "="*60)
print("正在初始化 OCR 引擎...")
print("="*60)

ocr = None
ocr_method = 'mock'

# 方案 1: 优先尝试 EasyOCR (用户指定)
print("\n[1/2] 尝试初始化 EasyOCR...")
try:
    from easyocr import Reader

    try:
        # 使用轻量配置
        ocr = Reader(['ch_sim', 'en'], gpu=False, verbose=False)
        ocr_method = 'easyocr'
        print("✓ EasyOCR 初始化成功！")
    except Exception as e:
        print(f"✗ EasyOCR 初始化失败: {str(e)[:100]}")

except ImportError:
    print("✗ EasyOCR 模块未安装")

# 方案 2: 备选方案 PaddleOCR
if ocr_method == 'mock':
    print("\n[2/2] 尝试初始化 PaddleOCR...")
    try:
        from paddleocr import PaddleOCR
    
        try:
            ocr = PaddleOCR(use_angle_cls=True, lang='ch')
            ocr_method = 'paddle'
            print("✓ PaddleOCR 初始化成功！")
        except Exception as e:
            print(f"✗ PaddleOCR 初始化失败: {str(e)[:100]}")
    except ImportError:
            print("✗ PaddleOCR 模块未安装")

# 方案 2: 备选方案 EasyOCR
if ocr_method == 'mock':
    print("\n[2/2] 尝试初始化 EasyOCR...")
    try:
        from easyocr import Reader

        try:
            # 使用轻量配置
            ocr = Reader(['ch_sim', 'en'], gpu=False, verbose=False)
            ocr_method = 'easyocr'
            print("✓ EasyOCR 初始化成功！")
        except Exception as e:
            print(f"✗ EasyOCR 初始化失败: {str(e)[:100]}")

    except ImportError:
        print("✗ EasyOCR 模块未安装")

if ocr_method == 'mock':
    print("\n" + "!"*60)
    print("⚠️  所有 OCR 引擎初始化失败，将使用模拟模式")
    print("!"*60)
    print("\n解决方案：")
    print("1. 重启服务（首次运行需要下载模型，可能需要几分钟）")
    print("2. 检查网络连接（模型需要从 GitHub 下载）")
    print("3. 手动安装依赖：pip install --upgrade paddleocr paddlepaddle")
    print("4. 清理模型缓存后重试：rm -rf ~/.paddleocr ~/.paddlex")
else:
    print("\n" + "="*60)
    print(f"✓ OCR 引擎就绪！使用: {ocr_method}")
    print("="*60)

print()

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

tasks = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_task_id():
    return str(uuid.uuid4())

def save_task(task_id, data):
    tasks[task_id] = data

def get_task(task_id):
    return tasks.get(task_id)

def detect_keywords_paddle(image_path, keywords):
    """使用 PaddleOCR 检测关键词"""
    matches = []

    import gc
    
    # --- 全局预处理：强制标准化 (尺寸 & EXIF 旋转) ---
    # 无论使用哪个 OCR 引擎，都必须先保证图片 "所见即所得"
    try:
        img_chk = Image.open(image_path)
        try:
            img_chk = ImageOps.exif_transpose(img_chk)
        except Exception as e:
            print(f"[OCR] EXIF 旋转处理失败 (非关键): {e}")

        max_side = 1280 
        needs_save = True # 强制保存

        if max(img_chk.size) > max_side:
            print(f"[OCR] 图片尺寸 {img_chk.size} 过大，正在压缩至 {max_side}px...")
            ratio = max_side / max(img_chk.size)
            new_size = (int(img_chk.size[0] * ratio), int(img_chk.size[1] * ratio))
            img_chk = img_chk.resize(new_size, Image.LANCZOS)
        
        # 总是保存处理后的图片 (覆盖原图或另存)
        # 这一步是修复 "错位" 的核心：保证磁盘文件 = 内存文件
        if needs_save:
            img_chk.save(image_path)
            print(f"[OCR] 图片已标准化并保存: {image_path}")
            
    except Exception as e:
        print(f"[OCR] 图片预处理失败: {e}")

    if ocr_method == 'paddle' and ocr:
        try:
            print(f"[OCR] PaddleOCR 识别中...")
            
            # (已移动到上方全局处理)

            # 2. 调用 OCR
            # 显式限制检测边长
            # 显式限制检测边长
            result = ocr.ocr(image_path)

            if result and result[0]:
                # PaddleOCR / PaddleX new return format (dict-like)
                # Check for keys 'dt_polys', 'rec_texts', 'rec_scores'
                first_res = result[0]
                
                # Normalize data source
                details = []
                
                # Check if it behaves like a dict (PaddleX OCRResult)
                if hasattr(first_res, 'keys') and 'dt_polys' in first_res and 'rec_texts' in first_res:
                    boxes = first_res['dt_polys']
                    texts = first_res['rec_texts']
                    scores = first_res['rec_scores']
                    
                    for box, text, score in zip(boxes, texts, scores):
                        details.append((box, text, score))
                        
                # Old format (list of [box, (text, score)])
                elif isinstance(first_res, list):
                     for item in first_res:
                         # item: [[x,y...], ('text', score)]
                         box = item[0]
                         text = item[1][0]
                         score = item[1][1]
                         details.append((box, text, score))

                # Process standardized details
                for box, text, confidence in details:
                    # 1. 置信度过滤
                    if confidence < 0.5:
                        print(f"[OCR] 忽略低置信度: {text} ({confidence:.2f})")
                        continue

                    print(f"[OCR] 识别: {text} (置信度: {confidence:.2f})")

                    for keyword in keywords:
                        if keyword in text:
                            # Calculate bounding box (x1, y1, x2, y2)
                            # box can be list of points or numpy array
                            import numpy as np
                            pts = np.array(box)
                            x_coords = pts[:, 0]
                            y_coords = pts[:, 1]
                            
                            line_x1, line_y1 = int(np.min(x_coords)), int(np.min(y_coords))
                            line_x2, line_y2 = int(np.max(x_coords)), int(np.max(y_coords))

                            # 2. 噪点过滤 (面积过小)
                            area = (line_x2 - line_x1) * (line_y2 - line_y1)
                            if area < 100:
                                print(f"[OCR] 忽略噪点 (大小 {area}): {text}")
                                continue
                            
                            # 3. 智能短句高亮逻辑 (已禁用)
                            # 原因：当 OCR 将多行文本识别为同一个框时 (如 标题+正文)，
                            # 简单的线性插值会导致下划线画在段落底部，且位置错乱。
                            # 暂时回归到 "所见即所得" 的整框高亮模式，保证位置绝对准确。
                            # 
                            # pts = np.array(box).reshape(4, 2)
                            # p0, p1, p2, p3 = pts[0], pts[1], pts[2], pts[3]
                            # try:
                            #     import re
                            #     # 定义句子分隔符 (中英文标点)
                            #     delimiters = r'[，。；：！？,.;:!\?\s]'
                            #     # 切分文本，保留分隔符以便计算位置
                            #     # 但为了简单，我们直接搜索关键词前后的分隔符位置
                                
                            #     full_len = len(text)
                            #     kw_start = text.find(keyword)
                                
                            #     if full_len > 0 and kw_start != -1:
                            #         # 向前寻找开始位置
                            #         clause_start = kw_start
                            #         while clause_start > 0:
                            #             if re.match(delimiters, text[clause_start - 1]):
                            #                 break
                            #             clause_start -= 1
                                    
                            #         # 向后寻找结束位置
                            #         clause_end = kw_start + len(keyword)
                            #         while clause_end < full_len:
                            #             if re.match(delimiters, text[clause_end]):
                            #                 break
                            #             clause_end += 1
                                        
                            #         print(f"[OCR] 关键词 '{keyword}' 所在短句: {text[clause_start:clause_end]}")
                                    
                            #         # Vector-based interpolation (Preserve Rotation)
                            #         def get_weighted_len(s):
                            #             l = 0
                            #             for char in s:
                            #                 # Simple heuristic: ASCII 0.6, Others (CN) 1.0
                            #                 if ord(char) < 128:
                            #                     l += 0.6
                            #                 else:
                            #                     l += 1.0
                            #             return l

                            #         total_weight = get_weighted_len(text)
                            #         start_weight = get_weighted_len(text[:clause_start])
                            #         clause_weight = get_weighted_len(text[clause_start:clause_end])
                                    
                            #         if total_weight > 0:
                            #             # Use original 4 points (usually TL, TR, BR, BL order from Paddle)
                            #             # Ensure it's a numpy array of shape (4, 2)
                            #             pts = np.array(box).reshape(4, 2)
                            #             p0, p1, p2, p3 = pts[0], pts[1], pts[2], pts[3]

                            #             ratio_start = start_weight / total_weight
                            #             ratio_end = (start_weight + clause_weight) / total_weight

                            #             # Limit ratios
                            #             ratio_start = max(0.0, min(1.0, ratio_start))
                            #             ratio_end = max(0.0, min(1.0, ratio_end))

                            #             # Interpolate Top Edge (p0 -> p1)
                            #             new_p0 = p0 + (p1 - p0) * ratio_start
                            #             new_p1 = p0 + (p1 - p0) * ratio_end

                            #             # Interpolate Bottom Edge (p3 -> p2)
                            #             # Note: Paddle standard order is TL, TR, BR, BL. 
                            #             # So Bottom Edge is p3(BL) -> p2(BR)
                            #             new_p3 = p3 + (p2 - p3) * ratio_start
                            #             new_p2 = p3 + (p2 - p3) * ratio_end

                            #             final_box = [new_p0.tolist(), new_p1.tolist(), new_p2.tolist(), new_p3.tolist()]
                            #         else:
                            #             final_box = box # Fallback to full box
                            #     else:
                            #         final_box = box # Fallback to full box

                            # except Exception as e:
                            #     print(f"计算短句位置失败: {e}, 使用整行框")
                            #     final_box = [line_x1, line_y1, line_x2, line_y2]
                            # Ensure clean python types for JSON serialization (handle numpy types)
                            # 3. 回退到稳定逻辑: 整行高亮
                            # 用户反馈切词逻辑 (Word Slicing) 效果极差 (位置不准)
                            # 原因：字符宽度估算无法处理复杂字体和中英混排
                            # 策略：高亮包含关键词的 "整行/整句"，保证 100% 覆盖正确
                            final_box = box

                            # Ensure clean python types for JSON serialization (handle numpy types)
                            clean_box = []
                            for p in final_box:
                                clean_box.append([int(p[0]), int(p[1])])
                            
                            matches.append({
                                'keyword': keyword,
                                'text': text,
                                'confidence': round(confidence, 2),
                                'box': clean_box
                            })
                            print(f"[匹配] ✓ 找到 '{keyword}'")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[OCR] PaddleOCR 识别失败: {e}")
        finally:
            gc.collect()

    elif ocr_method == 'easyocr' and ocr:
        try:
            print(f"[OCR] EasyOCR 识别中...")
            result = ocr.readtext(image_path)

            for detection in result:
                box = detection[0]
                text = detection[1]
                confidence = detection[2]

                # 1. 置信度过滤
                if confidence < 0.4: # EasyOCR 分数通常偏低
                     print(f"[OCR] 忽略低置信度: {text} ({confidence:.2f})")
                     continue

                print(f"[OCR] 识别: {text} (置信度: {confidence:.2f})")

                for keyword in keywords:
                    if keyword in text:
                        x_coords = [p[0] for p in box]
                        y_coords = [p[1] for p in box]
                        x1, y1, x2, y2 = min(x_coords), min(y_coords), max(x_coords), max(y_coords)
                        
                        # 2. 噪点过滤
                        area = (x2 - x1) * (y2 - y1)
                        if area < 100:
                            continue

                        # Convert box points to int lists for JSON serialization
                        final_box = [[int(p[0]), int(p[1])] for p in box]
                        
                        matches.append({
                            'keyword': keyword,
                            'text': text,
                            'confidence': round(confidence, 2),
                            'box': final_box
                        })
                        print(f"[匹配] ✓ 找到 '{keyword}'")

        except Exception as e:
            print(f"[OCR] EasyOCR 识别失败: {e}")

    else:
        # 模拟模式
        print("[OCR] 使用模拟模式")
        img = Image.open(image_path)
        width, height = img.size
        center_x = width // 2
        center_y = height // 2

        for idx, keyword in enumerate(keywords):
            offset_y = idx * 150
            x1 = center_x - 150
            y1 = center_y - 100 + offset_y
            x2 = center_x + 150
            y2 = center_y + 50 + offset_y

            matches.append({
                'keyword': keyword,
                'text': f'【{keyword}】',
                'confidence': 0.95,
                'box': [x1, y1, x2, y2]
            })

    print(f"[OCR] 匹配数: {len(matches)}")
    return matches

def create_annotated_image(image_path, matches):
    img = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(img)

    # 优雅的颜色方案
    colors = [
        (220, 53, 69, 230),    # 红色 - 亮红色
        (25, 135, 84, 230),    # 绿色 - 深绿色
        (13, 110, 253, 230),   # 蓝色 - 亮蓝色
        (255, 193, 7, 230),    # 黄色 - 金黄色
        (123, 31, 162, 230),   # 紫色 - 深紫色
        (244, 63, 94, 230),    # 橙色 - 亮橙色
        (23, 162, 184, 230)    # 青色 - 深青色
    ]

    for idx, match in enumerate(matches):
        box = match['box']
        keyword = match['keyword']
        color = colors[idx % len(colors)]

        x1, y1, x2, y2 = box
        padding = 12

        # 创建标记层
        marker_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
        marker_draw = ImageDraw.Draw(marker_img)

        # --- 荧光笔电影模式 (Cinematic Marker) ---
        # 1. 统一获取 AABB (即使是多边形也取外接矩形，保证形状规整)
        if len(box) == 4 and isinstance(box[0], list):
             pts = np.array(box)
             x1, y1 = np.min(pts, axis=0)
             x2, y2 = np.max(pts, axis=0)
        else:
             x1, y1, x2, y2 = box

        # 2. 计算样式参数
        text_height = y2 - y1
        padding_x = 10  # 增加水平宽容度
        padding_y = 4   # 增加垂直宽容度
        radius = 8      # 圆角更大一点

        print(f"[Mark] idx={idx} key={match['keyword']} box={box} -> x1={x1},y1={y1},x2={x2},y2={y2}")

        # 3. 绘制高亮色块 (Highlighter)
        marker_draw.rounded_rectangle(
            [x1 - padding_x, y1 - padding_y, x2 + padding_x, y2 + padding_y],
            radius=radius,
            fill=(*color[:3], 130),
            outline=None
        )

        


        # 合并到原图
        img.paste(Image.alpha_composite(img.convert('RGBA'), marker_img).convert('RGB'))
        draw = ImageDraw.Draw(img)

        # 添加序号标签 - 精美设计
        try:
            # 尝试加载中文字体（指定字体索引）
            font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 22, index=0)
            font_bold = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 22, index=0)
        except:
            try:
                # 备选方案：黑体
                font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 22)
                font_bold = font
            except:
                try:
                    # 备选方案：Arial Unicode MS（支持中文）
                    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 22)
                    font_bold = font
                except:
                    font = ImageFont.load_default()
                    font_bold = font

        label_text = f"{idx + 1}"
        label_bbox = draw.textbbox((0, 0), label_text, font=font)
        label_width = label_bbox[2] - label_bbox[0]
        label_height = label_bbox[3] - label_bbox[1]

        # 标签位置 - 左上角，适中距离
        label_x, label_y = x1 - padding, y1 - padding

        # 标签背景
        label_overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        label_draw = ImageDraw.Draw(label_overlay)
        
        # 精美的圆角标签
        label_padding = 6
        label_w = label_width + label_padding * 2
        label_h = label_height + label_padding * 2

        # 标签阴影
        label_draw.rounded_rectangle(
            [label_x + 1, label_y + 1, label_x + label_w + 1, label_y + label_h + 1],
            radius=8,
            fill=(0, 0, 0, 80)
        )

        # 标签主体 - 增加透明度
        label_draw.rounded_rectangle(
            [label_x, label_y, label_x + label_w, label_y + label_h],
            radius=8,
            fill=(*color[:3], 120),  # 增加透明度
            outline=(*color[:3], 180),  # 边框也增加透明度
            width=2
        )

        img.paste(Image.alpha_composite(img.convert('RGBA'), label_overlay).convert('RGB'))
        draw = ImageDraw.Draw(img)

        # 标签文字
        text_x = label_x + (label_w - label_width) // 2
        text_y = label_y + (label_h - label_height) // 2 - 2
        draw.text((text_x, text_y), label_text, fill='white', font=font)

        # 在框内添加关键词提示
        try:
            # 指定字体索引以正确加载中文字体
            hint_font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 16, index=0)
        except:
            try:
                # 备选方案：黑体
                hint_font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 16)
            except:
                try:
                    # 备选方案：Arial Unicode MS
                    hint_font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 16)
                except:
                    hint_font = ImageFont.load_default()

        # 只显示关键词的前几个字，避免太长
        hint_text = keyword[:10] + "..." if len(keyword) > 10 else keyword
        hint_bbox = draw.textbbox((0, 0), hint_text, font=hint_font)
        hint_width = hint_bbox[2] - hint_bbox[0]

        # 关键词标签 - 放在框底部，更紧凑
        hint_y = y2 + padding + 3
        hint_x = x1 + (x2 - x1) // 2 - hint_width // 2

        hint_overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        hint_draw = ImageDraw.Draw(hint_overlay)

        hint_w = hint_width + 12
        hint_h = hint_bbox[3] - hint_bbox[1] + 8

        # 关键词标签阴影
        hint_draw.rounded_rectangle(
            [hint_x + 1, hint_y + 1, hint_x + hint_w + 1, hint_y + hint_h + 1],
            radius=6,
            fill=(0, 0, 0, 70)
        )

        # 关键词标签主体 - 增加透明度
        hint_draw.rounded_rectangle(
            [hint_x, hint_y, hint_x + hint_w, hint_y + hint_h],
            radius=6,
            fill=(255, 255, 255, 100),  # 增加透明度
            outline=(*color[:3], 150),  # 边框增加透明度
            width=1
        )

        img.paste(Image.alpha_composite(img.convert('RGBA'), hint_overlay).convert('RGB'))
        draw = ImageDraw.Draw(img)

        draw.text((hint_x + 6, hint_y + 2), hint_text, fill=color[:3], font=hint_font)

    output_path = os.path.join(OUTPUT_FOLDER, f"annotated_{uuid.uuid4()}.jpg")
    img.save(output_path, quality=95, subsampling=0, optimize=True)
    return output_path

def create_silence_audio(duration, sample_rate=44100):
    silence = AudioArrayClip(np.zeros((int(duration * sample_rate), 1)), fps=sample_rate)
    return silence


async def generate_tts(text, voice="zh-CN-XiaoxiaoNeural"):
    """生成 TTS 语音 (Edge-TTS -> macOS 'say')"""
    try:
        # 1. 优先尝试 Edge-TTS
        communicate = edge_tts.Communicate(text, voice)
        output_path = os.path.join(OUTPUT_FOLDER, f"tts_{uuid.uuid4()}.mp3")
        await communicate.save(output_path)
        audio = AudioFileClip(output_path)
        print(f"[TTS] 成功生成语音 (Edge-TTS): {voice}")
        return audio
    except Exception as e:
        print(f"[TTS] Edge-TTS 失败: {e}")
        
        # 2. 失败后尝试 macOS 本地语音
        if sys.platform == 'darwin':
            try:
                print(f"[TTS] 尝试使用 macOS 本地语音...")
                output_path = os.path.join(OUTPUT_FOLDER, f"tts_mac_{uuid.uuid4()}.m4a")
                # 使用 'say' 命令，-o 输出文件，默认语音
                subprocess.run(['say', text, '-o', output_path], check=True)
                
                audio = AudioFileClip(output_path)
                print(f"[TTS] 成功生成语音 (macOS Native)")
                return audio
            except Exception as mac_e:
                print(f"[TTS] macOS 本地语音失败: {mac_e}")
        
        return None


def create_video(image_path, matches, voice_text, highlight_time=2.8, use_silent=True):
    img = Image.open(image_path).convert('RGB')
    img_array = np.array(img)
    bg_clip = ImageClip(img_array)

    # 1. 计算所需的最小视频时长
    # 每个关键词展示 3 秒 + 初始等待 1 秒 + 结尾缓冲 2 秒
    time_per_match = 3.0
    initial_delay = 1.0
    min_video_duration = initial_delay + len(matches) * time_per_match + 2.0
    
    print(f"[视频] 匹配数: {len(matches)}")
    print(f"[视频] 建议最小时长: {min_video_duration:.2f}s")

    audio = None
    if use_silent:
        print("[视频] 使用静音模式")
        audio = create_silence_audio(min_video_duration)
    else:
        # 尝试使用TTS生成语音
        if voice_text:
            print(f"[视频] 尝试生成TTS语音...")
            audio = asyncio.run(generate_tts(voice_text))
            
            if audio is None:
                print("[视频] TTS失败，使用静音")
                audio = create_silence_audio(min_video_duration)
            else:
                # 如果语音比画面短，延长音频（填充静音）
                if audio.duration < min_video_duration:
                    print(f"[视频] 语音时长 ({audio.duration:.2f}s) 小于画面时长，自动延长")
                    silence_padding = create_silence_audio(min_video_duration - audio.duration)
                    # 注意：moviepy 的音频拼接
                    from moviepy.editor import CompositeAudioClip
                    # 这里简单处理，直接设为该时长，不足部分会默认循环或无声，
                    # 更好的方式是创建一个新的静音clip作为底槽，把TTS叠加上去
                    # 简化：使用 set_duration，但这通常loop音频。
                    # 我们用 CompositeAudioClip 拼接静音补白
                    # audio = concatenate_audioclips([audio, silence_padding]) # 需要 import
                    # 简单修复：生成一段足够长的静音，把TTS合成上去
                    silence_bg = create_silence_audio(min_video_duration)
                    audio = CompositeAudioClip([audio.set_start(0), silence_bg.set_start(0)])
                    audio = audio.set_duration(min_video_duration)
        else:
            audio = create_silence_audio(min_video_duration)

    video_duration = audio.duration
    print(f"[视频] 最终视频时长: {video_duration:.2f}s")
    
    bg_clip = bg_clip.set_duration(video_duration)

    clips = [bg_clip]
    colors = [
        (220, 53, 69, 180),    # 红色
        (25, 135, 84, 180),    # 绿色
        (13, 110, 253, 180),   # 蓝色
        (255, 193, 7, 180),    # 黄色
        (123, 31, 162, 180),   # 紫色
        (244, 63, 94, 180),    # 橙色
        (23, 162, 184, 180)    # 青色
    ]

    for idx, match in enumerate(matches):
        box = match['box']
        padding = 12

        # 计算该 mask 的出现时间 (顺序播放)
        # 第一个在 initial_delay 出现
        start_time = initial_delay + idx * time_per_match
        
        # 持续时间
        duration = 2.5 # 每个显示 2.5 秒
        
        print(f"  - 关键词 '{match['keyword']}' (槽位 {idx}): {start_time:.1f}s -> {start_time+duration:.1f}s")

        # 创建标记层
        marker_img = Image.new('RGBA', (img_array.shape[1], img_array.shape[0]), (0, 0, 0, 0))
        marker_draw = ImageDraw.Draw(marker_img)

        color = colors[idx % len(colors)]
        
        # --- 视频版荧光笔模式 ---
        # 1. 获取坐标
        if len(box) == 4 and isinstance(box[0], list):
            pts = np.array(box)
            x1, y1 = np.min(pts, axis=0)
            x2, y2 = np.max(pts, axis=0)
        else:
            x1, y1, x2, y2 = box
            
        # 2. 绘制高亮
        padding_x = 10
        padding_y = 4
        
        marker_draw.rounded_rectangle(
            [x1 - padding_x, y1 - padding_y, x2 + padding_x, y2 + padding_y],
            radius=6,
            fill=(*color[:3], 130), # 保持一致的透明度
            outline=None
        )
        


        # 添加序号标签
        try:
            label_font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 22)
        except:
            label_font = ImageFont.load_default()

        label_text = f"{idx + 1}"
        label_bbox = marker_draw.textbbox((0, 0), label_text, font=label_font)
        label_width = label_bbox[2] - label_bbox[0]
        label_height = label_bbox[3] - label_bbox[1]

        # 序号标签位置
        label_x = x1 - padding
        label_y = y1 - padding

        label_padding = 6
        label_w = label_width + label_padding * 2
        label_h = label_height + label_padding * 2

        # 序号标签阴影
        marker_draw.rounded_rectangle(
            [label_x + 1, label_y + 1, label_x + label_w + 1, label_y + label_h + 1],
            radius=8,
            fill=(0, 0, 0, 60)
        )

        # 序号标签主体
        marker_draw.rounded_rectangle(
            [label_x, label_y, label_x + label_w, label_y + label_h],
            radius=8,
            fill=(*color[:3], 120),
            outline=(*color[:3], 180),
            width=2
        )

        # 序号标签文字
        text_x = label_x + (label_w - label_width) // 2
        text_y = label_y + (label_h - label_height) // 2 - 2
        marker_draw.text((text_x, text_y), label_text, fill=(255, 255, 255, 220), font=label_font)

        # 添加关键词提示
        keyword = match['keyword']
        hint_text = keyword[:10] + "..." if len(keyword) > 10 else keyword

        try:
            hint_font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 16)
        except:
            hint_font = ImageFont.load_default()

        hint_bbox = marker_draw.textbbox((0, 0), hint_text, font=hint_font)
        hint_width = hint_bbox[2] - hint_bbox[0]

        # 关键词标签位置
        hint_y = y2 + padding + 3
        hint_x = x1 + (x2 - x1) // 2 - hint_width // 2

        hint_w = hint_width + 12
        hint_h = hint_bbox[3] - hint_bbox[1] + 8

        # 关键词标签阴影
        marker_draw.rounded_rectangle(
            [hint_x + 1, hint_y + 1, hint_x + hint_w + 1, hint_y + hint_h + 1],
            radius=6,
            fill=(0, 0, 0, 60)
        )

        # 关键词标签主体
        marker_draw.rounded_rectangle(
            [hint_x, hint_y, hint_x + hint_w, hint_y + hint_h],
            radius=6,
            fill=(255, 255, 255, 100),
            outline=(*color[:3], 150),
            width=1
        )

        # 关键词标签文字
        marker_draw.text((hint_x + 6, hint_y + 2), hint_text, fill=(*color[:3], 220), font=hint_font)

        marker_clip = ImageClip(np.array(marker_img)) \
            .set_start(start_time) \
            .set_duration(video_duration - start_time) \
            .crossfadein(0.5)
            # .crossfadeout(0.4) # 取消消失动画，让其一直保留

        clips.append(marker_clip)

    final_video = CompositeVideoClip(clips)
    final_video = final_video.set_audio(audio)

    output_path = os.path.join(OUTPUT_FOLDER, f"video_{uuid.uuid4()}.mp4")
    final_video.write_videofile(output_path, fps=24, codec="libx264", preset='fast', threads=4, logger=None)

    return output_path, final_video.duration

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件格式'}), 400

    task_id = generate_task_id()
    
    # Fix: secure_filename might strip Chinese characters and break extension
    # We use UUID + original extension to ensure safety and compatibility
    ext = os.path.splitext(file.filename)[1].lower()
    if not ext:
        ext = '.jpg' # Default fallback
        
    filename = f"{task_id}{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # 如果是 PDF，自动转换为图片 (只取第一页)
    if ext == '.pdf':
        try:
            import fitz  # PyMuPDF
            print(f"[PDF] 正在转换: {filepath}")
            doc = fitz.open(filepath)
            if len(doc) > 0:
                page = doc[0] # First page
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # 2x zoom for better quality
                
                # Update filename to .png
                filename = f"{task_id}.png"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                pix.save(filepath)
                print(f"[PDF] 转换成功: {filepath}")
            else:
                return jsonify({'error': 'PDF 文件为空'}), 400
            doc.close()
        except ImportError:
            print("[PDF] 缺少 pymupdf 库，无法转换 PDF")
            return jsonify({'error': '服务器缺少 PDF 支持库 (pymupdf)'}), 500
        except Exception as e:
            print(f"[PDF] 转换失败: {e}")
            return jsonify({'error': f'PDF 转换失败: {str(e)}'}), 500

    save_task(task_id, {
        'status': 'uploaded',
        'filepath': filepath,
        'filename': file.filename,
        'created_at': datetime.now().isoformat(),
        'matches': [],
        'video_path': None
    })

    return jsonify({
        'task_id': task_id,
        'filename': file.filename,
        'message': '上传成功'
    })

@app.route('/api/ocr', methods=['POST'])
def ocr_detect():
    data = request.json
    task_id = data.get('task_id')
    keywords = data.get('keywords', [])

    if not task_id:
        return jsonify({'error': '缺少 task_id'}), 400

    task = get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    print(f"\n{'='*60}")
    print(f"[OCR] 开始识别")
    print(f"[OCR] 引擎: {ocr_method}")
    print(f"[OCR] 任务ID: {task_id}")
    print(f"[OCR] 关键词: {keywords}")
    print(f"[OCR] 图片: {task['filepath']}")
    print('='*60)

    matches = detect_keywords_paddle(task['filepath'], keywords)
    task['matches'] = matches
    task['status'] = 'ocr_completed'

    if matches:
        print(f"\n[OCR] 正在创建标注图片...")
        annotated_path = create_annotated_image(task['filepath'], matches)
        task['annotated_path'] = annotated_path
        print(f"[OCR] 标注图片: {annotated_path}")

    print(f"[OCR] 处理完成，返回 {len(matches)} 个匹配\n")

    return jsonify({
        'task_id': task_id,
        'matches': matches,
        'annotated_url': f'/download/{os.path.basename(task["annotated_path"])}' if matches else None,
        'message': f'识别完成，找到 {len(matches)} 个关键词'
    })

@app.route('/api/video', methods=['POST'])
def generate_video_api():
    data = request.json
    task_id = data.get('task_id')
    voice_text = data.get('voice_text', '')
    highlight_time = data.get('highlight_time', 2.8)
    use_silent = data.get('use_silent', True)

    if not task_id:
        return jsonify({'error': '缺少 task_id'}), 400

    task = get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    if not task['matches']:
        return jsonify({'error': '没有可圈画的关键词'}), 400

    task['status'] = 'processing'

    try:
        video_path, duration = create_video(
            task['filepath'],
            task['matches'],
            voice_text,
            highlight_time,
            use_silent
        )

        task['video_path'] = video_path
        task['video_duration'] = duration
        task['status'] = 'completed'

        return jsonify({
            'task_id': task_id,
            'video_url': f'/download/{os.path.basename(video_path)}',
            'duration': duration,
            'message': '视频生成成功'
        })
    except Exception as e:
        task['status'] = 'error'
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(filepath):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            abort(404)

    return send_from_directory(
        os.path.dirname(filepath),
        os.path.basename(filepath),
        as_attachment=True
    )

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    task_list = []
    for task_id, task in tasks.items():
        task_list.append({
            'task_id': task_id,
            'filename': task.get('filename'),
            'status': task.get('status'),
            'created_at': task.get('created_at'),
            'matches_count': len(task.get('matches', []))
        })

    task_list.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'tasks': task_list})

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task_api(task_id):
    task = get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    return jsonify({
        'task_id': task_id,
        'task': {
            'filename': task.get('filename'),
            'status': task.get('status'),
            'created_at': task.get('created_at'),
            'matches': task.get('matches', []),
            'matches_count': len(task.get('matches', [])),
            'annotated_url': f'/download/{os.path.basename(task["annotated_path"])}' if task.get('annotated_path') else None,
            'video_url': f'/download/{os.path.basename(task["video_path"])}' if task.get('video_path') else None
        }
    })

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task_api(task_id):
    task = get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    # 删除相关文件
    try:
        if task.get('filepath') and os.path.exists(task['filepath']):
            os.remove(task['filepath'])

        if task.get('annotated_path') and os.path.exists(task['annotated_path']):
            os.remove(task['annotated_path'])

        if task.get('video_path') and os.path.exists(task['video_path']):
            os.remove(task['video_path'])
    except Exception as e:
        print(f"[删除任务] 删除文件时出错: {e}")

    # 删除任务
    del tasks[task_id]

    return jsonify({'success': True, 'message': '任务已删除'})

@app.route('/api/ocr-engine', methods=['GET'])
def get_ocr_engine():
    engine_map = {
        'paddle': 'PaddleOCR',
        'easyocr': 'EasyOCR',
        'mock': '模拟模式（OCR 初始化失败）'
    }
    return jsonify({'engine': engine_map.get(ocr_method, '未知')})

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    global tasks
    try:
        # Clear global tasks dict
        tasks.clear()
        
        # Clear directories
        for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f"Failed to delete {file_path}. Reason: {e}")
        
        # Force GC
        import gc
        gc.collect()
        
        return jsonify({'success': True, 'message': '历史记录已清空'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Smart Caption Video Generator")
    print("=" * 60)
    print(f"📌 OCR Engine: {ocr_method}")
    print("📌 Access: http://localhost:5031")
    print("=" * 60)
    # Google Cloud Run configuration
    port = int(os.environ.get('PORT', 5031))
    print(f"📌 Starting on port: {port}")
    # Disable debug in production (implied by reading PORT) usually, but kept for now or toggle based on env
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)