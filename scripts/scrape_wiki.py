"""
碧蓝航线 Wiki 爬虫 v2 - 使用正则提取数据
"""

import requests
import json
import time
import os
import re

WIKI_API = "https://wiki.biligame.com/blhx/api.php"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\WikiData"
RATE_LIMIT = 1.0

HEADERS = {
    "User-Agent": "AzurLaneScraper/1.0 (Educational)",
}


def api_request(params, retries=3):
    params["format"] = "json"
    for attempt in range(retries):
        try:
            resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            time.sleep(RATE_LIMIT)
            return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return None


def get_ship_links():
    """从舰船图鉴页面获取舰船链接列表"""
    data = api_request({
        "action": "parse",
        "page": "舰船图鉴",
        "prop": "links",
    })
    if not data or "parse" not in data:
        return []
    
    links = data["parse"].get("links", [])
    ships = []
    for link in links:
        title = link.get("*", "")
        ns = link.get("ns", 0)
        if ns == 0 and title:
            skip = ["攻略", "公式", "数据", "列表", "活动", "装备", "章节", "地图",
                     "建造", "退役", "换装", "掉落", "经验", "技能", "阵营", "生日",
                     "考据", "原型舰", "命名", "型号", "日期", "打捞", "分类",
                     "1-", "2-", "3-", "4-", "5-", "6-", "7-", "8-", "9-", "10-",
                     "11-", "12-", "13-", "14-", "15-", "16-"]
            if not any(w in title for w in skip):
                ships.append(title)
    return ships


def extract_field(html, pattern):
    """用正则从 HTML 提取字段"""
    match = re.search(pattern, html)
    return match.group(1).strip() if match else ""


def parse_ship(html, name):
    """从 HTML 解析舰船数据"""
    ship = {
        "name": name,
        "number": extract_field(html, r'id="PNN"[^>]*>([^<]+)'),
        "ship_type": extract_field(html, r'id="PNshiptype"[^>]*>([^<]+)'),
        "rarity": extract_field(html, r'id="PNrarity"[^>]*>([^<]+)'),
        "faction": "",
        "cv_jp": "",
        "cv_cn": "",
        "illustrator": "",
        "release_date": "",
        "build_time": "",
    }
    
    # 阵营 - 从链接 title 提取
    camp_match = re.search(r'分类:阵营:([^"]+)"', html)
    if camp_match:
        ship["faction"] = camp_match.group(1)
    else:
        for camp in ["白鹰", "皇家", "重樱", "铁血", "东煌", "撒丁帝国", "北方联合", "自由鸢尾", "维希教廷", "郁金王国"]:
            if f">{camp}</a>" in html or f">{camp}\n" in html:
                ship["faction"] = camp
                break
    
    # CV - 从 CV 表格提取
    cv_section = re.search(r'<b>CV</b>.*?<td[^>]*>([^<]+)', html, re.DOTALL)
    if cv_section:
        cv_text = cv_section.group(1).strip()
        # 提取日文 CV 名
        cv_jp = re.search(r'([^\s/]+)\s*/\s*[^\s/]+\s*/\s*([^\s/]+)', cv_text)
        if cv_jp:
            ship["cv_jp"] = cv_jp.group(1)
        else:
            ship["cv_jp"] = cv_text.split("/")[0].strip()
    
    # 画师
    artist_match = re.search(r'<b>画师</b>.*?<td[^>]*>([^<]+)', html, re.DOTALL)
    if artist_match:
        ship["illustrator"] = artist_match.group(1).strip()
    
    # 实装日期
    date_match = re.search(r'实装.*?日期.*?<td[^>]*>(\d{4}年\d{2}月\d{2}日)', html, re.DOTALL)
    if date_match:
        ship["release_date"] = date_match.group(1)
    
    # 建造时间
    time_match = re.search(r'建造.*?时间.*?<td[^>]*>.*?(\d{2}:\d{2}:\d{2}[^<]*)', html, re.DOTALL)
    if time_match:
        ship["build_time"] = time_match.group(1).strip()
    
    return ship


def scrape_ship(name):
    data = api_request({
        "action": "parse",
        "page": name,
        "prop": "text",
    })
    if not data or "parse" not in data:
        return None
    html = data["parse"].get("text", {}).get("*", "")
    if not html:
        return None
    return parse_ship(html, name)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("正在获取舰船列表...")
    ship_list = get_ship_links()
    print(f"找到 {len(ship_list)} 个舰船页面\n")
    
    all_ships = []
    failed = []
    
    for i, name in enumerate(ship_list):
        print(f"[{i+1}/{len(ship_list)}] {name}", end=" → ")
        ship = scrape_ship(name)
        if ship and ship["ship_type"]:
            all_ships.append(ship)
            print(f"{ship['faction']} {ship['ship_type']} CV:{ship['cv_jp']}")
        else:
            failed.append(name)
            print("SKIP")
    
    # 保存
    output = os.path.join(OUTPUT_DIR, "ship_data.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_ships, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"成功: {len(all_ships)}, 失败/跳过: {len(failed)}")
    print(f"保存到: {output}")
    
    # 统计
    factions = {}
    types = {}
    cv_count = 0
    for s in all_ships:
        f = s.get("faction", "?")
        t = s.get("ship_type", "?")
        factions[f] = factions.get(f, 0) + 1
        types[t] = types.get(t, 0) + 1
        if s.get("cv_jp"):
            cv_count += 1
    
    print(f"\n阵营: {dict(sorted(factions.items(), key=lambda x: -x[1]))}")
    print(f"舰种: {dict(sorted(types.items(), key=lambda x: -x[1]))}")
    print(f"有CV信息: {cv_count}/{len(all_ships)}")


if __name__ == "__main__":
    main()
