# -*- coding: utf-8 -*-
"""HTTP 校验：起 http.server 根于 Output/，GET 每个受影响路径，验 200+长度+sha256。"""
import os, io, sys, hashlib, threading, urllib.request, functools, http.server, socketserver
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'Output')
paths = [l.strip() for l in io.open(os.path.join(ROOT,'.diag','_dedup_applied.txt'),encoding='utf-8') if l.strip()]

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

# 端口 0 让系统分配
Handler=functools.partial(http.server.SimpleHTTPRequestHandler, directory=OUT)
class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address=True; daemon_threads=True
srv=TS(('127.0.0.1',0), Handler)
port=srv.server_address[1]
threading.Thread(target=srv.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{port}/'
ok=0; bad=[]
for rel in paths:
    url=base+rel.replace(os.sep,'/')
    disk=os.path.join(OUT,rel)
    try:
        with urllib.request.urlopen(url,timeout=15) as r:
            code=r.getcode(); body=r.read()
        want=os.path.getsize(disk); ws=sha(disk)
        if code==200 and len(body)==want and hashlib.sha256(body).hexdigest()==ws:
            ok+=1
        else:
            bad.append((rel,code,len(body),want))
    except Exception as ex:
        bad.append((rel,'ERR',str(ex)))
srv.shutdown()
print(f'HTTP 校验 {ok}/{len(paths)} 通过 (port {port})')
for b in bad[:20]: print('  BAD',b)
