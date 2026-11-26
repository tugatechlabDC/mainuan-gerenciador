#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Mainuan Gerenciador Tarefas - interface gráfica (Qt)."""
import os
import sys
import time
import shlex
import shutil
import signal
import subprocess
import datetime
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n  # noqa: E402
from i18n import _, N_  # noqa: E402

import psutil  # noqa: E402
import sysinfo as S  # noqa: E402
import vt  # noqa: E402

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, Signal
except ImportError:  # alternativa: PyQt5
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import Qt, pyqtSignal as Signal


def _system_lang():
    """Idioma do sistema: variáveis de ambiente (LANGUAGE/LC_*/LANG) e, em último caso, o locale do Qt."""
    lang = i18n.detect_lang(default=None)
    if lang is None:
        try:
            lang = i18n._norm(QtCore.QLocale.system().name())
        except Exception:  # noqa: BLE001
            lang = None
    return lang or "en"


i18n.set_lang(_system_lang())  # automático, sem menu de idiomas
S.set_decimal("." if i18n.get_lang() == "en" else ",")

QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
LIBDIR = os.path.dirname(os.path.abspath(__file__))
HELPER = "/usr/lib/mainuan-gerenciador-tarefas/helper.py"
ROLE_PIDS = Qt.UserRole + 1

# ---- Paletas: azul do ícone (cyan Kora, #21D0DC -> #236C88); tema claro com o branco padrão ----
THEMES = {
    "dark": dict(BG="#0A1820", PANEL="#0F212B", CARD="#132D3B", BORDER="#1E4052", TEXT="#E8F6F9",
                 MUTED="#8DB0BF", ACCENT="#21D0DC", ACCENT2="#22A8BA", DEEP="#236C88",
                 WARN="#F5B83D", DANGER="#F0604D", OK="#2ED8A0", ONACC="#FFFFFF",
                 HOVER="#0F212B", SEL="#132D3B",
                 TAB="#236C88", TABSEL0="#2790A9", TABSEL1="#236C88", TABTEXT="#FFFFFF", TABBORDER="#21D0DC"),
    "light": dict(BG="#EAF5F6", PANEL="#F7FCFC", CARD="#FFFFFF", BORDER="#C3DEE1", TEXT="#0B2A2E",
                  MUTED="#527C82", ACCENT="#1E9BB3", ACCENT2="#22A8BA", DEEP="#236C88",
                  WARN="#B87400", DANGER="#CF3A2A", OK="#0E8F66", ONACC="#FFFFFF",
                  HOVER="#F7FCFC", SEL="#FFFFFF",
                  TAB="#22A8BA", TABSEL0="#21D0DC", TABSEL1="#22A8BA", TABTEXT="#000000", TABBORDER="#236C88"),
}
T = dict(THEMES["dark"])
FONT = "sans-serif"

ANSI_DARK = ["#1B2B30", "#F0604D", "#2ED8A0", "#F5B83D", "#4DA3FF", "#C77DFF", "#21D0DC", "#CFE6E8",
             "#4A6A70", "#FF8A7A", "#6BF0C4", "#FFD36B", "#7DBEFF", "#DDA6FF", "#6FE3EC", "#FFFFFF"]
ANSI_LIGHT = ["#0B2A2E", "#CF3A2A", "#0E8F66", "#B87400", "#1F6FD1", "#8E44C9", "#1E8FA8", "#5F7F84",
              "#3F5F64", "#E5533F", "#14B37F", "#D18A00", "#3C8BEB", "#A95FE0", "#22A8BA", "#8AA5A9"]


def set_theme(dark):
    T.clear()
    T.update(THEMES["dark" if dark else "light"])
    T["dark"] = dark


T["dark"] = True


def build_qss():
    return Template("""
QWidget { background: $BG; color: $TEXT; font-family: "$FONT"; font-size: 10pt; }
QLabel { background: transparent; }
QLabel#h1 { font-size: 20pt; font-weight: bold; }
QLabel#h2 { font-size: 12pt; color: $MUTED; }
QLabel#cap { color: $MUTED; font-size: 9pt; }
QLabel#val { font-size: 17pt; }
QLabel#ikey { color: $MUTED; }
QLabel#muted { color: $MUTED; }
QLabel#restitle { font-size: 12pt; }
QFrame#card { background: $CARD; border: 1px solid $BORDER; border-radius: 12px; }
QFrame#resitem { background: transparent; border: none; border-left: 3px solid transparent; }
QFrame#resitem[sel="true"] { background: $SEL; border-left: 3px solid $ACCENT; }
QFrame#resitem:hover { background: $HOVER; }
QFrame#banner { background: $CARD; border: 1px solid $WARN; border-radius: 10px; }
QMenuBar { background: $PANEL; border-bottom: 1px solid $BORDER; }
QMenuBar::item { padding: 5px 12px; background: transparent; }
QMenuBar::item:selected { background: $SEL; color: $ACCENT; }
QMenu { background: $PANEL; border: 1px solid $BORDER; padding: 4px; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background: $DEEP; color: white; }
QMenu::separator { height: 1px; background: $BORDER; margin: 4px 8px; }
QTabWidget::pane { border: none; border-top: 1px solid $BORDER; }
QTabBar { background: $BG; }
QTabBar::tab { background: $TAB; color: $TABTEXT; font-weight: bold; padding: 8px 14px; border: 1px solid $BORDER;
  border-bottom: none; margin-right: 2px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:hover { background: $TABSEL0; }
QTabBar::tab:selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $TABSEL0, stop:1 $TABSEL1);
  color: $TABTEXT; border-top: 3px solid $TABBORDER; }
QTabBar QToolButton { background: $PANEL; border: 1px solid $BORDER; border-radius: 6px; }
QPushButton { background: $SEL; border: 1px solid $BORDER; border-radius: 8px; padding: 7px 16px; }
QPushButton:hover { border-color: $ACCENT2; }
QPushButton:disabled { color: $MUTED; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $ACCENT2, stop:1 $DEEP);
  color: $ONACC; font-weight: bold; border: none; }
QPushButton#primary:hover { background: $ACCENT2; }
QPushButton#primary:disabled { background: $BORDER; color: $MUTED; }
QPushButton#danger { border-color: $DANGER; color: $DANGER; }
QTreeWidget, QTableWidget { background: $PANEL; alternate-background-color: $BG; border: 1px solid $BORDER;
  border-radius: 8px; selection-background-color: $DEEP; selection-color: white; outline: 0; }
QTreeWidget::item { padding: 3px 0; }
QHeaderView::section { background: $SEL; color: $MUTED; border: none; border-right: 1px solid $BORDER;
  padding: 6px; font-weight: normal; }
QLineEdit, QComboBox, QSpinBox { background: $PANEL; border: 1px solid $BORDER; border-radius: 6px; padding: 5px 8px; min-height: 24px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: $BORDER; border-radius: 6px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $ACCENT2; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: $BORDER; border-radius: 6px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: $ACCENT2; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QCheckBox { spacing: 8px; background: transparent; }
QMessageBox, QDialog, QInputDialog { background: $BG; }
QToolTip { background: $PANEL; color: $TEXT; border: 1px solid $BORDER; }
""").substitute(FONT=FONT, **{k: v for k, v in T.items() if k != "dark"})


def pick_font():
    try:
        fams = set(QtGui.QFontDatabase.families())
    except TypeError:
        fams = set(QtGui.QFontDatabase().families())
    for f in ("Inter", "Noto Sans", "Ubuntu", "Open Sans", "Cantarell", "Segoe UI", "DejaVu Sans"):
        if f in fams:
            return f
    return "sans-serif"


def pick_mono():
    try:
        fams = set(QtGui.QFontDatabase.families())
    except TypeError:
        fams = set(QtGui.QFontDatabase().families())
    for f in ("DejaVu Sans Mono", "Noto Sans Mono", "Ubuntu Mono", "Liberation Mono", "Hack",
              "Fira Mono", "Source Code Pro", "Monospace"):
        if f in fams:
            return f
    return "monospace"


def kde_is_dark():
    path = os.path.expanduser("~/.config/kdeglobals")
    try:
        sec = ""
        with open(path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    sec = line
                elif sec == "[Colors:Window]" and line.startswith("BackgroundNormal="):
                    r, g, b = [int(x) for x in line.split("=", 1)[1].split(",")[:3]]
                    return (0.299 * r + 0.587 * g + 0.114 * b) < 128
    except (OSError, ValueError):
        pass
    return None


def detect_dark():
    d = kde_is_dark()
    if d is not None:
        return d
    if shutil.which("gsettings"):
        out = S.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], timeout=2)
        if "dark" in out:
            return True
        if "default" in out or "light" in out:
            return False
    try:
        cs = QtGui.QGuiApplication.styleHints().colorScheme()
        if cs == Qt.ColorScheme.Dark:
            return True
        if cs == Qt.ColorScheme.Light:
            return False
    except (AttributeError, TypeError):
        pass
    return QtWidgets.QApplication.palette().color(QtGui.QPalette.Window).lightness() < 128


def logo_path():
    for p in ("/usr/share/icons/hicolor/256x256/apps/mainuan-gerenciador-tarefas.png",
              os.path.join(LIBDIR, "logo.png")):
        if os.path.exists(p):
            return p
    return ""


def qc(key, alpha=None):
    c = QtGui.QColor(T[key] if key in T else key)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def heat(pct):
    """Cor de fundo (turquesa) proporcional à utilização, como o Windows faz com o amarelo."""
    pct = max(0.0, min(100.0, pct))
    if pct < 0.5:
        return QtGui.QBrush()
    return QtGui.QBrush(qc("ACCENT", int(30 + pct * 1.9)))


def pct_txt(v):
    return "%s%%" % S.num(v, 1 if v < 10 else 0)


def disk_txt(bps):
    return "%s MB/s" % S.num(bps / 1048576.0, 1)


def user_visible_status(st):
    return {"stopped": _("Parado"), "zombie": _("Zombie")}.get(st, "")


PRIO_NICE = ((N_("Alta"), -15), (N_("Acima do normal"), -5), (N_("Normal"), 0),
             (N_("Abaixo do normal"), 5), (N_("Baixa"), 15))


# =========================================================================== widgets básicos
class Task(QtCore.QThread):
    done = Signal(object)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self.fn, self.args = fn, args

    def run(self):
        try:
            r = self.fn(*self.args)
        except Exception as e:  # noqa: BLE001
            r = e
        self.done.emit(r)


class Graph(QtWidgets.QWidget):
    """Gráfico de linha dos últimos 60 segundos (estilo Gerenciador de Tarefas)."""

    def __init__(self, series, maxv=100.0, auto=False, grid=True, minh=120, parent=None):
        super().__init__(parent)
        self.series = series          # lista de (deque, chave de cor do tema)
        self.base = float(maxv)
        self.auto = auto
        self.grid = grid
        self.setMinimumHeight(minh)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

    def scale(self):
        if not self.auto:
            return self.base
        peak = max((max(s) for s, _k in self.series), default=0.0)
        m = self.base
        while m < peak * 1.05:
            m *= 2
        return m

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width() - 1, self.height() - 1
        p.fillRect(0, 0, w + 1, h + 1, qc("PANEL"))
        if self.grid:
            gp = QtGui.QPen(qc("BORDER", 150))
            gp.setWidth(1)
            p.setPen(gp)
            for i in range(1, 10):
                x = int(w * i / 10.0)
                y = int(h * i / 10.0)
                p.drawLine(x, 0, x, h)
                p.drawLine(0, y, w, y)
        mx = self.scale() or 1.0
        for data, key in self.series:
            vals = list(data)
            n = len(vals)
            if n < 2:
                continue
            step = w / float(n - 1)
            path = QtGui.QPainterPath()
            line = QtGui.QPainterPath()
            path.moveTo(0, h)
            for i, v in enumerate(vals):
                x = i * step
                y = h - min(1.0, v / mx) * (h - 2) - 1
                path.lineTo(x, y)
                if i == 0:
                    line.moveTo(x, y)
                else:
                    line.lineTo(x, y)
            path.lineTo(w, h)
            path.closeSubpath()
            p.fillPath(path, qc(key, 60))
            pen = QtGui.QPen(qc(key))
            pen.setWidthF(1.6)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(line)
        p.setPen(QtGui.QPen(qc("ACCENT2")))
        p.setBrush(Qt.NoBrush)
        p.drawRect(0, 0, w, h)


class CompBar(QtWidgets.QWidget):
    """Barra de composição da memória."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parts = []
        self.setFixedHeight(34)

    def set_parts(self, parts):
        self.parts = parts
        self.update()

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        w, h = self.width() - 1, self.height() - 1
        p.fillRect(0, 0, w + 1, h + 1, qc("PANEL"))
        x = 0.0
        for frac, key in self.parts:
            seg = max(0.0, frac) * w
            if seg > 0.5:
                p.fillRect(QtCore.QRectF(x, 1, seg, h - 1), qc(key, 170))
                sep = QtGui.QPen(qc("BORDER"))
                p.setPen(sep)
                p.drawLine(int(x + seg), 0, int(x + seg), h)
            x += seg
        p.setPen(QtGui.QPen(qc("ACCENT2")))
        p.setBrush(Qt.NoBrush)
        p.drawRect(0, 0, w, h)


def label(text, name=None, wrap=False):
    lb = QtWidgets.QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


class StatGrid(QtWidgets.QWidget):
    """Valores grandes à esquerda e pares chave/valor à direita (como no Windows)."""

    def __init__(self, cols=3, parent=None):
        super().__init__(parent)
        self.cols = cols
        self._bk = self._ik = None
        self.bl, self.il = [], []
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(28)
        self.bg = QtWidgets.QGridLayout()
        self.bg.setHorizontalSpacing(26)
        self.bg.setVerticalSpacing(10)
        self.ig = QtWidgets.QGridLayout()
        self.ig.setHorizontalSpacing(14)
        self.ig.setVerticalSpacing(3)
        lay.addLayout(self.bg, 3)
        lay.addLayout(self.ig, 2)

    @staticmethod
    def _clear(layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def set(self, big, info):
        bk, ik = [k for k, _v in big], [k for k, _v in info]
        if bk != self._bk:
            self._clear(self.bg)
            self.bl = []
            for i, (k, _v) in enumerate(big):
                box = QtWidgets.QVBoxLayout()
                box.setSpacing(0)
                c, v = label(k, "cap"), label("", "val")
                box.addWidget(c)
                box.addWidget(v)
                self.bg.addLayout(box, i // self.cols, i % self.cols)
                self.bl.append(v)
            self._bk = bk
        if ik != self._ik:
            self._clear(self.ig)
            self.il = []
            for i, (k, _v) in enumerate(info):
                self.ig.addWidget(label(k, "ikey"), i, 0)
                v = label("")
                self.ig.addWidget(v, i, 1)
                self.il.append(v)
            self._ik = ik
        for lb, (_k, v) in zip(self.bl, big):
            lb.setText(v)
        for lb, (_k, v) in zip(self.il, info):
            lb.setText(v)


# =========================================================================== terminal
KEYS_ENUM = {
    Qt.Key_Return: "\r", Qt.Key_Enter: "\r", Qt.Key_Backspace: "\x7f", Qt.Key_Tab: "\t",
    Qt.Key_Backtab: "\x1b[Z", Qt.Key_Escape: "\x1b", Qt.Key_PageUp: "\x1b[5~",
    Qt.Key_PageDown: "\x1b[6~", Qt.Key_Insert: "\x1b[2~", Qt.Key_Delete: "\x1b[3~",
    Qt.Key_F1: "\x1bOP", Qt.Key_F2: "\x1bOQ", Qt.Key_F3: "\x1bOR", Qt.Key_F4: "\x1bOS",
    Qt.Key_F5: "\x1b[15~", Qt.Key_F6: "\x1b[17~", Qt.Key_F7: "\x1b[18~", Qt.Key_F8: "\x1b[19~",
    Qt.Key_F9: "\x1b[20~", Qt.Key_F10: "\x1b[21~", Qt.Key_F11: "\x1b[23~", Qt.Key_F12: "\x1b[24~",
}
ARROWS_ENUM = {Qt.Key_Up: "A", Qt.Key_Down: "B", Qt.Key_Right: "C", Qt.Key_Left: "D",
               Qt.Key_Home: "H", Qt.Key_End: "F"}
KEYS = {int(k): v for k, v in KEYS_ENUM.items()}
ARROWS = {int(k): v for k, v in ARROWS_ENUM.items()}
KEY_A, KEY_Z = int(Qt.Key_A), int(Qt.Key_Z)
K_RET, K_BS, K_ESC = int(Qt.Key_Return), int(Qt.Key_Backspace), int(Qt.Key_Escape)


class TermView(QtWidgets.QWidget):
    started = Signal()
    finished = Signal()

    def __init__(self, interactive=False, cols=130, rows=60, parent=None):
        super().__init__(parent)
        self.interactive = interactive
        self.fixed = (cols, rows)
        self.term = vt.Screen(cols, rows)
        self.proc = None
        self.notifier = None
        self._dirty = False
        self._cache = {}
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(False)
        self.set_font()
        self.set_theme()
        if interactive:
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        else:
            self.setFixedSize(cols * self.cw, rows * self.chh)

    # ---- aparência
    def set_font(self):
        f = QtGui.QFont(pick_mono())
        f.setPointSizeF(10.5)
        f.setStyleHint(QtGui.QFont.Monospace)
        self.f_norm = f
        self.f_bold = QtGui.QFont(f)
        self.f_bold.setBold(True)
        fm = QtGui.QFontMetrics(f)
        try:
            self.cw = max(1, fm.horizontalAdvance("M"))
        except AttributeError:
            self.cw = max(1, fm.width("M"))
        self.chh = fm.height()
        self.asc = fm.ascent()

    def set_theme(self):
        dark = T.get("dark", True)
        self.ansi = ANSI_DARK if dark else ANSI_LIGHT
        self.c_bg = QtGui.QColor("#0A1820" if dark else "#FFFFFF")
        self.c_fg = QtGui.QColor("#D5EAF0" if dark else "#0B2A2E")
        self._cache = {}
        self.update()

    def bg_css(self):
        return self.c_bg.name()

    def _col(self, spec):
        c = self._cache.get(spec)
        if c is None:
            if isinstance(spec, tuple):
                c = QtGui.QColor(*spec)
            elif spec < 16:
                c = QtGui.QColor(self.ansi[spec])
            elif spec < 232:
                i = spec - 16
                lv = (0, 95, 135, 175, 215, 255)
                c = QtGui.QColor(lv[i // 36], lv[(i // 6) % 6], lv[i % 6])
            else:
                v = 8 + (spec - 232) * 10
                c = QtGui.QColor(v, v, v)
            self._cache[spec] = c
        return c

    def _cell_colors(self, cell):
        _ch, fg, bg, fl = cell
        key = (fg, bg, fl & (vt.BOLD | vt.DIM | vt.REVERSE))
        r = self._cache.get(("cc", key))
        if r is None:
            if (fl & vt.BOLD) and isinstance(fg, int) and fg < 8:
                fg += 8
            fgc = self._col(fg) if fg is not None else self.c_fg
            bgc = self._col(bg) if bg is not None else None
            if fl & vt.REVERSE:
                fgc, bgc = (bgc if bgc is not None else self.c_bg), fgc
            if fl & vt.DIM:
                fgc = QtGui.QColor(fgc)
                fgc.setAlpha(150)
            r = (fgc, bgc)
            self._cache[("cc", key)] = r
        return r

    # ---- processo
    def fit(self):
        return max(20, self.width() // self.cw), max(5, self.height() // self.chh)

    def start(self, argv):
        self.stop()
        cols, rows = self.fit() if self.interactive else self.fixed
        self.term = vt.Screen(cols, rows)
        if not self.interactive:
            self.setFixedSize(cols * self.cw, rows * self.chh)
        try:
            self.proc = vt.PtyProcess(argv, cols, rows)
        except OSError:
            self.proc = None
            self.finished.emit()
            return
        self.term.respond = self.proc.write
        kind = getattr(QtCore.QSocketNotifier, "Read", None) or QtCore.QSocketNotifier.Type.Read
        self.notifier = QtCore.QSocketNotifier(self.proc.fileno(), kind, self)
        self.notifier.activated.connect(self._readable)
        self.started.emit()
        self.update()

    def running(self):
        return self.proc is not None and self.proc.alive()

    def stop(self):
        if self.notifier is not None:
            self.notifier.setEnabled(False)
            self.notifier.deleteLater()
            self.notifier = None
        if self.proc is not None:
            self.proc.close()
            self.proc = None

    def _readable(self, *_a):
        if self.proc is None:
            return
        for _i in range(16):
            d = self.proc.read()
            if d is None:
                break
            if d == b"":
                self._ended()
                return
            self.term.feed(d)
            self._dirty = True
        if self._dirty:
            self._dirty = False
            self.update()

    def _ended(self):
        if self.notifier is not None:
            self.notifier.setEnabled(False)
        if self.proc is not None:
            try:
                self.proc.proc.wait(timeout=1)
            except Exception:  # noqa: BLE001
                pass
        if not self.interactive:
            rows = self.term.used_rows()
            self.setFixedSize(self.term.cols * self.cw, rows * self.chh + 6)
        self.update()
        self.finished.emit()

    # ---- eventos
    def resizeEvent(self, ev):
        if self.interactive and self.proc is not None:
            cols, rows = self.fit()
            if (cols, rows) != (self.term.cols, self.term.rows):
                self.term.resize(cols, rows)
                self.proc.resize(cols, rows)
        super().resizeEvent(ev)

    def event(self, e):
        if e.type() == QtCore.QEvent.ShortcutOverride and self.interactive:
            e.accept()
            return True
        return super().event(e)

    def focusNextPrevChild(self, nxt):
        return False if self.interactive else super().focusNextPrevChild(nxt)

    def keyPressEvent(self, ev):
        if not self.interactive or self.proc is None:
            return super().keyPressEvent(ev)
        k = ev.key()
        m = ev.modifiers()
        mod = 1 + (1 if m & Qt.ShiftModifier else 0) + (2 if m & Qt.AltModifier else 0) + \
            (4 if m & Qt.ControlModifier else 0)
        data = None
        if k in ARROWS:
            c = ARROWS[k]
            if mod > 1:
                data = "\x1b[1;%d%s" % (mod, c)
            elif self.term.app_cursor:
                data = "\x1bO" + c
            else:
                data = "\x1b[" + c
        elif k in KEYS:
            data = KEYS[k]
            if (m & Qt.AltModifier) and k in (K_RET, K_BS, K_ESC):
                data = "\x1b" + data
        else:
            t = ev.text()
            if t:
                data = ("\x1b" + t) if (m & Qt.AltModifier) and not (m & Qt.ControlModifier) else t
            elif (m & Qt.ControlModifier) and KEY_A <= k <= KEY_Z:
                data = chr(k - KEY_A + 1)
        if data:
            self.proc.write(data.encode("utf-8"))
            ev.accept()
        else:
            super().keyPressEvent(ev)

    def _mouse(self, ev, btn, press):
        if not (self.interactive and self.proc and self.term.mouse):
            return False
        pt = ev.position().toPoint() if hasattr(ev, "position") else ev.pos()
        x = max(1, min(self.term.cols, pt.x() // self.cw + 1))
        y = max(1, min(self.term.rows, pt.y() // self.chh + 1))
        if self.term.mouse_sgr:
            s = "\x1b[<%d;%d;%d%s" % (btn, x, y, "M" if press else "m")
        else:
            b = btn if press else 3
            s = "\x1b[M" + chr(32 + b) + chr(32 + min(x, 223)) + chr(32 + min(y, 223))
        self.proc.write(s.encode("latin-1", "replace"))
        return True

    def mousePressEvent(self, ev):
        self.setFocus()
        b = {Qt.LeftButton: 0, Qt.MiddleButton: 1, Qt.RightButton: 2}.get(ev.button())
        if b is not None:
            self._mouse(ev, b, True)

    def mouseReleaseEvent(self, ev):
        b = {Qt.LeftButton: 0, Qt.MiddleButton: 1, Qt.RightButton: 2}.get(ev.button())
        if b is not None:
            self._mouse(ev, b, False)

    def wheelEvent(self, ev):
        dy = ev.angleDelta().y()
        if dy and self._mouse(ev, 64 if dy > 0 else 65, True):
            ev.accept()
        else:
            super().wheelEvent(ev)

    # ---- desenho
    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), self.c_bg)
        scr = self.term
        cw, chh, asc = self.cw, self.chh, self.asc
        r = ev.rect()
        r0 = max(0, r.top() // chh)
        r1 = min(scr.rows - 1, r.bottom() // chh)
        ncols = scr.cols
        p.setFont(self.f_norm)
        bold_on = False
        for row in range(r0, r1 + 1):
            cells = scr.buf[row]
            y = row * chh
            x0, cur = 0, None
            for col in range(ncols + 1):
                bgc = self._cell_colors(cells[col])[1] if col < ncols else None
                if bgc is not cur:
                    if cur is not None:
                        p.fillRect(x0 * cw, y, (col - x0) * cw, chh, cur)
                    x0, cur = col, bgc
            col = 0
            while col < ncols:
                cell = cells[col]
                ch, fg, bg, fl = cell
                if ch in (" ", "") or (fl & vt.HIDDEN):
                    col += 1
                    continue
                fgc = self._cell_colors(cell)[0]
                o = ord(ch[0])
                if len(ch) == 1 and 0x2580 <= o <= 0x2593:
                    x = col * cw
                    if o == 0x2588:
                        p.fillRect(x, y, cw, chh, fgc)
                    elif o == 0x2580:
                        p.fillRect(x, y, cw, chh // 2, fgc)
                    elif o == 0x2584:
                        p.fillRect(x, y + chh // 2, cw, chh - chh // 2, fgc)
                    elif o == 0x258C:
                        p.fillRect(x, y, cw // 2, chh, fgc)
                    elif o == 0x2590:
                        p.fillRect(x + cw // 2, y, cw - cw // 2, chh, fgc)
                    elif o in (0x2591, 0x2592, 0x2593):
                        c = QtGui.QColor(fgc)
                        c.setAlpha({0x2591: 70, 0x2592: 130, 0x2593: 190}[o])
                        p.fillRect(x, y, cw, chh, c)
                    else:
                        o = 0
                    if o:
                        col += 1
                        continue
                want_bold = bool(fl & vt.BOLD)
                if want_bold != bold_on:
                    p.setFont(self.f_bold if want_bold else self.f_norm)
                    bold_on = want_bold
                p.setPen(fgc)
                if len(ch) == 1 and o < 128:
                    j = col + 1
                    run = [ch]
                    while j < ncols:
                        c2 = cells[j]
                        if c2[3] == fl and c2[1] == fg and c2[2] == bg and len(c2[0]) == 1 and ord(c2[0]) < 128:
                            run.append(c2[0])
                            j += 1
                        else:
                            break
                    p.drawText(col * cw, y + asc, "".join(run))
                    if fl & vt.UNDER:
                        p.drawLine(col * cw, y + asc + 1, j * cw, y + asc + 1)
                    col = j
                else:
                    p.drawText(col * cw, y + asc, ch)
                    if fl & vt.UNDER:
                        p.drawLine(col * cw, y + asc + 1, (col + 1) * cw, y + asc + 1)
                    col += 1
        if self.interactive and scr.cursor_visible and self.hasFocus() and self.proc is not None:
            c = QtGui.QColor(self.c_fg)
            c.setAlpha(150)
            p.fillRect(scr.x * cw, scr.y * chh, cw, chh, c)


# =========================================================================== árvores / tabelas
class SItem(QtWidgets.QTreeWidgetItem):
    """Item ordenável por valor numérico (Qt.UserRole) ou texto."""

    def __lt__(self, other):
        tw = self.treeWidget()
        col = tw.sortColumn() if tw else 0
        grp = getattr(self, "prio", None)
        if grp is not None and getattr(other, "prio", None) is not None:
            asc = tw.header().sortIndicatorOrder() == Qt.AscendingOrder
            return (grp < other.prio) if asc else (grp > other.prio)
        a, b = self.data(col, Qt.UserRole), other.data(col, Qt.UserRole)
        if a is None or b is None:
            a, b = self.text(col).lower(), other.text(col).lower()
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


def make_tree(headers, widths=(), right=(), root_deco=False, multi=True):
    tw = QtWidgets.QTreeWidget()
    tw.setColumnCount(len(headers))
    tw.setHeaderLabels(headers)
    tw.setRootIsDecorated(root_deco)
    tw.setUniformRowHeights(True)
    tw.setAlternatingRowColors(False)
    tw.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection if multi
                        else QtWidgets.QAbstractItemView.SingleSelection)
    tw.setContextMenuPolicy(Qt.CustomContextMenu)
    tw.header().setStretchLastSection(False)
    tw.header().setSectionsClickable(True)
    for i, w in enumerate(widths):
        if w:
            tw.setColumnWidth(i, w)
    tw.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch if not widths or not widths[0]
                                     else QtWidgets.QHeaderView.Interactive)
    hi = tw.headerItem()
    for c in right:
        hi.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
    tw.setSortingEnabled(True)
    return tw


def set_row(it, values, nums=None, right=()):
    for c, v in enumerate(values):
        it.setText(c, v)
        if nums and nums.get(c) is not None:
            it.setData(c, Qt.UserRole, nums[c])
        else:
            it.setData(c, Qt.UserRole, v.lower() if isinstance(v, str) else v)
        if c in right:
            it.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)


class Page(QtWidgets.QWidget):
    """Base dos separadores."""

    def on_show(self):
        pass

    def refresh(self, sm):
        pass

    def on_theme(self):
        pass

    def shutdown(self):
        pass


# =========================================================================== Processos
GROUPS = (("apps", N_("Aplicações")), ("bg", N_("Processos em segundo plano")),
          ("system", N_("Processos do sistema")))


class ProcessesPage(Page):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.items, self.children = {}, {}
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        self.tw = make_tree([_("Nome"), _("Estado"), "CPU", _("Memória"), _("Disco")],
                            widths=(0, 90, 80, 100, 100), right=(2, 3, 4), root_deco=True)
        self.tw.setColumnWidth(0, 360)
        self.tw.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        self.tw.header().setStretchLastSection(True)
        self.tw.header().setMinimumHeight(48)
        self.tw.sortByColumn(0, Qt.AscendingOrder)
        self.gitems = {}
        for i, (kind, title) in enumerate(GROUPS):
            g = SItem([""] * 5)
            g.prio = i
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            self.tw.addTopLevelItem(g)
            g.setExpanded(True)
            g.setFlags(g.flags() & ~Qt.ItemIsSelectable)
            self.gitems[kind] = g
        v.addWidget(self.tw, 1)
        bar = QtWidgets.QHBoxLayout()
        bar.addStretch(1)
        self.btn = QtWidgets.QPushButton(_("Finalizar tarefa"))
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.end_task)
        bar.addWidget(self.btn)
        v.addLayout(bar)
        self.tw.itemSelectionChanged.connect(lambda: self.btn.setEnabled(bool(self.pids())))
        self.tw.customContextMenuRequested.connect(self.menu)
        self.tw.itemDoubleClicked.connect(lambda it, c: it.setExpanded(not it.isExpanded()))

    def pids(self):
        out = []
        for it in self.tw.selectedItems():
            d = it.data(0, ROLE_PIDS)
            if d:
                out.extend(d)
        return sorted(set(out))

    def end_task(self):
        p = self.pids()
        if p:
            self.win.signal_pids(p, signal.SIGTERM)

    def menu(self, pos):
        pids = self.pids()
        if not pids:
            return
        m = QtWidgets.QMenu(self)
        a_end = m.addAction(_("Finalizar tarefa"))
        a_tree = m.addAction(_("Finalizar árvore de processos"))
        a_kill = m.addAction(_("Forçar encerramento (SIGKILL)"))
        m.addSeparator()
        pm = m.addMenu(_("Definir prioridade"))
        pacts = {pm.addAction(_(n)): nice for n, nice in PRIO_NICE}
        a_aff = m.addAction(_("Definir afinidade…"))
        m.addSeparator()
        a_dir = m.addAction(_("Abrir local do ficheiro"))
        gp = self.tw.viewport().mapToGlobal(pos)
        act = m.exec(gp) if hasattr(m, "exec") else m.exec_(gp)
        if act is None:
            return
        if act == a_end:
            self.end_task()
        elif act == a_tree:
            self.win.signal_pids(pids, signal.SIGTERM, tree=True)
        elif act == a_kill:
            self.win.signal_pids(pids, signal.SIGKILL, force=True)
        elif act in pacts:
            self.win.set_nice(pids, pacts[act])
        elif act == a_aff:
            self.win.set_affinity(pids[0])
        elif act == a_dir:
            self.win.open_location(pids[0])

    def refresh(self, sm):
        groups = sm.groups()
        tw = self.tw
        tw.setSortingEnabled(False)
        hi = tw.headerItem()
        hi.setText(2, "%s\nCPU" % pct_txt(sm.cpu))
        hi.setText(3, "%s\n%s" % (pct_txt(sm.vm.percent), _("Memória")))
        disk_bps = sum(d["rd"] + d["wr"] for d in sm.disks.values())
        hi.setText(4, "%s\n%s" % (disk_txt(disk_bps), _("Disco")))
        total_mem = float(sm.vm.total) or 1.0
        seen = set()
        for kind, title in GROUPS:
            entries = groups[kind]
            g = self.gitems[kind]
            g.setText(0, "%s (%d)" % (_(title), len(entries)))
            for disp, plist in entries.items():
                key = (kind, disp)
                seen.add(key)
                it = self.items.get(key)
                if it is None:
                    it = SItem([""] * 5)
                    g.addChild(it)
                    self.items[key] = it
                    self.children[key] = {}
                name = _("Kernel do Linux") if disp == "kernel" else disp
                if len(plist) > 1:
                    name = "%s (%d)" % (name, len(plist))
                cpu = sum(p.cpu for p in plist)
                mem = sum(p.mem for p in plist)
                dsk = sum(p.disk for p in plist)
                stat = user_visible_status(plist[0].status) if len(plist) == 1 else ""
                set_row(it, [name, stat, pct_txt(cpu), S.fmt_mem(mem), disk_txt(dsk)],
                        {2: cpu, 3: mem, 4: dsk}, right=(2, 3, 4))
                it.setData(0, Qt.UserRole, name.lower())
                it.setData(0, ROLE_PIDS, [p.pid for p in plist])
                it.setBackground(2, heat(cpu))
                it.setBackground(3, heat(mem / total_mem * 100.0 * 3))
                it.setBackground(4, heat(dsk / 52428800.0 * 100.0))
                self._sync_children(key, it, plist, total_mem)
        for key in [k for k in self.items if k not in seen]:
            it = self.items.pop(key)
            self.children.pop(key, None)
            par = it.parent()
            if par is not None:
                par.removeChild(it)
        tw.setSortingEnabled(True)

    def _sync_children(self, key, it, plist, total_mem):
        kids = self.children[key]
        if len(plist) <= 1:
            for c in list(kids.values()):
                it.removeChild(c)
            kids.clear()
            return
        alive = set()
        for p in plist:
            alive.add(p.pid)
            c = kids.get(p.pid)
            if c is None:
                c = SItem([""] * 5)
                it.addChild(c)
                kids[p.pid] = c
            label_ = "%s [%d]" % (p.name, p.pid)
            set_row(c, [label_, user_visible_status(p.status), pct_txt(p.cpu), S.fmt_mem(p.mem), disk_txt(p.disk)],
                    {2: p.cpu, 3: p.mem, 4: p.disk}, right=(2, 3, 4))
            c.setData(0, ROLE_PIDS, [p.pid])
            c.setBackground(2, heat(p.cpu))
            c.setBackground(3, heat(p.mem / total_mem * 100.0 * 3))
            c.setBackground(4, heat(p.disk / 52428800.0 * 100.0))
        for pid in [k for k in kids if k not in alive]:
            it.removeChild(kids.pop(pid))


# =========================================================================== Desempenho
class ResItem(QtWidgets.QFrame):
    clicked = Signal(int)

    def __init__(self, idx, title, series, maxv=100.0, auto=False):
        super().__init__()
        self.idx = idx
        self.setObjectName("resitem")
        self.setProperty("sel", False)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        self.graph = Graph(series, maxv, auto, grid=False, minh=46)
        self.graph.setFixedSize(78, 50)
        lay.addWidget(self.graph)
        box = QtWidgets.QVBoxLayout()
        box.setSpacing(0)
        self.t = label(title, "restitle")
        self.s = label("", "muted")
        box.addStretch(1)
        box.addWidget(self.t)
        box.addWidget(self.s)
        box.addStretch(1)
        lay.addLayout(box, 1)

    def mousePressEvent(self, ev):
        self.clicked.emit(self.idx)

    def set_selected(self, v):
        self.setProperty("sel", v)
        self.style().unpolish(self)
        self.style().polish(self)


class DetailPage(QtWidgets.QWidget):
    def __init__(self, title, subtitle=""):
        super().__init__()
        self.v = QtWidgets.QVBoxLayout(self)
        self.v.setContentsMargins(18, 10, 18, 10)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(label(title, "h1"))
        head.addStretch(1)
        self.sub = label(subtitle, "h2")
        head.addWidget(self.sub)
        self.v.addLayout(head)
        self.stats = StatGrid()

    def add_graph(self, caption, graph, right=""):
        row = QtWidgets.QHBoxLayout()
        row.addWidget(label(caption, "cap"))
        row.addStretch(1)
        rl = label(right, "cap")
        row.addWidget(rl)
        self.v.addLayout(row)
        self.v.addWidget(graph, 1)
        return rl

    def finish(self):
        self.v.addSpacing(8)
        self.v.addWidget(self.stats)
        self.v.addStretch(0)


class CpuPage(DetailPage):
    def __init__(self, sm):
        super().__init__("CPU", S.cpu_model())
        self.static = S.cpu_static()
        self.total = Graph([(sm.series("cpu"), "ACCENT")], 100)
        self.cores = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(self.cores)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        n = S.NCPU
        cols = max(1, int(n ** 0.5 + 0.999))
        self.core_graphs = []
        for i in range(n):
            g = Graph([(sm.series("core%d" % i), "ACCENT")], 100, grid=False, minh=40)
            grid.addWidget(g, i // cols, i % cols)
            self.core_graphs.append(g)
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.total)
        self.stack.addWidget(self.cores)
        self.stack.setContextMenuPolicy(Qt.CustomContextMenu)
        self.stack.customContextMenuRequested.connect(self._menu)
        self.cap = self.add_graph(_("% de utilização"), self.stack, "100%")
        self.finish()

    def _menu(self, pos):
        m = QtWidgets.QMenu(self)
        a1 = m.addAction(_("Utilização geral do processador"))
        a2 = m.addAction(_("Processadores lógicos"))
        gp = self.stack.mapToGlobal(pos)
        act = m.exec(gp) if hasattr(m, "exec") else m.exec_(gp)
        if act == a1:
            self.stack.setCurrentIndex(0)
        elif act == a2:
            self.stack.setCurrentIndex(1)

    def refresh(self, sm):
        st = self.static
        big = [(_("Utilização"), pct_txt(sm.cpu)),
               (_("Velocidade"), "%s GHz" % S.num(sm.freq, 2) if sm.freq else "—"),
               (_("Processos"), str(len(sm.procs))), ("Threads", str(sm.threads_total)),
               (_("Identificadores"), str(S.open_handles())),
               (_("Tempo de atividade"), S.fmt_secs(S.uptime()))]
        info = [(_("Velocidade máxima"), "%s GHz" % S.num(st["maxf"], 2) if st["maxf"] else "—"),
                ("Sockets", str(st["sockets"])), (_("Núcleos"), str(st["cores"])),
                (_("Processadores lógicos"), str(st["logical"])),
                (_("Virtualização"), _("Ativada") if st["virt"] else _("Desativada")),
                (_("Cache L1"), S.fmt_kb(st["l1"])), (_("Cache L2"), S.fmt_kb(st["l2"])),
                (_("Cache L3"), S.fmt_kb(st["l3"]))]
        self.stats.set(big, info)
        for g in self.core_graphs:
            g.update()
        self.total.update()


class MemPage(DetailPage):
    def __init__(self, sm):
        super().__init__(_("Memória"), S.fmt_bytes(sm.vm.total))
        self.graph = Graph([(sm.series("mem"), "WARN")], 100)
        self.add_graph(_("Utilização de memória"), self.graph, S.fmt_bytes(sm.vm.total))
        self.v.addWidget(label(_("Composição da memória"), "cap"))
        self.bar = CompBar()
        self.v.addWidget(self.bar)
        self.finish()

    def refresh(self, sm):
        vm, sw = sm.vm, sm.swap
        tot = float(vm.total) or 1.0
        in_use = vm.total - vm.available
        cache = getattr(vm, "buffers", 0) + getattr(vm, "cached", 0)
        self.bar.set_parts([(in_use / tot, "WARN"), (cache / tot, "ACCENT2"), (max(0, vm.free) / tot, "BORDER")])
        big = [(_("Em uso"), S.fmt_bytes(in_use)), (_("Disponível"), S.fmt_bytes(vm.available)),
               (_("Em cache"), S.fmt_bytes(cache)),
               (_("Swap em uso"), "%s/%s" % (S.fmt_bytes(sw.used), S.fmt_bytes(sw.total)) if sw.total else "—")]
        info = [(_("Memória total"), S.fmt_bytes(vm.total)),
                (_("Partilhada"), S.fmt_bytes(getattr(vm, "shared", 0))),
                (_("Livre"), S.fmt_bytes(vm.free)), (_("Swap total"), S.fmt_bytes(sw.total) if sw.total else "—")]
        self.stats.set(big, info)
        self.graph.update()
        self.bar.update()


class DiskPage(DetailPage):
    def __init__(self, sm, name, idx):
        self.name = name
        self.info = S.disk_info(name)
        super().__init__(_("Disco %d (%s)") % (idx, name), self.info["model"])
        self.g1 = Graph([(sm.series("disk:%s:busy" % name), "ACCENT")], 100, minh=90)
        self.add_graph(_("Tempo de atividade"), self.g1, "100%")
        self.g2 = Graph([(sm.series("disk:%s:rate" % name), "OK")], 1048576.0, auto=True, minh=90)
        self.r2 = self.add_graph(_("Taxa de transferência de disco"), self.g2, "")
        self.finish()

    def refresh(self, sm):
        d = sm.disks.get(self.name, dict(busy=0, rd=0, wr=0, resp=0))
        inf = self.info
        big = [(_("Tempo ativo"), pct_txt(d["busy"])), (_("Tempo médio de resposta"), "%s ms" % S.num(d["resp"], 1)),
               (_("Taxa de leitura"), S.fmt_rate(d["rd"])), (_("Taxa de gravação"), S.fmt_rate(d["wr"]))]
        yes, no = _("Sim"), _("Não")
        info = [(_("Capacidade"), S.fmt_bytes(inf["cap"])), (_("Formatado"), S.fmt_bytes(inf["formatted"])),
                (_("Disco do sistema"), yes if inf["system"] else no),
                (_("Ficheiro de paginação"), yes if inf["swap"] else no), (_("Tipo"), inf["kind"])]
        self.stats.set(big, info)
        self.r2.setText(S.fmt_rate(self.g2.scale()))
        self.g1.update()
        self.g2.update()


class NetPage(DetailPage):
    def __init__(self, sm, name):
        self.name = name
        self.info = S.net_info(name)
        title = "Wi-Fi" if self.info["wifi"] else "Ethernet"
        super().__init__(title, name)
        self.g = Graph([(sm.series("net:%s:rx" % name), "ACCENT"), (sm.series("net:%s:tx" % name), "WARN")],
                       125000.0, auto=True)
        self.r = self.add_graph(_("Taxa de transferência"), self.g, "")
        self.finish()

    def refresh(self, sm):
        n = sm.nets.get(self.name, dict(tx=0, rx=0))
        inf = self.info
        if int(time.time()) % 10 == 0:
            self.info = inf = S.net_info(self.name)
        big = [(_("Enviar"), S.fmt_bits(n["tx"])), (_("Receber"), S.fmt_bits(n["rx"]))]
        info = [(_("Nome do adaptador"), self.name)]
        if inf["wifi"]:
            info.append(("SSID", inf["ssid"] or "—"))
        info += [(_("Tipo de ligação"), "Wi-Fi" if inf["wifi"] else "Ethernet"),
                 (_("Endereço IPv4"), inf["ipv4"] or "—"), (_("Endereço IPv6"), inf["ipv6"] or "—")]
        self.stats.set(big, info)
        self.r.setText(S.fmt_bits(self.g.scale()))
        self.g.update()


class GpuPage(DetailPage):
    def __init__(self, sm, i):
        self.i = i
        super().__init__("GPU %d" % i, sm.gpus[i]["name"])
        self.g1 = Graph([(sm.series("gpu%d" % i), "ACCENT")], 100, minh=90)
        self.add_graph(_("Utilização"), self.g1, "100%")
        self.g2 = Graph([(sm.series("gpumem%d" % i), "WARN")], 100, minh=90)
        self.add_graph(_("Memória dedicada da GPU"), self.g2, "100%")
        self.finish()

    def refresh(self, sm):
        if self.i >= len(sm.gpus):
            return
        g = sm.gpus[self.i]
        big = [(_("Utilização"), pct_txt(g["util"])),
               (_("Memória dedicada da GPU"), "%s/%s" % (S.fmt_bytes(g["mem_used"]), S.fmt_bytes(g["mem_total"])))]
        self.stats.set(big, [("Driver", g["driver"])])
        self.g1.update()
        self.g2.update()


class PerformancePage(Page):
    def __init__(self, sm):
        super().__init__()
        self.sm = sm
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        left = QtWidgets.QScrollArea()
        left.setWidgetResizable(True)
        left.setFixedWidth(250)
        left.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QtWidgets.QWidget()
        self.lv = QtWidgets.QVBoxLayout(holder)
        self.lv.setContentsMargins(0, 8, 0, 8)
        self.lv.setSpacing(2)
        left.setWidget(holder)
        self.stack = QtWidgets.QStackedWidget()
        h.addWidget(left)
        h.addWidget(self.stack, 1)
        self.entries = []   # (ResItem, page, subtitle_fn)
        n = len(self.entries)
        self._add(ResItem(n, "CPU", [(sm.series("cpu"), "ACCENT")]), CpuPage(sm),
                  lambda s: "%s  %s" % (pct_txt(s.cpu), ("%s GHz" % S.num(s.freq, 2)) if s.freq else ""))
        self._add(ResItem(len(self.entries), _("Memória"), [(sm.series("mem"), "WARN")]), MemPage(sm),
                  lambda s: "%s/%s (%d%%)" % (S.fmt_bytes(s.vm.total - s.vm.available), S.fmt_bytes(s.vm.total),
                                              round(s.vm.percent)))
        for i, d in enumerate(sm.disk_names()):
            self._add(ResItem(len(self.entries), _("Disco %d (%s)") % (i, d),
                              [(sm.series("disk:%s:busy" % d), "OK")]), DiskPage(sm, d, i),
                      (lambda dn: lambda s: pct_txt(s.disks.get(dn, {}).get("busy", 0)))(d))
        for nme in sm.net_names():
            page = NetPage(sm, nme)
            self._add(ResItem(len(self.entries), page.windowTitle() or ("Wi-Fi" if page.info["wifi"] else "Ethernet"),
                              [(sm.series("net:%s:rx" % nme), "ACCENT"), (sm.series("net:%s:tx" % nme), "WARN")],
                              125000.0, True), page,
                      (lambda nn: lambda s: "E: %s  R: %s" % (S.fmt_bits(s.nets.get(nn, {}).get("tx", 0)),
                                                              S.fmt_bits(s.nets.get(nn, {}).get("rx", 0))))(nme))
        for i, g in enumerate(sm.gpus):
            self._add(ResItem(len(self.entries), "GPU %d" % i, [(sm.series("gpu%d" % i), "ACCENT")]),
                      GpuPage(sm, i), (lambda gi: lambda s: pct_txt(s.gpus[gi]["util"]) if gi < len(s.gpus) else "")(i))
        self.lv.addStretch(1)
        self.select(0)

    def _add(self, item, page, subfn):
        item.clicked.connect(self.select)
        self.lv.addWidget(item)
        self.stack.addWidget(page)
        self.entries.append((item, page, subfn))

    def select(self, idx):
        for i, (it, _p, _f) in enumerate(self.entries):
            it.set_selected(i == idx)
        self.stack.setCurrentIndex(idx)
        self.refresh(self.sm)

    def refresh(self, sm):
        for it, _p, fn in self.entries:
            try:
                it.s.setText(fn(sm))
            except Exception:  # noqa: BLE001
                pass
            it.graph.update()
        cur = self.stack.currentWidget()
        if cur is not None:
            cur.refresh(sm)


# =========================================================================== Histórico
class HistoryPage(Page):
    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        top = QtWidgets.QHBoxLayout()
        self.info = label("", "muted")
        top.addWidget(self.info)
        top.addStretch(1)
        b = QtWidgets.QPushButton(_("Eliminar histórico de utilização"))
        b.clicked.connect(self.clear)
        top.addWidget(b)
        v.addLayout(top)
        self.tw = make_tree([_("Nome"), _("Tempo de CPU"), _("Leitura de disco"), _("Escrita em disco"),
                             _("Memória (pico)")], widths=(0, 120, 130, 130, 130), right=(1, 2, 3, 4))
        self.tw.sortByColumn(1, Qt.DescendingOrder)
        v.addWidget(self.tw, 1)
        self.items = {}

    def clear(self):
        self.win.sm.history.clear()
        self.items.clear()
        self.tw.clear()

    def refresh(self, sm):
        h = sm.history
        fmt = "%m/%d/%Y" if i18n.get_lang() == "en" else "%d/%m/%Y"
        self.info.setText(_("Utilização de recursos desde {d} para as aplicações do utilizador atual.").format(
            d=datetime.datetime.fromtimestamp(h.since).strftime(fmt)))
        tw = self.tw
        tw.setSortingEnabled(False)
        for name, a in h.apps.items():
            it = self.items.get(name)
            if it is None:
                it = SItem([""] * 5)
                tw.addTopLevelItem(it)
                self.items[name] = it
            set_row(it, [name, S.fmt_cpu_time(a["cpu"]), S.fmt_bytes(a["rd"]), S.fmt_bytes(a["wr"]),
                         S.fmt_mem(a.get("peak", 0))],
                    {1: a["cpu"], 2: a["rd"], 3: a["wr"], 4: a.get("peak", 0)}, right=(1, 2, 3, 4))
        tw.setSortingEnabled(True)


# =========================================================================== Arranque
class StartupPage(Page):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.entries = {}
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.addWidget(label(_("Programas que arrancam com a sessão (autostart). O impacto é estimado com o consumo de CPU e memória do programa, se estiver em execução."), "muted", wrap=True))
        self.tw = make_tree([_("Nome"), _("Origem"), _("Estado"), _("Impacto no arranque")],
                            widths=(0, 120, 120, 170))
        self.tw.sortByColumn(0, Qt.AscendingOrder)
        v.addWidget(self.tw, 1)
        bar = QtWidgets.QHBoxLayout()
        bar.addStretch(1)
        self.btn = QtWidgets.QPushButton(_("Desativar"))
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.toggle)
        bar.addWidget(self.btn)
        v.addLayout(bar)
        self.tw.itemSelectionChanged.connect(self._sel)
        self._last = 0

    def _cur(self):
        its = self.tw.selectedItems()
        return self.entries.get(its[0].data(0, ROLE_PIDS)) if its else None

    def _sel(self):
        e = self._cur()
        self.btn.setEnabled(e is not None)
        if e is not None:
            self.btn.setText(_("Desativar") if e["enabled"] else _("Ativar"))

    def toggle(self):
        e = self._cur()
        if e is None:
            return
        if not S.set_autostart(e["file"], not e["enabled"]):
            self.win.notify(_("Erro"), _("Não foi possível alterar esta entrada."), ok=False)
        self.reload()

    def on_show(self):
        self.reload()

    def reload(self):
        sel = self._cur()
        sel_file = sel["file"] if sel else None
        keys = ["Name[%s]" % c for c in i18n.lang_codes(i18n.get_lang())]
        origin_txt = {"user": _("Utilizador"), "system": _("Sistema"), "override": _("Sistema (alterado)")}
        impact_txt = {"high": _("Alto"), "mid": _("Médio"), "low": _("Baixo"), None: _("Não medido")}
        tw = self.tw
        tw.setSortingEnabled(False)
        tw.clear()
        self.entries = {}
        for e in S.list_autostart(keys):
            self.entries[e["file"]] = e
            imp = S.startup_impact(e, self.win.sm.procs)
            it = SItem([""] * 4)
            set_row(it, [e["name"], origin_txt.get(e["origin"], ""), _("Ativado") if e["enabled"] else _("Desativado"),
                         impact_txt[imp]], {0: e["name"].lower()})
            it.setData(0, ROLE_PIDS, e["file"])
            if not e["enabled"]:
                for c in range(4):
                    it.setForeground(c, QtGui.QBrush(qc("MUTED")))
            tw.addTopLevelItem(it)
            if e["file"] == sel_file:
                it.setSelected(True)
        tw.setSortingEnabled(True)
        self._sel()


# =========================================================================== Utilizadores
class UsersPage(Page):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.items, self.kids = {}, {}
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        self.tw = make_tree([_("Utilizador"), _("Estado"), "CPU", _("Memória"), _("Disco")],
                            widths=(0, 110, 80, 100, 100), right=(2, 3, 4), root_deco=True, multi=False)
        self.tw.setColumnWidth(0, 360)
        self.tw.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        self.tw.header().setStretchLastSection(True)
        self.tw.sortByColumn(2, Qt.DescendingOrder)
        v.addWidget(self.tw, 1)
        bar = QtWidgets.QHBoxLayout()
        bar.addStretch(1)
        self.btn = QtWidgets.QPushButton(_("Terminar sessão"))
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.logout)
        bar.addWidget(self.btn)
        v.addLayout(bar)
        self.tw.itemSelectionChanged.connect(self._sel)

    def _user(self):
        its = self.tw.selectedItems()
        if its and its[0].parent() is None:
            return its[0].data(0, ROLE_PIDS)
        return None

    def _sel(self):
        u = self._user()
        self.btn.setEnabled(bool(u) and u != S.ME and u != "root")

    def logout(self):
        u = self._user()
        if u and self.win.ask(_("Terminar sessão"), _("Terminar a sessão do utilizador {u}?").format(u=u)):
            self.win.helper(["terminate-user", u])

    def refresh(self, sm):
        tw = self.tw
        tw.setSortingEnabled(False)
        users = sm.users()
        total = float(sm.vm.total) or 1.0
        for user, plist in users.items():
            it = self.items.get(user)
            if it is None:
                it = SItem([""] * 5)
                tw.addTopLevelItem(it)
                self.items[user] = it
                self.kids[user] = {}
            cpu = sum(p.cpu for p in plist)
            mem = sum(p.mem for p in plist)
            dsk = sum(p.disk for p in plist)
            set_row(it, ["%s (%d)" % (user, len(plist)), _("Ativo") if user == S.ME else "", pct_txt(cpu),
                         S.fmt_mem(mem), disk_txt(dsk)], {2: cpu, 3: mem, 4: dsk}, right=(2, 3, 4))
            it.setData(0, ROLE_PIDS, user)
            it.setBackground(2, heat(cpu))
            it.setBackground(3, heat(mem / total * 300.0))
            agg = {}
            for p in plist:
                n = _("Kernel do Linux") if p.disp == "kernel" else p.disp
                a = agg.setdefault(n, [0.0, 0, 0.0, 0])
                a[0] += p.cpu
                a[1] += p.mem
                a[2] += p.disk
                a[3] += 1
            kids = self.kids[user]
            for n, (c, m, d, cnt) in agg.items():
                k = kids.get(n)
                if k is None:
                    k = SItem([""] * 5)
                    it.addChild(k)
                    kids[n] = k
                set_row(k, ["%s (%d)" % (n, cnt) if cnt > 1 else n, "", pct_txt(c), S.fmt_mem(m), disk_txt(d)],
                        {2: c, 3: m, 4: d}, right=(2, 3, 4))
                k.setData(0, ROLE_PIDS, None)
            for n in [x for x in kids if x not in agg]:
                it.removeChild(kids.pop(n))
        for user in [u for u in self.items if u not in users]:
            tw.takeTopLevelItem(tw.indexOfTopLevelItem(self.items.pop(user)))
            self.kids.pop(user, None)
        tw.setSortingEnabled(True)


# =========================================================================== Serviços
class ServicesPage(Page):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.items = {}
        self.busy = False
        self.last = 0.0
        self.tasks = []
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        top = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(_("Filtrar serviços…"))
        self.search.textChanged.connect(self.apply_filter)
        top.addWidget(self.search, 1)
        v.addLayout(top)
        self.tw = make_tree([_("Nome"), "PID", _("Descrição"), _("Estado"), _("Arranque")],
                            widths=(230, 80, 0, 120, 120), right=(1,), multi=False)
        self.tw.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        self.tw.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.tw.setColumnWidth(0, 250)
        self.tw.sortByColumn(0, Qt.AscendingOrder)
        v.addWidget(self.tw, 1)
        bar = QtWidgets.QHBoxLayout()
        bar.addStretch(1)
        self.bs = QtWidgets.QPushButton(_("Iniciar"))
        self.bp = QtWidgets.QPushButton(_("Parar"))
        self.br = QtWidgets.QPushButton(_("Reiniciar"))
        for b, act in ((self.bs, "start"), (self.bp, "stop"), (self.br, "restart")):
            b.setEnabled(False)
            b.clicked.connect((lambda a: lambda: self.act(a))(act))
            bar.addWidget(b)
        v.addLayout(bar)
        self.tw.itemSelectionChanged.connect(lambda: [b.setEnabled(self._unit() is not None)
                                                      for b in (self.bs, self.bp, self.br)])
        self.tw.customContextMenuRequested.connect(self.menu)

    def _unit(self):
        its = self.tw.selectedItems()
        return its[0].data(0, ROLE_PIDS) if its else None

    def act(self, action):
        u = self._unit()
        if u:
            self.win.helper(["service", action, u], after=lambda: self.reload(force=True))

    def menu(self, pos):
        u = self._unit()
        if not u:
            return
        m = QtWidgets.QMenu(self)
        acts = {m.addAction(_("Iniciar")): "start", m.addAction(_("Parar")): "stop",
                m.addAction(_("Reiniciar")): "restart"}
        gp = self.tw.viewport().mapToGlobal(pos)
        a = m.exec(gp) if hasattr(m, "exec") else m.exec_(gp)
        if a in acts:
            self.act(acts[a])

    def on_show(self):
        self.reload(force=True)

    def refresh(self, sm):
        self.reload()

    def reload(self, force=False):
        if self.busy or (not force and time.time() - self.last < 5):
            return
        self.busy = True
        self._reap()
        t = Task(S.list_services, parent=self)
        t.done.connect(self._loaded)
        t.finished.connect(self._reap)
        self.tasks.append(t)
        t.start()

    def _reap(self):
        keep = []
        for t in self.tasks:
            if t.isFinished():
                t.deleteLater()
            else:
                keep.append(t)
        self.tasks = keep

    def _loaded(self, res):
        self.busy = False
        self.last = time.time()
        if isinstance(res, Exception):
            return
        tw = self.tw
        tw.setSortingEnabled(False)
        alive = set()
        for u in res:
            alive.add(u["unit"])
            it = self.items.get(u["unit"])
            if it is None:
                it = SItem([""] * 5)
                tw.addTopLevelItem(it)
                self.items[u["unit"]] = it
            run = u["active"] == "active"
            st = _("Em execução") if run and u["sub"] == "running" else (_("Ativo") if run else
                                                                          (_("Falhou") if u["active"] == "failed" else _("Parado")))
            en = {"enabled": _("Automático"), "disabled": _("Desativado"), "static": _("Estático"),
                  "masked": _("Mascarado")}.get(u["enabled"], u["enabled"] or "—")
            set_row(it, [u["unit"][:-8], str(u["pid"]) if u["pid"] else "", u["desc"], st, en],
                    {1: u["pid"]}, right=(1,))
            it.setData(0, ROLE_PIDS, u["unit"])
        for k in [x for x in self.items if x not in alive]:
            tw.takeTopLevelItem(tw.indexOfTopLevelItem(self.items.pop(k)))
        tw.setSortingEnabled(True)
        self.apply_filter()

    def apply_filter(self, *_a):
        q = self.search.text().lower().strip()
        for it in self.items.values():
            it.setHidden(bool(q) and q not in it.text(0).lower() and q not in it.text(2).lower())


# =========================================================================== Fastfetch / Htop
class TerminalTab(Page):
    def __init__(self, win, tool, interactive):
        super().__init__()
        self.win, self.tool, self.interactive = win, tool, interactive
        self.started_once = False
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 10)
        bar = QtWidgets.QHBoxLayout()
        self.status = label("", "muted")
        bar.addWidget(self.status, 1)
        self.btn = QtWidgets.QPushButton(_("Reiniciar") if interactive else _("Atualizar"))
        self.btn.clicked.connect(self.run)
        bar.addWidget(self.btn)
        v.addLayout(bar)
        self.banner = QtWidgets.QFrame()
        self.banner.setObjectName("banner")
        bl = QtWidgets.QHBoxLayout(self.banner)
        self.bl = label("", wrap=True)
        bl.addWidget(self.bl, 1)
        self.binst = QtWidgets.QPushButton(_("Instalar"))
        self.binst.setObjectName("primary")
        self.binst.clicked.connect(self.install)
        bl.addWidget(self.binst)
        self.banner.hide()
        v.addWidget(self.banner)
        self.view = TermView(interactive=interactive)
        self.view.finished.connect(self._done)
        if interactive:
            v.addWidget(self.view, 1)
        else:
            self.scroll = QtWidgets.QScrollArea()
            self.scroll.setWidget(self.view)
            self.scroll.setWidgetResizable(False)
            self.scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            v.addWidget(self.scroll, 1)
        self.on_theme()

    def on_theme(self):
        self.view.set_theme()
        bg = self.view.bg_css()
        if self.interactive:
            self.view.setStyleSheet("")
        else:
            self.scroll.setStyleSheet("QScrollArea { background: %s; border: 1px solid %s; border-radius: 8px; }"
                                      % (bg, T["BORDER"]))
            self.scroll.viewport().setStyleSheet("background: %s;" % bg)

    def on_show(self):
        if not self.started_once:
            self.run()
        if self.interactive:
            self.view.setFocus()

    def run(self):
        if not shutil.which(self.tool):
            self.view.stop()
            self.bl.setText(_("O programa «{t}» não está instalado.").format(t=self.tool))
            self.binst.setEnabled(True)
            self.banner.show()
            self.status.setText("")
            return
        self.banner.hide()
        self.started_once = True
        self.status.setText(_("A executar «{t}»…").format(t=self.tool) if not self.interactive else
                            _("htop interativo: use o teclado e o rato dentro desta janela (F10 ou Q para sair)."))
        self.view.start([shutil.which(self.tool)])
        if self.interactive:
            self.view.setFocus()

    def _done(self):
        if self.interactive:
            self.status.setText(_("O htop terminou. Clique em «Reiniciar» para o abrir de novo."))
        else:
            self.status.setText(_("Resultado de «{t}» — clique em «Atualizar» para repetir.").format(t=self.tool))

    def install(self):
        self.binst.setEnabled(False)
        self.bl.setText(_("A instalar… pode demorar alguns minutos (é pedida a palavra-passe de administrador)."))
        self.win.helper(["install-tools", self.tool], after=self.run, fail=self._install_failed)

    def _install_failed(self):
        self.binst.setEnabled(True)
        self.bl.setText(_("Não foi possível instalar «{t}» automaticamente. Instale-o manualmente.").format(t=self.tool))

    def shutdown(self):
        self.view.stop()


# =========================================================================== janela principal
def run_helper(args):
    try:
        r = subprocess.run(["pkexec", HELPER] + [str(a) for a in args], capture_output=True, text=True,
                           timeout=3600)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, sm):
        super().__init__()
        self.sm = sm
        self.tasks = []
        self.setWindowTitle("Mainuan Gerenciador Tarefas")
        lp = logo_path()
        if lp:
            self.setWindowIcon(QtGui.QIcon(lp))
        self._placed = False
        self.fit_to_screen()

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.ElideNone)
        self.processes = ProcessesPage(self)
        self.perf = PerformancePage(sm)
        self.history = HistoryPage(self)
        self.startup = StartupPage(self)
        self.users = UsersPage(self)
        self.services = ServicesPage(self)
        self.fastfetch = TerminalTab(self, "fastfetch", False)
        self.htop = TerminalTab(self, "htop", True)
        self.pages = [self.perf, self.processes, self.history, self.startup, self.users,
                      self.services, self.fastfetch, self.htop]
        titles = [_("Desempenho"), _("Processos"), _("Histórico de aplicações"), _("Arranque"),
                  _("Utilizadores"), _("Serviços"), "Fastfetch", "Htop"]
        for pg, t in zip(self.pages, titles):
            self.tabs.addTab(pg, t)
        self.setCentralWidget(self.tabs)
        self._menus()
        self.tabs.currentChanged.connect(self.on_tab)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.interval = 1000
        self.timer.start(self.interval)
        self.theme_timer = QtCore.QTimer(self)
        self.theme_timer.timeout.connect(self.check_theme)
        self.theme_timer.start(10000)
        self.tabs.setCurrentIndex(0)   # abre sempre em Desempenho
        self.on_tab(0)

    # ---- tamanho e posição (sempre dentro da área útil do ecrã, acima do painel)
    def _screen_area(self):
        scr = None
        try:
            scr = QtGui.QGuiApplication.screenAt(QtGui.QCursor.pos())
        except Exception:  # noqa: BLE001
            pass
        if scr is None:
            scr = QtWidgets.QApplication.primaryScreen()
        return scr.availableGeometry()   # exclui painéis/barras de tarefas

    def fit_to_screen(self):
        a = self._screen_area()
        self.setMinimumSize(min(760, int(a.width() * 0.9)), min(480, int(a.height() * 0.9)))
        w, h = int(a.width() * 0.9), int(a.height() * 0.9)
        self.resize(w, h)
        self.move(a.x() + (a.width() - w) // 2, a.y() + (a.height() - h) // 2)

    def _clamp_to_screen(self):
        """Depois de visível, conta a moldura da janela e garante que cabe na área útil."""
        a = self._screen_area()
        fr = self.frameGeometry()
        ew, eh = max(0, fr.width() - self.width()), max(0, fr.height() - self.height())
        w = min(self.width(), a.width() - ew)
        h = min(self.height(), a.height() - eh)
        if (w, h) != (self.width(), self.height()):
            self.resize(w, h)
        x = a.x() + (a.width() - (w + ew)) // 2
        y = a.y() + (a.height() - (h + eh)) // 2
        self.move(x, y)

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._placed:
            self._placed = True
            QtCore.QTimer.singleShot(0, self._clamp_to_screen)

    # ---- menus
    def _menus(self):
        mb = self.menuBar()
        m1 = mb.addMenu(_("Ficheiro"))
        a = QAction(_("Executar nova tarefa…"), self)
        a.setShortcut("Ctrl+N")
        a.triggered.connect(self.new_task)
        m1.addAction(a)
        m1.addSeparator()
        q = QAction(_("Sair"), self)
        q.setShortcut("Ctrl+Q")
        q.triggered.connect(self.close)
        m1.addAction(q)
        m2 = mb.addMenu(_("Opções"))
        self.act_top = QAction(_("Sempre visível"), self)
        self.act_top.setCheckable(True)
        self.act_top.toggled.connect(self.set_on_top)
        m2.addAction(self.act_top)
        m3 = mb.addMenu(_("Ver"))
        r = QAction(_("Atualizar agora"), self)
        r.setShortcut("F5")
        r.triggered.connect(self.tick)
        m3.addAction(r)
        sp = m3.addMenu(_("Velocidade de atualização"))
        grp_cls = getattr(QtGui, "QActionGroup", None) or QtWidgets.QActionGroup
        grp = grp_cls(self)
        grp.setExclusive(True)
        for txt, ms in ((_("Alta"), 500), (_("Normal"), 1000), (_("Baixa"), 4000), (_("Pausada"), 0)):
            ac = QAction(txt, self)
            ac.setCheckable(True)
            ac.setChecked(ms == 1000)
            ac.triggered.connect((lambda v: lambda: self.set_speed(v))(ms))
            grp.addAction(ac)
            sp.addAction(ac)
        m4 = mb.addMenu(_("Ajuda"))
        ab = QAction(_("Sobre"), self)
        ab.triggered.connect(self.about)
        m4.addAction(ab)

    def set_on_top(self, on):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()

    def set_speed(self, ms):
        self.interval = ms
        if ms:
            self.timer.start(ms)
        else:
            self.timer.stop()

    def about(self):
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(_("Sobre"))
        lp = logo_path()
        if lp:
            box.setIconPixmap(QtGui.QPixmap(lp).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        box.setText("<b>Mainuan Gerenciador Tarefas</b><br>%s<br><br>© David Caixinha" %
                    _("Monitor de sistema e de tarefas para Linux, inspirado no Gerenciador de Tarefas do Windows 10."))
        box.exec() if hasattr(box, "exec") else box.exec_()

    # ---- ciclo
    def on_tab(self, i):
        pg = self.pages[i]
        pg.on_show()
        pg.refresh(self.sm)

    def tick(self):
        self.sm.sample()
        self.pages[self.tabs.currentIndex()].refresh(self.sm)

    def check_theme(self):
        d = detect_dark()
        if d != T.get("dark"):
            set_theme(d)
            QtWidgets.QApplication.instance().setStyleSheet(build_qss())
            for pg in self.pages:
                pg.on_theme()
            self.update()

    def closeEvent(self, ev):
        self.timer.stop()
        for pg in self.pages:
            pg.shutdown()
        self.sm.history.save()
        super().closeEvent(ev)

    # ---- diálogos
    def notify(self, title, text, ok=True):
        box = QtWidgets.QMessageBox.information if ok else QtWidgets.QMessageBox.warning
        box(self, title, text)

    def ask(self, title, text):
        r = QtWidgets.QMessageBox.question(self, title, text,
                                           QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                           QtWidgets.QMessageBox.No)
        return r == QtWidgets.QMessageBox.Yes

    def new_task(self):
        txt, ok = QtWidgets.QInputDialog.getText(self, _("Executar nova tarefa"),
                                                 _("Escreva o comando ou o programa a executar:"))
        if not ok or not txt.strip():
            return
        try:
            subprocess.Popen(shlex.split(txt), start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, ValueError) as e:
            self.notify(_("Erro"), str(e), ok=False)

    # ---- ações sobre processos
    def open_location(self, pid):
        for p in self.sm.procs:
            if p.pid == pid and p.exe:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(p.exe)))
                return
        self.notify(_("Erro"), _("Não foi possível determinar a localização do ficheiro."), ok=False)

    def signal_pids(self, pids, sig, tree=False, force=False):
        allp = set(pids)
        if tree:
            for pid in pids:
                try:
                    for c in psutil.Process(pid).children(recursive=True):
                        allp.add(c.pid)
                except psutil.Error:
                    pass
        allp.discard(os.getpid())
        allp.discard(1)
        if not allp:
            return
        foreign = [p for p in self.sm.procs if p.pid in allp and not p.mine]
        if force or foreign or len(allp) > 15:
            if not self.ask(_("Finalizar tarefa"),
                            _("Finalizar {n} processo(s)? Processos do sistema ou de outros utilizadores podem afetar o funcionamento do computador.").format(n=len(allp))):
                return
        denied = []
        for pid in sorted(allp, reverse=True):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                denied.append(pid)
        if denied:
            self.helper(["kill", "KILL" if sig == signal.SIGKILL else "TERM"] + denied)

    def set_nice(self, pids, nice):
        denied = []
        for pid in pids:
            try:
                psutil.Process(pid).nice(nice)
            except psutil.AccessDenied:
                denied.append(pid)
            except psutil.NoSuchProcess:
                pass
        if denied:
            self.helper(["renice", nice] + denied)

    def set_affinity(self, pid):
        try:
            cur = psutil.Process(pid).cpu_affinity()
        except psutil.Error:
            self.notify(_("Erro"), _("Não foi possível ler a afinidade deste processo."), ok=False)
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(_("Afinidade do processador"))
        v = QtWidgets.QVBoxLayout(dlg)
        v.addWidget(label(_("Escolha os processadores onde o processo pode ser executado:"), wrap=True))
        boxes = []
        grid = QtWidgets.QGridLayout()
        for i in range(S.NCPU):
            cb = QtWidgets.QCheckBox(_("Processador %d") % i)
            cb.setChecked(i in cur)
            boxes.append(cb)
            grid.addWidget(cb, i % 8, i // 8)
        v.addLayout(grid)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if not (dlg.exec() if hasattr(dlg, "exec") else dlg.exec_()):
            return
        cpus = [i for i, b in enumerate(boxes) if b.isChecked()]
        if not cpus:
            self.notify(_("Erro"), _("Selecione pelo menos um processador."), ok=False)
            return
        try:
            psutil.Process(pid).cpu_affinity(cpus)
        except psutil.AccessDenied:
            self.helper(["affinity", ",".join(map(str, cpus)), pid])
        except psutil.Error as e:
            self.notify(_("Erro"), str(e), ok=False)

    # ---- ações privilegiadas (pkexec)
    def helper(self, args, after=None, fail=None):
        self._reap()

        def work():
            rc, msg = run_helper(args)
            return (after, fail, rc, msg)

        t = Task(work, parent=self)
        t.done.connect(self._helper_done)
        t.finished.connect(self._reap)
        self.tasks.append(t)
        t.start()

    def _helper_done(self, res):
        if isinstance(res, Exception):
            self.notify(_("Erro"), str(res), ok=False)
            return
        after, fail, rc, msg = res
        if rc == 0:
            if after:
                after()
            return
        if fail:
            fail()
        if rc not in (126, 127):  # 126: autenticação cancelada
            self.notify(_("Erro"), msg or _("A operação falhou."), ok=False)

    def _reap(self):
        keep = []
        for t in self.tasks:
            if t.isFinished():
                t.deleteLater()
            else:
                keep.append(t)
        self.tasks = keep


def main():
    global FONT
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("mainuan-gerenciador-tarefas")
    try:
        app.setDesktopFileName("mainuan-gerenciador-tarefas")
    except AttributeError:
        pass
    FONT = pick_font()
    set_theme(detect_dark())
    app.setStyleSheet(build_qss())
    sm = S.Sampler(i18n.lang_codes(i18n.get_lang()))
    sm.sample()
    win = MainWindow(sm)
    win.show()
    return app.exec() if hasattr(app, "exec") else app.exec_()


if __name__ == "__main__":
    sys.exit(main())
