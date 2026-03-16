import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from client.print_monitor import run_background_client
from runtime_config import load_config_file


def main() -> None:
    parser = argparse.ArgumentParser(description="ManAni print monitor client")
    parser.add_argument("--config", default=None, help="Path to settings.json")
    parser.add_argument("--server-url", default=None, help="Central server base URL")
    parser.add_argument("--poll-interval", type=float, default=None, help="Spooler polling interval in seconds")
    args = parser.parse_args()

    config_path = args.config or os.path.join(ROOT, "config", "settings.json")
    config = load_config_file(config_path)

    server_url = args.server_url or str(config.get("central_server_url", "http://127.0.0.1:8787"))
    poll_interval = args.poll_interval if args.poll_interval is not None else float(config.get("poll_interval", 0.5))
    computer_name = str(config.get("computer_name", "")).strip() or None
    operator_id = str(config.get("operator_id", "")).strip() or "ADMIN"
    run_background_client(
        server_url=server_url,
        poll_interval=poll_interval,
        computer_name=computer_name,
        operator_id=operator_id,
    )


if __name__ == "__main__":
    main()
