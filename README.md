# 智能试卷视频生成器

基于 PaddleOCR 和 MoviePy 的教学视频自动生成工具。

## 功能特性

- 📤 **试卷上传** - 支持多种图片格式（PNG、JPG、JPEG、GIF、BMP、WEBP）
- 🔍 **OCR 识别** - 使用 PaddleOCR 自动识别试卷中的关键词
- 🎯 **智能圈画** - 自动在关键词位置生成彩色圆圈标注
- 🎬 **视频生成** - 一键生成带动画效果的教学视频
- 🗣️ **AI 配音** - 支持 Edge TTS 语音合成（可选）
- 💾 **文件管理** - 历史任务记录和批量下载

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务

```bash
python app.py
```

服务将运行在 `http://localhost:5000`

## 使用流程

1. **上传试卷图片** - 点击上传区域或拖拽文件
2. **添加关键词** - 输入要识别并圈画的关键词
3. **OCR 识别** - 点击"开始 OCR 识别"按钮
4. **查看标注结果** - 确认识别到的关键词位置
5. **配置视频参数** - 输入配音文案、设置圈圈出现时间
6. **生成视频** - 点击"生成视频"按钮
7. **下载结果** - 视频生成完成后自动下载

## API 接口

### 上传图片
```
POST /api/upload
Content-Type: multipart/form-data
```

参数：
- `file`: 图片文件

返回：
```json
{
  "task_id": "xxx",
  "filename": "exam.jpg",
  "message": "上传成功"
}
```

### OCR 识别
```
POST /api/ocr
Content-Type: application/json
```

参数：
```json
{
  "task_id": "xxx",
  "keywords": ["关键词1", "关键词2"]
}
```

返回：
```json
{
  "task_id": "xxx",
  "matches": [
    {
      "keyword": "中心思想",
      "text": "找出这段话的中心思想",
      "confidence": 0.98,
      "box": [100, 200, 300, 250]
    }
  ],
  "annotated_url": "/download/annotated_xxx.jpg",
  "message": "识别完成，找到 1 个关键词"
}
```

### 生成视频
```
POST /api/video
Content-Type: application/json
```

参数：
```json
{
  "task_id": "xxx",
  "voice_text": "配音文案",
  "highlight_time": 2.8,
  "use_silent": true
}
```

返回：
```json
{
  "task_id": "xxx",
  "video_url": "/download/video_xxx.mp4",
  "duration": 6.5,
  "message": "视频生成成功"
}
```

## 技术栈

- **Flask** - Web 框架
- **PaddleOCR** - OCR 文字识别
- **MoviePy** - 视频编辑
- **Edge TTS** - 语音合成
- **Pillow** - 图像处理

## 注意事项

1. **图片大小** - 单张图片最大支持 16MB
2. **OCR 准确率** - 取决于图片质量和文字清晰度
3. **视频生成时间** - 取决于图片分辨率和视频时长
4. **TTS 服务** - Edge TTS 可能因网络问题返回 403，建议使用静音模式
5. **内存占用** - PaddleOCR 首次加载模型需要约 500MB 内存

## 常见问题

### OCR 识别不准确
- 确保图片清晰、光照均匀
- 调整图片分辨率，建议 1000px 以上
- 避免倾斜或扭曲的图片

### 视频生成失败
- 检查磁盘空间是否充足
- 确认 FFmpeg 已正确安装
- 尝试使用静音模式

### TTS 无法使用
- 使用静音模式绕过 TTS
- 检查网络连接
- 考虑使用代理或 VPN

## 项目结构

```
.
├── app.py                    # Flask 主应用
├── requirements.txt          # 依赖清单
├── uploads/                  # 上传文件目录
├── outputs/                  # 输出文件目录
├── templates/
│   └── index.html           # 前端页面
├── ghost_hand_video.py       # 原始视频脚本
├── ghost_hand_video_v2.py    # 改进版脚本
├── ghost_hand_video_with_ocr.py  # OCR 集成版
└── test_ocr.py              # OCR 测试脚本
```

## License

MIT License
