import json
import logging
import re
from typing import Any, AsyncGenerator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
FINAL_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)


class OpenClawServiceError(RuntimeError):
    """A Gateway failure that the HTTP API must expose to its caller."""


class OpenClawService:
    def __init__(self):
        self.base_url = self._normalize_base_url(settings.OPENCLAW_API_URL)
        self.token = self._resolve_token()
        self.agent_id = settings.OPENCLAW_AGENT_ID
        self.session_id = self._normalize_session_key(settings.OPENCLAW_SESSION_KEY)
        self.client = httpx.AsyncClient(timeout=120.0)

    @staticmethod
    def _resolve_token() -> str:
        """Prefer the active Gateway secret without copying or logging it."""
        try:
            data = json.loads(
                Path(settings.OPENCLAW_SECRET_FILE).expanduser().read_text(encoding="utf-8")
            )
            token = data.get(settings.OPENCLAW_TOKEN_SECRET_ID, "")
            if isinstance(token, str) and token:
                return token
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[OpenClaw HTTP] No se pudo leer el token del Gateway: %s", exc)

        return settings.OPENCLAW_API_TOKEN

    def _normalize_session_key(self, raw_key: str) -> str:
        key = raw_key.strip()
        if key.startswith("agent:"):
            return key
        return f"agent:{self.agent_id}:{key}"

    def _normalize_base_url(self, raw_url: str) -> str:
        parsed = urlparse(raw_url.strip())
        scheme = parsed.scheme
        if scheme == "ws":
            scheme = "http"
        elif scheme == "wss":
            scheme = "https"
        normalized = urlunparse(parsed._replace(scheme=scheme, path="", params="", query="", fragment=""))
        return normalized.rstrip("/")

    def _normalize_response_text(self, text: str) -> str:
        match = FINAL_RE.search(text)
        if match:
            return match.group(1).strip()
        return THINK_RE.sub("", text).strip()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "x-openclaw-agent-id": self.agent_id,
            "x-openclaw-session-key": self.session_id,
        }

    def _build_payload(self, message: str, stream: bool) -> dict[str, Any]:
        prompt = (
            "/think off\n"
            "Respondé únicamente en texto plano. No generes audio, no uses MEDIA:, no adjuntes archivos. "
            "El TTS lo resuelve el backend después.\n"
            f"{message}"
        )
        return {
            "model": "openclaw",
            "input": prompt,
            "stream": stream,
        }

    async def ask_agent_stream(self, message: str) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/v1/responses"
        payload = self._build_payload(message, stream=True)
        current_event: str | None = None
        saw_delta = False

        try:
            async with self.client.stream("POST", url, json=payload, headers=self._headers()) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        current_event = None
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        current_event = line.split(":", 1)[1].strip()
                        continue
                    if not line.startswith("data:"):
                        continue

                    data_str = line.split(":", 1)[1].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.debug("[OpenClaw HTTP] SSE no JSON: %s", data_str)
                        continue

                    if current_event == "response.output_text.delta":
                        delta = data.get("delta")
                        if isinstance(delta, str) and delta:
                            saw_delta = True
                            yield delta
                    elif current_event == "response.output_text.done":
                        if saw_delta:
                            continue
                        text = data.get("text")
                        if isinstance(text, str) and text:
                            yield text
        except httpx.HTTPError as e:
            logger.error("[OpenClaw HTTP] HTTP error connecting to OpenClaw: %s", e)
            raise OpenClawServiceError("No se pudo comunicar con OpenClaw") from e

    async def send_message(self, message: str) -> str:
        chunks: list[str] = []
        async for chunk in self.ask_agent_stream(message):
            if chunk:
                chunks.append(chunk)

        if not chunks:
            raise OpenClawServiceError("OpenClaw no devolvió texto de respuesta")

        text = self._normalize_response_text("".join(chunks))
        if not text:
            raise OpenClawServiceError("OpenClaw devolvió una respuesta vacía")
        return text

    async def close(self):
        await self.client.aclose()
