"""
MarketScope Root Server Launcher
Runs the MarketScope backend server from the workspace root.
Usage:
    python server.py [--host 127.0.0.1] [--port 8765]
"""

import sys
from pathlib import Path

root_dir = Path(__file__).parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import importlib.util
server_py = root_dir / "marketscope" / "server.py"
spec = importlib.util.spec_from_file_location("marketscope_server", str(server_py))
ms_server = importlib.util.module_from_spec(spec)
sys.modules["marketscope_server"] = ms_server
spec.loader.exec_module(ms_server)
run_server = ms_server.run_server

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MarketScope HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
