#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Ações privilegiadas do Mainuan Gerenciador Tarefas (executado com pkexec).
Todos os argumentos são validados; nada é passado a um shell."""
import os
import pwd
import re
import subprocess
import sys

INSTALL = "/usr/lib/mainuan-gerenciador-tarefas/install-tools.sh"
UNIT_RE = re.compile(r"^[A-Za-z0-9:_.@\\-]{1,200}\.service$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def pids_from(args):
    out = []
    for a in args:
        if not a.isdigit():
            die("PID inválido: %s" % a)
        p = int(a)
        if p <= 1 or p == os.getpid():
            die("PID não permitido: %d" % p)
        out.append(p)
    if not out:
        die("Nenhum PID indicado")
    return out


def main(argv):
    if os.geteuid() != 0:
        die("Requer privilégios de administrador.")
    if len(argv) < 2:
        die("Uso: helper.py <ação> [argumentos]")
    act, args = argv[1], argv[2:]
    if act == "service":
        if len(args) != 2 or args[0] not in ("start", "stop", "restart") or not UNIT_RE.match(args[1]):
            die("Argumentos inválidos")
        r = subprocess.run(["/usr/bin/systemctl", args[0], "--", args[1]], capture_output=True, text=True)
        sys.stderr.write(r.stderr)
        return r.returncode
    if act == "kill":
        import signal
        if len(args) < 2 or args[0] not in ("TERM", "KILL"):
            die("Argumentos inválidos")
        sig = signal.SIGTERM if args[0] == "TERM" else signal.SIGKILL
        rc = 0
        for p in pids_from(args[1:]):
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
            except OSError as e:
                print("%d: %s" % (p, e), file=sys.stderr)
                rc = 1
        return rc
    if act == "renice":
        if len(args) < 2 or not re.match(r"^-?\d+$", args[0]) or not -20 <= int(args[0]) <= 19:
            die("Argumentos inválidos")
        rc = 0
        for p in pids_from(args[1:]):
            try:
                os.setpriority(os.PRIO_PROCESS, p, int(args[0]))
            except OSError as e:
                print("%d: %s" % (p, e), file=sys.stderr)
                rc = 1
        return rc
    if act == "affinity":
        if len(args) != 2 or not re.match(r"^\d+(,\d+)*$", args[0]):
            die("Argumentos inválidos")
        pid = pids_from(args[1:])[0]
        try:
            os.sched_setaffinity(pid, {int(x) for x in args[0].split(",")})
        except OSError as e:
            die(str(e), 1)
        return 0
    if act == "terminate-user":
        if len(args) != 1 or not USER_RE.match(args[0]):
            die("Argumentos inválidos")
        try:
            pw = pwd.getpwnam(args[0])
        except KeyError:
            die("Utilizador inexistente")
        caller = int(os.environ.get("PKEXEC_UID", "-1"))
        if pw.pw_uid < 1000 or pw.pw_uid == caller:
            die("Utilizador não permitido")
        r = subprocess.run(["/usr/bin/loginctl", "terminate-user", args[0]], capture_output=True, text=True)
        sys.stderr.write(r.stderr)
        return r.returncode
    if act == "install-tools":
        if len(args) > 1 or (args and args[0] not in ("htop", "fastfetch")):
            die("Argumentos inválidos")
        return subprocess.run([INSTALL] + args).returncode
    die("Ação desconhecida: %s" % act)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
