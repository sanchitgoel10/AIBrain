#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
git config core.hooksPath "Brain/.githooks"
echo "Installed hooks for ${repo_root}/Brain"
