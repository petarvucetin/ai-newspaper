---
name: block-push-to-main
enabled: true
event: bash
pattern: git\s+push.*(?:main|master)
action: block
---

🛑 **Push to main blocked!**

You requested that all code must be committed and merged to main by a human, not automatically.

**What you tried:** Pushing to the main/master branch

**What to do instead:**
1. Push to a feature branch: `git push origin feature-branch-name`
2. Create a pull request for human review
3. Have a teammate review and merge the changes to main

**If you really need to push to main:**
- Get explicit permission from a team member first
- Edit `.claude/hookify.push-to-main.local.md` and set `enabled: false` to temporarily disable this rule
