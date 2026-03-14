import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from client.print_monitor import run_background_client


def main() -> None:
    parser = argparse.ArgumentParser(description="CyberCafe print monitor client")
    parser.add_argument("--server-url", default="http://127.0.0.1:8787", help="Central server base URL")
    parser.add_argument("--poll-interval", type=float, default=1.2, help="Spooler polling interval in seconds")
    args = parser.parse_args()

    run_background_client(server_url=args.server_url, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
