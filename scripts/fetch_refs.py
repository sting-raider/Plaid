#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK = ROOT / "refs.lock.toml"
REFS = ROOT / ".refs"


def run(*args: str, cwd: pathlib.Path | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    data = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    REFS.mkdir(exist_ok=True)

    for item in data["repo"]:
        dst = REFS / item["name"]
        if not dst.exists():
            run("git", "clone", "--filter=blob:none", "--no-checkout", item["url"], str(dst))
        run("git", "fetch", "origin", item["rev"], cwd=dst)
        run("git", "checkout", "--detach", item["rev"], cwd=dst)

    return 0


if __name__ == "__main__":
    sys.exit(main())
