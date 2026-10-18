import unittest

from llm import get_provider
from llm.base import LLMError
from llm.opencode_provider import OpenCodeProvider


class OpenCodeProviderTest(unittest.TestCase):
    def test_resolve(self):
        provider = get_provider("opencode")
        self.assertEqual(provider.name, "opencode")
        self.assertTrue(provider.base_url.startswith("http"))

    def test_model_ref(self):
        self.assertEqual(OpenCodeProvider._model_ref("anthropic/claude-sonnet-4"),
                         {"providerID": "anthropic", "modelID": "claude-sonnet-4"})
        self.assertEqual(OpenCodeProvider._model_ref("a/b/c"),
                         {"providerID": "a", "modelID": "b/c"})

    def test_model_ref_invalid(self):
        with self.assertRaises(LLMError):
            OpenCodeProvider._model_ref("no-slash")

    def test_extract_text(self):
        sample = {"parts": [{"type": "text", "text": "x"},
                            {"type": "tool"},
                            {"type": "text", "text": "y"}]}
        self.assertEqual(OpenCodeProvider._extract_text(sample), "xy")
        self.assertEqual(OpenCodeProvider._extract_text({}), "")

    def test_extract_error_surfaces_upstream_message(self):
        sample = {"info": {"error": {"name": "APIError", "data": {
            "message": "This API key has expired.", "statusCode": 401,
            "responseBody": "{\"error\":{\"code\":\"api_key_expired\"}}"}}}, "parts": []}
        message = OpenCodeProvider._extract_error(sample)
        self.assertIn("api_key_expired", message)
        self.assertIn("expired", message)
        self.assertEqual(OpenCodeProvider._extract_error({}), "")

    def test_generate_without_server_raises_friendly(self):
        provider = OpenCodeProvider(base_url="http://127.0.0.1:59999", timeout=0.5)
        with self.assertRaises(LLMError):
            provider.generate("hi")


if __name__ == "__main__":
    unittest.main()
