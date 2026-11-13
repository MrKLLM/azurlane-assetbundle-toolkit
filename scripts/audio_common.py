# -*- coding: utf-8 -*-
"""ACB 解码 + ogg 转码的唯一实现（extract_cv_voice / extract_live2d_voice 共用）。

两调用方的历史差异（解码超时、报错文案与截断长度）做成参数，默认值 = CV 侧口径；
L2D 侧传 timeout=600 / empty_msg='vgmstream 未解出任何流' / detail=200。
"""
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P

OPUS_BITRATE = '48k'


def decode_acb(acb, tmp, *, timeout=900, empty_msg='vgmstream 未解出流', detail=160):
    """一个语音包 → {cue 名: wav 路径}（一次 vgmstream 调用取全部流）。"""
    src = os.path.join(tmp, 'in.acb')
    out = os.path.join(tmp, 'wav')
    os.makedirs(out, exist_ok=True)
    shutil.copy2(acb, src)
    r = subprocess.run([P.VGMSTREAM, '-i', '-S', '0', '-o', os.path.join(out, '?n.wav'), src],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    files = glob.glob(os.path.join(out, '*.wav'))
    if not files:
        raise RuntimeError('%s (rc=%s) %s' % (empty_msg, r.returncode, (r.stderr or '')[:detail]))
    return {os.path.splitext(os.path.basename(f))[0]: f for f in files}


def to_ogg(wav, dst, *, detail=160):
    """wav → 48k opus；产物 <1KB 判转码失败（两调用方原口径）。"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    r = subprocess.run([P.FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', wav,
                        '-c:a', 'libopus', '-b:a', OPUS_BITRATE, dst],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    if not os.path.exists(dst) or os.path.getsize(dst) < 1024:
        raise RuntimeError('ffmpeg 转码失败 %s: %s' % (wav, (r.stderr or '')[:detail]))