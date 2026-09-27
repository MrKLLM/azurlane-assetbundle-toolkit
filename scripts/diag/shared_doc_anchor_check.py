# -*- coding: utf-8 -*-
"""shared_doc_anchor_check.py —— 只读核对：本轮往共享长文档 / 前端正本里落的原话，还在不在盘上、
是不是由我以为的那笔提交带进去的。

存在的理由（2026-09-27 实测两次事故，判别与缓解见技能 shared-worktree-takeover-commit 第 3c 步）：
`PROJECT_STATUS.md` 这类长文档被多个会话同时写，而"整文件写回"这一手法对**别人刚插入的内容是隐形的**——
对方读的是你改之前的版本，写回来是一份不含你那段的完整文件，git 不报任何冲突。两种结局都要抓：
  · DROPPED  原话消失        —— 内容真丢了，必须查是谁删的、要不要重投
  · RIDER    原话在，但引入它的是别人的提交 —— 内容没丢，只是归属对不上（"我提交过了"是假证据）
⚠️ 只看 `git status` 干净、`git diff` 为空，**两种都发现不了**；本轮就是查过 status 仍被吞了一条。

用法:
  py -3 scripts/diag/shared_doc_anchor_check.py                 # 全量核对（台账 = 本目录 shared_doc_anchors.json）
  py -3 scripts/diag/shared_doc_anchor_check.py --strict        # 把 RIDER 也算失败
  py -3 scripts/diag/shared_doc_anchor_check.py --add <文件> <原话片段> [提交号] [备注]
        # 本轮落了新内容就灌一条；提交号留空/写 HEAD 则取当前 HEAD 短号
        # （某条想**只查存在、不校验归属**——例如与登记同笔提交的新内容——把台账里该条 commit 改成 ""）

退出码：0 = 全 OK（--strict 下要求无 RIDER）；1 = 有 DROPPED/MISSING（或 --strict 下有 RIDER）；2 = 台账或 git 不可用。
台账是**可腐烂的**：条目对应的内容若被有意改写或删除，请把台账一起改掉，别让它变成常亮的假警报。
"""
import sys, os, json, subprocess

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, 'scripts', 'diag', 'shared_doc_anchors.json')


def git(*args):
    r = subprocess.run(['git', '-c', 'core.quotepath=false', *args],
                       cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    return r.stdout.strip(), r.returncode


def head_short():
    out, rc = git('rev-parse', '--short', 'HEAD')
    return out if rc == 0 else ''


def introduced_by(needle, rel):
    """把锚点定位到**具体行**再 blame —— 不能用 `git log -S`：它报的是"最后一次改变该串出现
    次数的提交"，别人只要改写文档头部（同一串出现 2 次、被删掉 1 次）就会把幸存行的归属错算到
    他头上（实测误报过一次）。blame 给的是"当前这些字节是谁放的"，正是归属要问的东西。
    同一串可能在多处出现（如标题行 + 正文行），**任一处仍归记录方即算 OK**——只看第一处会被
    别人改写过的标题行掩盖掉正文里那句原话。"""
    p = os.path.join(ROOT, rel)
    try:
        lines = open(p, encoding='utf-8', errors='replace').read().split('\n')
    except OSError:
        return ''
    hits = [i for i, line in enumerate(lines, 1) if needle in line][:20]
    owners = []
    for n in hits:
        out, rc = git('blame', '-L', f'{n},{n}', '--porcelain', '--', rel)
        if rc != 0 or not out:
            continue
        sha = out.split('\n', 1)[0].split()[0]
        out2, rc2 = git('rev-parse', '--short', sha)
        owners.append(out2 if rc2 == 0 else sha[:7])
    return ','.join(dict.fromkeys(owners))          # 去重保序，供上层比对与展示


def check(strict=False):
    try:
        led = json.load(open(LEDGER, encoding='utf-8'))
    except OSError as e:
        print(f'[ERROR] 读不到台账 {LEDGER}: {e}')
        return 2
    anchors = led.get('anchors') or []
    if not anchors:
        print('[ERROR] 台账里没有条目')
        return 2
    bad = warn = 0
    for a in anchors:
        rel, needle, want = a.get('file', ''), a.get('needle', ''), a.get('commit', '')
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            print(f'  MISSING  {rel} 文件不存在（锚点：{needle[:28]}）')
            bad += 1
            continue
        text = open(p, encoding='utf-8', errors='replace').read()
        if needle not in text:
            print(f'  DROPPED  {rel}  已找不到「{needle[:34]}」 —— 大概率被别人的整文件写回吞了；'
                  f'查：git log -S"{needle[:20]}" --oneline -- {rel}')
            bad += 1
            continue
        got = introduced_by(needle, rel)
        if want and got and want not in got.split(','):
            warn += 1
            print(f'  RIDER    {rel}  「{needle[:28]}」在盘上，但每一处都是别人放的（{got}，记录的是 {want}）'
                  f'{"—— 内容没丢，归属对不上" if not strict else ""}')
        else:
            print(f'  OK       {rel}  「{needle[:28]}」')
    verdict = '全绿' if bad == 0 and (warn == 0 or not strict) else '有问题'
    print(f'\n核对 {len(anchors)} 条锚点 — OK/搭车 {len(anchors) - bad} 条，其中被他人提交搭车 {warn} 条，'
          f'丢失/缺文件 {bad} 条 ⇒ {verdict}')
    if bad == 0 and warn and not strict:
        print('（RIDER 不算失败：内容在盘上，只是提交归属与记录不符。要连归属一起管就加 --strict）')
    return 1 if (bad or (strict and warn)) else 0


def add(rel, needle, commit, note):
    try:
        led = json.load(open(LEDGER, encoding='utf-8'))
    except OSError as e:
        print(f'[ERROR] 读不到台账: {e}')
        return 2
    anchors = led.setdefault('anchors', [])
    if any(a.get('file') == rel and a.get('needle') == needle for a in anchors):
        print(f'台账里已有这条（{rel} / {needle}），不重复加')
        return 0
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        print(f'[ERROR] {rel} 不存在，拒绝登记')
        return 2
    if needle not in open(p, encoding='utf-8', errors='replace').read():
        print(f'[ERROR] 「{needle}」当前不在 {rel} 里，拒绝登记（先落内容再记锚点）')
        return 2
    if not commit or commit.upper() == 'HEAD':
        commit = head_short()
    anchors.append({'file': rel, 'needle': needle, 'commit': commit, 'note': note or ''})
    with open(LEDGER, 'w', encoding='utf-8') as f:
        json.dump(led, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'已登记 — {rel} :: {needle[:30]} @ {commit}')
    return 0


def main():
    args = sys.argv[1:]
    if '--add' in args:
        rest = args[args.index('--add') + 1:]
        rest = [a for a in rest if a != '--strict']
        if len(rest) < 2:
            print(__doc__)
            return 2
        return add(rest[0], rest[1], rest[2] if len(rest) > 2 else '', rest[3] if len(rest) > 3 else '')
    return check(strict='--strict' in args)


if __name__ == '__main__':
    sys.exit(main())
