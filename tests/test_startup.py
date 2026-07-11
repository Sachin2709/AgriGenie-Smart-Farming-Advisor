import unittest
from unittest.mock import patch

import app


class StartupTests(unittest.TestCase):
    def test_create_app_starts_rag_initialization_in_background(self):
        fake_thread = unittest.mock.Mock()
        with patch.object(app.db, "create_all") as create_all, patch("app.threading.Thread", return_value=fake_thread) as thread_cls:
            created_app = app.create_app()

        self.assertIs(created_app, app.app)
        create_all.assert_called_once()
        thread_cls.assert_called_once()
        fake_thread.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
