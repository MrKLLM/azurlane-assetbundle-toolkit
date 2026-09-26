#!/usr/bin/env python3
"""按 gallery_src/vendor/MANIFEST.json 补齐/校验画廊前端的第三方运行时库（4 个 JS）。

台账里每个文件都带 sha256；**只有哈希对得上才落盘**，所以配错的 URL 或换源的
另一份构建都不可能悄悄把画廊前端弄坏（这是本脚本存在的唯一理由）。

    py -3 scripts/fetch_gallery_vendor.py            # 缺件或哈希不符才拉
    py -3 scripts/fetch_gallery_vendor.py --check    # 只校验，不写盘、不出网；漂移即 exit 1
    py -3 scripts/fetch_gallery_vendor.py --manifest <路径>   # 换台账（自测用）

来源顺序：先本机已验证的副本（离线可用），再 verified=true 的 URL，最后才试未验证的。
"""
import sys, os, json, hashlib, shutil, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
argv = sys.argv[1:]
CHECK = '--check' in argv
MANIFEST = (os.path.join(ROOT, argv[argv.index('--manifest') + 1]) if '--manifest' in argv
            else os.path.join(ROOT, 'gallery_src', 'vendor', 'MANIFEST.json'))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dst_tmp):
    req = urllib.request.Request(url, headers={'User-Agent': 'gallery-vendor-provision'})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst_tmp, 'wb') as out:
        if r.status != 200:
            raise RuntimeError(f'HTTP {r.status}')
        shutil.copyfileobj(r, out)


def try_source(src, want, dst_tmp):
    """返回 (ok, 说明)。src 是 local 或 url 两种形态。"""
    if 'local' in src:
        p = os.path.join(ROOT, src['local'])
        if not os.path.isfile(p):
            return False, f"本机副本不在: {src['local']}"
        if sha256(p) != want:
            return False, f"本机副本哈希不符: {src['local']}"
        shutil.copyfile(p, dst_tmp)
        return True, f"来自 {src['local']}"
    url = src['url']
    try:
        fetch(url, dst_tmp)
    except Exception as e:
        return False, f'{url} 下载失败 {type(e).__name__}: {e}'
    got = sha256(dst_tmp)
    if got != want:
        return False, f'{url} 哈希不符（{got[:16]}… != {want[:16]}…）'
    return True, f'来自 {url}'


def main():
    entries = json.load(open(MANIFEST, encoding='utf-8'))['files']
    problems = 0
    for ent in entries:
        dst = os.path.join(ROOT, ent['path'].replace('/', os.sep))
        want = ent['sha256']
        if os.path.isfile(dst) and sha256(dst) == want:
            print(f'= {ent["path"]}  就位（{ent["bytes"]}B）')
            continue
        if CHECK:
            have = '缺件' if not os.path.isfile(dst) else f'哈希漂移 {sha256(dst)[:16]}…'
            print(f'! {ent["path"]}  {have}')
            problems += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        order = ([s for s in ent['sources'] if 'local' in s]
                 + [s for s in ent['sources'] if s.get('verified')]
                 + [s for s in ent['sources'] if 'local' not in s and not s.get('verified')])
        tmp = dst + '.tmp'
        for s in order:
            ok, msg = try_source(s, want, tmp)
            if ok:
                actual = os.path.getsize(tmp)
                if actual != ent['bytes']:
                    os.remove(tmp)
                    print(f'! {ent["path"]}  字节数 {actual} != 台账 {ent["bytes"]}，不落盘（{msg}）')
                    problems += 1
                    break
                os.replace(tmp, dst)
                print(f'→ {ent["path"]}  已补齐（{msg}）')
                break
            print(f'  × {msg}')
        else:
            problems += 1
            print(f'! {ent["path"]}  所有来源都没拿到哈希匹配的一份 —— 见台账里的 gap 字段')
        if os.path.isfile(tmp):
            os.remove(tmp)

    if CHECK:
        print(f'vendor 校验：{len(entries) - problems}/{len(entries)} 就位' if not problems
              else f'vendor 校验：{problems} 个缺件/漂移 —— 跑 py -3 scripts/fetch_gallery_vendor.py')
    sys.exit(1 if problems else 0)


main()
