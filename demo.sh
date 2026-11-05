#!/usr/bin/env bash
# demo.sh - walks through everything the recorded demonstration must show.
#
#   ./demo.sh            run the whole walkthrough top to bottom
#   ./demo.sh --pause    wait for Enter after each command (handy while recording)
#
# CODING_AGENT_IDENTIFIED_FLAG: developed with a coding agent as the handout
# requires; the flag marks the source throughout.
#
# It copies products.py into a fresh scratch directory and runs there, so the
# repository stays clean and the script can be rerun any number of times.
# Sections are labelled with the rubric criteria they demonstrate.

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="${TMPDIR:-/tmp}"
WORK="$(mktemp -d "${TMP%/}/products-demo.XXXXXX")"
cp "$REPO/products.py" "$WORK/"
cd "$WORK" || exit 1

PAUSE=0
[ "${1:-}" = "--pause" ] && PAUSE=1

if command -v shasum >/dev/null 2>&1; then SHA="shasum -a 256"; else SHA="sha256sum"; fi

heading() { printf '\n\033[1;36m==== %s ====\033[0m\n' "$*"; }
note()    { printf '\033[2m# %s\033[0m\n' "$*"; }
run() {
  printf '\n\033[1m$ %s\033[0m\n' "$1"
  eval "$1"
  local status=$?
  if [ "$status" -eq 0 ]; then
    printf '\033[32m[exit %d]\033[0m\n' "$status"
  else
    printf '\033[31m[exit %d]\033[0m\n' "$status"
  fi
  if [ "$PAUSE" -eq 1 ]; then read -r -p '(Enter to continue) ' </dev/tty; fi
}

heading "0. Setup"
note "A scratch directory holding a copy of products.py. No products.json exists yet."
run 'pwd'
run 'ls'
run 'python3 products.py --help'

heading "1. Required success sequence (A1-14)"
note "list with no data file at all prints an empty array"
run 'python3 products.py list'
run 'python3 products.py add --name "Notebook" --price 4.5 --quantity 10'
run 'python3 products.py add --name "Pencil" --price 1.25 --quantity 5'
run 'python3 products.py list'
run 'python3 products.py get 1'
note "update only the supplied field: name and price are preserved"
run 'python3 products.py update 1 --quantity 12'
run 'python3 products.py delete 2 --yes'
run 'python3 products.py list'
note "final data: only Notebook, price \"4.50\", quantity 12, next_id stays 3"
run 'cat products.json'
note "a brand-new invocation still reads the saved data"
run 'python3 products.py get 1'
note "delete 2 freed nothing: next_id is still 3, so the next add gets id 3"
run 'python3 products.py add --name "Ruler" --price 2 --quantity 30'

heading "2. --file with a separate data file (A1-15)"
note "--file points at a different data file; it works before or after the command name"
run 'python3 products.py --file store.json list'
run 'python3 products.py --file store.json add --name "Only In Store" --price 2.50 --quantity 7'
run 'python3 products.py list --file store.json'
run 'cat store.json'
note "the default products.json is unaffected"
run 'python3 products.py list'

heading "3. Missing ID (A1-15, A1-12)"
note "checksum of the data file before the failing commands"
run "$SHA products.json"
run 'python3 products.py get 99'
run 'python3 products.py update 99 --price 1'
run 'python3 products.py delete 99 --yes'

heading "4. Invalid values and invocations (A1-15, A1-10, A1-11)"
run 'python3 products.py add --name "" --price 1 --quantity 1'
run 'python3 products.py add --name "Bad Price" --price -5 --quantity 1'
run 'python3 products.py add --name "Bad Price" --price abc --quantity 1'
run 'python3 products.py add --name "Bad Price" --price 1.501 --quantity 1'
run 'python3 products.py update 1 --quantity 2.5'
note "an update with no fields is rejected"
run 'python3 products.py update 1'
run 'python3 products.py get abc'
run 'python3 products.py add --name "Missing flags"'

heading "5. Unconfirmed deletion (A1-15, A1-11)"
run 'python3 products.py delete 1'
note "product 1 is still there"
run 'python3 products.py get 1'

heading "6. None of the failures touched the file (A1-13)"
note "same checksum as in section 3"
run "$SHA products.json"

heading "7. Custom feature: lowstock (required demo)"
note "lowstock --threshold N lists products with quantity <= N, sorted by id"
run 'python3 products.py add --name "Eraser" --price 0.5 --quantity 2'
run 'python3 products.py add --name "Stapler" --price 3.25 --quantity 0'
run 'python3 products.py lowstock --threshold 5'
note "edge case 1: nothing at or below the threshold prints []"
run 'python3 products.py --file store.json lowstock --threshold 5'
note "edge case 2: an invalid threshold is a usage error, not a crash"
run 'python3 products.py lowstock --threshold -1'
run 'python3 products.py lowstock --threshold 2.5'
run 'python3 products.py lowstock --help'

heading "8. Invalid stored data and file errors (A1-12, A1-13)"
run 'printf "{ not json" > broken.json'
run 'python3 products.py --file broken.json list'
run 'python3 products.py --file broken.json add --name X --price 1 --quantity 1'
note "the broken file was not overwritten"
run 'cat broken.json; echo'
run 'python3 products.py --file /no/such/dir/products.json add --name X --price 1 --quantity 1'

heading "Done"
note "Scratch directory: $WORK"
