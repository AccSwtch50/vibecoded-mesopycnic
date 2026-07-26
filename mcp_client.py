import json
import os
import subprocess
import threading
import sys
import time
from typing import Dict, List, Any, Optional

CONFIG_FILE = "mcp_servers.json"

class MCPServerProcess:
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.request_id = 0
        self.tools: List[Dict[str, Any]] = []
        self.is_running = False

    def _get_next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def start(self):
        command = self.config.get("command")
        args = self.config.get("args", [])
        env_vars = self.config.get("env", {})

        if not command:
            raise ValueError(f"No command specified for MCP server '{self.name}'")

        cmd_list = [command] + args
        full_env = os.environ.copy()
        full_env.update(env_vars)

        self.proc = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=full_env
        )
        self.is_running = True

        # Perform initialize handshake
        init_res = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "SimpleChat", "version": "1.0.0"}
        })

        # Send initialized notification
        self._send_notification("notifications/initialized", {})

        # Fetch tools
        tools_res = self._send_request("tools/list", {})
        if tools_res and "result" in tools_res and "tools" in tools_res["result"]:
            self.tools = tools_res["result"]["tools"]

    def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        with self.lock:
            if not self.proc or self.proc.poll() is not None:
                raise RuntimeError(f"MCP server '{self.name}' process is not running")

            req_id = self._get_next_id()
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params
            }

            try:
                line = json.dumps(payload) + "\n"
                self.proc.stdin.write(line)
                self.proc.stdin.flush()
            except Exception as e:
                self.is_running = False
                raise RuntimeError(f"Failed to write to MCP server '{self.name}': {e}")

            # Read lines until we find matching response ID
            start_time = time.time()
            while time.time() - start_time < timeout:
                out_line = self.proc.stdout.readline()
                if not out_line:
                    break
                out_line = out_line.strip()
                if not out_line:
                    continue
                try:
                    data = json.loads(out_line)
                    if isinstance(data, dict) and data.get("id") == req_id:
                        return data
                except json.JSONDecodeError:
                    continue

            return None

    def _send_notification(self, method: str, params: Dict[str, Any]):
        with self.lock:
            if not self.proc or self.proc.poll() is not None:
                return
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params
            }
            try:
                line = json.dumps(payload) + "\n"
                self.proc.stdin.write(line)
                self.proc.stdin.flush()
            except Exception:
                pass

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        res = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        if not res:
            return f"Error: No response from MCP server '{self.name}' for tool '{tool_name}'"

        if "error" in res:
            return f"Error from MCP server '{self.name}': {res['error'].get('message', 'Unknown error')}"

        result = res.get("result", {})
        contents = result.get("content", [])
        output_parts = []
        for c in contents:
            if isinstance(c, dict):
                if c.get("type") == "text":
                    output_parts.append(c.get("text", ""))
                else:
                    output_parts.append(json.dumps(c))
            else:
                output_parts.append(str(c))

        return "\n".join(output_parts) if output_parts else json.dumps(result)

    def stop(self):
        with self.lock:
            if self.proc:
                try:
                    if self.proc.stdin:
                        self.proc.stdin.close()
                    if self.proc.stdout:
                        self.proc.stdout.close()
                    if self.proc.stderr:
                        self.proc.stderr.close()
                except Exception:
                    pass
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=1.0)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
                self.proc = None
            self.is_running = False


class MCPManager:
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.servers: Dict[str, MCPServerProcess] = {}

    def load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_file):
            return {"mcpServers": {}}
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except Exception:
            return {"mcpServers": {}}

    def save_config(self, config: Dict[str, Any]):
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def start_all(self):
        self.stop_all()
        config = self.load_config()
        mcp_servers = config.get("mcpServers", {})

        for s_name, s_cfg in mcp_servers.items():
            if s_cfg.get("enabled", True) is False:
                continue
            try:
                srv = MCPServerProcess(s_name, s_cfg)
                srv.start()
                self.servers[s_name] = srv
            except Exception as e:
                sys.stderr.write(f"Failed to start MCP server '{s_name}': {e}\n")

    def stop_all(self):
        for srv in self.servers.values():
            srv.stop()
        self.servers.clear()

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        openai_tools = []
        for s_name, srv in self.servers.items():
            for t in srv.tools:
                tool_name = t.get("name")
                desc = t.get("description", "")
                schema = t.get("inputSchema", {"type": "object", "properties": {}})

                # Format tool name: serverName__toolName or toolName
                func_name = f"{s_name}__{tool_name}"
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "description": f"[{s_name}] {desc}",
                        "parameters": schema
                    }
                })
        return openai_tools

    def execute_tool_call(self, func_name: str, arguments: Dict[str, Any]) -> str:
        if "__" in func_name:
            s_name, tool_name = func_name.split("__", 1)
        else:
            s_name = None
            tool_name = func_name

        if s_name and s_name in self.servers:
            return self.servers[s_name].call_tool(tool_name, arguments)

        # Fallback: search across servers for matching tool name
        for s_key, srv in self.servers.items():
            for t in srv.tools:
                if t.get("name") == tool_name:
                    return srv.call_tool(tool_name, arguments)

        return f"Error: No MCP server found for tool call '{func_name}'"
