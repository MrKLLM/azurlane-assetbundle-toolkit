# -*- coding: utf-8 -*-
"""资产更新控制台 —— 本地网页仪表盘，双击「启动资产更新控制台.bat」打开。

它**不重新实现**任何流水线逻辑：每个按钮都是去起 `scripts/update_pipeline.py` 子进程，
然后把它写的日志实时读回来显示。这样"界面上看到的"和"命令行跑的"永远是同一套代码，
不存在两份逻辑各自漂移的问题（本项目栽过这类坑）。

界面按「五步主线」组织（接模拟器 / 同步配置表 / 重新导出 / 看图对比 / 签字换入），
步骤归属与「写到哪儿」两个事实定义在 `update_pipeline.STEPS` 与 `Stage.writes` 里，
面板只读不抄 —— 抄一份就会在新加阶段时把它藏起来。

    py -3 scripts/pipeline_panel.py            # 起服务并自动开浏览器
    py -3 scripts/pipeline_panel.py --no-open  # 只起服务（无人值守）
    py -3 scripts/pipeline_panel.py --port 8790

安全边界（这是个能起子进程的本地服务，所以写死三条）：
  · 只绑 127.0.0.1，不对外。
  · 能跑什么由 `update_pipeline.STAGES` 的**阶段名白名单**决定 —— 前端传进来的
    stage/approve 名字必须命中白名单，否则拒绝。不存在"把输入拼进命令行"这条路。
  · 图片只从 `.diag/pipeline/` 里出，realpath 前缀校验，防目录穿越。
"""
import argparse
import glob
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PIPE = os.path.join(ROOT, 'scripts', 'update_pipeline.py')
WORK = os.path.join(ROOT, '.diag', 'pipeline')
PANEL = os.path.join(WORK, 'panel')
RUNS = os.path.join(PANEL, 'runs.json')
STATE = os.path.join(WORK, 'pipeline_state.json')
ARCHIVE = os.path.join(PANEL, 'archive')
BG_REVIEW_JSON = os.path.join(PANEL, 'bg_review.json')
ANNOT = os.path.join(ROOT, 'annotations', 'bg_char_labels.json')
BGROOT_ANNOT = os.path.join(ROOT, 'annotations', 'bg_root_names.json')
RAW_DIR = os.path.join(ROOT, 'Output', 'Raw')
BG_THUMBS = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_thumbs')
PORT = 8788
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')

_lock = threading.Lock()


def pid_alive(pid):
    """只读地判断一个子进程还在不在。

    ⚠️ Windows 上**绝对不能用 `os.kill(pid, 0)` 探活**：CPython 在非 POSIX 语义下把它
    实现成 `OpenProcess(...)+TerminateProcess(handle, 0)` —— 那不是探测，那是**杀掉**。
    本面板每 8 秒轮一次 /api/state，第一次轮询就会把正在跑的流水线子进程当场终止；
    一次真更新要跑几十分钟，症状会是"任务莫名结束、日志停在半路"。
    ⇒ 用 OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) + GetExitCodeProcess 只读取退出码。
    """
    if not pid:
        return False
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    k = ctypes.windll.kernel32
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        k.CloseHandle(h)


# ------------------------------------------------------------------ 阶段白名单
def stage_keys():
    """阶段名与档位一律从 update_pipeline 读，**不在面板里再抄一份清单**——
    抄了就会漂移（本项目栽过"谁写谁读各一份实现"这类坑）。
    update_pipeline 有 __main__ 保护，import 它没有副作用。"""
    sys.path.insert(0, HERE)
    import update_pipeline as up
    import importlib
    importlib.reload(up)          # 改了流水线脚本后不用重启面板
    return [{'key': s.key, 'title': s.title, 'tier': s.tier, 'judge': s.judge_desc,
             'step': s.step, 'writes': s.writes,
             # 缓存指纹该不该带 `cfg=`：面板按它挑指纹，不自己再抄一条"cfg.* 前缀"规则
             'produces_cfg': bool(getattr(s, 'produces_cfg', False)),
             # 预计耗时的两个来源都跟着阶段走（没量过的都是 0 ⇒ 进度台显示"未知"而不是猜）
             'est': getattr(s, 'est', 0.0), 'rate': getattr(s, 'rate', 0.0),
             'unit': getattr(s, 'unit', '')} for s in up.STAGES], dict(up.STEPS)


# ------------------------------------------------------------------ 运行记录
def load_runs():
    try:
        return json.load(open(RUNS, encoding='utf-8'))
    except Exception:
        return []


def save_runs(runs):
    os.makedirs(PANEL, exist_ok=True)
    tmp = RUNS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(runs, f, ensure_ascii=False, indent=1)
    os.replace(tmp, RUNS)


def new_round():
    """归档本轮阶段缓存与任务记录，回到第 1 步。

    只动 .diag/pipeline/ 下的**状态**，不碰 Output/、inputs/、files/ 与任何阶段产物。
    为什么不能靠删文件当"重置"：pipeline_state.json 是阶段缓存，删了只是让阶段显示
    idle；真正开新一轮仍要重新跑。归档而不是删，是为了还能回看上一轮到底跑了什么。
    """
    refresh_states()
    running = running_job()
    if running:
        return {'error': '还有任务在跑（%s），等它结束再开新一轮' % running.get('label', '')}
    os.makedirs(ARCHIVE, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    moved = []

    def _archive(src, name):
        dst = os.path.join(ARCHIVE, '%s_%s%s' % (name, stamp, os.path.splitext(src)[1]))
        os.replace(src, dst)
        try:
            moved.append(os.path.relpath(dst, ROOT).replace('\\', '/'))
        except ValueError:              # 测试把归档目录挪到别的盘符时也能报出来
            moved.append(dst.replace('\\', '/'))

    for src, name in ((STATE, 'pipeline_state'), (RUNS, 'runs')):
        if os.path.isfile(src):
            _archive(src, name)
    # 新一轮不是只清阶段结论：细节抽屉的「这次新增了什么 / 对照表」读的是
    # new_paintings.txt 与 sheet_*.png。它们留在 WORK 里，开新一轮后仍会显示上一轮
    # 的 36 个文件（2026-11-12 用户截图）。一并归档，并清掉 news 缓存。
    import glob as _glob
    round_files = [os.path.join(WORK, 'new_paintings.txt')]
    round_files += _glob.glob(os.path.join(WORK, 'sheet_*.png'))
    for src in round_files:
        if os.path.isfile(src):
            _archive(src, os.path.splitext(os.path.basename(src))[0])
    for slot in ('news', 'scope', 'units', 'scopetag'):
        _CACHE[slot] = [None, 0.0]
    save_runs([])
    return {'ok': True, 'stamp': stamp, 'archived': moved}


def running_job():
    for r in load_runs():
        if r.get('state') == 'running':
            if pid_alive(r.get('pid')):
                return r
            r['state'] = 'gone'
    return None


# ------------------------------------------------------------------ 背景人工标注
_BG_REVIEW = {'at': 0.0, 'data': None}
_BG_LOCK = threading.Lock()
BGPUB = {'id': 0, 'state': 'idle', 'step': 0, 'total': 4, 'title': '',
         'error': '', 'saved': 0, 'started': ''}
BG_STEPS = (
    ('生成复核索引', ['scripts/build_bg_meta.py', '--allow-unlabeled'], 300),
    ('发布角色标注', ['scripts/publish_bg_char_flags.py', '--from-annotations'], 300),
    ('重建背景索引', ['scripts/build_bg_meta.py'], 300),
    ('生成新缩略图', ['scripts/make_bg_thumbs.py'], 900),
)


def _run_py(argv, timeout=300):
    try:
        p = subprocess.run([PY] + argv, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout, env=ENV)
        return p.returncode, (p.stdout or '') + (p.stderr or '')
    except subprocess.TimeoutExpired:
        return 124, '超时（%ds）' % timeout
    except Exception as e:
        return 1, '%s: %s' % (type(e).__name__, e)


def bg_review(fresh=False):
    """扫描 Raw + 现有标注，返回待人工判「有没有角色」的新场景图。

    走 `build_bg_meta.py --review-out`，不写正式索引：新图正是 has_char 闸门要拦的东西，
    先给人工一张可点的清单。结果缓存 2 分钟，避免每开一次弹窗都重扫 1,900 张图。
    """
    if (not fresh and _BG_REVIEW['data'] is not None
            and time.time() - _BG_REVIEW['at'] < 120):
        return _BG_REVIEW['data']
    os.makedirs(PANEL, exist_ok=True)
    rc, out = _run_py(['scripts/build_bg_meta.py', '--review-out', BG_REVIEW_JSON], 300)
    if rc != 0:
        return {'error': '扫描新背景失败', 'log': out[-1600:]}
    try:
        with open(BG_REVIEW_JSON, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return {'error': '读不到复核清单：%s' % e}
    _BG_REVIEW.update(at=time.time(), data=data)
    return data


def bg_roots_save(body):
    """人工补名词根：只接受当前复核清单里的 root 档；写 annotations 正本后重建 bg_meta。"""
    names = body.get('names')
    if not isinstance(names, dict) or not names:
        return {'error': 'names 必须是非空 {root: 中文名}'}
    if len(names) > 50:
        return {'error': '一次最多补 50 个词根'}
    data = bg_review()
    if data.get('error'):
        return data
    allowed = {x.get('root') for x in
               ((data.get('unnamed_roots') or []) + (data.get('manual_roots') or []))
               if x.get('root')}
    clean = {}
    for root, cn in names.items():
        root = str(root).strip()
        cn = str(cn or '').strip()
        if root not in allowed:
            return {'error': '词根不在待命名清单里：%s（已有表内名字的词根不允许覆盖）' % root}
        if not cn or len(cn) > 40 or any(x in cn for x in '\n\r|\\'):
            return {'error': '中文名必须非空、≤40 字、不含换行/竖线/反斜杠：%s' % root}
        clean[root] = cn
    with _BG_LOCK:
        if BGPUB.get('state') == 'running':
            return {'error': '背景发布任务正在跑，等它结束再补名'}
    try:
        doc = (json.load(open(BGROOT_ANNOT, encoding='utf-8'))
               if os.path.isfile(BGROOT_ANNOT) else
               {'schema': 1,
                'note': '背景词根的人工补名正本（入库）。只补 root 档；不覆盖表内证据。',
                'labels': {}})
    except (OSError, ValueError) as e:
        return {'error': '读人工补名正本失败：%s' % e}
    labels = doc.setdefault('labels', {})
    for root, cn in clean.items():
        prev = labels.get(root) if isinstance(labels.get(root), dict) else {}
        # 更新名字不应冲掉已有的人工依据；只有第一次补名才写默认 why。
        why = str(prev.get('why') or '').strip() or '控制台背景标注复核台人工补名'
        labels[root] = {'cn': cn, 'why': why,
                        'updated_at': time.strftime('%Y-%m-%d %H:%M')}
    doc['schema'] = doc.get('schema', 1)
    doc['updated_at'] = time.strftime('%Y-%m-%d')
    tmp = BGROOT_ANNOT + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, BGROOT_ANNOT)
    except OSError as e:
        return {'error': '写人工补名正本失败：%s' % e}
    _BG_REVIEW.update(at=0.0, data=None)
    rc, out = _run_py(['scripts/build_bg_meta.py', '--allow-unlabeled'], 300)
    if rc != 0:
        return {'error': '命名已保存，但重建 bg_meta 失败', 'log': out[-1600:]}
    return {'ok': True, 'saved': len(clean), 'names': clean}


def bg_publish_worker(job_id):
    """后台跑 4 步发布；每完成一步更新 BGPUB，前端轮询画真实步进度。"""
    for i, (title, argv, timeout) in enumerate(BG_STEPS):
        with _BG_LOCK:
            if BGPUB.get('id') != job_id:
                return
            BGPUB.update(state='running', step=i, title=title, error='')
        rc, out = _run_py(argv, timeout)
        with _BG_LOCK:
            if BGPUB.get('id') != job_id:
                return
            BGPUB['step'] = i + 1
            if rc != 0:
                BGPUB.update(state='error', title=title,
                             error='%s失败（rc=%s）' % (title, rc),
                             detail=out[-1600:])
                return
    with _BG_LOCK:
        if BGPUB.get('id') == job_id:
            BGPUB.update(state='done', step=len(BG_STEPS), title='完成')
    _BG_REVIEW.update(at=0.0, data=None)


def bg_publish_status(job_id=None):
    with _BG_LOCK:
        d = dict(BGPUB)
    if job_id is not None and d.get('id') != job_id:
        return {'error': '这个发布任务已不存在（面板可能重启过）', 'state': 'stale'}
    d['steps'] = [x[0] for x in BG_STEPS]
    return d


def bg_chars_save(body):
    """保存人工标注；`publish=true` 时启动后台 4 步发布（不阻塞 HTTP 请求）。"""
    labels = body.get('labels')
    if not isinstance(labels, dict):
        return {'error': 'labels 必须是 {key: 0|1}'}
    if len(labels) > 5000:
        return {'error': '一次提交的标注太多（>5000）'}
    data = bg_review()
    if data.get('error'):
        return data
    scene = set(data.get('scene_keys') or [])
    if not scene:
        return {'error': '复核清单为空，先重扫'}
    clean = {}
    for k, v in labels.items():
        if k not in scene:
            return {'error': '这张图不在本轮场景清单里：%s' % k}
        if int(v) not in (0, 1):
            return {'error': '标注值只能是 0/1：%s=%r' % (k, v)}
        clean[k] = int(v)
    if not os.path.isfile(ANNOT):
        return {'error': '缺 %s（人工标注正本）' % os.path.relpath(ANNOT, ROOT)}
    try:
        with open(ANNOT, encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        return {'error': '读标注正本失败：%s' % e}
    all_labels = doc.setdefault('labels', {})
    before = len(all_labels)
    all_labels.update(clean)
    doc['updated_at'] = time.strftime('%Y-%m-%d %H:%M')
    doc.setdefault('schema', 1)
    doc.setdefault('note', '场景背景「画面里有没有角色」的人工视觉标注合并正本。')
    tmp = ANNOT + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=0)
        os.replace(tmp, ANNOT)
    except OSError as e:
        return {'error': '写标注正本失败：%s' % e}
    _BG_REVIEW.update(at=0.0, data=None)
    saved = len(all_labels) - before
    if not body.get('publish'):
        return {'ok': True, 'saved': saved, 'published': False, 'pending': len(scene - set(all_labels))}

    missing = sorted(scene - set(all_labels))
    if missing:
        return {'ok': True, 'saved': saved, 'published': False, 'pending': len(missing),
                'error': '还有 %d 张场景图没判，补齐后才能发布（前几张：%s）'
                         % (len(missing), '、'.join(missing[:5]))}
    with _BG_LOCK:
        if BGPUB.get('state') == 'running':
            return {'error': '上一次发布还在跑（%s），等它结束' % BGPUB.get('title')}
        BGPUB.update(id=BGPUB.get('id', 0) + 1, state='running', step=0,
                     total=len(BG_STEPS), title='准备中', error='', detail='',
                     saved=saved, started=time.strftime('%H:%M:%S'))
        job_id = BGPUB['id']
    threading.Thread(target=bg_publish_worker, args=(job_id,), daemon=True).start()
    return {'ok': True, 'saved': saved, 'published': False, 'job': job_id,
            'pending': 0, 'total': len(BG_STEPS), 'steps': [x[0] for x in BG_STEPS]}


def step_of_argv(argv):
    """这次任务该把「正在跑 / 待办」锚到第几步。

    runs.json 以前没有这个字段，`currentStep()` 读 `S.running.step` 永远是 undefined
    ⇒ 只能退回"第一个没绿的步骤"。deps 换表后那个步骤恰好是第 1 步，
    于是跑 cg（第 3 步）时右栏写「正在跑 01」（2026-10-23 用户截图）。
    """
    if '--plan' in argv:
        return 0
    only = None
    for i, a in enumerate(argv):
        if a == '--only' and i + 1 < len(argv):
            only = {x.strip() for x in argv[i + 1].split(',') if x.strip()}
    try:
        stages, _ = stage_keys()
    except Exception:
        return 1
    nums = [s.get('step') or 0 for s in stages if only is None or s['key'] in only]
    nums = [n for n in nums if n]
    return min(nums) if nums else 1


def cg_requested(argv):
    """这次任务是否**真的会写** CG（--only 含 cg 且 cg 被签字，或整条管线签了 cg）。"""
    only, approved, i = None, set(), 0
    while i < len(argv):
        if argv[i] == '--only' and i + 1 < len(argv):
            only = {x.strip() for x in argv[i + 1].split(',') if x.strip()}
            i += 2
        elif argv[i] == '--approve':
            i += 1
            while i < len(argv) and not argv[i].startswith('--'):
                approved.add(argv[i]); i += 1
        else:
            i += 1
    return ('cg' in approved) if only is None else ('cg' in only and 'cg' in approved)


def gallery_ok(timeout=2.0):
    """启动 CG 任务前的探活，与 update_pipeline.gallery_reachable 同一实现。"""
    sys.path.insert(0, HERE)
    try:
        import update_pipeline as up
        return up.gallery_reachable(timeout)
    except Exception:
        return False


def port_listening(port=8777):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0


def ensure_gallery(timeout=10.0):
    """CG 前置：8777 不在就**自己起**运行目录那份服务器，不再把双击 bat 甩给用户。

    - 已可达 → 直接过；
    - 端口被占但页面不对（旧的无根启动器/别的服务）→ 不盲目起第二个：
      新进程会走 port_in_use 复用旧进程，等于继续打开 404；让用户关掉那个窗口；
    - 端口空 → detached 启动 Output/gallery_v2/_gallery_server.py --export，轮询到可达。
    失败才回退到手动提示（并给出日志路径）。
    """
    if gallery_ok():
        return True, '8777 已就绪'
    if port_listening(8777):
        return False, ('8777 被另一个进程占用，但它没有 gallery_v2/index.html'
                       '（多半是旧的无根启动器）。关掉那个黑窗口后再点重导；'
                       '端口空闲时控制台会自己启动。')
    srv = os.path.join(ROOT, 'Output', 'gallery_v2', '_gallery_server.py')
    if not os.path.isfile(srv):
        return False, f'找不到 {srv}（先双击一次 Output\\gallery_v2\\启动资产浏览器.bat）'
    os.makedirs(PANEL, exist_ok=True)
    log = os.path.join(PANEL, 'gallery_server.log')
    lf = open(log, 'w', encoding='utf-8', errors='replace')
    try:
        p = subprocess.Popen([PY, srv, '--export'], cwd=os.path.dirname(srv),
                             stdout=lf, stderr=subprocess.STDOUT, env=ENV,
                             creationflags=0x00000008 if os.name == 'nt' else 0)
    finally:
        lf.close()
    for _ in range(max(1, int(timeout * 2))):
        if gallery_ok(1.0):
            return True, f'已自动启动画廊服务器 8777（pid={p.pid}；日志 {log}）'
        time.sleep(0.5)
    return False, (f'已尝试启动画廊服务器 8777，但 {timeout:.0f} 秒内仍不可达：'
                   f'看 {log}；或手动双击 Output\\gallery_v2\\启动资产浏览器.bat')


def start_job(label, argv, script=None):
    """起一个脱离面板的流水线子进程。重活必须串行 —— 已有在跑就拒绝。

    `script` 只允许**服务端代码里写死**的那几个（目前 `scripts/scan_assets.py` 一个），
    前端传不上来 —— 「能跑什么由白名单决定」这条边界不因泛化而破。
    """
    target = script or PIPE
    with _lock:
        cur = running_job()
        if cur:
            return None, f'已经有一个任务在跑（{cur["label"]}，pid={cur["pid"]}）。' \
                         f'这台机器 15.4GB，重活只允许一次一个。'
        if not script and cg_requested(argv):
            ok, why = ensure_gallery()
            if not ok:
                return None, why
            print(f'[控制台] {why}')
        os.makedirs(PANEL, exist_ok=True)
        rid = time.strftime('%H%M%S')
        log = os.path.join(PANEL, f'run_{rid}.log')
        lf = open(log, 'w', encoding='utf-8', errors='replace')
        p = subprocess.Popen([PY, target] + argv, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT,
                             env=ENV, creationflags=0x00000008 if os.name == 'nt' else 0)
        runs = load_runs()
        runs.append({'id': rid, 'label': label, 'argv': argv, 'pid': p.pid, 'log': log,
                     'step': 0 if script else step_of_argv(argv),
                     'state': 'running', 'started': time.strftime('%Y-%m-%d %H:%M:%S')})
        save_runs(runs)
        lf.close()   # 让子进程自己持有；父进程关掉句柄，进程结束后面板仍能读文件
        return rid, None


def refresh_states():
    """把每个 running 任务的实际状态回读一遍（靠日志收尾行，不靠 pid）。"""
    runs = load_runs()
    changed = False
    for r in runs:
        if r.get('state') != 'running':
            continue
        alive = pid_alive(r.get('pid'))
        tail = ''
        try:
            tail = open(r['log'], encoding='utf-8', errors='replace').read()[-4000:]
        except OSError:
            pass
        finished = ('===== 汇总 =====' in tail) or ('[FAIL]' in tail and not alive)
        if not alive:
            # 进程没了就是结束了。`--plan` 这类不打印「汇总」的正常结束也算 done，
            # 只是用 clean 记下有没有看到收尾行 —— 别把它误标成失败，那会让人以为跑挂了。
            r['state'] = 'done'
            r['clean'] = bool(finished or '要签字的 live 档' in tail or '[PASS]' in tail)
            r['ended'] = time.strftime('%Y-%m-%d %H:%M:%S')
            changed = True
    if changed:
        save_runs(runs)
    return runs


# ------------------------------------------------------------------ 进度台
# 跑的时候主屏上那条「已用 / 内存 / 阶段 N/M / 剩余」细带。四个量都必须是**可核对的事实**：
#   · 已用  = 子进程启动时刻（runs.json 的 started），不是"界面刷新了多久"
#   · 内存  = **整棵进程树**的工作集之和 —— 只算编排器自己会漏掉真正吃内存的那几个导出子进程
#   · 阶段  = 当前日志里最后一条 `== key` 行；N/M 的 M 来自**本次 argv 的范围**（--only 会缩小它）
#   · 剩余  = 各阶段**历史均值**之和（吃 .diag/pipeline/run_*.log 的时间戳）。
#             有阶段没样本时**不装作知道**：改报「≥」下限，而不是拿总时长×百分比糊一个数。
# 没在跑 ⇒ 返回 None，界面上一分都不多。这也是"静止时逐像素相同"能继续成立的前提。
_TS = re.compile(r'^\[(\d\d):(\d\d):(\d\d)\]')
_STAGE_START = re.compile(r'^\[\d\d:\d\d:\d\d\]\s+==\s+(\S+)')
_STAGE_VERDICT = re.compile(r'^\[\d\d:\d\d:\d\d\]\s+[\u2705\u274c]\s+(\S+):')
_STAGE_SKIP = re.compile(r'^\[\d\d:\d\d:\d\d\]\s+\u23ed\s+(\S+)')


def _secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def _stage_spans(path):
    """一份日志 → [(key, 起秒, 止秒)]。止 = 下一个阶段的起点，最后一个阶段止于日志末行。"""
    starts, last = [], None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                m = _TS.match(ln)
                if not m:
                    continue
                t = _secs(*m.groups())
                if last is not None and t < last:
                    t += 86400                     # 跨零点：按单调递增修一次
                last = t
                sm = _STAGE_START.match(ln)
                if sm:
                    starts.append((t, sm.group(1)))
    except OSError:
        return []
    out = []
    for i, (t, k) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else last
        if end is not None and end > t:
            out.append((k, t, end))
    return out


def _stage_means():
    """各阶段历史平均耗时（秒），样本 = .diag/pipeline/run_*.log。"""
    acc = {}
    for p in glob.glob(os.path.join(PANEL, 'run_*.log')):
        for k, a, b in _stage_spans(p):
            acc.setdefault(k, []).append(b - a)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def _scope_units(fp=None):
    """本次增量里每个"按项数线性耗时"的阶段要处理多少项（给速率估算用）。

    ⚠️ 历史均值在**第一次跑**时必然是空的（本项目 13 个阶段里 9 个从没真跑过），
    只认均值的话进度台的「剩余」永远显示未知 —— 那正是用户抱怨"不知道进行到什么程度"。
    """
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            importlib.reload(up)
            return {s.key: up.stage_units(s, False, fp) for s in up.STAGES
                    if getattr(s, 'rate', 0.0)}
        except Exception as e:
            print(f'[警告] 读各阶段本次项数失败：{e}')
            return None
    return _cached('units', 30.0, calc) or {}



def _progress_from_log(path):
    """当前日志 → (在跑的阶段key, 它的起点秒, 已判完的 key 集合, 已跳过的 key 集合)。"""
    started, done, skipped = [], set(), set()
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                if not _TS.match(ln):
                    continue
                m = _STAGE_START.match(ln)
                if m:
                    started.append((_secs(*_TS.match(ln).groups()), m.group(1)))
                    continue
                m = _STAGE_VERDICT.match(ln)
                if m:
                    done.add(m.group(1))
                    continue
                m = _STAGE_SKIP.match(ln)
                if m:
                    skipped.add(m.group(1))
    except OSError:
        return '', None, set(), set()
    cur, cur_t = '', None
    for t, k in started:
        if k not in done:
            cur, cur_t = k, t
    return cur, cur_t, done, skipped


def _scope_keys(argv, stages):
    """本次运行**打算考虑**的阶段（进度台的分母）。--plan 不跑阶段 ⇒ 0。"""
    allk = [s['key'] for s in stages]
    if '--plan' in argv:
        return []
    only = ''
    if '--only' in argv:
        i = argv.index('--only')
        if i + 1 < len(argv):
            only = argv[i + 1]
    if only:
        want = {x for x in only.split(',') if x}
        return [k for k in allk if k in want]
    return allk


def _tree_mem_mb(root):
    """整棵进程树的工作集合计（MB）+ 进程数。**只读查询**，与 pid_alive 同一条纪律。"""
    import ctypes

    class PE(ctypes.Structure):
        _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                    ('th32ProcessID', ctypes.c_ulong), ('th32DefaultHeapID', ctypes.c_void_p),
                    ('th32ModuleID', ctypes.c_ulong), ('cntThreads', ctypes.c_ulong),
                    ('th32ParentProcessID', ctypes.c_ulong), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', ctypes.c_ulong), ('szExeFile', ctypes.c_char * 260)]

    class PMC(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]

    k = ctypes.windll.kernel32
    kids = {}
    snap = k.CreateToolhelp32Snapshot(0x2, 0)          # TH32CS_SNAPPROCESS
    if snap and snap != -1:
        try:
            e = PE()
            e.dwSize = ctypes.sizeof(e)
            ok = k.Process32First(snap, ctypes.byref(e))
            while ok:
                kids.setdefault(e.th32ParentProcessID, []).append(e.th32ProcessID)
                ok = k.Process32Next(snap, ctypes.byref(e))
        finally:
            k.CloseHandle(snap)
    pids, stack = [], [int(root)]
    while stack:
        p = stack.pop()
        pids.append(p)
        stack.extend(kids.get(p, []))
    getmem = getattr(k, 'K32GetProcessMemoryInfo', None) or ctypes.windll.psapi.GetProcessMemoryInfo
    total = 0
    for p in pids:
        h = k.OpenProcess(0x1000, False, p)            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            c = PMC()
            c.cb = ctypes.sizeof(c)
            if getmem(h, ctypes.byref(c), c.cb):
                total += c.WorkingSetSize
        finally:
            k.CloseHandle(h)
    return total / 1048576.0, len(pids)


def _log_secs(path):
    """一份日志的首末时间戳差（秒）= 这一轮到底跑了多久。跨零点按 +86400 修一次。"""
    first = last = None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                m = _TS.match(ln)
                if not m:
                    continue
                t = _secs(*m.groups())
                if first is None:
                    first = t
                elif t < last:
                    t += 86400
                last = t
    except OSError:
        return None
    return max(0, last - first) if first is not None and last is not None else None


def _unit_progress(path):
    """日志里**最后一条**「a/b」形态的阶段内进度 → (done, total, 原文)。

    流水线侧统一打了这几种：`批次进度 25/269`、`live2d 进度 3/4`、`进度 12/40 成功=…`、
    被调脚本自己的 `处理 1200/4488`。没有命中就返回 None ⇒ 界面只报阶段级进度，
    **不拿"上一次的值"假装还在动**。
    """
    hit = None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                if '进度' not in ln:
                    continue
                m = re.search(r'(\d+)\s*/\s*(\d+)', ln)
                if m and int(m.group(2)) > 0:
                    hit = (int(m.group(1)), int(m.group(2)), ln.strip()[-64:])
    except OSError:
        return None
    return hit


def _last_run():
    """最近一次**已结束**的任务 → {id, label, secs, red}。没在跑、也没跑过 ⇒ None。"""
    for r in reversed(load_runs()):
        if r.get('state') == 'running':
            continue
        return {'id': r.get('id'), 'label': r.get('label'),
                'secs': _log_secs(r.get('log') or ''),
                'clean': bool(r.get('clean'))}
    return None


def _terminal_pulse(path, cur_t):
    """终端任务的「还在推进」信号：输出行数 / 本阶段行数 / 最后一行 / 距上次输出秒数。

    很多阶段不打 a/b（背景导出、语音解码…），阶段级 2/9 会半天不动，看着像卡死。
    这里改拿**子进程真实写出的日志**当推进源：行数单调增，前端用它驱动水道，
    并把最后一行原文摆出来，让用户看见终端在动。"""
    lines = stage_lines = 0
    last = ''
    last_t = None
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                s = ln.strip()
                if not s:
                    continue
                lines += 1
                m = _TS.match(ln)
                if m:
                    t = _secs(*m.groups())
                    if last_t is not None and t < last_t:
                        t += 86400
                    last_t = t
                    if cur_t is None or t >= cur_t:
                        stage_lines += 1
                last = s
    except OSError:
        pass
    try:
        age = round(max(0.0, time.time() - os.path.getmtime(path)), 1)
        size = os.path.getsize(path)
    except OSError:
        age, size = None, 0
    disp = re.sub(r'^\[\d\d:\d\d:\d\d\]\s*', '', last)[:140]
    return {'log_lines': lines, 'stage_lines': stage_lines, 'last_line': disp,
            'last_age': age, 'log_bytes': size}


def gauge_safe(run, stages, fp=None):
    """在跑 → 进度台的数据；刚跑完 → 一条**静态收尾条**；没跑过 → None。"""
    if not run:
        return None
    try:
        t0 = time.mktime(time.strptime(run.get('started', ''), '%Y-%m-%d %H:%M:%S'))
    except Exception:
        t0 = None
    elapsed = max(0.0, time.time() - t0) if t0 else None

    log = run.get('log') or ''
    cur, cur_t, done, skipped = _progress_from_log(log)
    scope = _scope_keys(run.get('argv') or [], stages)
    mem_mb, nproc = _tree_mem_mb(run.get('pid') or 0)

    eta, missing, known, srcs = None, 0, 0, {}
    means = _cached('means', 60.0, _stage_means) or {}
    units = _scope_units(fp)
    bykey = {s['key']: s for s in stages}

    def est_sec(k):
        """一个阶段的预计秒数 + 它是**怎么来的**（历史均值 / 实测速率×项数 / 实测常量）。"""
        if k in means:
            return means[k], 'hist'
        s = bykey.get(k) or {}
        if s.get('rate') and units.get(k):
            return s['rate'] * units[k], 'rate'
        if s.get('est'):
            return s['est'], 'est'
        return None, None

    if scope:
        first_t = next((t for _, t, _ in _stage_spans(log)), None)
        cur_el = 0.0
        if cur and cur_t is not None and first_t is not None and elapsed is not None:
            cur_el = max(0.0, elapsed - (cur_t - first_t))
        rest = [k for k in scope if k not in done and k not in skipped and k != cur]
        total_s = 0.0
        for k in rest:
            e, src = est_sec(k)
            if e is None:
                missing += 1
            else:
                total_s += e
                known += 1
                srcs[src] = srcs.get(src, 0) + 1
        if cur:
            e, src = est_sec(cur)
            if e is None:
                missing += 1
            else:
                total_s += max(0.0, e - cur_el)
                known += 1
                srcs[src] = srcs.get(src, 0) + 1
        if known:
            eta = total_s

    title = next((s['title'] for s in stages if s['key'] == cur), '')
    up_ = _unit_progress(log) if log else None
    return {'t0': t0, 'elapsed': elapsed, 'mem_mb': round(mem_mb, 1), 'nproc': nproc,
            'stage': cur, 'stage_title': title, 'done': len(done | skipped),
            'total': len(scope), 'skipped': len(skipped),
            'eta': None if eta is None else round(eta), 'eta_missing': missing,
            'eta_n': known, 'eta_src': srcs, 'samples': len(means),
            # 阶段内进度：日志里没有 a/b 就返回 None，界面只报阶段级，不拿旧值假装在动。
            'unit_done': (up_ or (None, None, ''))[0], 'unit_total': (up_ or (None, None, ''))[1],
            'unit_src': (up_ or (None, None, ''))[2], 'scope_keys': scope,
            # 分段条要按"哪几段已完成/已跳过"上色，光给个计数画不出真状态
            'done_keys': sorted(done), 'skipped_keys': sorted(skipped),
            # 本轮用时：跑完之后进度台按契约收起（静止帧判据在守），
            # 所以"这轮跑了多久"改由主屏那句话带出来，数据源是同一条日志的首末时间戳。
            'secs': _log_secs(log),
            # 终端推进信号：没有 a/b 的阶段靠它让水道继续走，并摆出最后一行日志。
            **_terminal_pulse(log, cur_t)}



# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        raw = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ('/', '/index.html'):
            # `/?asbuild=xxx` 下发一份"内联 build 被改掉"的页面 —— 探针据此模拟
            # 长驻旧标签页，验证它会自己刷到最新版（真实路径，不必手改内存变量）。
            asb = q.get('asbuild')
            return self._send(200, page_html(asb), 'text/html; charset=utf-8')
        if u.path == '/api/state':
            refresh_states()
            err = ''
            try:
                stages, steps = stage_keys()
            except Exception as e:
                stages, steps = [], {}
                err = str(e)
            state = {}
            try:
                raw = load_state_retry()
                # 外层闸只比"源包数"：换了一批包是"不该认任何旧结论"的大事件；
                # `deps=` 是本管线 deps 阶段的产物，不能拿它整块清空（2026-10-23）。
                # 配置表/依赖表变化该作废哪些阶段，交给下面的逐阶段指纹判。
                if bundles_of_fp(raw.get('fingerprint')) == bundles_of_fp(fingerprint_safe()):
                    # done=跳过缓存（只有暂存判绿档），verdict=上次结论（13 档全记）。
                    # 两个都要，且**指纹不同就一个都不读** —— 拿旧更新包的结论给这次的界面涂绿，
                    # 正是这条流水线最怕的那类假绿灯。
                    sc_now = scope_stamp_safe()
                    # ⚠️ 第二道章不是"整条指纹相等"，而是**逐阶段比**（§157）：
                    #   `cfg.*` 四个阶段用不含 `cfg=` 的指纹（它们的工作就是改写配置表，
                    #   拿自己的产物判过期会变成永动机）；其余阶段用全指纹。
                    #   只看整条相等会把「配置表刚刷新、下游该重跑」和「全都没变」混为一谈。
                    # ⚠️ 指纹**只算一次**（两条），不能每条 state 各 walk 一遍 9 万文件。
                    pair = fp_pair_safe()
                    prod = {s['key']: s.get('produces_cfg') for s in stages}
                    def _fp_ok(k, v):
                        want = (pair or {}).get('nocfg' if prod.get(k) else 'full')
                        return v.get('fingerprint') == (want or fingerprint_safe())
                    # done（跳过缓存）同样要认范围章：清单换过之后那条"已完成"就是假的
                    state = {k: v for k, v in (raw.get('done') or {}).items()
                             if v.get('scope') == sc_now and _fp_ok(k, v)}
                    # verdict 还要过第二道章：**范围清单的身份**。清单换过（被冲空又复原也算），
                    # 上一批跑出来的"本次增量没有立绘源包 ⇒ 跳过"就不是这轮的结论。
                    for k, v in (raw.get('verdict') or {}).items():
                        if v.get('scope') == sc_now and _fp_ok(k, v):
                            state[k] = v
            except Exception as e:
                # ⚠️ 以前这里是 `except Exception: pass` —— 于是任何一处小错（哪怕
                # 一个 KeyError）都让**整块结论静默变成空**，界面显示"全都未跑"，
                # 而用户看到的是"我的进度没了"却查不出原因（2026-10-17 23:35 实测）。
                # 失败要**说出来**：把它挂到 error 字段上，界面会显示这一行。
                print(f'[警告] 读阶段结论失败：{type(e).__name__}: {e}')
                err = f'读阶段结论失败：{type(e).__name__}: {e}'
            sheets = []
            for p in glob_sheets():
                sheets.append({'name': os.path.basename(p),
                               'kb': round(os.path.getsize(p) / 1024),
                               'mt': time.strftime('%m-%d %H:%M', time.localtime(
                                   os.path.getmtime(p)))})
            run = running_job()
            return self._send(200, {
                'stages': stages, 'steps': steps, 'state': state,
                'runs': load_runs()[-12:][::-1],
                'running': run, 'error': err, 'sheets': sheets,
                # 已发布皮肤表 vs 本轮解析产物：差几行（发布早于解析时会 > 0）。
                # 2026-10-17 §155：发布跑在解析刷新之前 ⇒ 新皮肤无名、语音档位派不出，
                # 而阶段结论全是绿的（缓存）——这个差就是唯一会说真话的信号。
                'skin_gap': skin_table_gap(),
                # 页面版本戳：旧标签页拿它和内联的 __BUILD__ 比，不等就自己 reload
                # （no-store 治不了"页面比服务旧"——见 §156）。
                'build': BUILD,
                # 最近一次**已结束**的任务用了多久：进度台按契约跑完就收起（静止帧判据），
                # 所以"这轮跑了多久 / 停在哪"要由主屏那句话带出来。
                'last': _last_run(),
                'news': newsafe(),
                # 一次 /api/state 只算**一遍**输入指纹（walk 9 万多个源包），往下传。
                # 以前各处各算，实测冷缓存那一拍要 5.8 秒 —— 前端轮询超时，看着就是进度不动。
                'fingerprint': (fp := ((fp_pair_safe() or {}).get('full')
                                       or fingerprint_safe())),
                'scope': scope_safe(fp),
                'gauge': gauge_safe(run, stages, fp),
            })
        if u.path == '/api/disk':
            # 盘面盘点：后台算、前端轮询。fresh=1 绕过 15 分钟缓存（「重新盘点」按钮用）。
            return self._send(200, disk_report(q.get('fresh') == '1'))
        if u.path == '/api/cleanup':
            return self._send(200, cleanup_list())
        if u.path == '/api/bg_review':
            return self._send(200, bg_review(q.get('fresh') == '1'))
        if u.path == '/api/bgchars/status':
            jid = q.get('job')
            return self._send(200, bg_publish_status(int(jid) if jid and jid.isdigit() else None))
        if u.path == '/bgimg':
            key = q.get('key', '')
            if '/' not in key:
                return self._send(400, {'error': 'key 必须是 <目录>/<名>'})
            d, name = key.split('/', 1)
            if not (re.fullmatch(r'[A-Za-z0-9_]+', d)
                    and re.fullmatch(r'[A-Za-z0-9_.-]+', name)):
                return self._send(403, {'error': '非法图名'})
            thumb = os.path.realpath(os.path.join(BG_THUMBS, d, name + '.webp'))
            raw = os.path.realpath(os.path.join(RAW_DIR, d, name + '.png'))
            base_t = os.path.realpath(BG_THUMBS) + os.sep
            base_r = os.path.realpath(RAW_DIR) + os.sep
            src, ctype = None, 'application/octet-stream'
            if q.get('full') != '1' and thumb.startswith(base_t) and os.path.isfile(thumb):
                src, ctype = thumb, 'image/webp'
            elif raw.startswith(base_r) and os.path.isfile(raw):
                src, ctype = raw, 'image/png'
            if not src:
                return self._send(404, {'error': '图不在盘上'})
            with open(src, 'rb') as f:
                return self._send(200, f.read(), ctype)
        if u.path == '/api/log':
            # 必须在这里也刷一次状态：前端追日志期间停掉了 8s 一次的 /api/state 轮询，
            # 只靠那边刷新的话，任务早就结束了面板还会一直显示「运行中」。
            refresh_states()
            rid = q.get('id', '')
            run = next((r for r in load_runs() if r['id'] == rid), None)
            if not run:
                return self._send(404, {'error': '没有这个任务'})
            off = int(q.get('offset', 0) or 0)
            try:
                with open(run['log'], 'rb') as f:
                    f.seek(off)
                    data = f.read(400_000)
            except OSError:
                data = b''
            return self._send(200, {'text': data.decode('utf-8', 'replace'),
                                    'offset': off + len(data),
                                    'state': run.get('state')})
        if u.path == '/file':
            p = os.path.realpath(os.path.join(WORK, unquote(q.get('path', ''))))
            if not p.startswith(os.path.realpath(WORK) + os.sep) or not os.path.isfile(p):
                return self._send(403, {'error': '只允许读 .diag/pipeline 下的文件'})
            with open(p, 'rb') as f:
                return self._send(200, f.read(),
                                  'image/png' if p.endswith('.png') else 'application/octet-stream')
        return self._send(404, {'error': 'not found'})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
        except Exception:
            return self._send(400, {'error': '不是合法 JSON'})
        if u.path == '/api/cleanup/run':
            rid, err = cleanup_run(str(body.get('target') or ''),
                                   str(body.get('confirm') or ''))
            if err:
                return self._send(400, {'error': err})
            return self._send(200, rid)
        if u.path == '/api/scan':
            # 重扫源包清单（重建 asset_manifest.json）。命令**写死在这里**，
            # 前端只发一个空 POST —— 白名单边界不因新增按钮而破。
            rid, err = start_job('重扫源包清单（scan_assets）', [], script='scripts/scan_assets.py')
            if err:
                return self._send(409, {'error': err})
            return self._send(200, {'id': rid})
        if u.path == '/api/bgchars':
            return self._send(200, bg_chars_save(body))
        if u.path == '/api/bgrootnames':
            return self._send(200, bg_roots_save(body))
        if u.path == '/api/newround':
            return self._send(200, new_round())
        if u.path != '/api/run':
            return self._send(404, {'error': 'not found'})
        valid = {s['key'] for s in stage_keys()[0]}
        only = [x for x in body.get('stages', []) if x in valid]
        if len(only) != len(body.get('stages', [])):
            return self._send(400, {'error': '含未知阶段名，拒绝'})
        approve = [x for x in body.get('approve', []) if x in valid]
        if len(approve) != len(body.get('approve', [])):
            return self._send(400, {'error': '含未知阶段名，拒绝'})
        argv = []
        label = '跑到待确认（不碰正式产物）'
        if body.get('plan'):
            argv, label = ['--plan'], '只看计划'
        else:
            if only:
                argv += ['--only', ','.join(only)]
                label = '单阶段：' + ','.join(only)
            if approve:
                argv += ['--approve'] + approve
                label += ' + 签字放行 ' + ','.join(approve)
            if body.get('full'):
                argv.append('--full')
                label += ' 【全量】'
            if body.get('force'):
                argv.append('--force')
                label += '（强制重跑）'
        if body.get('full'):
            return self._send(400, {'error': '全量重跑请以命令行方式执行 '
                                             'py -3 scripts/update_pipeline.py --full '
                                             '（它要手输 FULL 二次确认，网页上不做这个）'})
        rid, err = start_job(label, argv)
        if err:
            return self._send(409, {'error': err})
        return self._send(200, {'id': rid})


# ------------------------------------------------------------------ 盘面与清单
_DISK = {'state': 'idle', 'data': None, 'at': 0.0}
_DISK_TTL = 900.0        # 15 分钟：walk 18 万个文件约 1 分钟，别让轮询反复触发


def _disk_compute():
    """walk 四个关键目录 + 读两份清单状态。**只读**，不删不改任何东西。"""
    out = {}
    for label, p in (('ab', os.path.join(ROOT, 'files', 'AssetBundles')),
                     ('out', os.path.join(ROOT, 'Output')),
                     ('diag', os.path.join(ROOT, '.diag')),
                     ('inputs', os.path.join(ROOT, 'inputs'))):
        n = b = 0
        if os.path.isdir(p):
            for d, _, fs in os.walk(p):
                for f in fs:
                    n += 1
                    try:
                        b += os.path.getsize(os.path.join(d, f))
                    except OSError:
                        pass
        out[label] = {'files': n, 'bytes': b}
    # 源包清单的新鲜度：清单记录的文件数 vs 当场数出来的（§157 同一哲学：信实况）
    man = None
    mf = os.path.join(ROOT, 'asset_manifest.json')
    if os.path.isfile(mf):
        try:
            j = json.load(open(mf, encoding='utf-8'))
            man = {'total_files': (j.get('summary') or {}).get('total_files'),
                   'scanned': time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(mf)))}
        except Exception as e:
            man = {'error': f'{type(e).__name__}: {str(e)[:60]}'}
    if man and man.get('total_files') is not None:
        man['actual'] = out['ab']['files']
        man['fresh'] = (man['total_files'] == out['ab']['files'])
    st = None
    try:
        s = json.load(open(os.path.join(WORK, 'pipeline_state.json'), encoding='utf-8'))
        st = {'done': len(s.get('done') or {}), 'verdict': len(s.get('verdict') or {})}
    except Exception:
        pass
    return {'dirs': out, 'manifest': man, 'state': st,
            'at': time.strftime('%m-%d %H:%M')}


def disk_report(fresh=False):
    """盘面盘点：慢（walk 18 万文件），放后台线程算，前端轮询取结果。"""
    with _lock:
        if _DISK['state'] == 'computing':
            return {'status': 'computing'}
        if not fresh and _DISK['state'] == 'done' and time.time() - _DISK['at'] < _DISK_TTL:
            return {'status': 'ok', 'data': _DISK['data'],
                    'age': int(time.time() - _DISK['at'])}
        _DISK['state'] = 'computing'

    def work():
        try:
            data = _disk_compute()
            _DISK.update(state='done', data=data, at=time.time())
        except Exception as e:
            _DISK.update(state='error', data={'error': f'{type(e).__name__}: {str(e)[:80]}'},
                         at=time.time())
    threading.Thread(target=work, daemon=True).start()
    return {'status': 'computing'}


# ------------------------------------------------------------------ 清理中心
# 设计铁律：**能删什么由这张表决定**（key 写死在服务端，前端只传 key）；
# 每一项都标 safe —— unsafe 的必须 answer 原文 "DELETE" 才执行。
# 故意**不提供**的：源包 files/AssetBundles、inputs、Output 产物、
# .diag/sharecfg_re（cfg.publish 的解析源）、pipeline_state.json（阶段缓存）。
_CLEAN_TARGETS = [
    {'key': 'chrome_profiles', 'label': '浏览器调试配置',
     'desc': 'headless Chrome 的 user-data-dir（chrome_* / fav_profile_* / hovercost_profile_*），纯临时',
     'safe': True},
    {'key': 'panel_paper', 'label': '控制台截图区 .diag/panel_paper',
     'desc': '界面验收截图 + 探针浏览器配置，全部可再生', 'safe': True},
    {'key': 'ui_shots', 'label': 'UI 截图区 .diag/ui_shots',
     'desc': '同上（含 uishots 旧目录）', 'safe': True},
    {'key': 'pipeline_logs', 'label': '旧运行日志 .diag/pipeline/run_*.log',
     'desc': '保留最近 20 份，其余清掉', 'safe': True},
    {'key': 'old_bak', 'label': '换入备份 Output/_OLD_bak',
     'desc': '每次换入前的整批备份。⚠️ 清了就没有"一键回到换入前"；确认画廊显示正常再清。需手输 DELETE',
     'safe': False},
]
_CLEAN = {'running': None, 'last': None}
_KEEP_LOGS = 20


def _clean_paths(key):
    """把 target key 解析成**具体路径清单**。只认上表白名单里的 key。"""
    root = ROOT
    spec = next((t for t in _CLEAN_TARGETS if t['key'] == key), None)
    if not spec:
        return None
    paths = []
    if key == 'chrome_profiles':
        pats = ('chrome_', 'fav_profile_', 'hovercost_profile_', 'prof_')
        d = os.path.join(root, '.diag')
        if os.path.isdir(d):
            for e in os.scandir(d):
                if e.is_dir() and e.name.startswith(pats):
                    paths.append(e.path)
    elif key == 'panel_paper':
        paths.append(os.path.join(root, '.diag', 'panel_paper'))
    elif key == 'ui_shots':
        paths += [os.path.join(root, '.diag', 'ui_shots'),
                  os.path.join(root, '.diag', 'uishots')]
    elif key == 'pipeline_logs':
        logs = sorted(p for p in
                      glob.glob(os.path.join(root, '.diag', 'pipeline', 'run_*.log')))
        paths = logs[:-_KEEP_LOGS] if len(logs) > _KEEP_LOGS else []
    elif key == 'old_bak':
        paths.append(os.path.join(root, 'Output', '_OLD_bak'))
    return paths


def _clean_size(key):
    n = b = 0
    for p in (_clean_paths(key) or []):
        if os.path.isdir(p):
            for d, _, fs in os.walk(p):
                for f in fs:
                    n += 1
                    try:
                        b += os.path.getsize(os.path.join(d, f))
                    except OSError:
                        pass
        elif os.path.isfile(p):
            n, b = 1, os.path.getsize(p)
    return n, b


def cleanup_list(fresh=False):
    """清理中心账单：各目标的大小（缓存 5 分钟，walk 几万文件实测 12~16s）+ 上一次清理的结果。"""
    now = time.time()
    if fresh or not _CLEAN.get('sizes') or now - _CLEAN.get('sizes_at', 0) > 300:
        out = []
        for t in _CLEAN_TARGETS:
            n, b = _clean_size(t['key'])
            out.append({'key': t['key'], 'label': t['label'], 'desc': t['desc'],
                        'safe': t['safe'], 'files': n, 'bytes': b})
        _CLEAN['sizes'] = out
        _CLEAN['sizes_at'] = now
    return {'targets': _CLEAN['sizes'], 'last': _CLEAN.get('last'),
            'running': _CLEAN.get('running')}


def cleanup_run(key, confirm):
    """执行一项清理。白名单 + 二次确认（unsafe 项要求 answer 原文 DELETE）。"""
    spec = next((t for t in _CLEAN_TARGETS if t['key'] == key), None)
    if not spec:
        return None, '未知的清理目标（白名单拒绝）'
    if _CLEAN.get('running'):
        return None, '上一次清理还没跑完，等一下'
    if not spec['safe'] and confirm != 'DELETE':
        return None, '这一项要手动输入 DELETE 才会执行（删的是换入备份，不可恢复）'
    paths = _clean_paths(key) or []
    if not paths:
        return None, '没有可删的东西（可能已经清过了）'

    def work():
        n = b = 0
        errs = []
        import shutil
        for p in paths:
            try:
                if os.path.isdir(p):
                    for d, _, fs in os.walk(p):
                        for f in fs:
                            try:
                                b += os.path.getsize(os.path.join(d, f))
                                n += 1
                            except OSError:
                                pass
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.isfile(p):
                    b += os.path.getsize(p)
                    n += 1
                    os.remove(p)
            except Exception as e:
                errs.append(f'{os.path.basename(p)}: {type(e).__name__}')
        _DISK['state'] = 'idle'          # 盘点缓存作废，下次重新算
        _CLEAN['sizes'] = None           # 清理账单的尺寸也作废
        _CLEAN['last'] = {'key': key, 'label': spec['label'],
                          'files': n, 'bytes': b,
                          'at': time.strftime('%m-%d %H:%M'),
                          'errors': errs[:5]}
        _CLEAN['running'] = None
    _CLEAN['running'] = key
    threading.Thread(target=work, daemon=True).start()
    return {'started': key}, None


def skin_table_gap():
    """已发布皮肤表 vs 本轮解析产物，差几行（读不动返回 None，不挡主流程）。

    为什么需要它：`cfg.publish` 的结论是按指纹缓存的，发布跑在解析刷新之前时
    结论仍绿，但 `inputs/gamecfg/ship_skin_template.json` 里就是缺行
    （2026-10-17 实测：19:46 发布用 09-25 的 scalar，21:11 才刷新 ⇒ 少 6 行）。
    行数差是唯一不依赖缓存的真信号。
    """
    try:
        pub_p = os.path.join(ROOT, 'inputs', 'gamecfg', 'ship_skin_template.json')
        dev_p = os.path.join(ROOT, '.diag', 'sharecfg_re', 'cfg_json_scalar',
                             'ship_skin_template.json')
        if not os.path.isfile(pub_p) or not os.path.isfile(dev_p):
            return None
        pub = json.load(open(pub_p, encoding='utf-8'))
        dev = json.load(open(dev_p, encoding='utf-8'))
        gap = len(set(map(str, dev)) - set(map(str, pub)))
        if gap <= 0:
            return None
        lost = sorted(set(map(str, pub)) - set(map(str, dev)))
        sample = [dev[k].get('painting') for k in sorted(set(map(str, dev)) - set(map(str, pub)))
                  if isinstance(dev.get(k), dict)][:6]
        return {'pub': len(pub), 'dev': len(dev), 'gap': gap, 'lost': len(lost),
                'sample': [s for s in sample if s]}
    except Exception:
        return None


def newsafe():
    """这次更新**新增**了哪些皮肤（正式区之前没有的）+ 它们现在在不在、有没有语音、叫什么名。

    数据源是 review 落的 `new_paintings.txt` —— 没有"线上新增"这一档，就没有这个板块可言
    （§79 的根因正是它曾被并进"与线上不同"里，结果永远是 0）。
    """
    def calc():
        out = os.path.join(ROOT, 'Output')          # 面板侧没有 OUT，别照搬流水线那套名字
        lst = os.path.join(WORK, 'new_paintings.txt')
        if not os.path.isfile(lst):
            return {'rows': [], 'note': '还没跑过第 3 步的对照表 —— 它才算得出"哪些是新增"'}
        names = [x.strip() for x in open(lst, encoding='utf-8') if x.strip()]
        try:
            meta = json.load(open(os.path.join(out, 'ship_meta.json'), encoding='utf-8'))
        except Exception:
            meta = {}
        try:
            voice = json.load(open(os.path.join(out, 'gallery_v2', 'skin_voice.json'), encoding='utf-8'))
        except Exception:
            voice = {}
        rows = []
        for s in names:
            m = meta.get(s) or {}
            v = voice.get(s) or {}
            rows.append({'stem': s, 'base': m.get('base_painting') or s,
                         'ship': m.get('cn') or '', 'skin': m.get('skin_name') or '',
                         'faction': m.get('faction') or '', 'rarity': m.get('rarity') or '',
                         'voice': len(v.get('lines') or []), 'meta': bool(m),
                         'live': os.path.isfile(os.path.join(out, 'Paintings_v2', s + '.png'))})
        gkeys = {(r['base'], r['skin'] or r['ship'] or r['stem'],
                  r['ship'] or r['stem']) for r in rows}
        skins = len({(a, b) for a, b, c in gkeys if b and c and b != c})
        sheets = [x for x in ('sheet_paintings.png', 'sheet_paintings_bases.png')
                  if os.path.isfile(os.path.join(WORK, x))]
        return {'rows': rows,
                'live_n': sum(1 for r in rows if r['live']),
                'groups': len(gkeys), 'skins': skins,
                'sheet': sheets[0] if sheets else '', 'sheets': sheets}
    return _cached('news', 10.0, calc)


def glob_sheets():
    import glob
    ps = glob.glob(os.path.join(WORK, '*.png')) + glob.glob(os.path.join(WORK, '*.jpg'))
    # 最新生成的在最前：同一批可能有多张（sheet_1/2/…），旧的也不该排在前面。
    return sorted(ps, key=os.path.getmtime, reverse=True)


# 输入指纹要 os.walk 整个 files/AssetBundles（91,643 个文件，实测数秒）。
# 前端每 8s 轮询一次 /api/state，不缓存的话每次轮询都白扫一遍盘，首屏还会空着十几秒像死掉。
_CACHE = {'fp': [None, 0.0], 'scope': [None, 0.0], 'means': [None, 0.0], 'units': [None, 0.0],
           'scopetag': [None, 0.0], 'news': [None, 0.0]}


def _cached(slot, ttl, fn):
    # ⚠️ 这里原来写 `_CACHE[slot]` 直接取值，首次访问一个没见过的 slot 会 KeyError；
    #   而 `/api/state` 整块包在 `except Exception: pass` 里 ⇒ 一次 KeyError 就让
    #   **所有阶段结论静默变成空**（2026-10-17 23:35 实测：面板读到 0 条却毫无报错）。
    #   失败方向必须是"少缓存一次"，不是"整块读不出来"。用 .get 并补默认值。
    val, at = _CACHE.get(slot, (None, 0.0))
    now = time.time()
    if val is not None and now - at <= ttl:
        return val
    out = fn()
    if out is not None:          # 失败不缓存，下一拍就重试
        _CACHE[slot] = [out, now]
    return out


def fingerprint_safe():
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            return up.fingerprint()
        except Exception as e:
            print(f'[警告] 读输入指纹失败：{e}')
            return None
    return _cached('fp', 30.0, calc) or '(读不到：源包目录打不开？)'


def fp_pair_safe():
    """**一次**算两条指纹：全指纹 / 不含 `cfg=` 的指纹。

    §157 改成"逐阶段判缓存"之后，每个阶段要挑其中一条。旧版 `_fp_ok` 对
    **每个 key** 各调一次 `stage_fp_by_key_safe()` ⇒ 20 个阶段 = 20 次 walk 9 万
    文件，实测冷缓存 4.0 秒；而两条各算一次只要 0.39 秒（2026-10-21 实测）。
    这里整体缓存 30 秒，`/api/state` 里按阶段的 `produces_cfg` 挑一条用。
    """
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            return {'full': up.fingerprint(),
                    'nocfg': up.fingerprint(include_cfg=False)}
        except Exception as e:
            print(f'[警告] 读输入指纹失败：{e}')
            return None
    return _cached('fp_pair', 30.0, calc)


def bundles_of_fp(fp):
    """只取源包数那一半。外层闸用：deps 是本管线 `deps` 阶段自己换入的产物，
    拿它判"换了批输入"会把刚跑完的结论整块清掉（与 update_pipeline.bundles_of 同源）。"""
    parts = (fp or '').split(' ')
    return parts[0] if parts and parts[0].startswith('bundles=') else (fp or '')


def load_state_retry(tries=2, delay=0.15):
    """读阶段缓存。写端已改成原子替换，这里再兜一层：一次瞬时的半截 JSON
    不该变成"五步全 0"（2026-10-23 用户截图里 0/9 与 8/9 同屏就是这一类）。"""
    last = None
    for i in range(tries):
        try:
            with open(os.path.join(WORK, 'pipeline_state.json'), encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            last = e
            if i + 1 < tries:
                time.sleep(delay)
    raise last


def stage_fp_by_key_safe(key):
    """该阶段判缓存用的指纹（§157）。`cfg.*` 拿不含 `cfg=` 的那条，其余拿全的。

    读不到就返回 None，让调用方退回"整条指纹"这个保守判据。
    """
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            return up.stage_fp_by_key(key)
        except Exception:
            return None
    return _cached('stfp:' + key, 30.0, calc)


def scope_stamp_safe():
    """当前范围清单的身份（与 `update_pipeline.scope_stamp()` 同源）。读不到 ⇒ 'none'。"""
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            return up.scope_stamp()
        except Exception as e:
            print(f'[警告] 读范围清单身份失败：{e}')
            return None
    return _cached('scopetag', 20.0, calc) or 'none'


def scope_safe(fp=None):
    def calc():
        sys.path.insert(0, HERE)
        try:
            import update_pipeline as up
            t = up.affected_stems(False, fp)
            return None if t is None else len(t)
        except Exception as e:
            print(f'[警告] 读增量范围失败：{e}')
            return None
    return _cached('scope', 30.0, calc)


# 页面正本拆在 panel_page.html（原内联 PAGE 原样迁出）：PP.PAGE 属性与 BUILD 哈希口径不变，
# panel_ui_probe / check_page_js 都认这份。
PAGE = open(os.path.join(HERE, 'panel_page.html'), encoding='utf-8').read()


# ── 版本戳：让长驻标签页自己发现"服务已经重启过" ────────────────────────────
# 2026-10-17 22:45 用户看到的还是修复前的旧界面（右栏写"已跑完 05"、正文点名第 3 步
# 而按钮跳第 5 步）。响应头早就带 `Cache-Control: no-store`，所以**不是**浏览器缓存，
# 而是那个标签页从服务重启前就一直开着，从没重新加载过。
# ⇒ 光靠 no-store 治不了"页面比服务旧"。这里把 PAGE 的哈希同时下发（/api/state.build）
# 并内联进页面（__BUILD__）；两者不等时页面自己 reload，用户什么都不用做。
BUILD = hashlib.sha256(PAGE.encode('utf-8')).hexdigest()[:12]


def page_html(as_build=None):
    """把内联版本戳替换进页面。改 PAGE 的任何一处都会让 BUILD 变，从而触发旧页自刷新。

    `as_build` 只给探针用：下发一个"页面比服务旧"的版本，走的是和真实长驻标签页
    完全相同的代码路径。

    必须返回 **bytes**：`_send` 只对 bytes 走原样写出，str 会被 `json.dumps` —— 那会把整份
    HTML 变成一个带引号的 JSON 字符串，浏览器里只剩一堆 `\"`（2026-10-17 22:55 实测：
    页面全裸、无样式无脚本，截图上是一屏引号）。
    """
    return PAGE.replace('__BUILD__', as_build or BUILD).encode('utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=PORT)
    ap.add_argument('--no-open', action='store_true')
    a = ap.parse_args()

    class Server(ThreadingHTTPServer):
        allow_reuse_address = True            # 规避 TIME_WAIT 导致的绑定失败
        daemon_threads = True

        def handle_error(self, request, client_address):
            # 浏览器提前断开是常态（轮询/切页），默认实现会往 stderr 刷 traceback，
            # 而这正是把本地 dev server 楔成"半死"的那条路（见 docs/TROUBLESHOOTING.md §63）
            exc = sys.exc_info()[1]
            if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                                BrokenPipeError, TimeoutError)):
                return
            super().handle_error(request, client_address)

    # ⚠️ Windows 上 allow_reuse_address(=SO_REUSEADDR) 的语义和 POSIX 不同：
    #    它**允许两个进程绑同一个端口**，请求被随机分给其中一个 —— 于是会出现
    #    "两个控制台共用一个端口、各自看到的任务状态不一样"这种极难查的错。
    #    （本轮实测真的起了两个，靠数进程才发现。）所以绑之前先探一次端口。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.6)
        if probe.connect_ex(('127.0.0.1', a.port)) == 0:
            print(f'端口 {a.port} 上已经有一个控制台在跑了 —— 直接用它，别再起第二个。')
            print(f'  （若那个其实已经死了，换个端口：py -3 scripts/pipeline_panel.py --port 8790）')
            if not a.no_open:
                webbrowser.open(f'http://127.0.0.1:{a.port}/')
            return 0

    try:
        stage_keys()          # 起服务前先确认阶段清单读得出来，别到点按钮才炸
    except Exception as e:
        print(f'[错误] 读不到 update_pipeline 的阶段清单：{e}')
        return 1

    url = f'http://127.0.0.1:{a.port}/'
    print('=' * 60)
    print('  资产更新控制台')
    print('  地址:', url)
    print('  只绑 127.0.0.1；能跑的阶段由 update_pipeline 的白名单决定')
    print('  关闭本窗口即停止控制台（正在跑的流水线任务不会因此中断）')
    print('=' * 60)
    if not a.no_open:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    httpd = Server(('127.0.0.1', a.port), H)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止。')
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
