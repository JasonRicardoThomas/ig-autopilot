#!/usr/bin/env bash
# Commit data changes from a workflow; retry on push races.
set -e
git config user.name "autopilot"; git config user.email "autopilot@users.noreply.github.com"
git add data
if git diff --cached --quiet; then echo "nothing to commit"; exit 0; fi
git commit -m "${1:-autopilot update}"
for i in 1 2 3; do git pull --rebase origin main && git push origin HEAD:main && exit 0; sleep 5; done
exit 1
