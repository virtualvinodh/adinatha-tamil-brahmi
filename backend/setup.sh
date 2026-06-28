#!/bin/bash
set -e

VERSION="0.22.9"
DEST="$(dirname "$0")"

echo "Downloading PocketBase v${VERSION}..."
curl -L -o /tmp/pocketbase.zip \
  "https://github.com/pocketbase/pocketbase/releases/download/v${VERSION}/pocketbase_${VERSION}_linux_amd64.zip"

unzip -o /tmp/pocketbase.zip pocketbase -d "$DEST"
chmod +x "$DEST/pocketbase"
echo "Done. Run: make pocketbase"
echo "Then open http://127.0.0.1:8090/_/ to create admin and import backend/pb_schema.json"
