import os

from PyQt5.QtCore import QObject, Qt, QRect, QRectF, QSize, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                         QPainter, QPainterPath, QPixmap)
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

import core
import icons
import style


def _fmt(ms):
    s = max(0, int(ms / 1000))
    return f"{s // 60}:{s % 60:02d}"


class SeekBar(QWidget):
    seekRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max = 1
        self._value = 0
        self._dragging = False
        self._hover_ms = None
        self.setMouseTracking(True)
        self.setFixedHeight(26)
        self.setMinimumWidth(120)

    def setMaximum(self, ms):
        self._max = max(1, int(ms))
        self._value = min(self._value, self._max)
        self.update()

    def setValue(self, ms):
        if not self._dragging:
            self._value = min(max(0, int(ms)), self._max)
            self.update()

    def value(self):
        return self._value

    def _x_from_ms(self, ms):
        w = self.width() - 12
        return 6 + int(w * (ms / self._max))

    def _ms_from_x(self, x):
        w = self.width() - 12
        frac = (x - 6) / w if w > 0 else 0.0
        frac = min(1.0, max(0.0, frac))
        return int(frac * self._max)

    def _track_rect(self):
        return QRectF(6, self.height() / 2 - 2, self.width() - 12, 4)

    def _emit_seek(self):
        if self._hover_ms is not None:
            self._value = self._hover_ms
        self.seekRequested.emit(self._value)

    def mousePressEvent(self, event):
        self._dragging = True
        self._hover_ms = self._ms_from_x(event.pos().x())
        self._value = self._hover_ms
        self._emit_seek()
        self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._hover_ms = self._ms_from_x(event.pos().x())
        if self._dragging:
            self._value = self._hover_ms
            self.seekRequested.emit(self._value)
        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hover_ms = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        track = self._track_rect()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style.SURFACE3))
        p.drawRoundedRect(track, 2, 2)

        if self._value > 0:
            filled = QRectF(track)
            filled.setWidth(track.width() * (self._value / self._max))
            p.setBrush(QColor(style.ACCENT))
            p.drawRoundedRect(filled, 2, 2)

        thumb_x = self._x_from_ms(self._value if not self._dragging else (self._hover_ms or self._value))
        p.setBrush(QColor(style.TEXT))
        p.drawEllipse(QRectF(thumb_x - 5, self.height() / 2 - 5, 10, 10))

        if self._hover_ms is not None:
            bubble_x = self._x_from_ms(self._hover_ms)
            text = _fmt(self._hover_ms)
            font = QFont(self.font())
            font.setPointSize(9)
            fm = QFontMetrics(font)
            tw = fm.horizontalAdvance(text) + 14
            bh = 22
            bx = min(max(bubble_x - tw / 2, 2), self.width() - tw - 2)
            by = 0
            bubble = QRectF(bx, by, tw, bh)
            p.setBrush(QColor(style.SURFACE3))
            p.drawRoundedRect(bubble, 5, 5)
            p.setPen(QColor(style.TEXT))
            p.setFont(font)
            p.drawText(bubble, Qt.AlignCenter, text)
        p.end()


def _cover_art(pix, w, h, radius=6):
    if w <= 0 or h <= 0:
        return pix
    pm = pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    out = QPixmap(w, h)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, radius, radius)
    p.setClipPath(path)
    p.drawPixmap((w - pm.width()) // 2, (h - pm.height()) // 2, pm)
    top_h = int(h * 0.4)
    g = QLinearGradient(0, 0, 0, top_h)
    g.setColorAt(0.0, QColor(0, 0, 0, 170))
    g.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(QRectF(0, 0, w, top_h), QBrush(g))
    p.end()
    return out


class TrackMetaWorker(QThread):
    done = pyqtSignal(str, str, dict)

    def __init__(self, mp3_path, parent=None):
        super().__init__(parent)
        self.mp3_path = mp3_path

    def run(self):
        tags = core.probe_tags(self.mp3_path)
        cover = core.extract_cover_path(self.mp3_path)
        self.done.emit(self.mp3_path, cover, tags)


class VolumeSlider(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 70
        self._max = 100
        self._dragging = False
        self._hover_x = None
        self.setMouseTracking(True)
        self.setFixedHeight(26)
        self.setFixedWidth(110)

    def setValue(self, v):
        if not self._dragging:
            v = max(0, min(self._max, int(v)))
            changed = v != self._value
            self._value = v
            self.update()
            if changed:
                self.valueChanged.emit(self._value)

    def value(self):
        return self._value

    def _x_from_val(self, v):
        w = self.width() - 12
        return 6 + int(w * (v / self._max)) if self._max > 0 else 6

    def _val_from_x(self, x):
        w = self.width() - 12
        frac = (x - 6) / w if w > 0 else 0.0
        frac = min(1.0, max(0.0, frac))
        return int(frac * self._max)

    def _track_rect(self):
        return QRectF(6, self.height() / 2 - 1.5, self.width() - 12, 3)

    def mousePressEvent(self, event):
        self._dragging = True
        self._hover_x = event.pos().x()
        self._value = self._val_from_x(self._hover_x)
        self.valueChanged.emit(self._value)
        self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._hover_x = event.pos().x()
        if self._dragging:
            self._value = self._val_from_x(self._hover_x)
            self.valueChanged.emit(self._value)
        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hover_x = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        track = self._track_rect()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style.BORDER))
        p.drawRoundedRect(track, 1.5, 1.5)

        if self._value > 0:
            filled = QRectF(track)
            filled.setWidth(track.width() * (self._value / self._max))
            p.setBrush(QColor(style.MUTED))
            p.drawRoundedRect(filled, 1.5, 1.5)

        if self._hover_x is not None:
            hover_val = self._val_from_x(self._hover_x)
            bubble_x = self._x_from_val(hover_val)
            text = f"{hover_val}%"
            font = QFont(self.font())
            font.setPointSize(9)
            fm = QFontMetrics(font)
            tw = fm.horizontalAdvance(text) + 14
            bh = 22
            bx = min(max(bubble_x - tw / 2, 2), self.width() - tw - 2)
            by = 0
            bubble = QRectF(bx, by, tw, bh)
            p.setBrush(QColor(style.SURFACE3))
            p.drawRoundedRect(bubble, 5, 5)
            p.setPen(QColor(style.TEXT))
            p.setFont(font)
            p.drawText(bubble, Qt.AlignCenter, text)
        p.end()


class PlaybackManager(QObject):
    track_changed = pyqtSignal(str)
    state_changed = pyqtSignal(object)
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    queue_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths = []
        self._index = -1
        self._loop_mode = 'none'
        self._pending_pos = None
        self.player = QMediaPlayer(self)
        self.player.stateChanged.connect(self._on_state)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.mediaStatusChanged.connect(self._on_media_status)

    def _on_state(self, state):
        self.state_changed.emit(state)

    def _on_position(self, ms):
        self.position_changed.emit(int(ms))

    def _on_duration(self, ms):
        self.duration_changed.emit(int(ms))

    def _on_media_status(self, status):
        if status == QMediaPlayer.LoadedMedia and self._pending_pos is not None:
            pos, self._pending_pos = self._pending_pos, None
            dur = self.player.duration()
            if dur > 0:
                pos = max(0, min(pos, dur))
            self.player.setPosition(pos)
        if status == QMediaPlayer.EndOfMedia:
            if self._loop_mode == 'current':
                self.player.setPosition(0)
                self.player.play()
            else:
                self.next()

    def play_files(self, paths, start=0):
        self._paths = list(paths)
        self._index = max(0, start) if paths else -1
        self._load_current()
        self.queue_changed.emit()

    def _load_current(self):
        self._pending_pos = None
        if not (0 <= self._index < len(self._paths)):
            self.player.stop()
            return
        self.player.setMedia(QMediaContent(
            QUrl.fromLocalFile(self._paths[self._index])))
        self.player.play()
        self.track_changed.emit(self._paths[self._index])

    def current_path(self):
        if 0 <= self._index < len(self._paths):
            return self._paths[self._index]
        return None

    def toggle(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def is_playing(self):
        return self.player.state() == QMediaPlayer.PlayingState

    def set_loop_mode(self, mode):
        self._loop_mode = mode

    def loop_mode(self):
        return self._loop_mode

    def next(self):
        if self._loop_mode == 'playlist' and len(self._paths) > 1:
            self._index = (self._index + 1) % len(self._paths)
            self._load_current()
        elif self._index < len(self._paths) - 1:
            self._index += 1
            self._load_current()

    def previous(self):
        if self._index > 0:
            self._index -= 1
            self._load_current()

    def seek(self, ms):
        self.player.setPosition(ms)

    def set_volume(self, value):
        self.player.setVolume(value)

    def queue(self):
        return list(self._paths)

    def queue_index(self):
        return self._index

    def reorder_queue(self, new_paths):
        playing = self.current_path()
        self._paths = list(new_paths)
        if not self._paths:
            self._index = -1
            self.player.stop()
        elif playing and playing in self._paths:
            self._index = self._paths.index(playing)
        elif playing:
            # The current track was dropped from the queue: advance into the
            # same slot (now the next track) instead of leaving a dead index.
            self._index = min(self._index, len(self._paths) - 1)
            self._load_current()
        else:
            self._index = -1
        self.queue_changed.emit()

    def play_at_index(self, idx):
        if 0 <= idx < len(self._paths):
            self._index = idx
            self._load_current()

    def save_state(self, settings):
        settings.setValue('player/queue', self._paths)
        settings.setValue('player/index', self._index)
        settings.setValue('player/position', self.player.position())
        settings.setValue('player/loop', self._loop_mode)

    def restore_state(self, settings):
        paths = settings.value('player/queue', [])
        if isinstance(paths, str):
            # QSettings collapses one-element QStringList to a plain str.
            paths = [paths] if paths else []
        idx = int(settings.value('player/index', -1))
        pos = int(settings.value('player/position', 0))
        loop = settings.value('player/loop', 'none')
        self._loop_mode = loop if loop in ('none', 'playlist', 'current') else 'none'
        if paths and 0 <= idx < len(paths):
            self._paths = list(paths)
            self._index = idx
            self.player.setMedia(QMediaContent(
                QUrl.fromLocalFile(self._paths[self._index])))
            # Seeks are ignored until the media finishes loading; the
            # position is applied in _on_media_status on LoadedMedia.
            self._pending_pos = pos if pos > 0 else None
            self.track_changed.emit(self._paths[self._index])
            self.queue_changed.emit()
            return True
        return False


class PlayerBar(QWidget):
    current_track = pyqtSignal(str)
    queue_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.playback = PlaybackManager(self)
        self._cover = None
        self._build()
        self._connect()

    def _build(self):
        self.setFixedHeight(88)
        self.setObjectName("playerbar")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {style.BORDER};")
        outer.addWidget(sep)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(4)

        left = QWidget()
        left.setObjectName("playerLeft")
        lbox = QHBoxLayout(left)
        lbox.setContentsMargins(0, 0, 0, 0)
        lbox.setSpacing(10)
        self.cover_label = QLabel()
        self.cover_label.setObjectName("cover")
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setPixmap(icons.make_pixmap('music_note', style.MUTED, 24))
        self.cover_label.setFixedWidth(64)
        self.cover_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.meta_label = QLabel("Nothing playing")
        self.meta_label.setObjectName("playermeta")
        self.meta_label.setWordWrap(True)
        meta = QVBoxLayout()
        meta.setContentsMargins(0, 6, 0, 0)
        meta.setSpacing(0)
        meta.addWidget(self.meta_label)
        meta.addStretch(1)
        lbox.addWidget(self.cover_label)
        lbox.addLayout(meta, 1)

        center = QWidget()
        center.setObjectName("playerCenter")
        cbox = QVBoxLayout(center)
        cbox.setContentsMargins(0, 0, 0, 0)
        cbox.setSpacing(6)
        cbox.addSpacing(6)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.prev_btn = QToolButton()
        self.prev_btn.setObjectName("iconbtn")
        self.prev_btn.setFixedSize(34, 34)
        self.prev_btn.setToolTip("Previous")
        self.prev_btn.setIcon(icons.make_icon('previous', style.TEXT, 18))
        self.prev_btn.setIconSize(QSize(18, 18))
        self.play_btn = QToolButton()
        self.play_btn.setObjectName("iconbtn")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setProperty("play", True)
        self.play_btn.setToolTip("Play / Pause")
        self.play_btn.setIcon(icons.make_icon('play', style.ACCENT, 20))
        self.play_btn.setIconSize(QSize(20, 20))
        self.next_btn = QToolButton()
        self.next_btn.setObjectName("iconbtn")
        self.next_btn.setFixedSize(34, 34)
        self.next_btn.setToolTip("Next")
        self.next_btn.setIcon(icons.make_icon('next', style.TEXT, 18))
        self.next_btn.setIconSize(QSize(18, 18))
        controls.addStretch(1)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)
        controls.addStretch(1)
        cbox.addLayout(controls)

        seekrow = QHBoxLayout()
        seekrow.setSpacing(8)
        self.time_label = QLabel("0:00")
        self.time_label.setObjectName("muted")
        self.time_label.setFixedWidth(40)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.seek_bar = SeekBar()
        self.total_label = QLabel("0:00")
        self.total_label.setObjectName("muted")
        self.total_label.setFixedWidth(40)
        self.total_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        seekrow.addWidget(self.time_label)
        seekrow.addWidget(self.seek_bar, 1)
        seekrow.addWidget(self.total_label)
        cbox.addLayout(seekrow)

        right = QWidget()
        right.setObjectName("playerRight")
        rbox = QHBoxLayout(right)
        rbox.setContentsMargins(8, 0, 8, 0)
        rbox.setSpacing(6)
        rbox.setAlignment(Qt.AlignVCenter)
        self.loop_btn = QToolButton()
        self.loop_btn.setObjectName("iconbtn")
        self.loop_btn.setFixedSize(34, 34)
        self.loop_btn.setIconSize(QSize(18, 18))
        self.vol_btn = QToolButton()
        self.vol_btn.setObjectName("iconbtn")
        self.vol_btn.setFixedSize(26, 26)
        self.vol_btn.setIcon(icons.make_icon('volume', style.MUTED, 16))
        self.vol_btn.setIconSize(QSize(16, 16))
        self.vol_btn.setCursor(Qt.PointingHandCursor)
        self.vol_btn.setToolTip("Mute / Unmute")
        self.volume_slider = VolumeSlider()
        self.volume_slider.setValue(70)
        rbox.addWidget(self.loop_btn)
        rbox.addWidget(self.vol_btn)
        rbox.addWidget(self.volume_slider)

        self._splitter.addWidget(left)
        self._splitter.addWidget(center)
        self._splitter.addWidget(right)
        self._splitter.setSizes([240, 540, 180])

        outer.addWidget(self._splitter)

    def _connect(self):
        pm = self.playback
        pm.state_changed.connect(self._on_state)
        pm.position_changed.connect(self._on_position)
        pm.duration_changed.connect(self._on_duration)
        pm.track_changed.connect(self._on_track)
        pm.queue_changed.connect(self.queue_changed)
        self.play_btn.clicked.connect(pm.toggle)
        self.prev_btn.clicked.connect(pm.previous)
        self.next_btn.clicked.connect(pm.next)
        self.seek_bar.seekRequested.connect(pm.seek)
        self.seek_bar.seekRequested.connect(lambda ms: self.time_label.setText(_fmt(ms)))
        self.volume_slider.valueChanged.connect(pm.set_volume)
        self.volume_slider.valueChanged.connect(self._on_volume)
        self.loop_btn.clicked.connect(self._cycle_loop)
        self.vol_btn.clicked.connect(self._toggle_mute)
        pm.set_volume(self.volume_slider.value())
        self._update_loop_btn()

    def _cycle_loop(self):
        order = ['none', 'playlist', 'current']
        idx = order.index(self.playback.loop_mode())
        self.playback.set_loop_mode(order[(idx + 1) % len(order)])
        self._update_loop_btn()

    def _update_loop_btn(self):
        mode = self.playback.loop_mode()
        if mode == 'current':
            name, tip = 'repeat_one', "Loop: Current"
        elif mode == 'playlist':
            name, tip = 'loop', "Loop: Playlist"
        else:
            name, tip = 'loop', "Loop: Off"
        color = style.ACCENT if mode != 'none' else style.MUTED
        self.loop_btn.setIcon(icons.make_icon(name, color, 16))
        self.loop_btn.setToolTip(tip)

    def play_files(self, paths, start=0):
        self.playback.play_files(paths, start)

    def _on_state(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setIcon(icons.make_icon('pause', style.ACCENT, 20))
        else:
            self.play_btn.setIcon(icons.make_icon('play', style.ACCENT, 20))

    def _on_volume(self, value):
        name = 'volume_mute' if value == 0 else 'volume'
        self.vol_btn.setIcon(icons.make_icon(name, style.MUTED, 16))

    def _toggle_mute(self):
        if self.volume_slider.value() > 0:
            self._saved_vol = self.volume_slider.value()
            self.volume_slider.setValue(0)
        else:
            self.volume_slider.setValue(getattr(self, '_saved_vol', 70))

    def _on_position(self, ms):
        self.seek_bar.setValue(ms)
        self.time_label.setText(_fmt(ms))

    def _on_duration(self, ms):
        self.seek_bar.setMaximum(max(0, ms))
        self.total_label.setText(_fmt(ms))

    def _on_track(self, path):
        self.current_track.emit(path)
        self._current_path = path
        display = core.display_title(os.path.basename(path))
        self._set_meta(display, "")
        self.cover_label.setPixmap(icons.make_pixmap('music_note', style.MUTED, 24))
        self._cover = None
        # Parented to self: the thread object cannot be garbage-collected
        # while running, so no ref bookkeeping is needed.
        worker = TrackMetaWorker(path, self)
        worker.done.connect(self._on_meta)
        worker.start()

    def _elide_2lines(self, text, font_size):
        if not text:
            return text
        w = max(self.meta_label.width() - 4, 80)
        fm = QFontMetrics(QFont(self.meta_label.font().family(), font_size))
        rect = fm.boundingRect(QRect(0, 0, w, 0), Qt.TextWordWrap, text)
        if rect.height() <= fm.lineSpacing() * 2:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            r = fm.boundingRect(QRect(0, 0, w, 0), Qt.TextWordWrap, text[:mid])
            if r.height() <= fm.lineSpacing() * 2:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo].rstrip() + "\u2026"

    def _set_meta(self, title, artist, playlists=None):
        t = self._elide_2lines(title or "Nothing playing", 15)
        t = t.replace("&", "&amp;").replace("<", "&lt;")
        a = self._elide_2lines(artist or "", 13)
        a = a.replace("&", "&amp;").replace("<", "&lt;")
        lines = [f"<span style='font-size:15px;font-weight:600;'>{t}</span>"]
        if a:
            lines.append(
                f"<br><span style='font-size:13px;color:{style.MUTED};"
                f"margin-top:-3px;'>{a}</span>")
        if playlists is not None:
            if playlists:
                pl = ", ".join(playlists)
                pl_line = f"In: {pl}"
            else:
                pl_line = "Not in any playlist"
            pl_line = self._elide_2lines(pl_line, 11)
            lines.append(
                f"<br><span style='font-size:11px;color:{style.FAINT};"
                f"margin-top:-3px;'>{pl_line}</span>")
        self.meta_label.setText("".join(lines))

    def _on_meta(self, path, cover, tags):
        if path != self._current_path:
            return
        if cover:
            pix = QPixmap(cover)
            if not pix.isNull():
                self.cover_label.setPixmap(
                    _cover_art(pix, self.cover_label.width(),
                               self.cover_label.height()))
                self._cover = cover
        artist = tags.get('artist') or tags.get('albumartist') or ''
        title = core.display_title(os.path.basename(path))
        playlists = core.playlists_for_song(path)
        self._set_meta(title, artist, playlists)

    def save_state(self, settings):
        self.playback.save_state(settings)
        settings.setValue('player/volume', self.volume_slider.value())
        settings.setValue('player/splitter', self._splitter.saveState())

    def restore_state(self, settings):
        self.volume_slider.setValue(int(settings.value('player/volume', 70)))
        sp = settings.value('player/splitter')
        if sp:
            self._splitter.restoreState(sp)
        ok = self.playback.restore_state(settings)
        self._update_loop_btn()
        return ok
