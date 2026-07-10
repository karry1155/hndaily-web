#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path


def _link_or_copy(source, target):
    try: os.link(source, target)
    except OSError: shutil.copy2(source, target)


def prepare_staged_content(content_root, staged_content):
    if staged_content.exists(): shutil.rmtree(staged_content)
    staged_content.mkdir(parents=True)
    for name in ("items", "indexes", "weekly"):
        source = content_root / name
        if source.exists(): shutil.copytree(source, staged_content / name, copy_function=_link_or_copy)


def publish_staged_generation(content_root, staged_content, site_root, staged_site, audit_path, staged_audit, *, fail_after_content=False):
    entries = [(content_root / "items", staged_content / "items"), (content_root / "indexes", staged_content / "indexes"), (site_root, staged_site), (audit_path, staged_audit)]
    journal = []
    try:
        for index, (target, staged) in enumerate(entries):
            backup = target.with_name(f".{target.name}.radar-backup")
            if backup.exists():
                shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
            target.parent.mkdir(parents=True, exist_ok=True)
            had = target.exists()
            if had: target.replace(backup)
            staged.replace(target); journal.append((target, backup, had))
            if fail_after_content and index == 1: raise RuntimeError("injected publish failure")
    except Exception:
        for target, backup, had in reversed(journal):
            if target.exists(): shutil.rmtree(target) if target.is_dir() else target.unlink()
            if had and backup.exists(): backup.replace(target)
        raise
    else:
        for _, backup, _ in journal:
            if backup.exists(): shutil.rmtree(backup) if backup.is_dir() else backup.unlink()


def main(argv):
    if len(argv) == 4 and argv[1] == "prepare": prepare_staged_content(Path(argv[2]), Path(argv[3])); return 0
    if len(argv) == 8 and argv[1] == "publish": publish_staged_generation(*map(Path, argv[2:])); return 0
    print("Usage: radar_transaction.py prepare CONTENT STAGED | publish CONTENT STAGED SITE STAGED_SITE AUDIT STAGED_AUDIT", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main(sys.argv))
