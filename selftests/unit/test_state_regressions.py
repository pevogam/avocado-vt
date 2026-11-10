"""Regression coverage for object availability and guest state preservation."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from virttest.states import composition, lvm, qcow2, ramfile
from virttest.states import setup as ss
from virttest.utils_params import Params


class Guest:
    """A guest whose power transitions really change its simulated RAM."""

    def __init__(self, name="vm1", alive=True):
        self.name = name
        self.alive = alive
        self.paused = False
        self.memory = "test result"
        self.saved = {}
        self.events = []
        self.monitor = mock.Mock()

    def is_alive(self):
        return self.alive

    def is_paused(self):
        return self.paused

    def destroy(self, gracefully=False):
        self.events.append("stop")
        self.memory = None
        self.alive = False

    def create(self):
        self.events.append("boot")
        self.memory = "fresh boot"
        self.alive = True

    def pause(self):
        self.paused = True

    def resume(self, timeout=3):
        self.paused = False

    def verify_status(self, status):
        assert status == "paused" and self.paused

    def savevm(self, state):
        self.saved[state] = self.memory


class StateAvailabilityTest(unittest.TestCase):
    def setUp(self):
        self.backend = mock.Mock()
        self.backend.check.return_value = True
        self.params = Params(
            {
                "states_chain": "images",
                "images": "disk1 disk2",
                "vms": "vm1",
                "states": "mock",
                "show_state": "saved",
            }
        )
        self.patch = mock.patch.dict(ss.BACKENDS, {"mock": self.backend})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_scan_requires_every_requested_object(self):
        self.backend.show.side_effect = lambda p, obj: (
            ["saved"] if p["images"] == "disk1" else []
        )
        self.assertEqual(ss.show_states(self.params, require_all=True), [])
        self.backend.show.return_value = ["saved"]
        self.backend.show.side_effect = None
        self.assertEqual(
            ss.show_states(self.params, require_all=True), ["saved", "saved"]
        )

    def test_scan_rejects_missing_storage_even_when_ignored(self):
        self.params["show_mode"] = "ri"
        self.backend.check.side_effect = [True, False]
        self.backend.show.return_value = ["saved"]
        self.assertEqual(ss.show_states(self.params, require_all=True), [])

    def test_each_object_uses_its_own_filter(self):
        self.params.update({"show_state_disk1": "first", "show_state_disk2": "last"})
        self.backend.show.return_value = ["first", "last", "unrelated"]
        self.assertEqual(ss.show_states(self.params), ["first", "last"])

    def test_finalized_storage_is_not_listed(self):
        self.params.update({"images": "disk1", "show_mode": "fa"})
        self.backend.show.side_effect = FileNotFoundError("storage was removed")
        self.assertEqual(ss.show_states(self.params), [])
        self.backend.finalize.assert_called_once()
        self.backend.show.assert_not_called()

    def test_real_scan_control_rejects_partial_setup(self):
        control = (
            Path(__file__).resolve().parents[2]
            / "tp_multivm/controls/pre_state.control"
        )
        self.params["states"] = "qcow2"
        source = control.read_text().replace("PARAMS = {}", "PARAMS = INPUT_PARAMS")
        for backend in (qcow2.QCOW2VTBackend, ramfile.RamfileBackend):
            patch = mock.patch.object(
                backend, "image_state_backend", backend.image_state_backend
            )
            patch.start()
            self.addCleanup(patch.stop)
        with mock.patch.object(
            qcow2.QCOW2Backend, "check", return_value=True
        ), mock.patch.object(qcow2.QCOW2Backend, "download"), mock.patch.object(
            qcow2.QCOW2Backend,
            "show",
            side_effect=lambda p, obj: ["saved"] if p["images"] == "disk1" else [],
        ), mock.patch.object(
            ss, "BACKENDS", {}
        ):
            with self.assertRaises(AssertionError):
                exec(
                    compile(source, str(control), "exec"), {"INPUT_PARAMS": self.params}
                )


class GuestStateTest(unittest.TestCase):
    def setUp(self):
        self.vm = Guest()
        self.env = mock.Mock()
        self.env.get_vm.return_value = self.vm
        self.params = Params(
            {
                "states_chain": "nets vms images",
                "nets": "net1",
                "vms": "vm1",
                "images": "disk1 disk2",
                "states_images": "qcow2",
                "images_base_dir": "/unused",
                "get_state_images": "saved",
                "set_state_images": "saved",
                "unset_state_images": "saved",
            }
        )
        patch = mock.patch.dict(ss.BACKENDS, {"qcow2": qcow2.QCOW2Backend})
        patch.start()
        self.addCleanup(patch.stop)

    def test_all_images_are_restored_before_boot(self):
        with mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(qcow2.QCOW2Backend, "_get_driver") as driver:
            driver.side_effect = lambda p, obj: self.vm.events.append(p["images"])
            ss.get_states(self.params, self.env)
        self.assertEqual(self.vm.events, ["stop", "disk1", "disk2", "boot"])

    def test_failed_restore_keeps_guest_off_and_does_not_leak_batch(self):
        with mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(qcow2.QCOW2Backend, "_get_driver") as driver:
            driver.side_effect = [None, OSError("second disk failed")]
            with self.assertRaises(OSError):
                ss.get_states(self.params, self.env)
        self.assertEqual(self.vm.events, ["stop"])
        composition.ImageStateBackend.switch_on("hard", self.vm)
        self.assertEqual(self.vm.events, ["stop", "boot"])

    def test_explicit_off_policy_keeps_guest_off(self):
        self.params["get_switch"] = "off"
        with mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(qcow2.QCOW2Backend, "_get_driver"):
            ss.get_states(self.params, self.env)
        self.assertEqual(self.vm.events, ["stop"])

    def test_last_image_can_explicitly_leave_guest_off(self):
        self.params["get_switch_disk2"] = "off"
        with mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(qcow2.QCOW2Backend, "_get_driver"):
            ss.get_states(self.params, self.env)
        self.assertEqual(self.vm.events, ["stop"])

    def test_guest_is_booted_before_its_vm_state_is_loaded(self):
        self.params.update({"states_vms": "mock", "get_state_vms": "running"})
        vm_backend = mock.Mock()
        vm_backend.get.side_effect = lambda p, obj: self.assertTrue(obj.is_alive())
        with mock.patch.dict(ss.BACKENDS, {"mock": vm_backend}), mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(qcow2.QCOW2Backend, "_get_driver"):
            ss.get_states(self.params, self.env)
        vm_backend.get.assert_called_once()
        self.assertEqual(self.vm.events, ["stop", "boot"])

    def test_image_overwrite_defaults_unset_switch_and_boots_once(self):
        with mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(
            qcow2.QCOW2Backend, "_unset_driver"
        ) as delete, mock.patch.object(
            qcow2.QCOW2Backend, "_set_driver"
        ) as save:
            delete.side_effect = lambda p, obj: self.vm.events.append(
                "delete:" + p["images"]
            )
            save.side_effect = lambda p, obj: self.vm.events.append(
                "save:" + p["images"]
            )
            ss.set_states(self.params, self.env)
        self.assertEqual(
            self.vm.events,
            [
                "stop",
                "delete:disk1",
                "save:disk1",
                "delete:disk2",
                "save:disk2",
                "boot",
            ],
        )
        self.assertEqual(delete.call_args.args[0]["unset_switch"], "soft")

    def test_lvm_overwrite_defaults_unset_switch(self):
        self.params.update(
            {"images": "disk1", "states_images": "lvm", "lv_pointer_name": "current"}
        )
        with mock.patch.dict(ss.BACKENDS, {"lvm": lvm.LVMBackend}), mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(lvm.LVMBackend, "_unset_driver"), mock.patch.object(
            lvm.LVMBackend, "_set_driver"
        ):
            ss.set_states(self.params, self.env)
        self.assertEqual(self.vm.events, ["stop", "boot"])

    def test_push_finishes_all_images_before_boot(self):
        self.params["push_state_images"] = "saved"
        with mock.patch.object(
            ss, "_state_check_chain", return_value=False
        ), mock.patch.object(qcow2.QCOW2Backend, "_set_driver") as driver:
            driver.side_effect = lambda p, obj: self.vm.events.append(p["images"])
            ss.push_states(self.params, self.env)
        self.assertEqual(self.vm.events, ["stop", "disk1", "disk2", "boot"])

    def test_pop_finishes_restore_and_removal_before_boot(self):
        self.params["pop_state_images"] = "saved"
        with mock.patch.object(
            ss, "_state_check_chain", return_value=True
        ), mock.patch.object(
            qcow2.QCOW2Backend, "_get_driver"
        ) as restore, mock.patch.object(
            qcow2.QCOW2Backend, "_unset_driver"
        ) as delete:
            restore.side_effect = lambda p, obj: self.vm.events.append(
                "get:" + p["images"]
            )
            delete.side_effect = lambda p, obj: self.vm.events.append(
                "unset:" + p["images"]
            )
            ss.pop_states(self.params, self.env)
        self.assertEqual(
            self.vm.events,
            ["stop", "get:disk1", "unset:disk1", "get:disk2", "unset:disk2", "boot"],
        )

    def test_qcow2vt_overwrite_preserves_current_ram(self):
        self.params.update(
            {"set_state_vms": "saved", "set_state_images": "", "states_vms": "qcow2vt"}
        )
        with mock.patch.dict(
            ss.BACKENDS, {"qcow2vt": qcow2.QCOW2VTBackend}
        ), mock.patch.object(ss, "_state_check_chain", return_value=True):
            ss.set_states(self.params, self.env)
        self.vm.monitor.send_args_cmd.assert_called_once_with("delvm id=saved")
        self.assertEqual(self.vm.saved["saved"], "test result")
        self.assertEqual(self.vm.events, [])

    def test_qcow2vt_deletion_preserves_paused_guest(self):
        self.vm.pause()
        qcow2.QCOW2VTBackend.unset(Params({"unset_state": "saved"}), self.vm)
        self.assertTrue(self.vm.is_paused())
        self.assertEqual(self.vm.events, [])

    def test_qcow2vt_offline_deletion_visits_all_images(self):
        self.vm.alive = False
        self.params["unset_state"] = "saved"
        with mock.patch.object(
            qcow2.QCOW2VTBackend, "image_state_backend", qcow2.QCOW2Backend
        ), mock.patch.object(qcow2.QCOW2Backend, "_unset_driver") as delete:
            qcow2.QCOW2VTBackend.unset(self.params, self.vm)
        self.assertEqual(
            [c.args[0]["images"] for c in delete.call_args_list], ["disk1", "disk2"]
        )
        self.assertEqual(self.vm.events, [])


class StoredStateTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.params = Params(
            {
                "states_chain": "vms",
                "states": "ramfile",
                "vms": "vm1",
                "images": "disk1 disk2",
                "object_id": "vm1-id",
                "swarm_pool": str(self.root),
                "show_state": "root",
                "show_mode": "fa",
                "pool_scope": "own",
            }
        )
        patch = mock.patch.object(
            ramfile.RamfileBackend, "image_state_backend", qcow2.QCOW2ExtBackend
        )
        patch.start()
        self.addCleanup(patch.stop)

    def test_initialize_check_and_finalize_each_image(self):
        ramfile.RamfileBackend.initialize(self.params)
        vm_dir = self.root / "vm1-id"
        self.assertEqual(sorted(p.name for p in vm_dir.iterdir()), ["disk1", "disk2"])
        self.assertTrue(ramfile.RamfileBackend.check(self.params))
        (vm_dir / "disk2").rmdir()
        self.assertFalse(ramfile.RamfileBackend.check(self.params))
        (vm_dir / "disk2").mkdir()
        ramfile.RamfileBackend.finalize(self.params)
        self.assertFalse(vm_dir.exists())

    def test_clean_removes_populated_layout_without_listing_it(self):
        ramfile.RamfileBackend.initialize(self.params)
        vm_dir = self.root / "vm1-id"
        (vm_dir / "saved.state").touch()
        for image in self.params.objects("images"):
            (vm_dir / image / "saved.qcow2").touch()
        with mock.patch.dict(ss.BACKENDS, {"ramfile": ramfile.RamfileBackend}):
            self.assertEqual(ss.show_states(self.params), [])
        self.assertFalse(vm_dir.exists())

    def test_unset_running_ramfile_guest_stops_once_before_deleting(self):
        ramfile.RamfileBackend.initialize(self.params)
        vm_dir = self.root / "vm1-id"
        self.params.update(
            {
                "unset_state": "saved",
                "images_base_dir": str(self.root / "heads"),
                "image_name": "head",
            }
        )
        (vm_dir / "saved.state").touch()
        for image in self.params.objects("images"):
            (vm_dir / image / "saved.qcow2").touch()
        vm = Guest()
        with mock.patch.object(qcow2.QCOW2Backend, "_finalize"):
            ramfile.RamfileBackend.unset(self.params, vm)
        self.assertEqual(vm.events, ["stop"])
        self.assertFalse((vm_dir / "saved.state").exists())
        for image in self.params.objects("images"):
            self.assertFalse((vm_dir / image / "saved.qcow2").exists())

    def test_manual_create_and_clean_manage_vm_root_once(self):
        from virttest import intertest_setup

        params = self.params.copy()
        params.update(
            {
                "states_chain": "nets vms images",
                "nets": "net1",
                "states_vms": "ramfile",
                "states_images": "qcow2ext",
            }
        )
        config = {"param_dict": params.copy()}

        def run_show(config, tag=""):
            return ss.show_states(Params(config["param_dict"]))

        with mock.patch.dict(
            ss.BACKENDS, {"ramfile": ramfile.RamfileBackend}
        ), mock.patch.object(
            intertest_setup, "show", side_effect=run_show
        ), mock.patch.object(
            ramfile.RamfileBackend, "_show_driver", return_value=[]
        ):
            intertest_setup.create(config)
            vm_dir = self.root / "vm1-id"
            self.assertTrue((vm_dir / "disk1").is_dir())
            self.assertTrue((vm_dir / "disk2").is_dir())
            (vm_dir / "saved.state").touch()
            (vm_dir / "disk1" / "saved.qcow2").touch()
            intertest_setup.clean(config)
            self.assertFalse(vm_dir.exists())
        self.assertEqual(config["param_dict"], params)

    def test_manual_collect_downloads_vm_root(self):
        from virttest import intertest_setup

        params = self.params.copy()
        params.update({"states": "qcow2vt", "show_state": ""})
        config = {"param_dict": params.copy()}

        def run_show(config, tag=""):
            return ss.show_states(Params(config["param_dict"]))

        with mock.patch.dict(
            ss.BACKENDS, {"qcow2vt": qcow2.QCOW2VTBackend}
        ), mock.patch.object(
            intertest_setup, "show", side_effect=run_show
        ), mock.patch.object(
            qcow2.QCOW2VTBackend, "check", return_value=True
        ), mock.patch.object(
            qcow2.QCOW2VTBackend, "download"
        ) as download, mock.patch.object(
            qcow2.QCOW2VTBackend, "show", return_value=[]
        ):
            intertest_setup.collect(config)
        download.assert_called_once()
        self.assertEqual(
            download.call_args.args[0]["pool_scope"], "swarm cluster shared"
        )


if __name__ == "__main__":
    unittest.main()
