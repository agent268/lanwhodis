"""User corrections: persistence, overlay semantics, CLI, rule suggestions."""
import json

import pytest

from lanwhodis import classify, cli, export, labels, rules as rules_mod
from lanwhodis.labels import LabelStore
from test_core import make

MAC = "aa:bb:cc:dd:ee:01"


@pytest.fixture
def store(tmp_path):
    return LabelStore(tmp_path / "labels.json")


def test_set_get_persist_and_forget(store, tmp_path):
    store.set(MAC, name="Porch Cam", type="camera", notes="front door")
    again = LabelStore(tmp_path / "labels.json")          # a fresh process sees it
    assert again.get(MAC)["name"] == "Porch Cam" and again.get(MAC)["type"] == "camera"
    assert again.forget(MAC) and not again.forget(MAC)
    assert LabelStore(tmp_path / "labels.json").all() == {}


def test_partial_updates_and_clearing(store):
    store.set(MAC, name="A", type="camera")
    store.set(MAC, notes="n")                            # omitted fields untouched
    store.set(MAC, name="")                              # empty clears one field
    e = store.get(MAC)
    assert "name" not in e and e["type"] == "camera" and e["notes"] == "n"
    store.set(MAC, type=None, notes=None)                # nothing left -> entry removed
    assert store.get(MAC) is None


def test_invalid_type_is_rejected_and_nothing_saved(store):
    with pytest.raises(ValueError, match="unknown device type"):
        store.set(MAC, type="toaster")
    assert store.all() == {}


def test_corrupt_file_is_quarantined_not_fatal(tmp_path):
    p = tmp_path / "labels.json"
    p.write_text("{ this is not json", encoding="utf-8")
    s = LabelStore(p)
    assert s.all() == {} and list(tmp_path.glob("labels.bad-*"))
    s.set(MAC, name="ok")                                 # and it keeps working
    assert json.loads(p.read_text(encoding="utf-8"))["devices"][MAC]["name"] == "ok"


def test_apply_overrides_and_is_idempotent_and_reversible(store):
    d = make("192.168.1.9", MAC)
    d.vendor = "TP-LINK TECHNOLOGIES CO.,LTD."
    classify.classify(d)
    auto = (d.device_type, d.confidence)
    store.set(MAC, name="Porch Cam", type="camera", notes="front door")
    for _ in range(2):                                    # applying twice must not compound
        store.apply([d])
        assert (d.device_type, d.confidence, d.display_name) == ("camera", 1.0, "Porch Cam")
        assert d.auto_type == auto[0] and d.evidence[0].source == "user"
    snap = d.to_dict()
    assert snap["user"]["auto_type"] == auto[0] and snap["user"]["notes"] == "front door"
    store.forget(MAC)
    store.apply([d])
    assert (d.device_type, d.confidence) == auto and d.user_name is None and d.to_dict()["user"] is None


def test_reclassify_after_a_scan_keeps_the_scanners_own_verdict(store):
    d = make("192.168.1.9", MAC)
    d.vendor = "Ring LLC"
    store.set(MAC, type="smart_plug")
    classify.classify(d)
    store.apply([d])
    assert d.device_type == "smart_plug" and d.auto_type == "doorbell"
    classify.classify(d)                                  # next scan: fresh verdict, then overlay again
    store.apply([d])
    assert d.device_type == "smart_plug" and d.auto_type == "doorbell"


def test_ip_fallback_key_when_no_mac(store):
    d = make("192.168.1.77")
    store.set(labels.key_for(d), name="Mystery box")
    store.apply([d])
    assert labels.key_for(d) == "ip:192.168.1.77" and d.display_name == "Mystery box"


def test_normalize_key_forms():
    assert labels.normalize_key("AA-BB-CC-DD-EE-01") == MAC
    assert labels.normalize_key("ip:10.0.0.5") == "ip:10.0.0.5"
    assert labels.normalize_key("192.168.1.9", {"192.168.1.9": MAC}) == MAC
    with pytest.raises(ValueError, match="ARP table"):
        labels.normalize_key("192.168.1.9", {})
    with pytest.raises(ValueError):
        labels.normalize_key("nonsense")


def test_corrections_show_in_exports(store):
    d = make("192.168.1.9", MAC)
    classify.classify(d)
    store.set(MAC, name="Porch Cam", type="camera", notes="front door, gets <hot>")
    store.apply([d])
    csv = export.render([d], "csv")
    assert "Porch Cam" in csv and "Camera" in csv and "front door" in csv
    html = export.render([d], "html")
    assert "edited · auto:" in html and "&lt;hot&gt;" in html and "<hot>" not in html


def test_suggest_rules_generates_a_valid_loadable_rule(store, tmp_path):
    d = make("192.168.1.9", MAC)
    d.vendor = "Acme Widgets, Inc. (O'Neil)"
    classify.classify(d)
    store.label_device(d, type="pet_feeder")
    other = make("192.168.1.10", "aa:bb:cc:dd:ee:02")
    other.vendor = "Mixed Co"
    store.label_device(other, type="camera")
    store.label_device(make("192.168.1.11", "aa:bb:cc:dd:ee:03", vendor="Mixed Co"), type="light")
    text = labels.suggest_rules(store)
    assert "skipped 'Mixed Co'" in text
    (tmp_path / "vendor.toml").write_text(text, encoding="utf-8")
    try:
        rs = rules_mod.reload(tmp_path)
        assert not rs.errors
        fresh = make("192.168.1.50")
        fresh.vendor = "Acme Widgets, Inc. (O'Neil)"
        assert classify.classify(fresh).device_type == "pet_feeder"
    finally:
        rules_mod.reload(tmp_path / "nope")


def test_cli_label_list_forget_and_types(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LANWHODIS_HOME", str(tmp_path))
    assert cli.main(["--label", MAC, "--set-type", "camera", "--set-name", "Porch Cam", "--set-notes", "front"]) == 0
    assert cli.main(["--label", MAC]) == 2                           # needs something to set
    assert cli.main(["--label", MAC, "--set-type", "toaster"]) == 2   # invalid type rejected
    capsys.readouterr()
    assert cli.main(["--list-labels"]) == 0
    out = capsys.readouterr().out
    assert MAC in out and "Porch Cam" in out and "camera" in out and "# front" in out
    assert cli.main(["--list-types"]) == 0 and "thermostat" in capsys.readouterr().out
    assert cli.main(["--suggest-rules"]) == 0
    assert cli.main(["--forget", MAC]) == 0 and "forgot" in capsys.readouterr().out
    assert LabelStore().all() == {}
