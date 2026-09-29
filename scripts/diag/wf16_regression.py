# -*- coding: utf-8 -*-
"""WF-16 回归六件套串行跑完并汇总退出码。

为什么要有这个 runner（而不是人在终端一条条敲）：
1. 六件里有五件是 CDP 探针，`PORT` 与 `--user-data-dir` 目前写死且**各不相同**，
   并发跑会静默附着到同一个浏览器上，症状是"整条数据统一偏移一位"的假红灯
   （见 PROJECT_STATUS §6 第 19/20 条）。串行是唯一安全的形态。
2. 第 5 件 `hit_verify` 全库约 25 分钟，按 AGENTS.md 必须走**完全脱离宿主**的进程，
   不能挂在会话里等；这个脚本配 `run_detached.py` 起即可。
3. 退出码要逐件落进日志。⚠️ 绝不写 `... | tail -25`：`tail` 会吞掉中间明细，
   而且 `$?` 取的是 tail 的退出码——本轮之前就是这么把一个 WIRING=2 读成 EXIT=0 的。

  py -3 scripts/diag/run_detached.py --log .diag/_wf16.log -- \
      py -3 scripts/diag/wf16_regression.py
  # 只跑前四件 + 第六件（跳过 25 分钟的全库 hit_verify）：
  py -3 scripts/diag/wf16_regression.py --skip hit_verify
"""
import sys, os, subprocess, time, argparse

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# (标签, 命令, 是否可跳过) —— 顺序即 WF-16 里写死的顺序
STEPS = [
    ('1 l2d_ref_diff 抽样', ['l2d_ref_diff.py', 'antu_2', '--clips',
                             'idle,touch_head,touch_body,touch_special'], False),
    ('2 坐标系取证',       ['l2d_coord_forensics.py', 'lafeiii_3'], False),
    ('3 检查器验收',       ['l2d_inspector_verify.py', 'lafeiii_3'], False),
    ('4 交互五项',         ['interact_verify.py'], False),
    ('5 全量按部位点击',   ['hit_verify.py'], True),
    ('6 台词与全局开关',   ['talk_verify.py', '--shots'], False),
]


def server_forensics(port=8777):
    """半死判红时从进程外部量一次现场。

    为什么要这个：这个状态**罕见且复现不可靠**（09-29 那次之后原样重跑全库就没再犯），
    与其花半小时赌一次复现，不如让它下次发生时自己交代。三个量足以区分剩下的候选：
      threads/handles 暴涨   → 就是 stderr 楔死那条已证机制（见 _gallery_server.py 的 handle_error）
      进程根本不在           → 静默死掉（另一条已知形态）
      threads/handles 正常   → 两个已知机制都不是，还得另找
    """
    ps = ('$l=Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue|'
          'Select-Object -First 1 -ExpandProperty OwningProcess;'
          'if(-not $l){Write-Output "listener=none";exit}'
          '$p=Get-Process -Id $l -ErrorAction SilentlyContinue;'
          'if(-not $p){Write-Output "pid=$l gone";exit}'
          '$c=Get-CimInstance Win32_Process -Filter "ProcessId=$l";'
          '$pp=Get-Process -Id $c.ParentProcessId -ErrorAction SilentlyContinue;'
          'Write-Output ("pid={0} threads={1} handles={2} parentAlive={3} parent={4}"'
          ' -f $l,$p.Threads.Count,$p.HandleCount,[bool]$pp,$c.ParentProcessId)') % port
    # ⚠️ 这里必须用 Write-Output：PowerShell 里没有 `print` 这个命令，
    #    写成 print 会得到一句莫名其妙的「无法初始化设备 PRN」。
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                           capture_output=True, text=True, timeout=30)
        return (r.stdout or '').strip() or f'(无输出 rc={r.returncode} {(r.stderr or "")[:120]})'
    except Exception as e:
        return f'(取证本身失败：{type(e).__name__}: {e})'


def server_precheck(port=8777):
    """确认服务器能**真吐出字节**，不只是连得上。

    8777 静默死掉时，探针照样能截出"空白页"并逐条打印文件名。
    2026-09-29 全库跑就撞上过一次"半死"：连接照收、每个请求返回 0 字节，
    于是 hit_verify 把每个皮肤都判成 "GALLERY is not defined"，白跑 20 分钟。

    ⚠️ 机制只证到一半：已证死的是「stderr 是慢消费者时，每次客户端取消永久泄漏一个
       handler 线程 + 7 个句柄」（2600 次 ⇒ 线程 5→2605；已在 _gallery_server.py 堵掉），
       但 2600 次泄漏时正常请求仍能 5ms 拿到 858KB —— **没量到"整站 0 字节"的拐点**，
       所以不能声称它就是 09-29 那次的成因。判红时顺手把现场打出来，留给下次定性。
    """
    import urllib.request
    for path, min_bytes in (('gallery_v2/index.js', 200000), ('gallery_v2/index.html', 10000)):
        t0 = time.time()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/{path}', timeout=15) as r:
                got = len(r.read())
        except Exception as e:
            raise SystemExit(f'! {port} 上的画廊服务器不可达（{path}：{e}）——先起服务器再跑回归\n'
                             f'  现场: {server_forensics(port)}')
        if got < min_bytes:
            raise SystemExit(f'! 服务器半死：{path} 只返回 {got}B（应 ≥{min_bytes}B），'
                             f'耗时 {(time.time()-t0)*1000:.0f}ms。重启它再跑，别把这判成产品缺陷\n'
                             f'  现场: {server_forensics(port)}\n'
                             f'  起服务器: py -3 scripts/diag/run_detached.py --log '
                             f'.diag/gallery_server.log -- py -3 Output/gallery_v2/_gallery_server.py')
        print(f'预检: {path} {got}B / {(time.time()-t0)*1000:.0f}ms')
    print('预检通过：服务器能真吐出 index.js / index.html')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip', default='', help='逗号分隔的标签关键字，如 hit_verify')
    ap.add_argument('--full-ref', action='store_true',
                    help='第 1 件改成 --all 全量比对（只改前端视觉时不必，动过 motion 数据才要）')
    ap.add_argument('--precheck-only', action='store_true',
                    help='只跑服务器预检就退出（40 分钟的六件套之前先花 1 秒确认不白跑）')
    a = ap.parse_args()
    skips = [s.strip() for s in a.skip.split(',') if s.strip()]

    server_precheck()
    if a.precheck_only:
        return

    steps = list(STEPS)
    if a.full_ref:
        steps[0] = ('1 l2d_ref_diff 全量', ['l2d_ref_diff.py', '--all'], False)
    t0 = time.time()
    bad, done = [], []
    for label, args, skippable in steps:
        if any(s in ' '.join(args) for s in skips) and skippable:
            print(f'\n#### {label} —— 按 --skip 跳过', flush=True)
            continue
        script = os.path.join(HERE, args[0])
        print(f'\n#### {label}  {time.strftime("%H:%M:%S")}', flush=True)
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        r = subprocess.run([sys.executable, script] + args[1:], cwd=ROOT, env=env)
        print(f'#### {label} 退出码 = {r.returncode}', flush=True)
        (bad if r.returncode else done).append(f'{label}(exit {r.returncode})')

    print(f'\n===== 汇总（{time.time()-t0:.0f}s）=====')
    print('通过:', ', '.join(done) or '无')
    if bad:
        print('未通过:', ', '.join(bad))
        sys.exit(1)
    print('六件套全部通过')


if __name__ == '__main__':
    main()
