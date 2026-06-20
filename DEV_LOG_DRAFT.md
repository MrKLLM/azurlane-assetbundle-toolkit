# 碧蓝航线 AssetBundles 目录只读审计报告

> **审计时间**: 2026-06-19  
> **审计路径**: `D:\Azur Lane Assets\files\AssetBundles`  
> **审计模式**: 只读（不修改任何源文件）

---

## 1. 目录总览

| 指标 | 数值 |
|---|---|
| 顶层子目录数 | 196 |
| 根级文件数 | 41 |
| 总文件数 | ~86,890 |
| 总大小 | ~26.6 GB |
| 最大目录深度 | 9 层 |

### 文件后缀分布

| 后缀 | 数量 | 总大小 | 说明 |
|---|---|---|---|
| *(无后缀)* | 82,162 | 21,863 MB | Unity AssetBundle 二进制 blob |
| `.b` | 4,370 | 4,208 MB | 音频 Cue Bundle（仅 `cue/` 目录） |
| `.cpk` | 300 | 1,123 MB | 视频封存包（仅 `originsource/cpk/`） |
| `.dll` | 10 | 1.9 MB | 原生插件（仅 `hybridclr/hotfix/`） |
| `.shadowmap` | 6 | 58 MB | 阴影贴图（仅 `dorm3d/scenesres/`） |

### 根级文件（41个）

均为独立 AssetBundle，包含系统级资源：

| 文件 | 大小 | 用途 |
|---|---|---|
| `scripts32` / `scripts64` | ~36 MB | IL2CPP 脚本（32/64位） |
| `custom_builtin` | 23 MB | 自定义内建资源 |
| `dependencies` | 6 MB | 资源依赖关系图 |
| `shader` / `spineshader` / `l2dshader` | ~1 MB | 着色器（通用/Spine/Live2D） |
| `technologycard` / `tecnation` | ~1 MB | 科技系统 UI |
| `skinclassified` / `skinicon` | ~0.3 MB | 皮肤分类 UI |
| 其余 | <1 MB | 各类小 UI 图标资源 |

---

## 2. 资源映射表

### Tier 1: 超大型目录（>500 MB）

| 子目录 | 资源类型 | 文件特征 | 示例文件 |
|---|---|---|---|
| `painting/` | 立绘拆分资源 | 无后缀，含 `_tex`/`_n_tex` 变体 | `aidang`, `aidang_tex`, `aidang_2` |
| `cue/` | 音频 Cue Bundle | `.b` 后缀，命名 `bgm-*`/`se-*`/`cv-*` | `bgm-battle-ironblood.b`, `cv_fubuki_001.b` |
| `live2d/` | Live2D 动态模型 | 无后缀，按舰名+皮肤编号 | `lingbo`, `z23`, `qiye_7` |
| `dorm3d/` | 3D 宿舍系统 | 4 子目录：character/effect/furniture/scenesres | `character/aijier_db/`, `scenesres/*.shadowmap` |
| `spinepainting/` | Spine 动画立绘 | 无后缀，含 `_res` 资源包 | `aerbien_4`, `aerbien_4_res` |
| `island/` | 岛屿系统 | 44 个子目录，7 直属文件 | 多层嵌套，按区域命名 |
| `ui/` | UI 系统 | 3,747 直属 + 4 子目录 | `activityuipage/`, `minigameui/`, `skin/` |

### Tier 2: 中大型目录（100-500 MB）

| 子目录 | 资源类型 | 文件特征 | 示例文件 |
|---|---|---|---|
| `originsource/cpk/` | 视频封存 | `.cpk` 后缀，300 个文件 | `bg_135.cpk`, `unlock_*.cpk` |
| `paintingface/` | 面部特写 | 无后缀，按舰名+皮肤编号 | `aerbien_2`, `aersasi_3` |
| `bg/` | 场景背景图 | 无后缀，命名 `bg_*` / `star_level_bg_*` | `bg_daofeng_1`, `star_level_bg_100` |
| `char/` | 角色资产包 | 无后缀，按舰名+皮肤编号 | `aidang_2`, `fubuki_3` |
| `chapter/` | 章节地图 | 1,985 直属 + 3 子目录(atlas/celltexture/pic) | `1x1_1hololive`, `2x2normalisland_1` |
| `neweducateicon/` | 教育系统图标 | 无后缀，181 MB | 数字编号文件 |
| `furnitrues/` | 家具数据 | 134 个子目录，0 直属文件 | 按家具集编号组织 |
| `sharecfgdata/` | 共享配置数据 | 无后缀，32 个文件 | `sharecfg_*` |
| `map/` | 地图数据 | 无后缀，2,678 文件 | 按地图区域命名 |
| `levelmap/` | 关卡地图 | 297 直属 + 1 子目录 | 数字编号 |

### Tier 3: 中型目录（10-100 MB）

| 子目录 | 资源类型 | 文件特征 | 示例文件 |
|---|---|---|---|
| `sfurniture/` | 特殊家具 | 无后缀，1,129 文件 | 按家具集命名 |
| `shipyardicon/` | 船坞图标 | 无后缀，2,585 文件 | 按舰名+皮肤编号 |
| `gallerypic/` | 图鉴图片 | 无后缀，134 文件 | 图鉴用图 |
| `helpbg/` | 帮助背景 | 无后缀，353 文件 | `battle_ac_1`, `3ddorm_1` |
| `commonbg/` | 通用背景 | 无后缀，111 文件 | `bg_main_day`, `dockyard_bg` |
| `metapainting/` | META 立绘 | 无后缀，23 文件 | `970108`, `970109`（数字编号） |
| `metaship/` | META 角色 | 无后缀，314 文件 | META 系列角色资产 |
| `educatepolaroid/` | 教育拍立得 | 无后缀，167 文件 | 拍立得图片 |
| `mangapic/` | 漫画图片 | 无后缀，378 文件 | 漫画插图 |
| `font/` | 字体资源 | 无后缀，31 文件 | 字体 AssetBundle |
| `loadingbg/` | 加载背景 | 无后缀，48 文件 | `bg_1`~`bg_12`, `login_*` |
| `loadingbg_hx/` | 加载背景(HX) | 无后缀，13 文件 | HX 版本加载背景 |
| `backyardtheme/` | 后院主题 | 无后缀，247 文件 | 按主题编号 |
| `item/` | 道具图标 | 无后缀，1,684 文件 | 道具图标资源 |
| `equips/` | 装备图标 | 无后缀，1,690 文件 | 装备图标资源 |
| `props/` | 道具资源 | 无后缀，1,459 文件 | 道具 AssetBundle |
| `effect/` | 视觉特效 | 无后缀，980 文件 | 特效资源 |
| `qicon/` | Q版图标 | 无后缀，2,751 文件 | Q版角色图标 |
| `squareicon/` | 方形图标 | 无后缀，2,794 文件 | 方形图标 |
| `memoryicon/` | 回忆图标 | 无后缀，658 文件 | 回忆系统图标 |
| `herohrzicon/` | 横版英雄图标 | 无后缀，2,500 文件 | 横版角色图标 |
| `shipmodels/` | 舰船模型 | 无后缀，2,466 文件 | 3D 模型数据 |
| `skillicon/` | 技能图标 | 无后缀，1,760 文件 | 技能图标 |
| `furnitureicon/` | 家具图标 | 无后缀，3,914 文件 | 家具图标 |
| `storyicon/` | 剧情图标 | 无后缀，319 文件 | 剧情系统图标 |

### Tier 4: 小型目录（<10 MB）— 完整列表

| 子目录 | 资源类型 | 文件数 | 大小 |
|---|---|---|---|
| `actgiftpackages/` | 活动礼包 | 6 | 343 KB |
| `activitybanner/` | 活动横幅 | 137 | 6.3 MB |
| `activitybossbuff/` | 活动Boss Buff | 21 | 124 KB |
| `activitymedal/` | 活动勋章 | 284 | 3.5 MB |
| `activitypainting/` | 活动立绘 | 35 | 5 MB |
| `activityuitable/` | 活动UI表格 | 200 | 2.4 MB |
| `aircrafticon/` | 飞机图标 | 197 | 1.1 MB |
| `artresource/` | 美术资源 | 0(4子目录) | — |
| `backyardbg/` | 后院背景 | 2 | 221 KB |
| `battleresultitems/` | 战斗结算道具 | 16 | 150 KB |
| `battlescore/` | 战斗评分 | 4 | 228 KB |
| `beachguardgameassets/` | 沙滩守卫游戏 | 6 | 183 KB |
| `boxprefab/` | 盒子预制体 | 170 | 4.1 MB |
| `buildin_material/` | 内建材质 | 1 | 2.3 KB |
| `buildpainting/` | 建造立绘 | 4 | 7.4 MB |
| `bullet/` | 弹幕 | 0(1子目录) | 118 KB |
| `bulletall/` | 弹幕合集 | 56 | 483 KB |
| `cardtowerselectships/` | 卡牌塔选船 | 2 | 31 KB |
| `catterystyle/` | 猫爪样式 | 6 | 1.9 MB |
| `challengebossinfo/` | 挑战Boss信息 | 17 | 359 KB |
| `changeskin/` | 换装系统 | 7 | 588 KB |
| `chargeicon/` | 充值图标 | 186 | 3.8 MB |
| `char`* | 充值相关 | 451 | 12.5 MB |
| `chatframe/` | 聊天框 | 89 | 1.5 MB |
| `clouds/` | 云朵 | 21 | 733 KB |
| `cluepictures/` | 线索图片 | 35 | 2.5 MB |
| `clutter/` | 杂项 | 90 | 25 MB |
| `collectionfileillustration/` | 收藏文件插图 | 63 | 2.1 MB |
| `collectionfiletitle/` | 收藏文件标题 | 28 | 253 KB |
| `combatuistyle/` | 战斗UI样式 | 24 | 3.2 MB |
| `commanderhrz/` | 指挥官横版 | 20 | 222 KB |
| `commandericon/` | 指挥官图标 | 20 | 258 KB |
| `commanderpainting/` | 指挥官立绘 | 20 | 5.9 MB |
| `commanderrarity/` | 指挥官稀有度 | 4 | 27 KB |
| `commanderskillicon/` | 指挥官技能图标 | 30 | 285 KB |
| `commandertalenticon/` | 指挥官天赋图标 | 106 | 943 KB |
| `crusingmap/` | 巡航地图 | 3 | 404 KB |
| `cryptolalia/` | 加密语音 | 34 | 309 KB |
| `cryptolaliaship/` | 加密语音(角色) | 29 | 7.4 MB |
| `dailylevelicon/` | 每日关卡图标 | 5 | 273 KB |
| `dailyui/` | 每日UI | 8 | 230 KB |
| `dorm3daccompany/` | 3D宿舍陪伴 | — | — |
| `dorm3dbanner/` | 3D宿舍横幅 | — | — |
| `dorm3dchar/` | 3D宿舍角色 | — | — |
| `dorm3dcollection/` | 3D宿舍收藏 | — | — |
| `dorm3dcucoloris/` | 3D宿舍彩蛋 | — | — |
| `dorm3dholylight/` | 3D宿舍圣光 | — | — |
| `dorm3dicon/` | 3D宿舍图标 | — | — |
| `dorm3dins/` | 3D宿舍指导 | — | — |
| `dorm3dmemory/` | 3D宿舍回忆 | — | — |
| `dorm3dphoto/` | 3D宿舍照片 | — | — |
| `dorm3dselect/` | 3D宿舍选择 | — | — |
| `dorm3dskinpart/` | 3D宿舍皮肤部件 | — | — |
| `dreamlandui/` | 梦境UI | 3 | 4.5 MB |
| `educateanim/` | 教育动画 | 157 | 676 KB |
| `educateavatar/` | 教育头像 | 17 | 367 KB |
| `educatepicture/` | 教育图片 | 38 | 10 MB |
| `educateprops/` | 教育道具 | 165 | 2 MB |
| `educatesite/` | 教育场景 | 22 | 685 KB |
| `educatetarget/` | 教育目标 | 48 | 3.8 MB |
| `emblem/` | 徽章 | 28 | 465 KB |
| `eventtype/` | 活动类型 | 8 | 83 KB |
| `exploreobj/` | 探索目标 | 24 | 1.5 MB |
| `extra/` | 额外资源 | 2 | 37 KB |
| `extra_page/` | 额外页面 | 0(6子目录) | — |
| `feastchar/` | 祭典角色 | 7 | 1.4 MB |
| `feastchargift/` | 祭典礼物 | 7 | 128 KB |
| `feasticon/` | 祭典图标 | 7 | 109 KB |
| `feastpainting/` | 祭典立绘 | 7 | 1.3 MB |
| `feastpuzzle/` | 祭典拼图 | 7 | 37 KB |
| `frame/` | 边框 | 2 | 70 KB |
| `fushunadventure/` | 抚顺大冒险 | 48 | 1.2 MB |
| `gamehallicon/` | 游戏厅图标 | 23 | 2.1 MB |
| `guideitem/` | 引导道具 | 16 | 138 KB |
| `guildboss/` | 公会Boss | 16 | 723 KB |
| `guildevent/` | 公会活动 | 12 | 1.7 MB |
| `guildmission/` | 公会任务 | 25 | 1.6 MB |
| `guildpainting/` | 公会立绘 | 5 | 2.2 MB |
| `haixiao_3_doa/` | 海啸3 DOA | 0(1子目录) | 4.1 MB |
| `hideseekui/` | 躲猫猫UI | 20 | 79 KB |
| `holidayicon/` | 节日图标 | 23 | 1.4 MB |
| `hybridclr/` | 混合CLR | 0(1子目录) | 1.9 MB(.dll) |
| `icondesc/` | 图标描述 | 0(1子目录) | 9 KB |
| `iconframe/` | 图标边框 | 129 | 2.6 MB |
| `independenttex/` | 独立纹理 | 10 | 346 KB |
| `islandphoto/` | 岛屿照片 | 18 | 1.1 MB |
| `jiujiuexpeditioncollectionicon/` | 99远征收藏图标 | 15 | 244 KB |
| `leveluiview/` | 关卡UI视图 | 18 | 231 KB |
| `limitchallenge/` | 限时挑战 | 1(4子目录) | 143 KB |
| `linkbutton/` | 链接按钮 | 53 | 528 KB |
| `linkbutton_mellow/` | 链接按钮(圆润) | 41 | 430 KB |
| `livingareacover/` | 生活区封面 | 57 | 18 MB |
| `lotterybg/` | 抽奖背景 | 12 | 2 MB |
| `loveletteranim/` | 情书动画 | 0(1子目录) | 5.5 MB |
| `lovelettermedal/` | 情书勋章 | 7 | 578 KB |
| `loveletterstyle/` | 情书样式 | 4 | 6.7 MB |
| `loveletterstyleatlas/` | 情书样式图集 | 13 | 2.3 MB |
| `mapres/` | 地图资源 | 17(2子目录) | 8.2 MB |
| `medal/` | 勋章 | 164 | 5.2 MB |
| `medalalbum/` | 勋章专辑 | 18 | 868 KB |
| `memorystoryline/` | 回忆剧情线 | 95 | 3.5 MB |
| `musiccover/` | 音乐封面 | 10 | 482 KB |
| `neweducatecommonbg/` | 新教育通用背景 | 3 | 1.2 MB |
| `newshipbg/` | 新舰船背景 | 14 | 3.7 MB |
| `ninjacityicon/` | 忍者城图标 | 74 | 996 KB |
| `numbericon/` | 数字图标 | 0(1子目录) | — |
| `orbit/` | 轨道 | 125 | 17.5 MB |
| `painting_filte/` | 立绘滤镜 | 2 | 26 KB |
| `paintings/` | 立绘画集 | 4 | 3.8 MB |
| `paintingsother/` | 其他立绘 | 0(1子目录) | — |
| `pileaim/` | 堆叠瞄准 | 21 | 510 KB |
| `plane/` | 飞机 | 11 | 200 KB |
| `prefab/` | 预制体 | 0(1子目录) | — |
| `prints/` | 印花 | 16 | 673 KB |
| `puzzla/` | 拼图 | 8 | 2 MB |
| `roguecards/` | 肉鸽卡牌 | 50 | 557 KB |
| `roguegifts/` | 肉鸽礼物 | 10 | 101 KB |
| `scenes/` | 场景 | 2 | 534 KB |
| `sculpturerole/` | 雕塑角色 | 32 | 1.1 MB |
| `shipdesignicon/` | 舰船设计图标 | 46 | 729 KB |
| `shiprarity/` | 舰船稀有度 | 22 | 561 KB |
| `shopbanner/` | 商店横幅 | 12 | 1.7 MB |
| `shrine2022/` | 神社2022 | 28 | 1.2 MB |
| `spineitem/` | Spine道具 | 12 | 662 KB |
| `spweapon/` | 特殊武器 | 235 | 2.1 MB |
| `stacks/` | 堆叠 | 20 | 75 KB |
| `story/` | 剧情 | 12 | 58 KB |
| `storymap/` | 剧情地图 | 10 | 9.2 MB |
| `storypointicon/` | 剧情点图标 | 6 | 127 KB |
| `tecfateskillicon/` | 科技命运技能图标 | 68 | 423 KB |
| `technologyshipicon/` | 科技舰船图标 | 56 | 1.4 MB |
| `template/` | 模板 | 9 | 133 KB |
| `three3dquaitysettings/` | 3D画质设置 | 0(1子目录) | 3 KB |
| `towerclimbing/` | 爬塔 | 0(1子目录) | 209 KB |
| `towerclimbingcollectionicon/` | 爬塔收藏图标 | 15 | 244 KB |
| `universalrenderpipeline/` | URP管线 | 0(1子目录) | 105 KB |
| `world/` | 世界系统 | 多层嵌套(14子目录) | 多区域 |
| `worldhelpbg/` | 世界帮助背景 | 29 | 3.9 MB |
| `worldmap3d/` | 3D世界地图 | 0(2子目录) | 712 KB |
| `xunzhang/` | 勋章 | 10 | 471 KB |
| `voteships/` | 投票舰船 | 190 | 17 MB |
| `strategyicon/` | 策略图标 | 232 | 2 MB |
| `enemies/` | 敌人图标 | 340 | 4 MB |
| `emoji/` | 表情 | 208 | 6 MB |
| `shipstatus/` | 舰船状态 | — | 24 KB |

---

## 3. 关键资源精确定位

### 3.1 静态立绘（`painting/`）

**位置**: `D:\Azur Lane Assets\files\AssetBundles\painting\`

**数量**: 10,178 个文件，7,273 MB

**结构特征**:
- 每个舰娘有多个文件：基础bundle + `_tex` 纹理bundle
- 皮肤通过数字后缀 `_2`, `_3`... 标识
- 所有文件均为无后缀 Unity AssetBundle

**文件配对规则**:
```
{舰名}         → 立绘 Mesh/骨骼数据 Bundle
{舰名}_tex     → 立绘 Texture2D 纹理 Bundle
```

### 3.2 皮肤变体识别规则

从 `painting/` 目录文件列表分析得出的完整命名规则：

#### 变体编号（皮肤套数）
| 后缀 | 含义 | 示例 |
|---|---|---|
| *(无)* | 默认皮肤 | `aidang` |
| `_2` | 第2套皮肤 | `aidang_2` |
| `_3` | 第3套皮肤 | `aidang_3` |
| `_4`~`_9` | 更多皮肤 | `biaoqiang_9` |

#### 变体类型后缀
| 后缀 | 含义 | 示例 |
|---|---|---|
| `_alter` | 魔改版本 | `birui_alter` |
| `_hei` | 黑化版本 | `chicheng_heihua` |
| `_idol` | 偶像皮肤 | `chicheng_idol` |
| `_younv` | 幼女形态 | `chaijun_younv` |
| `_memory` | 回忆皮肤 | `birui_memory` |
| `_g` | G变体 | `bailu_g` |
| `_h` | H变体 | `biaoqiang_h` |
| `_dark_shadow` | 暗影变体 | `dadouquan_dark_shadow` |
| `_wjz` | 特殊变体 | `aila_wjz` |
| `_rank` | 竞技变体 | `aijiang_rank` |
| `_ex` | EX变体 | `banjiu_ex` |

#### 功能层后缀
| 后缀 | 含义 | 示例 |
|---|---|---|
| `_tex` | 纹理数据 | `aidang_tex` |
| `_n` | 夜间/普通变体 | `aidang_6_n` |
| `_rw` | RW变体纹理 | `aidang_6_rw_tex` |
| `_bj` | 背景层 | `aerjier_3_bj1_tex` |
| `_hx` | HX变体 | `aidang_6_hx` |
| `_shophx` | 商店HX | `alabama_2_shophx_tex` |
| `_front` | 前景层 | `aidang_h_front_tex` |
| `_middle` | 中景层 | `dafeng_idol_middle_tex` |
| `_asmr` | ASMR变体 | `aimudeng_5_asmr` |

#### 完整文件组示例（以 `aidang` 第6套皮肤为例）
```
aidang_6           → 立绘 Mesh Bundle
aidang_6_tex       → 立绘纹理 Bundle
aidang_6_n         → 夜间变体 Mesh
aidang_6_n_tex     → 夜间变体纹理
aidang_6_hx        → HX变体 Mesh
aidang_6_hx_tex    → HX变体纹理
aidang_6_rw_tex    → RW变体纹理
aidang_6_rw_hx_tex → RW+HX变体纹理
aidang_6_n_hx      → 夜间+HX Mesh
aidang_6_n_hx_tex  → 夜间+HX纹理
```

### 3.3 背景图

#### 场景背景（`bg/`）
**位置**: `D:\Azur Lane Assets\files\AssetBundles\bg\`  
**数量**: 1,254 个文件，606 MB

**命名模式**:
| 前缀 | 用途 | 示例 |
|---|---|---|
| `bg_{活动名}_{编号}` | 活动场景背景 | `bg_daofeng_1`, `bg_camelot_5` |
| `bg_{活动名}_cg{编号}` | 活动CG图 | `bg_tianqiong_cg1` |
| `star_level_bg_{编号}` | 关卡背景 | `star_level_bg_100` |
| `bg_story_{场景}` | 剧情背景 | `bg_story_room` |
| `bg_port_{港口}` | 港口背景 | `bg_port_niuyue` |
| `bg_main_{时段}` | 主界面背景 | `bg_main_day`, `bg_main_night` |
| `storymap_{区域}` | 故事地图 | `storymap_taipingyang` |
| `bg_project_{项目}` | 项目背景 | `bg_project_tb_cg1` |

#### 通用背景（`commonbg/`）
**位置**: `D:\Azur Lane Assets\files\AssetBundles\commonbg\`  
**数量**: 111 个文件，57 MB  
**用途**: 系统界面通用背景  
**示例**: `bg_main_day`, `dockyard_bg`, `buildship_bg`, `formation_bg`

#### 加载背景（`loadingbg/`）
**位置**: `D:\Azur Lane Assets\files\AssetBundles\loadingbg\`  
**数量**: 48 个文件，32 MB  
**示例**: `bg_1`~`bg_12`, `login_*`（按日期命名的登录背景）

#### 帮助背景（`helpbg/`）
**位置**: `D:\Azur Lane Assets\files\AssetBundles\helpbg\`  
**数量**: 353 个文件，59 MB  
**用途**: 帮助/教程页面背景

### 3.4 Live2D 动态皮肤（`live2d/`）

**位置**: `D:\Azur Lane Assets\files\AssetBundles\live2d\`  
**数量**: 256 个文件，2,513 MB

**命名规则**: `{舰名}_{皮肤编号}` 或 `{舰名}_{皮肤编号}_{变体}`  
**示例**: `lingbo`, `z23`, `qiye_7`, `xinnong_3_hx`

**文件特征**: 每个 Live2D 模型为单个无后缀 AssetBundle，体积较大（平均 ~10 MB），包含完整的 Live2D 模型数据、纹理、动作等。

**与 painting/ 的关联**: Live2D 皮肤在 `painting/` 中也有对应的静态立绘 bundle。

### 3.5 其他重要资源

#### Spine 动画立绘（`spinepainting/`）
**数量**: 406 文件，2,146 MB  
**特征**: 成对出现 — `{舰名}_{皮肤}` + `{舰名}_{皮肤}_res`  
**示例**: `aerbien_4` + `aerbien_4_res`

#### 面部特写（`paintingface/`）
**数量**: 2,160 文件，704 MB  
**用途**: 剧情对话中的角色面部特写

#### 3D 宿舍（`dorm3d/`）
**结构**: 4 子目录
```
dorm3d/
  character/    → 3D角色模型（aijier_db/, dafeng_db/ 等）
  effect/       → 视觉特效
  furniture/    → 3D家具模型
  scenesres/    → 场景资源（含 .shadowmap）
```

#### 视频封存（`originsource/cpk/`）
**数量**: 300 个 .cpk 文件，1,123 MB  
**命名**: `bg_*.cpk`, `unlock_*.cpk`, `tb_*.cpk`

#### 音频（`cue/`）
**数量**: 4,370 个 .b 文件，4,209 MB  
**命名模式**:
| 前缀 | 类型 | 示例 |
|---|---|---|
| `bgm-*` | 背景音乐 | `bgm-battle-ironblood.b` |
| `se-*` | 音效 | `se_001.b` |
| `cv_*` | 角色语音 | `cv_fubuki_001.b` |

---

## 4. 工具链缺口评估

### 必须安装的工具

| 工具 | 用途 | 下载地址 | 版本建议 |
|---|---|---|---|
| **AssetStudio** | 读取/预览/导出 Unity AssetBundle 中的 Texture2D、AudioClip、Mesh、Sprite 等资源。支持批量加载和搜索。 | [GitHub: Anatawa12/AssetStudio](https://github.com/Anatawa12/AssetStudio) | v0.16.0+ |
| **AssetStudioGUI** | AssetStudio 的 GUI 版本，提供可视化界面进行批量预览、筛选和导出。 | 同 AssetStudio 仓库 | 与 AssetStudio 同版本 |
| **UABE (Unity Asset Bundle Extractor)** | 直接编辑/导出 AssetBundle 内的资源，支持 .dat 导出和导入。 | [GitHub: SerenityCode/UnityAssetBundleExtractor](https://github.com/SerenityCode/UnityAssetBundleExtractor) | v3.0+ |
| **AssetRipper** | 自动化拆包工具，可将整个 AssetBundle 目录反向工程为可编辑的 Unity 项目结构。 | [GitHub: AssetRipper/AssetRipper](https://github.com/AssetRipper/AssetRipper) | 最新版 |
| **UnityPy** | Python 库，用于脚本化批量处理 AssetBundle。适合编写自动化导出脚本。 | [PyPI: UnityPy](https://pypi.org/project/UnityPy/) | v1.10+ |
| **Python 3.x** | 运行 UnityPy 脚本的运行环境。 | [python.org](https://www.python.org/) | 3.10+ |
| **Spine Viewer** | 预览和导出 Spine 动画。 | [Esoteric Software](https://esotericsoftware.com/spine-player) | Spine 3.8+ |
| **Live2D Cubism Viewer** | 预览 Live2D 模型和动作。 | [Live2D 官网](https://www.live2d.com/) | Cubism 4.2+ |
| **ffmpeg** | 处理 `.cpk` 视频包中的视频流，提取/转换视频。 | [ffmpeg.org](https://ffmpeg.org/download.html) | 最新稳定版 |
| **7-Zip** | 解压 `.cpk` 封存包（部分 .cpk 可用 7z 打开）。 | [7-zip.org](https://www.7-zip.org/) | 23.01+ |

### 工具作用详解

#### AssetStudio / AssetStudioGUI（核心工具）
- **导出 Texture2D**: 将 AssetBundle 中的纹理导出为 PNG/TGA
- **导出 Sprite**: 提取 Sprite 及其裁剪信息
- **导出 AudioClip**: 提取音频为 .wav
- **导出 Mesh**: 导出 3D 网格为 .obj
- **批量操作**: 支持整个目录递归加载和导出
- **搜索过滤**: 按资源类型、名称快速定位

#### UABE
- **资源查看**: 查看 AssetBundle 内所有资源的详细信息
- **资源导出**: 将单个资源导出为原始格式
- **资源修改**: 可修改 AssetBundle 后重新打包（本任务不需要）
- **批处理**: 支持命令行批量导出

#### AssetRipper
- **一键拆包**: 将 AssetBundle 目录重组为 Unity 项目
- **自动分类**: 按资源类型自动归类到标准 Unity 目录结构
- **依赖解析**: 自动处理资源间的依赖关系
- **保留元数据**: 保留原始资源的 meta 信息

#### UnityPy（脚本化方案）
```python
import UnityPy
env = UnityPy.load("path/to/assetbundle")
for obj in env.objects:
    if obj.type.name == "Texture2D":
        data = obj.read()
        data.image.save(f"{data.name}.png")
```
- 适合编写批量导出脚本
- 可处理 AssetStudio 无法识别的特殊格式
- 支持 Python 生态的图像处理库

---

## 5. 分阶段操作步骤

### 阶段 ① 工具安装

```bash
# 1. 安装 Python 3.10+
# 从 https://www.python.org/downloads/ 下载安装
# 安装时勾选 "Add Python to PATH"

# 2. 安装 UnityPy
pip install UnityPy

# 3. 下载 AssetStudio
# 从 https://github.com/Anatawa12/AssetStudio/releases 下载最新版
# 解压到任意目录即可使用

# 4. 下载 UABE
# 从 https://github.com/SerenityCode/UnityAssetBundleExtractor/releases 下载
# 解压到任意目录

# 5. 下载 AssetRipper（可选）
# 从 https://github.com/AssetRipper/AssetRipper/releases 下载

# 6. 下载 ffmpeg
# 从 https://ffmpeg.org/download.html 下载
# 将 ffmpeg.exe 加入系统 PATH
```

### 阶段 ② 扫描分类

```bash
# 使用 AssetStudioGUI 进行初步扫描：
# 1. 打开 AssetStudioGUI
# 2. File → Load Folder → 选择 D:\Azur Lane Assets\files\AssetBundles
# 3. 等待加载完成（首次可能需要较长时间）
# 4. 使用 Filter 功能按类型筛选：
#    - Texture2D: 立绘、背景、图标
#    - AudioClip: 语音、音效、BGM
#    - Mesh: 3D模型网格
#    - TextAsset: 配置数据

# 或使用 UnityPy 脚本批量扫描：
```

```python
# scan_bundles.py - 批量扫描 AssetBundle 统计
import UnityPy
import os
from collections import defaultdict

stats = defaultdict(lambda: defaultdict(int))
target_dir = r"D:\Azur Lane Assets\files\AssetBundles"

for root, dirs, files in os.walk(target_dir):
    for f in files:
        path = os.path.join(root, f)
        rel_path = os.path.relpath(path, target_dir)
        top_dir = rel_path.split(os.sep)[0] if os.sep in rel_path else "root"
        
        try:
            env = UnityPy.load(path)
            for obj in env.objects:
                stats[top_dir][obj.type.name] += 1
        except:
            stats[top_dir]["ERROR"] += 1

for dir_name, types in sorted(stats.items()):
    print(f"\n=== {dir_name} ===")
    for type_name, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {type_name}: {count}")
```

### 阶段 ③ 导出资源

#### 导出立绘（painting/）
```python
# export_paintings.py - 批量导出立绘纹理
import UnityPy
import os

source = r"D:\Azur Lane Assets\files\AssetBundles\painting"
output = r"D:\Azur Lane Assets\exported\paintings"

os.makedirs(output, exist_ok=True)

for f in os.listdir(source):
    if "_tex" in f:  # 只处理纹理文件
        path = os.path.join(source, f)
        try:
            env = UnityPy.load(path)
            for obj in env.objects:
                if obj.type.name == "Texture2D":
                    data = obj.read()
                    name = data.name or f
                    data.image.save(os.path.join(output, f"{name}.png"))
                    print(f"Exported: {name}.png")
        except Exception as e:
            print(f"Error: {f} - {e}")
```

#### 导出背景（bg/）
```python
# export_backgrounds.py - 批量导出背景图
import UnityPy
import os

source = r"D:\Azur Lane Assets\files\AssetBundles\bg"
output = r"D:\Azur Lane Assets\exported\backgrounds"

os.makedirs(output, exist_ok=True)

for f in os.listdir(source):
    path = os.path.join(source, f)
    try:
        env = UnityPy.load(path)
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                data = obj.read()
                name = data.name or f
                data.image.save(os.path.join(output, f"{name}.png"))
                print(f"Exported: {name}.png")
    except Exception as e:
        print(f"Error: {f} - {e}")
```

#### 导出 Live2D 模型
```bash
# Live2D 模型需要特殊处理：
# 1. 使用 AssetStudio 导出 Texture2D 纹理
# 2. 使用 Live2D Cubism Viewer 查看模型
# 3. 注意：Live2D 模型数据可能需要完整目录结构才能正确加载
```

### 阶段 ④ 合成整理

```bash
# 1. 创建整理目录结构
mkdir -p "D:\Azur Lane Assets\organized\paintings\default"
mkdir -p "D:\Azur Lane Assets\organized\paintings\skins"
mkdir -p "D:\Azur Lane Assets\organized\backgrounds\scene"
mkdir -p "D:\Azur Lane Assets\organized\backgrounds\common"
mkdir -p "D:\Azur Lane Assets\organized\backgrounds\loading"
mkdir -p "D:\Azur Lane Assets\organized\live2d"
mkdir -p "D:\Azur Lane Assets\organized\spine"
mkdir -p "D:\Azur Lane Assets\organized\audio\bgm"
mkdir -p "D:\Azur Lane Assets\organized\audio\se"
mkdir -p "D:\Azur Lane Assets\organized\audio\cv"
mkdir -p "D:\Azur Lane Assets\organized\ui"
mkdir -p "D:\Azur Lane Assets\organized\icons"

# 2. 按命名规则分类立绘
# - 无编号后缀 → default/
# - 有 _2, _3... 后缀 → skins/

# 3. 按类型分类背景
# - bg_* → scene/
# - commonbg/* → common/
# - loadingbg/* → loading/

# 4. 按前缀分类音频
# - bgm-* → bgm/
# - se-* → se/
# - cv_* → cv/
```

---

## 6. 附录

### 6.1 完整子目录清单（196个）

<details>
<summary>点击展开完整目录列表</summary>

```
actgiftpackages/          activitybanner/           activitybossbuff/
activitymedal/            activitypainting/         activityuitable/
aircrafticon/             artresource/              backyardbg/
backyardtheme/            battleresultitems/        battlescore/
beachguardgameassets/     bg/                       boxprefab/
buildin_material/         buildpainting/            bullet/
bulletall/                cardtowerselectships/     catterystyle/
challengebossinfo/        changeskin/               chargeicon/
char/                     char*                     chatframe/
clouds/                   cluepictures/             clutter/
collectionfileillustration/ collectionfiletitle/     combatuistyle/
commanderhrz/             commandericon/            commanderpainting/
commanderrarity/          commanderskillicon/       commandertalenticon/
commonbg/                 crusingmap/               crusingwindow/
cryptolalia/              cryptolaliaship/          cue/
dailylevelicon/           dailyui/                  dorm3d/
dorm3daccompany/          dorm3dbanner/             dorm3dchar/
dorm3dcollection/         dorm3dcucoloris/          dorm3dholylight/
dorm3dicon/               dorm3dins/                dorm3dmemory/
dorm3dphoto/              dorm3dselect/             dorm3dskinpart/
dreamlandui/              educateanim/              educateavatar/
educatepicture/           educatepolaroid/          educateprops/
educatesite/              educatetarget/            effect/
emblem/                   emoji/                    enemies/
eventtype/                exploreobj/               extra/
extra_page/               feastchar/                feastchargift/
feasticon/                feastpainting/            feastpuzzle/
font/                     frame/                    furnitrues/
furniture/                furnitureicon/            furnitures/
fushunadventure/          gallerypic/               gamehallicon/
guideitem/                guildboss/                guildevent/
guildmission/             guildpainting/            haixiao_3_doa/
helpbg/                   herohrzicon/              hideseekui/
holidayicon/              hybridclr/                icondesc/
iconframe/                independenttex/           island/
islandphoto/              item/                     jiujiuexpeditioncollectionicon/
levelmap/                 leveluiview/              limitchallenge/
linkbutton/               linkbutton_mellow/        live2d/
live2dmask/               livingareacover/          loadingbg/
loadingbg_hx/             lotterybg/                loveletteranim/
lovelettermedal/          loveletterstyle/          loveletterstyleatlas/
mangapic/                 map/                      mapres/
medal/                    medalalbum/               memoryicon/
memorystoryline/          metapainting/             metaship/
metaworldboss/            model/                    musiccover/
neweducatecommonbg/       neweducateicon/           newloading/
newshipbg/                ninjacityicon/            numbericon/
orbit/                    originsource/             painting/
painting_filte/           paintingface/             paintings/
paintingsother/           pileaim/                  plane/
prefab/                   prints/                   props/
puzzla/                   qicon/                    roguecards/
roguegifts/               scenes/                   sculpturerole/
sfurniture/               sharecfgdata/             shipdesignicon/
shipmodels/               shiprarity/               shipyardicon/
shopbanner/               shoppainting/             shrine2022/
spineitem/                spinepainting/            spweapon/
squareicon/               stacks/                   story/
storyicon/                storymap/                 storypointicon/
strategyicon/             teccatchup/               technologyshipicon/
template/                 three3dquaitysettings/    towerclimbing/
towerclimbingcollectionicon/ universalrenderpipeline/ voteships/
world/                    worldhelpbg/              worldmap3d/
xunzhang/
```

</details>

### 6.2 待确认目录

以下目录的资源类型和用途需要进一步确认：

| 目录 | 文件数 | 大小 | 待确认内容 |
|---|---|---|---|
| `artresource/` | 0(4子目录) | — | 子目录 atlas/effect/item/map 内容 |
| `extra_page/` | 0(6子目录) | — | 额外页面具体内容 |
| `numbericon/` | 0(1子目录) | — | t2 子目录内容 |
| `three3dquaitysettings/` | 0(1子目录) | 3 KB | 3D画质设置详情 |
| `towerclimbing/` | 0(1子目录) | 209 KB | 爬塔系统资源 |
| `universalrenderpipeline/` | 0(1子目录) | 105 KB | URP管线资源 |
| `worldmap3d/` | 0(2子目录) | 712 KB | area/map 子目录内容 |

### 6.3 导出路径建议

```
D:\Azur Lane Assets\exported\
├── paintings/
│   ├── default/          # 基础皮肤立绘 PNG
│   ├── skins/            # 皮肤立绘 PNG（按舰名分组）
│   └── face/             # 面部特写 PNG
├── backgrounds/
│   ├── scene/            # 场景背景 (bg/)
│   ├── common/           # 通用背景 (commonbg/)
│   ├── loading/          # 加载背景 (loadingbg/)
│   └── help/             # 帮助背景 (helpbg/)
├── live2d/               # Live2D 模型（需完整目录）
├── spine/                # Spine 动画
├── audio/
│   ├── bgm/              # 背景音乐
│   ├── se/               # 音效
│   └── cv/               # 角色语音
├── ui/                   # UI 资源
├── icons/                # 图标资源
└── models/               # 3D 模型
```

---

> **注意**: 本报告为只读审计，未对任何源文件进行修改或导出操作。实际导出需按照阶段 ③ 的步骤执行。
