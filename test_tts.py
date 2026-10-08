import json
import unittest
from collections.abc import Callable

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.services.tts import ElevenLabsProvider, SynthesizedAudio, TTSService


class ElevenLabsProviderTests(unittest.IsolatedAsyncioTestCase):
    def make_config(self, **overrides: object) -> Settings:
        values: dict[str, object] = {
            "_env_file": None,
            "TTS_PROVIDER": "elevenlabs",
            "ELEVENLABS_API_KEY": "unit-test-key",
            "ELEVENLABS_VOICE_ID": "voice-test",
        }
        values.update(overrides)
        return Settings(**values)

    def make_provider(
        self,
        config: Settings,
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> ElevenLabsProvider:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(client.aclose)
        return ElevenLabsProvider(config=config, client=client)

    async def test_v4_uses_dialogue_endpoint_and_returns_audio_metadata(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                content=b"fake-mp3",
                headers={"content-type": "audio/mpeg; charset=binary"},
            )

        provider = self.make_provider(
            self.make_config(
                ELEVENLABS_MODEL_ID="eleven_v4",
                ELEVENLABS_STABILITY=0.4,
                ELEVENLABS_SIMILARITY_BOOST=0.8,
            ),
            handler,
        )

        result = await provider.synthesize("Hola, Esteban.")

        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(
            str(request.url),
            "https://api.elevenlabs.io/v1/text-to-dialogue/stream"
            "?output_format=mp3_44100_128",
        )
        self.assertEqual(
            json.loads(request.content),
            {
                "inputs": [{"text": "Hola, Esteban.", "voice_id": "voice-test"}],
                "model_id": "eleven_v4",
                "language_code": "es",
                "settings": {"stability": 0.4, "similarity": 0.8},
            },
        )
        self.assertEqual(request.headers["xi-api-key"], "unit-test-key")
        self.assertEqual(result.data, b"fake-mp3")
        self.assertEqual(result.format, "mp3")
        self.assertEqual(result.output_format, "mp3_44100_128")
        self.assertEqual(result.media_type, "audio/mpeg")

    async def test_legacy_model_keeps_existing_endpoint_and_payload_by_default(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=b"legacy-mp3")

        provider = self.make_provider(self.make_config(), handler)

        result = await provider.synthesize("Hola.")

        request = requests[0]
        self.assertEqual(
            str(request.url),
            "https://api.elevenlabs.io/v1/text-to-speech/voice-test/stream"
            "?output_format=mp3_44100_128",
        )
        self.assertEqual(
            json.loads(request.content),
            {
                "text": "Hola.",
                "model_id": "eleven_flash_v2_5",
                "language_code": "es",
            },
        )
        self.assertEqual(result.data, b"legacy-mp3")
        self.assertEqual(result.media_type, "audio/mpeg")

    async def test_legacy_adjustments_are_mapped_to_voice_settings(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=b"audio")

        provider = self.make_provider(
            self.make_config(
                ELEVENLABS_STABILITY=0.5,
                ELEVENLABS_SIMILARITY_BOOST=0.75,
                ELEVENLABS_STYLE=0.2,
                ELEVENLABS_SPEED=1.1,
                ELEVENLABS_USE_SPEAKER_BOOST=True,
            ),
            handler,
        )

        await provider.synthesize("Hola.")

        self.assertEqual(
            json.loads(requests[0].content)["voice_settings"],
            {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.2,
                "speed": 1.1,
                "use_speaker_boost": True,
            },
        )

    async def test_legacy_stream_iterator_remains_available(self) -> None:
        provider = self.make_provider(
            self.make_config(),
            lambda request: httpx.Response(200, content=b"streamed-audio"),
        )

        chunks = [
            chunk async for chunk in provider.synthesize_stream("Hola.")
        ]

        self.assertEqual(chunks, [b"streamed-audio"])

    async def test_v4_rejects_legacy_only_voice_adjustments(self) -> None:
        config = self.make_config(
            ELEVENLABS_MODEL_ID="eleven_v4",
            ELEVENLABS_STYLE=0.2,
        )

        with self.assertRaisesRegex(ValueError, "ELEVENLABS_STYLE"):
            self.make_provider(config, lambda request: httpx.Response(200))

    async def test_http_failure_does_not_echo_response_body(self) -> None:
        provider = self.make_provider(
            self.make_config(),
            lambda request: httpx.Response(401, text="unit-test-key rejected"),
        )

        with self.assertRaises(RuntimeError) as raised:
            await provider.synthesize("Hola.")

        self.assertEqual(str(raised.exception), "ElevenLabs respondió HTTP 401")
        self.assertNotIn("unit-test-key", str(raised.exception))

    async def test_invalid_provider_value_is_rejected_by_configuration(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_config(TTS_PROVIDER="unknown")


class TTSServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_delegates_to_injected_provider(self) -> None:
        class FakeProvider:
            async def synthesize(self, text: str):
                return SynthesizedAudio(
                    data=text.encode(),
                    output_format="mp3_44100_128",
                    media_type="audio/mpeg",
                )

            async def close(self) -> None:
                return None

        provider = FakeProvider()
        service = TTSService(provider=provider)
        result = await service.synthesize("hola")
        self.assertEqual(result.data, b"hola")


if __name__ == "__main__":
    unittest.main()
