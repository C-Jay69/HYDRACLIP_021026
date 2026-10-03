#!/bin/bash
#
# Static analysis gate.
#
# Previously this script scanned `.rules/<name>.yml`, but the rule files live in
# `RULES/` — every single scan silently resolved to a missing path. It also
# assumed `ast-grep` was installed and referenced two rule files
# (useAuth.yml / authProvider.yml) that do not exist in this repo.

set -uo pipefail

RULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$RULES_DIR/.." && pwd)"
cd "$REPO_ROOT" || exit 1

if ! command -v ast-grep >/dev/null 2>&1; then
  echo "⏭  ast-grep is not installed — skipping static rule scan."
  echo "   Install it with: bun add -g @ast-grep/cli"
  exit 0
fi

RULES=(
  SelectItem.yml
  contrast.yml
  toast-hook.yml
  slot-nesting.yml
  require-button-interaction.yml
  supabase-google-sso.yml
  supabase-edge-function-get-body.yml
  no-csp-meta.yml
)

status=0

for rule in "${RULES[@]}"; do
  rule_path="$RULES_DIR/$rule"

  if [ ! -f "$rule_path" ]; then
    echo "⏭  Skipping missing rule: $rule"
    continue
  fi

  output=$(ast-grep scan -r "$rule_path" 2>&1)
  rc=$?

  if [ -n "$output" ]; then
    echo "=== $rule ==="
    echo "$output"
    echo ""
  fi

  if [ $rc -ne 0 ]; then
    status=1
  fi
done

# useAuth without an AuthProvider is only a problem when useAuth is actually used.
useauth_rule="$RULES_DIR/useAuth.yml"
authprovider_rule="$RULES_DIR/authProvider.yml"

if [ -f "$useauth_rule" ] && [ -f "$authprovider_rule" ]; then
  useauth_output=$(ast-grep scan -r "$useauth_rule" 2>/dev/null)

  if [ -n "$useauth_output" ]; then
    authprovider_output=$(ast-grep scan -r "$authprovider_rule" 2>/dev/null)

    if [ -z "$authprovider_output" ]; then
      echo "⚠️  Issue detected:"
      echo "The code uses the useAuth hook but no AuthProvider wraps the component tree."
      echo ""
      echo "Suggested fixes:"
      echo "1. Add an AuthProvider wrapper in App.tsx or the root component"
      echo "2. Ensure all components using useAuth sit inside the AuthProvider scope"
      status=1
    fi
  fi
fi

if [ $status -eq 0 ]; then
  echo "✅ Static rule scan passed."
fi

exit $status
