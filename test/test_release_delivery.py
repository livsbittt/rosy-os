import importlib.util
import json
import shutil

import pytest

from layout import Layout, read_activation, tree_fingerprint
from release_fixture import archive, signed_tree


class Runtime:
    def __init__(self, layout):
        self.layout, self.running, self.fail = layout, False, set()
        self.started, self.loaded = [], []

    def assert_stopped(self):
        if self.running:
            from bundle import BundleError
            raise BundleError("RUNTIME_BUSY", "stop the runtime for maintenance")

    def load_images(self, root, manifest):
        self.loaded.append(manifest["release_id"])

    def stop(self):
        self.running = False

    def prepare_data(self, path):
        assert path.is_dir()

    def start(self, mode):
        self.running = True
        self.started.append((read_activation(self.layout).release_id, mode))

    def healthy(self):
        return read_activation(self.layout).release_id not in self.fail


def test_delivery_entry_point_exists():
    assert importlib.util.find_spec("delivery") is not None


@pytest.fixture
def device(tmp_path):
    from delivery import Delivery
    layout = Layout.rooted(tmp_path / "device")
    layout.create_directories()
    (layout.etc / "rosy.yaml").write_text("robot:\n  id: test_robot\n", encoding="utf-8")
    (layout.var / "waypoints.json").write_text('[{"name":"home"}]')
    (layout.var / ".rosy").mkdir()
    (layout.var / ".rosy" / "waypoints.json").write_text('[{"name":"actual-home"}]')
    runtime = Runtime(layout)
    first, public, _ = signed_tree(tmp_path / "inputs")
    key = layout.trusted_keys / public.name
    shutil.copy2(public, key)
    delivery = Delivery(layout, key, runtime, device_target={"os_suite": "trixie"})
    return delivery, runtime, first


def test_install_preserves_snapshots_and_runs_core_only(device, tmp_path):
    delivery, runtime, first = device
    version = delivery.stage(archive(first, tmp_path / "first.tar"))
    result = delivery.install(version)
    assert result.state.value == "ACTIVATED_CORE_ONLY"
    assert runtime.started == [(version, "core")]
    record = read_activation(delivery.layout)
    snapshot = delivery.layout.data_generation(record.data_generation)
    before = tree_fingerprint(snapshot)
    working = delivery.layout.var / "data-working" / record.data_generation
    assert json.loads((working / ".rosy/waypoints.json").read_text())[0]["name"] == "actual-home"
    (working / "waypoints.json").write_text('[{"name":"changed"}]')
    assert tree_fingerprint(snapshot) == before
    assert (delivery.layout.etc / "rosy.yaml").read_text().startswith("robot:")


def test_failed_candidate_rolls_back_with_prior_working_data(device, tmp_path):
    delivery, runtime, first = device
    old = delivery.stage(archive(first, tmp_path / "first.tar"))
    delivery.install(old)
    old_record = read_activation(delivery.layout)
    old_work = delivery.layout.var / "data-working" / old_record.data_generation / "waypoints.json"
    old_work.write_text('[{"name":"operator-edit"}]')
    second, _, _ = signed_tree(tmp_path / "inputs", "2026.09.08-002")
    new = delivery.stage(archive(second, tmp_path / "second.tar"))
    runtime.stop()
    runtime.fail.add(new)
    result = delivery.install(new, health_timeout_s=0)
    assert result.state.value == "ROLLED_BACK_CORE_ONLY"
    assert read_activation(delivery.layout).release_id == old
    assert json.loads(old_work.read_text())[0]["name"] == "operator-edit"
    assert runtime.started[-1] == (old, "core")


def test_running_robot_is_refused_before_loading_images(device, tmp_path):
    from bundle import BundleError
    delivery, runtime, first = device
    version = delivery.stage(archive(first, tmp_path / "first.tar"))
    runtime.running = True
    with pytest.raises(BundleError, match="RUNTIME_BUSY"):
        delivery.install(version)
    assert runtime.loaded == []
    assert not delivery.layout.activation.exists()


def test_explicit_rollback_restores_previous_activation(device, tmp_path):
    delivery, runtime, first = device
    old = delivery.stage(archive(first, tmp_path / "first.tar"))
    delivery.install(old)
    second, _, _ = signed_tree(tmp_path / "inputs", "2026.09.08-002")
    new = delivery.stage(archive(second, tmp_path / "second.tar"))
    runtime.stop()
    delivery.install(new)
    runtime.stop()
    delivery.rollback()
    assert read_activation(delivery.layout).release_id == old
    assert runtime.started[-1] == (old, "core")


def test_staged_tampering_is_reverified_before_install(device, tmp_path):
    from bundle import BundleError
    delivery, runtime, first = device
    version = delivery.stage(archive(first, tmp_path / "first.tar"))
    (delivery.layout.staging / version / "runtime/compose.yaml").write_text("changed")
    with pytest.raises(BundleError, match="CHECKSUM_MISMATCH"):
        delivery.install(version)
    assert not runtime.loaded


def test_start_exception_also_rolls_back(device, tmp_path):
    delivery, runtime, first = device
    old = delivery.stage(archive(first, tmp_path / "first.tar"))
    delivery.install(old)
    second, _, _ = signed_tree(tmp_path / "inputs", "2026.09.08-002")
    new = delivery.stage(archive(second, tmp_path / "second.tar"))
    runtime.stop()
    original = runtime.start

    def start(mode):
        if read_activation(delivery.layout).release_id == new:
            raise RuntimeError("compose failed before health")
        original(mode)

    delivery.updater._start_runtime = start
    result = delivery.install(new)
    assert result.state.value == "ROLLED_BACK_CORE_ONLY"
    assert read_activation(delivery.layout).release_id == old


def test_rollback_record_is_durable_before_success_journal_is_removed(device, tmp_path):
    delivery, runtime, first = device
    old = delivery.stage(archive(first, tmp_path / "first.tar"))
    delivery.install(old)
    second, _, _ = signed_tree(tmp_path / "inputs", "2026.09.08-002")
    new = delivery.stage(archive(second, tmp_path / "second.tar"))
    runtime.stop()

    class PowerLoss(BaseException):
        pass

    def lost_power():
        raise PowerLoss()

    delivery.updater._clear_journal = lost_power
    with pytest.raises(PowerLoss):
        delivery.install(new)
    assert read_activation(delivery.layout).release_id == new
    assert json.loads(delivery.previous.read_text())["release_id"] == old


def test_signed_runtime_payload_is_readable_by_the_core_account(device, tmp_path):
    import os
    import stat
    if os.name != "posix":
        pytest.skip("POSIX permission bits; also run on Linux")
    delivery, _, first = device
    version = delivery.stage(archive(first, tmp_path / "first.tar"))
    delivery.install(version)
    mode = (delivery.layout.release(version) / "runtime/compose.yaml").stat().st_mode
    assert mode & stat.S_IROTH
    assert not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
