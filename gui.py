import os
import re
import sys
import ctypes
from datetime import datetime

os.environ.setdefault('QT_MULTIMEDIA_PREFERRED_PLUGINS', 'windowsmediafoundation')

from PyQt5.QtCore import QEvent, QObject, QSettings, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QColor, QPalette, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QAbstractButton,
    QListWidget, QListWidgetItem, QLabel, QSplitter, QTextEdit, QProgressBar,
    QMessageBox, QComboBox, QScrollArea, QFrame, QMenu,
    QInputDialog, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QStyledItemDelegate, QStyleOptionViewItem,
)

import core
import icons
import style
from player import PlayerBar


def rounded_pixmap(src, size, radius):
    try:
        if isinstance(src, str):
            with open(src, 'rb') as f:
                data = f.read()
        else:
            data = src
        pm = QPixmap()
        pm.loadFromData(data)
    except Exception:
        return None
    if pm.isNull():
        return None
    pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    p.setClipPath(path)
    p.drawPixmap((size - pm.width()) // 2, (size - pm.height()) // 2, pm)
    p.end()
    return out


def _song_cells(song, artist):
    title = re.sub(r"\s*\[[A-Za-z0-9_-]{6}\]$", "", song['title'])
    date = (datetime.fromtimestamp(song['mtime']).strftime('%Y-%m-%d')
            if song['mtime'] else '')
    return title, artist or '', date


def _settings():
    return QSettings("MusicDownloader", "MusicDownloader")


def _load_sort(settings_key, default_col, default_order):
    vals = _settings().value(settings_key + '/sort')
    if isinstance(vals, list) and len(vals) == 2:
        return int(vals[0]), int(vals[1])
    return default_col, default_order


def _populate_song_table(table, rows, current_path=None):
    table.setRowCount(0)
    table.setRowCount(len(rows))
    for row, r in enumerate(rows):
        title, artist, date = _song_cells(r['song'], r['artist'])
        playing = (current_path
                   and os.path.normpath(r['full']) == os.path.normpath(current_path))
        if playing:
            title = "\u25B6 " + title
        items = [QTableWidgetItem(title),
                 QTableWidgetItem(artist),
                 QTableWidgetItem(date)]
        items[0].setData(Qt.UserRole, r.get('user_data'))
        if r.get('tooltip'):
            items[0].setToolTip(r['tooltip'])
        if playing:
            for it in items:
                it.setForeground(QColor(style.ACCENT_HOVER))
        for col, it in enumerate(items):
            table.setItem(row, col, it)
    if hasattr(table, '_playing_delegate'):
        playing_rows = set()
        if current_path:
            for row, r in enumerate(rows):
                if os.path.normpath(r['full']) == os.path.normpath(current_path):
                    playing_rows.add(row)
        table._playing_delegate.setPlayingRows(playing_rows)



class SongTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings_key = None
        self._balancing = False
        self._dragging = False
        self._last_resized = None

    def _rebalance(self, avoid=None):
        if self._balancing:
            return
        hh = self.horizontalHeader()
        if not hh or hh.count() == 0:
            return
        if avoid is not None and avoid + 1 < hh.count():
            absorber = avoid + 1
        else:
            absorber = 0
        avail = self.viewport().width()
        total = sum(hh.sectionSize(i) for i in range(hh.count()))
        if total == avail:
            return
        delta = avail - total
        if hh.sectionSize(absorber) + delta < hh.minimumSectionSize():
            return
        self._balancing = True
        try:
            hh.resizeSection(absorber,
                             hh.sectionSize(absorber) + delta)
        finally:
            self._balancing = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebalance()

    def eventFilter(self, obj, event):
        if obj is self.horizontalHeader():
            if event.type() == QEvent.MouseButtonPress:
                self._dragging = True
            elif event.type() == QEvent.MouseButtonRelease:
                self._dragging = False
                self._rebalance(avoid=self._last_resized)
                if self._settings_key:
                    _settings().setValue(
                        self._settings_key + '/columns',
                        self.horizontalHeader().saveState())
        return super().eventFilter(obj, event)

    def _on_section_resized(self, index, *args):
        self._last_resized = index
        self._rebalance(avoid=index)
        if not self._dragging and self._settings_key:
            _settings().setValue(
                self._settings_key + '/columns',
                self.horizontalHeader().saveState())


class _PlayingDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._playing_rows = set()

    def setPlayingRows(self, rows):
        self._playing_rows = set(rows)

    def paint(self, painter, option, index):
        if index.row() in self._playing_rows:
            opt = QStyleOptionViewItem(option)
            opt.palette.setColor(QPalette.Text, QColor(style.ACCENT_HOVER))
            super().paint(painter, opt, index)
        else:
            super().paint(painter, option, index)


def _configure_song_table(table, settings_key):
    table._settings_key = settings_key
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["Song", "Artist", "Date"])
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.ElideRight)
    table.setAlternatingRowColors(True)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    table.setColumnWidth(0, 300)
    table.setColumnWidth(1, 200)
    table.setColumnWidth(2, 110)
    hh = table.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.Interactive)
    hh.setStretchLastSection(False)
    hh.setMinimumSectionSize(60)
    state = _settings().value(settings_key + '/columns')
    if state:
        table._balancing = True
        hh.restoreState(state)
        table._balancing = False
    hh.setSectionResizeMode(QHeaderView.Interactive)
    hh.setStretchLastSection(False)
    hh.setMinimumSectionSize(60)
    hh.setSortIndicatorShown(False)
    hh.installEventFilter(table)
    hh.sectionResized.connect(table._on_section_resized)
    table._rebalance()
    delegate = _PlayingDelegate(table)
    table.setItemDelegate(delegate)
    table._playing_delegate = delegate
    return table


_HEADER_LABELS = ["Song", "Artist", "Date"]


def _set_header_arrows(table, sort_col, sort_order):
    for col, label in enumerate(_HEADER_LABELS):
        text = label
        if col == sort_col:
            text += "\u2002\u2191" if sort_order == Qt.AscendingOrder \
                else "\u2002\u2193"
        table.horizontalHeaderItem(col).setText(text)


class NoScrollFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True
        return super().eventFilter(obj, event)


class ResultRow(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self._hover = False
        self.setFixedHeight(64)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(self._qss())

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 10, 0)
        lay.setSpacing(12)

        cover = QLabel()
        cover.setObjectName("cover")
        cover.setFixedSize(64, 64)
        cover.setAlignment(Qt.AlignCenter)
        thumb = result.get('thumb')
        pix = rounded_pixmap(thumb, 64, 0) if thumb else None
        if pix:
            cover.setPixmap(pix)
        else:
            cover.setStyleSheet(
                f"background-color: {style.SURFACE2}; border-radius: 0px;")
            cover.setPixmap(icons.make_pixmap('music_note', style.MUTED, 20))
        lay.addWidget(cover)

        vbox = QVBoxLayout()
        vbox.setSpacing(2)
        title = QLabel(result.get('title') or 'Unknown')
        title.setObjectName("tracktitle")
        title.setStyleSheet(f"color: {style.TEXT};")
        vbox.addWidget(title)
        sub = [s for s in (result.get('artist'), result.get('album')) if s]
        subtitle = QLabel(' \u2022 '.join(sub))
        subtitle.setObjectName("trackartist")
        subtitle.setStyleSheet(f"color: {style.MUTED}; font-size: 12px;")
        vbox.addWidget(subtitle)
        lay.addLayout(vbox, 1)

        if result.get('duration'):
            dur = QLabel(result['duration'])
            dur.setStyleSheet(f"color: {style.MUTED};")
            dur.setFixedWidth(48)
            dur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lay.addWidget(dur)

        kind = 'Track' if result.get('kind') == 'track' else 'Video'
        badge = QLabel(kind)
        badge.setFixedWidth(54)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"border-radius: 10px; padding: 2px 0; font-size: 11px; font-weight: 700;"
            f"background-color: {style.ACCENT if kind == 'Track' else style.SURFACE3};"
            f"color: {'#000' if kind == 'Track' else style.MUTED};")
        lay.addWidget(badge)

    def _qss(self):
        bg = style.SURFACE2 if self._hover else 'transparent'
        return f"background-color: {bg}; border: none; border-radius: 6px;"

    def enterEvent(self, event):
        self._hover = True
        self.setStyleSheet(self._qss())
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.setStyleSheet(self._qss())
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit(self.result)
        super().mousePressEvent(event)


class SearchWorker(QThread):
    results = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self):
        try:
            items = core.search_music(self.query)
            for it in items:
                it['thumb'] = core.thumbnail_path(it.get('thumb_url'))
            self.results.emit(items)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadWorker(QThread):
    log = pyqtSignal(str)
    done = pyqtSignal(object)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self._cancel = {'flag': False}

    def request_cancel(self):
        self._cancel['flag'] = True

    def run(self):
        try:
            result = core.download_url(
                self.url,
                progress_cb=None, cancel_flag=self._cancel)
            self.done.emit({'ok': True, 'result': result})
        except core.DownloadCancelled:
            self.done.emit({'ok': True, 'cancelled': True, 'result': None})
        except Exception as e:
            self.done.emit({'ok': False, 'error': str(e)})


class DownloadTab(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, on_download_finished, parent=None):
        super().__init__(parent)
        self.on_download_finished = on_download_finished
        self.worker = None
        self.search_worker = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        title = QLabel("Search YouTube Music")
        title.setObjectName("navheader")
        root.addWidget(title)

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for a song, artist, or album...")
        self.search_input.returnPressed.connect(self.do_search)
        search_btn = QPushButton("Search")
        search_btn.setProperty("accent", True)
        search_btn.setIcon(icons.make_icon('search', '#000000', 14))
        search_btn.setIconSize(search_btn.iconSize())
        search_btn.clicked.connect(self.do_search)
        row.addWidget(self.search_input, 1)
        row.addWidget(search_btn)
        root.addLayout(row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(120)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 4, 0)
        self.results_layout.setSpacing(4)
        self.results_layout.addStretch(1)
        self.scroll.setWidget(self.results_container)
        root.addWidget(self.scroll, 1)

        sep = QLabel("Download")
        sep.setObjectName("navheader")
        root.addWidget(sep)

        row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a YouTube or YouTube Music URL...")
        row.addWidget(self.url_input, 1)
        root.addLayout(row)

        btn_row = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.setProperty("accent", True)
        self.download_btn.setIcon(icons.make_icon('download', '#000000', 14))
        self.download_btn.clicked.connect(self.start_download)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_download)
        btn_row.addStretch(1)
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

    def do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self._clear_results()
        self.status_message.emit(f"Searching for \"{query}\"...")
        self.search_worker = SearchWorker(query)
        self.search_worker.results.connect(self.show_results)
        self.search_worker.failed.connect(
            lambda e: self.status_message.emit(f"Search failed: {e}"))
        self.search_worker.start()

    def _clear_results(self):
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def show_results(self, results):
        self._clear_results()
        for r in results:
            row = ResultRow(r)
            row.clicked.connect(self.use_result)
            self.results_layout.insertWidget(
                self.results_layout.count() - 1, row)
        self.status_message.emit(f"{len(results)} result(s) found")

    def use_result(self, result):
        self.url_input.setText(result.get('url', ''))

    def start_download(self):
        self.download(self.url_input.text().strip())

    def download(self, url):
        if not url:
            QMessageBox.warning(
                self, "No URL",
                "Paste a YouTube URL or search for a track first.")
            return
        if self.worker and self.worker.isRunning():
            return
        self.progress_bar.setVisible(True)
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_message.emit(f"Downloading {url}")
        self.worker = DownloadWorker(url)
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(self.on_worker_done)
        self.worker.start()

    def cancel_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_cancel()
            self.status_message.emit("Cancelling...")
            self.cancel_btn.setEnabled(False)

    def append_log(self, line):
        self.status_message.emit(line)

    def on_worker_done(self, data):
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if data.get('cancelled'):
            self.status_message.emit("Download cancelled")
            return
        if not data.get('ok'):
            self.status_message.emit("Download failed")
            QMessageBox.critical(
                self, "Download failed", str(data.get('error')))
            return
        result = data.get('result')
        if result:
            QMessageBox.information(
                self, "Download complete",
                f"Playlist saved to {result}")
        else:
            QMessageBox.information(
                self, "Download complete",
                "Song saved to All Songs.")
        self.status_message.emit("Download finished")
        self.on_download_finished()


class LibraryTab(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, play_request, on_change=None, download_request=None,
                 parent=None):
        super().__init__(parent)
        self.play_request = play_request
        self.on_change = on_change
        self.download_request = download_request
        self.current_path = None
        self._songs_by_full = {}
        self.artists = {}
        self._displayed = []
        self._sort_col = 2
        self._sort_order = Qt.DescendingOrder
        self._build()
        self._sort_col, self._sort_order = _load_sort(
            'library', 2, Qt.DescendingOrder)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        title = QLabel("Your Library")
        title.setObjectName("navheader")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        left = QWidget()
        left.setMinimumWidth(140)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(0, 0, 0, 0)
        lbox.setSpacing(6)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 12, 0)
        header_row.setSpacing(10)
        header_row.addWidget(self._section("PLAYLISTS"))
        header_row.addStretch(1)
        self.refresh_playlist_btn = QPushButton("Refresh")
        self.refresh_playlist_btn.setToolTip(
            "Re-download selected playlist (new entries only)")
        self.refresh_playlist_btn.setIcon(
            icons.make_icon('refresh', style.TEXT, 14))
        self.refresh_playlist_btn.clicked.connect(
            self.refresh_selected_playlist)
        header_row.addWidget(self.refresh_playlist_btn)
        lbox.addLayout(header_row)
        self.playlist_list = QListWidget()
        self.playlist_list.setObjectName("sidebar")
        self.playlist_list.currentItemChanged.connect(self.show_playlist)
        self.playlist_list.itemDoubleClicked.connect(
            lambda item: self._play(item.data(Qt.UserRole), None))
        self.playlist_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(
            self.show_playlist_menu)
        lbox.addWidget(self.playlist_list)
        splitter.addWidget(left)

        right = QWidget()
        right.setMinimumWidth(280)
        rbox = QVBoxLayout(right)
        rbox.setContentsMargins(12, 0, 0, 0)
        rbox.setSpacing(6)
        rbox.addWidget(self._section("SONGS"))
        self.song_filter = QLineEdit()
        self.song_filter.setPlaceholderText("Search songs in playlist...")
        self.song_filter.setClearButtonEnabled(True)
        self.song_filter.textChanged.connect(self._on_song_filter)
        rbox.addWidget(self.song_filter)
        self.song_table = _configure_song_table(SongTable(), 'library')
        self.song_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.song_table.customContextMenuRequested.connect(self.show_context_menu)
        self.song_table.cellDoubleClicked.connect(self.play_song)
        self.song_table.horizontalHeader().sectionClicked.connect(
            self._on_header_clicked)
        rbox.addWidget(self.song_table)
        splitter.addWidget(right)

        splitter.setSizes([280, 620])
        root.addWidget(splitter, 1)

        btn_row = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setProperty("accent", True)
        self.play_btn.setIcon(icons.make_icon('play', '#000000', 14))
        self.play_btn.clicked.connect(self.play_selected)
        self.delete_btn = QPushButton("Delete selected")
        self.delete_btn.setProperty("danger", True)
        self.delete_btn.setIcon(icons.make_icon('trash', '#ffffff', 14))
        self.delete_btn.clicked.connect(self.delete_song)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(icons.make_icon('refresh', style.TEXT, 14))
        self.refresh_btn.clicked.connect(self.reload)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch(1)
        self.open_songs_btn = QPushButton("Open Songs")
        self.open_songs_btn.setIcon(icons.make_icon('folder', style.TEXT, 14))
        self.open_songs_btn.clicked.connect(
            lambda: core.open_folder(core.MUSIC_DIR))
        self.open_root_btn = QPushButton("Open Playlists")
        self.open_root_btn.setIcon(icons.make_icon('folder', style.TEXT, 14))
        self.open_root_btn.clicked.connect(
            lambda: core.open_folder(core.PLAYLIST_DIR))
        btn_row.addWidget(self.open_songs_btn)
        btn_row.addWidget(self.open_root_btn)
        root.addLayout(btn_row)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("navheader")
        return lbl

    def reload(self):
        current = None
        if self.playlist_list.currentItem():
            current = self.playlist_list.currentItem().data(Qt.UserRole)['name']
        self.playlists = core.list_playlists()
        songs = core.list_all_songs()
        self._songs_by_full = {
            os.path.normpath(s['full']): s for s in songs}
        self.artists = core.get_artists(songs)
        self.playlist_list.clear()
        index = 0
        for i, p in enumerate(self.playlists):
            item = QListWidgetItem(f"{p['name']}  ({len(p['entries'])} songs)")
            item.setData(Qt.UserRole, p)
            self.playlist_list.addItem(item)
            if p['name'] == current:
                index = i
        if self.playlists:
            self.playlist_list.setCurrentRow(index)
        else:
            self.song_table.setRowCount(0)
        self.status_message.emit("Library refreshed")

    def show_playlist(self, current, _):
        if not current:
            self.song_table.setRowCount(0)
            _set_header_arrows(self.song_table, self._sort_col, self._sort_order)
            return
        p = current.data(Qt.UserRole)
        rows = []
        for entry in p['entries']:
            full = os.path.join(
                core.PLAYLIST_DIR, entry.replace('/', os.sep))
            norm = os.path.normpath(full)
            song = self._songs_by_full.get(norm)
            if song is None:
                song = {
                    'title': os.path.splitext(os.path.basename(entry))[0],
                    'mtime': 0,
                }
            artist = self.artists.get(norm)
            rows.append({'song': song, 'full': full,
                         'artist': artist,
                         'user_data': {'entry': entry, 'playlist_path': p['path'],
                                       'full': full}})
        text = self.song_filter.text().strip().lower()
        if text:
            rows = [r for r in rows
                    if text in (r['song'].get('title', '') or '').lower()
                    or text in (r['artist'] or '').lower()]
        rows.sort(key=self._lib_sort_key,
                  reverse=self._sort_order == Qt.DescendingOrder)
        self._displayed = rows
        _set_header_arrows(self.song_table, self._sort_col, self._sort_order)
        _populate_song_table(self.song_table, rows, self.current_path)

    def _lib_sort_key(self, r):
        if self._sort_col == 1:
            return (r['artist'] or '').lower()
        if self._sort_col == 2:
            return r['song'].get('mtime') or 0
        return r['song'].get('title', '').lower()

    def _on_header_clicked(self, col):
        if self._sort_col == col:
            order = (Qt.AscendingOrder
                     if self._sort_order == Qt.DescendingOrder
                     else Qt.DescendingOrder)
        else:
            order = Qt.AscendingOrder
        self._sort_col = col
        self._sort_order = order
        _settings().setValue('library/sort',
                             [self._sort_col, int(self._sort_order)])
        item = self.playlist_list.currentItem()
        if item:
            self.show_playlist(item, None)

    def show_context_menu(self, pos):
        item = self.song_table.itemAt(pos)
        if item is None:
            return
        row = self.song_table.row(item)
        data = self.song_table.item(row, 0).data(Qt.UserRole)
        entry = data['entry']

        menu = QMenu(self)
        sub = menu.addMenu("Add to playlist")
        real = [p for p in self.playlists if p['path']]
        if not real:
            act = sub.addAction("No playlists yet")
            act.setEnabled(False)
        for p in real:
            name = os.path.splitext(p['name'])[0]
            act = sub.addAction(name)
            act.setData(p['path'])
        sub.addSeparator()
        new_act = sub.addAction("New playlist...")

        chosen = menu.exec_(self.song_table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        title = os.path.splitext(os.path.basename(entry))[0]
        if chosen is new_act:
            name, ok = QInputDialog.getText(
                self, "New playlist", "Playlist name:")
            if not ok or not name.strip():
                return
            path = core.create_playlist(name)
            added = core.add_song_to_playlist(path, entry)
            msg = (f"Added \"{title}\" to {name.strip()}"
                   if added else f"Already in {name.strip()}")
        else:
            path = chosen.data()
            added = core.add_song_to_playlist(path, entry)
            name = os.path.splitext(os.path.basename(path))[0]
            msg = (f"Added \"{title}\" to {name}"
                   if added else f"Already in {name}")
        self.status_message.emit(msg)
        if added and self.on_change:
            self.on_change()

    def _available_paths(self, playlist):
        paths, order = [], {}
        for entry in playlist['entries']:
            full = os.path.join(core.PLAYLIST_DIR, entry.replace('/', os.sep))
            if os.path.exists(full):
                order[full] = len(paths)
                paths.append(full)
        return paths, order

    def _play(self, playlist, full):
        if hasattr(self, '_displayed') and self._displayed:
            paths = [r['full'] for r in self._displayed
                     if os.path.exists(r['full'])]
            start = next((i for i, r in enumerate(self._displayed)
                          if r['full'] == full), 0) if full else 0
        else:
            paths, order = self._available_paths(playlist)
            start = order.get(full, 0) if full else 0
        if not paths:
            self.status_message.emit("Nothing to play.")
            return
        self.play_request(paths, start)

    def _selected_full(self):
        row = self.song_table.currentRow()
        if row >= 0 and self.song_table.item(row, 0):
            return self.song_table.item(row, 0).data(Qt.UserRole)['full']
        return None

    def play_selected(self):
        current = self.playlist_list.currentItem()
        if not current:
            return
        playlist = current.data(Qt.UserRole)
        self._play(playlist, self._selected_full())

    def play_song(self, row, _col=None):
        current = self.playlist_list.currentItem()
        if not current:
            return
        playlist = current.data(Qt.UserRole)
        full = None
        if row >= 0 and self.song_table.item(row, 0):
            full = self.song_table.item(row, 0).data(Qt.UserRole)['full']
        self._play(playlist, full)

    def set_current_path(self, path):
        old = self.current_path
        self.current_path = path
        self._update_playing_indicator(old, path)

    def _update_playing_indicator(self, old_path, new_path):
        table = self.song_table
        old_norm = os.path.normpath(old_path) if old_path else None
        new_norm = os.path.normpath(new_path) if new_path else None
        for row, song in enumerate(self._displayed):
            s = os.path.normpath(song['full'])
            is_old = bool(old_norm and s == old_norm)
            is_new = bool(new_norm and s == new_norm)
            if not is_old and not is_new:
                continue
            item0 = table.item(row, 0)
            if not item0:
                continue
            text = item0.text()
            if is_new:
                if not text.startswith("\u25B6"):
                    item0.setText("\u25B6 " + text)
                for c in range(table.columnCount()):
                    it = table.item(row, c)
                    if it:
                        it.setForeground(QColor(style.ACCENT_HOVER))
            elif is_old:
                if text.startswith("\u25B6 "):
                    item0.setText(text[2:])
                for c in range(table.columnCount()):
                    it = table.item(row, c)
                    if it:
                        it.setForeground(QColor(style.TEXT))
        playing_rows = set()
        if new_norm:
            for row, song in enumerate(self._displayed):
                if os.path.normpath(song['full']) == new_norm:
                    playing_rows.add(row)
        if hasattr(table, '_playing_delegate'):
            table._playing_delegate.setPlayingRows(playing_rows)

    def _on_song_filter(self, _):
        if self.playlist_list.currentItem():
            self.show_playlist(self.playlist_list.currentItem(), None)

    def delete_song(self):
        row = self.song_table.currentRow()
        if row < 0 or not self.song_table.item(row, 0):
            return
        data = self.song_table.item(row, 0).data(Qt.UserRole)
        name = os.path.basename(data['entry'])
        ret = QMessageBox.question(
            self, "Delete song",
            f"Delete \"{name}\" from disk and its playlist?",
            QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        try:
            core.remove_song(data['playlist_path'], data['entry'])
        except Exception as e:
            QMessageBox.critical(self, "Delete failed", str(e))
            return
        self.status_message.emit(f"Deleted {name}")
        self.reload()

    def show_playlist_menu(self, pos):
        item = self.playlist_list.itemAt(pos)
        if item is None:
            return
        p = item.data(Qt.UserRole)
        if p is None or not p.get('path'):
            return
        menu = QMenu(self)
        act = menu.addAction("Refresh playlist")
        chosen = menu.exec_(self.playlist_list.viewport().mapToGlobal(pos))
        if chosen is act:
            self._refresh_playlist(p)

    def refresh_selected_playlist(self):
        item = self.playlist_list.currentItem()
        if item is None:
            return
        p = item.data(Qt.UserRole)
        if p is not None and p.get('path'):
            self._refresh_playlist(p)

    def _refresh_playlist(self, p):
        if not self.download_request:
            return
        name = os.path.splitext(p['name'])[0]
        url = core.get_playlist_url(p['path'])
        if not url:
            url, ok = QInputDialog.getText(
                self, "Refresh playlist",
                f"Playlist URL for \"{name}\":")
            if not ok or not url.strip():
                return
            url = url.strip()
            try:
                core.persist_playlist_url(p['path'], url)
            except Exception as e:
                QMessageBox.critical(
                    self, "Refresh failed", f"Could not save URL: {e}")
                return
        self.download_request(url)
        self.status_message.emit(f"Refreshing \"{name}\"...")


class AllSongsTab(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, play_request, on_change, parent=None):
        super().__init__(parent)
        self.play_request = play_request
        self.on_change = on_change
        self.playlists = []
        self.songs = []
        self.artists = {}
        self._displayed = []
        self.current_path = None
        self._sort_col = 2
        self._sort_order = Qt.DescendingOrder
        self._build()
        self._sort_col, self._sort_order = _load_sort(
            'allsongs', 2, Qt.DescendingOrder)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        title = QLabel("All Songs")
        title.setObjectName("navheader")
        root.addWidget(title)

        row = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Search title or artist...")
        self.filter_input.textChanged.connect(self._apply_filter)
        self.playlist_combo = QComboBox()
        self.playlist_combo.currentIndexChanged.connect(self._apply_filter)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(icons.make_icon('refresh', style.TEXT, 14))
        refresh_btn.clicked.connect(self.reload)
        row.addWidget(self.filter_input, 1)
        row.addWidget(self.playlist_combo)
        row.addWidget(refresh_btn)
        root.addLayout(row)

        self.song_table = _configure_song_table(SongTable(), 'allsongs')
        self.song_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.song_table.customContextMenuRequested.connect(self.show_context_menu)
        self.song_table.cellDoubleClicked.connect(self._play_item)
        self.song_table.horizontalHeader().sectionClicked.connect(
            self._on_header_clicked)
        root.addWidget(self.song_table, 1)

    def reload(self):
        self.playlists = [p for p in core.list_playlists() if p['path']]
        self.songs = core.list_all_songs()
        self.artists = core.get_artists(self.songs)
        current_playlist = self.playlist_combo.currentData()
        self.playlist_combo.blockSignals(True)
        self.playlist_combo.clear()
        self.playlist_combo.addItem("All playlists", None)
        for p in self.playlists:
            self.playlist_combo.addItem(
                os.path.splitext(p['name'])[0], p['name'])
        self.playlist_combo.blockSignals(False)
        if current_playlist is not None:
            idx = self.playlist_combo.findData(current_playlist)
            if idx >= 0:
                self.playlist_combo.setCurrentIndex(idx)
        self._apply_filter(self.filter_input.text())
        self.status_message.emit(f"{len(self.songs)} song(s)")

    def _visible_songs(self):
        text = self.filter_input.text().strip().lower()
        playlist_name = self.playlist_combo.currentData()
        playlist_entries = None
        if playlist_name:
            for p in self.playlists:
                if p['name'] == playlist_name:
                    playlist_entries = set(p['entries'])
                    break
        out = []
        for song in self.songs:
            if text:
                hay = ' '.join((
                    song['title'], song['source'],
                    self.artists.get(song['full'], '') or '')).lower()
                if text not in hay:
                    continue
            if playlist_entries and song['entry'] not in playlist_entries:
                continue
            out.append(song)
        return out

    def _sort_key(self, song):
        if self._sort_col == 1:
            return (self.artists.get(song['full']) or '').lower()
        if self._sort_col == 2:
            return song['mtime']
        return song['title'].lower()

    def _sort_displayed(self):
        reverse = self._sort_order == Qt.DescendingOrder
        self._displayed.sort(key=self._sort_key, reverse=reverse)

    def _on_header_clicked(self, col):
        if self._sort_col == col:
            order = (Qt.AscendingOrder
                     if self._sort_order == Qt.DescendingOrder
                     else Qt.DescendingOrder)
        else:
            order = Qt.AscendingOrder
        self._sort_col = col
        self._sort_order = order
        _settings().setValue('allsongs/sort',
                             [self._sort_col, int(self._sort_order)])
        self._apply_filter()

    def _apply_filter(self, _=None):
        self._displayed = self._visible_songs()
        self._sort_displayed()
        _set_header_arrows(self.song_table, self._sort_col, self._sort_order)
        rows = []
        for song in self._displayed:
            artist = self.artists.get(song['full'])
            rows.append({'song': song, 'artist': artist, 'full': song['full'],
                         'user_data': song['entry'], 'tooltip': song['full']})
        _populate_song_table(self.song_table, rows, self.current_path)

    def set_current_path(self, path):
        old = self.current_path
        self.current_path = path
        self._update_playing_indicator(old, path)

    def _update_playing_indicator(self, old_path, new_path):
        table = self.song_table
        old_norm = os.path.normpath(old_path) if old_path else None
        new_norm = os.path.normpath(new_path) if new_path else None
        for row, song in enumerate(self._displayed):
            s = os.path.normpath(song['full'])
            is_old = bool(old_norm and s == old_norm)
            is_new = bool(new_norm and s == new_norm)
            if not is_old and not is_new:
                continue
            item0 = table.item(row, 0)
            if not item0:
                continue
            text = item0.text()
            if is_new:
                if not text.startswith("\u25B6"):
                    item0.setText("\u25B6 " + text)
                for c in range(table.columnCount()):
                    it = table.item(row, c)
                    if it:
                        it.setForeground(QColor(style.ACCENT_HOVER))
            elif is_old:
                if text.startswith("\u25B6 "):
                    item0.setText(text[2:])
                for c in range(table.columnCount()):
                    it = table.item(row, c)
                    if it:
                        it.setForeground(QColor(style.TEXT))
        playing_rows = set()
        if new_norm:
            for row, song in enumerate(self._displayed):
                if os.path.normpath(song['full']) == new_norm:
                    playing_rows.add(row)
        if hasattr(table, '_playing_delegate'):
            table._playing_delegate.setPlayingRows(playing_rows)

    def _play_item(self, row, _col=None):
        song = self._displayed[row]
        self.play_request([s['full'] for s in self._displayed], row)

    def show_context_menu(self, pos):
        item = self.song_table.itemAt(pos)
        if item is None:
            return
        row = self.song_table.row(item)
        entry = item.data(Qt.UserRole)
        song = self._displayed[row]

        menu = QMenu(self)
        sub = menu.addMenu("Add to playlist")
        if not self.playlists:
            act = sub.addAction("No playlists yet")
            act.setEnabled(False)
        for p in self.playlists:
            name = os.path.splitext(p['name'])[0]
            act = sub.addAction(name)
            act.setData(p['path'])
        sub.addSeparator()
        new_act = sub.addAction("New playlist...")

        chosen = menu.exec_(self.song_table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is new_act:
            name, ok = QInputDialog.getText(
                self, "New playlist", "Playlist name:")
            if not ok or not name.strip():
                return
            path = core.create_playlist(name)
            added = core.add_song_to_playlist(path, entry)
            msg = (f"Added \"{song['title']}\" to {name.strip()}"
                   if added else f"Already in {name.strip()}")
        else:
            path = chosen.data()
            added = core.add_song_to_playlist(path, entry)
            name = os.path.splitext(os.path.basename(path))[0]
            msg = (f"Added \"{song['title']}\" to {name}"
                   if added else f"Already in {name}")
        self.status_message.emit(msg)
        if added and self.on_change:
            self.on_change()


class SpaceToggleFilter(QObject):
    def __init__(self, playback, parent=None):
        super().__init__(parent)
        self.playback = playback

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_Space
                and not event.modifiers()
                and QApplication.activeModalWidget() is None):
            focus = QApplication.focusWidget()
            if focus is None or not isinstance(
                    focus, (QLineEdit, QTextEdit, QPlainTextEdit,
                            QAbstractButton, QComboBox)):
                self.playback.toggle()
                return True
        return False


class QueueTab(QWidget):
    def __init__(self, play_request, parent=None):
        super().__init__(parent)
        self.play_request = play_request
        self._queue = []
        self._current = -1
        self._dirty = False
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        title = QLabel("Queue")
        title.setObjectName("navheader")
        root.addWidget(title)

        self.song_table = SongTable()
        self.song_table.setColumnCount(3)
        self.song_table.setHorizontalHeaderLabels(["Song", "Artist", "Date"])
        self.song_table.verticalHeader().setVisible(False)
        self.song_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.song_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.song_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.song_table.setShowGrid(False)
        self.song_table.setWordWrap(False)
        self.song_table.setTextElideMode(Qt.ElideRight)
        self.song_table.setAlternatingRowColors(True)
        self.song_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hh = self.song_table.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setSectionsClickable(False)
        self.song_table.setDragDropMode(QAbstractItemView.InternalMove)
        self.song_table.setDefaultDropAction(Qt.MoveAction)
        self.song_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.song_table.customContextMenuRequested.connect(
            self._show_context_menu)
        self.song_table.cellDoubleClicked.connect(self._play_item)
        self.song_table.model().rowsMoved.connect(self._on_rows_moved)
        root.addWidget(self.song_table, 1)

        btn_row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Queue")
        self.clear_btn.setIcon(icons.make_icon('trash', style.TEXT, 14))
        self.clear_btn.clicked.connect(self._clear_queue)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

    def _on_rows_moved(self):
        items = []
        for i in range(self.song_table.rowCount()):
            item = self.song_table.item(i, 0)
            if item:
                items.append(item.data(Qt.UserRole))
        self._queue = items

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self._dirty = False
            self._populate()

    def refresh_queue(self, paths=None, index=-1):
        if paths is not None:
            self._queue = list(paths)
        if index >= 0:
            self._current = index
        if self.isVisible():
            self._populate()
        else:
            self._dirty = True

    def set_current(self, path):
        for i, p in enumerate(self._queue):
            if os.path.normpath(p) == os.path.normpath(path):
                self._current = i
                break
        if self.isVisible():
            self._populate()
        else:
            self._dirty = True

    def _populate(self):
        current_path = (self._queue[self._current]
                        if 0 <= self._current < len(self._queue) else None)
        self.song_table.setRowCount(0)
        self.song_table.setRowCount(len(self._queue))
        for row, path in enumerate(self._queue):
            name = os.path.basename(path)
            display = re.sub(r"\s*\[[A-Za-z0-9_-]{6}\]\.mp3$", "", name)
            display = os.path.splitext(display)[0]
            playing = (current_path
                       and os.path.normpath(path) == os.path.normpath(current_path))
            if playing:
                display = "\u25B6 " + display
            try:
                artist = core._read_artist(path) or ''
            except Exception:
                artist = ''
            try:
                mtime = os.path.getmtime(path)
                date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d') if mtime else ''
            except Exception:
                date = ''
            items = [QTableWidgetItem(display),
                     QTableWidgetItem(artist),
                     QTableWidgetItem(date)]
            items[0].setData(Qt.UserRole, path)
            if playing:
                for it in items:
                    it.setForeground(QColor(style.ACCENT_HOVER))
            for col, it in enumerate(items):
                self.song_table.setItem(row, col, it)

    def _play_item(self, row, _col=None):
        if 0 <= row < len(self._queue):
            self.play_request(self._queue, row)

    def _show_context_menu(self, pos):
        item = self.song_table.itemAt(pos)
        if not item:
            return
        row = self.song_table.row(item)
        menu = QMenu(self)
        play_action = menu.addAction("Play from here")
        remove_action = menu.addAction("Remove from Queue")
        action = menu.exec_(
            self.song_table.viewport().mapToGlobal(pos))
        if action == play_action:
            self._play_item(row)
        elif action == remove_action:
            self.song_table.removeRow(row)
            if 0 <= row < len(self._queue):
                self._queue.pop(row)

    def _clear_queue(self):
        self.song_table.setRowCount(0)
        self._queue.clear()

_WM_APPCOMMAND = 0x0319
_WM_HOTKEY = 0x0312
_APCOMMAND_MEDIA_PLAY_PAUSE = 14
_APCOMMAND_MEDIA_NEXTTRACK = 11
_APCOMMAND_MEDIA_PREVIOUSTRACK = 12
_APCOMMAND_VOLUME_MUTE = 8

_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_MEDIA_NEXT_TRACK = 0xB0
_VK_MEDIA_PREV_TRACK = 0xB1
_MOD_NOREPEAT = 0x4000


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_ssize_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music Downloader")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.resize(1080, 780)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        sidebar = QWidget()
        sidebar.setMinimumWidth(200)
        sidebar.setStyleSheet(f"background-color: {style.BG};")
        sbox = QVBoxLayout(sidebar)
        sbox.setContentsMargins(12, 16, 12, 12)
        sbox.setSpacing(18)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        icon = QLabel()
        icon.setObjectName("brandicon")
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignCenter)
        icon.setPixmap(icons.make_pixmap('music_note', style.BG, 18))
        brand = QLabel("MUSIC DOWNLOADER")
        brand.setObjectName("brand")
        brand.setWordWrap(True)
        brand_row.addWidget(icon)
        brand_row.addWidget(brand, 1)
        sbox.addLayout(brand_row)

        self.nav = QListWidget()
        self.nav.setObjectName("sidebar")
        self.nav.addItem(QListWidgetItem(
            icons.make_icon('download', style.MUTED, 16), "Download"))
        self.nav.addItem(QListWidgetItem(
            icons.make_icon('library', style.MUTED, 16), "Library"))
        self.nav.addItem(QListWidgetItem(
            icons.make_icon('songs', style.MUTED, 16), "All Songs"))
        self.nav.addItem(QListWidgetItem(
            icons.make_icon('playlist', style.MUTED, 16), "Queue"))
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.viewport().installEventFilter(NoScrollFilter(self.nav))
        self.nav.setFixedHeight(204)
        sbox.addWidget(self.nav)
        sbox.addStretch(1)

        self.stack = QStackedWidget()
        self.download_tab = DownloadTab(on_download_finished=self.refresh_library)
        self.library_tab = LibraryTab(
            play_request=self.play_request, on_change=self.refresh_library,
            download_request=self.download_request)
        self.all_songs_tab = AllSongsTab(
            play_request=self.play_request, on_change=self.refresh_library)
        self.queue_tab = QueueTab(play_request=self.play_request)
        self.stack.addWidget(self.download_tab)
        self.stack.addWidget(self.library_tab)
        self.stack.addWidget(self.all_songs_tab)
        self.stack.addWidget(self.queue_tab)

        self.body_splitter = QSplitter(Qt.Horizontal)
        self.body_splitter.setChildrenCollapsible(False)
        self.body_splitter.setHandleWidth(8)
        self.body_splitter.addWidget(sidebar)
        self.body_splitter.addWidget(self.stack)
        self.body_splitter.setSizes([210, 870])
        body.addWidget(self.body_splitter, 1)
        root.addLayout(body, 1)

        self.player_bar = PlayerBar()
        self.player_bar.current_track.connect(self.library_tab.set_current_path)
        self.player_bar.current_track.connect(self.all_songs_tab.set_current_path)
        root.addWidget(self.player_bar)

        self.setCentralWidget(central)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.library_tab.reload()
        self.all_songs_tab.reload()

        self.player_bar.queue_changed.connect(self._sync_queue)
        self.player_bar.current_track.connect(self._sync_queue_current)

        settings = QSettings("MusicDownloader", "MusicDownloader")
        geom = settings.value('window/geometry')
        if geom:
            self.restoreGeometry(geom)
        body_sp = settings.value('window/splitter_body')
        if body_sp:
            self.body_splitter.restoreState(body_sp)
        if settings.value('player/queue'):
            self.player_bar.restore_state(settings)
            was_playing = self.player_bar.playback.current_path() is not None
            if was_playing:
                self._sync_queue()
                self._sync_queue_current(self.player_bar.playback.current_path())

        self._space_filter = SpaceToggleFilter(self.player_bar.playback, self)
        QApplication.instance().installEventFilter(self._space_filter)

        self._hotkey_ids = []
        user32 = ctypes.windll.user32
        hwnd = int(self.winId())
        for i, vk in enumerate([
            _VK_MEDIA_PLAY_PAUSE, _VK_MEDIA_NEXT_TRACK, _VK_MEDIA_PREV_TRACK,
        ], 1):
            if user32.RegisterHotKey(hwnd, i, _MOD_NOREPEAT, vk):
                self._hotkey_ids.append(i)

    def refresh_library(self):
        self.library_tab.reload()
        self.all_songs_tab.reload()

    def download_request(self, url):
        self.download_tab.download(url)

    def play_request(self, paths, index):
        self.player_bar.play_files(paths, index)

    def _sync_queue(self):
        pm = self.player_bar.playback
        self.queue_tab.refresh_queue(pm.queue(), pm.queue_index())

    def _sync_queue_current(self, path):
        self.queue_tab.set_current(path)

    def closeEvent(self, event):
        user32 = ctypes.windll.user32
        hwnd = int(self.winId())
        for hid in self._hotkey_ids:
            user32.UnregisterHotKey(hwnd, hid)
        settings = QSettings("MusicDownloader", "MusicDownloader")
        self.player_bar.save_state(settings)
        settings.setValue('window/geometry', self.saveGeometry())
        settings.setValue('window/splitter_body', self.body_splitter.saveState())
        settings.setValue('player/loop', self.player_bar.playback.loop_mode())
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_F11, Qt.Key_Escape):
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            try:
                msg = _MSG.from_address(int(message))
                if msg.message == _WM_HOTKEY:
                    pm = self.player_bar.playback
                    wid = msg.wParam
                    if wid == 1:
                        pm.toggle()
                    elif wid == 2:
                        pm.next()
                    elif wid == 3:
                        pm.previous()
                    return True, 0
                if msg.message == _WM_APPCOMMAND:
                    cmd = (msg.lParam >> 16) & 0xFFFF
                    pm = self.player_bar.playback
                    if cmd == _APPCOMMAND_MEDIA_PLAY_PAUSE:
                        pm.toggle()
                        return True, 0
                    elif cmd == _APPCOMMAND_MEDIA_NEXTTRACK:
                        pm.next()
                        return True, 0
                    elif cmd == _APPCOMMAND_MEDIA_PREVIOUSTRACK:
                        pm.previous()
                        return True, 0
                    elif cmd == _APPCOMMAND_VOLUME_MUTE:
                        from PyQt5.QtCore import QTimer
                        QTimer.singleShot(0, self.player_bar._toggle_mute)
                        return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Music Downloader")
    app.setStyle("fusion")
    app.setStyleSheet(style.QSS)
    win = MainWindow()
    win.showFullScreen()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
