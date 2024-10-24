import subprocess
import os
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class VideoId(BaseModel):
    video_id: str

def srt_to_txt(srt_content):
    lines = srt_content.split('\n')
    cleaned_lines = []
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            continue
        if line.strip().isdigit():  # 跳过字幕序号
            continue
        if re.match(r'^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$', line):  # 跳过时间戳
            skip_next = True  # 设置标志以跳过下一行（字幕文本）
            continue
        if line.strip():  # 只添加非空行
            cleaned_lines.append(line.strip())
    
    return "\n".join(cleaned_lines)

@app.post("/download-subtitles/")
async def download_subtitles(video: VideoId):
    try:
        url = f"https://www.youtube.com/watch?v={video.video_id}"
        output_dir = f"subtitles/{video.video_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        command = [
            "yt-dlp",
            "--username=oauth",
            "--password=",
            "--write-auto-sub",
            "--skip-download",
            "--sub-lang", "en",
            "--sub-format", "srt",
            "--output", f"{output_dir}/%(id)s.%(ext)s",
            url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        subtitle_file = f"{output_dir}/{video.video_id}.en.srt"
        if os.path.exists(subtitle_file):
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            cleaned_content = srt_to_txt(subtitle_content)
            return {"message": "Subtitles downloaded and cleaned successfully", "content": cleaned_content}
        else:
            raise HTTPException(status_code=404, detail="Subtitle file not found")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error executing yt-dlp: {e.stderr}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
