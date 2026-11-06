#!/usr/bin/env python3
"""
Clone Tool for IPA Uploader Repos
Creates a new IPA uploader repo from the template with new secrets.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

TEMPLATE_DIR = Path("/Users/qumi/Documents/applepass/shares/01/ipa_uploader")
DEFAULT_BASE_DIR = Path("/Users/qumi/Documents/applepass/shares/01")


def run_cmd(cmd: list[str], check=True) -> str:
    """Run a shell command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    if result.returncode != 0 and check:
        print(f"Error running: {' '.join(cmd)}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def create_local_repo(new_name: str, base_dir: Path, secrets: dict) -> Path:
    """Create a new repo from template with updated secrets."""
    new_repo_dir = base_dir / new_name

    if new_repo_dir.exists():
        print(f"Error: Directory {new_repo_dir} already exists")
        sys.exit(1)

    # Copy template
    print(f"Copying template to {new_repo_dir}...")
    shutil.copytree(TEMPLATE_DIR, new_repo_dir, ignore=shutil.ignore_patterns('.git', '.DS_Store'))

    # Update api_key.json
    api_key_path = new_repo_dir / "fastlane" / "api_key.json"
    with open(api_key_path) as f:
        api_key_json = json.load(f)

    api_key_json["key_id"] = secrets["key_id"]
    api_key_json["issuer_id"] = secrets["issuer_id"]
    api_key_json["key"] = secrets["p8_key"]

    with open(api_key_path, "w") as f:
        json.dump(api_key_json, f, indent=2)

    # Update workflow - replace old values with variables
    workflow_path = new_repo_dir / ".github" / "workflows" / "appstore_upload.yml"
    with open(workflow_path) as f:
        workflow_content = f.read()

    # Replace bundle ID and IPA path with secrets references
    workflow_content = workflow_content.replace(
        'IPA_PATH: ${{ secrets.IPA_PATH }}',
        f'IPA_PATH: ./{secrets["ipa_path"]}'
    )
    workflow_content = workflow_content.replace(
        'APP_IDENTIFIER: ${{ secrets.APP_IDENTIFIER }}',
        f'APP_IDENTIFIER: {secrets["bundle_id"]}'
    )

    with open(workflow_path, "w") as f:
        f.write(workflow_content)

    # Update README
    readme_path = new_repo_dir / "README.md"
    readme_content = f"""# {new_name}

iOS IPA Uploader using Fastlane + GitHub Actions

## Secrets Configured
- Key ID: {secrets["key_id"]}
- Bundle ID: {secrets["bundle_id"]}
- IPA Path: ./{secrets["ipa_path"]}

## Usage
1. Add your IPA file
2. Commit and push
3. Go to GitHub Actions and run the workflow
"""
    with open(readme_path, "w") as f:
        f.write(readme_content)

    # Initialize git
    run_cmd(["git", "init"], check=False)
    run_cmd(["git", "add", "."])
    run_cmd(["git", "commit", "-m", "Initial commit with IPA uploader setup"])

    # Update .gitignore
    gitignore_path = new_repo_dir / ".gitignore"
    with open(gitignore_path, "w") as f:
        f.write("*.ipa\n*.xcarchive\nbuild/\nDerivedData/\n")

    return new_repo_dir


def setup_github_secrets(repo_dir: Path, repo_url: str, secrets: dict):
    """Set up GitHub secrets using gh CLI."""
    # Extract owner/repo from URL
    # e.g., https://github.com/owner/repo.git -> owner/repo
    parts = repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
    gh_repo = f"{parts[-2]}/{parts[-1]}"

    print(f"\nSetting up GitHub secrets for {gh_repo}...")

    # Set secrets via gh
    secret_cmds = [
        ["gh", "secret", "set", "APP_STORE_CONNECT_KEY_ID", "-b", secrets["key_id"], "-R", gh_repo],
        ["gh", "secret", "set", "APP_STORE_CONNECT_ISSUER_ID", "-b", secrets["issuer_id"], "-R", gh_repo],
        ["gh", "secret", "set", "APP_STORE_CONNECT_API_KEY", "-b", secrets["p8_key"], "-R", gh_repo],
    ]

    for cmd in secret_cmds:
        print(f"Running: {' '.join(cmd[:3])}...")
        run_cmd(cmd)

    print("Secrets set successfully!")


def interactive_clone():
    """Interactive cloning wizard."""
    print("=" * 50)
    print("IPA Uploader Clone Tool")
    print("=" * 50)

    # Get inputs
    new_name = input("\nNew repo name (e.g., my_ipa_uploader): ").strip()
    base_dir = input(f"Base directory [{DEFAULT_BASE_DIR}]: ").strip()
    base_dir = Path(base_dir) if base_dir else DEFAULT_BASE_DIR

    key_id = input("App Store Connect Key ID: ").strip()
    issuer_id = input("App Store Connect Issuer ID: ").strip()

    print("Paste the .p8 private key content (BEGIN PRIVATE KEY to END PRIVATE KEY):")
    print("(Press Ctrl+D when done)")
    p8_lines = []
    try:
        while True:
            p8_lines.append(input())
    except EOFError:
        pass
    p8_key = "\n".join(p8_lines)

    bundle_id = input("Bundle ID (e.g., com.company.app): ").strip()
    ipa_name = input("IPA filename (e.g., MyApp.ipa): ").strip()

    secrets = {
        "key_id": key_id,
        "issuer_id": issuer_id,
        "p8_key": p8_key,
        "bundle_id": bundle_id,
        "ipa_path": ipa_name,
    }

    # Create local repo
    new_repo_dir = create_local_repo(new_name, base_dir, secrets)

    # GitHub setup
    print("\n" + "=" * 50)
    print("GitHub Setup")
    print("=" * 50)
    print("1. Create a new GitHub repo and get the URL")
    print("2. Push your local repo to GitHub")

    push_now = input("\nHave you created the GitHub repo? (y/n): ").strip().lower()

    if push_now == "y":
        repo_url = input("GitHub repo URL: ").strip()

        # Add remote and push
        os.chdir(new_repo_dir)
        run_cmd(["git", "remote", "add", "origin", repo_url])
        run_cmd(["git", "push", "-u", "origin", "main"])

        # Set up secrets
        setup_github_secrets(new_repo_dir, repo_url, secrets)

    print("\n" + "=" * 50)
    print(f"Done! Repo created at: {new_repo_dir}")
    print("=" * 50)


if __name__ == "__main__":
    interactive_clone()
