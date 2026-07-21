from __future__ import annotations

import argparse
import tarfile
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath


FORBIDDEN_PATH_PARTS = {"MonoDemo", "artifacts"}
FORBIDDEN_FILENAMES = {"design-qa.md", "verification-report.md"}
CONTENT_MARKERS = (
    b"/" + b"Users" + b"/",
    b"/private" + b"/tmp/",
    b"Mono" + b"-QA-",
)


def archives_in(paths: Iterable[Path]) -> list[Path]:
    archives: list[Path] = []
    for path in paths:
        if path.is_dir():
            archives.extend(sorted(path.glob("*.tar.gz")))
            archives.extend(sorted(path.glob("*.whl")))
        else:
            archives.append(path)
    return archives


def validate_member(archive: Path, name: str, data: bytes) -> list[str]:
    errors: list[str] = []
    parts = set(PurePosixPath(name).parts)
    if parts & FORBIDDEN_PATH_PARTS or PurePosixPath(name).name in FORBIDDEN_FILENAMES:
        errors.append(f"{archive.name}: forbidden path {name}")
    for marker in CONTENT_MARKERS:
        if marker in data:
            errors.append(f"{archive.name}: private marker in {name}: {marker.decode()}")
    return errors


def validate_archive(path: Path) -> list[str]:
    errors: list[str] = []
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                data = handle.read() if handle is not None else b""
                errors.extend(validate_member(path, member.name, data))
    elif path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                errors.extend(validate_member(path, name, archive.read(name)))
    else:
        errors.append(f"Unsupported distribution archive: {path}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Reject internal QA material in public distributions.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    archives = archives_in(args.paths)
    if not archives:
        raise SystemExit("No distribution archives found")

    errors = [error for archive in archives for error in validate_archive(archive)]
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Public distribution contents verified: {', '.join(path.name for path in archives)}")


if __name__ == "__main__":
    main()
