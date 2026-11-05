#!/usr/bin/env bash
# run_cmd.sh - runs one demo command file, pausing after every command.
#
#   usage: ./run_cmd.sh CMD_FILE
#
#   ./run_cmd.sh demo_cmd.txt                the whole recording, in handout order
#   ./run_cmd.sh command_output_cmd.txt      the handout's success sequence
#   ./run_cmd.sh persistance_id_cmd.txt      persistence and IDs (A1-07 to A1-09)
#   ./run_cmd.sh validation_errors_cmd.txt   validation and errors (A1-10 to A1-13)
#   ./run_cmd.sh custom_feature_cmd.txt      the custom lowstock feature
#
# The commands live in the *_cmd.txt files; see command_output_cmd.txt for the format.
# At each pause, press <space> to continue.
#
# CODING_AGENT_IDENTIFIED_FLAG: developed with a coding agent as the handout
# requires; the flag marks the source throughout.
#
# It copies products.py into a fresh scratch directory and runs there, so the
# repository stays clean and the script can be rerun any number of times.

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$#" -ne 1 ]; then
  echo "usage: $0 CMD_FILE   (e.g. $0 command_output_cmd.txt)" >&2
  exit 2
fi
CMDS="$1"
[ -f "$CMDS" ] && [ -r "$CMDS" ] || { echo "run_cmd.sh: cannot read command file: $CMDS" >&2; exit 1; }
CMDS="$(cd "$(dirname "$CMDS")" && pwd)/$(basename "$CMDS")"
TMP="${TMPDIR:-/tmp}"
WORK="$(mktemp -d "${TMP%/}/products-demo.XXXXXX")"
cp "$REPO/products.py" "$WORK/"
cd "$WORK" || exit 1

# Wait until the space bar is pressed (other keys are ignored). Skipped when
# there is no terminal to read from, so piped or scripted runs never hang.
wait_space() {
  { : </dev/tty; } 2>/dev/null || return 0
  printf '\033[2m(press <space> to continue)\033[0m'
  local key
  while IFS= read -rsn1 key </dev/tty; do
    [ "$key" = " " ] && break
  done
  printf '\r\033[K'
}

heading() { printf '\n\033[1;36m==== %s ====\033[0m\n' "$*"; }
note()    { printf '\033[2m# %s\033[0m\n' "$*"; }
# run COMMAND - show the command, run it, pause.
run() {
  printf '\n\033[1m$ %s\033[0m\n' "$1"
  eval "$1"
  local status=$?
  if [ "$status" -eq 0 ]; then
    printf '\033[32m[exit %d]\033[0m\n' "$status"
  else
    printf '\033[31m[exit %d]\033[0m\n' "$status"
  fi
  # pause after every command; the last command of a stage doubles as the stage break
  wait_space
}

# Read the command file on fd 3 so commands and pauses never consume its lines.
started=0
while IFS= read -r line <&3 || [ -n "$line" ]; do
  case "$line" in
    "== "*) started=1; heading "${line#== }" ;;
    "#"*)   [ "$started" -eq 1 ] && note "$(printf '%s' "${line#\#}" | sed 's/^ //')" ;;
    "")     ;;
    *)      run "$line" ;;
  esac
done 3<"$CMDS"

heading "Done"
note "Scratch directory: $WORK"
