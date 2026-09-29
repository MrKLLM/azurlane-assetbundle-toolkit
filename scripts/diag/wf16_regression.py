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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip', default='', help='逗号分隔的标签关键字，如 hit_verify')
    ap.add_argument('--full-ref', action='store_true',
                    help='第 1 件改成 --all 全量比对（只改前端视觉时不必，动过 motion 数据才要）')
    a = ap.parse_args()
    skips = [s.strip() for s in a.skip.split(',') if s.strip()]

    # 先确认服务器活着：8777 静默死掉时探针照样能截出"空白页"并逐条打印文件名
    import urllib.request
    try:
        urllib.request.urlopen('http://127.0.0.1:8777/gallery_v2/index.html', timeout=5)
    except Exception as e:
        raise SystemExit(f'! 8777 上的画廊服务器不可达（{e}）——先起服务器再跑回归')

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
