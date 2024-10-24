# youtube-subtitle-api

一个基于FastAPI的YouTube视频字幕下载API。

## 描述

这个项目提供了一个简单的API，用于下载YouTube视频的字幕。它使用yt-dlp库来获取字幕，并通过FastAPI提供Web API接口。

## 安装

1. 克隆此仓库:
   ```
   git clone https://github.com/dacaiguoguo/youtube-subtitle-api.git
   cd youtube-subtitle-api
   ```

2. 安装依赖:
   ```
   pip install -r requirements.txt
   ```

## 使用方法

### 启动服务
```
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 发送请求
```
curl -X POST "http://192.168.0.33:8000/download-subtitles/" -H "Content-Type: application/json" -d '{"video_id": "-W9cztx4O3o"}'
```

## 依赖项

- Python 3.6+
- FastAPI
- webvtt-py
- yt-dlp

## 许可证

本项目采用 MIT 许可证。查看 [LICENSE](LICENSE) 文件以获取完整的许可证文本。
