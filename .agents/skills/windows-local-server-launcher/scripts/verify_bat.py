# -*- coding: utf-8 -*-
"""Verify a generated .bat launcher end-to-end without double-clicking.

Drives the real .bat through `cmd /c` and asserts the three scenarios that
historically caused 闪退:

  1. fresh start        -> [QW-LAUNCHER] SERVING + port LISTENING + HTTP 200
  2. kill, restart now  -> binds again (allow_reuse_address beat TIME_WAIT)
  3. already running    -> second run prints REUSE, does not crash, keeps 200

Trust only the ASCII markers and the HTTP code. Chinese captured through a pipe
looks garbled even when the .bat is correct -- that is a harness decoding
artifact, not a bug; never "fix" encoding based on it.

Usage:
    python verify_bat.py --bat "D:\\proj\\web\\启动预览.bat" \
        --url http://127.0.0.1:8777/web/index.html [--settle 4]

Exit 0 = all scenarios passed. Always cleans up listeners it started.
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

MARK = "[QW-LAUNCHER]"
IS_WIN = os.name == "nt"


def netstat_listening(port):
    """PIDs LISTENING on `port` (Windows), via netstat."""
    out = subprocess.run("netstat -ano", shell=True, capture_output=True).stdout
    out = out.decode("gbk", "replace") if IS_WIN else out.decode("utf-8", "replace")
    pids = []
    for line in out.splitlines():
        if "LISTENING" in line.upper() and re.search(r"[:\.]%d\s" % port, line):
            pids.append(line.split()[-1])
    return pids


def kill_pids(pids):
    for pid in set(pids):
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                               capture_output=True)
            else:
                subprocess.run(["kill", "-9", pid], capture_output=True)
        except Exception:
            pass


def http_code(url, tries=10, pause=0.6):
    last = None
    for _ in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=4).getcode()
        except Exception as e:
            last = e
            time.sleep(pause)
    return "ERR %r" % last


class Runner(object):
    """Runs the .bat, collects stdout in a thread (server blocks forever)."""

    def __init__(self, bat, env_extra=None):
        self.bat = bat
        self.cwd = os.path.dirname(os.path.abspath(bat))
        self.env = dict(os.environ)
        self.env["QW_LAUNCHER_NO_BROWSER"] = "1"   # never spawn browsers in tests
        if env_extra:
            self.env.update(env_extra)
        self.proc = None
        self.lines = []
        self._t = None

    def start(self):
        self.proc = subprocess.Popen(["cmd", "/c", os.path.basename(self.bat)]
                                     if IS_WIN else ["sh", "-c", self.bat],
                                     cwd=self.cwd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, env=self.env)
        self._t = threading.Thread(target=self._pump)
        self._t.daemon = True
        self._t.start()

    def _pump(self):
        try:
            for raw in iter(self.proc.stdout.readline, b""):
                text = raw.decode("gbk", "replace") if IS_WIN else raw.decode("utf-8", "replace")
                self.lines.append(text)
        except Exception:
            pass

    def output(self):
        return "".join(self.lines)

    def exited(self):
        return self.proc is not None and self.proc.poll() is not None

    def stop(self):
        if self.proc and not self.exited():
            kill_pids([str(self.proc.pid)])
        kill_pids(netstat_listening(self.port) if getattr(self, "port", None) else [])


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Verify .bat local server launcher")
    p.add_argument("--bat", required=True)
    p.add_argument("--url", required=True, help="Full page URL the launcher serves")
    p.add_argument("--settle", type=float, default=4.0,
                   help="Seconds to wait for the server before asserting")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    bat = os.path.abspath(args.bat)
    if not os.path.isfile(bat):
        print("FAIL: bat not found: %s" % bat)
        return 2
    port = int(re.search(r":(\d+)", args.url).group(1))

    results = []

    def check(name, ok, detail="", fail_detail=""):
        results.append(ok)
        note = detail if ok else (fail_detail or detail)
        print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                            (" -- %s" % note) if note else ""))

    kill_pids(netstat_listening(port))          # start from a clean port
    time.sleep(0.5)

    # ---- Scenario 1: fresh start ------------------------------------------------
    r1 = Runner(bat)
    r1.port = port
    r1.start()
    time.sleep(args.settle)
    code = http_code(args.url, tries=1)
    if code != 200:
        code = http_code(args.url)
    check("1 fresh start serves 200", code == 200, "GET %s -> %s" % (args.url, code))
    check("1 no flash-close", not r1.exited(),
          "exit code %s" % r1.proc.returncode if r1.exited() else "still running")
    check("1 SERVING marker", ("%s SERVING" % MARK) in r1.output())
    if r1.exited():
        print("---- captured output ----\n%s" % r1.output())

    # ---- Scenario 3 (while 1 is alive): second run reuses ----------------------
    r2 = Runner(bat)
    r2.port = port
    r2.start()
    time.sleep(args.settle)
    check("3 second run reports REUSE", ("%s REUSE" % MARK) in r2.output())
    check("3 second run survives", not r2.exited())
    check("3 original still serves 200", http_code(args.url, tries=1) == 200)
    r2.stop()
    r1.stop()
    kill_pids(netstat_listening(port))
    time.sleep(1.0)   # leave TIME_WAIT behind on purpose

    # ---- Scenario 2: immediate restart after abrupt kill ----------------------
    r3 = Runner(bat)
    r3.port = port
    r3.start()
    time.sleep(args.settle)
    out3 = r3.output()
    code3 = http_code(args.url, tries=6)
    check("2 restart after kill binds", ("%s SERVING" % MARK) in out3,
          fail_detail="no SERVING marker -> allow_reuse_address missing / TIME_WAIT bind failure")
    check("2 serves 200 after kill", code3 == 200, "GET -> %s" % code3)
    r3.stop()

    time.sleep(1.0)
    left = netstat_listening(port)
    check("cleanup: port released", not left,
          fail_detail="still LISTENING: %s" % ",".join(left))
    if left:
        kill_pids(left)

    ok = all(results)
    print("\n%s  (%d/%d checks)" % ("ALL PASS" if ok else "FAILED",
                                    sum(1 for r in results if r), len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
