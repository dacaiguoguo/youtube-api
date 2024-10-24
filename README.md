# youtube-api

一个用于处理YouTube视频字幕的Python工具。

## 描述

这个项目提供了一套工具,用于下载、处理和分析YouTube视频的字幕。它使用YouTube API和webvtt-py库来实现功能。

## 安装

1. 克隆此仓库:
   ```
   git clone https://github.com/yourusername/youtube-api.git
   cd youtube-api
   ```

2. 安装依赖:
   ```
   pip install -r requirements.txt
   ```

## 使用方法
### 启动服务
```    
python main.py
```
### 发请求
```
curl -X POST "http://192.168.0.33:8000/download-subtitles/" -H "Content-Type: application/json" -d '{"video_id": "-W9cztx4O3o"}'
```

## 依赖项

- Python 3.6+
- webvtt-py

### 安装webvtt-py:
```
pip install webvtt-py
```

## 许可证

本项目采用 MIT 许可证。查看 [LICENSE](LICENSE) 文件以获取完整的许可证文本。

