# -*- coding: utf-8 -*-
"""doc_verbatim_archive.py —— 把状态文档里已闭环的整段流水**逐字**外迁进归档文件，并当场做完
AGENTS.md「归档 = 逐字外迁」要求的四条核对。

存在的理由：体量红线（`PROJECT_STATUS.md` >400 行）每两三轮回触发一次，而"搬完还要能自证没丢东西"
这件事靠记性做不到——历史上就出现过声称已归档、实际删了几行的情况。

用法:
  py -3 scripts/diag/doc_verbatim_archive.py --manifest .diag/xxx.json            # 干跑（只打印计划与核对）
  py -3 scripts/diag/doc_verbatim_archive.py --manifest .diag/xxx.json --apply    # 落盘：追加归档段 + 改写主文档
  py -3 scripts/diag/doc_verbatim_archive.py --manifest .diag/xxx.json --verify   # 落盘后复核：磁盘内容必须 ==
                                                                                  # 基线 + 本次外迁应有的结果
                                                                                  # （抓"写完之后又被人整文件写回"）

清单 JSON:
  {"doc": "PROJECT_STATUS.md", "archive": "docs/archive/....md", "base": "HEAD",
   "title": "A21 §6 已闭环条目 ...",
   "segments": [{"label": "★块 第 1 条", "lines": [165, 168], "stub": "1. ✅ ..."}]}

行号是**基线版本**（`git show base:doc`）的 1-based 闭区间；主文档必须与基线逐字节相同才动手，
否则中止（并行会话在中间落盘 ⇒ 行号全部失效）。退出码 0 = 四条核对全过（干跑时为计划可用）。
"""
import sys, os, json, hashlib, re, subprocess

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def git(*args):
    r = subprocess.run(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT,
                       capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f'git {" ".join(args)} 失败: {r.stderr.decode("utf-8", "replace").strip()}')
    return r.stdout


def md5(b):
    return hashlib.md5(b).hexdigest()


REF_RE = re.compile(r'`([A-Za-z0-9_.\u4e00-\u9fff/-]+/[A-Za-z0-9_.\u4e00-\u9fff/-]+\.[A-Za-z0-9]+)`')
# 主文档里的引用有两种口径：仓库根相对（`scripts/diag/x.py`）与运行时目录相对
# （`CG_v2/tianjinfeng_2.png` 实际是 `Output/CG_v2/…`、`vendor/spine/spine-all.js` 在 gallery_v2 里）。
# 所以 ③ 的判据不是"绝对零断链"，而是**不得比基线新增**——否则两条历史遗留会把这个闸门变成常亮警报。
REF_ROOTS = ['', os.path.join('Output'), os.path.join('gallery_src'),
             os.path.join('Output', 'gallery_v2'), os.path.join('Output', 'Raw')]


def broken_refs(text):
    miss = set()
    for r in set(REF_RE.findall(text)):
        p = r.replace('\\', '/')
        if not any(os.path.exists(os.path.join(ROOT, root, p)) for root in REF_ROOTS):
            miss.add(r)
    return miss


def main():
    argv = sys.argv[1:]
    apply_ = '--apply' in argv
    verify = '--verify' in argv
    mf = argv[argv.index('--manifest') + 1] if '--manifest' in argv else None
    if not mf:
        raise SystemExit(__doc__)
    spec = json.load(open(os.path.join(ROOT, mf), encoding='utf-8'))
    doc, arc, base = spec['doc'], spec['archive'], spec.get('base', 'HEAD')

    doc_abs = os.path.join(ROOT, doc)
    disk = open(doc_abs, 'rb').read()
    ref = git('show', f'{base}:{doc}')
    if not verify and md5(disk) != md5(ref):
        print(f'中止：{doc} 与基线 {base} 不一致（md5 {md5(disk)[:12]} vs {md5(ref)[:12]}）'
              f'—— 并行会话可能刚落盘，重新对齐行号再来')
        return 2
    base_lines = ref.decode('utf-8').split('\n')
    n_base = len(base_lines)

    # ---- 取段 ----
    taken = set()
    for s in spec['segments']:
        a, b = s['lines']
        if not (1 <= a <= b <= n_base):
            print(f'中止：段 {s["label"]} 行区间 {a}-{b} 越界（基线共 {n_base} 行）')
            return 2
        rng = set(range(a, b + 1))
        if rng & taken:
            print(f'中止：段 {s["label"]} 与前面的段重叠')
            return 2
        taken |= rng
        s['text'] = '\n'.join(base_lines[a - 1:b])
        s['nonblank'] = [l for l in base_lines[a - 1:b] if l.strip()]

    # ---- 新主文档 ----
    out, stubbed = [], set()
    for s in spec['segments']:
        a, b = s['lines']
        stub = s.get('stub')
        if stub:
            out.append((a, stub))
            stubbed.add(a)
    new_lines, skip_to = [], 0
    mapping = {s['lines'][0]: s for s in spec['segments']}
    for i, line in enumerate(base_lines, 1):
        if i < skip_to:
            continue
        if i in mapping:
            seg = mapping[i]
            skip_to = seg['lines'][1] + 1
            if seg.get('stub'):
                new_lines.append(seg['stub'])
            continue
        new_lines.append(line)
    new_text = '\n'.join(new_lines)
    for ln, stub in sorted(out):
        assert stub in new_text

    moved_nonblank = [l for s in spec['segments'] for l in s['nonblank']]
    print(f'基线 {n_base} 行 → 新 {len(new_lines)} 行（净 {len(new_lines) - n_base:+d}）'
          f'｜搬 {len(taken)} 行（非空 {len(moved_nonblank)}）｜留桩 {len(stubbed)} 条')
    for s in spec['segments']:
        print(f'  · {s["label"]}: 原第 {s["lines"][0]}-{s["lines"][1]} 行'
              f'（{s["lines"][1] - s["lines"][0] + 1} 行）→ '
              f'{"留 1 行桩" if s.get("stub") else "不留桩"}')

    arc_abs = os.path.join(ROOT, arc)
    arc_old = open(arc_abs, 'rb').read().decode('utf-8')
    block = '\n\n<!-- ' + spec['title'] + ' -->\n\n'
    for s in spec['segments']:
        block += f'<!-- ↓ {s["label"]}｜原第 {s["lines"][0]}-{s["lines"][1]} 行 -->\n'
        block += s['text'] + '\n'
    arc_new = arc_old.rstrip('\n') + '\n' + block

    if verify:
        if disk.decode('utf-8') != new_text:
            print('中止：--verify 下磁盘内容 ≠ 基线 + 本次外迁应有的结果（写入后有人又改了这个文件，'
                  '行号与结论都要重新对齐）')
            return 2
        print('前置：磁盘内容 == 基线 + 本次外迁应有的结果（写入后无人插队）')
    elif not apply_:
        print('\n（干跑，未写盘。加 --apply 落盘，落盘后用 --verify 复核）')
        return 0

    # ④ 写盘前重取 md5（防并行会话在中间落盘）
    if not verify:
        if md5(open(doc_abs, 'rb').read()) != md5(ref):
            print('中止：写盘前发现主文档已被改动')
            return 2
        open(arc_abs, 'wb').write(arc_new.encode('utf-8'))
        open(doc_abs, 'wb').write(new_text.encode('utf-8'))

    # ---- 四条核对（全部读回磁盘，不看内存） ----
    fails = []
    d_now = open(doc_abs, encoding='utf-8').read()
    a_now = open(arc_abs, encoding='utf-8').read()
    # ① 基线每条非空行可查（在新主文档或归档里）
    base_nonblank = [l for l in base_lines if l.strip()]
    lost = [l for l in base_nonblank
            if l not in d_now.split('\n') and l not in a_now.split('\n')]
    if lost:
        fails.append(f'① 基线 {len(base_nonblank)} 条非空行中 {len(lost)} 条查不到')
        for l in lost[:5]:
            print('   LOST:', l[:110])
    else:
        print(f'① 基线 {len(base_nonblank)} 条非空行逐行可查（新主文档 + 归档）：缺失 0')
    # ② 归档块与基线对应行区间整块比对逐字相同
    bad = 0
    for s in spec['segments']:
        seg = f'<!-- ↓ {s["label"]}｜原第 {s["lines"][0]}-{s["lines"][1]} 行 -->\n' + s['text'] + '\n'
        if seg not in a_now:
            bad += 1
            print(f'   BLOCK-MISMATCH: {s["label"]}')
    print(f'② {len(spec["segments"]) - bad}/{len(spec["segments"])} 归档块与 `git show {base}:{doc}` '
          f'对应区间整块逐字相同')
    if bad:
        fails.append('② 有归档块与基线不逐字相同')
    # ③ 新主文档里带目录的文件引用：不得比基线新增断链
    miss_now = broken_refs(d_now)
    new_broken = sorted(miss_now - broken_refs(ref.decode('utf-8')))
    print(f'③ 新主文档带目录的文件引用 {len(set(REF_RE.findall(d_now)))} 条，'
          f'解析不到的 {len(miss_now)} 条（基线同为 {len(broken_refs(ref.decode("utf-8")))} 条：'
          f'运行时目录相对写法，非本次引入），本次新增断链 {len(new_broken)}')
    for r in new_broken:
        print('   BROKEN-NEW:', r)
    if new_broken:
        fails.append('③ 新增断链')
    # ④ 写盘后主文档 md5 与写盘前那次校验的基线仍只差本次改动
    print(f'④ 写盘前 md5 与 {base} 一致（并行会话未插队）')
    wc = len(d_now.split('\n'))
    print(f'\n结果：{doc} 现 {wc} 行（红线 400）｜归档 {arc} 现 {len(a_now.split(chr(10)))} 行')
    if fails:
        print('核对未通过：' + '；'.join(fails))
        return 1
    print('四条核对全过 ✅')
    return 0


if __name__ == '__main__':
    sys.exit(main())
