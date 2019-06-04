#!/usr/bin/python

import os
import sys
import unittest
from collections import OrderedDict

# simple magic for using scripts within a source tree
basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.isdir(os.path.join(basedir, "virttest")):
    sys.path.append(basedir)

from virttest import utils_params

BASE_DICT = {
    "image_boot": "yes",
    "image_boot_stg": "no",
    "image_chain": "",
    "image_clone_command": "cp --reflink=auto %s %s",
    "image_format": "qcow2",
    "image_format_stg": "qcow2",
    "image_name": "images/f18-64",
    "image_name_stg": "enospc",
    "image_raw_device": "no",
    "image_remove_command": "rm -rf %s",
    "image_size": "10G",
    "image_snapshot_stg": "no",
    "image_unbootable_pattern": "Hard Disk.*not a bootable disk",
    "image_verify_bootable": "yes",
    "images": "image1 stg",
}

CORRECT_RESULT_MAPPING = {
    "image1": {
        "image_boot_stg": "no",
        "image_snapshot_stg": "no",
        "image_chain": "",
        "image_unbootable_pattern": "Hard Disk.*not a bootable disk",
        "image_name": "images/f18-64",
        "image_remove_command": "rm -rf %s",
        "image_name_stg": "enospc",
        "image_clone_command": "cp --reflink=auto %s %s",
        "image_size": "10G",
        "images": "image1 stg",
        "image_raw_device": "no",
        "image_format": "qcow2",
        "image_boot": "yes",
        "image_verify_bootable": "yes",
        "image_format_stg": "qcow2",
    },
    "stg": {
        "image_snapshot": "no",
        "image_boot_stg": "no",
        "image_snapshot_stg": "no",
        "image_chain": "",
        "image_unbootable_pattern": "Hard Disk.*not a bootable disk",
        "image_name": "enospc",
        "image_remove_command": "rm -rf %s",
        "image_name_stg": "enospc",
        "image_clone_command": "cp --reflink=auto %s %s",
        "image_size": "10G",
        "images": "image1 stg",
        "image_raw_device": "no",
        "image_format": "qcow2",
        "image_boot": "no",
        "image_verify_bootable": "yes",
        "image_format_stg": "qcow2",
    },
}


class TestParams(unittest.TestCase):
    def setUp(self):
        self.params = utils_params.Params(BASE_DICT)

    def testObjects(self):
        self.assertEquals(self.params.objects("images"), ["image1", "stg"])

    def testObjectsParams(self):
        for key in list(CORRECT_RESULT_MAPPING.keys()):
            self.assertEquals(
                self.params.object_params(key), CORRECT_RESULT_MAPPING[key]
            )

    def testGetItemMissing(self):
        try:
            self.params["bogus"]
            raise ValueError(
                "Did not get a ParamNotFound error when trying "
                "to access a non-existing param"
            )
        # pylint: disable=E0712
        except utils_params.ParamNotFound:
            pass

    def testGetItem(self):
        self.assertEqual(self.params["image_size"], "10G")

    def testGetBoolean(self):
        self.params["foo1"] = "yes"
        self.params["foo2"] = "no"
        self.params["foo3"] = "on"
        self.params["foo4"] = "off"
        self.params["foo5"] = "true"
        self.params["foo6"] = "false"
        self.assertEqual(True, self.params.get_boolean("foo1"))
        self.assertEqual(False, self.params.get_boolean("foo2"))
        self.assertEqual(True, self.params.get_boolean("foo3"))
        self.assertEqual(False, self.params.get_boolean("foo4"))
        self.assertEqual(True, self.params.get_boolean("foo5"))
        self.assertEqual(False, self.params.get_boolean("foo6"))
        self.assertEqual(False, self.params.get_boolean("notgiven"))

    def testGetNumeric(self):
        self.params["something"] = "7"
        self.params["foobar"] = 11
        self.params["barsome"] = 13.17
        self.assertEqual(7, self.params.get_numeric("something"))
        self.assertEqual(7, self.params.get_numeric("something"), int)
        self.assertEqual(7.0, self.params.get_numeric("something"), float)
        self.assertEqual(11, self.params.get_numeric("foobar"))
        self.assertEqual(11, self.params.get_numeric("something"), int)
        self.assertEqual(11.0, self.params.get_numeric("foobar"), float)
        self.assertEqual(13, self.params.get_numeric("barsome"))
        self.assertEqual(13, self.params.get_numeric("barsome"), int)
        self.assertEqual(13.17, self.params.get_numeric("barsome"), float)
        self.assertEqual(17, self.params.get_numeric("joke", 17))
        self.assertEqual(17.13, self.params.get_numeric("joke", 17.13), float)

    def testGetList(self):
        self.params["primes"] = "7 11 13 17"
        self.params["dashed"] = "7-11-13"
        self.assertEqual(["7", "11", "13", "17"], self.params.get_list("primes"))
        self.assertEqual(
            [7, 11, 13, 17], self.params.get_list("primes", "1 2 3", " ", int)
        )
        self.assertEqual([1, 2, 3], self.params.get_list("missing", "1 2 3", " ", int))
        self.assertEqual([7, 11, 13], self.params.get_list("dashed", "1 2 3", "-", int))

    def testGetDict(self):
        self.params["dummy"] = "name1=value1 name2=value2"
        self.assertEqual(
            {"name1": "value1", "name2": "value2"}, self.params.get_dict("dummy")
        )
        result_dict = self.params.get_dict("dummy", need_order=True)
        right_dict, wrong_dict = OrderedDict(), OrderedDict()
        right_dict["name1"] = "value1"
        right_dict["name2"] = "value2"
        wrong_dict["name2"] = "value2"
        wrong_dict["name1"] = "value1"
        self.assertEqual(right_dict, result_dict)
        self.assertNotEqual(wrong_dict, result_dict)

    def dropDictInternals(self):
        self.params["a"] = "7"
        self.params["b"] = "11"
        self.params["_b"] = "13"
        pruned = self.params.drop_dict_internals()
        self.assertIn("a", pruned.keys())
        self.assertEqual(pruned["a"], self.params["a"])
        self.assertIn("b", pruned.keys())
        self.assertEqual(pruned["b"], self.params["b"])
        self.assertNotIn("_b", pruned.keys())

    def testIsObjectSpecific(self):
        self.assertTrue(utils_params.is_object_specific("genie_vm1", ["vm1", "vm2"]))
        self.assertFalse(utils_params.is_object_specific("genie_vm1", ["nic1", "nic2"]))
        self.assertTrue(utils_params.is_object_specific("god_vm2", ["vm1", "vm2"]))
        self.assertFalse(utils_params.is_object_specific("god_vm2", ["nic1", "nic2"]))
        self.assertFalse(utils_params.is_object_specific("genie", ["vm1", "vm2"]))
        self.assertFalse(utils_params.is_object_specific("god", ["vm1", "vm2"]))
        self.assertFalse(utils_params.is_object_specific("wizard", ["vm1", "vm2"]))
        self.assertFalse(utils_params.is_object_specific("wizard", ["wizard"]))

    def testObjectParams(self):
        vm_params = utils_params.Params({"name_vm1": "josh", "name_vm2": "jean", "name": "jarjar", "surname": "jura"})
        params = utils_params.object_params(vm_params, "vm1", ["vm1", "vm2"])
        for key in params.keys():
            self.assertFalse(utils_params.is_object_specific(key, ["vm1", "vm2"]))

    def testObjectifyParams(self):
        params = utils_params.Params({"name_vm1": "josh", "name_vm2": "jean", "name": "jarjar", "surname": "jura"})
        vm_params = utils_params.objectify_params(params, "vm1", ["vm1", "vm2"])
        # Parameters already specific to the object must be preserved
        self.assertIn("name_vm1" in vm_params)
        # Parameters already specific to the object must be preserved
        self.assertEqual(vm_params["name_vm1"], params["name_vm1"])
        # Parameters specific to a different object must be pruned
        self.assertNotIn("name_vm2", vm_params)
        # Parameters not specific to any object must be pruned if there is specific alternative
        self.assertNotIn("name", vm_params)
        # Parameters not specific to any object must become specific to the object
        self.assertIn("surname_vm1", vm_params)
        # Parameters not specific to any object must become specific to the object
        self.assertNotIn("surname", vm_params)

    def testMergeObjectParams(self):
        params1 = utils_params.Params({"name_vm1": "josh", "name": "jarjar", "surname": "jura"})
        params2 = utils_params.Params({"name_vm2": "jean", "name": "jaja", "surname": "jura"})
        vm_params = utils_params.merge_object_params(["vm1", "vm2"], [params1, params2], "vms", "vm1")
        # Main object specific parameters must be default
        self.assertIn("name", vm_params)
        # Main object specific parameters must be default
        self.assertEqual(vm_params["name"], params1["name_vm1"])
        # Secondary object specific parameters must be preserved
        self.assertIn("name_vm2", vm_params)
        # Secondary object specific parameters must be preserved
        self.assertEqual(vm_params["name_vm2"], params2["name_vm2"])
        # The parameters identical for all objects are reduced to default parameters
        self.assertIn("surname", vm_params)
        # The parameters identical for all objects are reduced to default parameters
        self.assertEqual(vm_params["surname"], "jura")

    def testMultiplyParamsPerObject(self):
        os.environ['PREFIX'] = "ut"
        params = utils_params.Params({"vm_unique_keys": "foo bar", "foo": "baz", "bar": "bazz", "other": "misc"})
        vm_params = utils_params.multiply_params_per_object(params, ["vm1", "vm2"])
        # Object specific parameters must exist for each object
        self.assertIn("foo_vm1", vm_params)
        # Multiplication also involves the value
        self.assertTrue(vm_params["foo_vm1"].startswith("ut_vm1"), vm_params["foo_vm1"])
        # Object specific parameters must exist for each object
        self.assertIn("foo_vm2", vm_params)
        # Multiplication also involves the value
        self.assertTrue(vm_params["foo_vm2"].startswith("ut_vm2"), vm_params["foo_vm2"])
        # Default parameter is preserved after multiplication
        self.assertIn("foo", vm_params)
        # Default parameter value is preserved after multiplication
        self.assertFalse(vm_params["foo"].startswith("ut_vm1"), vm_params["foo"])
        # Default parameter value is preserved after multiplication
        self.assertFalse(vm_params["foo"].startswith("ut_vm2"), vm_params["foo"])
        # Object specific parameters must exist for each object
        self.assertIn("bar_vm1", vm_params)
        # Multiplication also involves the value
        self.assertTrue(vm_params["bar_vm1"].startswith("ut_vm1"), vm_params["bar_vm1"])
        # Object specific parameters must exist for each object
        self.assertIn("bar_vm2", vm_params)
        # Multiplication also involves the value
        self.assertTrue(vm_params["bar_vm2"].startswith("ut_vm2"), vm_params["bar_vm2"])
        # Default parameter is preserved after multiplication
        self.assertIn("bar", vm_params)
        # Default parameter value is preserved after multiplication
        self.assertFalse(vm_params["bar"].startswith("ut_vm1"), vm_params["bar"])
        # Default parameter value is preserved after multiplication
        self.assertFalse(vm_params["bar"].startswith("ut_vm2"), vm_params["bar"])
        # Object general parameters must not be multiplied
        self.assertNotIn("other_vm1", vm_params)
        # Object general parameters must not be multiplied
        self.assertNotIn("other_vm2", vm_params)
        # Object general parameters must be preserved as is
        self.assertIn("other", vm_params)
        # Object general parameter value is preserved after multiplication
        self.assertFalse(vm_params["other"].startswith("ut_vm1"), vm_params["other"])
        # Object general parameter value is preserved after multiplication
        self.assertFalse(vm_params["other"].startswith("ut_vm2"), vm_params["other"])


if __name__ == "__main__":
    unittest.main()
