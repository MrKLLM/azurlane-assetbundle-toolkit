# -*- coding: utf-8 -*-
"""皮肤表的唯一读取口：社区快照 `inputs/azdata/` 与设备侧权威表 `inputs/gamecfg/` 合并。

为什么是"合并"而不是"整表替换"：
  · 设备那份是从游戏本体 sharecfgdata 解出的（比社区快照新：已含 `aierdeliqi_9`=金月桂香、
    `mile_3`=幽幽桥上，坏坏来袭！ 两行，快照里没有），但它的清洗只保留标量字段，
    快照里的嵌套字段（`bound_bone`/`fx_container` 等）它没有 ⇒ 整行替换会让读这些字段的
    消费方静默拿到 None。⇒ **逐字段合并**：设备侧覆盖它有的字段，快照补齐其余。
  · 快照历史上也出现过"快照有、设备没有"的行 ⇒ 合并后必须**一条都不少**，写进断言。

设备表缺席时（换机器 / 还没跑 `42_publish_gamecfg.py`）自动退回纯快照，不报错 ——
失效方向是"少两行新皮肤"，不是"整条线跑不动"。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
AZDATA = os.path.join(ROOT, 'inputs', 'azdata')
DEV_FILE = os.path.join(ROOT, 'inputs', 'gamecfg', 'ship_skin_template.json')
AZ_FILE = os.path.join(AZDATA, 'azdata_ship_skin_template.json')


def load(verbose=False):
    az = json.load(open(AZ_FILE, encoding='utf-8'))
    if not os.path.isfile(DEV_FILE):
        if verbose:
            print(f'皮肤表：只用 azdata 快照 {len(az)} 行（设备侧表不在：{DEV_FILE}）')
        return az
    dv = json.load(open(DEV_FILE, encoding='utf-8'))
    out = dict(az)
    gained = renamed = 0
    for k, r in dv.items():
        base = out.get(k)
        if not isinstance(base, dict):
            gained += 1
            out[k] = dict(r)
            continue
        nm_new = str(r.get('name') or '').strip()
        nm_old = str(base.get('name') or '').strip()
        if nm_new and nm_new != nm_old:
            renamed += 1
        for f, v in r.items():
            base[f] = v
    lost = [k for k in az if k not in out]
    assert not lost, f'皮肤表合并不得丢行：丢了 {len(lost)} 行，例如 {lost[:3]}'
    if verbose:
        print(f'皮肤表：azdata {len(az)} 行 + 设备侧 {len(dv)} 行 → {len(out)} 行'
              f'（新增 {gained}、改名 {renamed}、丢行 0）')
    return out


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    d = load(verbose=True)
    for t in ('aierdeliqi_9', 'mile_3', 'xinnong_h'):
        hit = [(k, v.get('name')) for k, v in d.items()
               if isinstance(v, dict) and str(v.get('painting') or '').lower() == t]
        print(f'  {t:<16} {hit or "表里没有这一行"}')
