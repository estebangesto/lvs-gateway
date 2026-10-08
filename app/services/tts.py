import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SynthesizedAudio:
    data: bytes
    output_format: str
    media_type: str

    @property
    def format(self) -> str:
        return self.output_format.split("_", maxsplit=1)[0]


class TTSProvider(Protocol):
    async def synthesize(self, text: str) -> SynthesizedAudio: ...

    async def close(self) -> None: ...


def _media_type_for_format(output_format: str) -> str:
    codec = output_format.split("_", maxsplit=1)[0].lower()
    return {
        "mp3": "audio/mpeg",
        "pcm": "audio/pcm",
        "opus": "audio/opus",
        "ulaw": "audio/basic",
        "alaw": "audio/pcma",
    }.get(codec, "application/octet-stream")


class ElevenLabsProvider:
    """ElevenLabs adapter for legacy Text-to-Speech and v4 Text-to-Dialogue."""

    V4_MODEL_ID = "eleven_v4"
    LEGACY_ONLY_SETTINGS = (
        "ELEVENLABS_STYLE",
        "ELEVENLABS_SPEED",
        "ELEVENLABS_USE_SPEAKER_BOOST",
    )

    def __init__(
        self,
        config: Settings = settings,
        client: httpx.AsyncClient | None = None,
        api_key: str | None = None,
    ) -> None:
        self.config = config
        self.api_base = config.ELEVENLABS_API_BASE.rstrip("/")
        self._validate_model_settings()
        self.api_key = api_key if api_key is not None else self._resolve_api_key(config)
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=10.0)
        )
        self._owns_client = client is None

        logger.info(
            "[TTS] Cliente ElevenLabs inicializado (voice=%s, model=%s)",
            config.ELEVENLABS_VOICE_ID or "not-configured",
            config.ELEVENLABS_MODEL_ID,
        )

    @staticmethod
    def _resolve_api_key(config: Settings) -> str:
        """Resolve the ElevenLabs key without duplicating or logging it."""
        if config.ELEVENLABS_API_KEY:
            return config.ELEVENLABS_API_KEY

        try:
            data = json.loads(
                Path(config.ELEVENLABS_SECRET_FILE)
                .expanduser()
                .read_text(encoding="utf-8")
            )
            api_key = data.get("ELEVENLABS_API_KEY", "")
            if isinstance(api_key, str) and api_key:
                return api_key
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "[TTS] No se pudo leer la credencial de ElevenLabs: %s",
                type(exc).__name__,
            )

        return ""

    def _validate_model_settings(self) -> None:
        if self.config.ELEVENLABS_MODEL_ID != self.V4_MODEL_ID:
            return

        unsupported = [
            name
            for name in self.LEGACY_ONLY_SETTINGS
            if getattr(self.config, name) is not None
        ]
        if unsupported:
            names = ", ".join(unsupported)
            raise ValueError(
                f"{names} no son compatibles con {self.V4_MODEL_ID}; "
                "quitá esos ajustes o seleccioná un modelo ElevenLabs 2.5"
            )

    def _ensure_configured(self) -> None:
        if not self.api_key or not self.config.ELEVENLABS_VOICE_ID:
            raise RuntimeError(
                "ElevenLabs no está configurado: faltan ELEVENLABS_API_KEY "
                "o ELEVENLABS_VOICE_ID"
            )

    def _payload(self, text: str) -> tuple[str, dict[str, object]]:
        config = self.config
        if config.ELEVENLABS_MODEL_ID == self.V4_MODEL_ID:
            payload: dict[str, object] = {
                "inputs": [
                    {
                        "text": text,
                        "voice_id": config.ELEVENLABS_VOICE_ID,
                    }
                ],
                "model_id": config.ELEVENLABS_MODEL_ID,
                "language_code": config.ELEVENLABS_LANGUAGE_CODE,
            }
            dialogue_settings = {
                "stability": config.ELEVENLABS_STABILITY,
                "similarity": config.ELEVENLABS_SIMILARITY_BOOST,
            }
            settings_payload = {
                key: value for key, value in dialogue_settings.items()
                if value is not None
            }
            if settings_payload:
                payload["settings"] = settings_payload
            return "/v1/text-to-dialogue/stream", payload

        payload = {
            "text": text,
            "model_id": config.ELEVENLABS_MODEL_ID,
            "language_code": config.ELEVENLABS_LANGUAGE_CODE,
        }
        voice_settings = {
            "stability": config.ELEVENLABS_STABILITY,
            "similarity_boost": config.ELEVENLABS_SIMILARITY_BOOST,
            "style": config.ELEVENLABS_STYLE,
            "speed": config.ELEVENLABS_SPEED,
            "use_speaker_boost": config.ELEVENLABS_USE_SPEAKER_BOOST,
        }
        settings_payload = {
            key: value for key, value in voice_settings.items()
            if value is not None
        }
        if settings_payload:
            payload["voice_settings"] = settings_payload
        return (
            f"/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}/stream",
            payload,
        )

    async def synthesize(self, text: str) -> SynthesizedAudio:
        self._ensure_configured()
        endpoint, payload = self._payload(text)
        output_format = self.config.ELEVENLABS_OUTPUT_FORMAT
        headers = {
            "xi-api-key": self.api_key,
            "accept": "audio/*",
            "content-type": "application/json",
        }
        params = {"output_format": output_format}

        audio = bytearray()
        media_type = _media_type_for_format(output_format)
        try:
            async with self.client.stream(
                "POST",
                f"{self.api_base}{endpoint}",
                params=params,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                response_media_type = response.headers.get("content-type")
                if response_media_type:
                    media_type = response_media_type.split(";", maxsplit=1)[0].strip()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        audio.extend(chunk)
        except httpx.HTTPStatusError as exc:
            logger.error("[TTS] ElevenLabs respondió HTTP %s", exc.response.status_code)
            raise RuntimeError(
                f"ElevenLabs respondió HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("[TTS] Error comunicando con ElevenLabs: %s", type(exc).__name__)
            raise RuntimeError("No se pudo comunicar con ElevenLabs") from exc

        return SynthesizedAudio(
            data=bytes(audio),
            output_format=output_format,
            media_type=media_type,
        )

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Compatibility iterator for callers of the previous adapter API."""
        result = await self.synthesize(text)
        if result.data:
            yield result.data

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()


class TTSService:
    """Gateway-owned facade that selects and owns the configured TTS provider."""

    def __init__(
        self,
        config: Settings = settings,
        provider: TTSProvider | None = None,
    ) -> None:
        if provider is not None:
            self.provider = provider
        elif config.TTS_PROVIDER == "elevenlabs":
            self.provider = ElevenLabsProvider(config)
        else:
            raise ValueError(f"Proveedor TTS no soportado: {config.TTS_PROVIDER}")

    async def synthesize(self, text: str) -> SynthesizedAudio:
        return await self.provider.synthesize(text)

    async def close(self) -> None:
        await self.provider.close()


# Keep the former import available to local diagnostic scripts.
TextToSpeech = ElevenLabsProvider
