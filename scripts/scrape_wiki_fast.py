"""
碧蓝航线 Wiki 快速爬虫 - 并行获取舰船数据
"""

import requests
import json
import time
import os
import re
import concurrent.futures
from collections import defaultdict

WIKI_API = "https://wiki.biligame.com/blhx/api.php"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\WikiData"

HEADERS = {
    "User-Agent": "AzurLaneScraper/1.0 (Educational)",
}

FACTIONS = ["白鹰", "皇家", "重樱", "铁血", "东煌", "撒丁帝国", "北方联合", "自由鸢尾", "维希教廷", "郁金王国", "飓风"]


def api_request(params, retries=3):
    params["format"] = "json"
    for attempt in range(retries):
        try:
            resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return None


def get_all_ship_links():
    """从舰船图鉴页面获取所有舰船链接"""
    data = api_request({
        "action": "parse",
        "page": "舰船图鉴",
        "prop": "links",
    })
    if not data or "parse" not in data:
        return []

    links = data["parse"].get("links", [])
    ships = []
    skip = ["攻略", "公式", "数据", "列表", "活动", "装备", "章节", "地图",
            "建造", "退役", "换装", "掉落", "经验", "技能", "阵营", "生日",
            "考据", "原型舰", "命名", "型号", "日期", "打捞", "分类",
            "1-", "2-", "3-", "4-", "5-", "6-", "7-", "8-", "9-", "10-",
            "11-", "12-", "13-", "14-", "15-", "16-",
            "首页", "图鉴", "模拟", "定位", "筛选", "原型", "实装",
            "阵营方案", "战斗之星", "战争荣誉", "昵称术语", "船名对照",
            "绝版舰船", "改造舰船", "联动舰船", "舰船经验", "舰船定位",
            "技能列表", "打捞列表", "舰船介绍", "建造时间"]
    for link in links:
        title = link.get("*", "")
        ns = link.get("ns", 0)
        if ns == 0 and title:
            if not any(w in title for w in skip):
                ships.append(title)
    return ships


def extract_field(html, pattern):
    match = re.search(pattern, html)
    return match.group(1).strip() if match else ""


def parse_ship(html, name):
    ship = {
        "name": name,
        "ship_type": extract_field(html, r'id="PNshiptype"[^>]*>([^<]+)'),
        "rarity": extract_field(html, r'id="PNrarity"[^>]*>([^<]+)'),
        "faction": "",
    }

    # 阵营 - 从分类链接提取
    camp_match = re.search(r'分类:阵营:([^"]+)"', html)
    if camp_match:
        ship["faction"] = camp_match.group(1)
    else:
        for camp in FACTIONS:
            if f">{camp}</a>" in html or f">{camp}\n" in html:
                ship["faction"] = camp
                break

    if not ship["faction"]:
        camp_patterns = [
            r'class="[^"]*faction[^"]*"[^>]*>([^<]+)',
            r'data-faction="([^"]+)"',
        ]
        for pat in camp_patterns:
            m = re.search(pat, html)
            if m:
                ship["faction"] = m.group(1)
                break

    return ship


def scrape_single_ship(name):
    """爬取单个舰船数据"""
    try:
        data = api_request({
            "action": "parse",
            "page": name,
            "prop": "text",
        })
        if data and "parse" in data:
            html = data["parse"].get("text", {}).get("*", "")
            if html:
                ship = parse_ship(html, name)
                if ship["ship_type"]:
                    return ship
                else:
                    return None, name
            else:
                return None, name
        else:
            return None, name
    except Exception as e:
        return None, name


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("碧蓝航线 Wiki 快速爬虫 (并行版)")
    print("=" * 60)

    # 获取舰船列表
    print("\n正在获取舰船列表...")
    ship_list = get_all_ship_links()
    print(f"找到 {len(ship_list)} 个舰船页面\n")

    if not ship_list:
        print("未找到舰船列表！")
        return

    # 并行爬取
    print(f"开始爬取舰船数据 (8线程并行)...")
    start_time = time.time()

    all_ships = []
    failed = []
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_name = {executor.submit(scrape_single_ship, name): name for name in ship_list}

        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            completed += 1

            if completed % 50 == 0:
                print(f"  进度: {completed}/{len(ship_list)} ({completed * 100 // len(ship_list)}%)")

            result = future.result()
            if isinstance(result, dict):
                all_ships.append(result)
            else:
                failed.append(name)

    elapsed = time.time() - start_time

    # 保存
    output = os.path.join(OUTPUT_DIR, "ship_data.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_ships, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完成! 用时: {elapsed:.1f}秒")
    print(f"成功: {len(all_ships)}, 失败/跳过: {len(failed)}")
    print(f"保存到: {output}")

    # 统计
    factions = defaultdict(int)
    types = defaultdict(int)
    for s in all_ships:
        factions[s.get("faction", "未知")] += 1
        types[s.get("ship_type", "未知")] += 1

    print(f"\n阵营分布:")
    for f, c in sorted(factions.items(), key=lambda x: -x[1]):
        print(f"  {f}: {c}")

    print(f"\n舰种分布:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    if failed:
        print(f"\n失败列表 (前10): {failed[:10]}...")


if __name__ == "__main__":
    main()
