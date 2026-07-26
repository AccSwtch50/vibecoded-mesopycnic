import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time
from typing import List, Dict, Any, Generator, Optional, Tuple

class OpenAIService:
    def __init__(self, default_base_url: str = "https://api.openai.com/v1", default_api_key: str = ""):
        self.default_base_url = default_base_url.rstrip("/")
        self.default_api_key = default_api_key

    def _get_headers(self, api_key: str) -> Dict[str, str]:
        key = api_key if api_key else self.default_api_key
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SimpleChat/1.0"
        }
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def list_models(self, base_url: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        url_base = (base_url or self.default_base_url).rstrip("/")
        url = f"{url_base}/models"
        headers = self._get_headers(api_key or "")

        req = urllib.request.Request(url, headers=headers, method="GET")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=10, context=context) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "data" in data and isinstance(data["data"], list):
                    return data["data"]
                return []
        except Exception as e:
            return []

    def stream_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_manager: Optional[Any] = None
    ) -> Generator[Dict[str, Any], None, Tuple[str, str]]:
        """
        Streams chat completions.
        Yields dict events:
          {"type": "reasoning", "delta": "..."}
          {"type": "content", "delta": "..."}
          {"type": "tool_start", "id": "...", "name": "...", "arguments": "..."}
          {"type": "tool_executing", "name": "...", "arguments": "..."}
          {"type": "tool_result", "name": "...", "result": "..."}
          {"type": "error", "message": "..."}
        Returns (final_content, final_reasoning_content).
        """
        url_base = (base_url or self.default_base_url).rstrip("/")
        url = f"{url_base}/chat/completions"
        headers = self._get_headers(api_key or "")

        current_messages = list(messages)
        final_full_content = ""
        final_full_reasoning = ""

        max_tool_iterations = 5
        iteration = 0

        while iteration < max_tool_iterations:
            iteration += 1

            payload = {
                "model": model,
                "messages": current_messages,
                "stream": True
            }
            if tools:
                payload["tools"] = tools

            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            try:
                resp = urllib.request.urlopen(req, timeout=60, context=context)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                try:
                    err_json = json.loads(err_body)
                    msg = err_json.get("error", {}).get("message", err_body)
                except Exception:
                    msg = f"HTTP Error {e.code}: {err_body}"
                yield {"type": "error", "message": msg}
                return final_full_content, final_full_reasoning
            except Exception as e:
                yield {"type": "error", "message": f"Connection error: {str(e)}"}
                return final_full_content, final_full_reasoning

            tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}
            in_think_tag = False
            think_tag_buffer = ""

            with resp:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})

                        # 1. Check explicit reasoning fields
                        reasoning_delta = delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking")
                        if reasoning_delta:
                            final_full_reasoning += reasoning_delta
                            yield {"type": "reasoning", "delta": reasoning_delta}

                        # 2. Check content field for standard tokens or inline <think> tags
                        content_delta = delta.get("content")
                        if content_delta:
                            # Handle inline <think> tags if model wraps reasoning in <think>...</think>
                            i = 0
                            while i < len(content_delta):
                                if not in_think_tag:
                                    tag_idx = content_delta.find("<think>", i)
                                    if tag_idx != -1:
                                        normal_text = content_delta[i:tag_idx]
                                        if normal_text:
                                            final_full_content += normal_text
                                            yield {"type": "content", "delta": normal_text}
                                        in_think_tag = True
                                        i = tag_idx + 7
                                    else:
                                        normal_text = content_delta[i:]
                                        final_full_content += normal_text
                                        yield {"type": "content", "delta": normal_text}
                                        break
                                else:
                                    end_tag_idx = content_delta.find("</think>", i)
                                    if end_tag_idx != -1:
                                        think_text = content_delta[i:end_tag_idx]
                                        if think_text:
                                            final_full_reasoning += think_text
                                            yield {"type": "reasoning", "delta": think_text}
                                        in_think_tag = False
                                        i = end_tag_idx + 8
                                    else:
                                        think_text = content_delta[i:]
                                        final_full_reasoning += think_text
                                        yield {"type": "reasoning", "delta": think_text}
                                        break

                        # 3. Accumulate tool calls if present
                        delta_tool_calls = delta.get("tool_calls", [])
                        for tc in delta_tool_calls:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_accumulator:
                                tool_calls_accumulator[idx] = {
                                    "id": tc.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": tc.get("function", {}).get("name", ""),
                                        "arguments": tc.get("function", {}).get("arguments", "")
                                    }
                                }
                            else:
                                if tc.get("id"):
                                    tool_calls_accumulator[idx]["id"] += tc["id"]
                                fn = tc.get("function", {})
                                if fn.get("name"):
                                    tool_calls_accumulator[idx]["function"]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    tool_calls_accumulator[idx]["function"]["arguments"] += fn["arguments"]

            # If tool calls were accumulated, execute them via mcp_manager
            if tool_calls_accumulator and mcp_manager:
                formatted_tool_calls = list(tool_calls_accumulator.values())

                # Add assistant message with tool_calls to current_messages
                assistant_msg = {
                    "role": "assistant",
                    "content": final_full_content if final_full_content else None,
                    "tool_calls": formatted_tool_calls
                }
                current_messages.append(assistant_msg)

                for tc in formatted_tool_calls:
                    tc_id = tc.get("id")
                    func_name = tc.get("function", {}).get("name", "")
                    raw_args = tc.get("function", {}).get("arguments", "")

                    try:
                        parsed_args = json.loads(raw_args) if raw_args else {}
                    except Exception:
                        parsed_args = {}

                    yield {
                        "type": "tool_start",
                        "id": tc_id,
                        "name": func_name,
                        "arguments": raw_args
                    }
                    yield {
                        "type": "tool_executing",
                        "name": func_name,
                        "arguments": raw_args
                    }

                    # Execute via MCP
                    tool_result_str = mcp_manager.execute_tool_call(func_name, parsed_args)

                    yield {
                        "type": "tool_result",
                        "name": func_name,
                        "result": tool_result_str
                    }

                    # Add tool response to current_messages
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": tool_result_str
                    })

                # Loop to next iteration to send tool results back to LLM!
                continue
            else:
                # No tool calls, completion is complete!
                break

        return final_full_content, final_full_reasoning
