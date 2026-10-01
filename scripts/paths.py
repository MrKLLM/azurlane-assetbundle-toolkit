# -*- coding: utf-8 -*-
"""全项目唯一的路径出口：仓库根 + 外部工具位置，**换电脑/换用户名不用改代码**。

以前 21 个脚本把 `D:\\Azur Lane Assets` 和 `C:\\Users\\KLLM\\...` 写死在源码里，
其中 13 阶段调用链上 9 个 —— 换盘符或换用户名不是"迁移困难"，是**必炸**：
`mumu_sync` 会把包拉到错误的目录、diff 会拿错根（然后报"全部新增"，白下一遍 28.9GB）。

优先级（从高到低）：
  1. 环境变量 `AL_ASSETS_ROOT` —— 明确指定仓库根；
  2. 由本文件位置推导（`scripts/paths.py` 的上一级就是根）—— 双击 .bat、任何 cwd 都对；
  3. 都没有 ⇒ 抛错，**不猜、不用旧默认值**（猜错的代价是把资产写进别人的目录）。

外部工具同理：`AL_VGMSTREAM` / `AL_FFMPEG` / `AL_CHROME` 优先，其次 PATH，其次已知安装位置。
判据：`py -3 scripts/diag/check_paths.py`（不许再有脚本里出现写死的盘符）。
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _root_from_env():
    v = (os.environ.get('AL_ASSETS_ROOT') or '').strip().strip('"')
    if not v:
        return None
    p = os.path.abspath(os.path.expanduser(v))
    if not os.path.isdir(p):
        raise RuntimeError(f'AL_ASSETS_ROOT 指向的目录不存在：{p}')
    return p


ROOT = _root_from_env() or os.path.dirname(HERE)
if not os.path.isdir(os.path.join(ROOT, 'scripts')):
    raise RuntimeError(f'推导出的仓库根不像本项目（下面没有 scripts/）：{ROOT}\n'
                       f'    正常应当是含 scripts/、files/、Output/ 的那个目录；'
                       f'要手工指定就设环境变量 AL_ASSETS_ROOT')

FILES = os.path.join(ROOT, 'files')
AB = os.path.join(FILES, 'AssetBundles')          # 源包根
OUT = os.path.join(ROOT, 'Output')                # 正式产物根
DOCS = os.path.join(ROOT, 'docs')
WORK = os.path.join(ROOT, '.diag', 'pipeline')    # 编排器唯一的落盘区

# 派生产物里被到处引用的那几个
DEP_BUNDLE = os.path.join(AB, 'dependencies')
MANIFEST_PATH = os.path.join(OUT, 'dependency_manifest.json')
SHIP_META = os.path.join(OUT, 'ship_meta.json')
PAINT_OUT = os.path.join(OUT, 'Paintings_v2')
SPINE_OUT = os.path.join(OUT, 'Spine_v2')
LIVE2D_OUT = os.path.join(OUT, 'Live2D')
CG_OUT = os.path.join(OUT, 'CG_v2')
AUDIO_OUT = os.path.join(OUT, 'Audio')
GALLERY_OUT = os.path.join(OUT, 'gallery_v2')
ERRORS_LOG = os.path.join(DOCS, 'ERRORS.log')
LIVE2D_SRC = os.path.join(AB, 'live2d')      # 源包侧（产物侧是 LIVE2D_OUT）


def tool(env_var, which_name, *candidates):
    """外部可执行文件：env 优先 → PATH → 已知安装位置。都找不到返回 ''（调用方自己判红）。"""
    v = (os.environ.get(env_var) or '').strip().strip('"')
    if v:
        return v if os.path.isfile(v) else ''
    found = shutil.which(which_name)
    if found:
        return found
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return ''


_USER = os.path.expanduser('~')
VGMSTREAM = tool('AL_VGMSTREAM', 'vgmstream-cli',
                 os.path.join(_USER, 'AppData', 'Local', 'vgmstream', 'vgmstream-cli.exe'))
FFMPEG = tool('AL_FFMPEG', 'ffmpeg',
              os.path.join(_USER, 'AppData', 'Local', 'ffmpeg', 'ffmpeg.exe'),
              os.path.join(_USER, 'AppData', 'Local', 'Microsoft', 'WinGet', 'Links', 'ffmpeg.exe'))
MUMU_ADB_CANDIDATES = [
    'C:' + os.sep + 'Program Files' + os.sep + 'Netease' + os.sep + 'MuMu' + os.sep + 'nx_main' + os.sep + 'adb.exe',
    'C:' + os.sep + 'Program Files' + os.sep + 'Netease' + os.sep + 'MuMuPlayer' + os.sep + 'nx_main' + os.sep + 'adb.exe',
]
MUMU_ADB = tool('AL_ADB', 'adb', *MUMU_ADB_CANDIDATES) or next(
    (p for p in MUMU_ADB_CANDIDATES if os.path.isfile(p)), '')
MUMU_MANAGER = (os.path.join(os.path.dirname(MUMU_ADB), 'MuMuManager.exe')
                if MUMU_ADB else '')
CHROME = tool('AL_CHROME', 'chrome',
              r'C:\Program Files\Google\Chrome\Application\chrome.exe',
              r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe')


def rel(p):
    """给日志/界面看的短路径（不在根下面时原样返回，别抛）。"""
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:              # 跨盘符时 relpath 会抛，这里只影响显示
        return p


def report():
    return {'root': ROOT, 'ab_exists': os.path.isdir(AB), 'out_exists': os.path.isdir(OUT),
            'vgmstream': VGMSTREAM, 'ffmpeg': FFMPEG, 'chrome': CHROME,
            'from_env': bool(os.environ.get('AL_ASSETS_ROOT'))}


if __name__ == '__main__':
    import json
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(json.dumps(report(), ensure_ascii=False, indent=1))
