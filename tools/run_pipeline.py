from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_content_studio.config import load_settings  # noqa: E402
from youtube_content_studio.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    settings = load_settings()
    if not settings.openrouter_api_key:
        print("Missing OPENROUTER_API_KEY in environment or .env")
        return 1

    result = asyncio.run(run_pipeline(settings))
    print(result.pdf_path)
    print(result.manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
