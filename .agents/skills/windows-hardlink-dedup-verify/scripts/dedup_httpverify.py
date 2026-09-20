# -*- coding: utf-8 -*-
"""硬链接去重 步骤3/4：HTTP 三重校验（证明画廊/静态站能正常打开去重文件）。

进程内起 ThreadingHTTPServer 根于产物目录，GET _dedup_applied.txt 里每个受影响路径，
核对 HTTP 200 + Content-Length + 下载字节 sha256 三重一致。
这是「按文件名引用的消费方零破坏」的直接证据。

用法: python dedup_httpverify.py
配置(同上): DEDUP_ROOT / DEDUP_DIAG。
"""
import os, io, sys, functools, hashlib, threading, urllib.request, urllib.parse
import http.server, socketserver

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DIAG = os.environ.get('DEDUP_DIAG') or os.path.join(ROOT, '.diag')
OUT = os.environ.get('DEDUP_ROOT') or 'Output'
OUT = OUT if os.path.isabs(OUT) else os.path.join(ROOT, OUT)

paths = [l.strip() for l in io.open(os.path.join(DIAG, '_dedup_applied.txt'), encoding='utf-8') if l.strip()]
if not paths:
    print('没有已应用路径 (_dedup_applied.txt 为空)')
    sys.exit(0)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# 起一个只读 http.server 根于 OUT
class Quiet(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    def handle_error(self, *a): pass

class QH(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k): pass  # 静音逐条 GET 日志

def make_handler(*a, **k):
    return QH(*a, directory=OUT, **k)

srv = Quiet(('127.0.0.1', 0), make_handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

ok = 0
fails = []
try:
    for rel in paths:
        url = 'http://127.0.0.1:%d/%s' % (port, urllib.parse.quote(rel.replace('\\', '/')))
        local = os.path.join(OUT, rel)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                status = r.status
                clen = r.headers.get('Content-Length')
                body = r.read()
            want_len = str(os.path.getsize(local))
            if status != 200:
                fails.append(f'{rel}: HTTP {status}'); continue
            if clen is not None and clen != want_len:
                fails.append(f'{rel}: 长度 {clen}!={want_len}'); continue
            if len(body) != os.path.getsize(local):
                fails.append(f'{rel}: 下载字节 {len(body)}!={os.path.getsize(local)}'); continue
            if sha_bytes(body) != sha_file(local):
                fails.append(f'{rel}: sha256 不一致'); continue
            ok += 1
        except Exception as e:
            fails.append(f'{rel}: {type(e).__name__} {e}')
finally:
    srv.shutdown()

print(f'HTTP 校验: {ok}/{len(paths)} 通过   失败 {len(fails)}')
for m in fails[:40]:
    print('  ! ' + m)
sys.exit(0 if not fails else 1)
