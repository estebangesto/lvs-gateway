import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

class TextToSpeech:
    def __init__(self) -> None:
        self.api_base = settings.ELEVENLABS_API_BASE.rstrip("/")
        self.api_key = self._resolve_api_key()
        self.voice_id = settings.ELEVENLABS_VOICE_ID
        self.model_id = settings.ELEVENLABS_MODEL_ID
        self.output_format = settings.ELEVENLABS_OUTPUT_FORMAT
        self.language_code = settings.ELEVENLABS_LANGUAGE_CODE
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0))
        logger.info("[TTS] Cliente ElevenLabs inicializado (voice=%s, model=%s)", self.voice_id or "not-configured", self.model_id)

    @staticmethod
    def _resolve_api_key() -> str:
        """Resolve the ElevenLabs key without duplicating or logging it."""
        if settings.ELEVENLABS_API_KEY:
            return settings.ELEVENLABS_API_KEY

        try:
            data = json.loads(
                Path(settings.ELEVENLABS_SECRET_FILE).read_text(encoding="utf-8")
            )
            api_key = data.get("ELEVENLABS_API_KEY", "")
            if isinstance(api_key, str) and api_key:
                return api_key
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[TTS] No se pudo leer la credencial de ElevenLabs: %s", exc)

        return ""

    def _ensure_configured(self) -> None:
        if not self.api_key or not self.voice_id:
            raise RuntimeError("ElevenLabs no está configurado: faltan ELEVENLABS_API_KEY o ELEVENLABS_VOICE_ID")

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        self._ensure_configured()
        audio_text = text.replace("LVS", "assistant").replace("Esteban", "Estéban")
        url = f"{self.api_base}/v1/text-to-speech/{self.voice_id}/stream"
        payload = {
            "text": audio_text,
            "model_id": self.model_id,
            "language_code": self.language_code,
        }
        headers = {
            "xi-api-key": self.api_key,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        }
        params = {"output_format": self.output_format}

        try:
            async with self.client.stream("POST", url, params=params, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
        except httpx.HTTPStatusError as exc:
            logger.error("[TTS] ElevenLabs respondió HTTP %s", exc.response.status_code)
            raise RuntimeError(f"ElevenLabs respondió HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            logger.error("[TTS] Error comunicando con ElevenLabs: %s", exc)
            raise RuntimeError("No se pudo comunicar con ElevenLabs") from exc

    async def close(self) -> None:
        await self.client.aclose()
