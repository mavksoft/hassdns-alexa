#!/bin/sh
# Rebuilds hassdns-alexa-panel.js: bundles Lit into the panel source so the
# integration serves a single self-contained file (no CDN imports — required
# by HACS review, hacs/default#14507).
#
# Needs esbuild + lit installed once:
#   npm install --prefix _tools/build esbuild lit@2.8.0
set -eu
cd "$(dirname "$0")/../../.."
ESBUILD="${ESBUILD:-_tools/build/node_modules/@esbuild/darwin-x64/bin/esbuild}"
"$ESBUILD" custom_components/hassdns_alexa/frontend/src/hassdns-alexa-panel.js \
  --bundle --format=esm \
  --alias:lit="$PWD/_tools/build/node_modules/lit/index.js" \
  --outfile=custom_components/hassdns_alexa/frontend/hassdns-alexa-panel.js
