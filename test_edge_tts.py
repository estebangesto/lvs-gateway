import unittest

from pydantic import ValidationError

from app.core.config import Settings
from app.services.tts import EdgeTTSProvider, TTSService


class FakeCommunicate:
    calls: list[tuple[str, str, str, str]] = []
    chunks: list[dict[str, object]] = []

    def __init__(self, text, voice, *, rate, pitch):
        self.calls.append((text, voice, rate, pitch))

    async def stream(self):
        for chunk in self.chunks:
            yield chunk


class EdgeTTSProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeCommunicate.calls = []
        FakeCommunicate.chunks = [
            {"type": "WordBoundary", "data": {"text": "hola"}},
            {"type": "audio", "data": b"mp3-a"},
            {"type": "audio", "data": b"mp3-b"},
        ]

    def config(self, **overrides: object) -> Settings:
        return Settings(_env_file=None, **overrides)

    async def test_defaults_map_to_edge_client_and_report_actual_format(self):
        config = self.config()
        provider = EdgeTTSProvider(config, communicate_factory=FakeCommunicate)

        result = await provider.synthesize("Hola")

        self.assertEqual(
            FakeCommunicate.calls,
            [("Hola", "es-AR-ElenaNeural", "+15%", "+0Hz")],
        )
        self.assertEqual(result.data, b"mp3-amp3-b")
        self.assertEqual(result.output_format, "audio-24khz-48kbitrate-mono-mp3")
        self.assertEqual(result.media_type, "audio/mpeg")
        self.assertEqual(result.format, "mp3")

    async def test_overrides_are_passed_independently(self):
        config = self.config(
            EDGE_TTS_VOICE="en-US-AriaNeural",
            EDGE_TTS_LANGUAGE_CODE="en-US",
            EDGE_TTS_RATE="-10%",
            EDGE_TTS_PITCH="+3Hz",
        )
        provider = EdgeTTSProvider(config, communicate_factory=FakeCommunicate)

        await provider.synthesize("Hello")

        self.assertEqual(
            FakeCommunicate.calls,
            [("Hello", "en-US-AriaNeural", "-10%", "+3Hz")],
        )

    async def test_no_audio_is_reported_as_provider_failure(self):
        FakeCommunicate.chunks = [{"type": "WordBoundary", "data": {}}]
        provider = EdgeTTSProvider(
            self.config(), communicate_factory=FakeCommunicate
        )

        with self.assertRaisesRegex(RuntimeError, "no devolvió audio"):
            await provider.synthesize("Hola")

    async def test_provider_service_selects_edge_without_loading_elevenlabs_key(self):
        config = self.config(TTS_PROVIDER="edge")
        service = TTSService(config)

        self.assertIsInstance(service.provider, EdgeTTSProvider)

    async def test_voice_and_language_must_match(self):
        config = self.config(EDGE_TTS_LANGUAGE_CODE="en-US")

        with self.assertRaisesRegex(ValueError, "debe coincidir"):
            EdgeTTSProvider(config, communicate_factory=FakeCommunicate)

    async def test_fixed_edge_output_format_rejects_other_values(self):
        with self.assertRaises(ValidationError):
            self.config(EDGE_TTS_OUTPUT_FORMAT="audio-16khz-mono-mp3")

    async def test_client_failure_is_sanitized(self):
        class FailedCommunicate:
            def __init__(self, *args, **kwargs):
                pass

            async def stream(self):
                raise RuntimeError("internal provider detail")
                yield {}

        provider = EdgeTTSProvider(
            self.config(), communicate_factory=FailedCommunicate
        )

        with self.assertRaisesRegex(RuntimeError, "No se pudo completar") as raised:
            await provider.synthesize("Hola")
        self.assertNotIn("internal provider detail", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
