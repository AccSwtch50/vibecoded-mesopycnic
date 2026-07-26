import unittest
import urllib.request
import json
import socketserver
import http.server
import threading
import os

from db import Database
from server import SimpleChatHandler, db, mcp_manager

class TestServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db = "test_server.db"
        if os.path.exists(cls.test_db):
            os.remove(cls.test_db)

        # Re-initialize DB
        db.db_path = cls.test_db
        db._init_db()

        socketserver.TCPServer.allow_reuse_address = True
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), SimpleChatHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        mcp_manager.stop_all()
        if os.path.exists(cls.test_db):
            os.remove(cls.test_db)

    def test_static_index(self):
        url = f"{self.base_url}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("<title>SimpleChat", content)

    def test_conversations_api(self):
        # 1. Create conversation
        create_url = f"{self.base_url}/api/conversations"
        payload = json.dumps({"title": "Integration Test Chat", "model": "gpt-4o"}).encode("utf-8")
        req = urllib.request.Request(create_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 201)
            data = json.loads(resp.read().decode("utf-8"))
            conv_id = data["id"]
            self.assertEqual(data["title"], "Integration Test Chat")

        # 2. List conversations
        list_url = f"{self.base_url}/api/conversations"
        with urllib.request.urlopen(list_url) as resp:
            self.assertEqual(resp.status, 200)
            convs = json.loads(resp.read().decode("utf-8"))
            self.assertGreaterEqual(len(convs), 1)

        # 3. Patch conversation title
        patch_url = f"{self.base_url}/api/conversations/{conv_id}"
        patch_payload = json.dumps({"title": "Renamed Integration Chat"}).encode("utf-8")
        req = urllib.request.Request(patch_url, data=patch_payload, headers={"Content-Type": "application/json"}, method="PATCH")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            updated = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(updated["title"], "Renamed Integration Chat")

        # 4. Delete conversation
        del_url = f"{self.base_url}/api/conversations/{conv_id}"
        req = urllib.request.Request(del_url, method="DELETE")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

    def test_mcp_servers_api(self):
        url = f"{self.base_url}/api/mcp/servers"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("tools", data)
            self.assertIn("active_servers", data)

if __name__ == "__main__":
    unittest.main()
