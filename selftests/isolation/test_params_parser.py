#!/usr/bin/env python

import copy
import os
import tempfile
import unittest
from unittest import mock

from avocado import Test

import virttest.params_parser as param
from virttest.cartconf import IS_VARIANTER, Parser


class ParamsParserTest(Test):
    def setUp(self):
        self.base_dict = {}
        self.base_str = "only normal\n"
        self.base_file = "sets.cfg"
        self.show_restriction = False
        self.show_dictionaries = False
        self.show_dict_fullname = False
        self.show_dict_contents = False

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

    @unittest.skipUnless(IS_VARIANTER, "AST caching requires CartConf")
    def test_get_parser_cached(self):
        """Separate VT parsers reuse CartConf ASTs without sharing later edits."""
        left, right = param.get_parser(), param.get_parser()
        for config in (left, right):
            param.parse_batch(config, base_file=self.base_file, base_str=self.base_str)
        self.assertIsInstance(left, Parser)
        self.assertIs(left.ast, right.ast)
        expected = list(param.get_dicts(right))
        left.parse_dict({"extra": "left"})
        self.assertTrue(all(d["extra"] == "left" for d in param.get_dicts(left)))
        self.assertEqual(list(param.get_dicts(right)), expected)

    def test_parser_copy_isolation(self):
        """Recipes can branch while their parent is being evaluated."""
        parent = param.get_parser()
        parent.parse_string("variants:\n    - a:\n    - b:\n")
        original_steps = parent.steps
        for expected, d in zip(("a", "b"), param.get_dicts(parent)):
            child = copy.copy(parent)
            child.parse_string("only " + d["name"])
            child.parse_dict({"branch": expected})
            self.assertEqual(param.get_params(child)["name"], expected)
            self.assertEqual(param.get_params(child)["branch"], expected)
        self.assertEqual(parent.steps, original_steps)
        self.assertEqual([d["name"] for d in param.get_dicts(parent)], ["a", "b"])
        self.assertTrue(all("branch" not in d for d in param.get_dicts(parent)))

    def test_parse_batch_order(self):
        """Files, strings and dictionaries retain their overwrite priority."""
        with tempfile.TemporaryDirectory() as directory:
            for name, value in (("base.cfg", "1"), ("overwrite.cfg", "4")):
                with open(os.path.join(directory, name), "w") as handle:
                    handle.write("value += %s\n" % value)
            config = param.get_parser()
            config.parse_dict({"value": "0"})
            with mock.patch.object(param, "custom_configs_dir", return_value=directory):
                param.parse_batch(
                    config,
                    base_file="base.cfg",
                    base_str="value += 2\n",
                    base_dict={"value": "${value}3"},
                    ovrwrt_file="overwrite.cfg",
                    ovrwrt_str="value += 5\n",
                    ovrwrt_dict={"value": "${value}6"},
                )
            self.assertEqual(param.get_params(config)["value"], "0123456")
            report = param.report_parser(config)
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
        self.assertEqual(param.get_params(first)["hostname"], "first")
        self.assertEqual(param.get_params(second)["hostname"], "second")

    def test_parser_params(self):
        """Test that parameters obtain from parser or directly are the same."""
        self.base_str += "only tutorial1\n"
        config = param.get_parser()
        param.parse_batch(
            config,
            base_file=self.base_file,
            base_str=self.base_str,
            base_dict=self.base_dict,
        )
        params = param.get_params(
            config,
            show_restriction=False,
            show_dictionaries=False,
            show_dict_fullname=False,
            show_dict_contents=False,
        )
        d = param.get_dicts(config).__next__()
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
        param.parse_batch(
            config,
            base_file=self.base_file,
            base_str=self.base_str,
            base_dict=self.base_dict,
        )
        params = param.get_params(
            config,
            dict_index=1,
            show_restriction=False,
            show_dictionaries=False,
            show_dict_fullname=False,
            show_dict_contents=False,
        )
        for i, d in enumerate(param.get_dicts(config)):
            if i == 1:
                for key in params.keys():
                    self.assertEqual(
                        params[key],
                        d[key],
                        "The %s parameter must coincide: %s != %s"
                        % (key, params[key], d[key]),
                    )

        with self.assertRaises(ValueError):
            param.get_params(config, dict_index=2)

    def test_params_single_traversal(self):
        """Selecting parameters checks existence without a second traversal."""
        config = param.get_parser()
        config.parse_string(
            "variants:\n    - a:\n        value = one\n"
            "    - b:\n        value = two\n"
        )
        with mock.patch.object(
            Parser, "get_dicts_gen", autospec=True, side_effect=Parser.get_dicts_gen
        ) as get_dicts:
            params = param.get_params(config, list_of_keys=["value"], dict_index=1)
        self.assertEqual(params, {"value": "two"})
        get_dicts.assert_called_once()

    def test_params_empty_product(self):
        """An empty product keeps its distinct error for any dictionary index."""
        config = param.get_parser()
        config.parse_string("variants:\n    - a:\nonly missing\n")
        for show_dictionaries in (False, True):
            for dict_index in (0, 1, -1):
                with self.subTest(
                    show_dictionaries=show_dictionaries, dict_index=dict_index
                ):
                    with self.assertRaises(param.EmptyCartesianProduct) as error:
                        param.get_params(
                            config,
                            dict_index=dict_index,
                            show_dictionaries=show_dictionaries,
                        )
                    self.assertIn(param.report_parser(config), str(error.exception))

    def test_params_show_dictionaries(self):
        """Printing all variants preserves the requested parameter selection."""
        config = param.get_parser()
        config.parse_string("variants:\n    - a:\n    - b:\n")
        printed = []
        with mock.patch.object(
            param,
            "print_dicts",
            side_effect=lambda options, dicts: printed.extend(dicts),
        ):
            params = param.get_params(config, dict_index=1, show_dictionaries=True)
        self.assertEqual([d["name"] for d in printed], ["a", "b"])
        self.assertEqual(params, printed[1])


if __name__ == "__main__":
    unittest.main()
