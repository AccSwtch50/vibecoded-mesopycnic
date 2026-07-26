import unittest
import json
import http.server
import socketserver
import threading
import time
from openai_service import OpenAIService

class MockOpenAIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "object": "list",
                "data": [
                    {"id": "mock-gpt-4o", "object": "model"},
                    {"id": "mock-deepseek-r1", "object": "model"}
                ]
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            # Stream reasoning chunk then content chunk
            chunk1 = {
                "choices": [{"delta": {"reasoning_content": "Let me calculate this step by step..."}}]
            }
            chunk2 = {
                "choices": [{"delta": {"content": "The answer is 42."}}]
            }
            self.wfile.write(f"data: {json.dumps(chunk1)}\n\n".encode("utf-8"))
            self.wfile.flush()
            time.sleep(0.01)
            self.wfile.write(f"data: {json.dumps(chunk2)}\n\n".encode("utf-8"))
            self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

class TestOpenAIService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), MockOpenAIHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}/v1"
        cls.service = OpenAIService(default_base_url=cls.base_url)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_list_models(self):
        models = self.service.list_models(base_url=self.base_url)
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["id"], "mock-gpt-4o")

    def test_stream_chat_completion(self):
        messages = [{"role": "user", "content": "What is the meaning of life?"}]
        events = list(self.service.stream_chat_completion(messages, "mock-deepseek-r1", base_url=self.base_url))

        reasoning_events = [e for e in events if e.get("type") == "reasoning"]
        content_events = [e for e in events if e.get("type") == "content"]

        self.assertGreater(len(reasoning_events), 0)
        self.assertEqual(reasoning_events[0]["delta"], "Let me calculate this step by step...")
        self.assertGreater(len(content_events), 0)
        self.assertEqual(content_events[0]["delta"], "The answer is 42.")

if __name__ == "__main__":
    unittest.main()
