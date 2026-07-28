import io
import base64
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from app.services.stt import SpeechToText
from app.services.tts import TextToSpeech
from app.services.openclaw import OpenClawService, OpenClawServiceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stt_service = SpeechToText()
tts_service = TextToSpeech()
openclaw_service = OpenClawService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await openclaw_service.close()
    await tts_service.close()


app = FastAPI(title="Luc.ia Voice Service API", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "lucia-voice-service"}

@app.post("/voice/transcribe")
async def transcribe_voice(audio: UploadFile = File(...)):
    """Transcribe audio without waiting for OpenClaw or TTS."""
    logger.info("Recibido audio para transcripción: %s", audio.filename)
    audio_content = await audio.read()
    input_text = await stt_service.transcribe_stream(io.BytesIO(audio_content))
    if not input_text:
        raise HTTPException(status_code=400, detail="No se pudo transcribir el audio")
    logger.info("Transcripción exitosa: %s", input_text)
    return {"input_text": input_text}

@app.post("/voice/process")
async def process_voice(
    audio: UploadFile = File(None),
    text: str = Form(None),
    tts: bool | None = Form(None)
):
    """
    Endpoint principal:
    1. Si hay audio, lo transcribe.
    2. Si hay texto (o transcripción), lo envía a OpenClaw.
    3. Obtiene respuesta de OpenClaw.
    4. Si se solicitó TTS, genera audio de la respuesta con ElevenLabs.
    5. Devuelve JSON con texto y (opcionalmente) audio en base64.
    """
    input_text = text.strip() if text else None
    generated_audio_b64 = None
    is_voice_request = audio is not None

    # 1. Procesar Audio si existe
    if audio:
        logger.info(f"Recibido audio: {audio.filename}")
        audio_content = await audio.read()
        audio_stream = io.BytesIO(audio_content)
        input_text = await stt_service.transcribe_stream(audio_stream)
        
        if not input_text:
            raise HTTPException(status_code=400, detail="No se pudo transcribir el audio")
        logger.info(f"Transcripción exitosa: {input_text}")

    if not input_text:
        raise HTTPException(status_code=400, detail="Debe proporcionar 'audio' o 'text'")

    # 2. Enviar a OpenClaw
    logger.info(f"Enviando a OpenClaw: {input_text}")
    try:
        response_text = await openclaw_service.send_message(input_text)
    except OpenClawServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.info(f"Respuesta de OpenClaw: {response_text}")

    # Text requests are text-only by default. Voice requests synthesize by
    # default, unless the caller explicitly sends tts=false.
    synthesize_audio = is_voice_request if tts is None else tts

    # 3. Generate audio only when the caller requested it.
    if synthesize_audio and response_text:
        logger.info("Generando audio de respuesta...")
        audio_out_stream = io.BytesIO()
        try:
            async for chunk in tts_service.synthesize_stream(response_text):
                audio_out_stream.write(chunk)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        
        generated_audio_b64 = base64.b64encode(audio_out_stream.getvalue()).decode("utf-8")

    return {
        "input_text": input_text,
        "response_text": response_text,
        "response_audio_b64": generated_audio_b64,
        "format": "mp3" if generated_audio_b64 else None,
        "tts_generated": bool(generated_audio_b64),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
