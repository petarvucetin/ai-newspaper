## Deployment

- **Every commit auto-bumps** the patch version in `app/__init__.py` and **deploys to Docker** via the `.git/hooks/post-commit` hook.
- Docker runs on **port 8001** (mapped from container's 8000).
- The hook commits the version bump separately with prefix `build:` to prevent recursion.
- If the hook fails, run manually: `bash scripts/bump-and-deploy.sh`
- Never skip the post-commit hook (`--no-verify`) unless fixing the hook itself.
