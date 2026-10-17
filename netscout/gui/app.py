"""netscout GUI (PySide6)."""
from __future__ import annotations

import html
import sys
import threading

from PySide6.QtCore import QObject, QSize, QSortFilterProxyModel, Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QProgressBar, QPushButton, QSplitter,
                               QTableView, QTextBrowser, QVBoxLayout, QWidget, QHeaderView)

from .. import classify, devtypes, export, icons, scanner
from ..discovery import net
from ..model import Device

COLS = ["Device", "IP", "Type", "OS", "Vendor", "MAC", "Confidence"]
FILTERS = {
    "json": "JSON (*.json)", "html": "HTML (*.html)", "md": "Markdown (*.md)", "csv": "CSV (*.csv)",
    "xlsx": "Excel (*.xlsx)", "pdf": "PDF (*.pdf)", "txt": "Plain text (*.txt)",
}

_icon_cache: dict[str, QIcon] = {}


def type_icon(device_type: str) -> QIcon:
    """Rasterise the SVG pictogram at several sizes so it stays crisp on HiDPI screens."""
    if device_type not in _icon_cache:
        icon = QIcon()
        renderer = QSvgRenderer(icons.svg(device_type, 24).encode())
        for px in (24, 32, 48, 64, 96):
            pm = QPixmap(px, px)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            renderer.render(p)
            p.end()
            icon.addPixmap(pm)
        _icon_cache[device_type] = icon
    return _icon_cache[device_type]


class ScanWorker(QObject):
    updated = Signal(dict)          # snapshot of a device as it is discovered
    log = Signal(str)
    progress = Signal(str, float)
    finished = Signal(list, str)    # devices, error ('' on success)

    def __init__(self, ifaces):
        super().__init__()
        self.ifaces = ifaces
        self.stop = threading.Event()

    def run(self) -> None:
        def on_update(d: Device) -> None:
            try:   # discovery threads mutate devices concurrently; skip a torn snapshot
                classify.classify(d)
                self.updated.emit(d.to_dict())
            except RuntimeError:
                pass

        try:
            devices = scanner.scan(self.ifaces, stop=self.stop, on_update=on_update,
                                   log=self.log.emit, progress=self.progress.emit)
            self.finished.emit(devices, "")
        except Exception as e:
            self.finished.emit([], f"{type(e).__name__}: {e}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("netscout")
        self.resize(1180, 720)
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
        for w in (QLabel("Network:"), self.iface_combo, self.scan_btn, self.export_btn):
            top.addWidget(w)
        top.addStretch(1)
        top.addWidget(self.filter, 1)

        self.model = QStandardItemModel(0, len(COLS))
        self.model.setHorizontalHeaderLabels(COLS)
        self.proxy = QSortFilterProxyModel()
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
        for i, w in enumerate((220, 110, 130, 150, 0, 130, 80)):
            if w:
                self.table.setColumnWidth(i, w)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.table.selectionModel().selectionChanged.connect(self.show_selected)

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
        self.detail = QTextBrowser()
        self.detail.setOpenLinks(False)
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

        self.thread = QThread()
        self.worker = ScanWorker(ifaces)
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
        ip = snap["ip"]
        self.snapshots[ip] = snap
        row = self.rows.get(ip)
        if row is None:
            row = self.rows[ip] = self.model.rowCount()
            self.model.appendRow([QStandardItem() for _ in COLS])
        ip_key = tuple(int(p) for p in ip.split("."))
        values = [snap["name"], ip, snap["type_label"], snap["os"], snap["vendor"] or "", snap["mac"] or "",
                  f"{int(snap['confidence'] * 100)}%"]
        keys = [snap["name"].lower(), ip_key[0] << 24 | ip_key[1] << 16 | ip_key[2] << 8 | ip_key[3],
                snap["type_label"], snap["os"].lower(), (snap["vendor"] or "").lower(), snap["mac"] or "",
                snap["confidence"]]
        for c, (v, k) in enumerate(zip(values, keys)):
            it = self.model.item(row, c)
            it.setText(v)
            it.setData(k, Qt.ItemDataRole.UserRole)
        self.model.item(row, 0).setIcon(type_icon(snap["type"]))
        n = self.model.rowCount()
        self.setWindowTitle(f"netscout — {n} devices")

    def on_finished(self, devices: list, error: str) -> None:
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.devices = devices
        for d in devices:                       # final, fully-enriched classification
            self.on_device(d.to_dict())
        self.scan_btn.setText("Scan")
        self.scan_btn.setEnabled(True)
        self.bar.setVisible(False)
        self.export_btn.setEnabled(bool(devices))
        self.statusBar().showMessage(f"Scan failed: {error}" if error else f"Done — {len(devices)} devices")
        self.show_selected()

    # --- details --------------------------------------------------------------------------
    def show_selected(self, *_) -> None:
        idx = self.table.selectionModel().selectedRows(1)
        snap = self.snapshots.get(idx[0].data()) if idx else None
        if not snap:
            self.head_icon.clear()
            self.head_name.setText("Select a device")
            self.head_sub.setText("")
            self.detail.clear()
            return
        self.head_icon.setPixmap(type_icon(snap["type"]).pixmap(QSize(56, 56)))
        self.head_name.setText(snap["name"])
        self.head_sub.setText(f"{snap['type_label']} · {int(snap['confidence'] * 100)}% confidence")
        e = html.escape
        rows = [("IP", snap["ip"]), ("OS", snap["os"] and f'{snap["os"]} ({int(snap["os_confidence"] * 100)}%)'), ("MAC", snap["mac"]), ("Vendor", snap["vendor"]), ("Model", snap["model"]),
                ("Hostname", snap["hostname"]), ("Open ports", ", ".join(map(str, snap["open_ports"]))),
                ("Services", ", ".join(s.split(":", 1)[-1] for s in snap["services"]))]
        rows += [(k, v) for k, v in snap["facts"].items()]
        rows += [("Name via " + k, v) for k, v in snap["names"].items()]
        body = "".join(f"<tr><td><b>{e(k)}</b></td><td>{e(str(v))}</td></tr>" for k, v in rows if v)
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
        self.detail.setHtml(f"<table cellpadding=3>{body}</table><h4>Why this type?</h4><ul>{ev}</ul>")

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
