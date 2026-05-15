from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if not Path(ROOT / ".env.local").exists():
        print("Missing .env.local")
        return 1

    import modal

    modal.config.set_active_environment(os.getenv("MODAL_ENVIRONMENT", "default"))
    from modal_app import app  # noqa: E402

    with modal.enable_output():
        app.deploy()
    print("Deployed Modal app:", app.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
