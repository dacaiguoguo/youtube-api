from fastapi import FastAPI, HTTPException
import asyncio
import subprocess
import os
import sys
import platform
import webvtt
from cachetools import TTLCache
import json
from datetime import timedelta
import logging
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from time import sleep
from random import uniform
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# 根据操作系统确定 yt-dlp 和 deno 路径
def get_ytdlp_and_deno_paths():
    system = platform.system()

    if system == 'Darwin':  # macOS
        ytdlp_path = '/opt/homebrew/bin/yt-dlp'
        deno_path = os.path.expanduser('~/.deno/bin/deno')
    elif system == 'Linux':
        # 检查当前用户
        username = os.getenv('USER', 'root')
        if username == 'webui':
            ytdlp_path = os.path.expanduser('~/.local/bin/yt-dlp')
            deno_path = os.path.expanduser('~/.deno/bin/deno')
        elif username == 'root':
            ytdlp_path = '/usr/local/bin/yt-dlp'
            deno_path = '/root/.deno/bin/deno'
        else:
            ytdlp_path = '/usr/bin/yt-dlp'
            deno_path = os.path.expanduser('~/.deno/bin/deno')
    else:
        ytdlp_path = 'yt-dlp'
        deno_path = 'deno'

    # 检查路径是否存在，如果不存在则使用默认命令
    if not os.path.exists(ytdlp_path):
        ytdlp_path = 'yt-dlp'
    if not os.path.exists(deno_path):
        deno_path = 'deno'

    logger.info(f"使用 yt-dlp 路径: {ytdlp_path}")
    logger.info(f"使用 deno 路径: {deno_path}")

    return ytdlp_path, deno_path

YT_DLP_PATH, DENO_PATH = get_ytdlp_and_deno_paths()

class VideoId(BaseModel):
    video_id: str
    video_url: str

class WebUrl(BaseModel):
    url: HttpUrl

# 从环境变量中读取 API 密钥
API_KEY = os.environ.get('YOUTUBE_API_KEY')
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY environment variable is not set")

youtube = build('youtube', 'v3', developerKey=API_KEY)

def vtt_to_txt(vtt_file_path):
    plain_text = []
    for caption in webvtt.read(vtt_file_path):
        plain_text.append(caption.text.strip())
    return '\n'.join(plain_text)

def get_video_details(video_id):
    request = youtube.videos().list(
        part='snippet,statistics,contentDetails',
        id=video_id
    )
    response = request.execute()

    if 'items' in response and len(response['items']) > 0:
        video_info = response['items'][0]
        snippet = video_info['snippet']
        statistics = video_info['statistics']
        content_details = video_info['contentDetails']

        return {
            "title": snippet['title'],
            "description": snippet['description'],
            "channelTitle": snippet['channelTitle'],
            "publishedAt": snippet['publishedAt'],
            "viewCount": statistics['viewCount'],
            "likeCount": statistics['likeCount'],
            "commentCount": statistics['commentCount'],
            "duration": content_details['duration']
        }
    else:
        return None

def validate_youtube_id(video_id):
    return bool(video_id) and len(video_id) == 11

async def download_subtitles_async(video_id, output_dir, max_retries=3):
    # 检查是否已存在字幕文件（可能有不同的语言后缀）
    if os.path.exists(output_dir):
        existing_files = [f for f in os.listdir(output_dir) if f.startswith(f"{video_id}.") and f.endswith('.vtt')]
        if existing_files:
            logger.info(f"Subtitle file already exists: {existing_files[0]}")
            return

    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(output_dir, f"{video_id}")

    command = [
        YT_DLP_PATH,
        "--cookies", "cookies.txt",
        "--write-auto-sub",
        "--sub-format", "vtt",
        "--skip-download",
        "--output", output_template,
        "--extractor-args", f"youtube:player_client=web;jsruntimes={DENO_PATH}",
        "--remote-components", "ejs:github",
        url
    ]

    # 重试逻辑
    for attempt in range(max_retries):
        try:
            logger.info(f"Executing yt-dlp command (attempt {attempt + 1}/{max_retries}): {' '.join(command)}")
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            stderr_text = stderr.decode()
            stdout_text = stdout.decode()

            # 检查是否成功下载字幕（即使视频格式不可用，只要字幕下载成功就算成功）
            subtitle_downloaded = (
                "Writing video subtitles" in stderr_text or
                "Destination:" in stderr_text and ".vtt" in stderr_text or
                process.returncode == 0
            )

            if subtitle_downloaded:
                logger.info("yt-dlp subtitle download completed")
                logger.debug(f"yt-dlp stdout: {stdout_text}")
                if stderr_text:
                    logger.debug(f"yt-dlp stderr: {stderr_text}")
                return

            if process.returncode != 0:
                logger.error(f"Error executing yt-dlp (returncode={process.returncode}): {stderr_text}")

                # 检查是否只是格式不可用错误（但字幕可能已下载）
                if "Requested format is not available" in stderr_text and "--skip-download" in ' '.join(command):
                    logger.warning("Video format not available, but we only need subtitles anyway")
                    # 检查字幕文件是否已生成
                    subtitle_files = [f for f in os.listdir(output_dir) if f.startswith(f"{video_id}.") and f.endswith('.vtt')]
                    if subtitle_files:
                        logger.info(f"Subtitle file found: {subtitle_files[0]}")
                        return

                # 检查是否是速率限制错误
                if "429" in stderr_text or "Too Many Requests" in stderr_text:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10  # 10, 20, 30 seconds
                        logger.info(f"Rate limited. Waiting {wait_time} seconds before retry...")
                        await asyncio.sleep(wait_time)
                        continue

                raise HTTPException(status_code=500, detail={
                    "status": "error",
                    "error_type": "yt_dlp_error",
                    "message": f"Error executing yt-dlp: {stderr_text}"
                })

            return

        except HTTPException:
            if attempt == max_retries - 1:
                raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            if attempt == max_retries - 1:
                raise HTTPException(status_code=500, detail={
                    "status": "error",
                    "error_type": "unexpected_error",
                    "message": str(e)
                })

async def get_video_details_async(video_id):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_video_details, video_id)

def create_session_with_retries():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

# 创建一个TTL缓存，最多存储1000个项目，每个缓存项保存1天
subtitle_cache = TTLCache(maxsize=1000, ttl=86400)

@app.post("/download-subtitles/")
async def download_subtitles(video: VideoId):
    logger.info(f"Received request for video ID: {video.video_id}")
    
    if not validate_youtube_id(video.video_id):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Invalid YouTube video ID format",
                "data": {
                    "video_id": video.video_id,
                    "video_url": video.video_url
                }
            }
        )

    # 检查缓存
    cache_key = f"subtitles_{video.video_id}"
    if cache_key in subtitle_cache:
        logger.info(f"Cache hit for video ID: {video.video_id}")
        return subtitle_cache[cache_key]

    # 如果缓存中没有，执行原来的下载逻辑
    try:
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)
        
        subtitle_task = asyncio.create_task(download_subtitles_async(video.video_id, output_dir))
        video_details_task = asyncio.create_task(get_video_details_async(video.video_id))
        
        await asyncio.gather(subtitle_task, video_details_task)
        
        subtitle_file = os.path.join(output_dir, f"{video.video_id}.vtt")

        video_details = await video_details_task

        if os.path.exists(subtitle_file):
            cleaned_content = vtt_to_txt(subtitle_file)
            
            # 将结果存入缓存
            response_data = {
                "detail": {
                    "status": "success",
                    "message": "Subtitles downloaded and cleaned successfully",
                    "data": {
                        "video_id": video.video_id,
                        "video_url": video.video_url,
                        "subtitles": cleaned_content
                    }
                }
            }
            subtitle_cache[cache_key] = response_data
            return response_data
        else:
            return {
                "detail": {
                    "status": "success",
                    "message": "Subtitles not found, but video details fetched successfully" if video_details else "Neither subtitles nor video details found",
                    "data": {
                        "video_details": video_details if video_details else {},
                        "video_id": video.video_id,
                        "video_url": video.video_url
                    }
                }
            }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"Error downloading subtitles: {str(e)}",
                "data": {
                    "video_id": video.video_id,
                    "video_url": video.video_url
                }
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"Error processing request: {str(e)}",
                "data": {
                    "video_id": video.video_id,
                    "video_url": video.video_url
                }
            }
        )

@app.post("/fetch-webpage/")
async def fetch_webpage(web_url: WebUrl):
    logger.info(f"Received request to fetch URL: {web_url.url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        # 创建带有重试机制的会话
        session = create_session_with_retries()
        
        # 添加随机延迟
        sleep(uniform(0.1, 1.0))
        
        # 发送GET请求获取网页内容
        response = session.get(
            str(web_url.url),
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        
        # 使用BeautifulSoup解析网页
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 移除所有script和style标签
        for script in soup(["script", "style"]):
            script.decompose()
            
        # 获取文本内容
        text = soup.get_text()
        
        # 清理文本（删除多余的空白行和空格）
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return {
            "detail": {
                "status": "success",
                "message": "Webpage content fetched successfully",
                "data": {
                    "content": text,
                    "url": str(web_url.url)
                }
            }
        }
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"Error fetching webpage: {str(e)}",
                "data": {
                    "url": str(web_url.url)
                }
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"Error processing request: {str(e)}",
                "data": {
                    "url": str(web_url.url)
                }
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
