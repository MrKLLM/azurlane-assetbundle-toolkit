# -*- coding: utf-8 -*-
"""无头 Chrome 的 CDP 端口与 user-data-dir：并发会话之间绝不共用同一个。

为什么必须动态（这条不是"整洁"，是**假数据**的来源）：`--user-data-dir` 相同的第二个 chrome
**不会另起进程，而是附着到第一个**，于是两个会话的 CDP 命令灌进同一个页面；端口写死同理，
第二个会话连上的是别人的浏览器。症状都不是报错，而是"整条序列统一偏移一位"这种**看起来很像
真结果**的假数据（2026-09-27 `hit_verify` 报出 WIRING=38、每条 played 恰好滞后一个部位，
就是这么来的，见 PROJECT_STATUS §6 第 19/20 条）。

出口（探针一律走这里，别在自己文件里写死数字）：
    PORT, PROFILE = cdp_slot.slot(ROOT, 'hitv')
- 端口：默认让 OS 挑一个真空闲端口；`AL_CDP_PORT` 可钉死（用于复现某一次运行），
  但该端口若已被占用就**直接退出**，绝不静默附着到别人的浏览器。
- profile：`.diag/chrome_<tag>_<pid>`，每个进程一份。按 `chrome_*` 前缀能被
  `clean_diag_profiles.py` 清掉（每份几百 MB，跑完记得清）。`AL_CDP_PROFILE_DIR` 换落点。
"""
import os
import socket
import sys

# 本模块的报错走 SystemExit → **stderr**。GBK 控制台下中文会被编成 GBK，
# 抓输出的调用方按 UTF-8 解码直接崩（§9.3 根因 3 的同一族，只是这次崩的是"闸门拒绝启动"那句话）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

DEFAULT_BASE = '.diag'


def _in_use(port, host='127.0.0.1'):
    s = socket.socket()
    s.settimeout(0.2)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def _free_port():
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
    finally:
        s.close()


def port(tag=''):
    """一个确定没人占的 CDP 端口。设了 `AL_CDP_PORT` 就必须是空闲的，否则退出。"""
    env = (os.environ.get('AL_CDP_PORT') or '').strip()
    if env:
        p = int(env)
        if _in_use(p):
            raise SystemExit(
                'AL_CDP_PORT=%d 已被占用（探针 %s）——那通常是**另一个会话**的调试端口。\n'
                '  要么去掉这个环境变量让它自己挑一个，要么换一个空闲端口；\n'
                '  不能继续：端口撞了不会报错，只会把两个会话的命令灌进同一个页面，'
                '产出"整序列统一偏移一位"的假数据。' % (p, tag or '?'))
        return p
    for _ in range(30):
        p = _free_port()
        if not _in_use(p):
            return p
    raise SystemExit('挑不到空闲的 CDP 端口（本机端口可能被占满）')


def profile(root, tag):
    """本进程专属的 user-data-dir。**不能**按脚本名共用一份：那样第二个 chrome 会附着第一个。"""
    base = (os.environ.get('AL_CDP_PROFILE_DIR') or '').strip() or os.path.join(root, DEFAULT_BASE)
    d = os.path.join(base, 'chrome_%s_%d' % (tag or 'probe', os.getpid()))
    os.makedirs(d, exist_ok=True)
    return d


def slot(root, tag):
    p, d = port(tag), profile(root, tag)
    print('[cdp] %s → 端口 %d · profile %s' % (tag or 'probe', p, os.path.relpath(d, root)))
    return p, d
