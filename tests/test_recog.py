"""Rapid7 Recog integration: bundled databases load cleanly, matching resolves params, results feed
the OS and device-type classifiers."""
from lanwhodis import classify, osdetect, recog
from test_core import make


def test_all_bundled_databases_load_without_skips():
    for key in recog._FILES:
        db = recog.database(key)
        assert db.prints, key
        assert db.skipped == 0, f"{key}: {db.skipped} patterns Python's re could not compile"


def test_ssh_banner_prefix_is_stripped_and_params_resolve():
    d = make()
    d.facts["ssh_banner"] = "SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u5"
    recog.annotate(d)
    m = d.recog[0]
    assert m.db == "ssh.banner" and m.params["service.version"] == "9.2p1" and m.params["os.vendor"] == "Debian"


def test_literal_and_group_params_and_interpolation():
    m = recog.match("http_header.server", "lighttpd/1.4.55")
    assert m.params["service.product"] == "lighttpd" and m.params["service.version"] == "1.4.55"
    assert m.params["service.cpe23"].endswith(":1.4.55")        # {service.version} interpolated


def test_apple_model_in_mdns_device_info_identifies_a_laptop():
    d = make()
    d.facts["device_info_txt"] = "model=MacBookPro18,3|osxvers=22"
    recog.annotate(d)
    classify.classify(d)
    assert d.device_type == "laptop" and d.os_hint == "macOS"
    assert d.model == "MacBook Pro (14-Inch, M1, 2021)"


def test_recog_os_feeds_os_detection_with_distro_detail():
    d = make()
    d.facts["ssh_banner"] = "SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u5"
    recog.annotate(d)
    osdetect.detect(d)
    assert d.os_hint == "Linux" and d.os_detail and d.os_detail.startswith("Debian")


def test_recog_hw_device_votes_for_type():
    d = make()
    d.facts["http80_title"] = "hue personal wireless lighting"     # the bridge's literal (lowercase) title
    recog.annotate(d)
    ev = classify.gather(d)
    assert any(e.source == "recog" and e.device_type == "light" for e in ev)


def test_annotate_is_idempotent_and_unknown_banners_match_nothing():
    d = make()
    d.facts["ssh_banner"] = "SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u5"
    d.facts["http80_server"] = "totally-made-up-server/0.0"
    recog.annotate(d)
    recog.annotate(d)
    assert len(d.recog) == 1
    assert recog.match("ssh.banner", "") is None and recog.match("nope", "x") is None


def test_os_family_map_applied_for_mac_os_x():
    from lanwhodis import rules
    m = recog.match("mdns.device-info.txt", "osxvers=22")
    assert recog.os_family_and_detail(m, rules.get().recog_os)[0] == "macOS"
