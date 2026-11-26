# -*- coding: utf-8 -*-
"""Recolha de dados do sistema para o Mainuan Gerenciador Tarefas (sem Qt)."""
import collections
import glob
import json
import os
import pwd
import re
import shlex
import shutil
import subprocess
import time

import psutil

HIST = 60
NCPU = psutil.cpu_count(logical=True) or 1
ME = pwd.getpwuid(os.getuid()).pw_name
DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "mainuan-gerenciador-tarefas")


def run(cmd, timeout=6):
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.stdout
    except Exception:
        return ""


def read(path, default=""):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


# --------------------------------------------------------------- formatação
_DEC = [","]


def set_decimal(sep):
    _DEC[0] = sep


def num(v, d=1):
    s = ("%." + str(d) + "f") % v
    return s.replace(".", _DEC[0])


def fmt_bytes(n):
    n = float(n)
    for unit, div in (("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= div:
            return "%s %s" % (num(n / div, 1 if n / div < 100 else 0), unit)
    return "%d B" % n


def fmt_mem(n):
    """Memória como no Windows: MB abaixo de 1 GB, GB acima."""
    n = float(n)
    if n >= 1 << 30:
        return "%s GB" % num(n / (1 << 30), 1)
    return "%s MB" % num(n / (1 << 20), 1)


def fmt_rate(bps):
    return fmt_bytes(bps) + "/s"


def fmt_bits(bps):
    b = float(bps) * 8
    if b >= 1e9:
        return "%s Gbps" % num(b / 1e9, 1)
    if b >= 1e6:
        return "%s Mbps" % num(b / 1e6, 1)
    return "%s Kbps" % num(b / 1e3, 1)


def fmt_secs(s):
    s = int(s)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    base = "%d:%02d:%02d" % (h, m, s)
    return ("%d:" % d) + base if d else base


def fmt_cpu_time(s):
    s = int(s)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return "%d:%02d:%02d" % (h, m, s)


# --------------------------------------------------------------- aplicações (.desktop)
_SKIP_CMDS = {"sh", "bash", "dash", "env", "python", "python3", "java", "flatpak", "snap",
              "xdg-open", "gtk-launch", "kioclient", "kioclient5", "konsole", "gnome-terminal",
              "xterm", "x-terminal-emulator", "pkexec", "sudo", "gksu", "nohup"}


def _desktop_cmd(exec_line):
    try:
        toks = shlex.split(exec_line)
    except ValueError:
        toks = exec_line.split()
    for t in toks:
        if t == "env" or "=" in t.split("/")[0] or t.startswith("-") or t.startswith("%"):
            continue
        b = os.path.basename(t)
        if b in _SKIP_CMDS:
            return None
        return b
    return None


class DesktopIndex:
    def __init__(self, lang_codes):
        self.by_cmd = {}
        keys = ["Name[%s]" % c for c in lang_codes]
        dirs = ["/usr/share/applications", "/usr/local/share/applications",
                os.path.expanduser("~/.local/share/applications"),
                "/var/lib/snapd/desktop/applications",
                "/var/lib/flatpak/exports/share/applications",
                os.path.expanduser("~/.local/share/flatpak/exports/share/applications")]
        for d in dirs:
            for path in glob.glob(os.path.join(d, "*.desktop")):
                self._load(path, keys)

    def _load(self, path, keys):
        data = {}
        try:
            with open(path, "r", errors="replace") as f:
                inside = False
                for line in f:
                    line = line.strip()
                    if line.startswith("["):
                        if inside:
                            break
                        inside = line == "[Desktop Entry]"
                        continue
                    if inside and "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        data.setdefault(k.strip(), v.strip())
        except OSError:
            return
        if data.get("Type") != "Application" or data.get("NoDisplay", "").lower() == "true" \
                or data.get("Hidden", "").lower() == "true":
            return
        cmd = _desktop_cmd(data.get("Exec", ""))
        if not cmd:
            return
        name = next((data[k] for k in keys if k in data), data.get("Name", cmd))
        self.by_cmd.setdefault(cmd, name)
        wm = data.get("StartupWMClass")
        if wm:
            self.by_cmd.setdefault(wm, name)

    def match(self, name, exe, cmdline):
        cands = []
        if exe:
            cands.append(os.path.basename(exe))
        if name:
            cands.append(name)
        if cmdline:
            c0 = os.path.basename(cmdline[0].split(" ")[0])
            cands.append(c0)
            if c0.startswith("python") and len(cmdline) > 1:
                cands.append(os.path.splitext(os.path.basename(cmdline[1]))[0])
        for c in cands:
            if c in self.by_cmd:
                return self.by_cmd[c]
        return None


# --------------------------------------------------------------- processos
class Proc:
    __slots__ = ("pid", "ppid", "name", "user", "status", "nice", "threads", "mem", "cpu",
                 "disk", "cmd", "exe", "kernel", "kind", "disp", "cpu_time", "rd", "wr", "mine")


class Sampler:
    def __init__(self, lang_codes=("en",)):
        self.desk = DesktopIndex(lang_codes)
        self.procs = []
        self.t_last = None
        self._io = {}
        self._disk_prev = None
        self._net_prev = None
        self.hist = {}
        self.cpu = 0.0
        self.cpu_core = [0.0] * NCPU
        self.freq = 0.0
        self.vm = psutil.virtual_memory()
        self.swap = psutil.swap_memory()
        self.disks = {}
        self.nets = {}
        self.gpus = []
        self._gpu_t = 0
        self.threads_total = 0
        self.history = AppHistory()
        psutil.cpu_percent(None)
        psutil.cpu_percent(None, percpu=True)

    def series(self, name):
        h = self.hist.get(name)
        if h is None:
            h = collections.deque([0.0] * HIST, maxlen=HIST)
            self.hist[name] = h
        return h

    # ---- amostragem
    def sample(self):
        now = time.monotonic()
        dt = (now - self.t_last) if self.t_last else 1.0
        dt = max(dt, 0.05)
        self.t_last = now
        self._sample_procs(dt)
        self.cpu = psutil.cpu_percent(None)
        self.cpu_core = psutil.cpu_percent(None, percpu=True)
        try:
            f = psutil.cpu_freq()
            self.freq = (f.current / 1000.0) if f else 0.0
        except Exception:
            self.freq = 0.0
        self.vm = psutil.virtual_memory()
        self.swap = psutil.swap_memory()
        self.series("cpu").append(self.cpu)
        for i, v in enumerate(self.cpu_core):
            self.series("core%d" % i).append(v)
        self.series("mem").append(self.vm.percent)
        self._sample_disks(dt)
        self._sample_nets(dt)
        self._sample_gpu(now)
        self.history.update(self.procs)

    def _sample_procs(self, dt):
        attrs = ["pid", "ppid", "name", "username", "status", "nice", "num_threads",
                 "memory_info", "cpu_percent", "cpu_times", "cmdline", "exe", "io_counters"]
        out = []
        io_new = {}
        threads = 0
        for p in psutil.process_iter(attrs, ad_value=None):
            i = p.info
            try:
                pr = Proc()
                pr.pid = i["pid"]
                pr.ppid = i["ppid"] or 0
                pr.name = i["name"] or "?"
                pr.user = i["username"] or "?"
                pr.status = i["status"] or ""
                pr.nice = i["nice"] if i["nice"] is not None else 0
                pr.threads = i["num_threads"] or 0
                mi = i["memory_info"]
                pr.mem = max(0, (mi.rss - getattr(mi, "shared", 0))) if mi else 0
                pr.cpu = min(100.0, (i["cpu_percent"] or 0.0) / NCPU)
                ct = i["cpu_times"]
                pr.cpu_time = (ct.user + ct.system) if ct else 0.0
                pr.cmd = i["cmdline"] or []
                pr.exe = i["exe"] or ""
                io = i["io_counters"]
                pr.rd = io.read_bytes if io else 0
                pr.wr = io.write_bytes if io else 0
                key = (pr.pid, pr.name)
                io_new[key] = pr.rd + pr.wr
                prev = self._io.get(key)
                pr.disk = max(0.0, (pr.rd + pr.wr - prev) / dt) if prev is not None else 0.0
                pr.kernel = (not pr.cmd) and pr.ppid in (0, 2) and not pr.exe
                pr.mine = pr.user == ME
                threads += pr.threads
                self._classify(pr)
                out.append(pr)
            except Exception:
                continue
        self._io = io_new
        self.procs = out
        self.threads_total = threads

    def _classify(self, pr):
        if pr.kernel:
            pr.kind, pr.disp = "system", "kernel"
        elif pr.mine:
            app = self.desk.match(pr.name, pr.exe, pr.cmd)
            if app:
                pr.kind, pr.disp = "apps", app
            else:
                pr.kind, pr.disp = "bg", pr.name
        else:
            pr.kind, pr.disp = "system", pr.name

    def groups(self):
        """{kind: {disp: [Proc,...]}} para a página Processos."""
        g = {"apps": {}, "bg": {}, "system": {}}
        for p in self.procs:
            g[p.kind].setdefault(p.disp, []).append(p)
        return g

    def users(self):
        u = {}
        for p in self.procs:
            u.setdefault(p.user, []).append(p)
        return u

    # ---- discos
    @staticmethod
    def _is_phys(name):
        return bool(re.match(r"^(sd[a-z]+|vd[a-z]+|xvd[a-z]+|hd[a-z]+|nvme\d+n\d+|mmcblk\d+)$", name))

    def disk_names(self):
        try:
            io = psutil.disk_io_counters(perdisk=True) or {}
        except Exception:
            io = {}
        return sorted(n for n in io if self._is_phys(n))

    def _sample_disks(self, dt):
        try:
            io = psutil.disk_io_counters(perdisk=True) or {}
        except Exception:
            return
        prev = self._disk_prev or {}
        for n, c in io.items():
            if not self._is_phys(n):
                continue
            p = prev.get(n)
            busy = rd = wr = resp = 0.0
            if p:
                busy = min(100.0, max(0.0, (getattr(c, "busy_time", 0) - getattr(p, "busy_time", 0)) / (dt * 10.0)))
                rd = max(0.0, (c.read_bytes - p.read_bytes) / dt)
                wr = max(0.0, (c.write_bytes - p.write_bytes) / dt)
                ops = (c.read_count - p.read_count) + (c.write_count - p.write_count)
                tm = (c.read_time - p.read_time) + (c.write_time - p.write_time)
                resp = (tm / ops) if ops > 0 else 0.0
            self.disks[n] = dict(busy=busy, rd=rd, wr=wr, resp=resp)
            self.series("disk:%s:busy" % n).append(busy)
            self.series("disk:%s:rate" % n).append(rd + wr)
        self._disk_prev = io

    # ---- rede
    def net_names(self):
        names = []
        try:
            stats = psutil.net_if_stats()
        except Exception:
            return names
        for n, s in stats.items():
            if n == "lo" or not s.isup:
                continue
            if re.match(r"^(docker|veth|br-|virbr|vmnet|tun|tap|vboxnet|lxc|flannel|cni)", n):
                continue
            names.append(n)
        return sorted(names)

    def _sample_nets(self, dt):
        try:
            io = psutil.net_io_counters(pernic=True) or {}
        except Exception:
            return
        prev = self._net_prev or {}
        for n, c in io.items():
            p = prev.get(n)
            tx = rx = 0.0
            if p:
                tx = max(0.0, (c.bytes_sent - p.bytes_sent) / dt)
                rx = max(0.0, (c.bytes_recv - p.bytes_recv) / dt)
            self.nets[n] = dict(tx=tx, rx=rx)
            self.series("net:%s:tx" % n).append(tx)
            self.series("net:%s:rx" % n).append(rx)
        self._net_prev = io

    # ---- GPU
    def _sample_gpu(self, now):
        if now - self._gpu_t < 2.0 and self._gpu_t:
            for i, g in enumerate(self.gpus):
                self.series("gpu%d" % i).append(g["util"])
                self.series("gpumem%d" % i).append(g["mem_pct"])
            return
        self._gpu_t = now
        self.gpus = detect_gpus()
        for i, g in enumerate(self.gpus):
            self.series("gpu%d" % i).append(g["util"])
            self.series("gpumem%d" % i).append(g["mem_pct"])


def detect_gpus():
    gpus = []
    if shutil.which("nvidia-smi"):
        out = run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,driver_version",
                   "--format=csv,noheader,nounits"], timeout=3)
        for line in out.splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 5:
                try:
                    used, total = float(parts[2]) * 1048576, float(parts[3]) * 1048576
                    gpus.append(dict(name=parts[0], util=float(parts[1]), mem_used=used, mem_total=total,
                                     mem_pct=(used / total * 100) if total else 0.0, driver=parts[4]))
                except ValueError:
                    pass
    for dev in sorted(glob.glob("/sys/class/drm/card[0-9]/device")):
        busy = read(os.path.join(dev, "gpu_busy_percent"))
        if not busy.isdigit():
            continue
        used = read(os.path.join(dev, "mem_info_vram_used"))
        total = read(os.path.join(dev, "mem_info_vram_total"))
        u = float(used) if used.isdigit() else 0.0
        t = float(total) if total.isdigit() else 0.0
        name = read(os.path.join(dev, "product_name")) or "AMD GPU"
        gpus.append(dict(name=name, util=float(busy), mem_used=u, mem_total=t,
                         mem_pct=(u / t * 100) if t else 0.0, driver="amdgpu"))
    return gpus


# --------------------------------------------------------------- informação estática
def cpu_model():
    for line in read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    out = run(["lscpu"])
    m = re.search(r"Model name:\s*(.+)", out)
    return m.group(1).strip() if m else "CPU"


def _to_kb(txt):
    m = re.match(r"([\d.]+)\s*([KMG]i?B)", txt)
    if not m:
        return 0.0
    v = float(m.group(1))
    return v * {"K": 1, "M": 1024, "G": 1048576}[m.group(2)[0]]


def cpu_static():
    info = read("/proc/cpuinfo")
    sockets = len(set(re.findall(r"physical id\s*:\s*(\d+)", info))) or 1
    flags = ""
    for line in info.splitlines():
        if line.startswith("flags"):
            flags = line
            break
    virt = (" vmx" in flags) or (" svm" in flags)
    out = run(["lscpu"])
    caches = {}
    for key in ("L1d", "L1i", "L2", "L3"):
        m = re.search(r"^%s cache:\s*([\d.]+\s*[KMG]i?B)" % key, out, re.M)
        caches[key] = _to_kb(m.group(1)) if m else 0.0
    l1 = caches["L1d"] + caches["L1i"]
    try:
        maxf = psutil.cpu_freq().max / 1000.0
    except Exception:
        maxf = 0.0
    return dict(sockets=sockets, cores=psutil.cpu_count(logical=False) or NCPU, logical=NCPU,
                virt=virt, l1=l1, l2=caches["L2"], l3=caches["L3"], maxf=maxf)


def fmt_kb(kb):
    if not kb:
        return "—"
    if kb >= 1024:
        return "%s MB" % num(kb / 1024.0, 1)
    return "%d KB" % kb


def uptime():
    return time.time() - psutil.boot_time()


def open_handles():
    v = read("/proc/sys/fs/file-nr").split()
    return int(v[0]) if v and v[0].isdigit() else 0


def disk_info(name):
    base = "/sys/block/%s" % name
    size = read(base + "/size")
    cap = int(size) * 512 if size.isdigit() else 0
    model = (read(base + "/device/model") or read(base + "/device/name") or name).strip()
    rot = read(base + "/queue/rotational")
    kind = "HDD" if rot == "1" else ("SSD" if rot == "0" else "—")
    if name.startswith("nvme"):
        kind = "SSD (NVMe)"
    formatted = 0
    is_system = False
    for part in psutil.disk_partitions(all=False):
        dev = os.path.basename(part.device)
        if dev == name or dev.startswith(name) and re.match(r"^p?\d+$", dev[len(name):]):
            try:
                formatted += psutil.disk_usage(part.mountpoint).total
            except OSError:
                pass
            if part.mountpoint == "/":
                is_system = True
    has_swap = any(os.path.basename(l.split()[0]).startswith(name) for l in read("/proc/swaps").splitlines()[1:] if l.split())
    return dict(model=model, cap=cap, kind=kind, formatted=formatted, system=is_system, swap=has_swap)


def net_info(name):
    wifi = os.path.isdir("/sys/class/net/%s/wireless" % name)
    ipv4 = ipv6 = ""
    try:
        for a in psutil.net_if_addrs().get(name, []):
            if a.family.name == "AF_INET" and not ipv4:
                ipv4 = a.address
            elif a.family.name == "AF_INET6" and not ipv6:
                ipv6 = a.address.split("%")[0]
    except Exception:
        pass
    ssid = ""
    if wifi:
        if shutil.which("iwgetid"):
            ssid = run(["iwgetid", "-r", name]).strip()
        if not ssid and shutil.which("nmcli"):
            for line in run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"]).splitlines():
                if line.startswith("yes:"):
                    ssid = line[4:]
                    break
    speed = 0
    try:
        speed = psutil.net_if_stats()[name].speed
    except Exception:
        pass
    return dict(wifi=wifi, ipv4=ipv4, ipv6=ipv6, ssid=ssid, speed=speed)


# --------------------------------------------------------------- histórico de aplicações
class AppHistory:
    PATH = os.path.join(DATA_DIR, "history.json")

    def __init__(self):
        self.since = time.time()
        self.apps = {}
        self._last = {}
        self._dirty = 0
        self._saved = time.time()
        try:
            with open(self.PATH) as f:
                d = json.load(f)
            self.since = float(d.get("since", self.since))
            self.apps = d.get("apps", {})
        except (OSError, ValueError):
            pass

    def update(self, procs):
        new = {}
        for p in procs:
            if p.kind != "apps":
                continue
            key = (p.pid, p.name)
            cur = (p.cpu_time, p.rd, p.wr)
            old = self._last.get(key)
            new[key] = cur
            a = self.apps.setdefault(p.disp, {"cpu": 0.0, "rd": 0, "wr": 0, "peak": 0})
            if old:
                a["cpu"] += max(0.0, cur[0] - old[0])
                a["rd"] += max(0, cur[1] - old[1])
                a["wr"] += max(0, cur[2] - old[2])
            a["peak"] = max(a.get("peak", 0), p.mem)
        # memória pico por aplicação (soma dos processos no instante)
        tot = {}
        for p in procs:
            if p.kind == "apps":
                tot[p.disp] = tot.get(p.disp, 0) + p.mem
        for k, v in tot.items():
            self.apps[k]["peak"] = max(self.apps[k].get("peak", 0), v)
        self._last = new
        if time.time() - self._saved > 30:
            self.save()

    def save(self):
        self._saved = time.time()
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = self.PATH + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"since": self.since, "apps": self.apps}, f)
            os.replace(tmp, self.PATH)
        except OSError:
            pass

    def clear(self):
        self.since = time.time()
        self.apps = {}
        self.save()


# --------------------------------------------------------------- arranque (autostart)
AUTOSTART_USER = os.path.expanduser("~/.config/autostart")
AUTOSTART_SYS = "/etc/xdg/autostart"


def _parse_desktop(path):
    d = {}
    try:
        with open(path, "r", errors="replace") as f:
            inside = False
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    if inside:
                        break
                    inside = line == "[Desktop Entry]"
                    continue
                if inside and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    d.setdefault(k.strip(), v.strip())
    except OSError:
        pass
    return d


def list_autostart(lang_keys=()):
    entries = {}
    for origin, folder in (("system", AUTOSTART_SYS), ("user", AUTOSTART_USER)):
        for path in sorted(glob.glob(os.path.join(folder, "*.desktop"))):
            base = os.path.basename(path)
            d = _parse_desktop(path)
            if not d:
                continue
            name = next((d[k] for k in lang_keys if k in d), d.get("Name", base[:-8]))
            disabled = d.get("Hidden", "").lower() == "true" or \
                d.get("X-GNOME-Autostart-enabled", "").lower() == "false"
            e = entries.get(base, {"file": base, "name": name, "origin": origin, "exec": d.get("Exec", ""),
                                   "enabled": True, "comment": d.get("Comment", "")})
            if origin == "user":
                e["name"] = name if d.get("Name") else e["name"]
                e["exec"] = d.get("Exec", e["exec"])
                if e["origin"] == "system":
                    e["origin"] = "override"
            e["enabled"] = not disabled
            entries[base] = e
    return sorted(entries.values(), key=lambda e: e["name"].lower())


def set_autostart(file, enabled):
    os.makedirs(AUTOSTART_USER, exist_ok=True)
    upath = os.path.join(AUTOSTART_USER, file)
    spath = os.path.join(AUTOSTART_SYS, file)
    if os.path.exists(upath):
        lines = read(upath).splitlines()
    elif os.path.exists(spath):
        lines = read(spath).splitlines()
    else:
        return False
    out, in_entry, done = [], False, False
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            if in_entry and not done:
                out.extend(_flags(enabled))
                done = True
            in_entry = s == "[Desktop Entry]"
            out.append(line)
            continue
        if in_entry and (s.startswith("Hidden=") or s.startswith("X-GNOME-Autostart-enabled=")):
            continue
        out.append(line)
    if in_entry and not done:
        out.extend(_flags(enabled))
    with open(upath, "w") as f:
        f.write("\n".join(out) + "\n")
    return True


def _flags(enabled):
    return ["Hidden=false", "X-GNOME-Autostart-enabled=true"] if enabled else \
        ["Hidden=true", "X-GNOME-Autostart-enabled=false"]


def startup_impact(entry, procs):
    """Estimativa: usa o tempo de CPU e a memória do programa se estiver em execução."""
    cmd = _desktop_cmd(entry.get("exec", ""))
    if not cmd:
        return None
    mine = [p for p in procs if p.mine and (p.name == cmd or os.path.basename(p.exe or "") == cmd)]
    if not mine:
        return None
    cpu = sum(p.cpu_time for p in mine)
    mem = sum(p.mem for p in mine)
    if cpu >= 10 or mem > 500 * 1048576:
        return "high"
    if cpu >= 3 or mem > 150 * 1048576:
        return "mid"
    return "low"


# --------------------------------------------------------------- serviços
def list_services():
    out = run(["systemctl", "list-units", "--type=service", "--all", "--plain", "--no-legend",
               "--no-pager"], timeout=10)
    units = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4 and parts[0].endswith(".service"):
            units.append(dict(unit=parts[0], load=parts[1], active=parts[2], sub=parts[3],
                              desc=parts[4] if len(parts) > 4 else ""))
    units = [u for u in units if u["load"] != "not-found"]
    props = {}
    if units:
        names = [u["unit"] for u in units]
        for i in range(0, len(names), 150):
            sh = run(["systemctl", "show", "-p", "Id,MainPID,UnitFileState", "--no-pager"] + names[i:i + 150],
                     timeout=10)
            for block in sh.split("\n\n"):
                kv = dict(l.split("=", 1) for l in block.splitlines() if "=" in l)
                if "Id" in kv:
                    props[kv["Id"]] = kv
    for u in units:
        kv = props.get(u["unit"], {})
        pid = kv.get("MainPID", "0")
        u["pid"] = int(pid) if pid.isdigit() else 0
        u["enabled"] = kv.get("UnitFileState", "")
    return units
