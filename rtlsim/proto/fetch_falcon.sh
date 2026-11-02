#!/usr/bin/env bash
# Round 7: fetch liboqs at the pinned release tag into PROTO_TP, outside the repository, for its Falcon-512 folder.
# Nothing fetched here is committed. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../config.sh"
source "$HERE/config.sh"
mkdir -p "$PROTO_TP"
D="$PROTO_TP/liboqs"
if [ ! -d "$D/.git" ]; then
  git clone -q --depth 1 --branch "$LIBOQS_TAG" "$LIBOQS_URL" "$D"
fi
[ "$(git -C "$D" rev-parse HEAD)" = "$LIBOQS_COMMIT" ]
echo "$D at $(git -C "$D" rev-parse HEAD) (tag $LIBOQS_TAG)"
head -3 "$D/$FALCON_SUBDIR/LICENSE"
