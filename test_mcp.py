import unittest
import os
import json
import time
from mcp_client import MCPManager

class TestMCPClient(unittest.TestCase):
    def setUp(self):
        self.test_config = "test_mcp_servers.json"
        config_data = {
            "mcpServers": {
                "test_math": {
                    "command": "python3",
                    "args": ["sample_mcp_server.py"],
                    "enabled": True
                }
            }
        }
        with open(self.test_config, "w") as f:
            json.dump(config_data, f, indent=2)

        self.manager = MCPManager(self.test_config)
        self.manager.start_all()

    def tearDown(self):
        self.manager.stop_all()
        if os.path.exists(self.test_config):
            os.remove(self.test_config)

    def test_tools_discovery(self):
        tools = self.manager.get_openai_tools()
        self.assertGreater(len(tools), 0)
        names = [t["function"]["name"] for t in tools]
        self.assertIn("test_math__get_current_time", names)
        self.assertIn("test_math__evaluate_math", names)

    def test_tool_execution(self):
        result = self.manager.execute_tool_call("test_math__evaluate_math", {"expression": "15 * 8"})
        self.assertIn("120", result)

        time_res = self.manager.execute_tool_call("test_math__get_current_time", {})
        self.assertIn("Current local time is", time_res)

if __name__ == "__main__":
    unittest.main()
