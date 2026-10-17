"""netscout GUI (PySide6)."""
from __future__ import annotations

import html
import sqlite3
import sys
import threading
import time

from PySide6.QtCore import QObject, QSize, QSortFilterProxyModel, Qt, QThread, QUrl, Signal
from PySide6.QtGui import (QColor, QDesktopServices, QIcon, QPainter, QPixmap, QStandardItem,
                           QStandardItemModel)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QSplitter, QTableView,
                               QTextBrowser, QVBoxLayout, QWidget, QHeaderView)

from .. import classify, devtypes, export, history, icons, scanner
from ..discovery import net
from ..labels import LabelStore, key_for
from ..model import Device

COLS = ["Device", "IP", "Type", "Status", "OS", "Vendor", "MAC", "Confidence"]
SID_ROLE = Qt.ItemDataRole.UserRole + 1        # which snapshot a row shows (online: IP, offline: "offline:<key>")
OFFLINE_ROLE = Qt.ItemDataRole.UserRole + 2
FILTERS = {
    "json": "JSON (*.json)", "html": "HTML (*.html)", "md": "Markdown (*.md)", "csv": "CSV (*.csv)",
    "xlsx": "Excel (*.xlsx)", "pdf": "PDF (*.pdf)", "txt": "Plain text (*.txt)",
}

_icon_cache: dict[tuple[str, bool], QIcon] = {}


def type_icon(device_type: str, dim: bool = False) -> QIcon:
    """Rasterise the SVG pictogram at several sizes so it stays crisp on HiDPI screens.
    dim=True is the faded variant used for devices that are currently offline."""
    if (device_type, dim) not in _icon_cache:
        icon = QIcon()
        renderer = QSvgRenderer(icons.svg(device_type, 24).encode())
        for px in (24, 32, 48, 64, 96):
            pm = QPixmap(px, px)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setOpacity(0.35 if dim else 1.0)
            renderer.render(p)
            p.end()
            icon.addPixmap(pm)
        _icon_cache[(device_type, dim)] = icon
    return _icon_cache[(device_type, dim)]


class RowFilter(QSortFilterProxyModel):
    """Text filter plus the 'show offline devices' switch."""
    show_offline = True

    def filterAcceptsRow(self, row, parent) -> bool:
        if not self.show_offline and self.sourceModel().item(row, 0).data(OFFLINE_ROLE):
            return False
        return super().filterAcceptsRow(row, parent)


def _ago(ts: float) -> str:
    secs = max(0, int(time.time() - ts))
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if secs >= size:
            n = secs // size
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"


def offline_snapshot(k: history.KnownDevice) -> dict:
    """A snapshot (same shape as Device.to_dict) for a remembered device that didn't answer this scan."""
    return {"sid": f"offline:{k.key}", "offline": True, "ip": k.last_ip, "mac": k.mac, "name": k.name,
            "hostname": None, "vendor": k.vendor, "model": None, "type": k.type,
            "type_label": devtypes.label(k.type), "category": devtypes.category(k.type), "confidence": 0.0,
            "os": k.os or "", "os_family": None, "os_detail": None, "os_confidence": 0.0, "os_evidence": [],
            "web_url": None, "web_urls": [], "advertised": [], "recog": [], "user": None, "open_ports": [],
            "services": [], "names": {}, "facts": {}, "evidence": [],
            "history": {"status": "offline", "first_seen": k.first_seen, "last_seen": k.last_seen,
                        "seen_count": k.seen_count, "missed": k.missed}}


class ScanWorker(QObject):
    updated = Signal(dict)          # snapshot of a device as it is discovered
    log = Signal(str)
    progress = Signal(str, float)
    finished = Signal(list, str)    # devices, error ('' on success)

    def __init__(self, ifaces, labels: LabelStore):
        super().__init__()
        self.ifaces = ifaces
        self.labels = labels
        self.stop = threading.Event()

    def run(self) -> None:
        def on_update(d: Device) -> None:
            try:   # discovery threads mutate devices concurrently; skip a torn snapshot
                classify.classify(d)
                self.labels.apply([d])          # your corrections show up live too
                self.updated.emit(d.to_dict())
            except RuntimeError:
                pass

        try:
            devices = scanner.scan(self.ifaces, stop=self.stop, on_update=on_update, labels=self.labels,
                                   log=self.log.emit, progress=self.progress.emit)
            self.finished.emit(devices, "")
        except Exception as e:
            self.finished.emit([], f"{type(e).__name__}: {e}")


class EditDialog(QDialog):
    """Correct what netscout thinks a device is: your name, type and notes are remembered by MAC."""

    def __init__(self, parent, snap: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Edit {snap['name']}")
        user = snap.get("user") or {}
        auto_type = user.get("auto_type") or snap["type"]
        auto_label = devtypes.label(auto_type)
        self.reset_requested = False

        self.name = QLineEdit(user.get("name") or "")
        self.name.setPlaceholderText("auto: " + (snap["name"] if not user.get("name") else snap["ip"]))
        self.type = QComboBox()
        self.type.addItem(type_icon(auto_type), f"Auto-detected: {auto_label}", None)
        for key, (label, category, _) in sorted(devtypes.TYPES.items(), key=lambda kv: (kv[1][1], kv[1][0])):
            self.type.addItem(type_icon(key), f"{category} › {label}", key)
        if user.get("type"):
            self.type.setCurrentIndex(self.type.findData(user["type"]))
        self.type.setIconSize(QSize(22, 22))
        self.notes = QPlainTextEdit(user.get("notes") or "")
        self.notes.setPlaceholderText("Anything worth remembering (location, owner, what it controls)…")
        self.notes.setFixedHeight(90)

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        reset = buttons.addButton("Reset to auto-detected", QDialogButtonBox.ButtonRole.DestructiveRole)
        reset.setEnabled(bool(user))
        reset.clicked.connect(self._reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"{snap['ip']}  ·  {snap['mac'] or 'no MAC'}  ·  detected as {auto_label} "
                             f"({int((user.get('auto_confidence') or snap['confidence']) * 100)}%)"))
        lay.addLayout(form)
        lay.addWidget(buttons)
        self.setMinimumWidth(460)

    def _reset(self) -> None:
        self.reset_requested = True
        self.accept()

    def fields(self) -> dict:
        return {"name": self.name.text().strip() or None, "type": self.type.currentData(),
                "notes": self.notes.toPlainText().strip() or None}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("netscout")
        self.resize(1180, 720)
        self.labels = LabelStore()
        self.scanned: list = []         # interfaces of the scan in progress / last completed
        self.devices: list[Device] = []
        self.rows: dict[str, int] = {}
        self.snapshots: dict[str, dict] = {}
        self.thread: QThread | None = None
        self.worker: ScanWorker | None = None

        self.iface_combo = QComboBox()
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self.toggle_scan)
        self.export_btn = QPushButton("Export…")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_results)
        self.filter = QLineEdit(placeholderText="Filter devices…", clearButtonEnabled=True)

        top = QHBoxLayout()
        self.offline_box = QCheckBox("Show offline")
        self.offline_box.setChecked(True)
        self.offline_box.setToolTip("Devices seen in earlier scans that didn't answer this time")
        self.offline_box.toggled.connect(self._toggle_offline)
        for w in (QLabel("Network:"), self.iface_combo, self.scan_btn, self.export_btn, self.offline_box):
            top.addWidget(w)
        top.addStretch(1)
        top.addWidget(self.filter, 1)

        self.model = QStandardItemModel(0, len(COLS))
        self.model.setHorizontalHeaderLabels(COLS)
        self.proxy = RowFilter()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setIconSize(QSize(28, 28))
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate((210, 110, 130, 80, 150, 0, 125, 80)):
            if w:
                self.table.setColumnWidth(i, w)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.table.selectionModel().selectionChanged.connect(self.show_selected)
        self.table.doubleClicked.connect(lambda *_: self.open_web_ui())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_menu)

        self.open_btn = QPushButton("Open web UI")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(lambda *_: self.open_web_ui())
        self.head_icon = QLabel()
        self.head_icon.setFixedSize(56, 56)
        self.head_name = QLabel("Select a device")
        self.head_name.setStyleSheet("font-size:17px;font-weight:600")
        self.head_sub = QLabel("")
        hl = QVBoxLayout()
        hl.addWidget(self.head_name)
        hl.addWidget(self.head_sub)
        head = QHBoxLayout()
        head.addWidget(self.head_icon)
        head.addLayout(hl, 1)
        head.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.detail = QTextBrowser()
        self.detail.setOpenLinks(False)
        self.detail.anchorClicked.connect(self.on_link)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addLayout(head)
        rl.addWidget(self.detail, 1)

        split = QSplitter()
        split.addWidget(self.table)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.addLayout(top)
        cl.addWidget(split, 1)
        self.setCentralWidget(central)

        self.bar = QProgressBar()
        self.bar.setMaximumWidth(220)
        self.bar.setRange(0, 1000)
        self.bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.bar)
        self.refresh_interfaces()

    # --- scanning -------------------------------------------------------------------------
    def refresh_interfaces(self) -> None:
        self.ifaces = net.list_interfaces()
        self.iface_combo.clear()
        if len(self.ifaces) > 1:
            self.iface_combo.addItem("All networks", None)
        for i in self.ifaces:
            self.iface_combo.addItem(i.label, i)
        if not self.ifaces:
            self.statusBar().showMessage("No active IPv4 network found")
            self.scan_btn.setEnabled(False)

    def toggle_scan(self) -> None:
        if self.thread and self.thread.isRunning():
            if self.worker:
                self.worker.stop.set()
            self.scan_btn.setEnabled(False)
            self.statusBar().showMessage("Stopping…")
            return
        sel = self.iface_combo.currentData()
        ifaces = [sel] if sel else self.ifaces
        self.model.removeRows(0, self.model.rowCount())
        self.rows.clear()
        self.snapshots.clear()
        self.devices = []
        self.export_btn.setEnabled(False)
        self.scan_btn.setText("Stop")
        self.bar.setValue(0)
        self.bar.setVisible(True)
        self.statusBar().showMessage("Scanning…")

        self.scanned = ifaces
        self.thread = QThread()
        self.worker = ScanWorker(ifaces, self.labels)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.updated.connect(self.on_device)
        self.worker.log.connect(self.statusBar().showMessage)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.thread.start()

    def on_progress(self, stage: str, frac: float) -> None:
        base = {"sweep": 0.0, "ports": 0.5}.get(stage, 0.0)
        span = 0.5
        self.bar.setValue(int((base + span * frac) * 1000))

    def on_device(self, snap: dict) -> None:
        sid = snap.setdefault("sid", snap["ip"])
        offline = bool(snap.get("offline"))
        self.snapshots[sid] = snap
        row = self.rows.get(sid)
        if row is None:
            row = self.rows[sid] = self.model.rowCount()
            self.model.appendRow([QStandardItem() for _ in COLS])
        ip = snap["ip"]
        ip_key = tuple(int(p) for p in ip.split("."))
        user = snap.get("user")
        edited = bool(user and user["type"])
        hist = snap.get("history") or {}
        status = "Offline" if offline else {"new": "New", "returned": "Returned"}.get(hist.get("status"), "")
        values = [snap["name"], ip, snap["type_label"] + (" ✎" if edited else ""), status, snap["os"],
                  snap["vendor"] or "", snap["mac"] or "",
                  "" if offline else f"{int(snap['confidence'] * 100)}%"]
        keys = [snap["name"].lower(), ip_key[0] << 24 | ip_key[1] << 16 | ip_key[2] << 8 | ip_key[3],
                snap["type_label"], status, snap["os"].lower(), (snap["vendor"] or "").lower(),
                snap["mac"] or "", snap["confidence"]]
        for c, (v, k) in enumerate(zip(values, keys)):
            it = self.model.item(row, c)
            it.setText(v)
            it.setData(k, Qt.ItemDataRole.UserRole)
            it.setForeground(QColor("#8a94a3") if offline else QColor("#4cc38a") if (c == 3 and status) else QColor())
        first = self.model.item(row, 0)
        first.setData(sid, SID_ROLE)
        first.setData(offline, OFFLINE_ROLE)
        first.setIcon(type_icon(snap["type"], dim=offline))
        self.model.item(row, 2).setToolTip(
            f"You set this. Auto-detected: {user['auto_type_label']} ({int(user['auto_confidence'] * 100)}%)"
            if edited else "")
        self.model.item(row, 3).setToolTip(
            f"Last seen {_ago(hist['last_seen'])}" if offline and hist.get("last_seen") else "")
        self.setWindowTitle(f"netscout — {sum(1 for s in self.snapshots.values() if not s.get('offline'))} devices")

    def _toggle_offline(self, on: bool) -> None:
        self.proxy.show_offline = on
        self.proxy.invalidateFilter()

    def _record_history(self, devices: list[Device]) -> str:
        """Store this scan and add remembered-but-silent devices as offline rows. Returns a status suffix."""
        if self.worker and self.worker.stop.is_set():
            return " (stopped: not recorded in history)"      # a partial scan would make devices look gone
        nets = [str(i.network) for i in self.scanned]
        try:
            h = history.History()
            diff = h.record(devices, nets)
            keys = {key_for(d) for d in devices}
            offline = h.offline(nets, keys)
        except (sqlite3.Error, OSError) as e:
            return f" (history unavailable: {e})"
        for d in devices:                                     # refresh rows: they now carry history
            self.on_device(d.to_dict())
        for k in offline:
            self.on_device(offline_snapshot(k))
        bits = [f"{len(diff.new)} new"] * bool(diff.new) + [f"{len(diff.returned)} returned"] * bool(diff.returned) \
            + [f"{len(diff.moved)} moved"] * bool(diff.moved) + [f"{len(diff.left)} left"] * bool(diff.left)
        if diff.baseline_networks:
            bits.append("baseline recorded")
        return " · " + ", ".join(bits) if bits else ""

    def on_finished(self, devices: list, error: str) -> None:
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.devices = devices
        for d in devices:                       # final, fully-enriched classification
            self.on_device(d.to_dict())
        suffix = "" if error else self._record_history(devices)
        self.scan_btn.setText("Scan")
        self.scan_btn.setEnabled(True)
        self.bar.setVisible(False)
        self.export_btn.setEnabled(bool(devices))
        self.statusBar().showMessage(f"Scan failed: {error}" if error else f"Done — {len(devices)} devices{suffix}")
        self.show_selected()

    # --- details --------------------------------------------------------------------------
    def show_selected(self, *_) -> None:
        snap = self.selected_snap()
        if not snap:
            self.head_icon.clear()
            self.head_name.setText("Select a device")
            self.head_sub.setText("")
            self.detail.clear()
            self.open_btn.setEnabled(False)
            return
        self.open_btn.setEnabled(bool(snap["web_url"]))
        self.open_btn.setToolTip(snap["web_url"] or "No web interface found for this device")
        self.head_icon.setPixmap(type_icon(snap["type"]).pixmap(QSize(56, 56)))
        self.head_name.setText(snap["name"])
        self.head_sub.setText(f"{snap['type_label']} · offline" if snap.get("offline")
                              else f"{snap['type_label']} · {int(snap['confidence'] * 100)}% confidence")
        e = html.escape
        user = snap.get("user") or {}
        h = snap.get("history") or {}
        if snap.get("offline"):
            hist_text = (f"Offline - last seen {_ago(h['last_seen'])}; missed {h['missed']} scan"
                         f"{'s' if h['missed'] != 1 else ''}. First seen "
                         f"{time.strftime('%Y-%m-%d', time.localtime(h['first_seen']))}, seen in {h['seen_count']} scans.")
        elif h.get("status") == "new":
            hist_text = "New device: first time it has been seen on this network"
        elif h.get("first_seen"):
            hist_text = (("Returned after being away. " if h.get("status") == "returned" else "")
                         + f"First seen {time.strftime('%Y-%m-%d', time.localtime(h['first_seen']))}, "
                           f"seen in {h['seen_count']} scans"
                         + (f"; previously at {h['previous_ip']}" if h.get("previous_ip") else ""))
        else:
            hist_text = None
        rows = [("History", hist_text), ("Auto-detected", user.get("type") and
                 f"{user['auto_type_label']} ({int(user['auto_confidence'] * 100)}%) - you changed this"),
                ("Your notes", user.get("notes")),
                ("IP", snap["ip"]), ("OS", snap["os"] and f'{snap["os"]} ({int(snap["os_confidence"] * 100)}%)'), ("MAC", snap["mac"]), ("Vendor", snap["vendor"]), ("Model", snap["model"]),
                ("Hostname", snap["hostname"]), ("Open ports", ", ".join(map(str, snap["open_ports"])))]
        # per-service facts (mdns:_x._tcp = port N) are shown properly in "Advertised services" below
        rows += [(k, v) for k, v in snap["facts"].items() if not k.startswith("mdns:")]
        rows += [("Name via " + k, v) for k, v in snap["names"].items()]
        body = "".join(f"<tr><td><b>{e(k)}</b></td><td>{e(str(v))}</td></tr>" for k, v in rows if v)
        body += "".join(f"<tr><td><b>Web UI</b></td><td><a href=\"{e(w['url'])}\">{e(w['url'])}</a> "
                        f"<i>({e(w['source'])})</i></td></tr>" for w in snap["web_urls"][:6])
        seen, items = set(), []
        for x in snap["evidence"]:      # same hint arriving via several names/sources is shown once
            key = (x["source"], x["device_type"], str(x["detail"]).lower())
            if key not in seen:
                seen.add(key)
                items.append(f"<li><b>{e(x['source'])}</b> → {e(devtypes.label(x['device_type']))} "
                             f"{int(x['weight'] * 100)}% <i>{e(str(x['detail']))}</i></li>")
        for x in snap["os_evidence"]:
            key = ("os:" + x["source"], x["device_type"], str(x["detail"]).lower())
            if key not in seen:
                seen.add(key)
                items.append(f"<li><b>os/{e(x['source'])}</b> → {e(x['device_type'])} "
                             f"{int(x['weight'] * 100)}% <i>{e(str(x['detail']))}</i></li>")
        ev = "".join(items[:20])
        svc = "".join(
            f"<p style='margin:6px 0 0 0'><b>{e(label)}</b></p><ul style='margin-top:2px'>"
            + "".join(f"<li>{e(export.service_line(s))}"
                      + (f" <i>{e(' · '.join(f'{k}={v}' for k, v in list(s['details'].items())[:5]))}</i>"
                         if s["details"] and s["protocol"] in ("mdns", "wsd") else "") + "</li>" for s in items)
            + "</ul>" for label, items in export.grouped_services(snap))
        svc_html = f"<h4>Advertised services ({len(snap['advertised'])})</h4>{svc}" if svc else ""
        self.detail.setHtml(f"<table cellpadding=3>{body}</table>{svc_html}"
                            + (f"<h4>Why this type?</h4><ul>{ev}</ul>" if ev else ""))

    # --- web UI / context menu -------------------------------------------------------------
    def selected_snap(self) -> dict | None:
        idx = self.table.selectionModel().selectedRows(0)
        return self.snapshots.get(idx[0].data(SID_ROLE)) if idx else None

    def open_web_ui(self, url: str | None = None) -> None:
        snap = self.selected_snap()
        allowed = {w["url"] for w in snap["web_urls"]} if snap else set()
        url = url or (snap["web_url"] if snap else None)
        if not url or url not in allowed:   # only ever open URLs the scan attributed to this device
            self.statusBar().showMessage("No web interface found for this device")
            return
        QDesktopServices.openUrl(QUrl(url))
        self.statusBar().showMessage(f"Opened {url}")

    def on_link(self, qurl: QUrl) -> None:
        self.open_web_ui(qurl.toString())

    def show_menu(self, pos) -> None:
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return
        self.table.selectRow(idx.row())
        snap = self.selected_snap()
        if not snap:
            return
        menu = QMenu(self)
        act = menu.addAction("Open web UI")
        act.setEnabled(bool(snap["web_url"]))
        act.triggered.connect(lambda *_: self.open_web_ui())
        menu.addAction("Edit name / type / notes…").triggered.connect(lambda *_: self.edit_device())
        menu.addSeparator()
        menu.addAction("Copy IP").triggered.connect(lambda *_: QApplication.clipboard().setText(snap["ip"]))
        if snap["mac"]:
            menu.addAction("Copy MAC").triggered.connect(lambda *_: QApplication.clipboard().setText(snap["mac"]))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def edit_device(self) -> None:
        snap = self.selected_snap()
        if not snap:
            return
        if snap.get("offline"):
            self.statusBar().showMessage("Offline devices can be edited once they answer a scan again")
            return
        device = next((d for d in self.devices if d.ip == snap["ip"]), None)
        if device is None:            # live rows exist before the scan finishes; corrections need the final device
            self.statusBar().showMessage("Wait for the scan to finish, then edit")
            return
        dlg = EditDialog(self, snap)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.reset_requested:
            self.labels.forget(key_for(device))
        else:
            self.labels.label_device(device, **dlg.fields())
        self.labels.apply([device])
        self.on_device(device.to_dict())
        self.show_selected()
        self.statusBar().showMessage("Saved" if not dlg.reset_requested else "Back to auto-detected")

    # --- export ---------------------------------------------------------------------------
    def export_results(self) -> None:
        path, chosen = QFileDialog.getSaveFileName(self, "Export results", "netscout-results.xlsx",
                                                   ";;".join(FILTERS.values()))
        if not path:
            return
        fmt = export.format_for_path(path) or next((k for k, v in FILTERS.items() if v == chosen), "json")
        try:
            export.write(self.devices, fmt, path, {"networks": ", ".join(str(i.network) for i in self.ifaces)})
            self.statusBar().showMessage(f"Saved {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def closeEvent(self, ev) -> None:
        if self.worker:
            self.worker.stop.set()
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        super().closeEvent(ev)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("netscout")
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
