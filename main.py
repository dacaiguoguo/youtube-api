import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class VideoId(BaseModel):
    video_id: str

@app.post("/download-subtitles/")
async def download_subtitles(video: VideoId):
    try:
        url = f"https://www.youtube.com/watch?v={video.video_id}"
        command = [
            "yt-dlp",
            "--username=oauth",
            "--password=",
            "--write-auto-sub",
            "--skip-download",
            url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        return {"message": "Subtitles downloaded successfully", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error executing yt-dlp: {e.stderr}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
