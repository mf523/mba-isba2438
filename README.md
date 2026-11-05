# Product Inventory CLI (Assignment 1)

`products.py` is a command-line tool that keeps a product inventory in a local JSON file.
It uses only the Python 3 standard library, never prompts for input, prints JSON on success
and prints a one-line error on failure.

## Requirements

- Python 3.8 or newer. Nothing to install.

## Quick start

Run everything from the repository root:

```sh
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
| usage or value error: bad syntax, missing flag, invalid name/price/quantity/threshold, invalid id, empty update, `delete` without `--yes`, empty `--file` path | nothing | usage line then `Error: ...` | 2 |
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
- If the file exists but is not valid UTF-8 JSON in exactly this shape, every data command fails with exit 1 and leaves the file alone. `--help` never reads the file, so it still works.

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
