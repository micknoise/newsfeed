"""
Local Kokoro TTS server — serves audio to the GitHub Pages site.
Runs on http://localhost:8765/tts?text=...&voice=af_sky

Start manually:  python3 tts_server.py
Auto-start:      see com.micknoise.newsfeed-tts.plist (launchd)
"""

import os
import subprocess
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

KOKORO  = "/Users/cci-research/miniconda3/bin/kokoro"
FFMPEG  = "/opt/homebrew/bin/ffmpeg"
PORT    = 8765

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://micknoise.github.io",
        "http://localhost",
        "http://127.0.0.1",
        "null",  # file:// origin
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/tts")
async def tts(
    text:  str = Query(..., max_length=2000),
    voice: str = Query("af_sky"),
    speed: float = Query(1.0),
):
    text = text.strip()
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)

    tmp_dir = Path(tempfile.mkdtemp(prefix="newsfeed_tts_"))
    wav_path = tmp_dir / "out.wav"
    ogg_path = tmp_dir / "out.ogg"

    try:
        r = subprocess.run(
            [KOKORO, "-t", text, "-m", voice, "-s", str(speed), "-o", str(wav_path)],
            capture_output=True, timeout=60,
        )
        if r.returncode != 0:
            return JSONResponse({"error": "kokoro failed", "detail": r.stderr.decode()}, status_code=500)

        r = subprocess.run(
            [FFMPEG, "-y", "-i", str(wav_path),
             "-c:a", "libvorbis", "-q:a", "4", str(ogg_path)],
            capture_output=True, timeout=30,
        )
        if r.returncode != 0:
            return JSONResponse({"error": "ffmpeg failed"}, status_code=500)

        return FileResponse(
            str(ogg_path),
            media_type="audio/ogg",
            headers={"Cache-Control": "no-store"},
            background=_cleanup(tmp_dir),
        )
    except Exception as e:
        _cleanup(tmp_dir)()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/ping")
async def ping():
    return {"ok": True}


class _cleanup:
    """Background task to delete the temp directory after the response is sent."""
    def __init__(self, path: Path):
        self.path = path

    def __call__(self):
        import shutil
        shutil.rmtree(self.path, ignore_errors=True)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
