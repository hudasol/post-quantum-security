#!/usr/bin/env bash
# Fetch Renode (free, MIT licence) at a pinned release, outside the repository, and check its hash.
# Author: Huda Mueen. Used only by renode_check.py (label emulated). Usage:
#   DEST=<directory outside the repository> bash bench/board_kit/fetch_renode.sh
# then: RENODE_BIN=$DEST/renode_1.16.1-dotnet_portable/renode python3 bench/board_kit/renode_check.py
set -euo pipefail
VER=1.16.1
FILE=renode-$VER.linux-portable-dotnet.tar.gz
SHA=00e113cdbd0f5354cf2f64bbe3f5a070d8958409542fca66e45ac97d982938c0
DEST=${DEST:?set DEST to a directory outside the repository}
mkdir -p "$DEST"
cd "$DEST"
[ -f "$FILE" ] || curl -sSL -o "$FILE" "https://github.com/renode/renode/releases/download/v$VER/$FILE"
echo "$SHA  $FILE" | sha256sum -c -
[ -d "renode_$VER-dotnet_portable" ] || tar xzf "$FILE"
echo "renode at $DEST/renode_$VER-dotnet_portable/renode"
