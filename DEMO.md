# Recording the demonstration

How to run the recorded demonstration of `products.py`. For the tool itself see [README.md](README.md).

```sh
./run_cmd.sh demo_cmd.txt                # the whole recording, in handout order
./run_cmd.sh command_output_cmd.txt      # the handout's success sequence
./run_cmd.sh persistance_id_cmd.txt      # persistence and IDs (A1-07 to A1-09)
./run_cmd.sh validation_errors_cmd.txt   # validation and errors (A1-10 to A1-13)
./run_cmd.sh custom_feature_cmd.txt      # the custom lowstock feature
```

`run_cmd.sh` takes exactly one command file, reads it line by line and pauses after every command; press <space> to continue. Each run copies `products.py` into a fresh scratch directory and runs there, so it is safe to rerun. In a command file, `== ` starts a stage heading, `# ` is a note shown on screen, blank lines are ignored and every other line is a command. Rubric ids are written at the end of the note above the commands they label, for example `# get returns product 1   [A1-03, A1-14]`, so the recording names the criterion each step demonstrates.

**`demo_cmd.txt` — the whole recording in one run.** Follows the handout's "Demonstration and Submission" list in order: start with no `products.json`, the eight-command success sequence, the saved file and a later invocation, a missing id / invalid value / delete without `--yes` with checksums proving the file is unchanged, `--file` with a separate data file, the code walkthrough (with `SAY:` prompts for what to explain), and `lowstock` with a successful use and the `[]` edge case. The other four files below go deeper into each rubric group.

**`command_output_cmd.txt` — the handout's success sequence.** Starting with no `products.json`, it runs the handout's eight commands in order: `--help`, the Notebook and Pencil adds (ids 1 and 2), `list`, `get 1`, `update 1 --quantity 12`, `delete 2 --yes`, and the final `list`. It then shows the saved file (only Notebook, `"4.50"`, quantity 12, `next_id` 3) and a later invocation reading the saved data.

**`persistance_id_cmd.txt` — persistence and IDs (A1-07 to A1-09).** A missing data file lists as `[]` and is not created; adds in separate processes are saved and read back; the file has the `next_id`/`products` shape; deleting id 2 leaves `next_id` at 3, so the next add gets id 3; `--file` works before or after the command and leaves `products.json` untouched.

**`validation_errors_cmd.txt` — validation and errors (A1-10 to A1-13).** Invalid names, prices and quantities on `add` and `update`; invalid ids, unknown commands and flags, extra arguments, missing flags, an empty update and `delete` without `--yes`; missing ids on `get`, `update` and `delete`; a checksum showing the file is byte-for-byte unchanged after every failure; malformed, empty and schema-breaking data files, and a write to a directory that does not exist.

**`custom_feature_cmd.txt` — the custom `lowstock` feature.** `lowstock --help`, a successful report, the `[]` no-match edge case, invalid thresholds, and the core commands still working.

Together, `persistance_id_cmd.txt` and `validation_errors_cmd.txt` cover the A1-15 checks: persistence, `--file`, missing id, invalid value and unconfirmed deletion.
