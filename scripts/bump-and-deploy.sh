#!/usr/bin/env bash
# Bump patch version in app/__init__.py and rebuild+restart Docker container.
# Called automatically by Claude Code post-commit hook.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

VERSION_FILE="app/__init__.py"

# --- Bump patch version ---
current=$(grep -oP '(?<=__version__ = ")[^"]+' "$VERSION_FILE")
IFS='.' read -r major minor patch <<< "$current"
patch=$((patch + 1))
new_version="$major.$minor.$patch"

sed -i "s/__version__ = \"$current\"/__version__ = \"$new_version\"/" "$VERSION_FILE"
echo "Version: $current -> $new_version"

# Amend the commit to include the version bump
git add "$VERSION_FILE"
git commit --amend --no-edit --no-verify

# --- Docker rebuild & deploy ---
echo "Building and deploying Docker container..."
docker compose up --build -d

echo "Deploy complete. Running on port 8001."
