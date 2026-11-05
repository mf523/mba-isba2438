# Design

How `products.py` is built: the code walkthrough, a reference of every class, method and constant, and the design choices. For using the tool see [README.md](README.md).

## How the code works

Read this before the recording so the explanation is in your own words.

**Structure.** The code is organised into five classes, each with one job:

| Class | Job |
|---|---|
| `Validators` | static methods that check and clean command-line values (`name`, `price`, `quantity`, `product_id`) |
| `ProductStore` | the JSON file at one path: `load`, `check`, `save` |
| `Inventory` | the six commands as methods (`add`, `list`, `get`, `update`, `delete`, `lowstock`), working on a `ProductStore` |
| `Parser` | an `argparse.ArgumentParser` whose usage errors print `Error: ...` and exit 2 |
| `ProductsCLI` | builds the parser, runs one command, prints the JSON result and returns the exit code |

`ProductError` is the exception for runtime failures, and `main()` simply calls `ProductsCLI().run()`.

**Entry point.** `main()` calls `ProductsCLI().run()`, and its return value becomes the exit code. `run()` first switches stdout and stderr to UTF-8 so non-ASCII names print everywhere. It then builds the argument parser, parses the command line, rejects an empty `--file ""` path (exit 2), works out which data file to use (`--file` or `products.json`), creates an `Inventory` on a `ProductStore` for that path, and calls the `Inventory` method named after the chosen command. Whatever that method returns is printed as JSON with exit 0. If it raises `ProductError`, the message is printed on stderr and the exit code is 1. Any other unexpected exception is also caught and reported as `Error: unexpected ...` with exit 1, so a traceback is never shown.

**Parsing and validation.** `ProductsCLI.build_parser()` defines the six sub-commands with `argparse`. Each `--name`, `--price`, `--quantity`, `ID` and `--threshold` argument has a `type=` function (`Validators.name`, `Validators.price`, `Validators.quantity`, `Validators.product_id`) that either returns the cleaned value or raises an error. argparse turns that error into a usage message and exit code 2. Because this runs during parsing, every value is validated before any file is opened. `Validators.price` is the interesting one: a regex accepts only plain digits with an optional one- or two-digit decimal part, then `decimal.Decimal` formats it as the canonical two-decimal string, so `4`, `4.5` and `4.50` all become `"4.50"`. The two checks argparse cannot express, an `update` with no fields and a `delete` without `--yes`, are done at the top of `Inventory.update` and `Inventory.delete` and also use exit code 2.

**Reading the file.** `ProductStore.load()` opens the file as UTF-8 and parses it with `json.loads`. A missing file returns an empty store, `{"next_id": 1, "products": []}`, without creating anything. Any other read problem, a JSON syntax error, or a file that is not UTF-8 becomes a `ProductError`. The parsed data then goes through `ProductStore.check`, which confirms the exact shape: `next_id` is an integer of 1 or more, `products` is a list, every product has exactly the four fields with the right types (`price` must be a string like `"4.50"`), no id repeats, and every id is below `next_id`.

**Each command.** `Inventory.add` takes `next_id` as the new product's id, appends the product, increments `next_id` and saves. `Inventory.list` returns the products sorted by id. `Inventory.get` uses `Inventory.find`, which scans for the id and raises `ProductError` when it is absent. `Inventory.update` collects the flags that were actually given, finds the product, applies only those fields with `dict.update`, and saves. `Inventory.delete` finds the product (so a missing id fails before anything changes), filters it out of the list, saves, and returns `{"deleted_id": ID}`. `next_id` is not touched, which is what keeps deleted ids from being reused.

**The custom command.** `Inventory.lowstock` loads the store, keeps the products whose `quantity` is at or below the threshold, sorts them by id and returns them; `ProductsCLI.run()` prints the array as JSON. It reads the file and never writes one, so it cannot damage anything.

**Writing the file.** `ProductStore.save(data)` sorts the products, serialises the whole store with `json.dumps(indent=2, ensure_ascii=False)`, writes it to a temporary file in the same directory, flushes and fsyncs it, copies the original file's permissions, and finally calls `os.replace` to rename the temporary file over the real one. The rename is atomic, so the file on disk is always either the complete old version or the complete new version. If anything fails along the way the temporary file is removed and the original is untouched.

**Why failed mutations never change the file.** Order of operations in every mutating command: validate arguments (argparse) → load and check the file → find the product (`update` and `delete`) → apply the change in memory → write atomically. Every failure happens before the write, and the write cannot half-succeed.

### Reference: every class, method and constant

**Constants** (top of the file)

| Name | Value / purpose |
|---|---|
| `DEFAULT_FILE` | `"products.json"`, used when `--file` is not given |
| `EXIT_OK`, `EXIT_ERROR`, `EXIT_USAGE` | exit codes 0, 1 and 2 |
| `FIELDS` | the four product fields `id`, `name`, `price`, `quantity`; `ProductStore.check` requires exactly these |
| `EDITABLE_FIELDS` | `name`, `price`, `quantity`, the fields `update` may change |
| `EXAMPLES` | the examples printed at the end of `--help` |

**`ProductError(Exception)`** — raised for runtime failures (missing id, invalid stored data, file read/write errors); `ProductsCLI.run` turns it into `Error: ...` on stderr and exit 1.

**`Validators`** — all static methods, used as argparse `type=` functions; each returns the cleaned value or raises `argparse.ArgumentTypeError` (exit 2).

| Method | Accepts | Returns |
|---|---|---|
| `name(text)` | at least one non-blank character | the name, trimmed |
| `price(text)` | digits with an optional one- or two-digit decimal part | the price as a two-decimal string, e.g. `"4.50"` |
| `quantity(text)` | plain digits (also used for `--threshold`) | an `int` of 0 or more |
| `product_id(text)` | plain digits, value 1 or more | an `int` id |

**`ProductStore(path)`** — the JSON data file at one path.

| Method | What it does |
|---|---|
| `__init__(path)` | remembers the file path |
| `empty()` | static; returns a new empty store `{"next_id": 1, "products": []}` |
| `load()` | reads and parses the file as UTF-8 JSON, runs `check`, returns the data; a missing file returns `empty()`; read, decode and JSON errors raise `ProductError` |
| `check(data)` | verifies the exact `next_id`/`products` shape and every product's fields, raising `ProductError` with the reason; uses a small inner `fail(reason)` helper to build the message |
| `save(data)` | sorts the products by id and writes the store atomically (temp file, fsync, copy permissions, `os.replace`); OS errors raise `ProductError` and the temp file is removed |
| `_is_int(value)` | static helper; true for an `int` that is not a `bool` |
| `_is_price(value)` | static helper; true for a string like `"4.50"` (digits, a point, exactly two digits) |

**`Inventory(store)`** — the commands; each takes the parsed `args` and returns the value to print.

| Method | What it does |
|---|---|
| `__init__(store)` | keeps the `ProductStore` to work on |
| `find(data, product_id)` | static; returns the product with that id or raises `ProductError("product with id N not found")` |
| `add(args)` | creates a product with id `next_id`, increments `next_id`, saves, returns the product |
| `list(args)` | returns all products sorted by id |
| `get(args)` | returns `find(data, args.id)` |
| `update(args)` | rejects an update with no fields (exit 2), finds the product, changes only the supplied fields, saves, returns the product |
| `delete(args)` | rejects a missing `--yes` (exit 2), finds the product, removes it, saves, returns `{"deleted_id": ID}`; `next_id` is unchanged |
| `lowstock(args)` | custom feature; returns products with `quantity <= args.threshold`, sorted by id; never writes |

**`Parser(argparse.ArgumentParser)`**

| Method | What it does |
|---|---|
| `error(message)` | overrides argparse's default: prints the usage line, then `Error: message` on stderr, and exits with `EXIT_USAGE` (2) |

**`ProductsCLI`**

| Method | What it does |
|---|---|
| `build_parser()` | builds the `Parser` with the global `--file` option and the six sub-commands and their arguments; an inner `command(name, help_text)` helper creates each sub-command, adds the second `--file` option that may follow the command name, and records the sub-parser so `update` and `delete` can report usage errors |
| `run(argv=None)` | the whole program: parse, choose the data file, call the `Inventory` method named after the command, print the JSON result, return the exit code (see **Entry point** above) |

**`main(argv=None)`** — returns `ProductsCLI().run(argv)`; the `if __name__ == "__main__"` block passes that to `sys.exit`.

## Design choices where the handout leaves room

The handout pins the contract (exact flag names, exit codes, default path, validation thresholds); a few details are left open. These are the choices made here; each is a one-line change if the assignment handout says otherwise.

| Choice | What this tool does | Where to change it |
|---|---|---|
| exit codes | 0 success, 1 runtime error, 2 usage/value error | `EXIT_ERROR`, `EXIT_USAGE` at the top of `products.py` |
| default data file | `products.json` in the current directory | `DEFAULT_FILE` |
| `--file` position | accepted before or after the command name | the second `--file` argument in `ProductsCLI.build_parser` |
| price input | leading zeros allowed (`04.5` → `"4.50"`) | `Validators.price` |
| quantity rule | 0 is allowed; decimals like `2.0` and signs like `+1` are rejected | `Validators.quantity` |
| name rule | blank rejected; stored trimmed | `Validators.name` |
| missing data file | reads as empty, created by the first `add` | `ProductStore.load`, the `FileNotFoundError` branch |
| output formatting | pretty-printed JSON, two-space indent | the `json.dumps` call in `ProductsCLI.run()` |
| stored-data strictness | exactly `next_id` and `products` at the top level, exactly four fields per product | `ProductStore.check` |
| lowstock threshold | required, inclusive (quantity <= threshold) | `Inventory.lowstock` |
