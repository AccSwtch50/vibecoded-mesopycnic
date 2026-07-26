#!/usr/bin/env python3
import sys
import json
import datetime
import math
import sqlite3

def send_response(response):
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def handle_request(req):
    if not isinstance(req, dict):
        return

    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "SampleMathTimeServer",
                    "version": "1.0.0"
                }
            }
        })
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "get_current_time",
                        "description": "Returns the current date and time in ISO format.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "timezone": {
                                    "type": "string",
                                    "description": "Optional timezone name (e.g. UTC, local)"
                                }
                            }
                        }
                    },
                    {
                        "name": "evaluate_math",
                        "description": "Evaluates a mathematical expression safely (e.g. '2 + 2 * 10', 'math.sqrt(144)', 'math.pi').",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression to evaluate"
                                }
                            },
                            "required": ["expression"]
                        }
                    },
                    {
                        "name": "echo",
                        "description": "Echoes back the given message.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {
                                    "type": "string",
                                    "description": "Message to echo back"
                                }
                            },
                            "required": ["message"]
                        }
                    }
                ]
            }
        })
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "get_current_time":
            now = datetime.datetime.now().isoformat()
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"Current local time is: {now}"}
                    ]
                }
            })
        elif tool_name == "evaluate_math":
            expr = args.get("expression", "")
            try:
                allowed_names = {"math": math, "abs": abs, "round": round, "pow": pow}
                val = eval(expr, {"__builtins__": None}, allowed_names)
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Result of `{expr}` = {val}"}
                        ]
                    }
                })
            except Exception as e:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error evaluating `{expr}`: {str(e)}"}
                        ],
                        "isError": True
                    }
                })
        elif tool_name == "echo":
            msg = args.get("message", "")
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"Echo: {msg}"}
                    ]
                }
            })
        else:
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found"
                }
            })
    else:
        if req_id is not None:
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found"
                }
            })

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            handle_request(req)
        except Exception as e:
            sys.stderr.write(f"Error parsing line: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
