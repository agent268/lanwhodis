"""Data directory selection and the one-time migration from the project's old name (netscout)."""
from lanwhodis import paths


def test_home_override_and_legacy_alias(tmp_path, monkeypatch):
    monkeypatch.delenv("LANWHODIS_HOME", raising=False)
    monkeypatch.setenv("NETSCOUT_HOME", str(tmp_path / "old-style"))
    assert paths.data_dir() == tmp_path / "old-style"                 # legacy variable still honoured
    monkeypatch.setenv("LANWHODIS_HOME", str(tmp_path / "new-style"))
    assert paths.data_dir() == tmp_path / "new-style"                 # and the new one wins


def test_old_data_dir_is_moved_once(tmp_path, monkeypatch):
    for var in ("LANWHODIS_HOME", "NETSCOUT_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(paths, "_base", lambda: tmp_path)
    old = tmp_path / "netscout"
    (old / "rules").mkdir(parents=True)
    (old / "labels.json").write_text('{"version": 1, "devices": {}}', encoding="utf-8")
    new = paths.data_dir()
    assert new == tmp_path / "lanwhodis" and (new / "labels.json").is_file() and (new / "rules").is_dir()
    assert not old.exists()
    assert paths.data_dir() == new                                    # second call: nothing to move


def test_existing_new_dir_is_never_overwritten(tmp_path, monkeypatch):
    for var in ("LANWHODIS_HOME", "NETSCOUT_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(paths, "_base", lambda: tmp_path)
    (tmp_path / "netscout").mkdir()
    (tmp_path / "netscout" / "labels.json").write_text("old", encoding="utf-8")
    (tmp_path / "lanwhodis").mkdir()
    (tmp_path / "lanwhodis" / "labels.json").write_text("new", encoding="utf-8")
    assert (paths.data_dir() / "labels.json").read_text(encoding="utf-8") == "new"
    assert (tmp_path / "netscout" / "labels.json").read_text(encoding="utf-8") == "old"     # left alone


def test_fresh_install_uses_new_name_and_creates_nothing(tmp_path, monkeypatch):
    for var in ("LANWHODIS_HOME", "NETSCOUT_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(paths, "_base", lambda: tmp_path)
    assert paths.data_dir() == tmp_path / "lanwhodis" and not (tmp_path / "lanwhodis").exists()
