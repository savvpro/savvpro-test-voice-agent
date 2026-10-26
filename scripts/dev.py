"""Start both local services after explicit demo setup. Ctrl+C stops both."""
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the Riverside local demo")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        parser.error("Node.js 24 and npm 11 are required.")
    environment = dict(os.environ)
    environment["API_PROXY_TARGET"] = f"http://127.0.0.1:{args.backend_port}"
    environment["ALLOWED_ORIGINS"] = f"http://127.0.0.1:{args.frontend_port},http://127.0.0.1:{args.backend_port}"
    for command in ([sys.executable, "-m", "lost_property.cli", "migrate"], [sys.executable, "-m", "lost_property.cli", "seed", "--demo"]):
        subprocess.run(command, cwd=root / "backend", env=environment, check=True)
    commands = [
        ([sys.executable, "-m", "uvicorn", "lost_property.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(args.backend_port)], root / "backend"),
        ([npm, "run", "dev", "--", "--port", str(args.frontend_port), "--strictPort"], root / "frontend"),
    ]
    children: list[subprocess.Popen[bytes]] = []
    try:
        for command, directory in commands:
            children.append(subprocess.Popen(command, cwd=directory, env=environment, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, start_new_session=os.name != "nt"))
        print(f"\nRiverside is starting at http://127.0.0.1:{args.frontend_port}\nPress Ctrl+C to stop both services.\n", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
