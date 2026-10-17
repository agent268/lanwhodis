"""Declarative rules: packaged rules validate, user rules add/override, bad user rules are skipped."""
import pytest

from lanwhodis import classify, rules as rules_mod
from test_core import make, os_of


@pytest.fixture
def user_rules(tmp_path):
    """Point the rule loader at a temp user dir; restore the packaged rules afterwards."""
    def apply(files: dict[str, str]):
        for name, body in files.items():
            (tmp_path / name).write_text(body, encoding="utf-8")
        return rules_mod.reload(tmp_path)
    yield apply
    rules_mod.reload(tmp_path / "does-not-exist")


def test_user_rule_adds_a_vendor_match(user_rules):
    d = make()
    d.vendor = "Acme Widgets Ltd"
    assert classify.classify(d).device_type == "unknown"
    user_rules({"vendor.toml": '[[rule]]\nmatch = "acme widgets"\nvotes = { pet_feeder = 0.9 }\n'})
    assert classify.classify(d).device_type == "pet_feeder"


def test_user_service_and_port_rules_override_packaged(user_rules):
    user_rules({"services.toml": '[services]\n"mdns:_ipp._tcp" = { camera = 0.99 }\n',
                "ports.toml": '[ports]\n"9100" = {}\n'})
    d = make()
    d.services.add("mdns:_ipp._tcp")
    d.open_ports.add(9100)
    assert classify.classify(d).device_type == "camera"
    assert rules_mod.get().ports[9100] == {}


def test_bad_user_rules_are_reported_and_skipped_not_fatal(user_rules):
    rs = user_rules({
        "vendor.toml": ('[[rule]]\nmatch = "([unclosed"\nvotes = { camera = 0.5 }\n\n'
                        '[[rule]]\nmatch = "ok"\nvotes = { not_a_type = 0.5 }\n\n'
                        '[[rule]]\nmatch = "fine"\nvotes = { camera = 7 }\n\n'
                        '[[rule]]\nmatch = "good one"\nvotes = { camera = 0.5 }\n'),
        "names.toml": "this is = not [valid toml",
    })
    assert len(rs.errors) == 4
    assert any("bad regex" in e for e in rs.errors)
    assert any("unknown device type" in e for e in rs.errors)
    assert any("between 0 and 1" in e for e in rs.errors)
    d = make()
    d.vendor = "A Good One Inc"
    assert classify.classify(d).device_type == "camera"       # the valid rule still loaded


def test_user_os_rule_with_capture_group(user_rules):
    user_rules({"os.toml": "[[text]]\nmatch = 'acmeos (\\d+)'\nfamily = \"AcmeOS\"\ndetail = 'v\\1'\nweight = 0.9\n"})
    d = os_of(text=["Server: AcmeOS 7"])
    assert (d.os_hint, d.os_detail) == ("AcmeOS", "v7")
