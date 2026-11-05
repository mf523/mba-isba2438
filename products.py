#!/usr/bin/env python3
"""products.py - a product-inventory CLI backed by a local JSON file.

CODING_AGENT_IDENTIFIED_FLAG: this tool was developed with a coding agent,
as the assignment handout requires ("Use a Coding Agent for assessed
development"). The flag marks the source throughout.

Python 3 standard library only. Every command is non-interactive: nothing
ever prompts, so the tool is safe to call from scripts and recordings.

Commands
    add    --name NAME --price PRICE --quantity QTY     create a product
    list                                                every product, sorted by id
    get    ID                                           one product
    update ID [--name NAME] [--price PRICE] [--quantity QTY]
                                                        change only the supplied fields
    delete ID --yes                                     remove a product (needs --yes)
    lowstock --threshold N                              custom feature: products with
                                                        quantity at or below N

Output contract
    success ................ JSON on stdout, exit 0, nothing on stderr
    usage / value error .... "Error: ..." on stderr, exit 2, data file untouched
    runtime error .......... "Error: ..." on stderr, exit 1, data file untouched
                             (missing id, invalid stored data, file problems)
    A traceback is never printed.

Storage
    {"next_id": <int>, "products": [{"id": 1, "name": "...", "price": "9.99",
                                     "quantity": 10}, ...]}
    Prices are stored and printed as strings with exactly two decimal places
    ("9.99"). Default path is ./products.json; --file PATH selects another
    data file. A missing file reads as an empty inventory and is created by
    the first successful add. Writes are atomic (temp file + rename), so a
    failure mid-write can never leave a half-written file.
"""

# CODING_AGENT_IDENTIFIED_FLAG - see the module docstring: coding-agent
# development is required by the handout and flagged throughout the source.

import argparse
import decimal
import json
import os
import re
import shutil
import sys
import tempfile

DEFAULT_FILE = "products.json"

EXIT_OK = 0
EXIT_ERROR = 1   # runtime failure: missing id, invalid stored data, file error
EXIT_USAGE = 2   # bad invocation: syntax, missing flags, invalid values

FIELDS = ("id", "name", "price", "quantity")
EDITABLE_FIELDS = ("name", "price", "quantity")

EXAMPLES = """\
examples:
  python3 products.py add --name "Blue Widget" --price 9.99 --quantity 10
  python3 products.py list
  python3 products.py get 1
  python3 products.py update 1 --price 12.50 --quantity 8
  python3 products.py delete 1 --yes
  python3 products.py lowstock --threshold 5
  python3 products.py --file inventory.json list
"""


class ProductError(Exception):
    """A runtime failure, reported on stderr with EXIT_ERROR."""


# ---------------------------------------------------------------------------
# CODING_AGENT_IDENTIFIED_FLAG
# Validators: value checks for command-line input. These run inside argparse
# (as `type=` functions), so every supplied value is checked before the data
# file is even opened.
# ---------------------------------------------------------------------------

class Validators:
    """Turn raw command-line text into clean values, or raise ArgumentTypeError."""

    @staticmethod
    def name(text):
        """A name must contain at least one non-blank character; it is stored trimmed."""
        name = text.strip()
        if not name:
            raise argparse.ArgumentTypeError("must not be empty")
        return name

    @staticmethod
    def price(text):
        """A price is digits with an optional one- or two-digit decimal part.

        Signs, currency symbols, exponents and extra decimal places are rejected.
        The value is returned as the canonical string with exactly two decimal
        places, so "4", "4.5" and "4.50" all become "4.50".
        """
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", text):
            raise argparse.ArgumentTypeError(
                "must be a decimal amount with at most two decimal places, got %r" % text)
        return format(decimal.Decimal(text), ".2f")

    @staticmethod
    def quantity(text):
        """A quantity is a nonnegative whole number, written as plain digits."""
        if not re.fullmatch(r"[0-9]+", text):
            raise argparse.ArgumentTypeError("must be a whole number of 0 or more, got %r" % text)
        try:
            return int(text)
        except ValueError:            # absurdly long digit strings
            raise argparse.ArgumentTypeError("must be a whole number of 0 or more, got %r" % text)

    @staticmethod
    def product_id(text):
        """A product id is a positive integer."""
        if not re.fullmatch(r"[0-9]+", text):
            raise argparse.ArgumentTypeError("must be a positive integer, got %r" % text)
        try:
            product_id = int(text)
        except ValueError:            # absurdly long digit strings
            raise argparse.ArgumentTypeError("must be a positive integer, got %r" % text)
        if product_id < 1:
            raise argparse.ArgumentTypeError("must be a positive integer, got %r" % text)
        return product_id


# ---------------------------------------------------------------------------
# CODING_AGENT_IDENTIFIED_FLAG
# ProductStore: reading, checking and atomically writing the JSON file.
# ---------------------------------------------------------------------------

class ProductStore:
    """The JSON data file at one path: {"next_id": N, "products": [...]}."""

    def __init__(self, path):
        self.path = path

    @staticmethod
    def empty():
        return {"next_id": 1, "products": []}

    def load(self):
        """Return the parsed store. A missing file counts as an empty store."""
        path = self.path
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except FileNotFoundError:
            return self.empty()
        except UnicodeDecodeError:
            raise ProductError("invalid data in %s: file is not valid UTF-8" % path)
        except OSError as exc:
            raise ProductError("cannot read %s: %s" % (path, exc.strerror or exc))
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ProductError("invalid data in %s: not valid JSON (%s)" % (path, exc))
        self.check(data)
        return data

    @staticmethod
    def _is_int(value):
        return isinstance(value, int) and not isinstance(value, bool)

    @staticmethod
    def _is_price(value):
        """Prices are stored as strings with exactly two decimal places, like "4.50"."""
        return isinstance(value, str) and re.fullmatch(r"[0-9]+\.[0-9]{2}", value) is not None

    def check(self, data):
        """Raise ProductError unless `data` has exactly the next_id/products shape."""
        path = self.path

        def fail(reason):
            raise ProductError("invalid data in %s: %s" % (path, reason))

        if not isinstance(data, dict) or set(data) != {"next_id", "products"}:
            fail("expected an object with exactly the keys next_id and products")
        next_id = data["next_id"]
        if not self._is_int(next_id) or next_id < 1:
            fail("next_id must be an integer of 1 or more")
        if not isinstance(data["products"], list):
            fail("products must be a list")
        seen = set()
        for item in data["products"]:
            if not isinstance(item, dict) or set(item) != set(FIELDS):
                fail("each product needs exactly the fields %s" % ", ".join(FIELDS))
            if not self._is_int(item["id"]) or item["id"] < 1:
                fail("product id must be a positive integer")
            if item["id"] in seen:
                fail("duplicate product id %d" % item["id"])
            if item["id"] >= next_id:
                fail("product id %d is not below next_id %d" % (item["id"], next_id))
            if not isinstance(item["name"], str) or not item["name"].strip():
                fail("product %d has an empty name" % item["id"])
            if not self._is_price(item["price"]):
                fail("product %d has an invalid price (expected a string like \"4.50\")" % item["id"])
            if not self._is_int(item["quantity"]) or item["quantity"] < 0:
                fail("product %d has an invalid quantity" % item["id"])
            seen.add(item["id"])

    def save(self, data):
        """Write the store atomically: temp file in the same directory, then rename.

        Either the rename succeeds and the file is completely replaced, or it
        fails and the previous bytes are still there untouched.
        """
        path = self.path
        data["products"].sort(key=lambda item: item["id"])
        payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        directory = os.path.dirname(os.path.abspath(path))
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(prefix=".products-", suffix=".tmp", dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if os.path.exists(path):
                shutil.copymode(path, temp_path)
            else:
                os.chmod(temp_path, 0o644)
            os.replace(temp_path, path)
            temp_path = None
        except OSError as exc:
            raise ProductError("cannot write %s: %s" % (path, exc.strerror or exc))
        finally:
            if temp_path is not None:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# CODING_AGENT_IDENTIFIED_FLAG
# Inventory: the commands. Each method receives the parsed args and returns
# the JSON-serialisable value to print.
# ---------------------------------------------------------------------------

class Inventory:
    """The six commands, working on one ProductStore."""

    def __init__(self, store):
        self.store = store

    @staticmethod
    def find(data, product_id):
        for item in data["products"]:
            if item["id"] == product_id:
                return item
        raise ProductError("product with id %d not found" % product_id)

    def add(self, args):
        data = self.store.load()
        product = {
            "id": data["next_id"],
            "name": args.name,
            "price": args.price,
            "quantity": args.quantity,
        }
        data["products"].append(product)
        data["next_id"] += 1          # ids only ever move forward
        self.store.save(data)
        return product

    def list(self, args):
        data = self.store.load()
        return sorted(data["products"], key=lambda item: item["id"])

    def get(self, args):
        data = self.store.load()
        return self.find(data, args.id)

    def update(self, args):
        changes = {}
        for field in EDITABLE_FIELDS:
            value = getattr(args, field)
            if value is not None:
                changes[field] = value
        if not changes:
            args.parser.error("update needs at least one of --name, --price, --quantity")
        data = self.store.load()
        product = self.find(data, args.id)
        product.update(changes)       # unspecified fields are left as they were
        self.store.save(data)
        return product

    def delete(self, args):
        if not args.yes:
            args.parser.error("delete needs --yes to confirm removing product %d" % args.id)
        data = self.store.load()
        self.find(data, args.id)      # raises ProductError when the id is missing
        data["products"] = [item for item in data["products"] if item["id"] != args.id]
        self.store.save(data)         # next_id is deliberately not changed
        return {"deleted_id": args.id}

    def lowstock(self, args):
        """Custom feature: report every product that is running low.

        A product is low when its quantity is at or below --threshold. The report
        is a JSON array sorted by id; [] means nothing needs reordering.
        """
        data = self.store.load()
        return sorted(
            (item for item in data["products"] if item["quantity"] <= args.threshold),
            key=lambda item: item["id"],
        )


# ---------------------------------------------------------------------------
# CODING_AGENT_IDENTIFIED_FLAG
# Command-line interface: Parser (argparse with our error format) and
# ProductsCLI (builds the parser, dispatches to Inventory, prints the result).
# ---------------------------------------------------------------------------

class Parser(argparse.ArgumentParser):
    """ArgumentParser whose usage errors print "Error: ..." and use EXIT_USAGE."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, "Error: %s\n" % message)


class ProductsCLI:
    """Parse the command line, run one Inventory command, print JSON, return an exit code."""

    def build_parser(self):
        parser = Parser(
            prog="products.py",
            description="Manage a product inventory stored in a local JSON file.",
            epilog=EXAMPLES,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            allow_abbrev=False,
        )
        parser.add_argument(
            "--file", metavar="PATH", default=None,
            help="JSON data file to use (default: %s in the current directory)" % DEFAULT_FILE,
        )
        subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", title="commands")
        subparsers.required = True

        def command(name, help_text):
            sub = subparsers.add_parser(name, help=help_text, description=help_text,
                                        allow_abbrev=False)
            # Accept --file after the command name too. SUPPRESS keeps the
            # subparser from overwriting a --file given before the command.
            sub.add_argument("--file", metavar="PATH", default=argparse.SUPPRESS,
                             help="JSON data file to use (may also be given before the command)")
            # the subcommand name doubles as the Inventory method that runs it
            sub.set_defaults(parser=sub)
            return sub

        add = command("add", "Create a product and print it.")
        add.add_argument("--name", required=True, type=Validators.name, help="product name (non-empty)")
        add.add_argument("--price", required=True, type=Validators.price,
                         help="price, a decimal amount with at most two decimal places")
        add.add_argument("--quantity", required=True, type=Validators.quantity,
                         help="quantity, a whole number 0 or greater")

        command("list", "Print every product sorted by id, or [] when there are none.")

        get = command("get", "Print the product with the given id.")
        get.add_argument("id", type=Validators.product_id, help="product id (positive integer)")

        update = command("update", "Change the supplied fields of a product and print the result.")
        update.add_argument("id", type=Validators.product_id, help="product id (positive integer)")
        update.add_argument("--name", type=Validators.name, help="new name (non-empty)")
        update.add_argument("--price", type=Validators.price,
                            help="new price, a decimal amount with at most two decimal places")
        update.add_argument("--quantity", type=Validators.quantity,
                            help="new quantity, a whole number 0 or greater")

        delete = command("delete", "Remove a product. Requires --yes to confirm.")
        delete.add_argument("id", type=Validators.product_id, help="product id (positive integer)")
        delete.add_argument("--yes", action="store_true", help="confirm the deletion (required)")

        lowstock = command("lowstock",
                           "Custom feature: print products whose quantity is at or "
                           "below the threshold, sorted by id. [] means nothing needs reordering.")
        lowstock.add_argument("--threshold", required=True, type=Validators.quantity,
                              help="report products with quantity <= THRESHOLD (whole number 0 or more)")

        return parser

    def run(self, argv=None):
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8")   # keep non-ASCII names printable everywhere
            except (AttributeError, ValueError):
                pass

        parser = self.build_parser()
        args = parser.parse_args(argv)
        if args.file == "":
            parser.error("--file needs a path")
        path = args.file if args.file is not None else DEFAULT_FILE

        try:
            inventory = Inventory(ProductStore(path))
            result = getattr(inventory, args.command)(args)
        except ProductError as exc:
            print("Error: %s" % exc, file=sys.stderr)
            return EXIT_ERROR
        except Exception as exc:  # safety net: never show a traceback
            print("Error: unexpected %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
            return EXIT_ERROR

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return EXIT_OK


def main(argv=None):
    return ProductsCLI().run(argv)


if __name__ == "__main__":
    sys.exit(main())
