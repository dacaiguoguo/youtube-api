import subprocess
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class VideoId(BaseModel):
    video_id: str

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
            "--sub-format", "txt",
            "--output", f"{output_dir}/%(id)s.%(ext)s",
            url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        subtitle_file = f"{output_dir}/{video.video_id}.en.txt"
        if os.path.exists(subtitle_file):
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            return {"message": "Subtitles downloaded successfully", "content": subtitle_content}
        else:
            raise HTTPException(status_code=404, detail="Subtitle file not found")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error executing yt-dlp: {e.stderr}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
