#!/usr/bin/env python

import copy
import os
import tempfile
import unittest
from unittest import mock

from avocado import Test

from avocado_vt.discovery import DiscoveryMixIn
from virttest import cartconf
from virttest.cartconf import EmptyCartesianProduct, Parser
from virttest.cartgraph import utils as param


class ParamsParserTest(Test):
    def setUp(self):
        self.base_dict = {}
        self.base_str = "only normal\n"
        self.base_file = "sets.cfg"

    def tearDown(self):
        pass

    def test_all_suffixes_by_restriction(self):
        """Test a resulting list of suffixes from a suffix variant restriction."""
        output = param.all_suffixes_by_restriction("only cluster1", key="nets")
        self.assertEqual(
            output, ["cluster1.net6", "cluster1.net7", "cluster1.net8", "cluster1.net9"]
        )

        output = param.all_suffixes_by_restriction(
            "no localhost, net6, net7", key="nets"
        )
        self.assertEqual(
            output, ["cluster1.net8", "cluster1.net9", "cluster2.net8", "cluster2.net9"]
        )

    def test_join_str(self):
        """Test that a resulting join string satisfies a certain syntactic form."""
        output = param.join_str(
            {"vm2": "param1 = A\n", "vm1": "only a"}, "vms", base_str="param2 = B\n"
        )
        self.assertEqual(
            output,
            "param2 = B\n"
            "vm1:\n"
            "    only a\n"
            "vm2:\n"
            "    param1 = A\n"
            "join vm1 vm2\n",
        )

        with self.assertRaises(ValueError):
            param.join_str({"vm_VARIANT_NOT_IN_VMS": "param1 = A\n"}, "vms")

    def test_get_parser_cached(self):
        """Separate VT parsers reuse CartConf ASTs without sharing later edits."""
        left, right = param.get_parser(), param.get_parser()
        for config in (left, right):
            config.parse_file(param.config_file(self.base_file))
            if self.base_str:
                config.parse_str(self.base_str)
        self.assertIsInstance(left, Parser)
        self.assertIs(left.ast, right.ast)
        expected = list(right.iter_params())
        left.parse_dict({"extra": "left"})
        self.assertTrue(all(d["extra"] == "left" for d in left.iter_params()))
        self.assertEqual(list(right.iter_params()), expected)

    def test_parser_copy_isolation(self):
        """Recipes can branch while their parent is being evaluated."""
        parent = param.get_parser()
        parent.parse_str("variants:\n    - a:\n    - b:\n")
        original_steps = parent.steps
        for expected, d in zip(("a", "b"), parent.iter_params()):
            child = copy.copy(parent)
            child.parse_str("only " + d["name"])
            child.parse_dict({"branch": expected})
            self.assertEqual(child.get_params()["name"], expected)
            self.assertEqual(child.get_params()["branch"], expected)
        self.assertEqual(parent.steps, original_steps)
        self.assertEqual([d["name"] for d in parent.iter_params()], ["a", "b"])
        self.assertTrue(all("branch" not in d for d in parent.iter_params()))

    def test_parse_input_order(self):
        """Files, strings and dictionaries retain their overwrite priority."""
        with tempfile.TemporaryDirectory() as directory:
            for name, value in (("base.cfg", "1"), ("overwrite.cfg", "4")):
                with open(os.path.join(directory, name), "w") as handle:
                    handle.write("value += %s\n" % value)
            config = param.get_parser()
            config.parse_dict({"value": "0"})
            with mock.patch.object(param, "custom_configs_dir", return_value=directory):
                config.parse_file(param.config_file("base.cfg"))
                config.parse_str("value += 2\n")
                config.parse_dict({"value": "${value}3"})
                config.parse_file(param.config_file("overwrite.cfg"))
                config.parse_str("value += 5\n")
                config.parse_dict({"value": "${value}6"})
            self.assertEqual(config.get_params()["value"], "0123456")
            report = str(config)
            self.assertIn(os.path.join(directory, "base.cfg"), report)
            self.assertIn("Parsed string:", report)
            self.assertIn("Parsed dictionary:", report)

    def test_parser_defaults(self):
        """New parsers pick up current defaults even after the AST cache is warm."""
        with mock.patch.dict(os.environ, {"PREFIX": "first"}):
            first = param.get_parser()
            first.parse_dict({"value": "same"})
        with mock.patch.dict(os.environ, {"PREFIX": "second"}):
            second = param.get_parser()
            second.parse_dict({"value": "same"})
        self.assertEqual(first.get_params()["hostname"], "first")
        self.assertEqual(second.get_params()["hostname"], "second")

    def test_save_config_preserves_input_order(self):
        """Saved configurations retain every input and its overwrite priority."""
        with tempfile.TemporaryDirectory() as directory:
            base = os.path.join(directory, "base.cfg")
            saved = os.path.join(directory, "saved.cfg")
            with open(base, "w") as handle:
                handle.write("value += 1\nvariants:\n    - a:\n    - b:\n")
            parsed = Parser()
            parsed.parse_dict({"value": "0"})
            parsed.parse_file(base)
            parsed.parse_str("value += 2\n")
            parsed.parse_dict({"value": "${value}3"})
            parsed.parse_str("only a")
            parsed.parse_dict({"extra": "retained"})
            discovery = DiscoveryMixIn()
            discovery.config = {"vt.save_config": saved}
            discovery._save_parser_cartesian_config(parsed)
            restored = Parser(saved)
            self.assertEqual(
                list(restored.get_dicts_gen()), list(parsed.get_dicts_gen())
            )

    def test_parser_params(self):
        """Test that parameters obtain from parser or directly are the same."""
        self.base_str += "only tutorial1\n"
        config = param.get_parser()
        config.parse_file(param.config_file(self.base_file))
        if self.base_str:
            config.parse_str(self.base_str)
        if self.base_dict:
            config.parse_dict(self.base_dict)
        params = config.get_params()
        d = config.iter_params().__next__()
        for key in params.keys():
            self.assertEqual(
                params[key],
                d[key],
                "The %s parameter must coincide: %s != %s" % (key, params[key], d[key]),
            )

    def test_params_dict_index(self):
        """Test that parameters obtained via an additional dictionary index are the correct ones."""
        self.base_str = "only all..tutorial2\n"
        config = param.get_parser()
        config.parse_file(param.config_file(self.base_file))
        if self.base_str:
            config.parse_str(self.base_str)
        if self.base_dict:
            config.parse_dict(self.base_dict)
        params = config.get_params(dict_index=1)
        for i, d in enumerate(config.iter_params()):
            if i == 1:
                for key in params.keys():
                    self.assertEqual(
                        params[key],
                        d[key],
                        "The %s parameter must coincide: %s != %s"
                        % (key, params[key], d[key]),
                    )

        with self.assertRaises(ValueError):
            config.get_params(dict_index=2)

    def test_params_single_traversal(self):
        """Selecting parameters checks existence without a second traversal."""
        config = param.get_parser()
        config.parse_str(
            "variants:\n    - a:\n        value = one\n"
            "    - b:\n        value = two\n"
        )
        with mock.patch.object(
            Parser, "get_dicts_gen", autospec=True, side_effect=Parser.get_dicts_gen
        ) as get_dicts:
            params = config.get_params(dict_index=1)
        self.assertEqual(params["value"], "two")
        get_dicts.assert_called_once()

    def test_params_empty_product(self):
        """An empty product keeps its distinct error for any dictionary index."""
        config = param.get_parser()
        config.parse_str("variants:\n    - a:\nonly missing\n")
        for verbose in (False, True):
            for dict_index in (0, 1, -1):
                with self.subTest(verbose=verbose, dict_index=dict_index):
                    with self.assertRaises(EmptyCartesianProduct) as error:
                        config.get_params(dict_index=dict_index, verbose=verbose)
                    self.assertIn(str(config), str(error.exception))


if __name__ == "__main__":
    unittest.main()
