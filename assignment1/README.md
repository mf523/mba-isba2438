# Product Inventory CLI (Assignment 1)

`products.py` is a command-line tool that keeps a product inventory in a local JSON file.
It uses only the Python 3 standard library, never prompts for input, prints JSON on success
and prints a one-line error on failure.

## Requirements

- Python 3.8 or newer. Nothing to install.

## Quick start

Run everything from inside the `assignment1` folder:

```sh
cd assignment1
python3 products.py add --name "Blue Widget" --price 9.99 --quantity 10
python3 products.py list
python3 products.py get 1
python3 products.py update 1 --price 12.50 --quantity 8
python3 products.py lowstock --threshold 5
python3 products.py delete 1 --yes
python3 products.py --help
```

Data lives in `products.json` in the current directory. Use `--file PATH` to pick another file.

## Commands

| Command | Arguments | Prints on success |
|---|---|---|
| `add` | `--name NAME --price PRICE --quantity QTY` (all three required) | the new product |
| `list` | none | every product as a JSON array sorted by id, or `[]` when there are none |
| `get` | `ID` | the product with that id |
| `update` | `ID` plus at least one of `--name`, `--price`, `--quantity` | the product after the change; fields you do not pass are kept as they were |
| `delete` | `ID --yes` | `{"deleted_id": ID}` |
| `lowstock` | `--threshold N` | products with quantity at or below N, sorted by id (see below) |

`--file PATH` can go before or after the command name:

```sh
python3 products.py --file inventory.json list
python3 products.py list --file inventory.json
```

Every command has `--help`.

## Output and exit codes

| Situation | stdout | stderr | exit |
|---|---|---|---|
| success | JSON result | nothing | 0 |
| usage or value error: bad syntax, missing flag, invalid name/price/quantity/threshold, invalid id, empty update, `delete` without `--yes` | nothing | usage line then `Error: ...` | 2 |
| runtime error: id not found, invalid stored data, file cannot be read or written | nothing | `Error: ...` | 1 |

A traceback is never shown. A failed command never changes the data file.

A product is printed like this — `price` is always a string with exactly two decimal places:

```json
{
  "id": 1,
  "name": "Blue Widget",
  "price": "9.99",
  "quantity": 10
}
```

## Validation rules

Values are checked before the data file is opened, so a bad value can never change anything.

| Field | Rule | Rejected examples |
|---|---|---|
| `name` | at least one non-blank character; stored with surrounding whitespace trimmed | `""`, `"   "` |
| `price` | digits with an optional one- or two-digit decimal part, 0 or greater; stored as a string with exactly two decimal places (`4.5` → `"4.50"`) | `-1`, `+1`, `abc`, `$5`, `1e3`, `1.501`, `4.`, `.5` |
| `quantity` | a nonnegative whole number, plain digits only | `-1`, `+1`, `1.5`, `2.0`, `1e3`, `ten` |
| `ID` | a positive integer | `0`, `-1`, `1.5`, `abc`, `1a` |
| `--threshold` | a nonnegative whole number, plain digits only | `-1`, `1.5`, `abc` |

Flag names must be spelled out in full (`--nam` is not accepted as `--name`).

## Custom feature: lowstock

**The problem.** A small store reorders stock before it runs out, but `list` only shows
everything at once and gives no sense of urgency. With more than a handful of products, scrolling the
full list to spot what is running low is slow and error-prone.

**Who it helps.** Whoever reorders: the owner or a clerk opening the shop in the morning who
wants one question answered — *what do I need to restock today?* — without reading the whole
inventory or eyeballing quantities.

**Syntax.**

```sh
python3 products.py [--file PATH] lowstock --threshold N
```

**Inputs.** `--threshold N` is required: a nonnegative whole number (plain digits). A product
is reported when its `quantity` is **at or below** N, so `--threshold 0` finds only
out-of-stock items. The store is never modified; `lowstock` is read-only.

**Expected output.** A JSON array of the matching products (each with `id`, `name`, `price`,
`quantity`), sorted by id, smallest first. `[]` means nothing is at or below the threshold.

**Runnable example.**

```sh
$ python3 products.py add --name "Eraser" --price 0.50 --quantity 2
$ python3 products.py add --name "Stapler" --price 3.25 --quantity 0
$ python3 products.py add --name "Ruler" --price 1.10 --quantity 30
$ python3 products.py lowstock --threshold 5
[
  {
    "id": 1,
    "name": "Eraser",
    "price": "0.50",
    "quantity": 2
  },
  {
    "id": 2,
    "name": "Stapler",
    "price": "3.25",
    "quantity": 0
  }
]
$ python3 products.py --file empty.json lowstock --threshold 5
[]
```

Run `python3 products.py lowstock --help` for the built-in description.

## Data file

```json
{
  "next_id": 4,
  "products": [
    {"id": 1, "name": "Blue Widget", "price": "9.99", "quantity": 10},
    {"id": 2, "name": "Red Gadget", "price": "24.50", "quantity": 3}
  ]
}
```

- UTF-8, pretty-printed, non-ASCII names stored as-is (not escaped).
- `price` is always a string with exactly two decimal places.
- `next_id` is the id the next `add` will use. It only ever goes up.
- Products are kept sorted by id.
- If the file does not exist, reading commands treat it as an empty inventory (`list` and `lowstock` print `[]`, `get` reports the id as not found) and do not create it. The first successful `add` creates it. `update` and `delete` on a missing file report not found and do not create it.
- If the file exists but is not valid UTF-8 JSON in exactly this shape, every command fails with exit 1 and leaves the file alone.

## IDs

- The first product gets id 1, the next gets 2, and so on.
- An id never changes once assigned; `update` keeps it.
- `delete` removes the product but leaves `next_id` unchanged, so a deleted id is never handed out again. Delete id 3 and the next `add` gets id 4.

## Errors never damage the file

All validation and lookups happen before the file is written. The write itself is atomic: the new content goes to a temporary file in the same directory, which is then renamed over the old one. The old bytes are either completely replaced or completely untouched.

## Tests

```sh
python3 -m unittest -v
```

`test_products.py` runs the real CLI as a separate process in a temporary directory for each test, organised by rubric criterion (`A101Add`, `A102List`, ... `A113FailedMutationsLeaveFileUnchanged`) plus a `CustomLowStock` suite for the custom feature. It checks exit codes, that nothing goes to stdout on failure, that no traceback is printed, and that the file bytes are unchanged after every failed mutation.

## Recording the demonstration

```sh
./demo.sh            # runs everything top to bottom
./demo.sh --pause    # waits for Enter after each command, easier to narrate
```

The script copies `products.py` into a scratch directory and runs there, so it is safe to rerun. Each section is labelled with the rubric criterion it covers:

1. Success sequence, matching the handout script exactly: `list` on an empty store, Notebook and Pencil adds, `list`, `get 1`, `update 1 --quantity 12`, `delete 2 --yes`, final `list`, the file contents (`next_id` stays 3), a later invocation reading the saved data, and an `add` that proves the deleted id is not reused.
2. `--file`: a second data file, the flag before and after the command, and the default file left untouched.
3. Missing id on `get`, `update` and `delete`.
4. Invalid values and invocations: empty name, negative and non-numeric price, three-decimal price, decimal quantity, empty update, non-numeric id, missing flags.
5. Unconfirmed deletion: `delete 1` without `--yes` is rejected and product 1 is still there.
6. A checksum showing the file is byte-for-byte unchanged after every failure above.
7. Custom feature: a `lowstock` success, the `[]` no-match edge case, invalid thresholds, and `lowstock --help`.
8. Invalid stored data and a write to a directory that does not exist.

## How the code works

Read this before the recording so the explanation is in your own words.

**Entry point.** `main()` builds the argument parser, parses the command line, works out which data file to use (`--file` or `products.json`), and calls the function registered for the chosen command. Whatever that function returns is printed as JSON. If it raises `ProductError`, the message is printed on stderr and the exit code is 1.

**Parsing and validation.** `build_parser()` defines the six sub-commands with `argparse`. Each `--name`, `--price`, `--quantity`, `ID` and `--threshold` argument has a `type=` function (`parse_name`, `parse_price`, `parse_quantity`, `parse_id`) that either returns the cleaned value or raises an error. argparse turns that error into a usage message and exit code 2. Because this runs during parsing, every value is validated before any file is opened. `parse_price` is the interesting one: a regex accepts only plain digits with an optional one- or two-digit decimal part, then `decimal.Decimal` formats it as the canonical two-decimal string, so `4`, `4.5` and `4.50` all become `"4.50"`. The two checks argparse cannot express, an `update` with no fields and a `delete` without `--yes`, are done at the top of `cmd_update` and `cmd_delete` and also use exit code 2.

**Reading the file.** `load_store(path)` opens the file as UTF-8 and parses it with `json.loads`. A missing file returns an empty store, `{"next_id": 1, "products": []}`, without creating anything. Any other read problem, a JSON syntax error, or a file that is not UTF-8 becomes a `ProductError`. The parsed data then goes through `check_store`, which confirms the exact shape: `next_id` is an integer of 1 or more, `products` is a list, every product has exactly the four fields with the right types (`price` must be a string like `"4.50"`), no id repeats, and every id is below `next_id`.

**Each command.** `cmd_add` takes `next_id` as the new product's id, appends the product, increments `next_id` and saves. `cmd_list` returns the products sorted by id. `cmd_get` uses `find_product`, which scans for the id and raises `ProductError` when it is absent. `cmd_update` collects the flags that were actually given, finds the product, applies only those fields with `dict.update`, and saves. `cmd_delete` finds the product (so a missing id fails before anything changes), filters it out of the list, saves, and returns `{"deleted_id": ID}`. `next_id` is not touched, which is what keeps deleted ids from being reused.

**The custom command.** `cmd_lowstock` loads the store, keeps the products whose `quantity` is at or below the threshold, sorts them by id and returns them; `main()` prints the array as JSON. It reads the file and never writes one, so it cannot damage anything.

**Writing the file.** `save_store(path, data)` sorts the products, serialises the whole store with `json.dumps(indent=2, ensure_ascii=False)`, writes it to a temporary file in the same directory, flushes and fsyncs it, copies the original file's permissions, and finally calls `os.replace` to rename the temporary file over the real one. The rename is atomic, so the file on disk is always either the complete old version or the complete new version. If anything fails along the way the temporary file is removed and the original is untouched.

**Why failed mutations never change the file.** Order of operations in every mutating command: validate arguments (argparse) → load and check the file → find the product → apply the change in memory → write atomically. Every failure happens before the write, and the write cannot half-succeed.

## Design choices where the handout leaves room

The handout pins the contract (exact flag names, exit codes, default path, validation thresholds); a few details are left open. These are the choices made here; each is a one-line change if the assignment handout says otherwise.

| Choice | What this tool does | Where to change it |
|---|---|---|
| exit codes | 0 success, 1 runtime error, 2 usage/value error | `EXIT_ERROR`, `EXIT_USAGE` at the top of `products.py` |
| default data file | `products.json` in the current directory | `DEFAULT_FILE` |
| `--file` position | accepted before or after the command name | the second `--file` argument in `build_parser` |
| price input | leading zeros allowed (`04.5` → `"4.50"`) | `parse_price` |
| quantity rule | 0 is allowed; decimals like `2.0` and signs like `+1` are rejected | `parse_quantity` |
| name rule | blank rejected; stored trimmed | `parse_name` |
| missing data file | reads as empty, created by the first `add` | `load_store`, the `FileNotFoundError` branch |
| output formatting | pretty-printed JSON, two-space indent | the `json.dumps` call in `main()` |
| stored-data strictness | exactly `next_id` and `products` at the top level, exactly four fields per product | `check_store` |
| lowstock threshold | required, inclusive (quantity <= threshold) | `cmd_lowstock` |
