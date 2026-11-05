#!/usr/bin/env python3
"""End-to-end tests for products.py, organised by rubric criterion (A1-01 .. A1-13),
plus tests for the custom lowstock feature.

CODING_AGENT_IDENTIFIED_FLAG: developed with a coding agent as the handout
requires; the flag marks the source throughout.

Every test runs the real CLI in a fresh temporary directory as a separate
process, so exit codes, stdout/stderr separation, tracebacks and the bytes
left on disk are all checked exactly as a grader would see them.

Run:  python3 -m unittest -v
"""

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.py")
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


class CliTestCase(unittest.TestCase):
    """Helpers shared by every test class."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name
        self.path = os.path.join(self.cwd, "products.json")

    # -- running the CLI ---------------------------------------------------

    def raw(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args],
            cwd=self.cwd, capture_output=True, text=True, encoding="utf-8",
        )

    def ok(self, *args):
        """Run expecting success; return the parsed JSON from stdout."""
        proc = self.raw(*args)
        self.assertEqual(proc.returncode, 0, self._describe(args, proc))
        self.assertEqual(proc.stderr, "", self._describe(args, proc))
        return json.loads(proc.stdout)

    def fails(self, expected_code, *args):
        """Run expecting failure; assert the reporting rules; return stderr."""
        proc = self.raw(*args)
        self.assertEqual(proc.returncode, expected_code, self._describe(args, proc))
        self.assertEqual(proc.stdout, "", "success output printed on failure: " + self._describe(args, proc))
        self.assertNotIn("Traceback", proc.stderr, self._describe(args, proc))
        self.assertIn("Error:", proc.stderr, self._describe(args, proc))
        return proc.stderr

    @staticmethod
    def _describe(args, proc):
        return "\nargs=%r\nexit=%r\nstdout=%r\nstderr=%r" % (args, proc.returncode, proc.stdout, proc.stderr)

    # -- the data file -----------------------------------------------------

    def file_bytes(self, path=None):
        with open(path or self.path, "rb") as handle:
            return handle.read()

    def file_json(self, path=None):
        return json.loads(self.file_bytes(path).decode("utf-8"))

    def write_file(self, content, path=None):
        if not isinstance(content, (bytes, str)):
            content = json.dumps(content)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(path or self.path, mode) as handle:
            handle.write(content)

    def digest(self, path=None):
        return hashlib.sha256(self.file_bytes(path)).hexdigest()

    def seed(self, count=3):
        """Add `count` products named P1..Pn with alternating decimal/whole prices."""
        return [self.ok("add", "--name", "P%d" % n, "--price", "%d.5" % n if n % 2 else "%d" % (n * 2),
                        "--quantity", str(n))
                for n in range(1, count + 1)]


# ---------------------------------------------------------------------------
# Commands and output contract
# ---------------------------------------------------------------------------

class A101Add(CliTestCase):
    def test_add_creates_and_prints_product(self):
        result = self.ok("add", "--name", "Blue Widget", "--price", "9.99", "--quantity", "10")
        self.assertEqual(result, {"id": 1, "name": "Blue Widget", "price": "9.99", "quantity": 10})
        self.assertEqual(self.file_json()["products"], [result])

    def test_add_output_field_order(self):
        proc = self.raw("add", "--name", "X", "--price", "1", "--quantity", "2")
        self.assertEqual(list(json.loads(proc.stdout)), ["id", "name", "price", "quantity"])

    def test_add_accepts_zero_price_and_zero_quantity(self):
        result = self.ok("add", "--name", "Free", "--price", "0", "--quantity", "0")
        self.assertEqual((result["price"], result["quantity"]), ("0.00", 0))

    def test_price_is_canonicalised_to_two_decimal_places(self):
        self.assertEqual(self.ok("add", "--name", "A", "--price", "4.5", "--quantity", "1")["price"], "4.50")
        self.assertEqual(self.ok("add", "--name", "B", "--price", "4", "--quantity", "1")["price"], "4.00")
        self.assertEqual(self.ok("add", "--name", "C", "--price", "4.50", "--quantity", "1")["price"], "4.50")
        self.assertEqual(self.ok("add", "--name", "D", "--price", "0", "--quantity", "1")["price"], "0.00")


class A102List(CliTestCase):
    def test_list_prints_empty_array_when_no_file(self):
        self.assertEqual(self.ok("list"), [])
        self.assertFalse(os.path.exists(self.path), "list must not create the file")

    def test_list_prints_empty_array_when_no_products(self):
        self.write_file({"next_id": 5, "products": []})
        self.assertEqual(self.ok("list"), [])

    def test_list_returns_every_product(self):
        added = self.seed(3)
        self.assertEqual(self.ok("list"), added)

    def test_list_sorts_by_numeric_id(self):
        products = [
            {"id": 10, "name": "ten", "price": "1.00", "quantity": 1},
            {"id": 2, "name": "two", "price": "1.00", "quantity": 1},
            {"id": 9, "name": "nine", "price": "1.00", "quantity": 1},
        ]
        self.write_file({"next_id": 11, "products": products})
        self.assertEqual([p["id"] for p in self.ok("list")], [2, 9, 10])


class A103Get(CliTestCase):
    def test_get_returns_matching_product(self):
        added = self.seed(3)
        for product in added:
            self.assertEqual(self.ok("get", str(product["id"])), product)

    def test_get_selects_by_id_not_position(self):
        self.seed(3)
        self.ok("delete", "1", "--yes")
        self.assertEqual(self.ok("get", "2")["name"], "P2")
        self.assertEqual(self.ok("get", "3")["name"], "P3")


class A104Update(CliTestCase):
    def test_update_one_field_preserves_the_rest(self):
        self.seed(2)
        result = self.ok("update", "2", "--price", "19.99")
        self.assertEqual(result, {"id": 2, "name": "P2", "price": "19.99", "quantity": 2})
        self.assertEqual(self.ok("get", "2"), result)
        self.assertEqual(self.ok("get", "1")["name"], "P1", "other products untouched")

    def test_update_every_field(self):
        self.seed(1)
        result = self.ok("update", "1", "--name", "Renamed", "--quantity", "0", "--price", "0")
        self.assertEqual(result, {"id": 1, "name": "Renamed", "price": "0.00", "quantity": 0})
        self.assertEqual(self.file_json()["products"], [result])

    def test_update_two_fields(self):
        self.seed(1)
        result = self.ok("update", "1", "--name", "New", "--quantity", "42")
        self.assertEqual(result["price"], "1.50")
        self.assertEqual(result, {"id": 1, "name": "New", "price": "1.50", "quantity": 42})

    def test_update_keeps_id_and_next_id(self):
        self.seed(2)
        self.ok("update", "1", "--name", "Changed")
        data = self.file_json()
        self.assertEqual(data["next_id"], 3)
        self.assertEqual([p["id"] for p in data["products"]], [1, 2])


class A105Delete(CliTestCase):
    def test_delete_removes_only_selected_and_returns_deleted_id(self):
        self.seed(3)
        self.assertEqual(self.ok("delete", "2", "--yes"), {"deleted_id": 2})
        self.assertEqual([p["id"] for p in self.ok("list")], [1, 3])
        self.assertEqual([p["id"] for p in self.file_json()["products"]], [1, 3])

    def test_delete_yes_before_id_also_works(self):
        self.seed(1)
        self.assertEqual(self.ok("delete", "--yes", "1"), {"deleted_id": 1})
        self.assertEqual(self.ok("list"), [])


class A106Interface(CliTestCase):
    def test_help_for_every_command_exits_zero(self):
        for args in (["--help"], ["-h"], ["add", "--help"], ["list", "--help"],
                     ["get", "--help"], ["update", "--help"], ["delete", "--help"],
                     ["lowstock", "--help"]):
            proc = self.raw(*args)
            self.assertEqual(proc.returncode, 0, args)
            self.assertIn("usage:", proc.stdout, args)
            self.assertEqual(proc.stderr, "", args)
        self.assertFalse(os.path.exists(self.path), "help must not read or create the data file")

    def test_top_level_help_lists_commands_and_file_flag(self):
        text = self.raw("--help").stdout
        for word in ("add", "list", "get", "update", "delete", "lowstock",
                     "--file", "--threshold"):
            self.assertIn(word, text)

    def test_no_command_is_a_usage_error(self):
        self.fails(2)

    def test_unknown_command_is_a_usage_error(self):
        self.fails(2, "remove", "1")

    def test_success_output_is_json_only_on_stdout(self):
        proc = self.raw("add", "--name", "X", "--price", "1", "--quantity", "1")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        json.loads(proc.stdout)            # the whole of stdout is one JSON document

    def test_non_interactive_with_closed_stdin(self):
        proc = subprocess.run([sys.executable, SCRIPT, "delete", "1", "--yes"], cwd=self.cwd,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)  # not found, but it never waited for input
        self.assertNotIn("Traceback", proc.stderr)

    def test_stdlib_only(self):
        with open(SCRIPT, encoding="utf-8") as handle:
            source = handle.read()
        stdlib = {"argparse", "decimal", "json", "os", "re", "shutil", "sys", "tempfile"}
        for line in source.splitlines():
            if line.startswith(("import ", "from ")):
                module = line.split()[1].split(".")[0]
                self.assertIn(module, stdlib, line)


# ---------------------------------------------------------------------------
# Persistence and IDs
# ---------------------------------------------------------------------------

class A107FileFormat(CliTestCase):
    def test_file_shape_and_field_types(self):
        self.ok("add", "--name", "Widget", "--price", "10", "--quantity", "3")
        data = self.file_json()
        self.assertEqual(set(data), {"next_id", "products"})
        self.assertEqual(data["next_id"], 2)
        product = data["products"][0]
        self.assertEqual(list(product), ["id", "name", "price", "quantity"])
        self.assertIsInstance(product["id"], int)
        self.assertIsInstance(product["name"], str)
        self.assertIsInstance(product["price"], str)
        self.assertEqual(product["price"], "10.00")
        self.assertIsInstance(product["quantity"], int)
        self.assertEqual(product, {"id": 1, "name": "Widget", "price": "10.00", "quantity": 3})

    def test_file_is_utf8_and_round_trips_unicode(self):
        name = "Café ☕ – naïve"
        result = self.ok("add", "--name", name, "--price", "1", "--quantity", "1")
        self.assertEqual(result["name"], name)
        raw = self.file_bytes()
        raw.decode("utf-8")                                   # valid UTF-8
        self.assertIn(name.encode("utf-8"), raw)              # stored as real UTF-8, not escapes
        self.assertEqual(self.ok("get", "1")["name"], name)

    def test_empty_inventory_file_after_deleting_everything(self):
        self.seed(1)
        self.ok("delete", "1", "--yes")
        self.assertEqual(self.file_json(), {"next_id": 2, "products": []})


class A108Ids(CliTestCase):
    def test_ids_start_at_one_and_increase(self):
        self.assertEqual([p["id"] for p in self.seed(3)], [1, 2, 3])

    def test_ids_are_stable_across_updates(self):
        self.seed(2)
        self.ok("update", "1", "--name", "Changed")
        self.assertEqual([p["id"] for p in self.ok("list")], [1, 2])

    def test_deleted_ids_are_never_reused(self):
        self.seed(3)
        self.ok("delete", "3", "--yes")                       # delete the highest id
        self.assertEqual(self.file_json()["next_id"], 4)
        self.assertEqual(self.ok("add", "--name", "P4", "--price", "1", "--quantity", "1")["id"], 4)
        self.ok("delete", "2", "--yes")                       # delete a middle id
        self.assertEqual(self.ok("add", "--name", "P5", "--price", "1", "--quantity", "1")["id"], 5)
        self.assertEqual([p["id"] for p in self.ok("list")], [1, 4, 5])

    def test_ids_never_repeat_even_after_deleting_everything(self):
        self.seed(2)
        self.ok("delete", "1", "--yes")
        self.ok("delete", "2", "--yes")
        self.assertEqual(self.ok("list"), [])
        self.assertEqual(self.ok("add", "--name", "P3", "--price", "1", "--quantity", "1")["id"], 3)

    def test_next_id_in_file_is_respected(self):
        self.write_file({"next_id": 100, "products": []})
        self.assertEqual(self.ok("add", "--name", "X", "--price", "1", "--quantity", "1")["id"], 100)


class A109Persistence(CliTestCase):
    def test_persists_across_separate_invocations(self):
        self.ok("add", "--name", "A", "--price", "1", "--quantity", "1")
        self.ok("add", "--name", "B", "--price", "2", "--quantity", "2")
        self.ok("update", "1", "--quantity", "9")
        self.assertEqual(self.ok("get", "1"), {"id": 1, "name": "A", "price": "1.00", "quantity": 9})
        self.assertEqual(len(self.ok("list")), 2)

    def test_default_path_is_products_json_in_current_directory(self):
        self.ok("add", "--name", "A", "--price", "1", "--quantity", "1")
        self.assertTrue(os.path.isfile(self.path))
        self.assertEqual(os.listdir(self.cwd), ["products.json"])

    def test_file_flag_before_command(self):
        other = os.path.join(self.cwd, "inventory.json")
        self.ok("--file", other, "add", "--name", "A", "--price", "1", "--quantity", "1")
        self.assertTrue(os.path.isfile(other))
        self.assertFalse(os.path.exists(self.path), "default file must not be touched")
        self.assertEqual(self.ok("--file", other, "list")[0]["name"], "A")
        self.assertEqual(self.ok("list"), [], "default store is still empty")

    def test_file_flag_after_command(self):
        other = os.path.join(self.cwd, "inventory.json")
        self.ok("add", "--file", other, "--name", "A", "--price", "1", "--quantity", "1")
        self.assertEqual(self.ok("list", "--file", other)[0]["name"], "A")
        self.assertEqual(self.ok("get", "1", "--file", other)["name"], "A")
        self.assertFalse(os.path.exists(self.path))

    def test_file_flag_relative_path(self):
        self.ok("--file", "sub.json", "add", "--name", "A", "--price", "1", "--quantity", "1")
        self.assertTrue(os.path.isfile(os.path.join(self.cwd, "sub.json")))

    def test_two_files_are_independent(self):
        self.seed(2)
        other = os.path.join(self.cwd, "other.json")
        self.ok("--file", other, "add", "--name", "Only", "--price", "1", "--quantity", "1")
        self.assertEqual(len(self.ok("list")), 2)
        self.assertEqual(len(self.ok("--file", other, "list")), 1)
        self.assertEqual(self.ok("--file", other, "get", "1")["name"], "Only")

    def test_missing_file_reads_as_empty_and_add_creates_it(self):
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.ok("list"), [])
        self.fails(1, "get", "1")
        self.assertFalse(os.path.exists(self.path), "reads must not create the file")
        self.ok("add", "--name", "A", "--price", "1", "--quantity", "1")
        self.assertEqual(self.file_json(), {"next_id": 2, "products": [
            {"id": 1, "name": "A", "price": "1.00", "quantity": 1}]})

    def test_update_and_delete_on_missing_file_do_not_create_it(self):
        self.fails(1, "update", "1", "--name", "X")
        self.fails(1, "delete", "1", "--yes")
        self.assertFalse(os.path.exists(self.path))


# ---------------------------------------------------------------------------
# Validation and errors
# ---------------------------------------------------------------------------

class A110ValueValidation(CliTestCase):
    def add(self, name="Widget", price="1", quantity="1"):
        return "add", "--name", name, "--price", price, "--quantity", quantity

    def test_name_rejected_when_empty_or_blank(self):
        for name in ("", " ", "\t", "   \n"):
            self.fails(2, *self.add(name=name))
        self.assertFalse(os.path.exists(self.path))

    def test_name_is_trimmed_on_add_and_update(self):
        """Leading and trailing whitespace is removed; the rest is kept as typed."""
        result = self.ok(*self.add(name="  Notebook  "))
        self.assertEqual(result["name"], "Notebook")
        self.assertEqual(self.file_json()["products"][0]["name"], "Notebook")
        result = self.ok("update", "1", "--name", "\tPencil \n")
        self.assertEqual(result["name"], "Pencil")
        self.assertEqual(self.ok("get", "1")["name"], "Pencil")

    def test_name_interior_text_is_preserved(self):
        """Only the ends are trimmed: inner spacing, case and punctuation survive."""
        for name in ("Blue  Widget", "Notebook (A5, ruled)", "café au lait", "a"):
            result = self.ok(*self.add(name=name))
            self.assertEqual(result["name"], name)
            self.assertEqual(self.ok("get", str(result["id"]))["name"], name)

    def test_duplicate_names_are_allowed(self):
        first = self.ok(*self.add(name="Notebook"))
        second = self.ok(*self.add(name="Notebook"))
        self.assertEqual((first["id"], second["id"]), (1, 2))
        self.assertEqual([p["name"] for p in self.ok("list")], ["Notebook", "Notebook"])
        self.assertEqual(self.ok("update", "2", "--name", "Notebook")["id"], 2)

    def test_id_cannot_be_supplied_on_add(self):
        """The tool assigns ids: neither an --id flag nor a positional id is accepted."""
        self.fails(2, "add", "--id", "5", "--name", "X", "--price", "1", "--quantity", "1")
        self.fails(2, "add", "5", "--name", "X", "--price", "1", "--quantity", "1")
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.ok(*self.add())["id"], 1)

    def test_price_rejected_when_not_a_plain_decimal(self):
        for price in ("abc", "", "-1", "-0.01", "+1", "+4.5", "nan", "inf", "-inf",
                      "1,5", "$5", "5%", "1e3", "1E3", "1.501", "4.", ".5", ".",
                      "1.5.0", " 1", "1 "):
            self.fails(2, *self.add(price=price))
        self.assertFalse(os.path.exists(self.path))

    def test_price_accepts_zero_one_or_two_decimal_places(self):
        self.assertEqual(self.ok(*self.add(price="9.99"))["price"], "9.99")
        self.assertEqual(self.ok(*self.add(price="10"))["price"], "10.00")
        self.assertEqual(self.ok(*self.add(price="0"))["price"], "0.00")
        self.assertEqual(self.ok(*self.add(price="0.5"))["price"], "0.50")
        self.assertEqual(self.ok(*self.add(price="4.5"))["price"], "4.50")

    def test_quantity_rejected_when_not_whole_or_negative(self):
        for quantity in ("abc", "", "1.5", "2.0", "-1", "-0", "+1", "1e3", "nan", "ten", "1 0"):
            self.fails(2, *self.add(quantity=quantity))
        self.assertFalse(os.path.exists(self.path))

    def test_quantity_accepts_zero_and_large_whole_numbers(self):
        self.assertEqual(self.ok(*self.add(quantity="0"))["quantity"], 0)
        self.assertEqual(self.ok(*self.add(quantity="1000000"))["quantity"], 1000000)

    def test_non_ascii_digits_are_rejected(self):
        """Only ASCII digits count: \\d in a regex would also match e.g. Arabic-Indic ٤."""
        self.fails(2, *self.add(price="١٢.٥٠"))
        self.fails(2, *self.add(quantity="٤"))
        self.fails(2, "get", "١")

    def test_absurdly_long_digit_strings(self):
        """int() refuses str-to-int conversions over ~4300 digits: quantity and id
        must report a usage error rather than crash. The price grammar has no length
        limit and uses Decimal, so a long-but-grammatical price is accepted."""
        self.fails(2, *self.add(quantity="9" * 5000))
        self.fails(2, "get", "9" * 5000)
        long_price = self.ok(*self.add(price="9" * 5000))
        self.assertEqual(long_price["price"], "9" * 5000 + ".00")

    def test_update_applies_the_same_rules(self):
        self.seed(1)
        before = self.file_bytes()
        for args in (("--name", ""), ("--name", "  "), ("--price", "-5"), ("--price", "x"),
                     ("--price", "1.501"), ("--price", "1e2"), ("--quantity", "1.5"),
                     ("--quantity", "-1"), ("--quantity", ""), ("--quantity", "+2")):
            self.fails(2, "update", "1", *args)
            self.assertEqual(self.file_bytes(), before)
        self.assertEqual(self.ok("get", "1")["name"], "P1")

    def test_one_bad_value_rejects_whole_add(self):
        """A valid name and price must not be saved when the quantity is bad."""
        self.fails(2, *self.add(name="Good", price="5", quantity="bad"))
        self.assertEqual(self.ok("list"), [])

    def test_one_bad_value_rejects_whole_update(self):
        self.seed(1)
        self.fails(2, "update", "1", "--name", "Good", "--price", "-1")
        self.assertEqual(self.ok("get", "1"), {"id": 1, "name": "P1", "price": "1.50", "quantity": 1})

    def test_validation_happens_before_the_file_is_read(self):
        """Bad values are rejected as usage errors even when the file is corrupt."""
        self.write_file("not json")
        self.fails(2, *self.add(price="-1"))
        self.assertEqual(self.file_bytes(), b"not json")


class A111InvocationValidation(CliTestCase):
    def test_invalid_ids(self):
        self.seed(1)
        for bad in ("abc", "0", "-1", "1.5", "", "1a", "0x1", "one", " "):
            self.fails(2, "get", bad)
            self.fails(2, "update", bad, "--name", "X")
            self.fails(2, "delete", bad, "--yes")

    def test_syntax_errors(self):
        self.seed(1)
        self.fails(2, "get")                                   # missing id
        self.fails(2, "get", "1", "2")                         # extra positional
        self.fails(2, "list", "extra")
        self.fails(2, "get", "1", "--bogus")                   # unknown flag
        self.fails(2, "--bogus", "list")
        self.fails(2, "add", "--name")                         # flag without value
        self.fails(2, "--file")                                # global flag without value
        self.fails(2, "--file", "", "list")                    # empty path

    def test_missing_required_flags_on_add(self):
        self.fails(2, "add")
        self.fails(2, "add", "--name", "X")
        self.fails(2, "add", "--name", "X", "--price", "1")
        self.fails(2, "add", "--price", "1", "--quantity", "1")
        self.fails(2, "add", "--name", "X", "--quantity", "1")
        self.assertFalse(os.path.exists(self.path))

    def test_empty_update_is_rejected(self):
        self.seed(1)
        before = self.file_bytes()
        self.fails(2, "update", "1")
        self.assertEqual(self.file_bytes(), before)
        self.fails(2, "update")

    def test_delete_without_yes_is_rejected(self):
        self.seed(2)
        before = self.file_bytes()
        stderr = self.fails(2, "delete", "1")
        self.assertIn("--yes", stderr)
        self.assertEqual(self.file_bytes(), before)
        self.assertEqual(len(self.ok("list")), 2)

    def test_abbreviated_flags_are_not_accepted(self):
        self.fails(2, "add", "--nam", "X", "--price", "1", "--quantity", "1")
        self.fails(2, "delete", "1", "--y")
        self.fails(2, "lowstock", "--thresh", "1")


class A112ErrorReporting(CliTestCase):
    def test_missing_id_on_get_update_delete(self):
        self.seed(2)
        for args in (("get", "99"), ("update", "99", "--name", "X"), ("delete", "99", "--yes")):
            stderr = self.fails(1, *args)
            self.assertIn("99", stderr)
            self.assertIn("not found", stderr)

    def test_invalid_json_in_file(self):
        self.write_file("{ this is not json")
        self.fails(1, "list")
        self.fails(1, "get", "1")
        self.fails(1, "add", "--name", "X", "--price", "1", "--quantity", "1")
        self.fails(1, "update", "1", "--name", "X")
        self.fails(1, "delete", "1", "--yes")
        self.fails(1, "lowstock", "--threshold", "5")

    def test_wrong_shape_in_file(self):
        cases = [
            [],                                                     # not an object
            {},                                                     # keys missing
            {"products": []},                                       # no next_id
            {"next_id": 1},                                         # no products
            {"next_id": "1", "products": []},                       # next_id not an int
            {"next_id": 0, "products": []},                         # next_id below 1
            {"next_id": 1, "products": {}},                         # products not a list
            {"next_id": 2, "products": [{"id": 1}]},                # fields missing
            {"next_id": 2, "products": [{"id": 1, "name": "", "price": "1.00", "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": "1", "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": "1.5", "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": "1.500", "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": "1.50.0", "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": "-1.00", "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": 1.0, "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": 1, "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": None, "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": "1.00", "quantity": 1.5}]},
            {"next_id": 2, "products": [{"id": "1", "name": "A", "price": "1.00", "quantity": 1}]},
            {"next_id": 2, "products": [{"id": 1, "name": "A", "price": "1.00", "quantity": -1}]},
            {"next_id": 1, "products": [{"id": 1, "name": "A", "price": "1.00", "quantity": 1}]},  # id >= next_id
            {"next_id": 3, "products": [{"id": 1, "name": "A", "price": "1.00", "quantity": 1},
                                        {"id": 1, "name": "B", "price": "1.00", "quantity": 1}]},  # duplicate id
        ]
        for case in cases:
            self.write_file(case)
            stderr = self.fails(1, "list")
            self.assertIn("invalid data", stderr, case)

    def test_valid_canonical_file_is_accepted(self):
        """A hand-written file using the documented schema must load fine."""
        self.write_file({"next_id": 2, "products": [
            {"id": 1, "name": "A", "price": "1.00", "quantity": 1}]})
        self.assertEqual(self.ok("list"), [{"id": 1, "name": "A", "price": "1.00", "quantity": 1}])

    def test_not_utf8_file(self):
        self.write_file(b"\xff\xfe\x00garbage")
        self.assertIn("UTF-8", self.fails(1, "list"))

    def test_empty_file_is_an_error_and_is_left_unchanged(self):
        self.write_file(b"")
        self.fails(1, "list")
        self.fails(1, "add", "--name", "X", "--price", "1", "--quantity", "1")
        self.assertEqual(self.file_bytes(), b"")

    def test_path_is_a_directory(self):
        folder = os.path.join(self.cwd, "folder")
        os.mkdir(folder)
        self.fails(1, "--file", folder, "list")
        self.fails(1, "--file", folder, "add", "--name", "X", "--price", "1", "--quantity", "1")
        self.assertTrue(os.path.isdir(folder))

    def test_missing_parent_directory_on_write(self):
        missing = os.path.join(self.cwd, "no-such-dir", "products.json")
        self.fails(1, "--file", missing, "add", "--name", "X", "--price", "1", "--quantity", "1")
        self.assertFalse(os.path.exists(missing))

    @unittest.skipIf(IS_ROOT, "root ignores file permissions")
    def test_unreadable_file(self):
        self.seed(1)
        os.chmod(self.path, 0)
        self.addCleanup(os.chmod, self.path, stat.S_IRUSR | stat.S_IWUSR)
        self.assertIn("cannot read", self.fails(1, "list"))

    @unittest.skipIf(IS_ROOT, "root ignores directory permissions")
    def test_unwritable_directory_leaves_file_unchanged(self):
        self.seed(1)
        before = self.file_bytes()
        os.chmod(self.cwd, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, self.cwd, stat.S_IRWXU)
        self.assertIn("cannot write", self.fails(1, "add", "--name", "X", "--price", "1", "--quantity", "1"))
        self.assertEqual(self.file_bytes(), before)
        self.assertEqual(os.listdir(self.cwd), ["products.json"], "no temp file left behind")

    def test_errors_go_to_stderr_without_traceback_or_success_json(self):
        proc = self.raw("get", "42")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("Error:"))
        self.assertNotIn("Traceback", proc.stderr)


class A113FailedMutationsLeaveFileUnchanged(CliTestCase):
    def setUp(self):
        super().setUp()
        self.seed(2)
        self.before = self.file_bytes()
        self.before_digest = self.digest()

    def check(self, code, *args):
        self.fails(code, *args)
        self.assertEqual(self.digest(), self.before_digest, "file bytes changed after %r" % (args,))
        self.assertEqual(self.file_json()["next_id"], 3, "next_id changed after %r" % (args,))
        self.assertEqual(os.listdir(self.cwd), ["products.json"], "stray file after %r" % (args,))

    def test_update_missing_id(self):
        self.check(1, "update", "99", "--name", "X")

    def test_delete_missing_id(self):
        self.check(1, "delete", "99", "--yes")

    def test_delete_without_yes(self):
        self.check(2, "delete", "1")

    def test_empty_update(self):
        self.check(2, "update", "1")

    def test_invalid_values_on_add(self):
        self.check(2, "add", "--name", "", "--price", "1", "--quantity", "1")
        self.check(2, "add", "--name", "X", "--price", "-1", "--quantity", "1")
        self.check(2, "add", "--name", "X", "--price", "1.501", "--quantity", "1")
        self.check(2, "add", "--name", "X", "--price", "1", "--quantity", "1.5")

    def test_invalid_values_on_update(self):
        self.check(2, "update", "1", "--price", "abc")
        self.check(2, "update", "1", "--quantity", "-3")
        self.check(2, "update", "1", "--name", " ")

    def test_missing_flags_on_add(self):
        self.check(2, "add", "--name", "X")

    def test_invalid_id_syntax(self):
        self.check(2, "update", "abc", "--name", "X")
        self.check(2, "delete", "abc", "--yes")

    def test_corrupt_file_is_not_overwritten(self):
        self.write_file(b"{broken")
        for args in (("add", "--name", "X", "--price", "1", "--quantity", "1"),
                     ("update", "1", "--name", "X"), ("delete", "1", "--yes")):
            self.fails(1, *args)
            self.assertEqual(self.file_bytes(), b"{broken")

    def test_successful_mutation_does_change_file(self):
        """Sanity check that the digest comparison is meaningful."""
        self.ok("update", "1", "--name", "Changed")
        self.assertNotEqual(self.digest(), self.before_digest)


# ---------------------------------------------------------------------------
# Custom feature: lowstock
# ---------------------------------------------------------------------------

class CustomLowStock(CliTestCase):
    def stock(self):
        """Three products: quantities 2, 0 and 30 (ids 1..3)."""
        self.ok("add", "--name", "Eraser", "--price", "0.50", "--quantity", "2")
        self.ok("add", "--name", "Stapler", "--price", "3.25", "--quantity", "0")
        self.ok("add", "--name", "Ruler", "--price", "1.10", "--quantity", "30")

    def test_reports_products_at_or_below_threshold_sorted_by_id(self):
        self.stock()
        report = self.ok("lowstock", "--threshold", "5")
        self.assertEqual([p["id"] for p in report], [1, 2])
        self.assertEqual([p["name"] for p in report], ["Eraser", "Stapler"])

    def test_threshold_is_inclusive(self):
        self.stock()
        self.assertEqual([p["id"] for p in self.ok("lowstock", "--threshold", "2")], [1, 2])
        self.assertEqual([p["id"] for p in self.ok("lowstock", "--threshold", "30")], [1, 2, 3])

    def test_high_threshold_returns_everything(self):
        self.stock()
        self.assertEqual(len(self.ok("lowstock", "--threshold", "100")), 3)

    def test_no_matching_products_prints_empty_array(self):
        self.ok("add", "--name", "Ruler", "--price", "1.10", "--quantity", "30")
        self.assertEqual(self.ok("lowstock", "--threshold", "5"), [])

    def test_zero_threshold_matches_only_out_of_stock(self):
        self.stock()
        report = self.ok("lowstock", "--threshold", "0")
        self.assertEqual([p["name"] for p in report], ["Stapler"])

    def test_missing_file_reads_as_empty_and_creates_nothing(self):
        self.assertEqual(self.ok("lowstock", "--threshold", "5"), [])
        self.assertFalse(os.path.exists(self.path), "lowstock must not create the file")

    def test_invalid_thresholds_are_usage_errors(self):
        for threshold in ("-1", "abc", "1.5", "2.0", "1e3", "", "+1"):
            self.fails(2, "lowstock", "--threshold", threshold)

    def test_missing_threshold_is_a_usage_error(self):
        self.fails(2, "lowstock")

    def test_positional_threshold_is_a_usage_error(self):
        self.stock()
        before = self.digest()
        self.fails(2, "lowstock", "5")
        self.assertEqual(self.digest(), before)

    def test_unknown_flag_is_a_usage_error(self):
        self.fails(2, "lowstock", "--threshold", "5", "--bogus")

    def test_failed_lowstock_does_not_change_the_file(self):
        self.stock()
        before = self.digest()
        self.fails(2, "lowstock", "--threshold", "-1")
        self.assertEqual(self.digest(), before)

    def test_successful_lowstock_does_not_rewrite_the_file(self):
        self.stock()
        before = self.digest()
        self.ok("lowstock", "--threshold", "5")
        self.assertEqual(self.digest(), before, "read-only command rewrote the file")

    def test_works_with_file_flag(self):
        other = os.path.join(self.cwd, "store.json")
        self.ok("--file", other, "add", "--name", "Eraser", "--price", "0.50", "--quantity", "2")
        self.assertEqual([p["name"] for p in self.ok("--file", other, "lowstock", "--threshold", "5")], ["Eraser"])
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()


