import unittest

from app import get_local_fallback_response


class FallbackResponseTests(unittest.TestCase):
    def test_pest_prompt_uses_local_guidance(self):
        response = get_local_fallback_response(
            "How can I control pests in wheat?",
            include_service_notice=True,
        )
        self.assertIn("Local guidance", response)
        self.assertIn("pest or disease", response.lower())
        self.assertNotIn("watsonx", response.lower())


if __name__ == "__main__":
    unittest.main()
