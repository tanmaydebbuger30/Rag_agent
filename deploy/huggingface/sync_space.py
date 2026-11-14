"""Upload the app to a Hugging Face Docker Space.

Usage:
    HF_TOKEN=hf_... python deploy/huggingface/sync_space.py <username>/<space-name>
    python deploy/huggingface/sync_space.py <username>/<space-name> --dry-run   # stage only

Only the files the Docker image needs are uploaded. The guidance PDFs are left
out: the app reads the prebuilt data/processed/regulatory_chunks.jsonl, so the
Space never has to store large binaries. The Space README (with the YAML header
Hugging Face reads: sdk, app_port) replaces the project README.
"""
import argparse
import os
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPACE_README = Path(__file__).with_name("SPACE_README.md")

INCLUDE = ["Dockerfile", ".dockerignore", "requirements.txt", "backend", "frontend", "data"]
IGNORE = ["__pycache__", "*.pyc", "node_modules", "dist", "*.pdf", ".DS_Store", "*.sqlite3"]
SYNCED_PATHS = ["backend/**", "frontend/**", "data/**", "Dockerfile", ".dockerignore", "requirements.txt"]


def stage(dest: Path) -> list[str]:
    for name in INCLUDE:
        src = REPO / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=shutil.ignore_patterns(*IGNORE))
        else:
            shutil.copy2(src, dest / name)
    shutil.copy2(SPACE_README, dest / "README.md")
    return sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("space", help="<username>/<space-name>")
    parser.add_argument("--dry-run", action="store_true", help="stage files and print them; upload nothing")
    parser.add_argument("--stage-dir", help="stage into this folder instead of a temporary one")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(args.stage_dir or tmp)
        dest.mkdir(parents=True, exist_ok=True)
        files = stage(dest)
        size = sum((dest / f).stat().st_size for f in files)
        print(f"Staged {len(files)} files ({size / 1e6:.1f} MB) for {args.space}")
        if args.dry_run:
            print("\n".join(files))
            return

        from huggingface_hub import HfApi

        api = HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)
        api.upload_folder(
            repo_id=args.space,
            repo_type="space",
            folder_path=dest,
            commit_message="Sync from GitHub",
            delete_patterns=SYNCED_PATHS,      # remove files that no longer exist in the repo
        )
        print(f"Uploaded. The Space rebuilds automatically: https://huggingface.co/spaces/{args.space}")


if __name__ == "__main__":
    main()
