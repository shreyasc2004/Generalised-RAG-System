"""Cross-platform bootstrap. Run with: python scripts/setup.py"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import venv


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up folder RAG without a separate database installation")
    parser.add_argument("--dev", action="store_true", help="Include test dependencies")
    parser.add_argument("--skip-model", action="store_true", help="Defer the embedding model download until first use")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 or newer is required.")
    root = Path(__file__).resolve().parents[1]
    environment = root / ".venv"
    executable = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not executable.exists():
        venv.create(environment, with_pip=True)
    subprocess.run([str(executable), "-m", "pip", "install", "--upgrade", "pip"], cwd=root, check=True)
    target = f"{root}[dev]" if args.dev else str(root)
    subprocess.run([str(executable), "-m", "pip", "install", "-e", target], cwd=root, check=True)
    command = [str(executable), "-m", "rag", "init"]
    if not args.skip_model:
        command.append("--download-model")
    subprocess.run(command, cwd=root, check=True)
    print(f"Ready. Put documents in: {root / 'Knowledge base' / 'kb'}")
    print(f'Run: "{executable}" -m rag serve')


if __name__ == "__main__":
    main()

