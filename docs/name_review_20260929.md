# 55 组显示名待勾表（2026-09-29，未决）

背景：§6 第 2 条原记「112 组显示手抄表名、换配置优先会影响 112 张卡」。逐组实测后：

- 84 组两个名字都有且不同；
- 其中 **49 组配置名属于另一个实体**（同组的 META 形态，如 `gangute`→`甘古特·META`），由「改名不得让阵营/舰种/稀有度变空」这条零回退不变式自动挡下，**不在本表**；
- 4 组配置名是占位垃圾（`▅海▊▇洛▅■芬特▇▆`、`？？？`、`ladyE`），由「像不像真名」判据挡下，**不在本表**；
- 剩下 **55 组** = 本表：45 组真换名 + 10 组仅去首尾空白。

## 结论（2026-09-29 18:30 已换入）

用户看过本表后答复「**全勾**」。已换入线上索引：

- 实际变化 **64 组** = 45 真换名 + 10 去尾空格 + 9 占位符回落到组键
  （`？？？`/`？？？？？`/`544845544F574552` 这类此前**直接印在卡片上**，现回落成组键）。
- 备份 `Output/_OLD_bak/gallery_index_pre_names_20260929_1824/`；期望清单 `docs/name_expect_20260929.json`。
- 闸门 `gallery_index_diff_check.py --expect …` 退出码 0；`with_cn` 984→975（差值即那 9 个占位符），`with_faction`/`ship`/`story` 一字未动。
- 换入后线上抽查：`missr`=好人理查德、`strength`=仲裁者·司特莲库斯·VIII、`aijiang`=绊爱（并补上 驱逐/精锐）、`gelifen`/`npcchaijun` 尾空格已去、`hierophant` 仍是**教皇**、`dosair` 仍是**多塞特**（占位符判据生效）、`kelei` 仍是**可畏**且阵营/舰种/稀有度全在（零回退不变式生效）、`2B`/`A2` 保住。

> ⚠️ 本表的 `[ ]` 勾选框是**做坏了的**：GitHub 风格 checkbox 在表格单元格里不渲染成可点控件，等于给了一张不能填的表。以后这类待勾清单一律出 **TSV/CSV**，或直接让用户口述要排除哪些。

---


## 一、仅去掉首尾空白（10 组，属清理）

| 组键 | 现名（带尾空格） | 换后 |
|---|---|---|
| `baoduoliuhua` | `宝多六花 ` | `宝多六花` |
| `daleike` | `尼科洛索·达雷科 ` | `尼科洛索·达雷科` |
| `digaiteluyin` | `迪盖·特鲁因 ` | `迪盖·特鲁因` |
| `gelifen` | `格里芬 ` | `格里芬` |
| `jiaosuai` | `焦苏埃·卡尔杜齐 ` | `焦苏埃·卡尔杜齐` |
| `npcbenningdun` | `本宁顿 ` | `本宁顿` |
| `npcchaijun` | `柴郡 ` | `柴郡` |
| `pasadina` | `帕萨迪纳 ` | `帕萨迪纳` |
| `qian` | `新条茜 ` | `新条茜` |
| `tuolichaili` | `托里拆利 ` | `托里拆利` |

## 二、真换名（45 组）

### 仲裁者系列全称（10）

| 勾 | 组键 | 现名 | → 配置名 | 来源档 | 备注 |
|---|---|---|---|---|---|
| [ ] | `chariot` | 战车 | **仲裁者·提尔瑞特·VII** | painting |  |
| [ ] | `devil` | 恶魔 | **仲裁者·迪贝路·XV** | painting |  |
| [ ] | `emperor` | 皇帝 | **仲裁者·英普拉·IV** | painting |  |
| [ ] | `empress` | 女皇 | **仲裁者·恩普雷斯·III** | painting |  |
| [ ] | `hermit` | 隐者 | **仲裁者·赫米忒·IX** | painting |  |
| [ ] | `lovers` | 恋人 | **仲裁者·拉沃斯·VI** | painting |  |
| [ ] | `moon` | 月亮 | **仲裁者·沐恩·XVIII** | painting |  |
| [ ] | `strength` | 力量 | **仲裁者·司特莲库斯·VIII** | painting |  |
| [ ] | `temperance` | 节制 | **仲裁者·天帕岚斯·XIV** | painting |  |
| [ ] | `tower` | 塔 | **仲裁者·托瓦·XVI** | painting |  |

### NPC/剧情角色（15）

| 勾 | 组键 | 现名 | → 配置名 | 来源档 | 备注 |
|---|---|---|---|---|---|
| [ ] | `anjie` | 安捷 | **安洁** | painting |  |
| [ ] | `fulami` | 弗拉米 | **芙拉米** | painting |  |
| [ ] | `lanmao` | 蓝猫 | **指挥喵** | painting |  |
| [ ] | `lianren` | 连刃 | **战争协议-镰刃** | painting |  |
| [ ] | `machinemagician` | 机械魔术师 | **审判机·「魔术师」** | painting |  |
| [ ] | `madamm` | 夫人 | **M女士** | painting_ci |  |
| [ ] | `maria` | 玛丽亚 | **玛利亚** | painting |  |
| [ ] | `missr` | R小姐 | **好人理查德** | painting_ci |  |
| [ ] | `ryouko` | 凉子 | **天原凉子** | painting |  |
| [ ] | `shenpanjizhanche` | 审判机战车 | **审判机·「战车」** | painting |  |
| [ ] | `silverfox` | 银狐 | **「银狐」女士** | painting |  |
| [ ] | `starbeast` | 星兽 | **星之兽** | painting |  |
| [ ] | `tbniang` | TB娘 | **领航员-TB** | painting |  |
| [ ] | `youtuobiya` | 尤托比亚 | **尤托比娅·萨伏伊** | painting |  |
| [ ] | `yulun` | 雨轮 | **战争协议-玉轮** | painting |  |

### 舰船（20）

| 勾 | 组键 | 现名 | → 配置名 | 来源档 | 备注 |
|---|---|---|---|---|---|
| [ ] | `aijiang` | 海酱 | **绊爱** | painting | 字段 type:—→驱逐;rarity:—→精锐 |
| [ ] | `gushouchuan` | 古手川 | **古手川唯** | painting |  |
| [ ] | `haixiao` | 海啸 | **海咲** | painting_ci |  |
| [ ] | `hdn102` | 伊织 | **绀紫之心** | painting_ci | ⚠️ 角色本名 vs HDD 形态名，且 §6 第 5 条记过「hdn 系列原错位一档」 |
| [ ] | `hdn202` | 涅普顿 | **圣黑之心** | painting_ci | ⚠️ 角色本名 vs HDD 形态名，且 §6 第 5 条记过「hdn 系列原错位一档」 |
| [ ] | `hdn302` | 布兰 | **群白之心** | painting_ci | ⚠️ 角色本名 vs HDD 形态名，且 §6 第 5 条记过「hdn 系列原错位一档」 |
| [ ] | `hdn402` | 诺瓦露 | **翡绿之心** | painting_ci | ⚠️ 角色本名 vs HDD 形态名，且 §6 第 5 条记过「hdn 系列原错位一档」 |
| [ ] | `huan` | 幻 | **环** | painting |  |
| [ ] | `lala` | 拉拉 | **菈菈·撒塔琳·戴比路克** | painting |  |
| [ ] | `maliluosi` | 玛利萝丝 | **玛莉萝丝** | painting_ci |  |
| [ ] | `mengmeng` | 梦梦 | **梦梦·贝莉雅·戴比路克** | painting |  |
| [ ] | `nana` | 娜娜 | **娜娜·阿丝达·戴比路克** | painting |  |
| [ ] | `paidi` | 派迪 | **派蒂** | painting_ci |  |
| [ ] | `qiannai` | 琪露诺 | **千乃** | painting_ci |  |
| [ ] | `suixiang` | 碎湘 | **穗香** | painting |  |
| [ ] | `tansuozhe` | 探索者 | **探索者-艾普洛** | painting |  |
| [ ] | `xiliansi` | 西连斯 | **西连寺春菜** | painting |  |
| [ ] | `xipeier` | 希佩尔 | **希佩尔海军上将(μ兵装)** | painting | 本组只有 idol/idolns 两个皮肤，故 μ兵装就是这组本身 |
| [ ] | `zhixiao` | 织宵 | **凪咲** | painting_ci |  |
| [ ] | `zhuzi` | 珠子 | **筑紫** | painting_ci |  |

## 三、被自动挡下的 49 组（供核对，不需要勾）

判据：换过去会让阵营/舰种/稀有度比现在更空。典型是 `X` → `X·META`（同组的 META 形态），以及 `kelei` 可畏→柯蕾（换过去丢 皇家/航母/超稀有、category 从 ship 翻成 story）。
另 `2B`/`A2` 是尼尔联动真名，纯 ASCII 规则第一版误杀、已改成只挡长度 ≥5 的回显串。
