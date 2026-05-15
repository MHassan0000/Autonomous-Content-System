from __future__ import annotations

import json
from pathlib import Path

import modal


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_DIR = ROOT / ".tmp" / "downloads"
OUTPUT_VOLUME_NAME = "autonomous-content-system-output"


def _read_volume_text(volume, path: str) -> str:
    data = b""
    for chunk in volume.read_file(path):
        data += chunk
    return data.decode("utf-8")


def _read_volume_bytes(volume, path: str) -> bytes:
    data = b""
    for chunk in volume.read_file(path):
        data += chunk
    return data


def _find_latest_report(volume) -> tuple[str, str | None, str | None]:
    try:
        latest = json.loads(_read_volume_text(volume, "latest.json"))
        pdf_path = latest.get("volume_pdf_path")
        manifest_path = latest.get("volume_manifest_path")
        run_id = latest.get("run_id", "latest")
        if pdf_path:
            return run_id, pdf_path, manifest_path
    except Exception:
        pass

    candidates: list[str] = []
    for entry in volume.listdir("/", recursive=True):
        path = getattr(entry, "path", None) or getattr(entry, "name", None) or str(entry)
        if isinstance(path, str) and path.endswith("report.pdf"):
            candidates.append(path.lstrip("/"))

    if not candidates:
        raise SystemExit("No report.pdf found in the Modal Volume. Run the workflow first.")

    candidates.sort()
    pdf_path = candidates[-1]
    manifest_path = pdf_path.replace("report.pdf", "manifest.json")
    run_id = Path(pdf_path).parent.name
    return run_id, pdf_path, manifest_path


def main() -> int:
    volume = modal.Volume.from_name(OUTPUT_VOLUME_NAME)

    run_id, pdf_path, manifest_path = _find_latest_report(volume)
    target_dir = DOWNLOAD_DIR / run_id
    target_dir.mkdir(parents=True, exist_ok=True)

    pdf_target = target_dir / "report.pdf"
    pdf_target.write_bytes(_read_volume_bytes(volume, pdf_path))

    manifest_target = target_dir / "manifest.json"
    try:
        manifest_target.write_text(_read_volume_text(volume, manifest_path), encoding="utf-8")
    except Exception:
        manifest_target = None

    print(str(pdf_target))
    if manifest_target:
        print(str(manifest_target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
