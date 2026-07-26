import http.server
import socketserver
import json
import os
import urllib.parse
import sys
from typing import Dict, Any

from db import Database
from mcp_client import MCPManager
from openai_service import OpenAIService

PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0")

db = Database()
mcp_manager = MCPManager()
mcp_manager.start_all()
openai_service = OpenAIService()

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

class SimpleChatHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Professional minimal logging
        sys.stdout.write(f"[{self.log_date_time_string()}] {self.command} {self.path} -> {args[0]}\n")
        sys.stdout.flush()

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400):
        self._send_json({"error": message}, status=status)

    def _parse_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # API Endpoints
        if path == "/api/conversations":
            convs = db.list_conversations()
            return self._send_json(convs)

        elif path.startswith("/api/conversations/") and "/messages" in path:
            # /api/conversations/<id>/messages
            parts = path.split("/")
            conv_id = parts[3]
            msgs = db.get_conversation_messages(conv_id)
            return self._send_json(msgs)

        elif path.startswith("/api/conversations/"):
            conv_id = path.split("/")[-1]
            conv = db.get_conversation(conv_id)
            if not conv:
                return self._send_error("Conversation not found", status=404)
            msgs = db.get_conversation_messages(conv_id)
            conv["messages"] = msgs
            return self._send_json(conv)

        elif path == "/api/mcp/servers":
            config = mcp_manager.load_config()
            tools = mcp_manager.get_openai_tools()
            statuses = mcp_manager.get_server_statuses()
            active_servers = [s["name"] for s in statuses if s["running"]]
            return self._send_json({
                "config": config,
                "statuses": statuses,
                "active_servers": active_servers,
                "tools": tools
            })

        elif path == "/api/models":
            base_url = query.get("base_url", [db.get_setting("base_url", "https://api.openai.com/v1")])[0]
            api_key = query.get("api_key", [db.get_setting("api_key", "")])[0]
            models = openai_service.list_models(base_url=base_url, api_key=api_key)
            return self._send_json(models)

        elif path == "/api/settings":
            settings = db.get_all_settings()
            return self._send_json(settings)

        # Static asset serving
        if path == "/":
            file_path = os.path.join(STATIC_DIR, "index.html")
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            content_type = "text/html"
            if file_path.endswith(".css"):
                content_type = "text/css"
            elif file_path.endswith(".js"):
                content_type = "application/javascript"
            elif file_path.endswith(".json"):
                content_type = "application/json"
            elif file_path.endswith(".png"):
                content_type = "image/png"
            elif file_path.endswith(".svg"):
                content_type = "image/svg+xml"

            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_error("File not found", status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/conversations":
            data = self._parse_json_body()
            conv = db.create_conversation(
                title=data.get("title", "New Chat"),
                system_prompt=data.get("system_prompt", ""),
                base_url=data.get("base_url", ""),
                model=data.get("model", "")
            )
            return self._send_json(conv, status=201)

        elif path == "/api/settings":
            data = self._parse_json_body()
            for k, v in data.items():
                db.set_setting(k, str(v))
            return self._send_json({"status": "ok"})

        elif path == "/api/mcp/servers":
            data = self._parse_json_body()
            mcp_manager.save_config(data)
            mcp_manager.start_all()
            return self._send_json({"status": "ok", "active_servers": list(mcp_manager.servers.keys())})

        elif path == "/api/chat":
            # SSE Chat Stream handler
            data = self._parse_json_body()
            conv_id = data.get("conversation_id")
            user_message_text = data.get("message", "").strip()
            model = data.get("model") or db.get_setting("model", "gpt-4o")
            base_url = data.get("base_url") or db.get_setting("base_url", "https://api.openai.com/v1")
            api_key = data.get("api_key") or db.get_setting("api_key", "")
            system_prompt = data.get("system_prompt")
            enable_mcp = data.get("enable_mcp", True)

            if not conv_id:
                # Create conversation if not specified
                conv = db.create_conversation(
                    title=user_message_text[:30] if user_message_text else "New Chat",
                    system_prompt=system_prompt or "",
                    base_url=base_url,
                    model=model
                )
                conv_id = conv["id"]

            # Add user message to DB
            if user_message_text:
                db.add_message(conv_id, "user", user_message_text)

            # Auto title update if default "New Chat"
            conv = db.get_conversation(conv_id)
            if conv and conv["title"] == "New Chat" and user_message_text:
                auto_title = user_message_text[:35] + ("..." if len(user_message_text) > 35 else "")
                db.update_conversation(conv_id, title=auto_title)

            # Fetch conversation history
            raw_msgs = db.get_conversation_messages(conv_id)
            formatted_msgs = []

            # System prompt prepending
            sys_p = system_prompt if system_prompt is not None else conv.get("system_prompt", "")
            if sys_p:
                formatted_msgs.append({"role": "system", "content": sys_p})

            for m in raw_msgs:
                msg_obj = {"role": m["role"], "content": m["content"]}
                if m["role"] == "assistant" and m.get("tool_calls"):
                    msg_obj["tool_calls"] = m["tool_calls"]
                if m["role"] == "tool" and m.get("tool_call_id"):
                    msg_obj["tool_call_id"] = m["tool_call_id"]
                formatted_msgs.append(msg_obj)

            # Gather tools if MCP enabled
            tools = mcp_manager.get_openai_tools() if enable_mcp else None

            # Headers for SSE
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            def send_event(event_type: str, payload: Dict[str, Any]):
                msg = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
                try:
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass

            # Stream execution
            stream_gen = openai_service.stream_chat_completion(
                messages=formatted_msgs,
                model=model,
                base_url=base_url,
                api_key=api_key,
                tools=tools,
                mcp_manager=mcp_manager if enable_mcp else None
            )

            accumulated_content = ""
            accumulated_reasoning = ""
            executed_tool_calls = []

            try:
                for event in stream_gen:
                    e_type = event.get("type")
                    if e_type == "reasoning":
                        accumulated_reasoning += event.get("delta", "")
                        send_event("reasoning", {"delta": event.get("delta", "")})
                    elif e_type == "content":
                        accumulated_content += event.get("delta", "")
                        send_event("content", {"delta": event.get("delta", "")})
                    elif e_type == "tool_start":
                        send_event("tool_start", event)
                    elif e_type == "tool_executing":
                        send_event("tool_executing", event)
                    elif e_type == "tool_result":
                        executed_tool_calls.append(event)
                        send_event("tool_result", event)
                    elif e_type == "error":
                        send_event("error", {"message": event.get("message")})
            except Exception as e:
                send_event("error", {"message": str(e)})

            # Save completed assistant message to SQLite
            saved_msg = db.add_message(
                conversation_id=conv_id,
                role="assistant",
                content=accumulated_content,
                reasoning_content=accumulated_reasoning,
                tool_calls=executed_tool_calls if executed_tool_calls else None
            )

            send_event("done", {
                "conversation_id": conv_id,
                "message": saved_msg
            })

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/conversations/"):
            conv_id = path.split("/")[-1]
            data = self._parse_json_body()
            updated = db.update_conversation(conv_id, **data)
            if not updated:
                return self._send_error("Conversation not found", status=404)
            return self._send_json(updated)
        else:
            self._send_error("Method not allowed", status=405)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/conversations/"):
            conv_id = path.split("/")[-1]
            deleted = db.delete_conversation(conv_id)
            if not deleted:
                return self._send_error("Conversation not found", status=404)
            return self._send_json({"status": "deleted", "id": conv_id})
        else:
            self._send_error("Method not allowed", status=405)


def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer((HOST, PORT), SimpleChatHandler) as httpd:
        print(f"🚀 SimpleChat server running on http://{HOST}:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down SimpleChat...")
            mcp_manager.stop_all()

if __name__ == "__main__":
    run_server()
