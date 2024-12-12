from fastapi import FastAPI, HTTPException
import asyncio
import subprocess
import os
import webvtt
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

async def download_subtitles_async(video_id, output_dir):
    url = f"https://www.youtube.com/watch?v={video_id}"
    command = [
        "yt-dlp",
        "--cookies", "/opt/youtube-api/cookies.txt",
        "--write-auto-sub",
        "--skip-download",
        "--sub-lang", "en",
        "--sub-format", "vtt",
        "--output", f"{output_dir}/%(id)s.%(ext)s",
        url
    ]
    
    logger.info("Executing yt-dlp command")
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"Error executing yt-dlp: {stderr.decode()}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "error_type": "yt_dlp_error",
            "message": f"Error executing yt-dlp: {stderr.decode()}"
        })
    
    logger.info("yt-dlp command executed successfully")
    logger.debug(f"yt-dlp stdout: {stdout.decode()}")
    logger.debug(f"yt-dlp stderr: {stderr.decode()}")

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
    
    try:
        output_dir = f"subtitles/{video.video_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        subtitle_task = asyncio.create_task(download_subtitles_async(video.video_id, output_dir))
        video_details_task = asyncio.create_task(get_video_details_async(video.video_id))
        
        await asyncio.gather(subtitle_task, video_details_task)
        
        subtitle_file = f"{output_dir}/{video.video_id}.en.vtt"
        video_details = await video_details_task

        if os.path.exists(subtitle_file):
            cleaned_content = vtt_to_txt(subtitle_file)
            
            return {
                "detail": {
                    "status": "success",
                    "message": "Subtitles downloaded and cleaned successfully",
                    "data": {
                        "content": cleaned_content,
                        "video_details": video_details,
                        "video_id": video.video_id,
                        "video_url": video.video_url
                    }
                }
            }
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
