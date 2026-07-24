import io
import os
import tempfile
import logging
import json
import socket
from pathlib import Path
from fastapi.concurrency import run_in_threadpool
from app.core.config import settings

logger = logging.getLogger(__name__)

class SpeechToText:
    def __init__(self, model_name=None):
        # model_name is kept for backward compatibility but ignored 
        # as the external service manages its own model.
        self.socket_path = settings.STT_SOCKET_PATH
        logger.info(f"[STT] Usando servicio externo via socket: {self.socket_path}")

    def _transcribe_via_socket(self, audio_path: str) -> str:
        """
        Sends a transcription request to the local lucia-stt service.
        """
        if not os.path.exists(self.socket_path):
            logger.error(f"[STT] Socket no encontrado: {self.socket_path}")
            return "[Error: Servicio STT no disponible]"

        payload = {
            "path": str(Path(audio_path).absolute()),
            "language": "es",
            "beam_size": 1,
        }

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(30.0)
                s.connect(self.socket_path)
                s.sendall((json.dumps(payload) + "\n").encode("utf-8"))

                buf = bytearray()
                while not buf.endswith(b"\n"):
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)

            response = json.loads(buf.decode("utf-8").strip())
            if "error" in response:
                logger.error(f"[STT] Error del servicio: {response['error']}")
                return ""
            
            text = response.get("text", "").strip()
            return text
        except Exception as e:
            logger.error(f"[STT] Error conectando al socket: {e}")
            return ""

    async def transcribe_stream(self, audio_stream: io.BytesIO) -> str:
        """
        Transcribe audio from an in-memory BytesIO stream by saving to a 
        temporary file and calling the external STT service.
        """
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_stream.read())
                tmp_path = tmp.name
            
            logger.info(f"[STT] Delegando transcripción de {tmp_path} al servicio externo...")
            text = await run_in_threadpool(self._transcribe_via_socket, tmp_path)
            logger.info(f"[STT] Resultado: '{text}'")
            return text if text else ""
        except Exception as e:
            logger.error(f"[STT] Error en flujo de transcripción: {e}")
            return ""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
