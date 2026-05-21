"""v2-step-26: 代理 edge-tts 合成语音, 返 mp3 stream。

edge-tts 是微软 Edge 浏览器内置 TTS 的逆向实现, 免费、高质量、多语言。
依赖 edge-tts pip 包, requirements.txt 已加。未安装时优雅返 503。
"""
from __future__ import annotations
import io
import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])


class TtsRequest(BaseModel):
    text: str
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"  # 默认中文女声
    rate: Optional[str] = "+0%"
    pitch: Optional[str] = "+0Hz"


@router.post("/synthesize")
async def synthesize(req: TtsRequest):
    try:
        import edge_tts  # type: ignore
    except ImportError:
        return JSONResponse({"error": "edge-tts not installed. pip install edge-tts"}, status_code=503)

    if not req.text or len(req.text) > 2000:
        return JSONResponse({"error": "text empty or exceeds 2000 chars"}, status_code=400)

    communicate = edge_tts.Communicate(req.text, req.voice, rate=req.rate, pitch=req.pitch)
    buf = io.BytesIO()
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
    except Exception as e:
        logger.exception("edge-tts stream failed")
        return JSONResponse({"error": f"tts failed: {e}"}, status_code=502)

    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/mpeg",
                             headers={"Cache-Control": "no-cache"})


@router.get("/voices")
async def list_voices():
    """返常用中英音色。"""
    return {
        "voices": [
            {"id": "zh-CN-XiaoxiaoNeural", "name": "中文 小晓 (女)", "locale": "zh-CN"},
            {"id": "zh-CN-YunxiNeural",  "name": "中文 云戏 (男)", "locale": "zh-CN"},
            {"id": "zh-CN-YunjianNeural","name": "中文 云健 (男,运动)", "locale": "zh-CN"},
            {"id": "en-US-AriaNeural",   "name": "English Aria (F)", "locale": "en-US"},
            {"id": "en-US-GuyNeural",    "name": "English Guy (M)",  "locale": "en-US"},
        ]
    }
