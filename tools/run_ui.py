from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    os.environ.setdefault("STREAMLIT_SERVER_PORT", "8501")
    os.environ.setdefault("STREAMLIT_SERVER_ADDRESS", "localhost")
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(ROOT / "src" / "youtube_content_studio" / "ui" / "app.py"),
        "--server.address",
        os.environ["STREAMLIT_SERVER_ADDRESS"],
        "--server.port",
        os.environ["STREAMLIT_SERVER_PORT"],
    ]
    stcli.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
