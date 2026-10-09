import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenClaw Gateway (OpenResponses HTTP API)
    OPENCLAW_API_URL: str = "http://localhost:18789"
    OPENCLAW_API_TOKEN: str = ""
    OPENCLAW_SECRET_FILE: str = "~/.openclaw/secrets.json"
    OPENCLAW_TOKEN_SECRET_ID: str = "GATEWAY_AUTH_TOKEN"
    OPENCLAW_AGENT_ID: str = "main"
    OPENCLAW_SESSION_KEY: str = "lvs-desktop"

    # ElevenLabs TTS. Prefer the active OpenClaw secret store so the service
    # does not keep a second plaintext copy of the API key. An environment
    # value remains available for standalone deployments.
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_SECRET_FILE: str = "~/.openclaw/secrets.json"
    ELEVENLABS_VOICE_ID: str = "p7AwDmKvTdoHTBuueGvP"
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"
    ELEVENLABS_OUTPUT_FORMAT: str = "mp3_44100_128"
    ELEVENLABS_LANGUAGE_CODE: str = "es"
    ELEVENLABS_API_BASE: str = "https://api.elevenlabs.io"
    TTS_PROVIDER: Literal["elevenlabs", "edge"] = "elevenlabs"
    ELEVENLABS_STABILITY: float | None = Field(default=None, ge=0, le=1)
    ELEVENLABS_SIMILARITY_BOOST: float | None = Field(default=None, ge=0, le=1)
    ELEVENLABS_STYLE: float | None = Field(default=None, ge=0, le=1)
    ELEVENLABS_SPEED: float | None = Field(default=None, gt=0)
    ELEVENLABS_USE_SPEAKER_BOOST: bool | None = None

    # Microsoft Edge TTS has a fixed MP3 output format in edge-tts.
    EDGE_TTS_VOICE: str = "es-AR-ElenaNeural"
    EDGE_TTS_LANGUAGE_CODE: str = Field(
        default="es-AR", pattern=r"^[a-z]{2}-[A-Z]{2}$"
    )
    EDGE_TTS_OUTPUT_FORMAT: Literal[
        "audio-24khz-48kbitrate-mono-mp3"
    ] = "audio-24khz-48kbitrate-mono-mp3"
    EDGE_TTS_RATE: str = Field(default="+15%", pattern=r"^[+-]\d+%$")
    EDGE_TTS_PITCH: str = Field(default="+0Hz", pattern=r"^[+-]\d+Hz$")

    # Local persistent STT worker.
    STT_SOCKET_PATH: str = os.path.join(
        os.getenv("XDG_RUNTIME_DIR", str(Path.home() / ".local" / "run")),
        "lvs-stt.sock",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
