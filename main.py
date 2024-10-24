import subprocess
import os
import webvtt
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

class VideoId(BaseModel):
    video_id: str

def vtt_to_txt(vtt_file_path):
    plain_text = []
    for caption in webvtt.read(vtt_file_path):
        plain_text.append(caption.text.strip())
    return '\n'.join(plain_text)

@app.post("/download-subtitles/")
async def download_subtitles(video: VideoId):
    logger.info(f"Received request for video ID: {video.video_id}")
    try:
        url = f"https://www.youtube.com/watch?v={video.video_id}"
        output_dir = f"subtitles/{video.video_id}"
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")
        
        command = [
            "yt-dlp",
            "--username=oauth",
            "--password=",
            "--write-auto-sub",
            "--skip-download",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--output", f"{output_dir}/%(id)s.%(ext)s",
            url
        ]
        
        logger.info("Executing yt-dlp command")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"yt-dlp command executed successfully. Return code: {result.returncode}")
        logger.debug(f"yt-dlp stdout: {result.stdout}")
        logger.debug(f"yt-dlp stderr: {result.stderr}")
        
        subtitle_file = f"{output_dir}/{video.video_id}.en.vtt"
        if os.path.exists(subtitle_file):
            logger.info(f"Subtitle file found: {subtitle_file}")
            cleaned_content = vtt_to_txt(subtitle_file)
            logger.info("Subtitles cleaned successfully")
            return {"message": "Subtitles downloaded and cleaned successfully", "content": cleaned_content}
        else:
            logger.error("Subtitle file not found")
            raise HTTPException(status_code=404, detail="Subtitle file not found")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing yt-dlp: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Error executing yt-dlp: {e.stderr}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
