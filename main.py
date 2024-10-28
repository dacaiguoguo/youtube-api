import asyncio
import subprocess
import os
import webvtt
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from googleapiclient.discovery import build

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

class VideoId(BaseModel):
    video_id: str
    video_url: str  # 新增 video_url 字段

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

async def download_subtitles_async(video_id, output_dir):
    url = f"https://www.youtube.com/watch?v={video_id}"
    command = [
        "yt-dlp",
        "--username=oauth+MY_PROFILE",
        "--password=",
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
        raise HTTPException(status_code=500, detail=f"Error executing yt-dlp: {stderr.decode()}")
    
    logger.info("yt-dlp command executed successfully")
    logger.debug(f"yt-dlp stdout: {stdout.decode()}")
    logger.debug(f"yt-dlp stderr: {stderr.decode()}")

async def get_video_details_async(video_id):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_video_details, video_id)

@app.post("/download-subtitles/")
async def download_subtitles(video: VideoId):
    logger.info(f"Received request for video ID: {video.video_id}")
    try:
        output_dir = f"subtitles/{video.video_id}"
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")
        
        # 并行执行字幕下载和获取视频详情
        subtitle_task = asyncio.create_task(download_subtitles_async(video.video_id, output_dir))
        video_details_task = asyncio.create_task(get_video_details_async(video.video_id))
        
        await asyncio.gather(subtitle_task, video_details_task)
        
        subtitle_file = f"{output_dir}/{video.video_id}.en.vtt"
        video_details = await video_details_task

        if os.path.exists(subtitle_file):
            logger.info(f"Subtitle file found: {subtitle_file}")
            cleaned_content = vtt_to_txt(subtitle_file)
            logger.info("Subtitles cleaned successfully")
            
            if video_details:
                logger.info("Video details fetched successfully")
                return {
                    "message": "Subtitles downloaded and cleaned successfully",
                    "content": cleaned_content,
                    "video_details": video_details,
                    "video_id": video.video_id,
                    "video_url": video.video_url  # 在返回值中添加 video_url
                }
            else:
                logger.warning("Video details not found")
                return {
                    "message": "Subtitles downloaded and cleaned successfully, but video details not found",
                    "content": cleaned_content,
                    "video_id": video.video_id,
                    "video_url": video.video_url  # 在返回值中添加 video_url
                }
        else:
            logger.warning("Subtitle file not found")
            if video_details:
                logger.info("Video details fetched successfully")
                return {
                    "message": "Subtitles not found, but video details fetched successfully",
                    "video_details": video_details,
                    "video_id": video.video_id,
                    "video_url": video.video_url  # 在返回值中添加 video_url
                }
            else:
                logger.error("Neither subtitles nor video details found")
                raise HTTPException(status_code=404, detail="Neither subtitles nor video details found")

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
