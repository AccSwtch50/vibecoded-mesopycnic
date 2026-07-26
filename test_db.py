import unittest
import os
from db import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "test_mesopycnic.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.db = Database(self.test_db_path)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_conversation_crud(self):
        conv = self.db.create_conversation("Test Title", "System prompt", "http://localhost", "gpt-4o")
        self.assertIsNotNone(conv["id"])
        self.assertEqual(conv["title"], "Test Title")

        convs = self.db.list_conversations()
        self.assertEqual(len(convs), 1)

        updated = self.db.update_conversation(conv["id"], title="Updated Title")
        self.assertEqual(updated["title"], "Updated Title")

        deleted = self.db.delete_conversation(conv["id"])
        self.assertTrue(deleted)
        self.assertEqual(len(self.db.list_conversations()), 0)

    def test_message_crud(self):
        conv = self.db.create_conversation("Msg Test")
        msg1 = self.db.add_message(conv["id"], "user", "Hello AI")
        self.assertEqual(msg1["content"], "Hello AI")
        self.assertEqual(msg1["role"], "user")

        msg2 = self.db.add_message(conv["id"], "assistant", "Hello human!", reasoning_content="Thinking about greetings...")
        self.assertEqual(msg2["reasoning_content"], "Thinking about greetings...")

        msgs = self.db.get_conversation_messages(conv["id"])
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["content"], "Hello AI")
        self.assertEqual(msgs[1]["content"], "Hello human!")

    def test_settings(self):
        self.db.set_setting("api_key", "sk-12345")
        val = self.db.get_setting("api_key")
        self.assertEqual(val, "sk-12345")

if __name__ == "__main__":
    unittest.main()