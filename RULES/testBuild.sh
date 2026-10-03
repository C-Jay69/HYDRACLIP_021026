#!/bin/bash
#
# Build verification.
#
# The previous version ran `npx vite build --outDir /workspace/.dist`. This
# project does not use Vite at all (CLAUDE.md explicitly says not to), there is
# no Vite config, and `/workspace` does not exist — so the script could only
# ever fail. The real build is Bun's bundler via build.ts.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

if ! command -v bun >/dev/null 2>&1; then
  echo "bun is required but was not found on PATH."
  echo "Install it from https://bun.sh or with: npm install -g bun"
  exit 1
fi

# Type check first: the bundler happily emits output for code that does not
# type check, so a green build alone is not enough signal.
TYPES=$(bunx tsc --noEmit 2>&1)
TYPES_RC=$?

if [ $TYPES_RC -ne 0 ]; then
  echo "❌ Type check failed:"
  echo "$TYPES"
  exit $TYPES_RC
fi

OUTPUT=$(bun run build 2>&1)
BUILD_RC=$?

if [ $BUILD_RC -ne 0 ]; then
  echo "❌ Build failed:"
  echo "$OUTPUT"
  exit $BUILD_RC
fi

# A build that emits an empty JS chunk means the HTML entry never referenced
# the app script — the page would serve a 200 and render nothing. Guard it.
JS_BYTES=$(find dist -name '*.js' -not -name '*.map' -exec cat {} + 2>/dev/null | wc -c)

if [ "${JS_BYTES:-0}" -lt 10000 ]; then
  echo "❌ Build produced ${JS_BYTES:-0} bytes of JavaScript."
  echo "   The React entry is probably not referenced from src/index.html."
  echo "   Expected: <script type=\"module\" src=\"./frontend.tsx\"></script>"
  exit 1
fi

if ! find dist -name '*.css' | grep -q .; then
  echo "❌ Build produced no CSS. Tailwind is not being bundled."
  exit 1
fi

echo "$OUTPUT"
echo "✅ Build verified (${JS_BYTES} bytes of JS, CSS emitted)."
exit 0
