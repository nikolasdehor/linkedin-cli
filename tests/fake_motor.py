#!/usr/bin/env python3
"""Motor MCP falso: espelha tools/call para testar o transporte stdio."""

import json
import os
import sys


def _read_msg():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    if "--status" in sys.argv:
        if os.environ.get("FAKE_NO_SESSION"):
            sys.stdout.write("No valid source session found\n")
            return 1
        sys.stdout.write("session ok\n")
        return 0
    while True:
        msg = _read_msg()
        if msg is None:
            return 0
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-motor", "version": "0"},
            }})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/call":
            name = msg["params"]["name"]
            args = msg["params"].get("arguments", {})
            if name == "boom":
                _send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": "No valid LinkedIn session was found."}],
                    "isError": True,
                }})
            else:
                _send({"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": json.dumps({"tool": name, "args": args})}],
                }})
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": mid, "result": {"tools": []}})
        else:
            _send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "nope"}})


if __name__ == "__main__":
    sys.exit(main())
