# -*- coding: utf-8 -*-
"""Emulador de terminal mínimo (VT100/xterm) e processo num pseudo-terminal.

Usado para mostrar, dentro da app, o resultado visual (com cores) do Fastfetch,
e o Htop interativo. Sem dependências externas.
"""
import codecs
import fcntl
import os
import pty
import shutil
import signal
import struct
import subprocess
import termios
import unicodedata

BOLD, DIM, ITALIC, UNDER, BLINK, REVERSE, HIDDEN, STRIKE = 1, 2, 4, 8, 16, 32, 64, 128
BLANK = (" ", None, None, 0)

ACS = {"j": "┘", "k": "┐", "l": "┌", "m": "└", "n": "┼", "q": "─", "t": "├", "u": "┤",
       "v": "┴", "w": "┬", "x": "│", "a": "▒", "`": "◆", "~": "·", "o": "⎺", "s": "⎽",
       "0": "█", "f": "°", "g": "±", "h": "░", "y": "≤", "z": "≥", "{": "π", "|": "≠",
       "}": "£"}


def cwidth(ch):
    o = ord(ch)
    if o < 0x300:
        return 1
    if unicodedata.combining(ch) or o in (0x200B, 0x200C, 0x200D, 0xFE0F):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


class Screen:
    def __init__(self, cols=80, rows=24, respond=None):
        self.respond = respond or (lambda data: None)
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.alt = None
        self.reset()

    # ------------------------------------------------------------ estado
    def reset(self):
        self.bg = None
        self.main = [self._row() for _ in range(self.rows)]
        self.buf = self.main
        self.alt = None
        self.x = self.y = 0
        self.fg = None
        self.fl = 0
        self.top, self.bot = 0, self.rows - 1
        self.tabs = set(range(8, self.cols, 8))
        self.pending = False
        self.autowrap = True
        self.origin = False
        self.cursor_visible = True
        self.app_cursor = False
        self.mouse = 0
        self.mouse_sgr = False
        self.charsets = ["B", "B"]
        self.gl = 0
        self.saved = None
        self.state = 0
        self.csi = ""
        self.cs_slot = 0
        self.last = " "

    def _blank(self):
        return (" ", None, self.bg, 0) if self.bg is not None else BLANK

    def _row(self):
        return [self._blank()] * self.cols

    def resize(self, cols, rows):
        cols, rows = max(1, cols), max(1, rows)
        if cols == self.cols and rows == self.rows:
            return
        old_rows = self.rows
        for b in (self.main, self.alt):
            if b is None:
                continue
            active = b is self.buf
            for r in b:
                if len(r) < cols:
                    r.extend([BLANK] * (cols - len(r)))
                else:
                    del r[cols:]
            while len(b) < rows:
                b.append([BLANK] * cols)
            while len(b) > rows:
                if active and self.y > rows - 1:
                    del b[0]
                    self.y -= 1
                else:
                    b.pop()
        self.cols, self.rows = cols, rows
        self.x = min(self.x, cols - 1)
        self.y = max(0, min(self.y, rows - 1))
        self.top, self.bot = 0, rows - 1
        self.tabs = set(range(8, cols, 8))
        self.pending = False
        _ = old_rows

    # ------------------------------------------------------------ entrada
    def feed(self, data):
        text = self._decoder.decode(data)
        for c in text:
            self._char(c)

    def _char(self, c):
        st = self.state
        if st == 0:
            o = ord(c)
            if o < 32 or o == 127:
                self._c0(c)
            else:
                self._print(c)
        elif st == 1:
            self._esc(c)
        elif st == 2:
            o = ord(c)
            if 0x20 <= o <= 0x3F:
                self.csi += c
            elif 0x40 <= o <= 0x7E:
                self.state = 0
                self._csi(c)
            elif c == "\x1b":
                self.state = 1
            elif o < 32:
                self._c0(c)
            else:
                self.state = 0
        elif st == 3:
            if c == "\x07":
                self.state = 0
            elif c == "\x1b":
                self.state = 4
        elif st == 4:
            self.state = 0
            if c != "\\":
                self.state = 1
                self._esc(c)
        elif st == 5:
            if c in "B0AUK":
                self.charsets[self.cs_slot] = c
            self.state = 0
        elif st == 6:
            self.state = 0

    def _c0(self, c):
        if c == "\x1b":
            self.state = 1
        elif c == "\r":
            self.x = 0
            self.pending = False
        elif c in "\n\x0b\x0c":
            self._index()
        elif c == "\b":
            if self.x > 0:
                self.x -= 1
            self.pending = False
        elif c == "\t":
            self._tab(1)
        elif c == "\x0e":
            self.gl = 1
        elif c == "\x0f":
            self.gl = 0

    def _esc(self, c):
        self.state = 0
        if c == "[":
            self.csi = ""
            self.state = 2
        elif c == "]" or c in "PX^_":
            self.state = 3
        elif c in "()":
            self.cs_slot = 0 if c == "(" else 1
            self.state = 5
        elif c in "*+#%":
            self.state = 6
        elif c == "7":
            self._save()
        elif c == "8":
            self._restore()
        elif c == "D":
            self._index()
        elif c == "E":
            self.x = 0
            self._index()
        elif c == "M":
            self._rindex()
        elif c == "H":
            self.tabs.add(self.x)
        elif c == "c":
            self.reset()
        elif c == "\x1b":
            self.state = 1

    # ------------------------------------------------------------ texto
    def _print(self, c):
        if self.charsets[self.gl] == "0":
            c = ACS.get(c, c)
        w = cwidth(c)
        if w == 0:
            px = self.x if self.pending else self.x - 1
            if px >= 0:
                row = self.buf[self.y]
                ch, fg, bg, fl = row[px]
                row[px] = (ch + c, fg, bg, fl)
            return
        if self.pending:
            self.pending = False
            if self.autowrap:
                self.x = 0
                self._index()
        if self.x + w > self.cols:
            if self.autowrap:
                self.x = 0
                self._index()
            else:
                self.x = self.cols - w
        row = self.buf[self.y]
        row[self.x] = (c, self.fg, self.bg, self.fl)
        if w == 2 and self.x + 1 < self.cols:
            row[self.x + 1] = ("", self.fg, self.bg, self.fl)
        self.x += w
        if self.x >= self.cols:
            self.x = self.cols - 1
            self.pending = True
        self.last = c

    def _index(self):
        if self.y == self.bot:
            self._scroll_up(1)
        elif self.y < self.rows - 1:
            self.y += 1
        self.pending = False

    def _rindex(self):
        if self.y == self.top:
            self._scroll_down(1)
        elif self.y > 0:
            self.y -= 1
        self.pending = False

    def _scroll_up(self, n):
        n = min(n, self.bot - self.top + 1)
        for _ in range(n):
            del self.buf[self.top]
            self.buf.insert(self.bot, self._row())

    def _scroll_down(self, n):
        n = min(n, self.bot - self.top + 1)
        for _ in range(n):
            del self.buf[self.bot]
            self.buf.insert(self.top, self._row())

    def _tab(self, n):
        for _ in range(n):
            x = self.x + 1
            while x < self.cols - 1 and x not in self.tabs:
                x += 1
            self.x = min(x, self.cols - 1)
        self.pending = False

    def _save(self):
        self.saved = (self.x, self.y, self.fg, self.bg, self.fl, list(self.charsets),
                      self.gl, self.origin)

    def _restore(self):
        if self.saved is None:
            self.x = self.y = 0
            return
        (self.x, self.y, self.fg, self.bg, self.fl, cs, self.gl, self.origin) = self.saved
        self.charsets = list(cs)
        self.x = min(self.x, self.cols - 1)
        self.y = min(self.y, self.rows - 1)
        self.pending = False

    # ------------------------------------------------------------ CSI
    def _csi(self, final):
        buf = self.csi
        priv = ""
        if buf and buf[0] in "?<=>":
            priv, buf = buf[0], buf[1:]
        inter = ""
        while buf and buf[-1] in " !\"#$%&'()*+,-./":
            inter, buf = buf[-1] + inter, buf[:-1]
        raw = buf.split(";") if buf else []
        if final == "m" and not priv and not inter:
            self._sgr(raw if raw else ["0"])
            return
        params = []
        for part in raw:
            part = part.split(":")[0]
            params.append(int(part) if part.isdigit() else 0)
        n0 = params[0] if params else 0
        n = n0 or 1
        self.pending = False
        if inter:
            return
        if final == "@" and not priv:
            row = self.buf[self.y]
            row[self.x:self.x] = [self._blank()] * n
            del row[self.cols:]
        elif final == "A":
            lim = self.top if self.y >= self.top else 0
            self.y = max(lim, self.y - n)
        elif final in "Be":
            lim = self.bot if self.y <= self.bot else self.rows - 1
            self.y = min(lim, self.y + n)
        elif final in "Ca":
            self.x = min(self.cols - 1, self.x + n)
        elif final == "D":
            self.x = max(0, self.x - n)
        elif final == "E":
            self.y = min(self.rows - 1, self.y + n)
            self.x = 0
        elif final == "F":
            self.y = max(0, self.y - n)
            self.x = 0
        elif final in "G`":
            self.x = max(0, min(self.cols - 1, n - 1))
        elif final == "d":
            self._goto_row(n - 1)
        elif final in "Hf":
            r = (params[0] or 1) - 1 if params else 0
            c = (params[1] or 1) - 1 if len(params) > 1 else 0
            self._goto_row(r)
            self.x = max(0, min(self.cols - 1, c))
        elif final == "I":
            self._tab(n)
        elif final == "J":
            self._erase_display(n0)
        elif final == "K":
            self._erase_line(n0)
        elif final == "L":
            if self.top <= self.y <= self.bot:
                for _ in range(min(n, self.bot - self.y + 1)):
                    del self.buf[self.bot]
                    self.buf.insert(self.y, self._row())
        elif final == "M":
            if self.top <= self.y <= self.bot:
                for _ in range(min(n, self.bot - self.y + 1)):
                    del self.buf[self.y]
                    self.buf.insert(self.bot, self._row())
        elif final == "P":
            row = self.buf[self.y]
            del row[self.x:self.x + n]
            row.extend([self._blank()] * (self.cols - len(row)))
        elif final == "X":
            row = self.buf[self.y]
            k = min(n, self.cols - self.x)
            row[self.x:self.x + k] = [self._blank()] * k
        elif final == "S":
            self._scroll_up(n)
        elif final == "T" and not priv:
            self._scroll_down(n)
        elif final == "b":
            for _ in range(min(n, 500)):
                self._print(self.last)
        elif final == "g":
            if n0 == 0:
                self.tabs.discard(self.x)
            elif n0 == 3:
                self.tabs.clear()
        elif final in "hl":
            on = final == "h"
            for p in (params or [0]):
                self._mode(priv, p, on)
        elif final == "n" and not priv:
            if n0 == 5:
                self.respond(b"\x1b[0n")
            elif n0 == 6:
                yy = self.y - self.top if self.origin else self.y
                self.respond(("\x1b[%d;%dR" % (yy + 1, self.x + 1)).encode())
        elif final == "c":
            if priv == ">":
                self.respond(b"\x1b[>0;10;1c")
            elif not priv and n0 == 0:
                self.respond(b"\x1b[?62;c")
        elif final == "r" and not priv:
            top = (params[0] or 1) - 1 if params else 0
            bot = (params[1] or self.rows) - 1 if len(params) > 1 else self.rows - 1
            bot = min(bot, self.rows - 1)
            if 0 <= top < bot:
                self.top, self.bot = top, bot
                self.x = 0
                self.y = self.top if self.origin else 0
        elif final == "s" and not priv:
            self._save()
        elif final == "u" and not priv:
            self._restore()
        elif final == "t":
            if n0 == 18:
                self.respond(("\x1b[8;%d;%dt" % (self.rows, self.cols)).encode())
            elif n0 == 14:
                self.respond(("\x1b[4;%d;%dt" % (self.rows * 16, self.cols * 8)).encode())

    def _goto_row(self, r):
        if self.origin:
            self.y = max(self.top, min(self.bot, self.top + r))
        else:
            self.y = max(0, min(self.rows - 1, r))

    def _erase_line(self, mode):
        row = self.buf[self.y]
        b = self._blank()
        if mode == 0:
            row[self.x:] = [b] * (self.cols - self.x)
        elif mode == 1:
            row[:self.x + 1] = [b] * (self.x + 1)
        else:
            row[:] = [b] * self.cols

    def _erase_display(self, mode):
        if mode == 0:
            self._erase_line(0)
            for r in range(self.y + 1, self.rows):
                self.buf[r] = self._row()
        elif mode == 1:
            for r in range(0, self.y):
                self.buf[r] = self._row()
            self._erase_line(1)
        else:
            for r in range(self.rows):
                self.buf[r] = self._row()

    def _mode(self, priv, p, on):
        if priv == "?":
            if p == 1:
                self.app_cursor = on
            elif p == 6:
                self.origin = on
                self.x = 0
                self.y = self.top if on else 0
            elif p == 7:
                self.autowrap = on
            elif p == 25:
                self.cursor_visible = on
            elif p in (47, 1047, 1049):
                self._alt_screen(on, save=(p == 1049))
            elif p in (1000, 1002, 1003):
                self.mouse = p if on else 0
            elif p == 1006:
                self.mouse_sgr = on

    def _alt_screen(self, on, save):
        if on and self.alt is None:
            if save:
                self._save()
            self.alt = [self._row() for _ in range(self.rows)]
            self.buf = self.alt
            self.x = self.y = 0
        elif not on and self.alt is not None:
            self.alt = None
            self.buf = self.main
            if save:
                self._restore()

    def _sgr(self, items):
        i = 0
        while i < len(items):
            s = items[i]
            if ":" in s:
                sub = [int(v) if v.isdigit() else 0 for v in s.split(":")]
                k = sub[0]
                if k in (38, 48) and len(sub) >= 3:
                    col = None
                    if sub[1] == 5:
                        col = sub[2]
                    elif sub[1] == 2 and len(sub) >= 5:
                        col = tuple(sub[-3:])
                    if col is not None:
                        if k == 38:
                            self.fg = col
                        else:
                            self.bg = col
                elif k == 4:
                    if len(sub) > 1 and sub[1] == 0:
                        self.fl &= ~UNDER
                    else:
                        self.fl |= UNDER
                i += 1
                continue
            n = int(s) if s.isdigit() else 0
            if n == 0:
                self.fg = self.bg = None
                self.fl = 0
            elif n == 1:
                self.fl |= BOLD
            elif n == 2:
                self.fl |= DIM
            elif n == 3:
                self.fl |= ITALIC
            elif n in (4, 21):
                self.fl |= UNDER
            elif n in (5, 6):
                self.fl |= BLINK
            elif n == 7:
                self.fl |= REVERSE
            elif n == 8:
                self.fl |= HIDDEN
            elif n == 9:
                self.fl |= STRIKE
            elif n == 22:
                self.fl &= ~(BOLD | DIM)
            elif n == 23:
                self.fl &= ~ITALIC
            elif n == 24:
                self.fl &= ~UNDER
            elif n == 25:
                self.fl &= ~BLINK
            elif n == 27:
                self.fl &= ~REVERSE
            elif n == 28:
                self.fl &= ~HIDDEN
            elif n == 29:
                self.fl &= ~STRIKE
            elif 30 <= n <= 37:
                self.fg = n - 30
            elif 40 <= n <= 47:
                self.bg = n - 40
            elif 90 <= n <= 97:
                self.fg = n - 90 + 8
            elif 100 <= n <= 107:
                self.bg = n - 100 + 8
            elif n == 39:
                self.fg = None
            elif n == 49:
                self.bg = None
            elif n in (38, 48):
                col = None
                nxt = items[i + 1] if i + 1 < len(items) else ""
                if nxt == "5" and i + 2 < len(items):
                    col = int(items[i + 2]) if items[i + 2].isdigit() else 0
                    i += 2
                elif nxt == "2" and i + 4 < len(items):
                    vals = [int(v) if v.isdigit() else 0 for v in items[i + 2:i + 5]]
                    col = tuple(min(255, v) for v in vals)
                    i += 4
                if col is not None:
                    if n == 38:
                        self.fg = col
                    else:
                        self.bg = col
            i += 1

    # ------------------------------------------------------------ utilitários
    def dump(self):
        """Linhas de texto simples (para testes e para medir o conteúdo)."""
        return ["".join(c[0] for c in row).rstrip() for row in self.buf]

    def used_rows(self):
        for i in range(self.rows - 1, -1, -1):
            if any(c[0].strip() or c[2] is not None for c in self.buf[i]):
                return i + 1
        return 1


def _set_winsize(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


_CLEAN_ENV = ("KITTY_WINDOW_ID", "WEZTERM_EXECUTABLE", "ITERM_SESSION_ID", "TERM_PROGRAM",
              "TERM_PROGRAM_VERSION", "VTE_VERSION", "KONSOLE_VERSION", "KONSOLE_DBUS_SERVICE",
              "KONSOLE_DBUS_SESSION", "WT_SESSION", "TMUX", "STY", "LINES", "COLUMNS",
              "ALACRITTY_SOCKET", "ALACRITTY_LOG", "GHOSTTY_RESOURCES_DIR")


class PtyProcess:
    """Executa um comando num pseudo-terminal."""

    def __init__(self, argv, cols=100, rows=30):
        env = dict(os.environ)
        for k in _CLEAN_ENV:
            env.pop(k, None)
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        if "utf-8" not in (env.get("LC_ALL") or env.get("LC_CTYPE") or env.get("LANG", "")).lower().replace("utf8", "utf-8"):
            env["LANG"] = "C.UTF-8"
            env.pop("LC_ALL", None)
        master, slave = pty.openpty()
        _set_winsize(slave, rows, cols)
        self.master = master
        setsid = shutil.which("setsid")
        try:
            if setsid:
                self.proc = subprocess.Popen([setsid, "-c"] + list(argv), stdin=slave, stdout=slave,
                                             stderr=slave, close_fds=True, env=env)
            else:
                self.proc = subprocess.Popen(
                    list(argv), stdin=slave, stdout=slave, stderr=slave, close_fds=True, env=env,
                    start_new_session=True,
                    preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))
        finally:
            os.close(slave)
        os.set_blocking(master, False)

    def fileno(self):
        return self.master

    def read(self):
        """bytes (pode ser vazio) | None se não há dados | b'' em fim de ficheiro."""
        try:
            return os.read(self.master, 65536)
        except BlockingIOError:
            return None
        except OSError:
            return b""

    def write(self, data):
        view = memoryview(data)
        tries = 0
        while view and tries < 200:
            try:
                n = os.write(self.master, view)
                view = view[n:]
            except BlockingIOError:
                tries += 1
            except OSError:
                return

    def resize(self, cols, rows):
        try:
            _set_winsize(self.master, rows, cols)
        except OSError:
            pass

    def alive(self):
        return self.proc.poll() is None

    def close(self):
        try:
            if self.proc.poll() is None:
                try:
                    os.killpg(self.proc.pid, signal.SIGHUP)
                except (ProcessLookupError, PermissionError):
                    self.proc.terminate()
                try:
                    self.proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(self.proc.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        self.proc.kill()
                    self.proc.wait(timeout=1)
        finally:
            try:
                os.close(self.master)
            except OSError:
                pass
