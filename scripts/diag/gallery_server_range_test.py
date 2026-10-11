# -*- coding: utf-8 -*-
"""`_gallery_server.py` 的 Range 支持与既有端点回归（原地起一份服务器，**不占 8777**）。

为什么要这个测试：2026-10-06 给 BGM 页补 Range 支持时，8777 上那台服务器
**可能正被另一个会话的探针用着**，不能为了验证去重启它 ⇒ 把服务器对象抽成
`make_server(port, root)`，测试自己挑一个空闲端口起一份，跑完 shutdown。
⚠️ 读路径原地测；`POST /save_cg` 会往正式目录 `Output/CG_v2/` 落文件，
   那是别的会话会扫的生产区 ⇒ 只回归它的分支没被改坏（无 name ⇒ 400），不在 CG_v2 里造临时文件。
   `POST /l2d_freeze` 的写路径则把 `GS.FREEZE_DIR` 换成本测试自己的临时目录再打，
   顺带验「tag 里带路径也逃不出该目录」——命名权在服务端，这条必须有判据。

用法: py -3 scripts/diag/gallery_server_range_test.py
退出码: 0 = 全过；1 = 有判据未过。
"""
import http.client
import os
import socket
import sys
import threading
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import _gallery_server as GS   # noqa: E402

FAIL = []


def say(cond, msg):
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAIL.append(msg)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def req(port, path, headers=None, method='GET', data=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
    c.request(method, path, body=data, headers=headers or {})
    r = c.getresponse()
    body = r.read()
    hd = {k.lower(): v for k, v in r.getheaders()}
    c.close()
    return r.status, hd, body


def main():
    out = os.path.join(ROOT, 'Output')
    port = free_port()
    httpd = GS.make_server(port=port, root=out)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        rel = 'gallery_v2/bgm.html'
        fp = os.path.join(out, 'gallery_v2', 'bgm.html')
        size = os.path.getsize(fp)
        raw = open(fp, 'rb').read()

        st, hd, body = req(port, '/' + rel)
        say(st == 200 and len(body) == size, f'全量 GET：{st} / {len(body)} 字节（文件 {size}）')

        st, hd, body = req(port, '/' + rel, {'Range': 'bytes=0-99'})
        say(st == 206 and body == raw[:100] and hd.get('content-range') == f'bytes 0-99/{size}',
            f'首 100 字节：{st} / Content-Range={hd.get("content-range")} / 内容逐字节相同={body == raw[:100]}')

        st, hd, body = req(port, '/' + rel, {'Range': f'bytes={size // 2}-{size // 2 + 499}'})
        say(st == 206 and body == raw[size // 2:size // 2 + 500],
            f'中段 500 字节：{st} / 长度 {len(body)}')

        st, hd, body = req(port, '/' + rel, {'Range': 'bytes=-50'})
        say(st == 206 and body == raw[-50:], f'后缀区间 bytes=-50：{st} / 长度 {len(body)}（应为 50）')

        st, hd, body = req(port, '/' + rel, {'Range': f'bytes={size - 10}-'})
        say(st == 206 and body == raw[-10:], f'开区间到文件末：{st} / 长度 {len(body)}')

        st, hd, body = req(port, '/' + rel, {'Range': f'bytes={size + 100}-'})
        say(st == 416, f'越界区间应 416，实得 {st}')

        st, hd, body = req(port, '/' + rel, {'Range': 'bytes=abc-'})
        say(st == 200 and len(body) == size, f'畸形 Range ⇒ 回落全量 200（不是 500），实得 {st}')

        # 音频本体：Chrome 先要一个探测性的尾区间，再要中段。
        # ⚠️ 目录名跟着音频归并动过（BGM_ogg/BGM_flac → 单一 Audio/BGM），判据按扩展名取，
        #    缺哪种格式就跳过哪种，别让一次目录改名把整台回归变成假失败。
        bdir = os.path.join(out, 'Audio', 'BGM')
        cands = sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []
        say(bool(cands), f'Audio/BGM 可作 Range 判据的文件数：{len(cands)}')
        for ext in ('.ogg', '.flac'):
            af = next((x for x in cands if x.lower().endswith(ext)), None)
            if not af:
                continue
            afs = os.path.join(bdir, af)
            araw = open(afs, 'rb').read()
            asz = len(araw)
            apath = 'Audio/BGM/' + af
            st, hd, body = req(port, '/' + apath, {'Range': 'bytes=0-1'})
            say(st == 206 and body == araw[:2] and hd.get('content-type', '').startswith('audio'),
                f'{ext} 前 2 字节（magic）：{st} / Content-Type={hd.get("content-type")} / '
                f'开头 {body[:2]!r} == 文件头 {araw[:2]!r}')
            st, hd, body = req(port, '/' + apath, {'Range': f'bytes={asz - 3}-'})
            say(st == 206 and body == araw[-3:], f'{ext} 尾 3 字节：{st} / 长度 {len(body)}')
            # FLAC 那一档的专属坑：Python mimetypes 给 `.flac` 的是遗留的 `audio/x-flac`，
            # 而 Chrome `canPlayType('audio/x-flac')` 返回空串 ⇒ 类型必须钉成 `audio/flac`。
            if ext == '.flac':
                st, hd, body = req(port, '/' + apath)
                say(st == 200 and hd.get('content-type') == 'audio/flac',
                    f'FLAC 的 Content-Type = {hd.get("content-type")!r}（必须是 audio/flac）')
                st, hd, body = req(port, '/' + apath, {'Range': 'bytes=0-3'})
                say(st == 206 and body == araw[:4],
                    f'FLAC 也走 Range：{st} / 前 4 字节 {body!r} == 文件头 {araw[:4]!r}')

        st, hd, body = req(port, '/cg_exists?name=2b_2')
        say(st == 200 and body in (b'0', b'1'), f'既有端点 /cg_exists 仍工作：{st} / {body!r}')
        st, hd, body = req(port, '/cg_exists?name=../etc')
        say(st == 200 and body == b'0', f'非法名被 _NAME_RE 挡掉（不越界读盘）：{body!r}')

        # ---------- POST /l2d_freeze（Live2D 暂停帧存档）：写路径全程落在临时目录里 ----------
        # 存档目录按「这台服务器正在服务的 root」算（Handler._freeze_dir），所以测试把服务根
        # 指到一个临时树即可，不碰真的 .diag/l2d_freeze/。
        tmp = os.path.join(ROOT, '.diag', '_server_test_freeze')
        orig_fd = GS.Handler._freeze_dir
        GS.Handler._freeze_dir = lambda self: tmp
        for f in os.listdir(tmp) if os.path.isdir(tmp) else []:
            os.remove(os.path.join(tmp, f))
        payload = '{"tag":"gezi_2-home","params":{"ParamEyeLOpen":1},"t":11.03}'
        st, hd, body = req(port, '/l2d_freeze', {'Content-Type': 'application/json'}, 'POST',
                           payload.encode('utf-8'))
        fn = body.decode('utf-8')
        say(st == 200 and fn.endswith('-gezi_2-home.json'),
            f'暂停存档应答文件名：{st} / {fn}')
        landed = os.path.join(tmp, fn)
        say(os.path.isfile(landed) and open(landed, 'rb').read().decode('utf-8') == payload,
            f'内容逐字节落盘：{os.path.getsize(landed) if os.path.isfile(landed) else "没有这个文件"} 字节')

        # 命名权在服务端：请求带路径也逃不出 FREEZE_DIR
        evil = '{"tag":"../../windows/evil.exe"}'
        st, hd, body = req(port, '/l2d_freeze', {}, 'POST', evil.encode('utf-8'))
        fn2 = body.decode('utf-8')
        say(st == 200 and not os.path.isdir(os.path.join(ROOT, 'windows'))
            and os.path.abspath(os.path.join(tmp, fn2)).startswith(os.path.abspath(tmp)),
            f'恶意 tag 被清洗后仍在目录内：{fn2}')
        say(not os.path.exists(os.path.join(ROOT, os.pardir, 'windows')) and
            not os.path.exists(os.path.join(ROOT, 'Output', 'windows')), '上层目录没被写出新文件夹')

        st, hd, body = req(port, '/l2d_freeze', {'Content-Type': 'application/json'}, 'POST',
                           payload.encode('utf-8'))
        fn3 = body.decode('utf-8')
        say(st == 200 and fn3 != fn and os.path.isfile(os.path.join(tmp, fn))
            and os.path.isfile(os.path.join(tmp, fn3)),
            f'同一秒内重复暂停不覆盖前一份：{fn} / {fn3}')

        st, hd, body = req(port, '/l2d_freeze', {}, 'POST', b'{ not json')
        say(st == 400, f'坏 JSON 应 400，实得 {st}（不落半个文件：{len(os.listdir(tmp))} 份）')
        st, hd, body = req(port, '/l2d_freeze', {}, 'POST', b'')
        say(st == 400, f'空 body 应 400，实得 {st}')

        st, hd, body = req(port, '/save_cg', {'Content-Type': 'application/json'}, 'POST', b'{}')
        say(st == 400, f'既有 POST /save_cg 的分支没被改坏（无 name ⇒ 400，实得 {st}）')

        st, hd, body = req(port, '/gallery_v2/index.json')
        say(st == 200 and len(body) > 20000, f'大文件全量读仍正常：{st} / {len(body):,} 字节')
        print()
        if FAIL:
            print(f'[FAIL] {len(FAIL)} 条未过')
            return 1
        print('[PASS] Range 支持与既有端点全部判据通过')
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == '__main__':
    sys.exit(main())
