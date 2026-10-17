"""Presence history: baselines, debounced leaving, returning, IP moves, network scoping, retention."""
import pytest

from lanwhodis import history
from lanwhodis.history import History
from test_core import make

NET_A, NET_B = "192.168.1.0/24", "10.0.0.0/24"
DAY = 86400


@pytest.fixture
def hist(tmp_path):
    return History(tmp_path / "history.db")


def dev(ip, mac, name=None):
    d = make(ip, mac)
    if name:
        d.hostname = name
    return d


def test_first_scan_is_a_silent_baseline(hist):
    d1, d2 = dev("192.168.1.2", "aa:00:00:00:00:01", "tv"), dev("192.168.1.3", "aa:00:00:00:00:02", "pc")
    diff = hist.record([d1, d2], [NET_A], now=1000)
    assert diff.baseline_networks == [NET_A] and not diff.new and not diff.changed
    assert d1.history["status"] == "known" and d1.history["seen_count"] == 1
    assert hist.events() == [] and len(hist.known()) == 2
    assert diff.summary_lines() == [f"first scan of {NET_A} recorded as the baseline"]


def test_new_device_after_baseline_is_reported_once(hist):
    a = dev("192.168.1.2", "aa:00:00:00:00:01")
    hist.record([a], [NET_A], now=1000)
    b = dev("192.168.1.9", "aa:00:00:00:00:09", "newphone")
    diff = hist.record([a, b], [NET_A], now=2000)
    assert [d.mac for d in diff.new] == ["aa:00:00:00:00:09"] and b.history["status"] == "new"
    assert hist.events()[0].kind == "new"
    again = hist.record([a, b], [NET_A], now=3000)
    assert not again.new and b.history["status"] == "known" and b.history["seen_count"] == 2
    assert b.history["first_seen"] == 2000


def test_leaving_is_debounced_and_returning_is_reported(hist):
    a, b = dev("192.168.1.2", "aa:00:00:00:00:01"), dev("192.168.1.3", "aa:00:00:00:00:02", "nas")
    hist.record([a, b], [NET_A], now=1000)
    d2 = hist.record([a], [NET_A], now=2000)                    # b missed once: could just be napping
    assert not d2.left and not hist.events()
    d3 = hist.record([a], [NET_A], now=3000)                    # missed twice: gone
    assert [k.mac for k in d3.left] == ["aa:00:00:00:00:02"] and hist.events()[0].kind == "left"
    d4 = hist.record([a], [NET_A], now=4000)                    # still gone: not announced again
    assert not d4.left
    assert [k.mac for k in hist.offline([NET_A], {"aa:00:00:00:00:01"})] == ["aa:00:00:00:00:02"]
    back = dev("192.168.1.3", "aa:00:00:00:00:02", "nas")
    d5 = hist.record([a, back], [NET_A], now=5000)
    assert [d.mac for d in d5.returned] == ["aa:00:00:00:00:02"] and back.history["status"] == "returned"
    assert hist.offline([NET_A], {"aa:00:00:00:00:01", "aa:00:00:00:00:02"}) == []


def test_a_nap_of_one_scan_is_not_an_event(hist):
    a, b = dev("192.168.1.2", "aa:00:00:00:00:01"), dev("192.168.1.3", "aa:00:00:00:00:02")
    hist.record([a, b], [NET_A], now=1000)
    hist.record([a], [NET_A], now=2000)
    diff = hist.record([a, b], [NET_A], now=3000)
    assert not diff.changed and b.history["status"] == "known" and hist.events() == []


def test_ip_change_is_reported_and_stored(hist):
    hist.record([dev("192.168.1.20", "aa:00:00:00:00:05", "cam")], [NET_A], now=1000)
    moved = dev("192.168.1.77", "aa:00:00:00:00:05", "cam")
    diff = hist.record([moved], [NET_A], now=2000)
    assert diff.moved == [(moved, "192.168.1.20")] and moved.history["previous_ip"] == "192.168.1.20"
    assert "192.168.1.20 -> 192.168.1.77" in hist.events()[0].detail
    assert hist.known()[0].last_ip == "192.168.1.77"


def test_networks_are_tracked_independently(hist):
    a = dev("192.168.1.2", "aa:00:00:00:00:01")
    b = dev("10.0.0.5", "bb:00:00:00:00:01")
    hist.record([a, b], [NET_A, NET_B], now=1000)
    for t in (2000, 3000, 4000):                               # scanning only B must not age out A's devices
        hist.record([b], [NET_B], now=t)
    assert all(k.missed == 0 for k in hist.known() if k.mac == a.mac)
    new_b = dev("10.0.0.9", "bb:00:00:00:00:09")
    assert hist.record([b, new_b], [NET_B], now=5000).new == [new_b]
    fresh = dev("172.16.0.4", "cc:00:00:00:00:01")             # a network we have never scanned: baseline
    diff = hist.record([fresh], ["172.16.0.0/24"], now=6000)
    assert not diff.new and diff.baseline_networks == ["172.16.0.0/24"]


def test_device_without_mac_is_keyed_by_ip(hist):
    d = dev("192.168.1.50", None)
    hist.record([d], [NET_A], now=1000)
    assert hist.known()[0].key == "ip:192.168.1.50"


def test_old_data_is_pruned(hist):
    hist.record([dev("192.168.1.2", "aa:00:00:00:00:01")], [NET_A], now=1000)
    later = 1000 + (history.RETENTION_DAYS + 5) * DAY
    hist.record([dev("192.168.1.3", "aa:00:00:00:00:02")], [NET_A], now=later)
    assert [k.mac for k in hist.known()] == ["aa:00:00:00:00:02"] and hist.scan_count() == 1


def test_corrupt_database_is_quarantined(tmp_path):
    p = tmp_path / "history.db"
    p.write_bytes(b"this is not a sqlite database" * 100)
    h = History(p)
    assert list(tmp_path.glob("history.bad-*"))
    assert not h.record([dev("192.168.1.2", "aa:00:00:00:00:01")], [NET_A]).changed


def test_summary_lines_and_clear(hist):
    a = dev("192.168.1.2", "aa:00:00:00:00:01")
    hist.record([a], [NET_A], now=1000)
    new = dev("192.168.1.9", "aa:00:00:00:00:09", "newphone")
    lines = hist.record([a, new], [NET_A], now=2000).summary_lines()
    assert lines[0].startswith("NEW") and "192.168.1.9" in lines[0] and "newphone" in lines[0]
    hist.clear()
    assert hist.known() == [] and hist.events() == [] and hist.scan_count() == 0


# --- CLI / export integration ------------------------------------------------------------
def test_cli_known_events_and_forget(tmp_path, monkeypatch, capsys):
    from lanwhodis import cli
    monkeypatch.setenv("LANWHODIS_HOME", str(tmp_path))
    h = History()
    a = dev("192.168.1.2", "aa:00:00:00:00:01", "tv")
    h.record([a], [NET_A], now=1000)
    h.record([a, dev("192.168.1.9", "aa:00:00:00:00:09", "phone")], [NET_A], now=2000)
    assert cli.main(["--known"]) == 0
    out = capsys.readouterr().out
    assert "192.168.1.9" in out and "online" in out and "seen 1x" in out
    assert cli.main(["--events"]) == 0 and "NEW" in capsys.readouterr().out
    assert cli.main(["--events", "1"]) == 0
    assert cli.main(["--forget-history"]) == 0 and "cleared" in capsys.readouterr().out
    assert cli.main(["--known"]) == 0 and "no devices recorded" in capsys.readouterr().out


def test_cli_record_skips_cancelled_and_disabled_scans(tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace
    from lanwhodis import cli
    from lanwhodis.discovery.base import Iface
    import ipaddress
    monkeypatch.setenv("LANWHODIS_HOME", str(tmp_path))
    ifaces = [Iface("eth0", "192.168.1.5", ipaddress.ip_network(NET_A))]
    devices = [dev("192.168.1.2", "aa:00:00:00:00:01")]
    stopped = threading.Event()
    stopped.set()
    assert cli._record(devices, ifaces, SimpleNamespace(no_history=False), stopped) is None   # partial scan
    assert cli._record(devices, ifaces, SimpleNamespace(no_history=True), threading.Event()) is None
    assert History().scan_count() == 0
    diff = cli._record(devices, ifaces, SimpleNamespace(no_history=False), threading.Event())
    assert diff.baseline_networks == [NET_A] and History().scan_count() == 1


def test_first_seen_column_in_exports(hist):
    from lanwhodis import export
    d = dev("192.168.1.2", "aa:00:00:00:00:01")
    hist.record([d], [NET_A], now=1_700_000_000)
    csv = export.render([d], "csv")
    assert csv.splitlines()[0].endswith("First seen") and "2023-11-1" in csv.splitlines()[1]
    plain = dev("192.168.1.3", "aa:00:00:00:00:02")          # never recorded: blank, not an error
    assert export.render([plain], "csv").splitlines()[1].endswith(",")
