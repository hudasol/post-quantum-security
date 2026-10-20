#!/bin/sh
# Install ProVerif at a pinned version from the source tarball of its home page.
# ProVerif is distributed under the GNU GPL version 2 (stated on the install page).
# The source is built outside the repository and never committed.
# Requirements: an OCaml native compiler (tested with OCaml 4.14.1 from the
# Ubuntu 24.04 package ocaml-nox), make and curl.
set -eu
PROVERIF_VERSION="2.05"
PROVERIF_URL="https://bblanche.gitlabpages.inria.fr/proverif/proverif${PROVERIF_VERSION}.tar.gz"
PROVERIF_SHA256_FILE="$(cd "$(dirname "$0")" && pwd)/proverif.sha256"
REPO_PARENT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${THIRD_PARTY:-$REPO_PARENT/third_party}/proverif"

if ! command -v ocamlopt >/dev/null 2>&1; then
  echo "ocamlopt not found; on Ubuntu 24.04 install it with: apt-get install ocaml-nox" >&2
  exit 1
fi
mkdir -p "$DEST"
cd "$DEST"
if [ ! -f "proverif${PROVERIF_VERSION}.tar.gz" ]; then
  curl -sSfL -o "proverif${PROVERIF_VERSION}.tar.gz" "$PROVERIF_URL"
fi
EXPECTED="$(cut -d' ' -f1 "$PROVERIF_SHA256_FILE")"
ACTUAL="$(sha256sum "proverif${PROVERIF_VERSION}.tar.gz" | cut -d' ' -f1)"
if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "checksum mismatch: expected $EXPECTED got $ACTUAL" >&2
  exit 1
fi
tar xzf "proverif${PROVERIF_VERSION}.tar.gz"
cd "proverif${PROVERIF_VERSION}"
nice -n 10 ./build -nointeract
./proverif -help 2>&1 | head -1 || true
echo "ProVerif ${PROVERIF_VERSION} installed at $DEST/proverif${PROVERIF_VERSION}/proverif"
