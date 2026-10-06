from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


CUAD_ZENODO_URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip?download=1"


def _download(url: str, destination: Path, timeout: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def _safe_extract(zip_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target_path = (destination / member.filename).resolve()
            if destination not in target_path.parents and target_path != destination:
                raise RuntimeError(f"Unsafe path in archive: {member.filename}")
        archive.extractall(destination)


def _has_files(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and extract the CUAD dataset.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/cuad"),
        help="Directory where the CUAD archive should be extracted.",
    )
    parser.add_argument(
        "--url",
        default=CUAD_ZENODO_URL,
        help="CUAD archive URL. Defaults to the official Zenodo release.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and re-extract even if the output directory already has files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir: Path = args.output_dir

    if _has_files(output_dir) and not args.force:
        print(f"CUAD already exists in {output_dir}. Use --force to overwrite.", file=sys.stderr)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "CUAD_v1.zip"
        print(f"Downloading CUAD from {args.url}")
        _download(args.url, archive_path, args.timeout)

        if args.force and _has_files(output_dir):
            for child in list(output_dir.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()

        print(f"Extracting to {output_dir}")
        _safe_extract(archive_path, output_dir)

    print("CUAD download complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
