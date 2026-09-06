import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenClaw Gateway (OpenResponses HTTP API)
    OPENCLAW_API_URL: str = "http://localhost:18789"
    OPENCLAW_API_TOKEN: str = ""
    OPENCLAW_SECRET_FILE: str = "/home/esteban/.openclaw/secrets.json"
    OPENCLAW_TOKEN_SECRET_ID: str = "GATEWAY_AUTH_TOKEN"
    OPENCLAW_AGENT_ID: str = "main"
    OPENCLAW_SESSION_KEY: str = "lvs-desktop"

    # ElevenLabs TTS. Prefer the active OpenClaw secret store so the service
    # does not keep a second plaintext copy of the API key. An environment
    # value remains available for standalone deployments.
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_SECRET_FILE: str = "/home/esteban/.openclaw/secrets.json"
    ELEVENLABS_VOICE_ID: str = "p7AwDmKvTdoHTBuueGvP"
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"
    ELEVENLABS_OUTPUT_FORMAT: str = "mp3_44100_128"
    ELEVENLABS_LANGUAGE_CODE: str = "es"
    ELEVENLABS_API_BASE: str = "https://api.elevenlabs.io"

    # Local persistent STT worker.
    STT_SOCKET_PATH: str = f"/run/user/{os.getuid()}/lvs-stt.sock"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
