"""Bridge between the Qt Quick UI and the LanWhodis core. QML renders; everything with logic lives here.

* ``DeviceModel`` / ``DeviceFilter``: the device list (live while scanning) with search, category and
  status filtering.
* ``Backend``: scan control, selection + the detail panel's content, corrections, history, export,
  theme/zoom settings.
"""
from __future__ import annotations

import html
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from PySide6.QtCore import (Property, QAbstractListModel, QModelIndex, QObject, QSortFilterProxyModel, Qt,
                            QThread, QTimer, QUrl, Signal, Slot)
from PySide6.QtGui import QDesktopServices, QGuiApplication

from .. import classify, devtypes, export, history, icons, paths, scanner
from ..discovery import net
from ..labels import LabelStore, key_for
from ..model import Device

CATEGORIES = list(icons.CATEGORY_COLOR)       # Computers, Mobile, Media, Gaming, Smart Home, ...
CATEGORY_ICON = {"Computers": "device_computer", "Mobile": "device_phone", "Media": "device_tv",
                 "Gaming": "device_game_console", "Smart Home": "ui_home", "Peripherals": "device_printer",
                 "Network": "device_router", "Other": "device_unknown"}
_ROLES = ["sid", "name", "ip", "ipKey", "mac", "typeKey", "typeLabel", "category", "color", "iconName", "vendor",
          "os", "confidence", "status", "edited", "offline", "webUrl", "subtitle", "search", "labelDark", "labelLight"]


def _ago(ts: float) -> str:
    secs = max(0, int(time.time() - ts))
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if secs >= size:
            n = secs // size
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"


def _date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def offline_snapshot(k: history.KnownDevice) -> dict:
    """A snapshot (same shape as Device.to_dict) for a remembered device that didn't answer this scan."""
    return {"sid": f"offline:{k.key}", "offline": True, "ip": k.last_ip, "mac": k.mac, "name": k.name,
            "hostname": None, "vendor": k.vendor, "model": None, "type": k.type,
            "type_label": devtypes.label(k.type), "category": devtypes.category(k.type), "confidence": 0.0,
            "os": k.os or "", "os_confidence": 0.0, "os_evidence": [], "web_url": None, "web_urls": [],
            "advertised": [], "recog": [], "user": None, "open_ports": [], "services": [], "names": {},
            "facts": {}, "evidence": [],
            "history": {"status": "offline", "first_seen": k.first_seen, "last_seen": k.last_seen,
                        "seen_count": k.seen_count, "missed": k.missed}}


def row_from_snapshot(snap: dict) -> dict:
    sid = snap.setdefault("sid", snap["ip"])
    offline = bool(snap.get("offline"))
    user = snap.get("user")
    hist = snap.get("history") or {}
    status = "offline" if offline else (hist.get("status") if hist.get("status") in ("new", "returned") else "")
    typ = snap["type"]
    label_dark, label_light = icons.label_colors(typ)
    try:
        a, b, c, d = (int(p) for p in snap["ip"].split("."))
        ip_key = (a << 24) | (b << 16) | (c << 8) | d
    except ValueError:
        ip_key = 0
    vendor = snap.get("vendor") or ""
    detail = vendor if vendor and vendor != snap["name"] else (snap.get("os") or "")
    return {"sid": sid, "name": snap["name"], "ip": snap["ip"], "ipKey": ip_key, "mac": snap.get("mac") or "",
            "typeKey": typ, "typeLabel": snap["type_label"], "category": snap.get("category", "Other"),
            "color": icons.color(typ), "iconName": f"device_{typ}", "vendor": vendor, "os": snap.get("os") or "",
            "confidence": 0.0 if offline else float(snap.get("confidence", 0.0)), "status": status,
            "edited": bool(user and user.get("type")), "offline": offline, "webUrl": snap.get("web_url") or "",
            "subtitle": f"{snap['type_label']} · {detail}" if detail else snap["type_label"],
            "labelDark": label_dark, "labelLight": label_light,
            "search": " ".join([snap["name"], snap["ip"], snap.get("mac") or "", vendor, snap["type_label"],
                                snap.get("os") or "", snap.get("model") or ""]).lower()}


class DeviceModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []
        self._index: dict[str, int] = {}

    def roleNames(self) -> dict:                   # noqa: N802 (Qt API)
        return {Qt.ItemDataRole.UserRole + 1 + i: n.encode() for i, n in enumerate(_ROLES)}

    def rowCount(self, parent=QModelIndex()) -> int:   # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        i = role - (Qt.ItemDataRole.UserRole + 1)
        return self._rows[index.row()].get(_ROLES[i]) if 0 <= i < len(_ROLES) else None

    def upsert(self, row: dict) -> None:
        at = self._index.get(row["sid"])
        if at is None:
            self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows))
            self._index[row["sid"]] = len(self._rows)
            self._rows.append(row)
            self.endInsertRows()
        else:
            self._rows[at] = row
            self.dataChanged.emit(self.index(at), self.index(at))

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self._index.clear()
        self.endResetModel()

    def rows(self) -> list[dict]:
        return self._rows


class DeviceFilter(QSortFilterProxyModel):
    """Search + category + status filtering, sorted by IP (or name / type)."""

    def __init__(self, source: DeviceModel) -> None:
        super().__init__(source)
        self.setSourceModel(source)
        self.setDynamicSortFilter(True)
        self._search, self._category, self._show_offline, self._status = "", "", True, ""
        self.set_sort("ip")

    def set_sort(self, key: str) -> None:
        role = {"ip": "ipKey", "name": "name", "type": "typeLabel"}.get(key, "ipKey")
        self.setSortRole(Qt.ItemDataRole.UserRole + 1 + _ROLES.index(role))
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.sort(0)

    def configure(self, search=None, category=None, show_offline=None, status=None) -> None:
        begin = getattr(self, "beginFilterChange", None)     # Qt >= 6.9; invalidateFilter() is deprecated since 6.10
        if begin:
            begin()
        if search is not None:
            self._search = search.strip().lower()
        if category is not None:
            self._category = category
        if show_offline is not None:
            self._show_offline = show_offline
        if status is not None:
            self._status = status
        (getattr(self, "endFilterChange", None) or self.invalidateFilter)()

    def filterAcceptsRow(self, row: int, parent) -> bool:   # noqa: N802 (Qt API)
        r = self.sourceModel().rows()[row]
        if r["offline"] and not self._show_offline and self._status != "offline":
            return False
        if self._category and r["category"] != self._category:
            return False
        if self._status == "new" and r["status"] not in ("new", "returned"):
            return False                                     # "new or back"
        if self._status and self._status != "new" and r["status"] != self._status:
            return False
        return not self._search or self._search in r["search"]


class ScanWorker(QObject):
    updated = Signal(dict)          # snapshot of a device as it is discovered
    log = Signal(str)
    progress = Signal(str, float)
    finished = Signal(list, str)    # devices, error ('' on success)

    def __init__(self, ifaces, labels: LabelStore) -> None:
        super().__init__()
        self.ifaces, self.labels = ifaces, labels
        self.stop = threading.Event()

    @Slot()
    def run(self) -> None:
        def on_update(d: Device) -> None:
            try:   # discovery threads mutate devices concurrently; skip a torn snapshot
                classify.classify(d)
                self.labels.apply([d])
                self.updated.emit(d.to_dict())
            except RuntimeError:
                pass

        try:
            devices = scanner.scan(self.ifaces, stop=self.stop, on_update=on_update, labels=self.labels,
                                   log=self.log.emit, progress=self.progress.emit)
            self.finished.emit(devices, "")
        except Exception as e:                  # surface it in the UI instead of dying silently
            self.finished.emit([], f"{type(e).__name__}: {e}")


def _settings_path() -> Path:
    return paths.data_dir() / "settings.json"


class Backend(QObject):
    scanningChanged = Signal()
    progressChanged = Signal()
    statusChanged = Signal()
    countsChanged = Signal()
    currentChanged = Signal()
    interfacesChanged = Signal()
    themeChanged = Signal()
    reduceMotionChanged = Signal()
    zoomChanged = Signal()
    filtersChanged = Signal()
    toast = Signal(str)
    editRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.labels = LabelStore()
        self._model = DeviceModel(self)
        self._proxy = DeviceFilter(self._model)
        self._snaps: dict[str, dict] = {}
        self._devices: list[Device] = []
        self._scanned: list = []
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None
        self._scanning, self._progress, self._status = False, 0.0, "Ready when you are."
        self._selected = ""
        self._current: dict = {}
        self._category, self._search, self._status_filter, self._show_offline = "", "", "", True
        self._view = "grid"
        self._ifaces = net.list_interfaces()
        self._iface_index = 0
        self._ever_scanned = False
        s = self._load_settings()
        self._theme = s.get("theme") or ("deck" if os.environ.get("SteamDeck") == "1" else "dark")
        self._zoom = float(s.get("zoom", 1.0))
        self._view = s.get("view", "grid")
        self._reduce_motion = self._os_reduces_motion()
        # keep the Qt objects referenced: PySide frees the C++ child when its parent wrapper is collected
        self._style_hints = QGuiApplication.styleHints() if QGuiApplication.instance() else None
        self._a11y_hints = self._style_hints.accessibility() if self._style_hints is not None else None
        if self._a11y_hints is not None and hasattr(self._a11y_hints, "motionPreferenceChanged"):
            self._a11y_hints.motionPreferenceChanged.connect(self._motion_changed)
        self._counts_timer = QTimer(self, singleShot=True, interval=120)
        self._counts_timer.timeout.connect(self._emit_counts)

    # ---- settings ------------------------------------------------------------------------
    @staticmethod
    def _load_settings() -> dict:
        try:
            return json.loads(_settings_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        try:
            paths.ensure(_settings_path().parent)
            _settings_path().write_text(json.dumps({"theme": self._theme, "zoom": self._zoom, "view": self._view}),
                                        encoding="utf-8")
        except OSError:
            pass

    # ---- reduced motion ------------------------------------------------------------------
    @staticmethod
    def _os_reduces_motion() -> bool:
        if os.environ.get("LANWHODIS_REDUCE_MOTION") == "1":
            return True
        if QGuiApplication.instance() is None:
            return False
        style_hints = QGuiApplication.styleHints()          # hold it: the accessibility object is its child
        hints = style_hints.accessibility()
        try:
            return hints.motionPreference() == Qt.MotionPreference.ReducedMotion
        except AttributeError:                              # Qt older than 6.10 has no motion preference
            return False

    def _motion_changed(self, *_) -> None:
        self._reduce_motion = self._os_reduces_motion()
        self.reduceMotionChanged.emit()

    @Property(bool, notify=reduceMotionChanged)
    def reduceMotion(self) -> bool:
        return self._reduce_motion

    # ---- properties ----------------------------------------------------------------------
    @Property(QObject, constant=True)
    def devices(self) -> QObject:
        return self._proxy

    @Property(bool, notify=scanningChanged)
    def scanning(self) -> bool:
        return self._scanning

    @Property(float, notify=progressChanged)
    def progress(self) -> float:
        return self._progress

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=countsChanged)
    def hasDevices(self) -> bool:
        return bool(self._snaps)

    @Property("QVariantList", notify=countsChanged)
    def categories(self) -> list:
        rows = [r for r in self._model.rows() if self._show_offline or not r["offline"]]
        out = [{"key": "", "label": "All devices", "icon": "ui_apps", "color": "", "labelDark": "", "labelLight": "",
                "count": len(rows)}]
        for c in CATEGORIES:
            n = sum(1 for r in rows if r["category"] == c)
            if n:
                out.append({"key": c, "label": c, "icon": CATEGORY_ICON.get(c, "device_unknown"),
                            "color": icons.CATEGORY_COLOR[c], "labelDark": icons.CATEGORY_LABEL_DARK.get(c, icons.CATEGORY_COLOR[c]),
                            "labelLight": icons.CATEGORY_LABEL_LIGHT.get(c, icons.CATEGORY_COLOR[c]), "count": n})
        return out

    @Property("QVariantMap", notify=countsChanged)
    def statusCounts(self) -> dict:
        rows = self._model.rows()
        return {"new": sum(1 for r in rows if r["status"] in ("new", "returned")),
                "offline": sum(1 for r in rows if r["offline"]),
                "online": sum(1 for r in rows if not r["offline"])}

    @Property("QVariantMap", notify=currentChanged)
    def current(self) -> dict:
        return self._current

    @Property("QVariantList", notify=interfacesChanged)
    def interfaceLabels(self) -> list:
        labels = [i.label for i in self._ifaces]
        return (["All networks"] + labels) if len(labels) > 1 else labels

    @Property(int, notify=interfacesChanged)
    def interfaceIndex(self) -> int:
        return self._iface_index

    @interfaceIndex.setter
    def interfaceIndex(self, v: int) -> None:
        if v != self._iface_index:
            self._iface_index = v
            self.interfacesChanged.emit()

    @Property(str, notify=themeChanged)
    def theme(self) -> str:
        return self._theme

    @theme.setter
    def theme(self, v: str) -> None:
        if v in ("dark", "light", "deck") and v != self._theme:
            self._theme = v
            self._save_settings()
            self.themeChanged.emit()

    @Property(float, notify=zoomChanged)
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, v: float) -> None:
        v = max(0.7, min(1.8, round(v, 2)))
        if v != self._zoom:
            self._zoom = v
            self._save_settings()
            self.zoomChanged.emit()

    @Property(str, notify=filtersChanged)
    def view(self) -> str:
        return self._view

    @view.setter
    def view(self, v: str) -> None:
        if v in ("grid", "list") and v != self._view:
            self._view = v
            self._save_settings()
            self.filtersChanged.emit()

    @Property(str, notify=filtersChanged)
    def category(self) -> str:
        return self._category

    @Property(str, notify=filtersChanged)
    def statusFilter(self) -> str:
        return self._status_filter

    @Property(bool, notify=filtersChanged)
    def showOffline(self) -> bool:
        return self._show_offline

    @Property("QVariantList", constant=True)
    def deviceTypes(self) -> list:
        return [{"key": k, "label": v[0], "category": v[1], "icon": f"device_{k}", "color": icons.color(k),
                 "labelDark": icons.label_colors(k)[0], "labelLight": icons.label_colors(k)[1]}
                for k, v in sorted(devtypes.TYPES.items(), key=lambda kv: (CATEGORIES.index(kv[1][1]), kv[1][0]))
                if k != "unknown"]

    @Property(str, constant=True)
    def dataDir(self) -> str:
        return str(paths.data_dir())

    # ---- filtering -----------------------------------------------------------------------
    @Slot(str)
    def setSearch(self, text: str) -> None:
        self._search = text
        self._proxy.configure(search=text)

    @Slot(str)
    def setCategory(self, key: str) -> None:
        self._category = key
        self._proxy.configure(category=key)
        self.filtersChanged.emit()

    @Slot(str)
    def setStatusFilter(self, key: str) -> None:
        self._status_filter = "" if key == self._status_filter else key
        self._proxy.configure(status=self._status_filter)
        self.filtersChanged.emit()

    @Slot(bool)
    def setShowOffline(self, on: bool) -> None:
        self._show_offline = on
        self._proxy.configure(show_offline=on)
        self.filtersChanged.emit()
        self.countsChanged.emit()

    @Slot(str)
    def setSort(self, key: str) -> None:
        self._proxy.set_sort(key)

    @Slot()
    def cycleTheme(self) -> None:
        order = ["dark", "light", "deck"]
        self.theme = order[(order.index(self._theme) + 1) % len(order)]

    # ---- scanning ------------------------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self._status = text
        self.statusChanged.emit()

    @Slot()
    def toggleScan(self) -> None:
        if self._scanning:
            self.stopScan()
        else:
            self.startScan()

    @Slot()
    def startScan(self) -> None:
        if self._scanning or not self._ifaces:
            if not self._ifaces:
                self._set_status("No active IPv4 network found - connect to Wi-Fi or Ethernet.")
            return
        if len(self._ifaces) > 1 and self._iface_index == 0:
            ifaces = self._ifaces
        else:
            ifaces = [self._ifaces[self._iface_index - (1 if len(self._ifaces) > 1 else 0)]]
        self._model.clear()
        self._snaps.clear()
        self._devices = []
        self._select("")
        self._scanned = ifaces
        self._ever_scanned = True
        self._scanning, self._progress = True, 0.0
        self.scanningChanged.emit()
        self.progressChanged.emit()
        self._set_status("Scanning " + ", ".join(str(i.network) for i in ifaces) + " …")
        self._emit_counts()

        self._thread = QThread()
        self._worker = ScanWorker(ifaces, self.labels)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.updated.connect(self._on_snapshot)
        self._worker.log.connect(self._set_status)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    @Slot()
    def stopScan(self) -> None:
        if self._worker:
            self._worker.stop.set()
        self._set_status("Stopping …")

    def _on_progress(self, stage: str, frac: float) -> None:
        self._progress = min(1.0, {"sweep": 0.0, "ports": 0.5}.get(stage, 0.0) + 0.5 * frac)
        self.progressChanged.emit()

    def _on_snapshot(self, snap: dict) -> None:
        row = row_from_snapshot(snap)
        self._snaps[row["sid"]] = snap
        self._model.upsert(row)
        if row["sid"] == self._selected:
            self._refresh_current()
        self._counts_timer.start()

    def _emit_counts(self) -> None:
        self.countsChanged.emit()

    def _on_finished(self, devices: list, error: str) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        stopped = bool(self._worker and self._worker.stop.is_set())
        self._thread = None
        self._devices = devices
        for d in devices:                       # final, fully-enriched classification
            self._on_snapshot(d.to_dict())
        suffix = "" if error else self._record_history(devices, stopped)
        self._scanning = False
        self.scanningChanged.emit()
        self._emit_counts()
        self._set_status(f"Scan failed: {error}" if error else f"{len(devices)} devices found{suffix}")

    def _record_history(self, devices: list[Device], stopped: bool) -> str:
        if stopped:
            return " (stopped - not recorded in history)"
        nets = [str(i.network) for i in self._scanned]
        try:
            h = history.History()
            diff = h.record(devices, nets)
            offline = h.offline(nets, {key_for(d) for d in devices})
        except (sqlite3.Error, OSError) as e:
            return f" (history unavailable: {e})"
        for d in devices:                       # refresh rows: they now carry history
            self._on_snapshot(d.to_dict())
        for k in offline:
            self._on_snapshot(offline_snapshot(k))
        bits = []
        for n, word in ((len(diff.new), "new"), (len(diff.returned), "returned"), (len(diff.moved), "moved"),
                        (len(diff.left), "left")):
            if n:
                bits.append(f"{n} {word}")
        if diff.baseline_networks:
            bits.append("baseline recorded")
        return " · " + ", ".join(bits) if bits else ""

    # ---- selection + detail --------------------------------------------------------------
    @Slot(str)
    def select(self, sid: str) -> None:
        self._select(sid)

    def _select(self, sid: str) -> None:
        self._selected = sid
        self._refresh_current()

    def _refresh_current(self) -> None:
        snap = self._snaps.get(self._selected)
        self._current = self._detail(snap) if snap else {}
        self.currentChanged.emit()

    def _detail(self, snap: dict) -> dict:
        offline = bool(snap.get("offline"))
        user = snap.get("user") or {}
        h = snap.get("history") or {}
        typ = snap["type"]
        if offline:
            hist = (f"Offline - last seen {_ago(h['last_seen'])}; missed {h['missed']} scan"
                    f"{'s' if h['missed'] != 1 else ''}. First seen {_date(h['first_seen'])}, seen in "
                    f"{h['seen_count']} scans.")
        elif h.get("status") == "new":
            hist = "New device: first time it has been seen on this network."
        elif h.get("first_seen"):
            hist = (("Returned after being away. " if h.get("status") == "returned" else "")
                    + f"First seen {_date(h['first_seen'])}, seen in {h['seen_count']} scans"
                    + (f"; previously at {h['previous_ip']}" if h.get("previous_ip") else "") + ".")
        else:
            hist = ""

        def rows(*pairs) -> list:
            return [{"k": k, "v": str(v)} for k, v in pairs if v]

        facts = [(k.replace("_", " "), v) for k, v in snap["facts"].items() if not k.startswith("mdns:")]
        general = rows(("IP address", snap["ip"]), ("MAC address", snap["mac"]), ("Vendor", snap["vendor"]),
                       ("Model", snap["model"]), ("Hostname", snap["hostname"]),
                       ("Operating system", snap["os"] and f"{snap['os']} ({int(snap['os_confidence'] * 100)}%)"),
                       ("Open ports", ", ".join(map(str, snap["open_ports"]))))
        names = rows(*[(f"Name via {k}", v) for k, v in snap["names"].items()])
        sections = [{"title": "GENERAL", "rows": general}]
        if names or facts:
            sections.append({"title": "MORE DETAILS", "rows": names + rows(*facts)})
        groups = [{"title": label, "items": [export.service_line(s) for s in items]}
                  for label, items in export.grouped_services(snap)]
        if groups:
            sections.append({"title": f"ADVERTISED SERVICES ({len(snap['advertised'])})", "groups": groups})
        seen, ev = set(), []
        for x in snap["evidence"]:
            key = (x["source"], x["device_type"], str(x["detail"]).lower())
            if key not in seen:
                seen.add(key)
                ev.append({"source": x["source"], "text": f"{devtypes.label(x['device_type'])} - {x['detail']}",
                           "weight": float(x["weight"])})
        for x in snap["os_evidence"]:
            key = ("os:" + x["source"], x["device_type"], str(x["detail"]).lower())
            if key not in seen:
                seen.add(key)
                ev.append({"source": "os/" + x["source"], "text": f"{x['device_type']} - {x['detail']}",
                           "weight": float(x["weight"])})
        if ev:
            sections.append({"title": "WHY THIS TYPE", "evidence": ev[:20]})
        auto = ""
        if user.get("type"):
            auto = f"You set this. Auto-detected: {user['auto_type_label']} ({int(user['auto_confidence'] * 100)}%)"
        return {"sid": snap["sid"], "name": snap["name"], "typeKey": typ, "typeLabel": snap["type_label"],
                "category": snap.get("category", "Other"), "color": icons.color(typ), "iconName": f"device_{typ}",
                "labelDark": icons.label_colors(typ)[0], "labelLight": icons.label_colors(typ)[1],
                "confidence": 0.0 if offline else float(snap["confidence"]), "offline": offline,
                "status": "offline" if offline else (h.get("status") or ""), "ip": snap["ip"],
                "mac": snap.get("mac") or "", "webUrl": snap.get("web_url") or "",
                "webUrls": [w["url"] for w in snap["web_urls"]], "history": hist, "autoLine": auto,
                "notes": user.get("notes") or "", "userName": user.get("name") or "",
                "userType": user.get("type") or "", "sections": sections, "editable": not offline}

    # ---- actions -------------------------------------------------------------------------
    @Slot(str)
    def openUrl(self, url: str) -> None:
        snap = self._snaps.get(self._selected) or {}
        allowed = {w["url"] for w in snap.get("web_urls", [])}
        if url in allowed:                       # only ever open URLs the scan attributed to this device
            QDesktopServices.openUrl(QUrl(url))
            self.toast.emit(f"Opened {url}")
        else:
            self.toast.emit("No web interface found for this device")

    @Slot()
    def requestEdit(self) -> None:
        if self._current.get("editable"):
            self.editRequested.emit()

    @Slot(str)
    def copyText(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.toast.emit(f"Copied {text}")

    @Slot(str, str, str, str)
    def saveEdit(self, sid: str, name: str, type_key: str, notes: str) -> None:
        d = next((d for d in self._devices if (self._snaps.get(sid) or {}).get("ip") == d.ip), None)
        if d is None:
            self.toast.emit("Wait for the scan to finish, then edit")
            return
        self.labels.label_device(d, name=name.strip() or None, type=type_key or None, notes=notes.strip() or None)
        self.labels.apply([d])
        self._on_snapshot(d.to_dict())
        self.toast.emit("Saved")

    @Slot(str)
    def resetEdit(self, sid: str) -> None:
        d = next((d for d in self._devices if (self._snaps.get(sid) or {}).get("ip") == d.ip), None)
        if d is None:
            return
        self.labels.forget(key_for(d))
        self.labels.apply([d])
        self._on_snapshot(d.to_dict())
        self.toast.emit("Back to auto-detected")

    @Slot(str, str)
    def exportTo(self, file_url: str, fmt: str) -> None:
        path = QUrl(file_url).toLocalFile() or file_url
        fmt = export.format_for_path(path) or (fmt if fmt in export.FORMATS else "json")
        if not self._devices:
            self.toast.emit("Nothing to export yet - run a scan first")
            return
        try:
            export.write(self._devices, fmt, path, {"networks": ", ".join(str(i.network) for i in self._scanned)})
            self.toast.emit(f"Saved {Path(path).name}")
        except Exception as e:                   # noqa: BLE001 - show any writer error to the user
            self.toast.emit(f"Export failed: {e}")

    @Slot(result="QVariantList")
    def exportFormats(self) -> list:
        return [{"fmt": f, "label": {"json": "JSON", "html": "HTML report", "md": "Markdown", "csv": "CSV",
                                     "xlsx": "Excel workbook", "pdf": "PDF", "txt": "Plain text"}[f]}
                for f in export.FORMATS]

    def shutdown(self) -> None:
        if self._worker:
            self._worker.stop.set()
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
