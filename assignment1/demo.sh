#!/usr/bin/env bash
# demo.sh - walks through everything the recorded demonstration must show.
#
#   ./demo.sh            run the whole walkthrough top to bottom
#   ./demo.sh --pause    wait for Enter after each command (handy while recording)
#
# It copies products.py into a fresh scratch directory and runs there, so the
# repository stays clean and the script can be rerun any number of times.
# Sections are labelled with the rubric criteria they demonstrate.

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/products-demo.XXXXXX")"
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

heading "1. Success sequence (A1-14)"
note "list with no data file at all prints an empty array"
run 'python3 products.py list'
run 'python3 products.py add --name "Blue Widget" --price 9.99 --quantity 10'
run 'python3 products.py add --name "Red Gadget" --price 24.50 --quantity 3'
run 'python3 products.py add --name "Green Gizmo" --price 4.25 --quantity 100'
run 'python3 products.py list'
run 'python3 products.py get 2'
note "update only the supplied fields: the name is preserved"
run 'python3 products.py update 2 --price 19.99 --quantity 5'
note "and here price and quantity are preserved"
run 'python3 products.py update 1 --name "Blue Widget Pro"'
run 'python3 products.py delete 3 --yes'
run 'python3 products.py list'
note "next_id stays at 4 after deleting id 3, so the next add gets id 4 and 3 is never reused"
run 'cat products.json'
run 'python3 products.py add --name "Yellow Thing" --price 1 --quantity 1'

heading "1b. Final data (A1-14)"
run 'python3 products.py list'
run 'cat products.json'

heading "2. Persistence (A1-15)"
note "Every command above ran as its own process. A brand-new invocation still sees the data:"
run 'ls -l products.json'
run 'python3 products.py get 1'

heading "3. --file (A1-15)"
note "--file points at a different data file; it works before or after the command name"
run 'python3 products.py --file store.json list'
run 'python3 products.py --file store.json add --name "Only In Store" --price 2.50 --quantity 7'
run 'python3 products.py list --file store.json'
run 'cat store.json'
note "the default products.json is unaffected"
run 'python3 products.py list'

heading "4. Missing ID (A1-15, A1-12)"
note "checksum of the data file before the failing commands"
run "$SHA products.json"
run 'python3 products.py get 99'
run 'python3 products.py update 99 --price 1'
run 'python3 products.py delete 99 --yes'

heading "5. Invalid values and invocations (A1-15, A1-10, A1-11)"
run 'python3 products.py add --name "" --price 1 --quantity 1'
run 'python3 products.py add --name "Bad Price" --price -5 --quantity 1'
run 'python3 products.py add --name "Bad Price" --price abc --quantity 1'
run 'python3 products.py update 1 --quantity 2.5'
note "an update with no fields is rejected"
run 'python3 products.py update 1'
run 'python3 products.py get abc'
run 'python3 products.py add --name "Missing flags"'

heading "6. Unconfirmed deletion (A1-15, A1-11)"
run 'python3 products.py delete 1'
note "product 1 is still there"
run 'python3 products.py get 1'

heading "7. None of the failures touched the file (A1-13)"
note "same checksum as in section 4"
run "$SHA products.json"

heading "8. Invalid stored data and file errors (A1-12, A1-13)"
run 'printf "{ not json" > broken.json'
run 'python3 products.py --file broken.json list'
run 'python3 products.py --file broken.json add --name X --price 1 --quantity 1'
note "the broken file was not overwritten"
run 'cat broken.json; echo'
run 'python3 products.py --file /no/such/dir/products.json add --name X --price 1 --quantity 1'

heading "Done"
note "Scratch directory: $WORK"
