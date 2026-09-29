# -*- coding: utf-8 -*-
"""红路径测试：闸门必须真的能红。

一个从没红过的闸门等于没有闸门。在 8798 起一个「照收连接、回 200 但 0 字节」的桩，
这正是 09-29 观察到的半死形态，然后调**真**的 server_precheck(8798) 看它判不判红、
现场那行填没填。
"""
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import wf16_regression as w  # noqa: E402


def stub(stop):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', 8798))
    s.listen(5)
    s.settimeout(0.4)
    while not stop.is_set():
        try:
            c, _ = s.accept()
            c.recv(4096)
            # 照收、回 200、Content-Length: 0 —— 半死的原样指纹
            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            c.close()
        except socket.timeout:
            continue
        except OSError:
            break
    s.close()


stop = threading.Event()
t = threading.Thread(target=stub, args=(stop,), daemon=True)
t.start()
time.sleep(0.8)
try:
    w.server_precheck(8798)
    print('❌ 闸门没红 —— 桩返回 0 字节它却放行了，这条判据是空的')
    sys.exit(1)
except SystemExit as e:
    msg = str(e)
    print('✅ 闸门判红，退出码 =', e.code if isinstance(e.code, int) else '(文本)')
    print(msg)
    assert '半死' in msg, '红是红了，但没说是半死'
    assert '现场:' in msg, '没带现场取证'
    assert 'threads=' in msg or 'listener=' in msg, '现场那行是空的'
    print('\n✅ 三条断言全过：判红 + 归因成"半死" + 带出现场')
finally:
    stop.set()
