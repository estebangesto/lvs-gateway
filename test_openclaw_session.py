import asyncio
import unittest

from app.services.openclaw import OpenClawService


class OpenClawSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OpenClawService()

    def tearDown(self) -> None:
        asyncio.run(self.service.close())

    def test_legacy_session_key_is_scoped_to_configured_agent(self) -> None:
        self.assertEqual(self.service.session_id, "agent:main:lvs-desktop")

    def test_already_scoped_session_key_is_preserved(self) -> None:
        self.assertEqual(
            self.service._normalize_session_key("agent:custom:session"),
            "agent:custom:session",
        )

    def test_headers_include_agent_and_scoped_session(self) -> None:
        headers = self.service._headers()
        self.assertEqual(headers["x-openclaw-agent-id"], "main")
        self.assertEqual(headers["x-openclaw-session-key"], "agent:main:lvs-desktop")


if __name__ == "__main__":
    unittest.main()
