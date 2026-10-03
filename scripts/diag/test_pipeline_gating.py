# -*- coding: utf-8 -*-
"""签字门与增量范围的**闸门自测**：不跑任何真产物，只验证"未签字/缺范围时到底有没有去写盘"。

为什么单独要有这个：这三条都是"看起来在工作、其实形同虚设"的那类缺陷 ——
`st_audio`/`st_cg` 收了 `approved` 参数却从不检查它，`affected.txt` 从来没人生成
导致"增量"静默等于全量。光看代码和界面都发现不了，只有把**是否调用写产物子进程**
当成可观测状态量出来才算守住。

    py -3 scripts/diag/test_pipeline_gating.py        # 退出码即结论

判据全部落在"产品行动那一刻"（有没有 spawn 那个会覆写 Output/ 的子进程），
不落在文案上 —— 文案会改，行动不会说谎。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import update_pipeline as up  # noqa: E402

FAIL = []


def ck(name, cond, got=''):
    print(f'  {"PASS" if cond else "FAIL"}  {name}' + (f'  ← {got}' if got and not cond else ''))
    if not cond:
        FAIL.append(name)


class Rec:
    """替掉 run()：只记录被调用了什么，绝不真跑。`rc_of` 让某条命令返回指定退出码，
    用来测"某个只读判据红了，阶段结论会不会跟着红"——不设这个参数时它恒 0，等于
    所有只读半边都默认通过，那正是上一版漏掉的形状。"""

    def __init__(self, out='', rc_of=None):
        self.calls = []
        self.out = out
        self.rc_of = rc_of or {}

    def __call__(self, argv, **kw):
        line = ' '.join(str(a) for a in argv)
        self.calls.append([str(a) for a in argv])
        for key, rc in self.rc_of.items():
            if key in line:
                return rc, self.out, ''
        return 0, self.out, ''

    def hit(self, *keys):
        return [c for c in self.calls if any(k in ' '.join(c) for k in keys)]


def tmp_work(f):
    """把 WORK 挪到临时目录：这些测试会写范围清单，绝不许碰真的 .diag/pipeline/。"""
    d = tempfile.mkdtemp(prefix='gating_')
    old = up.WORK
    up.WORK = d
    try:
        return f(d)
    finally:
        up.WORK = old
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------ 1 范围映射
def t_stems():
    print('\n[1] 范围清单 → 各阶段 stem 的映射')
    # ⚠️ 用**盘上真实存在**的包名：主皮肤与否最终由磁盘裁判（见 stems_for 的注释），
    # 编出来的名字会被正确地滤掉，那样测试就只是在测自己的假设。
    paths = ['AssetBundles/painting/2b', 'AssetBundles/painting/2b_tex',
             'AssetBundles/painting/a2_n_bj1_tex',          # 部件包：painting/ 下没有 a2_n_bj1 主包
             'AssetBundles/painting/zzz_not_a_skin_tex',    # 根本不存在
             'AssetBundles/painting/mat_ship_x', 'AssetBundles/painting/x_dark_shadow',
             'AssetBundles/spinepainting/2b_2', 'AssetBundles/spinepainting/adaerbote_4_res',
             'AssetBundles/live2d/abeikelongbi_3', 'AssetBundles/ui/icon_a',
             'AssetBundles/cue/bgm-airraidalarm.b', 'AssetBundles/painting/sub/dir/deep']
    p = up.stems_for('painting', paths, main_only=True)
    ck('painting：_tex 归并到主皮肤', p == ['2b'], str(p))
    ck('painting：带编号的部件包（_bj1）不算一张立绘', 'a2_n_bj1' not in p, str(p))
    ck('painting：磁盘上没有主包的名字一律不进来（防渲染报 ✗ 判红停线）',
       'zzz_not_a_skin' not in p, str(p))
    ck('painting：mat_*/_dark_shadow/跨目录都被滤掉',
       all('mat' not in x and 'shadow' not in x and 'deep' not in x for x in p), str(p))
    ck('spine：只吃 spinepainting/ 且 _res 归并',
       up.stems_for('spinepainting', paths) == ['2b_2', 'adaerbote_4'],
       str(up.stems_for('spinepainting', paths)))
    ck('live2d：只吃 live2d/', up.stems_for('live2d', paths) == ['abeikelongbi_3'],
       str(up.stems_for('live2d', paths)))
    ck('cue 的包不会混进立绘清单，ui 的包谁都不混',
       up.stems_for('cue', paths) == ['bgm-airraidalarm.b'] and not up.stems_for('ui', paths))



# ------------------------------------------------------------------ 2 缺清单不许兜底成全量
def t_no_scope():
    print('\n[2] 没有范围清单时：判红停下，绝不按全量兜底')
    def body(d):
        fp_real = up.fingerprint
        up.fingerprint = lambda: 'bundles=1 deps=test'
        try:
            for key, fn in (('paintings', lambda: up.st_paintings(False, set())),
                            ('spine', lambda: up.st_spine(False, set())),
                            ('live2d', lambda: up.st_live2d(False, set())),
                            ('cg', lambda: up.st_cg(False, {'cg'}))):
                r = Rec()
                old, up.run = up.run, r
                try:
                    ok = fn()
                finally:
                    up.run = old
                v = up.RESULTS[key]
                ck(f'{key}: 无清单 → 判红', ok is False and v['ok'] is False, str(v))
                ck(f'{key}: 无清单 → 说了"拒绝按全量兜底"', '拒绝按全量兜底' in v['detail'], v['detail'])
                ck(f'{key}: 无清单 → 一个子进程都没起', r.calls == [], str(r.calls))
            mode, payload = up.scope_state(False)
            ck('scope_state 报 missing 而不是静默 None', mode == 'missing', f'{mode} {payload}')
            ck('affected_stems（面板读的接口）在无清单时返回 None', up.affected_stems(False) is None)
            up.fingerprint = fp_real
        finally:
            up.fingerprint = fp_real
    tmp_work(body)


def t_stale_scope():
    print('\n[3] 清单属于另一批输入：判 stale，同样不许兜底')
    def body(d):
        open(os.path.join(d, 'affected.txt'), 'w', encoding='utf-8').write(
            'AssetBundles/painting/haitian_3\n')
        import json
        json.dump({'fingerprint': 'bundles=1 deps=OTHER', 'at': 'x'},
                  open(os.path.join(d, 'affected.meta'), 'w', encoding='utf-8'))
        mode, payload = up.scope_state(False)
        ck('判成 stale 并给出两边指纹', mode == 'stale' and '≠' in payload, f'{mode} {payload}')
    tmp_work(body)


# ------------------------------------------------------------------ 4 签字门
def t_gates():
    print('\n[4] live 档的签字门：未签字不得起写产物的子进程')
    def body(d):
        # 造一份"当前有效"的范围清单，让 stale/missing 那条路径不干扰本项
        real = up.fingerprint
        up.fingerprint = lambda: 'bundles=1 deps=test'
        try:
            up.write_scope(['AssetBundles/cue/bgm-airraidalarm.b',
                            'AssetBundles/spinepainting/2b_2'], 1, 1)
            ck('write_scope 两份文件一起落（上一版只写了 meta）',
               os.path.isfile(os.path.join(d, 'affected.txt'))
               and os.path.isfile(os.path.join(d, 'affected.meta')))

            for key, fn, writers, label in (
                    ('audio', lambda: up.st_audio(set()), ['extract_cv_voice'], '音频解码'),
                    ('cg', lambda: up.st_cg(False, set()), ['run_cg_export'], 'CG 导出')):
                r = Rec()
                old, up.run = up.run, r
                try:
                    ok = fn()
                finally:
                    up.run = old
                v = up.RESULTS[key]
                ck(f'{key}: 未签字 → 没起{label}子进程', not r.hit(*writers), str(r.calls))
                ck(f'{key}: 未签字 → 结论里保留"未签字"给前端识别', '未签字' in v['detail'], v['detail'])
                ck(f'{key}: 未签字 → 判绿（它做完了该做的只读半边）', ok is True, str(v))
                ck(f'{key}: 未签字 → 明说正式区没动', '未动' in v['detail'] or '一张都没重导' in v['detail'],
                   v['detail'])

            # 反向对照：签了字就必须真的去写，否则门是"焊死"的、也不对
            for key, fn, writers in (('audio', lambda: up.st_audio({'audio'}), ['extract_cv_voice']),
                                     ('cg', lambda: up.st_cg(True, {'cg'}), ['run_cg_export'])):
                r = Rec('完成3 跳过0 失败0')
                old, up.run = up.run, r
                try:
                    fn()
                finally:
                    up.run = old
                ck(f'{key}: 签字后 → 确实起了 {writers[0]}', len(r.hit(*writers)) == 1, str(r.calls))
            # cg 的增量范围要按 spinepainting 过滤后传给 --only
            r = Rec('完成1 跳过0 失败0')
            old, up.run = up.run, r
            try:
                up.st_cg(False, {'cg'})
            finally:
                up.run = old
            only = [c for c in r.calls if 'run_cg_export' in ' '.join(c)]
            ck('cg: 增量只导变更的皮肤（--only 收窄）',
               only and '--only' in only[0] and only[0][only[0].index('--only') + 1] == '2b_2',
               str(only))

            # ── 降级台账接进了 audio 档（2026-10-03）：它红了，这一档就不许报绿 ──
            # 只读判据默认全 0 的桩测不出这条：上一版所有"跑了两道审计"的结论都是无条件 True，
            # 而 audio 档真正要拦的恰恰是"游戏改了形状、我们只能猜着填"那种情况。
            r = Rec()
            old, up.run = up.run, r
            try:
                ok = up.st_audio(set())
            finally:
                up.run = old
            ck('audio: 未签字 → 降级台账这道只读判据确实跑了',
               len(r.hit('check_degradation')) == 1, str(r.calls))
            ck('audio: 未签字 → 台账结论进了给前端看的那行', '降级' in up.RESULTS['audio']['detail']
               or 'OK' in up.RESULTS['audio']['detail'], up.RESULTS['audio']['detail'])
            r = Rec(rc_of={'check_degradation': 1})
            old, up.run = up.run, r
            try:
                ok = up.st_audio(set())
            finally:
                up.run = old
            ck('audio: 台账判红 → 未签字分支也判红（不再无条件绿）', ok is False,
               str(up.RESULTS['audio']))
            ck('audio: 台账判红 → 结论里说清"先判断再签字"', '先判断' in up.RESULTS['audio']['detail'],
               up.RESULTS['audio']['detail'])
            r = Rec(rc_of={'check_degradation': 1})
            old, up.run = up.run, r
            try:
                ok = up.st_audio({'audio'})
            finally:
                up.run = old
            ck('audio: 台账判红 → 即使签了字，结论仍是红（签了字也不等于数据形状没变）',
               ok is False and len(r.hit('extract_cv_voice')) == 1, str(up.RESULTS['audio']))

            # ── 「恒 exit 0 只作参考」的辅助脚本，退出码必须被读 ──
            # voice_gap_audit 设计上不返回非 0（它的产出是分类清单，不是判据），
            # 所以 rc≠0 只有一个意思：它自己崩了。2026-10-03 换三元组时把它弄坏（ValueError），
            # 因为没人看这个 rc，audio 档照绿了一整天 ⇒ 这类"参考型"脚本的崩溃必须有色。
            r = Rec(rc_of={'voice_gap_audit': 1})
            old, up.run = up.run, r
            try:
                ok = up.st_audio(set())
            finally:
                up.run = old
            ck('audio: gap_audit 崩了（它恒 0，非 0 即故障）→ 未签字分支也判红', ok is False,
               str(up.RESULTS['audio']))
            ck('audio: 判红时结论点名是 gap_audit 崩，不是含糊的"rc 非 0"',
               'gap_audit 崩' in up.RESULTS['audio']['detail'], up.RESULTS['audio']['detail'])
        finally:
            up.fingerprint = real
    tmp_work(body)


# ------------------------------------------------------------------ 5 进度透传
def t_stream():
    print('\n[5] run() 必须边跑边吐进度（面板只看得到本进程的 stdout）')
    code = ('import sys,time\n'
            'for i in range(12):\n'
            '    print(f"进度 {i+1}/12 张", flush=True)\n'
            '    time.sleep(0.12)\n'
            'print("最后一行")\n')
    t0 = time.time()
    first = {'t': None}
    real_print = up.log

    def spy(m):
        if first['t'] is None and '进度' in m:
            first['t'] = time.time() - t0
        real_print(m)
    up.log = spy
    old_env = dict(up.ENV)
    up.ENV = dict(old_env, PYTHONIOENCODING='utf-8')
    try:
        rc, so, se = up.run([sys.executable, '-c', code], timeout=60)
    finally:
        up.log = real_print
        up.ENV = old_env
    ck('退出码与全文都还在（判据照旧能数行）', rc == 0 and so.count('进度') == 12, f'rc={rc}')
    ck('收尾行进来了', '最后一行' in so)
    # 关键：**第一条进度行的到达时间早于命令结束** —— 憋到最后吐就等于界面静默
    ck('进度是流式转发而非跑完才吐', first['t'] is not None and first['t'] < 1.0,
       f'首行 {first["t"]:.2f}s')


def t_timeout_tree():
    print('\n[6] 超时走整树 taskkill 并照旧抛 TimeoutExpired（让阶段判红）')
    code = ('import subprocess,sys,time\n'
            'subprocess.Popen([sys.executable,"-c","import time;time.sleep(120)"])\n'
            'time.sleep(120)\n')
    try:
        up.run([sys.executable, '-c', code], timeout=3)
        ck('超时抛异常', False, '没抛')
    except subprocess.TimeoutExpired:
        ck('超时抛 TimeoutExpired（阶段据此判红）', True)
    time.sleep(1.0)
    n = subprocess.run(['taskkill'], capture_output=True)  # 只为拿一次 shell 句柄，不用其结果
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          '@((Get-CimInstance Win32_Process | Where-Object '
                          '{ $_.Name -eq "python.exe" -and $_.CommandLine -match "time.sleep\\(120\\)" }).Count)'],
                         capture_output=True, text=True).stdout.strip()
    ck('超时后子进程树没留下睡 120 秒的孤儿', out in ('0', ''), f'残留={out}')


def t_clean_diff():
    print('\n[7] diff 报"0 新增 0 变更"：是合法状态，不许判红、更不许把已有清单冲空')
    def body(d):
        real = up.fingerprint
        up.fingerprint = lambda: 'bundles=1 deps=test'
        try:
            up.write_scope(['AssetBundles/painting/2b'], 1, 0)      # 先放一份有效清单
            before = open(os.path.join(d, 'affected.txt'), encoding='utf-8').read()

            def empty_diff(argv, **kw):                              # 模拟"已拉完，再查一次没变化"
                open(os.path.join(d, 'diff_paths.txt'), 'w', encoding='utf-8').close()
                return 0, '== 新增（模拟器有，本地没有）: 0 个 ==\n== 本地独有: 0 个 ==', ''
            old, up.run = up.run, empty_diff
            try:
                ok = up.st_pull(set())
            finally:
                up.run = old
            v = up.RESULTS['pull']
            ck('0 变更 → 判绿（不是红）', ok is True, str(v))
            ck('0 变更 → 沿用上次清单而不是报"范围不可用"', '沿用上次 detect 的范围清单' in v['detail'],
               v['detail'])
            ck('0 变更 → affected.txt 内容一字未改（没被空清单冲掉）',
               open(os.path.join(d, 'affected.txt'), encoding='utf-8').read() == before)

            os.remove(os.path.join(d, 'affected.txt'))
            os.remove(os.path.join(d, 'affected.meta'))
            old, up.run = up.run, empty_diff
            try:
                ok2 = up.st_pull(set())
            finally:
                up.run = old
            v2 = up.RESULTS['pull']
            ck('0 变更且本来就没清单 → 仍判绿并说"没有要重算的东西"',
               ok2 is True and '没有要重算的东西' in v2['detail'], str(v2))
        finally:
            up.fingerprint = real
    tmp_work(body)


def t_deps_gate():
    print('\n[8] 依赖表超集闸门：只对本管线消费的丢失判红')
    old = {'painting/2b': {'file': '../AssetBundles/painting/2b'},
           'spinepainting/x': {'file': '../AssetBundles/spinepainting/x'},
           'iconframe/10001_skeletondata': {'file': '../AssetBundles/android/iconframe/10001_skeletondata'},
           'ui/whatever': {'file': '../AssetBundles/ui/whatever'}}
    # 丢 1 条 painting（消费）+ 1 条 ui（不消费）；iconframe 那条留着当阴性对照
    new = {k: v for k, v in old.items() if k not in ('painting/2b', 'ui/whatever')}
    fatal, benign = up.deps_classify(old, new)
    ck('消费目录（painting）丢了 → fatal', fatal == ['painting/2b'], str(fatal))
    ck('不消费的条目丢了 → benign，不判红', benign == ['ui/whatever'], str(benign))
    f0, b0 = up.deps_classify(old, {k: v for k, v in old.items()
                                    if k != 'iconframe/10001_skeletondata'})
    ck('只丢 iconframe 时既不判红也不声张成 fatal（2026-10-01 真跑撞到的那 4 条）',
       not f0 and b0 == ['iconframe/10001_skeletondata'], f'{f0} {b0}')
    f2, b2 = up.deps_classify(old, old)
    ck('一条没丢时两边都空', not f2 and not b2, f'{f2} {b2}')


def t_freshness_key():
    print('\n[9] 范围清单的新鲜度只能看源包数，不许看派生产物')
    def body(d):
        real = up.fingerprint
        up.fingerprint = lambda: 'bundles=92679 deps=OLDHASH'
        up.write_scope(['AssetBundles/painting/2b'], 1, 0)
        # 正常顺序：拉完包 → 换入依赖表（deps 哈希变）→ 跑导出。
        # 拿整条指纹判过期 = 每次正常运行都把刚写好的清单打成废纸（2026-10-01 真事故）。
        up.fingerprint = lambda: 'bundles=92679 deps=NEWHASH'
        mode, payload = up.scope_state(False)
        ck('源包没变、只换了依赖表 ⇒ 清单仍算 ok（不是 stale）', mode == 'ok', f'{mode} {payload}')
        ck('清单内容一条没丢', up.affected_stems(False) == ['2b'], str(up.affected_stems(False)))
        # 源包真的变了才算过期
        up.fingerprint = lambda: 'bundles=99999 deps=NEWHASH'
        mode2, why2 = up.scope_state(False)
        ck('源包数变了才算 stale，并说清两边 bundles=', mode2 == 'stale' and 'bundles=' in why2,
           f'{mode2} {why2}')
        # 过期 + 零变更 ⇒ 绝不允许把非空清单冲掉
        up.fingerprint = lambda: 'bundles=92679 deps=NEWHASH'
        up.write_scope([], 0, 0)
        left = [x.strip() for x in open(os.path.join(d, 'affected.txt'), encoding='utf-8') if x.strip()]
        ck('空结果不得覆盖非空清单（旧内容原样保住）', left == ['AssetBundles/painting/2b'], str(left))
        up.fingerprint = real
    tmp_work(body)


def t_device_down():
    print('\n[10] 模拟器没开：包已在本地时不许把整条线卡在第 1 步')
    def body(d):
        real = up.fingerprint
        up.fingerprint = lambda: 'bundles=1 deps=test'
        rec = Rec()

        def fail_run(argv, **kw):
            rec.calls.append([str(a) for a in argv])
            return 1, '✗ 连不上模拟器（已扫端口 16384-16499）\n' \
                      '    raise RuntimeError("ls 顶层失败: no devices")', ''
        try:
            up.write_scope(['AssetBundles/painting/2b'], 1, 0)
            old, up.run = up.run, fail_run
            try:
                ok = up.st_pull(set())
            finally:
                up.run = old
            v = up.RESULTS['pull']
            ck('设备不可达 + 清单有效 → 判绿（沿用清单继续，不卡线）', ok is True, str(v))
            ck('结论说清"设备不可达"与"沿用清单"两件事',
               '设备不可达' in v['detail'] and '沿用清单' in v['detail'], v['detail'])
            ck('没试图跑 sync --apply（设备没开时绝不能去写 files/）',
               not [c for c in rec.calls if '--apply' in c],
               str(rec.calls))

            os.remove(os.path.join(d, 'affected.txt'))
            os.remove(os.path.join(d, 'affected.meta'))
            old, up.run = up.run, fail_run
            try:
                ok2 = up.st_pull(set())
            finally:
                up.run = old
            v2 = up.RESULTS['pull']
            ck('设备不可达且清单也不可用 → 判红（这时确实没法知道范围）',
               ok2 is False and '不可用' in v2['detail'], str(v2))
        finally:
            up.fingerprint = real
    tmp_work(body)


def main():
    t_stems()
    t_no_scope()
    t_stale_scope()
    t_gates()
    t_stream()
    t_timeout_tree()
    t_clean_diff()
    t_deps_gate()
    t_freshness_key()
    t_device_down()
    print('\n' + ('[FAIL] ' + '；'.join(FAIL) if FAIL else '[PASS] 签字门与增量范围闸门全绿'))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
