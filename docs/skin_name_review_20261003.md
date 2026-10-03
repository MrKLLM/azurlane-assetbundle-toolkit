# 皮肤标签换成游戏真名 —— 改前/改后对照（2026-10-03）

> 生成：`py -3 scripts/diag/skin_name_review.py`（只读，不动 `Output/`）。
> 数据：`Output/gallery_v2/index.json`（现标签）+ `inputs/gamecfg/ship_skin_template.json`（真名）
> + `name_code.json`（占位符展开）。画法后缀（`_n`/`_hx`）保留成 `·无背景版` 等标记。

**总账**：皮肤条目 4487 | 会变 **3033** | 本来就一样 1351 | 换不了、保留现标签 78 | 需人看的可疑 107

可疑分布：名字塌了(==船名) 82、像垃圾串:全问号 13、长度异常 12

## 一、需要人勾选的（107 条）

勾选规则：把 `- [ ]` 改成 `- [x]` 表示**这条不许换**（保留现标签）；不勾 = 按对照表换。

### 多塞特 · `dosair_n` — 像垃圾串:全问号

改前 `无背景版` → 改后 `？？？·无背景版`

![dosair_n](../Output/gallery_v2/thumbs/dosair_n.webp)

- [ ] 这条不换
### 甘古特 · `gangute_dark` — 像垃圾串:全问号

改前 `dark` → 改后 `？？？`

![gangute_dark](../Output/gallery_v2/thumbs/gangute_dark.webp)

- [ ] 这条不换
### npcjinluhao · `npcjinluhao_3` — 像垃圾串:全问号

改前 `皮肤3` → 改后 `？？？`

![npcjinluhao_3](../Output/gallery_v2/thumbs/npcjinluhao_3.webp)

- [ ] 这条不换
### npcshi · `npcshi_3` — 像垃圾串:全问号

改前 `皮肤3` → 改后 `？？`

![npcshi_3](../Output/gallery_v2/thumbs/npcshi_3.webp)

- [ ] 这条不换
### 恰巴耶夫 · `qiabayefu_dark` — 像垃圾串:全问号

改前 `dark` → 改后 `？？？`

![qiabayefu_dark](../Output/gallery_v2/thumbs/qiabayefu_dark.webp)

- [ ] 这条不换
### 天原凉子 · `ryouko_shallow` — 像垃圾串:全问号

改前 `shallow` → 改后 `？？？?`

![ryouko_shallow](../Output/gallery_v2/thumbs/ryouko_shallow.webp)

- [ ] 这条不换
### 水星纪念 · `shuixingjinian_dark` — 像垃圾串:全问号

改前 `dark` → 改后 `？？？`

![shuixingjinian_dark](../Output/gallery_v2/thumbs/shuixingjinian_dark.webp)

- [ ] 这条不换
### 苏维埃罗西亚 · `suweiailuoxiya_dark` — 像垃圾串:全问号

改前 `dark` → 改后 `？？？`

![suweiailuoxiya_dark](../Output/gallery_v2/thumbs/suweiailuoxiya_dark.webp)

- [ ] 这条不换
### 苏维埃同盟 · `suweiaitongmeng_dark` — 像垃圾串:全问号

改前 `dark` → 改后 `？？？`

![suweiaitongmeng_dark](../Output/gallery_v2/thumbs/suweiaitongmeng_dark.webp)

- [ ] 这条不换
### 塔什干 · `tashigan_dark` — 像垃圾串:全问号

改前 `dark` → 改后 `？？？`

![tashigan_dark](../Output/gallery_v2/thumbs/tashigan_dark.webp)

- [ ] 这条不换
### unknown1 · `unknown1_hx` — 像垃圾串:全问号

改前 `和谐版` → 改后 `？？？？？·和谐版`

![unknown1_hx](../Output/gallery_v2/thumbs/unknown1_hx.webp)

- [ ] 这条不换
### unknown2 · `unknown2_hx` — 像垃圾串:全问号

改前 `和谐版` → 改后 `？？？？？·和谐版`

![unknown2_hx](../Output/gallery_v2/thumbs/unknown2_hx.webp)

- [ ] 这条不换
### 威严 · `weiyan_dark` — 像垃圾串:全问号

改前 `dark` → 改后 `？？？`

![weiyan_dark](../Output/gallery_v2/thumbs/weiyan_dark.webp)

- [ ] 这条不换
### 艾菈·冯·杜勒 · `aila_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `艾菈·冯·杜勒`

![aila_wjz](../Output/gallery_v2/thumbs/aila_wjz.webp)

- [ ] 这条不换
### 埃姆登 · `aimudeng_4_npc` — 名字塌了(==船名)

改前 `皮肤4·npc` → 改后 `埃姆登`

![aimudeng_4_npc](../Output/gallery_v2/thumbs/aimudeng_4_npc.webp)

- [ ] 这条不换
### 比叡 · `birui_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `比叡`

![birui_memory](../Output/gallery_v2/thumbs/birui_memory.webp)

- [ ] 这条不换
### 赤城 · `chicheng_alter` — 名字塌了(==船名)

改前 `alter` → 改后 `赤城`

![chicheng_alter](../Output/gallery_v2/thumbs/chicheng_alter.webp)

- [ ] 这条不换
### 大黄蜂 · `dahuangfeng_hx` — 名字塌了(==船名)

改前 `和谐版` → 改后 `大黄蜂·和谐版`

![dahuangfeng_hx](../Output/gallery_v2/thumbs/dahuangfeng_hx.webp)

- [ ] 这条不换
### 高雄 · `gaoxiong_dark` — 名字塌了(==船名)

改前 `dark` → 改后 `高雄`

![gaoxiong_dark](../Output/gallery_v2/thumbs/gaoxiong_dark.webp)

- [ ] 这条不换
### 海咲 · `haixiao_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `海咲`

![haixiao_doa](../Output/gallery_v2/thumbs/haixiao_doa.webp)

- [ ] 这条不换
### 海咲 · `haixiao_doa_wjz` — 名字塌了(==船名)

改前 `doa·wjz` → 改后 `海咲`

![haixiao_doa_wjz](../Output/gallery_v2/thumbs/haixiao_doa_wjz.webp)

- [ ] 这条不换
### 好人理查德 · `haorenlichade_alter` — 名字塌了(==船名)

改前 `alter` → 改后 `好人理查德`

![haorenlichade_alter](../Output/gallery_v2/thumbs/haorenlichade_alter.webp)

- [ ] 这条不换
### 绀紫之心 · `hdn102_1` — 名字塌了(==船名)

改前 `皮肤1` → 改后 `绀紫之心`

![hdn102_1](../Output/gallery_v2/thumbs/hdn102_1.webp)

- [ ] 这条不换
### 圣黑之心 · `hdn202_1` — 名字塌了(==船名)

改前 `皮肤1` → 改后 `圣黑之心`

![hdn202_1](../Output/gallery_v2/thumbs/hdn202_1.webp)

- [ ] 这条不换
### 布兰 · `hdn301_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `布兰`

![hdn301_memory](../Output/gallery_v2/thumbs/hdn301_memory.webp)

- [ ] 这条不换
### 群白之心 · `hdn302_1` — 名字塌了(==船名)

改前 `皮肤1` → 改后 `群白之心`

![hdn302_1](../Output/gallery_v2/thumbs/hdn302_1.webp)

- [ ] 这条不换
### 贝露 · `hdn401_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `贝露`

![hdn401_memory](../Output/gallery_v2/thumbs/hdn401_memory.webp)

- [ ] 这条不换
### 翡绿之心 · `hdn402_1` — 名字塌了(==船名)

改前 `皮肤1` → 改后 `翡绿之心`

![hdn402_1](../Output/gallery_v2/thumbs/hdn402_1.webp)

- [ ] 这条不换
### 仲裁者·赫米忒·IX · `hermit_alter` — 名字塌了(==船名)

改前 `alter` → 改后 `仲裁者·赫米忒·IX`

![hermit_alter](../Output/gallery_v2/thumbs/hermit_alter.webp)

- [ ] 这条不换
### 赫斯缇雅 · `hesitiya_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `赫斯缇雅`

![hesitiya_wjz](../Output/gallery_v2/thumbs/hesitiya_wjz.webp)

- [ ] 这条不换
### 环 · `huan_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `环`

![huan_doa](../Output/gallery_v2/thumbs/huan_doa.webp)

- [ ] 这条不换
### 旧金山 · `jiujinshan_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `旧金山`

![jiujinshan_wjz](../Output/gallery_v2/thumbs/jiujinshan_wjz.webp)

- [ ] 这条不换
### 科罗拉多 · `keluoladuo_2` — 名字塌了(==船名)

改前 `皮肤2` → 改后 `科罗拉多`

![keluoladuo_2](../Output/gallery_v2/thumbs/keluoladuo_2.webp)

- [ ] 这条不换
### 拉菲II · `lafeiii_n` — 名字塌了(==船名)

改前 `无背景版` → 改后 `拉菲II·无背景版`

![lafeiii_n](../Output/gallery_v2/thumbs/lafeiii_n.webp)

- [ ] 这条不换
### 蕾妮雅 · `leiniya_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `蕾妮雅`

![leiniya_wjz](../Output/gallery_v2/thumbs/leiniya_wjz.webp)

- [ ] 这条不换
### 灵敏 · `lingmin_alter` — 名字塌了(==船名)

改前 `alter` → 改后 `灵敏`

![lingmin_alter](../Output/gallery_v2/thumbs/lingmin_alter.webp)

- [ ] 这条不换
### 黎塞留 · `lisailiu_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `黎塞留`

![lisailiu_memory](../Output/gallery_v2/thumbs/lisailiu_memory.webp)

- [ ] 这条不换
### 琉·璃昂 · `liuliang_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `琉·璃昂`

![liuliang_wjz](../Output/gallery_v2/thumbs/liuliang_wjz.webp)

- [ ] 这条不换
### 露娜 · `luna_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `露娜`

![luna_doa](../Output/gallery_v2/thumbs/luna_doa.webp)

- [ ] 这条不换
### 罗恩 · `luoen_3` — 名字塌了(==船名)

改前 `皮肤3` → 改后 `罗恩`

![luoen_3](../Output/gallery_v2/thumbs/luoen_3.webp)

- [ ] 这条不换
### 罗马 · `luoma_ghost` — 名字塌了(==船名)

改前 `ghost` → 改后 `罗马`

![luoma_ghost](../Output/gallery_v2/thumbs/luoma_ghost.webp)

- [ ] 这条不换
### 马里兰 · `malilan_2` — 名字塌了(==船名)

改前 `皮肤2` → 改后 `马里兰`

![malilan_2](../Output/gallery_v2/thumbs/malilan_2.webp)

- [ ] 这条不换
### 玛莉萝丝 · `maliluosi_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `玛莉萝丝`

![maliluosi_doa](../Output/gallery_v2/thumbs/maliluosi_doa.webp)

- [ ] 这条不换
### 玛莉萝丝 · `maliluosi_doa_wjz` — 名字塌了(==船名)

改前 `doa·wjz` → 改后 `玛莉萝丝`

![maliluosi_doa_wjz](../Output/gallery_v2/thumbs/maliluosi_doa_wjz.webp)

- [ ] 这条不换
### 莫妮卡 · `monika_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `莫妮卡`

![monika_doa](../Output/gallery_v2/thumbs/monika_doa.webp)

- [ ] 这条不换
### 莫妮卡 · `monika_doa_wjz` — 名字塌了(==船名)

改前 `doa·wjz` → 改后 `莫妮卡`

![monika_doa_wjz](../Output/gallery_v2/thumbs/monika_doa_wjz.webp)

- [ ] 这条不换
### 妮娜·弗里德 · `nina_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `妮娜·弗里德`

![nina_wjz](../Output/gallery_v2/thumbs/nina_wjz.webp)

- [ ] 这条不换
### 宁海 · `ninghai_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `宁海`

![ninghai_memory](../Output/gallery_v2/thumbs/ninghai_memory.webp)

- [ ] 这条不换
### 阿尔萨斯 · `npcaersasi_3` — 名字塌了(==船名)

改前 `皮肤3` → 改后 `阿尔萨斯`

![npcaersasi_3](../Output/gallery_v2/thumbs/npcaersasi_3.webp)

- [ ] 这条不换
### 埃米尔·贝尔汀 · `npcaimierbeierding_5` — 名字塌了(==船名)

改前 `皮肤5` → 改后 `埃米尔·贝尔汀`

![npcaimierbeierding_5](../Output/gallery_v2/thumbs/npcaimierbeierding_5.webp)

- [ ] 这条不换
### 布伦努斯 · `npcbulunnusi_3` — 名字塌了(==船名)

改前 `皮肤3` → 改后 `布伦努斯`

![npcbulunnusi_3](../Output/gallery_v2/thumbs/npcbulunnusi_3.webp)

- [ ] 这条不换
### 关岛 · `npcguandao_3` — 名字塌了(==船名)

改前 `皮肤3` → 改后 `关岛`

![npcguandao_3](../Output/gallery_v2/thumbs/npcguandao_3.webp)

- [ ] 这条不换
### 光辉 · `npcguanghui_9` — 名字塌了(==船名)

改前 `皮肤9` → 改后 `光辉`

![npcguanghui_9](../Output/gallery_v2/thumbs/npcguanghui_9.webp)

- [ ] 这条不换
### 加斯科涅 · `npcjiasikenie_3` — 名字塌了(==船名)

改前 `皮肤3` → 改后 `加斯科涅`

![npcjiasikenie_3](../Output/gallery_v2/thumbs/npcjiasikenie_3.webp)

- [ ] 这条不换
### 君主 · `npcjunzhu_5` — 名字塌了(==船名)

改前 `皮肤5` → 改后 `君主`

![npcjunzhu_5](../Output/gallery_v2/thumbs/npcjunzhu_5.webp)

- [ ] 这条不换
### 柯莱特 · `npckelaite_2` — 名字塌了(==船名)

改前 `皮肤2` → 改后 `柯莱特`

![npckelaite_2](../Output/gallery_v2/thumbs/npckelaite_2.webp)

- [ ] 这条不换
### 可畏 · `npckewei_6` — 名字塌了(==船名)

改前 `皮肤6` → 改后 `可畏`

![npckewei_6](../Output/gallery_v2/thumbs/npckewei_6.webp)

- [ ] 这条不换
### 拉菲Ⅱ · `npclafeiii_4` — 名字塌了(==船名)

改前 `皮肤4` → 改后 `拉菲Ⅱ`

![npclafeiii_4](../Output/gallery_v2/thumbs/npclafeiii_4.webp)

- [ ] 这条不换
### 路易九世 · `npcluyijiushi_4` — 名字塌了(==船名)

改前 `皮肤4` → 改后 `路易九世`

![npcluyijiushi_4](../Output/gallery_v2/thumbs/npcluyijiushi_4.webp)

- [ ] 这条不换
### 马里兰 · `npcmalilan_3_n` — 名字塌了(==船名)

改前 `皮肤3·无背景版` → 改后 `马里兰·无背景版`

![npcmalilan_3_n](../Output/gallery_v2/thumbs/npcmalilan_3_n.webp)

- [ ] 这条不换
### 莫加多尔 · `npcmojiaduoer_2` — 名字塌了(==船名)

改前 `皮肤2` → 改后 `莫加多尔`

![npcmojiaduoer_2](../Output/gallery_v2/thumbs/npcmojiaduoer_2.webp)

- [ ] 这条不换
### 萨里 · `npcsali_2` — 名字塌了(==船名)

改前 `皮肤2` → 改后 `萨里`

![npcsali_2](../Output/gallery_v2/thumbs/npcsali_2.webp)

- [ ] 这条不换
### 维克斯堡 · `npcweikesibao_2` — 名字塌了(==船名)

改前 `皮肤2` → 改后 `维克斯堡`

![npcweikesibao_2](../Output/gallery_v2/thumbs/npcweikesibao_2.webp)

- [ ] 这条不换
### 雅努斯 · `npcyanusi_7` — 名字塌了(==船名)

改前 `皮肤7` → 改后 `雅努斯`

![npcyanusi_7](../Output/gallery_v2/thumbs/npcyanusi_7.webp)

- [ ] 这条不换
### 厌战 · `npcyanzhan_4` — 名字塌了(==船名)

改前 `皮肤4` → 改后 `厌战`

![npcyanzhan_4](../Output/gallery_v2/thumbs/npcyanzhan_4.webp)

- [ ] 这条不换
### 女天狗 · `nvtiangou_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `女天狗`

![nvtiangou_doa](../Output/gallery_v2/thumbs/nvtiangou_doa.webp)

- [ ] 这条不换
### 女天狗 · `nvtiangou_doa_wjz` — 名字塌了(==船名)

改前 `doa·wjz` → 改后 `女天狗`

![nvtiangou_doa_wjz](../Output/gallery_v2/thumbs/nvtiangou_doa_wjz.webp)

- [ ] 这条不换
### 派蒂 · `paidi_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `派蒂`

![paidi_doa](../Output/gallery_v2/thumbs/paidi_doa.webp)

- [ ] 这条不换
### 平海 · `pinghai_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `平海`

![pinghai_memory](../Output/gallery_v2/thumbs/pinghai_memory.webp)

- [ ] 这条不换
### 千乃 · `qiannai_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `千乃`

![qiannai_doa](../Output/gallery_v2/thumbs/qiannai_doa.webp)

- [ ] 这条不换
### 企业 · `qiye_dark` — 名字塌了(==船名)

改前 `dark` → 改后 `企业`

![qiye_dark](../Output/gallery_v2/thumbs/qiye_dark.webp)

- [ ] 这条不换
### 企业 · `qiye_dark_memory` — 名字塌了(==船名)

改前 `dark·memory` → 改后 `企业`

![qiye_dark_memory](../Output/gallery_v2/thumbs/qiye_dark_memory.webp)

- [ ] 这条不换
### 让·巴尔 · `rangbaer_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `让·巴尔`

![rangbaer_memory](../Output/gallery_v2/thumbs/rangbaer_memory.webp)

- [ ] 这条不换
### 瑞鹤 · `ruihe_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `瑞鹤`

![ruihe_memory](../Output/gallery_v2/thumbs/ruihe_memory.webp)

- [ ] 这条不换
### 萨福克 · `safuke_xinshou` — 名字塌了(==船名)

改前 `xinshou` → 改后 `萨福克`

![safuke_xinshou](../Output/gallery_v2/thumbs/safuke_xinshou.webp)

- [ ] 这条不换
### 三笠 · `sanli_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `三笠`

![sanli_memory](../Output/gallery_v2/thumbs/sanli_memory.webp)

- [ ] 这条不换
### 「银狐」女士 · `silverfox_shadow` — 名字塌了(==船名)

改前 `shadow` → 改后 `「银狐」女士`

![silverfox_shadow](../Output/gallery_v2/thumbs/silverfox_shadow.webp)

- [ ] 这条不换
### 穗香 · `suixiang_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `穗香`

![suixiang_doa](../Output/gallery_v2/thumbs/suixiang_doa.webp)

- [ ] 这条不换
### 穗香 · `suixiang_doa_wjz` — 名字塌了(==船名)

改前 `doa·wjz` → 改后 `穗香`

![suixiang_doa_wjz](../Output/gallery_v2/thumbs/suixiang_doa_wjz.webp)

- [ ] 这条不换
### 苏维埃同盟 · `suweiaitongmeng_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `苏维埃同盟`

![suweiaitongmeng_wjz](../Output/gallery_v2/thumbs/suweiaitongmeng_wjz.webp)

- [ ] 这条不换
### 天城 · `tiancheng_cv` — 名字塌了(==船名)

改前 `cv` → 改后 `天城`

![tiancheng_cv](../Output/gallery_v2/thumbs/tiancheng_cv.webp)

- [ ] 这条不换
### 武藏 · `wuzang_s` — 名字塌了(==船名)

改前 `s` → 改后 `武藏`

![wuzang_s](../Output/gallery_v2/thumbs/wuzang_s.webp)

- [ ] 这条不换
### 霞.改 · `xia_g` — 名字塌了(==船名)

改前 `G` → 改后 `霞.改`

![xia_g](../Output/gallery_v2/thumbs/xia_g.webp)

- [ ] 这条不换
### 翔鹤 · `xianghe_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `翔鹤`

![xianghe_memory](../Output/gallery_v2/thumbs/xianghe_memory.webp)

- [ ] 这条不换
### 西弗吉尼亚 · `xifujiniya_2` — 名字塌了(==船名)

改前 `皮肤2` → 改后 `西弗吉尼亚`

![xifujiniya_2](../Output/gallery_v2/thumbs/xifujiniya_2.webp)

- [ ] 这条不换
### 新月 · `xinyue_jp` — 名字塌了(==船名)

改前 `jp` → 改后 `新月`

![xinyue_jp](../Output/gallery_v2/thumbs/xinyue_jp.webp)

- [ ] 这条不换
### 希佩尔海军上将(μ兵装) · `xipeier_idol` — 名字塌了(==船名)

改前 `idol` → 改后 `希佩尔海军上将(μ兵装)`

![xipeier_idol](../Output/gallery_v2/thumbs/xipeier_idol.webp)

- [ ] 这条不换
### 希佩尔海军上将(μ兵装) · `xipeier_idolns` — 名字塌了(==船名)

改前 `idolns` → 改后 `希佩尔海军上将(μ兵装)`

![xipeier_idolns](../Output/gallery_v2/thumbs/xipeier_idolns.webp)

- [ ] 这条不换
### 伊莉丝 · `yilisi_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `伊莉丝`

![yilisi_doa](../Output/gallery_v2/thumbs/yilisi_doa.webp)

- [ ] 这条不换
### 逸仙 · `yixian_memory` — 名字塌了(==船名)

改前 `memory` → 改后 `逸仙`

![yixian_memory](../Output/gallery_v2/thumbs/yixian_memory.webp)

- [ ] 这条不换
### 优米雅·利斯菲尔德 · `youmiya_wjz` — 名字塌了(==船名)

改前 `wjz` → 改后 `优米雅·利斯菲尔德`

![youmiya_wjz](../Output/gallery_v2/thumbs/youmiya_wjz.webp)

- [ ] 这条不换
### 约克 · `yueke_ger` — 名字塌了(==船名)

改前 `ger` → 改后 `约克`

![yueke_ger](../Output/gallery_v2/thumbs/yueke_ger.webp)

- [ ] 这条不换
### 凪咲 · `zhixiao_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `凪咲`

![zhixiao_doa](../Output/gallery_v2/thumbs/zhixiao_doa.webp)

- [ ] 这条不换
### 凪咲 · `zhixiao_doa_wjz` — 名字塌了(==船名)

改前 `doa·wjz` → 改后 `凪咲`

![zhixiao_doa_wjz](../Output/gallery_v2/thumbs/zhixiao_doa_wjz.webp)

- [ ] 这条不换
### 筑紫 · `zhuzi_doa` — 名字塌了(==船名)

改前 `doa` → 改后 `筑紫`

![zhuzi_doa](../Output/gallery_v2/thumbs/zhuzi_doa.webp)

- [ ] 这条不换
### 八舞耶俱矢·八舞夕弦 · `bawu_2` — 长度异常

改前 `皮肤2` → 改后 `Blue Ocean Rendezvous`

![bawu_2](../Output/gallery_v2/thumbs/bawu_2.webp)

- [ ] 这条不换
### 八舞耶俱矢·八舞夕弦 · `bawu_2_hx` — 长度异常

改前 `皮肤2·和谐版` → 改后 `Blue Ocean Rendezvous·和谐版`

![bawu_2_hx](../Output/gallery_v2/thumbs/bawu_2_hx.webp)

- [ ] 这条不换
### 八舞耶俱矢·八舞夕弦 · `bawu_2_n` — 长度异常

改前 `皮肤2·无背景版` → 改后 `Blue Ocean Rendezvous·无背景版`

![bawu_2_n](../Output/gallery_v2/thumbs/bawu_2_n.webp)

- [ ] 这条不换
### 八舞耶俱矢·八舞夕弦 · `bawu_2_n_hx` — 长度异常

改前 `皮肤2·无背景版·和谐版` → 改后 `Blue Ocean Rendezvous·和谐版·无背景版`

![bawu_2_n_hx](../Output/gallery_v2/thumbs/bawu_2_n_hx.webp)

- [ ] 这条不换
### 标枪 · `biaoqiang_10` — 长度异常

改前 `皮肤10` → 改后 `PINKLOVE★Heart Lancer`

![biaoqiang_10](../Output/gallery_v2/thumbs/biaoqiang_10.webp)

- [ ] 这条不换
### 标枪 · `biaoqiang_10_n` — 长度异常

改前 `皮肤10·无背景版` → 改后 `PINKLOVE★Heart Lancer·无背景版`

![biaoqiang_10_n](../Output/gallery_v2/thumbs/biaoqiang_10_n.webp)

- [ ] 这条不换
### 柴郡 · `chaijun_h` — 长度异常

改前 `h` → 改后 `White Seaside Melody！`

![chaijun_h](../Output/gallery_v2/thumbs/chaijun_h.webp)

- [ ] 这条不换
### 柴郡 · `chaijun_h_n` — 长度异常

改前 `h·无背景版` → 改后 `White Seaside Melody！·无背景版`

![chaijun_h_n](../Output/gallery_v2/thumbs/chaijun_h_n.webp)

- [ ] 这条不换
### 黑太子 · `heitaizi_h` — 长度异常

改前 `h` → 改后 `Love's Greeting（爱的礼赞）`

![heitaizi_h](../Output/gallery_v2/thumbs/heitaizi_h.webp)

- [ ] 这条不换
### 黑太子 · `heitaizi_h_n` — 长度异常

改前 `h·无背景版` → 改后 `Love's Greeting（爱的礼赞）·无背景版`

![heitaizi_h_n](../Output/gallery_v2/thumbs/heitaizi_h_n.webp)

- [ ] 这条不换
### 乌尔里希·冯·胡滕 · `wuerlixi_h` — 长度异常

改前 `h` → 改后 `Liebestrank（迷魂酒/爱情魔药）`

![wuerlixi_h](../Output/gallery_v2/thumbs/wuerlixi_h.webp)

- [ ] 这条不换
### 乌尔里希·冯·胡滕 · `wuerlixi_h_n` — 长度异常

改前 `h·无背景版` → 改后 `Liebestrank（迷魂酒/爱情魔药）·无背景版`

![wuerlixi_h_n](../Output/gallery_v2/thumbs/wuerlixi_h_n.webp)

- [ ] 这条不换

## 二、全量对照（3033 条，按船分组，可直接 grep）

| 船 | 皮肤键 | 改前 | 改后 |
|---|---|---|---|
| 2B | `2b_2` | 皮肤2 | **须臾的休憩** |
| 2B | `2b_2_n` | 皮肤2·无背景版 | **须臾的休憩·无背景版** |
| A2 | `a2_2` | 皮肤2 | **禁忌的果实** |
| A2 | `a2_2_n` | 皮肤2·无背景版 | **禁忌的果实·无背景版** |
| 阿贝克隆比 | `abeikelongbi_2` | 皮肤2 | **惊叫南瓜！** |
| 阿贝克隆比 | `abeikelongbi_3` | 皮肤3 | **坏坏兔的恶作剧！** |
| 阿贝克隆比 | `abeikelongbi_3_hx` | 皮肤3·和谐版 | **坏坏兔的恶作剧！·和谐版** |
| 阿贝克隆比 | `abeikelongbi_4` | 皮肤4 | **海上的猫鼠游戏** |
| 阿贝克隆比 | `abeikelongbi_4_n` | 皮肤4·无背景版 | **海上的猫鼠游戏·无背景版** |
| 阿布鲁齐公爵 | `abuluqi_2` | 皮肤2 | **漆黑的人鱼公主** |
| 阿布鲁齐公爵 | `abuluqi_2_hx` | 皮肤2·和谐版 | **漆黑的人鱼公主·和谐版** |
| 阿布鲁齐公爵 | `abuluqi_2_n` | 皮肤2·无背景版 | **漆黑的人鱼公主·无背景版** |
| 阿布鲁齐公爵 | `abuluqi_2_n_hx` | 皮肤2·无背景版·和谐版 | **漆黑的人鱼公主·和谐版·无背景版** |
| 阿达尔伯特亲王 | `adaerbote_2` | 皮肤2 | **闭店后的特别时光** |
| 阿达尔伯特亲王 | `adaerbote_2_n` | 皮肤2·无背景版 | **闭店后的特别时光·无背景版** |
| 阿达尔伯特亲王 | `adaerbote_3` | 皮肤3 | **浴室中的小小意外** |
| 阿达尔伯特亲王 | `adaerbote_3_n` | 皮肤3·无背景版 | **浴室中的小小意外·无背景版** |
| 阿达尔伯特亲王 | `adaerbote_4` | 皮肤4 | **黑与白的魔术师** |
| 阿达尔伯特亲王 | `adaerbote_4_n` | 皮肤4·无背景版 | **黑与白的魔术师·无背景版** |
| 阿蒂利奥·雷戈洛 | `adiliao_2` | 皮肤2 | **灵感之巢** |
| 阿蒂利奥·雷戈洛 | `adiliao_2_n` | 皮肤2·无背景版 | **灵感之巢·无背景版** |
| 阿蒂利奥·雷戈洛 | `adiliao_3` | 皮肤3 | **云端降落的天使** |
| 阿蒂利奥·雷戈洛 | `adiliao_3_n` | 皮肤3·无背景版 | **云端降落的天使·无背景版** |
| 阿尔贝托·迪·朱塞诺 | `aerbeituo_2` | 皮肤2 | **华丽的“意外”** |
| 阿尔贝托·迪·朱塞诺 | `aerbeituo_2_n` | 皮肤2·无背景版 | **华丽的“意外”·无背景版** |
| 阿尔比恩 | `aerbien_2` | 皮肤2 | **银月下的夜之眷属** |
| 阿尔比恩 | `aerbien_2_n` | 皮肤2·无背景版 | **银月下的夜之眷属·无背景版** |
| 阿尔比恩 | `aerbien_3` | 皮肤3 | **香气来朱阁** |
| 阿尔比恩 | `aerbien_3_n` | 皮肤3·无背景版 | **香气来朱阁·无背景版** |
| 阿尔比恩 | `aerbien_4` | 皮肤4 | **晨光里的事故** |
| 阿尔比恩 | `aerbien_4_n` | 皮肤4·无背景版 | **晨光里的事故·无背景版** |
| 阿尔弗雷多·奥里亚尼 | `aerfuleiduo_2` | 皮肤2 | **华丽的Vivace** |
| 阿尔弗雷多·奥里亚尼 | `aerfuleiduo_2_n` | 皮肤2·无背景版 | **华丽的Vivace·无背景版** |
| 阿尔汉格尔斯克 | `aerhangeersike_2` | 皮肤2 | **择日而航** |
| 阿尔汉格尔斯克 | `aerhangeersike_2_n` | 皮肤2·无背景版 | **择日而航·无背景版** |
| 阿尔汉格尔斯克 | `aerhangeersike_3` | 皮肤3 | **与魔女同行** |
| 阿尔汉格尔斯克 | `aerhangeersike_3_n` | 皮肤3·无背景版 | **与魔女同行·无背景版** |
| 阿尔及利亚-王国军方旗骑士 | `aerjiliya_2` | 皮肤2 | **白沙天堂** |
| 阿尔及利亚-王国军方旗骑士 | `aerjiliya_2_hx` | 皮肤2·和谐版 | **白沙天堂·和谐版** |
| 阿尔及利亚-王国军方旗骑士 | `aerjiliya_2_n` | 皮肤2·无背景版 | **白沙天堂·无背景版** |
| 阿尔及利亚-王国军方旗骑士 | `aerjiliya_2_n_hx` | 皮肤2·无背景版·和谐版 | **白沙天堂·和谐版·无背景版** |
| 阿尔及利亚-王国军方旗骑士 | `aerjiliya_3` | 皮肤3 | **红桃皇后的审判** |
| 阿尔及利亚-王国军方旗骑士 | `aerjiliya_3_n` | 皮肤3·无背景版 | **红桃皇后的审判·无背景版** |
| 阿尔萨斯 | `aersasi_2` | 皮肤2 | **盛夏的圣迹** |
| 阿尔萨斯 | `aersasi_2_n` | 皮肤2·无背景版 | **盛夏的圣迹·无背景版** |
| 阿尔萨斯 | `aersasi_3` | 皮肤3 | **圣宵之鬼的微醺** |
| 阿尔萨斯 | `aersasi_3_n` | 皮肤3·无背景版 | **圣宵之鬼的微醺·无背景版** |
| 阿芙乐尔 | `afuleer_2` | 皮肤2 | **囚塔中的曙光公主** |
| 阿芙乐尔 | `afuleer_2_n` | 皮肤2·无背景版 | **囚塔中的曙光公主·无背景版** |
| 阿芙乐尔 | `afuleer_3` | 皮肤3 | **略勉强的角色扮演?** |
| 阿芙乐尔 | `afuleer_3_n` | 皮肤3·无背景版 | **略勉强的角色扮演?·无背景版** |
| 阿芙乐尔 | `afuleer_4` | 皮肤4 | **微醺的海风** |
| 阿芙乐尔 | `afuleer_4_n` | 皮肤4·无背景版 | **微醺的海风·无背景版** |
| 阿贺野 | `aheye_2` | 皮肤2 | **约会游戏？** |
| 阿贺野 | `aheye_3` | 皮肤3 | **圣夜的小小捉弄** |
| 阿贺野 | `aheye_4` | 皮肤4 | **告白的蓝闪蝶** |
| 爱宕 | `aidang_2` | 皮肤2 | **盛夏进行曲** |
| 爱宕 | `aidang_3` | 皮肤3 | **冬季风物诗** |
| 爱宕 | `aidang_4` | 皮肤4 | **学园幻想曲** |
| 爱宕 | `aidang_5` | 皮肤5 | **巅峰时速** |
| 爱宕 | `aidang_5_n` | 皮肤5·无背景版 | **巅峰时速·无背景版** |
| 爱宕 | `aidang_6` | 皮肤6 | **满月之夜的狼** |
| 爱宕 | `aidang_6_hx` | 皮肤6·和谐版 | **满月之夜的狼·和谐版** |
| 爱宕 | `aidang_6_n` | 皮肤6·无背景版 | **满月之夜的狼·无背景版** |
| 爱宕 | `aidang_6_n_hx` | 皮肤6·无背景版·和谐版 | **满月之夜的狼·和谐版·无背景版** |
| 爱宕 | `aidang_h` | h | **白花的誓言** |
| 爱丁堡 | `aidingbao_2` | 皮肤2 | **图书室的妖精** |
| 爱丁堡 | `aidingbao_3` | 皮肤3 | **Candy Maid** |
| 埃尔宾 | `aierbin_2` | 皮肤2 | **幻梦的普洛塞庇娜** |
| 埃尔宾 | `aierbin_2_n` | 皮肤2·无背景版 | **幻梦的普洛塞庇娜·无背景版** |
| 埃尔宾 | `aierbin_3` | 皮肤3 | **不眠之夜的愿望** |
| 埃尔宾 | `aierbin_3_n` | 皮肤3·无背景版 | **不眠之夜的愿望·无背景版** |
| 埃尔宾 | `aierbin_4` | 皮肤4 | **春灯佳人** |
| 埃尔宾 | `aierbin_4_n` | 皮肤4·无背景版 | **春灯佳人·无背景版** |
| 埃尔德里奇 | `aierdeliqi_2` | 皮肤2 | **圣夜的拥抱** |
| 埃尔德里奇 | `aierdeliqi_3` | 皮肤3 | **空教室的不可思议** |
| 埃尔德里奇 | `aierdeliqi_4` | 皮肤4 | **正月的牵手** |
| 埃尔德里奇 | `aierdeliqi_5` | 皮肤5 | **喵喵偶像团？** |
| 埃尔德里奇 | `aierdeliqi_7` | 皮肤7 | **太空中秋节** |
| 埃尔德里奇 | `aierdeliqi_7_n` | 皮肤7·无背景版 | **太空中秋节·无背景版** |
| 埃尔德里奇 | `aierdeliqi_8` | 皮肤8 | **美好的放学时刻** |
| 埃尔德里奇 | `aierdeliqi_8_n` | 皮肤8·无背景版 | **美好的放学时刻·无背景版** |
| 埃尔德里奇 | `aierdeliqi_9` | 皮肤9 | **金月桂香** |
| 埃尔德里奇 | `aierdeliqi_9_n` | 皮肤9·无背景版 | **金月桂香·无背景版** |
| 埃尔德里奇 | `aierdeliqi_g` | G | **埃尔德里奇.改** |
| 埃尔德里奇 | `aierdeliqi_g_n` | G·无背景版 | **埃尔德里奇.改·无背景版** |
| 埃尔德里奇 | `aierdeliqi_h` | h | **相约于林荫暖阳** |
| 埃尔德里奇 | `aierdeliqi_h_n` | h·无背景版 | **相约于林荫暖阳·无背景版** |
| 艾尔温 | `aierwen_2` | 皮肤2 | **星期天的水族馆** |
| 艾尔温 | `aierwen_2_n` | 皮肤2·无背景版 | **星期天的水族馆·无背景版** |
| 埃佛森 | `aifosen_2` | 皮肤2 | **落于窗台的暖阳** |
| 埃佛森 | `aifosen_2_n` | 皮肤2·无背景版 | **落于窗台的暖阳·无背景版** |
| 埃佛森 | `aifosen_3` | 皮肤3 | **红树林的守护精灵** |
| 埃佛森 | `aifosen_3_n` | 皮肤3·无背景版 | **红树林的守护精灵·无背景版** |
| 绊爱 | `aijiangdd_2` | 皮肤2 | **Sakura Festival** |
| 埃吉尔 | `aijier_2` | 皮肤2 | **港区的龙女仆** |
| 埃吉尔 | `aijier_2_n` | 皮肤2·无背景版 | **港区的龙女仆·无背景版** |
| 埃吉尔 | `aijier_3` | 皮肤3 | **金龙腾祥云** |
| 埃吉尔 | `aijier_3_hx` | 皮肤3·和谐版 | **金龙腾祥云·和谐版** |
| 埃吉尔 | `aijier_3_n` | 皮肤3·无背景版 | **金龙腾祥云·无背景版** |
| 埃吉尔 | `aijier_3_n_hx` | 皮肤3·无背景版·和谐版 | **金龙腾祥云·和谐版·无背景版** |
| 埃吉尔 | `aijier_4` | 皮肤4 | **私密闲暇时** |
| 埃吉尔 | `aijier_4_hx` | 皮肤4·和谐版 | **私密闲暇时·和谐版** |
| 埃吉尔 | `aijier_4_n` | 皮肤4·无背景版 | **私密闲暇时·无背景版** |
| 埃吉尔 | `aijier_younv` | younv | **小埃吉尔** |
| 埃吉尔 | `aijier_younv_n` | younv·无背景版 | **小埃吉尔·无背景版** |
| 埃克塞特 | `aikesaite_2` | 皮肤2 | **荣耀与举杯同在** |
| 埃克塞特 | `aikesaite_2_n` | 皮肤2·无背景版 | **荣耀与举杯同在·无背景版** |
| 埃克塞特 | `aikesaite_g` | G | **埃克塞特.改** |
| 艾菈·冯·杜勒 | `aila_2` | 皮肤2 | **假日的户外风格** |
| 艾菈·冯·杜勒 | `aila_2_n` | 皮肤2·无背景版 | **假日的户外风格·无背景版** |
| 艾菈·冯·杜勒 | `aila_wjz` | wjz | **艾菈·冯·杜勒** ⚠名字塌了(==船名) |
| 艾伦·萨姆纳 | `ailunsamuna_2` | 皮肤2 | **Charming Rabbit** |
| 艾伦·萨姆纳 | `ailunsamuna_2_hx` | 皮肤2·和谐版 | **Charming Rabbit·和谐版** |
| 艾伦·萨姆纳 | `ailunsamuna_2_n` | 皮肤2·无背景版 | **Charming Rabbit·无背景版** |
| 艾伦·萨姆纳 | `ailunsamuna_2_n_hx` | 皮肤2·无背景版·和谐版 | **Charming Rabbit·和谐版·无背景版** |
| 艾伦·萨姆纳 | `ailunsamuna_3` | 皮肤3 | **双面侠盗** |
| 艾伦·萨姆纳 | `ailunsamuna_3_n` | 皮肤3·无背景版 | **双面侠盗·无背景版** |
| 埃曼努埃尔·佩萨格诺 | `aimannuaier_2` | 皮肤2 | **后台准备时间** |
| 埃曼努埃尔·佩萨格诺 | `aimannuaier_2_n` | 皮肤2·无背景版 | **后台准备时间·无背景版** |
| 埃米尔·贝尔汀 | `aimierbeierding_2` | 皮肤2 | **蓝色海岸** |
| 埃米尔·贝尔汀 | `aimierbeierding_3` | 皮肤3 | **「女仆」浪漫** |
| 埃米尔·贝尔汀 | `aimierbeierding_3_hx` | 皮肤3·和谐版 | **「女仆」浪漫·和谐版** |
| 埃米尔·贝尔汀 | `aimierbeierding_4` | 皮肤4 | **芬芳的舞姬** |
| 埃米尔·贝尔汀 | `aimierbeierding_4_n` | 皮肤4·无背景版 | **芬芳的舞姬·无背景版** |
| 埃米尔·贝尔汀 | `aimierbeierding_5` | 皮肤5 | **闪耀的“魔法”** |
| 埃米尔·贝尔汀 | `aimierbeierding_5_n` | 皮肤5·无背景版 | **闪耀的“魔法”·无背景版** |
| 埃米尔·贝尔汀 | `aimierbeierding_g` | G | **埃米尔·贝尔汀.改** |
| 埃姆登 | `aimudeng_2` | 皮肤2 | **黑白的夜之主** |
| 埃姆登 | `aimudeng_2_hx` | 皮肤2·和谐版 | **黑白的夜之主·和谐版** |
| 埃姆登 | `aimudeng_2_n` | 皮肤2·无背景版 | **黑白的夜之主·无背景版** |
| 埃姆登 | `aimudeng_3` | 皮肤3 | **探求的水月之涧** |
| 埃姆登 | `aimudeng_4` | 皮肤4 | **引路的双轨极星** |
| 埃姆登 | `aimudeng_4_npc` | 皮肤4·npc | **埃姆登** ⚠名字塌了(==船名) |
| 埃姆登 | `aimudeng_5` | 皮肤5 | **水畔的夕暮私语** |
| 埃姆登 | `aimudeng_5_asmr` | 皮肤5·ASMR | **水畔的夕暮私语** |
| 埃姆登 | `aimudeng_5_n` | 皮肤5·无背景版 | **水畔的夕暮私语·无背景版** |
| 埃塞克斯 | `aisaikesi_10` | 皮肤10 | **泳池里的默契训练** |
| 埃塞克斯 | `aisaikesi_10_hx` | 皮肤10·和谐版 | **泳池里的默契训练·和谐版** |
| 埃塞克斯 | `aisaikesi_10_n` | 皮肤10·无背景版 | **泳池里的默契训练·无背景版** |
| 埃塞克斯 | `aisaikesi_10_n_hx` | 皮肤10·无背景版·和谐版 | **泳池里的默契训练·和谐版·无背景版** |
| 埃塞克斯 | `aisaikesi_3` | 皮肤3 | **66号公路之旅** |
| 埃塞克斯 | `aisaikesi_4` | 皮肤4 | **Craft Fairytail** |
| 埃塞克斯 | `aisaikesi_4_n` | 皮肤4·无背景版 | **Craft Fairytail·无背景版** |
| 埃塞克斯 | `aisaikesi_5` | 皮肤5 | **笔墨乾坤** |
| 埃塞克斯 | `aisaikesi_5_n` | 皮肤5·无背景版 | **笔墨乾坤·无背景版** |
| 埃塞克斯 | `aisaikesi_6` | 皮肤6 | **名侦探·埃塞克斯** |
| 埃塞克斯 | `aisaikesi_6_n` | 皮肤6·无背景版 | **名侦探·埃塞克斯·无背景版** |
| 埃塞克斯 | `aisaikesi_7` | 皮肤7 | **碧海之梦** |
| 埃塞克斯 | `aisaikesi_7_n` | 皮肤7·无背景版 | **碧海之梦·无背景版** |
| 埃塞克斯 | `aisaikesi_8` | 皮肤8 | **赛道88之风** |
| 埃塞克斯 | `aisaikesi_8_n` | 皮肤8·无背景版 | **赛道88之风·无背景版** |
| 埃塞克斯 | `aisaikesi_9` | 皮肤9 | **水漾在疾驰之前** |
| 埃塞克斯 | `aisaikesi_9_n` | 皮肤9·无背景版 | **水漾在疾驰之前·无背景版** |
| 埃塞克斯 | `aisaikesi_alter` | alter | **埃塞克斯·META** |
| 埃塞克斯 | `aisaikesi_alter_n` | alter·无背景版 | **埃塞克斯·META·无背景版** |
| 埃塞克斯 | `aisaikesi_g` | G | **埃塞克斯.改** |
| 埃塞克斯 | `aisaikesi_g_n` | G·无背景版 | **埃塞克斯.改·无背景版** |
| 爱斯基摩人 | `aisijimo_2` | 皮肤2 | **海边的“问题儿童”** |
| 爱斯基摩人 | `aisijimo_2_n` | 皮肤2·无背景版 | **海边的“问题儿童”·无背景版** |
| 阿贾克斯 | `ajiakesi_2` | 皮肤2 | **晚会女王** |
| 阿贾克斯 | `ajiakesi_3` | 皮肤3 | **节日的“特别奖励”** |
| 阿贾克斯 | `ajiakesi_3_n` | 皮肤3·无背景版 | **节日的“特别奖励”·无背景版** |
| 阿贾克斯 | `ajiakesi_g` | G | **阿贾克斯.改** |
| 阿基里斯 | `ajilisi_g` | G | **阿基里斯.改** |
| 阿卡司塔 | `akasita_2` | 皮肤2 | **外出模式** |
| 阿卡司塔 | `akasita_3` | 皮肤3 | **元宵灯会** |
| 阿卡司塔 | `akasita_4` | 皮肤4 | **「白」与「黑」** |
| 阿卡司塔 | `akasita_4_n` | 皮肤4·无背景版 | **「白」与「黑」·无背景版** |
| 阿卡司塔 | `akasita_g` | G | **阿卡司塔.改** |
| 阿拉巴马 | `alabama_2` | 皮肤2 | **金锱银铢** |
| 阿拉巴马 | `alabama_3` | 皮肤3 | **予你的镜头** |
| 阿拉巴马 | `alabama_3_n` | 皮肤3·无背景版 | **予你的镜头·无背景版** |
| 阿罗芒什 | `aluomangshi_2` | 皮肤2 | **足尖弓矢** |
| 阿罗芒什 | `aluomangshi_2_n` | 皮肤2·无背景版 | **足尖弓矢·无背景版** |
| 安德烈亚·多利亚 | `andelieyaduoliya_2` | 皮肤2 | **安心舒适之旅** |
| 安克雷奇 | `ankeleiqi_2` | 皮肤2 | **海豚、海洋、游泳课** |
| 安克雷奇 | `ankeleiqi_2_hx` | 皮肤2·和谐版 | **海豚、海洋、游泳课·和谐版** |
| 安克雷奇 | `ankeleiqi_2_n` | 皮肤2·无背景版 | **海豚、海洋、游泳课·无背景版** |
| 安克雷奇 | `ankeleiqi_2_n_hx` | 皮肤2·无背景版·和谐版 | **海豚、海洋、游泳课·和谐版·无背景版** |
| 安克雷奇 | `ankeleiqi_3` | 皮肤3 | **舟畔共明月** |
| 安克雷奇 | `ankeleiqi_3_n` | 皮肤3·无背景版 | **舟畔共明月·无背景版** |
| 安克雷奇 | `ankeleiqi_4` | 皮肤4 | **香甜牛奶味之夜** |
| 安克雷奇 | `ankeleiqi_4_n` | 皮肤4·无背景版 | **香甜牛奶味之夜·无背景版** |
| 安克雷奇 | `ankeleiqi_h` | h | **落日与烟花的誓言** |
| 安克雷奇 | `ankeleiqi_younv` | younv | **小安克雷奇** |
| 安克雷奇 | `ankeleiqi_younv_n` | younv·无背景版 | **小安克雷奇·无背景版** |
| 安妮女王复仇号 | `anninvwang_2` | 皮肤2 | **隐秘之拥的呼唤** |
| 安妮女王复仇号 | `anninvwang_2_n` | 皮肤2·无背景版 | **隐秘之拥的呼唤·无背景版** |
| 鞍山 | `anshan_2` | 皮肤2 | **和平的号角** |
| 鞍山 | `anshan_3` | 皮肤3 | **夕照伊人** |
| 鞍山 | `anshan_g` | G | **鞍山.改** |
| 鞍山 | `anshan_g_n` | G·无背景版 | **鞍山.改·无背景版** |
| 安土 | `antu_2` | 皮肤2 | **午夜的瑰色电梯** |
| 安土 | `antu_2_hx` | 皮肤2·和谐版 | **午夜的瑰色电梯·和谐版** |
| 安土 | `antu_3` | 皮肤3 | **午夜的瑰色电梯** |
| 安土 | `antu_3_n` | 皮肤3·无背景版 | **午夜的瑰色电梯·无背景版** |
| 奥丁 | `aoding_2` | 皮肤2 | **挥毫苍雪** |
| 奥古斯特·冯·帕塞瓦尔 | `aogusite_2` | 皮肤2 | **女仆魔女** |
| 奥古斯特·冯·帕塞瓦尔 | `aogusite_2_n` | 皮肤2·无背景版 | **女仆魔女·无背景版** |
| 奥古斯特·冯·帕塞瓦尔 | `aogusite_3` | 皮肤3 | **被阳光照亮之时** |
| 奥古斯特·冯·帕塞瓦尔 | `aogusite_3_n` | 皮肤3·无背景版 | **被阳光照亮之时·无背景版** |
| 奥古斯特·冯·帕塞瓦尔 | `aogusite_4` | 皮肤4 | **与“魔女”的星夜之约** |
| 奥古斯特·冯·帕塞瓦尔 | `aogusite_4_n` | 皮肤4·无背景版 | **与“魔女”的星夜之约·无背景版** |
| 奥列格 | `aoliege_2` | 皮肤2 | **壁炉旁的慵懒时光** |
| 奥列格 | `aoliege_2_n` | 皮肤2·无背景版 | **壁炉旁的慵懒时光·无背景版** |
| 查尔斯·奥斯本 | `aosiben_g` | G | **查尔斯·奥斯本.改** |
| 查尔斯·奥斯本 | `aosiben_g_n` | G·无背景版 | **查尔斯·奥斯本.改·无背景版** |
| 奥托·冯·阿尔文斯莱本 | `aotuo_2` | 皮肤2 | **猎物与陷阱？** |
| 奥托·冯·阿尔文斯莱本 | `aotuo_2_n` | 皮肤2·无背景版 | **猎物与陷阱？·无背景版** |
| 奥托·冯·阿尔文斯莱本 | `aotuo_3` | 皮肤3 | **笨女仆大危机？！** |
| 奥托·冯·阿尔文斯莱本 | `aotuo_3_hx` | 皮肤3·和谐版 | **笨女仆大危机？！·和谐版** |
| 奥托·冯·阿尔文斯莱本 | `aotuo_3_n` | 皮肤3·无背景版 | **笨女仆大危机？！·无背景版** |
| 奥托·冯·阿尔文斯莱本 | `aotuo_3_n_hx` | 皮肤3·无背景版·和谐版 | **笨女仆大危机？！·和谐版·无背景版** |
| 阿斯托利亚 | `asituoliya_2` | 皮肤2 | **黑兔嘉年华** |
| 阿斯托利亚 | `asituoliya_2_hx` | 皮肤2·和谐版 | **黑兔嘉年华·和谐版** |
| 阿斯托利亚 | `asituoliya_2_n` | 皮肤2·无背景版 | **黑兔嘉年华·无背景版** |
| 阿斯托利亚 | `asituoliya_2_n_hx` | 皮肤2·无背景版·和谐版 | **黑兔嘉年华·和谐版·无背景版** |
| 阿斯托利亚 | `asituoliya_3` | 皮肤3 | **清纯系辣妹？** |
| 阿武隈 | `awuwei_g` | G | **阿武隈.改** |
| 巴丹 | `badan_2` | 皮肤2 | **软绵绵睡衣** |
| 巴尔的摩 | `baerdimo_2` | 皮肤2 | **放学后的ACE** |
| 巴尔的摩 | `baerdimo_3` | 皮肤3 | **ACE的旅行记** |
| 巴尔的摩 | `baerdimo_3_n` | 皮肤3·无背景版 | **ACE的旅行记·无背景版** |
| 巴尔的摩 | `baerdimo_4` | 皮肤4 | **Black Ace** |
| 巴尔的摩 | `baerdimo_4_n` | 皮肤4·无背景版 | **Black Ace·无背景版** |
| 巴尔的摩 | `baerdimo_5` | 皮肤5 | **夜风Minuet** |
| 巴尔的摩 | `baerdimo_6` | 皮肤6 | **迅疾的蓝星** |
| 巴尔的摩 | `baerdimo_6_n` | 皮肤6·无背景版 | **迅疾的蓝星·无背景版** |
| 巴尔的摩 | `baerdimo_h` | h | **微风拂过之时** |
| 巴尔的摩 | `baerdimo_h_n` | h·无背景版 | **微风拂过之时·无背景版** |
| 巴尔的摩 | `baerdimo_idol` | idol | **巴尔的摩(μ兵装)** |
| 巴尔的摩 | `baerdimo_idol_n` | idol·无背景版 | **巴尔的摩(μ兵装)·无背景版** |
| 白凤 | `baifeng_2` | 皮肤2 | **缭乱之花的忍者游戏** |
| 白凤 | `baifeng_2_n` | 皮肤2·无背景版 | **缭乱之花的忍者游戏·无背景版** |
| 白凤 | `baifeng_3` | 皮肤3 | **晴雨狐嫁** |
| 白凤 | `baifeng_3_n` | 皮肤3·无背景版 | **晴雨狐嫁·无背景版** |
| 白龙 | `bailong_2` | 皮肤2 | **快刀女仆？** |
| 白龙 | `bailong_2_n` | 皮肤2·无背景版 | **快刀女仆？·无背景版** |
| 白龙 | `bailong_3` | 皮肤3 | **丝竹喧阗** |
| 白龙 | `bailong_3_n` | 皮肤3·无背景版 | **丝竹喧阗·无背景版** |
| 白龙 | `bailong_4` | 皮肤4 | **龙雕百炼** |
| 白龙 | `bailong_4_n` | 皮肤4·无背景版 | **龙雕百炼·无背景版** |
| 白龙 | `bailong_5` | 皮肤5 | **薄织四叠** |
| 白龙 | `bailong_5_n` | 皮肤5·无背景版 | **薄织四叠·无背景版** |
| 白露 | `bailu_2` | 皮肤2 | **要来点鱼雷吗？** |
| 白露 | `bailu_3` | 皮肤3 | **雪融烟火夜** |
| 白露 | `bailu_3_n` | 皮肤3·无背景版 | **雪融烟火夜·无背景版** |
| 白露 | `bailu_g` | G | **白露.改** |
| 白露 | `bailu_g_n` | G·无背景版 | **白露.改·无背景版** |
| 白雪 | `baixue_2` | 皮肤2 | **白兔饲养员** |
| 白雪 | `baixue_2_n` | 皮肤2·无背景版 | **白兔饲养员·无背景版** |
| 百眼巨人 | `baiyanjuren_2` | 皮肤2 | **学园之眠不觉晓** |
| 百眼巨人 | `baiyanjuren_2_n` | 皮肤2·无背景版 | **学园之眠不觉晓·无背景版** |
| 百眼巨人 | `baiyanjuren_3` | 皮肤3 | **雅致的试衣间** |
| 百眼巨人 | `baiyanjuren_3_n` | 皮肤3·无背景版 | **雅致的试衣间·无背景版** |
| 百眼巨人 | `baiyanjuren_4` | 皮肤4 | **特训中的威严之人** |
| 百眼巨人 | `baiyanjuren_4_hx` | 皮肤4·和谐版 | **特训中的威严之人·和谐版** |
| 百眼巨人 | `baiyanjuren_4_n` | 皮肤4·无背景版 | **特训中的威严之人·无背景版** |
| 百眼巨人 | `baiyanjuren_4_n_hx` | 皮肤4·无背景版·和谐版 | **特训中的威严之人·和谐版·无背景版** |
| 巴拉卡少校 | `balaka_2` | 皮肤2 | **死亡之神的戏谑** |
| 巴拉卡少校 | `balaka_2_hx` | 皮肤2·和谐版 | **死亡之神的戏谑·和谐版** |
| 巴拉卡少校 | `balaka_2_n` | 皮肤2·无背景版 | **死亡之神的戏谑·无背景版** |
| 巴拉卡少校 | `balaka_2_n_hx` | 皮肤2·无背景版·和谐版 | **死亡之神的戏谑·和谐版·无背景版** |
| 伴尔维 | `banerwei_2` | 皮肤2 | **俩人的柔软体操** |
| 伴尔维 | `banerwei_2_n` | 皮肤2·无背景版 | **俩人的柔软体操·无背景版** |
| 伴尔维 | `banerwei_3` | 皮肤3 | **清凉的甜蜜滋味** |
| 伴尔维 | `banerwei_3_hx` | 皮肤3·和谐版 | **清凉的甜蜜滋味·和谐版** |
| 伴尔维 | `banerwei_3_n` | 皮肤3·无背景版 | **清凉的甜蜜滋味·无背景版** |
| 伴尔维 | `banerwei_3_n_hx` | 皮肤3·无背景版·和谐版 | **清凉的甜蜜滋味·和谐版·无背景版** |
| 滨风 | `bangfeng_2` | 皮肤2 | **模范优等生** |
| 滨风 | `bangfeng_4` | 皮肤4 | **美味的关键是爱？！** |
| 滨风 | `bangfeng_4_n` | 皮肤4·无背景版 | **美味的关键是爱？！·无背景版** |
| 滨风 | `bangfeng_g` | G | **滨风.改** |
| 邦克山 | `bangkeshan_2` | 皮肤2 | **纵情假日** |
| 邦克山 | `bangkeshan_2_hx` | 皮肤2·和谐版 | **纵情假日·和谐版** |
| 邦克山 | `bangkeshan_2_n` | 皮肤2·无背景版 | **纵情假日·无背景版** |
| 邦克山 | `bangkeshan_2_n_hx` | 皮肤2·无背景版·和谐版 | **纵情假日·和谐版·无背景版** |
| 斑鸠 | `banjiu_2` | 皮肤2 | **片刻小憩** |
| 斑鸠 | `banjiu_2_n` | 皮肤2·无背景版 | **片刻小憩·无背景版** |
| 半人马 | `banrenma_2` | 皮肤2 | **沙滨的水之精灵** |
| 半人马 | `banrenma_3` | 皮肤3 | **清冽的春风** |
| 宝多六花 | `baoduoliuhua_2` | 皮肤2 | **晴空的车站** |
| 宝多六花 | `baoduoliuhua_2_n` | 皮肤2·无背景版 | **晴空的车站·无背景版** |
| 宝多六花 | `baoduoliuhua_3` | 皮肤3 | **家居小憩** |
| 宝多六花 | `baoduoliuhua_3_n` | 皮肤3·无背景版 | **家居小憩·无背景版** |
| 巴托洛梅奥·科莱奥尼 | `batuoluomeiao_2` | 皮肤2 | **艳后的浪漫攻心计** |
| 巴托洛梅奥·科莱奥尼 | `batuoluomeiao_2_n` | 皮肤2·无背景版 | **艳后的浪漫攻心计·无背景版** |
| 八舞耶俱矢·八舞夕弦 | `bawu_2` | 皮肤2 | **Blue Ocean Rendezvous** ⚠长度异常 |
| 八舞耶俱矢·八舞夕弦 | `bawu_2_hx` | 皮肤2·和谐版 | **Blue Ocean Rendezvous·和谐版** ⚠长度异常 |
| 八舞耶俱矢·八舞夕弦 | `bawu_2_n` | 皮肤2·无背景版 | **Blue Ocean Rendezvous·无背景版** ⚠长度异常 |
| 八舞耶俱矢·八舞夕弦 | `bawu_2_n_hx` | 皮肤2·无背景版·和谐版 | **Blue Ocean Rendezvous·和谐版·无背景版** ⚠长度异常 |
| 八舞耶俱矢·八舞夕弦 | `bawu_n` | 无背景版 | **八舞耶俱矢・八舞夕弦·无背景版** |
| 北安普敦 | `beianpudunii_2` | 皮肤2 | **竞泳之星** |
| 北安普敦 | `beianpudunii_3` | 皮肤3 | **闲云野鹤** |
| 北安普敦 | `beianpudunii_3_n` | 皮肤3·无背景版 | **闲云野鹤·无背景版** |
| 北安普敦 | `beianpudunii_n` | 无背景版 | **北安普敦II·无背景版** |
| 贝尔 | `beier_2` | 皮肤2 | **酒馆中的小失误** |
| 贝尔 | `beier_2_n` | 皮肤2·无背景版 | **酒馆中的小失误·无背景版** |
| 贝尔法斯特 | `beierfasite_2` | 皮肤2 | **彩云之玫瑰** |
| 贝尔法斯特 | `beierfasite_3` | 皮肤3 | **优雅而高贵的从者** |
| 贝尔法斯特 | `beierfasite_4` | 皮肤4 | **女仆长的购物日** |
| 贝尔法斯特 | `beierfasite_5` | 皮肤5 | **凛冽的钢之从者** |
| 贝尔法斯特 | `beierfasite_7` | 皮肤7 | **完美的代理店长** |
| 贝尔法斯特 | `beierfasite_8` | 皮肤8 | **倾城之华扇** |
| 贝尔法斯特 | `beierfasite_9` | 皮肤9 | **至福的侍奉** |
| 贝尔法斯特 | `beierfasite_9_hx` | 皮肤9·和谐版 | **至福的侍奉·和谐版** |
| 贝尔法斯特 | `beierfasite_9_n` | 皮肤9·无背景版 | **至福的侍奉·无背景版** |
| 贝尔法斯特 | `beierfasite_9_n_hx` | 皮肤9·无背景版·和谐版 | **至福的侍奉·和谐版·无背景版** |
| 贝尔法斯特 | `beierfasite_g` | G | **贝尔法斯特·改** |
| 贝尔法斯特 | `beierfasite_g_n` | G·无背景版 | **贝尔法斯特·改·无背景版** |
| 贝尔法斯特 | `beierfasite_h` | h | **克拉达的誓约** |
| 贝尔法斯特 | `beierfasite_younv` | younv | **小贝法** |
| 北风 | `beifeng_2` | 皮肤2 | **祭典制霸！** |
| 北风 | `beifeng_2_n` | 皮肤2·无背景版 | **祭典制霸！·无背景版** |
| 北风 | `beifeng_4` | 皮肤4 | **鸽子与魔术之夜** |
| 北风 | `beifeng_4_n` | 皮肤4·无背景版 | **鸽子与魔术之夜·无背景版** |
| 北卡罗来纳 | `beikaluolaina_2` | 皮肤2 | **秘密的换装练习？** |
| 北卡罗来纳 | `beikaluolaina_2_hx` | 皮肤2·和谐版 | **秘密的换装练习？·和谐版** |
| 北卡罗来纳 | `beikaluolaina_2_n` | 皮肤2·无背景版 | **秘密的换装练习？·无背景版** |
| 北卡罗来纳 | `beikaluolaina_2_n_hx` | 皮肤2·无背景版·和谐版 | **秘密的换装练习？·和谐版·无背景版** |
| 北卡罗来纳 | `beikaluolaina_3` | 皮肤3 | **与阳光一同闪耀** |
| 北卡罗来纳 | `beikaluolaina_3_n` | 皮肤3·无背景版 | **与阳光一同闪耀·无背景版** |
| 贝劳森林 | `beilaosenlin_2` | 皮肤2 | **水色疗愈** |
| 贝劳森林 | `beilaosenlin_2_hx` | 皮肤2·和谐版 | **水色疗愈·和谐版** |
| 贝利 | `beili_2` | 皮肤2 | **捣蛋黑兔** |
| 贝利 | `beili_3` | 皮肤3 | **圣诞兔兔驾到！** |
| 贝利 | `beili_3_n` | 皮肤3·无背景版 | **圣诞兔兔驾到！·无背景版** |
| 贝利 | `beili_g` | G | **贝利.改** |
| 贝奇 | `beiqi_2` | 皮肤2 | **华丽的速度之星** |
| 贝奇 | `beiqi_3` | 皮肤3 | **炫目的赛场之星** |
| 贝奇 | `beiqi_3_n` | 皮肤3·无背景版 | **炫目的赛场之星·无背景版** |
| 贝亚德 | `beiyade_2` | 皮肤2 | **骑士的修行之“兔”！** |
| 贝亚德 | `beiyade_2_hx` | 皮肤2·和谐版 | **骑士的修行之“兔”！·和谐版** |
| 贝亚德 | `beiyade_2_n` | 皮肤2·无背景版 | **骑士的修行之“兔”！·无背景版** |
| 贝亚德 | `beiyade_2_n_hx` | 皮肤2·无背景版·和谐版 | **骑士的修行之“兔”！·和谐版·无背景版** |
| 贝亚恩 | `beiyaen_2` | 皮肤2 | **夏日救生站** |
| 贝亚恩 | `beiyaen_2_n` | 皮肤2·无背景版 | **夏日救生站·无背景版** |
| 本宁顿 | `benningdun_2` | 皮肤2 | **全速！盛夏逐光企划** |
| 本宁顿 | `benningdun_2_n` | 皮肤2·无背景版 | **全速！盛夏逐光企划·无背景版** |
| 本森 | `bensen_2` | 皮肤2 | **万圣兔兔美少女！** |
| 本森 | `bensen_2_n` | 皮肤2·无背景版 | **万圣兔兔美少女！·无背景版** |
| 标枪 | `biaoqiang_10` | 皮肤10 | **PINKLOVE★Heart Lancer** ⚠长度异常 |
| 标枪 | `biaoqiang_10_n` | 皮肤10·无背景版 | **PINKLOVE★Heart Lancer·无背景版** ⚠长度异常 |
| 标枪 | `biaoqiang_2` | 皮肤2 | **22娘** |
| 标枪 | `biaoqiang_3` | 皮肤3 | **沙滩野餐会** |
| 标枪 | `biaoqiang_4` | 皮肤4 | **一起成为服务生！** |
| 标枪 | `biaoqiang_5` | 皮肤5 | **微速前进！** |
| 标枪 | `biaoqiang_5_hx` | 皮肤5·和谐版 | **微速前进！·和谐版** |
| 标枪 | `biaoqiang_6` | 皮肤6 | **王道偶像·元气120！** |
| 标枪 | `biaoqiang_7` | 皮肤7 | **枕头大战！** |
| 标枪 | `biaoqiang_8` | 皮肤8 | **成就达成？！** |
| 标枪 | `biaoqiang_8_hx` | 皮肤8·和谐版 | **成就达成？！·和谐版** |
| 标枪 | `biaoqiang_8_n` | 皮肤8·无背景版 | **成就达成？！·无背景版** |
| 标枪 | `biaoqiang_8_n_hx` | 皮肤8·无背景版·和谐版 | **成就达成？！·和谐版·无背景版** |
| 标枪 | `biaoqiang_9` | 皮肤9 | **夜宴的新风格？** |
| 标枪 | `biaoqiang_9_n` | 皮肤9·无背景版 | **夜宴的新风格？·无背景版** |
| 标枪 | `biaoqiang_g` | G | **标枪.改** |
| 标枪 | `biaoqiang_h` | h | **幸福纯白** |
| 杓鹬 | `biaoyu_2` | 皮肤2 | **东煌之韵** |
| 杓鹬 | `biaoyu_g` | G | **杓鹬.改** |
| 比洛克西 | `biluokexi_2` | 皮肤2 | **俊俏丽人** |
| 比洛克西 | `biluokexi_2_n` | 皮肤2·无背景版 | **俊俏丽人·无背景版** |
| 比洛克西 | `biluokexi_4` | 皮肤4 | **洛城女帝** |
| 比洛克西 | `biluokexi_5` | 皮肤5 | **绚烂缤纷花火夜** |
| 比洛克西 | `biluokexi_5_n` | 皮肤5·无背景版 | **绚烂缤纷花火夜·无背景版** |
| 比洛克西 | `biluokexi_6` | 皮肤6 | **罗密欧or朱丽叶？** |
| 比洛克西 | `biluokexi_6_n` | 皮肤6·无背景版 | **罗密欧or朱丽叶？·无背景版** |
| 宾夕法尼亚 | `binxifaniya_2` | 皮肤2 | **石州飞将** |
| 比叡 | `birui_2` | 皮肤2 | **月下巡游** |
| 比叡 | `birui_4` | 皮肤4 | **红梅垂香** |
| 比叡 | `birui_5` | 皮肤5 | **海滩瑰景** |
| 比叡 | `birui_5_n` | 皮肤5·无背景版 | **海滩瑰景·无背景版** |
| 比叡 | `birui_memory` | memory | **比叡** ⚠名字塌了(==船名) |
| 比叡 | `birui_younv` | younv | **小比叡** |
| 比叡·META（前排） | `birui_alter_n` | 无背景版 | **比叡·META·无背景版** |
| 俾斯麦 | `bisimai_2` | 皮肤2 | **铁血的辉光** |
| 俾斯麦 | `bisimai_2_hx` | 皮肤2·和谐版 | **铁血的辉光·和谐版** |
| 俾斯麦 | `bisimai_3` | 皮肤3 | **黑铁·至福乐土** |
| 俾斯麦 | `bisimai_3_n` | 皮肤3·无背景版 | **黑铁·至福乐土·无背景版** |
| 俾斯麦 | `bisimai_4` | 皮肤4 | **未完成的圣诞惊喜** |
| 俾斯麦 | `bisimai_4_hx` | 皮肤4·和谐版 | **未完成的圣诞惊喜·和谐版** |
| 俾斯麦 | `bisimai_4_n` | 皮肤4·无背景版 | **未完成的圣诞惊喜·无背景版** |
| 俾斯麦 | `bisimai_4_n_hx` | 皮肤4·无背景版·和谐版 | **未完成的圣诞惊喜·和谐版·无背景版** |
| 俾斯麦 | `bisimai_h` | h | **Wedding Dominion** |
| 俾斯麦 | `bisimai_h_n` | h·无背景版 | **Wedding Dominion·无背景版** |
| 俾斯麦Zwei | `bisimaiz_2` | 皮肤2 | **清澈假日** |
| 俾斯麦Zwei | `bisimaiz_2_n` | 皮肤2·无背景版 | **清澈假日·无背景版** |
| 俾斯麦Zwei | `bisimaiz_3` | 皮肤3 | **沐光缀心** |
| 波尔塔瓦 | `boertawa_2` | 皮肤2 | **决断的优雅女王** |
| 波尔塔瓦 | `boertawa_2_n` | 皮肤2·无背景版 | **决断的优雅女王·无背景版** |
| 博尔扎诺 | `boerzhanuo_2` | 皮肤2 | **旋舞之刻** |
| 博尔扎诺 | `boerzhanuo_2_n` | 皮肤2·无背景版 | **旋舞之刻·无背景版** |
| 博尔扎诺 | `boerzhanuo_3` | 皮肤3 | **漂流荒岛与神秘宝藏** |
| 博尔扎诺 | `boerzhanuo_4` | 皮肤4 | **独属二人的灯火夜** |
| 博尔扎诺 | `boerzhanuo_4_n` | 皮肤4·无背景版 | **独属二人的灯火夜·无背景版** |
| 博格 | `boge_g` | G | **博格.改** |
| 博加特里 | `bojiateli_2` | 皮肤2 | **情感数据维护中** |
| 博加特里 | `bojiateli_2_n` | 皮肤2·无背景版 | **情感数据维护中·无背景版** |
| 波拉 | `bola_2` | 皮肤2 | **水边的事故？** |
| 印第安纳波利斯 | `bolisi_2` | 皮肤2 | **与姐姐一起的校园生活？** |
| 印第安纳波利斯 | `bolisi_3` | 皮肤3 | **环城之夜** |
| 印第安纳波利斯 | `bolisi_3_hx` | 皮肤3·和谐版 | **环城之夜·和谐版** |
| 印第安纳波利斯 | `bolisi_3_n` | 皮肤3·无背景版 | **环城之夜·无背景版** |
| 印第安纳波利斯 | `bolisi_3_n_hx` | 皮肤3·无背景版·和谐版 | **环城之夜·和谐版·无背景版** |
| 伯明翰 | `bominghan_2` | 皮肤2 | **赤色的骑行者** |
| 伯明翰 | `bominghan_3` | 皮肤3 | **乘风破浪之时** |
| 伯明翰 | `bominghan_4` | 皮肤4 | **瑞雪丰年** |
| 伯明翰 | `bominghan_4_n` | 皮肤4·无背景版 | **瑞雪丰年·无背景版** |
| 伯明翰 | `bominghan_5` | 皮肤5 | **Briar Maid** |
| 伯明翰 | `bominghan_5_n` | 皮肤5·无背景版 | **Briar Maid·无背景版** |
| 威廉·D·波特 | `bote_2` | 皮肤2 | **女仆服务？天翻地覆！** |
| 威廉·D·波特 | `bote_2_hx` | 皮肤2·和谐版 | **女仆服务？天翻地覆！·和谐版** |
| 威廉·D·波特 | `bote_2_n` | 皮肤2·无背景版 | **女仆服务？天翻地覆！·无背景版** |
| 威廉·D·波特 | `bote_2_n_hx` | 皮肤2·无背景版·和谐版 | **女仆服务？天翻地覆！·和谐版·无背景版** |
| 波特兰 | `botelan_2` | 皮肤2 | **与印第一起的校园生活** |
| 波特兰 | `botelan_g` | G | **波特兰.改** |
| 博伊西 | `boyixi_2` | 皮肤2 | **羞怯的蓝宝石** |
| 博伊西 | `boyixi_2_n` | 皮肤2·无背景版 | **羞怯的蓝宝石·无背景版** |
| 博伊西 | `boyixi_3` | 皮肤3 | **古堡奇谈** |
| 博伊西 | `boyixi_3_n` | 皮肤3·无背景版 | **古堡奇谈·无背景版** |
| 博伊西 | `boyixi_4` | 皮肤4 | **翠玉的海人鱼** |
| 博伊西 | `boyixi_4_hx` | 皮肤4·和谐版 | **翠玉的海人鱼·和谐版** |
| 博伊西 | `boyixi_5` | 皮肤5 | **失误的美味魔法** |
| 博伊西 | `boyixi_5_n` | 皮肤5·无背景版 | **失误的美味魔法·无背景版** |
| 博伊西 | `boyixi_idol` | idol | **博伊西(μ兵装)** |
| 博伊西 | `boyixi_idol_n` | idol·无背景版 | **博伊西(μ兵装)·无背景版** |
| 布莱默顿 | `bulaimodun_2` | 皮肤2 | **Happy Dating！** |
| 布莱默顿 | `bulaimodun_2_n` | 皮肤2·无背景版 | **Happy Dating！·无背景版** |
| 布莱默顿 | `bulaimodun_3` | 皮肤3 | **炙热的网球练习** |
| 布莱默顿 | `bulaimodun_3_n` | 皮肤3·无背景版 | **炙热的网球练习·无背景版** |
| 布莱默顿 | `bulaimodun_4` | 皮肤4 | **功夫少女！** |
| 布莱默顿 | `bulaimodun_4_hx` | 皮肤4·和谐版 | **功夫少女！·和谐版** |
| 布莱默顿 | `bulaimodun_4_n` | 皮肤4·无背景版 | **功夫少女！·无背景版** |
| 布莱默顿 | `bulaimodun_4_n_hx` | 皮肤4·无背景版·和谐版 | **功夫少女！·和谐版·无背景版** |
| 布莱默顿 | `bulaimodun_5` | 皮肤5 | **悠然放松时光** |
| 布莱默顿 | `bulaimodun_5_n` | 皮肤5·无背景版 | **悠然放松时光·无背景版** |
| 布莱默顿 | `bulaimodun_6` | 皮肤6 | **特别的治愈时间** |
| 布莱默顿 | `bulaimodun_6_n` | 皮肤6·无背景版 | **特别的治愈时间·无背景版** |
| 布莱默顿 | `bulaimodun_h` | h | **幸福的轨迹** |
| 布莱默顿 | `bulaimodun_h_n` | h·无背景版 | **幸福的轨迹·无背景版** |
| 布雷斯特 | `buleisite_2` | 皮肤2 | **苍海织歌** |
| 布雷斯特 | `buleisite_2_n` | 皮肤2·无背景版 | **苍海织歌·无背景版** |
| 布雷斯特 | `buleisite_3` | 皮肤3 | **良夜春景** |
| 布雷斯特 | `buleisite_3_n` | 皮肤3·无背景版 | **良夜春景·无背景版** |
| 特装型布里MKIII | `buli_super_2` | 皮肤2 | **BurinBurin★正义使者** |
| 特装型布里MKIII | `buli_super_2_n` | 皮肤2·无背景版 | **BurinBurin★正义使者·无背景版** |
| 布里斯托尔 | `bulisituoer_2` | 皮肤2 | **东煌志怪谈** |
| 布里斯托尔 | `bulisituoer_3` | 皮肤3 | **“头”号调查员** |
| 布里斯托尔 | `bulisituoer_3_n` | 皮肤3·无背景版 | **“头”号调查员·无背景版** |
| 布伦努斯 | `bulunnusi_2` | 皮肤2 | **夜幕下的演奏者** |
| 布伦努斯 | `bulunnusi_2_n` | 皮肤2·无背景版 | **夜幕下的演奏者·无背景版** |
| 布伦努斯 | `bulunnusi_3` | 皮肤3 | **演奏者的夜想曲** |
| 布伦努斯 | `bulunnusi_3_n` | 皮肤3·无背景版 | **演奏者的夜想曲·无背景版** |
| 布伦希尔德 | `bulunxierde_2` | 皮肤2 | **挑战·趣味障碍赛！** |
| 布伦希尔德 | `bulunxierde_2_n` | 皮肤2·无背景版 | **挑战·趣味障碍赛！·无背景版** |
| 布吕歇尔 | `bulvxieer_2` | 皮肤2 | **急转直下的Fallinlove** |
| 布吕歇尔 | `bulvxieer_2_n` | 皮肤2·无背景版 | **急转直下的Fallinlove·无背景版** |
| 布吕歇尔 | `bulvxieer_3` | 皮肤3 | **扶摇直上的BurningLove** |
| 布吕歇尔 | `bulvxieer_3_hx` | 皮肤3·和谐版 | **扶摇直上的BurningLove·和谐版** |
| 布吕歇尔 | `bulvxieer_3_n` | 皮肤3·无背景版 | **扶摇直上的BurningLove·无背景版** |
| 布吕歇尔 | `bulvxieer_3_n_hx` | 皮肤3·无背景版·和谐版 | **扶摇直上的BurningLove·和谐版·无背景版** |
| 布吕歇尔 | `bulvxieer_4` | 皮肤4 | **放学后的等待** |
| 布吕歇尔 | `bulvxieer_4_n` | 皮肤4·无背景版 | **放学后的等待·无背景版** |
| 不挠 | `bunao_2` | 皮肤2 | **没干劲的女仆小姐** |
| 不挠 | `bunao_2_n` | 皮肤2·无背景版 | **没干劲的女仆小姐·无背景版** |
| 不挠 | `bunao_3` | 皮肤3 | **慵懒的领航员小姐** |
| 不挠 | `bunao_3_n` | 皮肤3·无背景版 | **慵懒的领航员小姐·无背景版** |
| 不屈-王国军守护骑士 | `buqu_2` | 皮肤2 | **“小红帽”的烦恼** |
| 不屈-王国军守护骑士 | `buqu_2_hx` | 皮肤2·和谐版 | **“小红帽”的烦恼·和谐版** |
| 不屈-王国军守护骑士 | `buqu_3` | 皮肤3 | **寒冬全力配送中！** |
| 不屈-王国军守护骑士 | `buqu_4` | 皮肤4 | **全力以赴的伪装监听！** |
| 不屈-王国军守护骑士 | `buqu_4_n` | 皮肤4·无背景版 | **全力以赴的伪装监听！·无背景版** |
| 不屈-王国军守护骑士 | `buqu_n` | 无背景版 | **不屈·无背景版** |
| 布什 | `bushi_2` | 皮肤2 | **小小画家** |
| 不知火 | `buzhihuo_2` | 皮肤2 | **月饼、不来一点吗？** |
| 不知火 | `buzhihuo_2_n` | 皮肤2·无背景版 | **月饼、不来一点吗？·无背景版** |
| 不知火 | `buzhihuo_g` | G | **不知火.改** |
| 苍龙 | `canglong_2` | 皮肤2 | **松间鹤** |
| 苍龙 | `canglong_3` | 皮肤3 | **走廊上的风纪委员** |
| 苍龙 | `canglong_g` | G | **苍龙.改** |
| 柴郡 | `chaijun_2` | 皮肤2 | **Dating Summer！** |
| 柴郡 | `chaijun_2_n` | 皮肤2·无背景版 | **Dating Summer！·无背景版** |
| 柴郡 | `chaijun_3` | 皮肤3 | **音乐绚烂CaitSith** |
| 柴郡 | `chaijun_3_n` | 皮肤3·无背景版 | **音乐绚烂CaitSith·无背景版** |
| 柴郡 | `chaijun_4` | 皮肤4 | **冰雪公主** |
| 柴郡 | `chaijun_4_hx` | 皮肤4·和谐版 | **冰雪公主·和谐版** |
| 柴郡 | `chaijun_4_n` | 皮肤4·无背景版 | **冰雪公主·无背景版** |
| 柴郡 | `chaijun_5` | 皮肤5 | **绚烂夜梦** |
| 柴郡 | `chaijun_5_hx` | 皮肤5·和谐版 | **绚烂夜梦·和谐版** |
| 柴郡 | `chaijun_5_n` | 皮肤5·无背景版 | **绚烂夜梦·无背景版** |
| 柴郡 | `chaijun_5_n_hx` | 皮肤5·无背景版·和谐版 | **绚烂夜梦·和谐版·无背景版** |
| 柴郡 | `chaijun_6` | 皮肤6 | **柴郡猫的童话书迷宫** |
| 柴郡 | `chaijun_6_n` | 皮肤6·无背景版 | **柴郡猫的童话书迷宫·无背景版** |
| 柴郡 | `chaijun_h` | h | **White Seaside Melody！** ⚠长度异常 |
| 柴郡 | `chaijun_h_n` | h·无背景版 | **White Seaside Melody！·无背景版** ⚠长度异常 |
| 柴郡 | `chaijun_younv` | younv | **小柴郡** |
| 柴郡 | `chaijun_younv_n` | younv·无背景版 | **小柴郡·无背景版** |
| 长波 | `changbo_2` | 皮肤2 | **幸福的「长波」** |
| 长波 | `changbo_3` | 皮肤3 | **安心的“长波”** |
| 长波 | `changbo_3_hx` | 皮肤3·和谐版 | **安心的“长波”·和谐版** |
| 长波 | `changbo_3_n` | 皮肤3·无背景版 | **安心的“长波”·无背景版** |
| 长波 | `changbo_3_n_hx` | 皮肤3·无背景版·和谐版 | **安心的“长波”·和谐版·无背景版** |
| 长波 | `changbo_4` | 皮肤4 | **长夜相伴** |
| 长波 | `changbo_4_n` | 皮肤4·无背景版 | **长夜相伴·无背景版** |
| 长波 | `changbo_5` | 皮肤5 | **温软甜乡** |
| 长波 | `changbo_5_hx` | 皮肤5·和谐版 | **温软甜乡·和谐版** |
| 长波 | `changbo_5_n` | 皮肤5·无背景版 | **温软甜乡·无背景版** |
| 长波 | `changbo_5_n_hx` | 皮肤5·无背景版·和谐版 | **温软甜乡·和谐版·无背景版** |
| 长波 | `changbo_h` | h | **永恒相守** |
| 长春 | `changchun_2` | 皮肤2 | **春之嬉** |
| 长春 | `changchun_3` | 皮肤3 | **“红”运当头** |
| 长春 | `changchun_3_n` | 皮肤3·无背景版 | **“红”运当头·无背景版** |
| 长春 | `changchun_g` | G | **长春.改** |
| 长春 | `changchun_g_n` | G·无背景版 | **长春.改·无背景版** |
| 长岛 | `changdao_2` | 皮肤2 | **干物三连！** |
| 长岛 | `changdao_3` | 皮肤3 | **L.I.@万圣限时直播中** |
| 长岛 | `changdao_4` | 皮肤4 | **可靠的接待员？** |
| 长岛 | `changdao_4_n` | 皮肤4·无背景版 | **可靠的接待员？·无背景版** |
| 长岛 | `changdao_5` | 皮肤5 | **红包，多多益善！** |
| 长岛 | `changdao_5_n` | 皮肤5·无背景版 | **红包，多多益善！·无背景版** |
| 长岛 | `changdao_g` | G | **长岛.改** |
| 长风 | `changfeng_2` | 皮肤2 | **温馨的大扫除时间** |
| 长风 | `changfeng_2_n` | 皮肤2·无背景版 | **温馨的大扫除时间·无背景版** |
| 长风 | `changfeng_3` | 皮肤3 | **天青胜玉** |
| 长风 | `changfeng_3_n` | 皮肤3·无背景版 | **天青胜玉·无背景版** |
| 长良 | `changliang_2` | 皮肤2 | **悠闲春日** |
| 长门 | `changmen_2` | 皮肤2 | **神子的休憩** |
| 长门 | `changmen_3` | 皮肤3 | **御狐的辉振袖** |
| 长门 | `changmen_4` | 皮肤4 | **神子的闲暇一刻** |
| 长门 | `changmen_5` | 皮肤5 | **神子的华服** |
| 长门 | `changmen_6` | 皮肤6 | **牵心结缘** |
| 长门 | `changmen_6_n` | 皮肤6·无背景版 | **牵心结缘·无背景版** |
| 长门 | `changmen_h` | h | **御狐的白装束** |
| 长月 | `changyue_2` | 皮肤2 | **喵喵女仆有点危险？** |
| 赤城 | `chicheng_2` | 皮肤2 | **乐园的彼岸花** |
| 赤城 | `chicheng_3` | 皮肤3 | **梅与雪** |
| 赤城 | `chicheng_4` | 皮肤4 | **朱娟余醺** |
| 赤城 | `chicheng_5` | 皮肤5 | **朝凰来仪** |
| 赤城 | `chicheng_5_n` | 皮肤5·无背景版 | **朝凰来仪·无背景版** |
| 赤城 | `chicheng_6` | 皮肤6 | **路边的甜蜜** |
| 赤城 | `chicheng_6_n` | 皮肤6·无背景版 | **路边的甜蜜·无背景版** |
| 赤城 | `chicheng_alter` | alter | **赤城** ⚠名字塌了(==船名) |
| 赤城 | `chicheng_h` | h | **深红的虞美人** |
| 赤城 | `chicheng_idol` | idol | **赤城(μ兵装)** |
| 赤城 | `chicheng_idolns` | idolns | **赤城(μ兵装)** |
| 赤城 | `chicheng_younv` | younv | **小赤城** |
| 川内 | `chuannei_g` | G | **川内.改** |
| 初春 | `chuchun_2` | 皮肤2 | **初春之雪** |
| 初春 | `chuchun_3` | 皮肤3 | **春邀灯火** |
| 初春 | `chuchun_3_n` | 皮肤3·无背景版 | **春邀灯火·无背景版** |
| 初春 | `chuchun_4` | 皮肤4 | **猫咖逢春** |
| 初春 | `chuchun_4_n` | 皮肤4·无背景版 | **猫咖逢春·无背景版** |
| 初春 | `chuchun_g` | G | **初春.改** |
| 吹雪 | `chuixue_2` | 皮肤2 | **迟到前的一刻** |
| 吹雪 | `chuixue_3` | 皮肤3 | **Music Pixy** |
| 吹雪 | `chuixue_4` | 皮肤4 | **小鸡看板娘** |
| 吹雪 | `chuixue_5` | 皮肤5 | **特型偶像Fubuki** |
| 吹雪 | `chuixue_6` | 皮肤6 | **实习服务生Fubuki** |
| 吹雪 | `chuixue_7` | 皮肤7 | **灯影下的困境** |
| 天海春香 | `chunxiang_2` | 皮肤2 | **喧嚣中的静谧** |
| 天海春香 | `chunxiang_2_n` | 皮肤2·无背景版 | **喧嚣中的静谧·无背景版** |
| 春月 | `chunyue_2` | 皮肤2 | **迎春的神乐舞** |
| 春月 | `chunyue_2_n` | 皮肤2·无背景版 | **迎春的神乐舞·无背景版** |
| 春月 | `chunyue_3` | 皮肤3 | **温泉屋的小魔女** |
| 春月 | `chunyue_3_n` | 皮肤3·无背景版 | **温泉屋的小魔女·无背景版** |
| 初霜 | `chushuang_2` | 皮肤2 | **吉时祝宴** |
| 初霜 | `chushuang_g` | G | **初霜.改** |
| 初月 | `chuyue_2` | 皮肤2 | **八月恋夏** |
| 初月 | `chuyue_2_n` | 皮肤2·无背景版 | **八月恋夏·无背景版** |
| 初月 | `chuyue_3` | 皮肤3 | **节日的奢华时光♪** |
| 初月 | `chuyue_3_n` | 皮肤3·无背景版 | **节日的奢华时光♪·无背景版** |
| 初月 | `chuyue_h` | h | **红桥映雪** |
| 初月 | `chuyue_h_n` | h·无背景版 | **红桥映雪·无背景版** |
| 出云 | `chuyun_2` | 皮肤2 | **出云千本樱** |
| 出云 | `chuyun_3` | 皮肤3 | **尾尖的心跳特调** |
| 出云 | `chuyun_3_n` | 皮肤3·无背景版 | **尾尖的心跳特调·无背景版** |
| 匆忙 | `congmang_2` | 皮肤2 | **人偶藏馆** |
| 匆忙 | `congmang_2_n` | 皮肤2·无背景版 | **人偶藏馆·无背景版** |
| 大潮 | `dachao_2` | 皮肤2 | **驯鹿与圣诞礼物** |
| 大潮 | `dachao_2_hx` | 皮肤2·和谐版 | **驯鹿与圣诞礼物·和谐版** |
| 大潮 | `dachao_3` | 皮肤3 | **夜宴微醺** |
| 大潮 | `dachao_3_hx` | 皮肤3·和谐版 | **夜宴微醺·和谐版** |
| 大潮 | `dachao_4` | 皮肤4 | **新春福至 ** |
| 大潮 | `dachao_5` | 皮肤5 | **午餐的邀约？** |
| 大潮 | `dachao_5_n` | 皮肤5·无背景版 | **午餐的邀约？·无背景版** |
| 大胆 | `dadan_2` | 皮肤2 | **汗水浸润的冰凉邂逅** |
| 大胆 | `dadan_2_n` | 皮肤2·无背景版 | **汗水浸润的冰凉邂逅·无背景版** |
| 大凤 | `dafeng_2` | 皮肤2 | **毒苹果** |
| 大凤 | `dafeng_2_hx` | 皮肤2·和谐版 | **毒苹果·和谐版** |
| 大凤 | `dafeng_3` | 皮肤3 | **放学后的甜蜜时光** |
| 大凤 | `dafeng_3_n` | 皮肤3·无背景版 | **放学后的甜蜜时光·无背景版** |
| 大凤 | `dafeng_4` | 皮肤4 | **凤鸣春晓** |
| 大凤 | `dafeng_5` | 皮肤5 | **恋慕伴侣** |
| 大凤 | `dafeng_5_n` | 皮肤5·无背景版 | **恋慕伴侣·无背景版** |
| 大凤 | `dafeng_6` | 皮肤6 | **海滨的白日美梦** |
| 大凤 | `dafeng_6_n` | 皮肤6·无背景版 | **海滨的白日美梦·无背景版** |
| 大凤 | `dafeng_7` | 皮肤7 | **绮愿良宵** |
| 大凤 | `dafeng_7_n` | 皮肤7·无背景版 | **绮愿良宵·无背景版** |
| 大凤 | `dafeng_h` | h | **潮风的吸引** |
| 大凤 | `dafeng_h_n` | h·无背景版 | **潮风的吸引·无背景版** |
| 大凤 | `dafeng_idol` | idol | **大凤(μ兵装)** |
| 大凤 | `dafeng_idol_n` | idol·无背景版 | **大凤(μ兵装)·无背景版** |
| 大凤 | `dafeng_younv` | younv | **小大凤** |
| 大凤 | `dafeng_younv_n` | younv·无背景版 | **小大凤·无背景版** |
| 莱昂纳多·达·芬奇 | `dafenqi_2` | 皮肤2 | **湖畔的小天鹅** |
| 莱昂纳多·达·芬奇 | `dafenqi_2_n` | 皮肤2·无背景版 | **湖畔的小天鹅·无背景版** |
| 莱昂纳多·达·芬奇 | `dafenqi_3` | 皮肤3 | **摇摆兔女郎** |
| 莱昂纳多·达·芬奇 | `dafenqi_3_n` | 皮肤3·无背景版 | **摇摆兔女郎·无背景版** |
| 大黄蜂 | `dahuangfeng_2` | 皮肤2 | **Bubbly Anniversary！** |
| 大黄蜂 | `dahuangfeng_3` | 皮肤3 | **美味生活！** |
| 大黄蜂 | `dahuangfeng_4` | 皮肤4 | **应援即是正义！** |
| 大黄蜂 | `dahuangfeng_4_n` | 皮肤4·无背景版 | **应援即是正义！·无背景版** |
| 大黄蜂 | `dahuangfeng_hx` | 和谐版 | **大黄蜂·和谐版** ⚠名字塌了(==船名) |
| 大黄蜂 | `dahuangfengii_2` | 皮肤2 | **驰骋于大海之上！** |
| 大黄蜂 | `dahuangfengii_2_hx` | 皮肤2·和谐版 | **驰骋于大海之上！·和谐版** |
| 大黄蜂 | `dahuangfengii_n` | 无背景版 | **大黄蜂II·无背景版** |
| 黛朵 | `daiduo_2` | 皮肤2 | **多愁的BIsqueDoll** |
| 黛朵 | `daiduo_idol` | idol | **黛朵(μ兵装)** |
| 黛朵 | `daiduo_idol_n` | idol·无背景版 | **黛朵(μ兵装)·无背景版** |
| 尼科洛索·达雷科 | `daleike_2` | 皮肤2 | **出航前的余兴** |
| 尼科洛索·达雷科 | `daleike_2_hx` | 皮肤2·和谐版 | **出航前的余兴·和谐版** |
| 尼科洛索·达雷科 | `daleike_2_n` | 皮肤2·无背景版 | **出航前的余兴·无背景版** |
| 尼科洛索·达雷科 | `daleike_2_n_hx` | 皮肤2·无背景版·和谐版 | **出航前的余兴·和谐版·无背景版** |
| 丹佛 | `danfo_2` | 皮肤2 | **假日悠悠** |
| 岛风 | `daofeng_3` | 皮肤3 | **盛夏岛屿的小憩** |
| 岛风 | `daofeng_3_n` | 皮肤3·无背景版 | **盛夏岛屿的小憩·无背景版** |
| 岛风 | `daofeng_4` | 皮肤4 | **最速兔兔的邀请函(?)** |
| 岛风 | `daofeng_4_n` | 皮肤4·无背景版 | **最速兔兔的邀请函(?)·无背景版** |
| 岛风 | `daofeng_5` | 皮肤5 | **不思议国度的白兔** |
| 岛风 | `daofeng_5_hx` | 皮肤5·和谐版 | **不思议国度的白兔·和谐版** |
| 岛风 | `daofeng_5_n` | 皮肤5·无背景版 | **不思议国度的白兔·无背景版** |
| 岛风 | `daofeng_6` | 皮肤6 | **慌乱的月下玉兔** |
| 岛风 | `daofeng_6_n` | 皮肤6·无背景版 | **慌乱的月下玉兔·无背景版** |
| 岛风 | `daofeng_7` | 皮肤7 | **白兔一动也不动** |
| 岛风 | `daofeng_7_n` | 皮肤7·无背景版 | **白兔一动也不动·无背景版** |
| 大青花鱼 | `daqinghuayu_3` | 皮肤3 | **箱子里的“惊喜”** |
| 大青花鱼 | `daqinghuayu_3_n` | 皮肤3·无背景版 | **箱子里的“惊喜”·无背景版** |
| 大青花鱼 | `daqinghuayu_4` | 皮肤4 | **黑裙下的「秘密」** |
| 大青花鱼 | `daqinghuayu_4_hx` | 皮肤4·和谐版 | **黑裙下的「秘密」·和谐版** |
| 大青花鱼 | `daqinghuayu_4_n` | 皮肤4·无背景版 | **黑裙下的「秘密」·无背景版** |
| 大青花鱼 | `daqinghuayu_4_n_hx` | 皮肤4·无背景版·和谐版 | **黑裙下的「秘密」·和谐版·无背景版** |
| 大青花鱼 | `daqinghuayu_idol` | idol | **大青花鱼(μ兵装)** |
| 大青花鱼 | `daqinghuayu_idol_n` | idol·无背景版 | **大青花鱼(μ兵装)·无背景版** |
| 大山 | `dashan_2` | 皮肤2 | **祈愿的巫女兔** |
| 大山 | `dashan_2_n` | 皮肤2·无背景版 | **祈愿的巫女兔·无背景版** |
| 德雷克 | `deleike_2` | 皮肤2 | **黄金鹿的闲暇时光** |
| 德文郡 | `dewenjun_2` | 皮肤2 | **红月下的恶魔** |
| 德意志 | `deyizhi_2` | 皮肤2 | **漆黑的魔姬** |
| 德意志 | `deyizhi_3` | 皮肤3 | **艳阳下的“福利”时间** |
| 德意志 | `deyizhi_4` | 皮肤4 | **魔姬的夜宴** |
| 德意志 | `deyizhi_5` | 皮肤5 | **华灯下的支配者** |
| 电 | `dian_2` | 皮肤2 | **香草布丁** |
| 电 | `dian_3` | 皮肤3 | **花火Inazuma** |
| 电 | `dian_4` | 皮肤4 | **月下妖精Inazuma** |
| 电 | `dian_4_n` | 皮肤4·无背景版 | **月下妖精Inazuma·无背景版** |
| 电 | `dian_5` | 皮肤5 | **蔷薇紫的芳香** |
| 电 | `dian_5_n` | 皮肤5·无背景版 | **蔷薇紫的芳香·无背景版** |
| 敌对 | `didui_2` | 皮肤2 | **水畔的守望之光** |
| 敌对 | `didui_2_n` | 皮肤2·无背景版 | **水畔的守望之光·无背景版** |
| 迪盖·特鲁因 | `digaiteluyin_2` | 皮肤2 | **温泉边的捕食者** |
| 迪盖·特鲁因 | `digaiteluyin_2_hx` | 皮肤2·和谐版 | **温泉边的捕食者·和谐版** |
| 迪盖·特鲁因 | `digaiteluyin_2_n` | 皮肤2·无背景版 | **温泉边的捕食者·无背景版** |
| 迪盖·特鲁因 | `digaiteluyin_2_n_hx` | 皮肤2·无背景版·和谐版 | **温泉边的捕食者·和谐版·无背景版** |
| 帝国 | `diguo_2` | 皮肤2 | **图书管理员的倦怠** |
| 帝国 | `diguo_2_n` | 皮肤2·无背景版 | **图书管理员的倦怠·无背景版** |
| 帝国 | `diguo_3` | 皮肤3 | **醉忘今宵** |
| 帝国 | `diguo_3_n` | 皮肤3·无背景版 | **醉忘今宵·无背景版** |
| 迪凯纳 | `dikaina_2` | 皮肤2 | **深红的热夜** |
| 迪凯纳 | `dikaina_2_hx` | 皮肤2·和谐版 | **深红的热夜·和谐版** |
| 迪凯纳 | `dikaina_2_n` | 皮肤2·无背景版 | **深红的热夜·无背景版** |
| 迪凯纳 | `dikaina_2_n_hx` | 皮肤2·无背景版·和谐版 | **深红的热夜·和谐版·无背景版** |
| 的里雅斯特 | `diliyasite_2` | 皮肤2 | **期待的便当时间？** |
| 的里雅斯特 | `diliyasite_2_n` | 皮肤2·无背景版 | **期待的便当时间？·无背景版** |
| 的里雅斯特 | `diliyasite_3` | 皮肤3 | **热气蒸腾温泉夜** |
| 的里雅斯特 | `diliyasite_3_n` | 皮肤3·无背景版 | **热气蒸腾温泉夜·无背景版** |
| 的里雅斯特 | `diliyasite_4` | 皮肤4 | **墨雅夜韵** |
| 的里雅斯特 | `diliyasite_4_n` | 皮肤4·无背景版 | **墨雅夜韵·无背景版** |
| 迪米特里·顿斯科伊 | `dimiteli_2` | 皮肤2 | **兔兔的床边服务** |
| 迪米特里·顿斯科伊 | `dimiteli_2_n` | 皮肤2·无背景版 | **兔兔的床边服务·无背景版** |
| 定安 | `dingan_2` | 皮肤2 | **红红火火度勤春** |
| 定安 | `dingan_2_hx` | 皮肤2·和谐版 | **红红火火度勤春·和谐版** |
| 定安 | `dingan_2_n` | 皮肤2·无背景版 | **红红火火度勤春·无背景版** |
| 定安 | `dingan_2_n_hx` | 皮肤2·无背景版·和谐版 | **红红火火度勤春·和谐版·无背景版** |
| 定安 | `dingan_3` | 皮肤3 | **秘密市场调研？！** |
| 定安 | `dingan_3_hx` | 皮肤3·和谐版 | **秘密市场调研？！·和谐版** |
| 定安 | `dingan_3_n` | 皮肤3·无背景版 | **秘密市场调研？！·无背景版** |
| 定安 | `dingan_3_n_hx` | 皮肤3·无背景版·和谐版 | **秘密市场调研？！·和谐版·无背景版** |
| 迪普莱克斯 | `dipulaikesi_2` | 皮肤2 | **Final Check** |
| 迪普莱克斯 | `dipulaikesi_2_n` | 皮肤2·无背景版 | **Final Check·无背景版** |
| 多塞特 | `dosair_n` | 无背景版 | **？？？·无背景版** ⚠像垃圾串:全问号 |
| 独角兽 | `dujiaoshou_10` | 皮肤10 | **纯白守护天使** |
| 独角兽 | `dujiaoshou_10_n` | 皮肤10·无背景版 | **纯白守护天使·无背景版** |
| 独角兽 | `dujiaoshou_11` | 皮肤11 | **Champion of Unicorn** |
| 独角兽 | `dujiaoshou_11_n` | 皮肤11·无背景版 | **Champion of Unicorn·无背景版** |
| 独角兽 | `dujiaoshou_2` | 皮肤2 | **小小的星之歌姬** |
| 独角兽 | `dujiaoshou_3` | 皮肤3 | **春之礼** |
| 独角兽 | `dujiaoshou_4` | 皮肤4 | **憧憬的约会日** |
| 独角兽 | `dujiaoshou_5` | 皮肤5 | **祈愿的雪与梅** |
| 独角兽 | `dujiaoshou_6` | 皮肤6 | **天使的My Night** |
| 独角兽 | `dujiaoshou_6_n` | 皮肤6·无背景版 | **天使的My Night·无背景版** |
| 独角兽 | `dujiaoshou_7` | 皮肤7 | **清凉阅读时光** |
| 独角兽 | `dujiaoshou_8` | 皮肤8 | **天使的护理时间** |
| 独角兽 | `dujiaoshou_8_n` | 皮肤8·无背景版 | **天使的护理时间·无背景版** |
| 独角兽 | `dujiaoshou_9` | 皮肤9 | **幸福乐章** |
| 独角兽 | `dujiaoshou_g` | G | **独角兽.改** |
| 独角兽 | `dujiaoshou_g_n` | G·无背景版 | **独角兽.改·无背景版** |
| 独角兽 | `dujiaoshou_h` | h | **梦想的纯白誓约** |
| 独立 | `duli_2` | 皮肤2 | **远道而来的转校生** |
| 独立 | `duli_3` | 皮肤3 | **海风的Lucky Time** |
| 独立 | `duli_3_n` | 皮肤3·无背景版 | **海风的Lucky Time·无背景版** |
| 独立 | `duli_5` | 皮肤5 | **「独立」品牌** |
| 独立 | `duli_5_n` | 皮肤5·无背景版 | **「独立」品牌·无背景版** |
| 独立 | `duli_6` | 皮肤6 | **Relaxation.I** |
| 独立 | `duli_6_n` | 皮肤6·无背景版 | **Relaxation.I·无背景版** |
| 独立 | `duli_7` | 皮肤7 | **海边的按摩时光** |
| 独立 | `duli_7_n` | 皮肤7·无背景版 | **海边的按摩时光·无背景版** |
| 独立 | `duli_g` | G | **独立.改** |
| 渡良濑 | `dulianglai_2` | 皮肤2 | **不会消失的换装魔法** |
| 渡良濑 | `dulianglai_2_n` | 皮肤2·无背景版 | **不会消失的换装魔法·无背景版** |
| 敦刻尔克 | `dunkeerke_2` | 皮肤2 | **“甜蜜”夏日** |
| 敦刻尔克 | `dunkeerke_3` | 皮肤3 | **午后三时的Venus** |
| 杜威 | `duwei_2` | 皮肤2 | **夏日憧憬** |
| 杜威 | `duwei_3` | 皮肤3 | **冬夜的感谢** |
| 杜伊斯堡 | `duyisibao_2` | 皮肤2 | **两人的秘密特训！** |
| 杜伊斯堡 | `duyisibao_2_hx` | 皮肤2·和谐版 | **两人的秘密特训！·和谐版** |
| 杜伊斯堡 | `duyisibao_2_n` | 皮肤2·无背景版 | **两人的秘密特训！·无背景版** |
| 杜伊斯堡 | `duyisibao_2_n_hx` | 皮肤2·无背景版·和谐版 | **两人的秘密特训！·和谐版·无背景版** |
| 恶毒 | `edu_2` | 皮肤2 | **懒懒的星期天** |
| 恶毒 | `edu_3` | 皮肤3 | **秘密基地的Mercredi** |
| 恶毒 | `edu_3_hx` | 皮肤3·和谐版 | **秘密基地的Mercredi·和谐版** |
| 恶毒 | `edu_4` | 皮肤4 | **懒懒的白兔** |
| 恶毒 | `edu_4_n` | 皮肤4·无背景版 | **懒懒的白兔·无背景版** |
| 恶毒 | `edu_idol` | idol | **恶毒(μ兵装)** |
| 恶毒 | `edu_idol_n` | idol·无背景版 | **恶毒(μ兵装)·无背景版** |
| 俄克拉荷马 | `ekelahema_2` | 皮肤2 | **炸裂变身大作战！** |
| 俄克拉荷马 | `ekelahema_2_n` | 皮肤2·无背景版 | **炸裂变身大作战！·无背景版** |
| 俄克拉荷马 | `ekelahema_g` | G | **俄克拉荷马.改** |
| 仲裁者·英普拉·IV | `emperor_n` | 无背景版 | **仲裁者·英普拉·IV ·无背景版** |
| 第二代 | `erdaimu_2` | 皮肤2 | **私人时间** |
| 第二代 | `erdaimu_2_n` | 皮肤2·无背景版 | **私人时间·无背景版** |
| 法戈 | `fage_2` | 皮肤2 | **纯白热潮** |
| 法戈 | `fage_2_hx` | 皮肤2·和谐版 | **纯白热潮·和谐版** |
| 法戈 | `fage_2_n` | 皮肤2·无背景版 | **纯白热潮·无背景版** |
| 法戈 | `fage_2_n_hx` | 皮肤2·无背景版·和谐版 | **纯白热潮·和谐版·无背景版** |
| 反击 | `fanji_3` | 皮肤3 | **武韵春华** |
| 反击 | `fanji_3_n` | 皮肤3·无背景版 | **武韵春华·无背景版** |
| 反击 | `fanji_alter` | alter | **反击·META** |
| 斐济 | `feiji_2` | 皮肤2 | **时尚风情？** |
| 菲利克斯·舒尔茨 | `feilikesishuerci_2` | 皮肤2 | **甜蜜的“报复”** |
| 菲利克斯·舒尔茨 | `feilikesishuerci_2_n` | 皮肤2·无背景版 | **甜蜜的“报复”·无背景版** |
| 飞龙 | `feilong_2` | 皮肤2 | **放学后的极道少女** |
| 飞龙 | `feilong_alter` | alter | **飞龙·META** |
| 飞龙 | `feilong_g` | G | **飞龙.改** |
| 飞鸟 | `feiniao_2` | 皮肤2 | **蔚蓝大海** |
| 飞鸟 | `feiniao_2_n` | 皮肤2·无背景版 | **蔚蓝大海·无背景版** |
| 腓特烈大帝 | `feiteliedadi_2` | 皮肤2 | **雅乐的黯衣** |
| 腓特烈大帝 | `feiteliedadi_2_n` | 皮肤2·无背景版 | **雅乐的黯衣·无背景版** |
| 腓特烈大帝 | `feiteliedadi_3` | 皮肤3 | **相会于盛夏之夜** |
| 腓特烈大帝 | `feiteliedadi_3_n` | 皮肤3·无背景版 | **相会于盛夏之夜·无背景版** |
| 腓特烈大帝 | `feiteliedadi_4` | 皮肤4 | **红封之礼** |
| 腓特烈大帝 | `feiteliedadi_4_n` | 皮肤4·无背景版 | **红封之礼·无背景版** |
| 腓特烈大帝 | `feiteliedadi_5` | 皮肤5 | **携心夜烛** |
| 腓特烈大帝 | `feiteliedadi_5_n` | 皮肤5·无背景版 | **携心夜烛·无背景版** |
| 腓特烈大帝 | `feiteliedadi_h` | h | **摇篮的Zeremonie** |
| 腓特烈大帝 | `feiteliedadi_h_hx` | h·和谐版 | **摇篮的Zeremonie·和谐版** |
| 腓特烈·卡尔 | `feiteliekaer_2` | 皮肤2 | **沉溺于爱的游戏** |
| 腓特烈·卡尔 | `feiteliekaer_2_n` | 皮肤2·无背景版 | **沉溺于爱的游戏·无背景版** |
| 腓特烈·卡尔 | `feiteliekaer_3` | 皮肤3 | **夏日防晒计划** |
| 腓特烈·卡尔 | `feiteliekaer_3_n` | 皮肤3·无背景版 | **夏日防晒计划·无背景版** |
| 腓特烈·卡尔 | `feiteliekaer_4` | 皮肤4 | **午夜频道** |
| 腓特烈·卡尔 | `feiteliekaer_4_n` | 皮肤4·无背景版 | **午夜频道·无背景版** |
| 鲱鱼 | `feiyu_2` | 皮肤2 | **孤镇绝尘** |
| 鲱鱼 | `feiyu_2_n` | 皮肤2·无背景版 | **孤镇绝尘·无背景版** |
| 飞云 | `feiyun_2` | 皮肤2 | **飞云在天** |
| 飞云 | `feiyun_2_n` | 皮肤2·无背景版 | **飞云在天·无背景版** |
| 飞云 | `feiyun_3` | 皮肤3 | **飞云大人的糖衣炮弹** |
| 飞云 | `feiyun_3_n` | 皮肤3·无背景版 | **飞云大人的糖衣炮弹·无背景版** |
| 凤翔 | `fengxiang_2` | 皮肤2 | **秋枕梦** |
| 风云 | `fengyun_2` | 皮肤2 | **烟火之夜、静谧之海** |
| 风云 | `fengyun_2_n` | 皮肤2·无背景版 | **烟火之夜、静谧之海·无背景版** |
| 风云 | `fengyun_3` | 皮肤3 | **放学后的悠扬** |
| 风云 | `fengyun_3_n` | 皮肤3·无背景版 | **放学后的悠扬·无背景版** |
| 风云 | `fengyun_4` | 皮肤4 | **热茶与女仆修行** |
| 风云 | `fengyun_4_n` | 皮肤4·无背景版 | **热茶与女仆修行·无背景版** |
| 伏波 | `fubo_2` | 皮肤2 | **淘趣闹新春** |
| 伏波 | `fubo_2_n` | 皮肤2·无背景版 | **淘趣闹新春·无背景版** |
| 复仇 | `fuchou_2` | 皮肤2 | **进击的冒失女仆** |
| 复仇 | `fuchou_2_n` | 皮肤2·无背景版 | **进击的冒失女仆·无背景版** |
| 福尔班 | `fuerban_2` | 皮肤2 | **纯白花语** |
| 福尔班 | `fuerban_3` | 皮肤3 | **学园的见习骑士** |
| 福尔班 | `fuerban_4` | 皮肤4 | **香槟盛宴** |
| 福尔班 | `fuerban_g` | G | **福尔班.改** |
| 福尔班 | `fuerban_h` | h | **誓约的神圣花束** |
| 福尔班 | `fuerban_h_n` | h·无背景版 | **誓约的神圣花束·无背景版** |
| 伏尔加 | `fuerjia_2` | 皮肤2 | **超美味·AR侦探体验？** |
| 伏尔加 | `fuerjia_2_n` | 皮肤2·无背景版 | **超美味·AR侦探体验？·无背景版** |
| 弗兰德尔 | `fulandeer_2` | 皮肤2 | **愿恕爱怜之罪** |
| 弗兰德尔 | `fulandeer_2_n` | 皮肤2·无背景版 | **愿恕爱怜之罪·无背景版** |
| 弗朗西斯科·卡拉乔洛 | `fulangxisike_2` | 皮肤2 | **灯光下的自白** |
| 弗朗西斯科·卡拉乔洛 | `fulangxisike_2_n` | 皮肤2·无背景版 | **灯光下的自白·无背景版** |
| 富兰克林 | `fulankelin_2` | 皮肤2 | **“护士”小姐的留院日志** |
| 富兰克林 | `fulankelin_2_n` | 皮肤2·无背景版 | **“护士”小姐的留院日志·无背景版** |
| 弗里茨·鲁梅 | `fulici_2` | 皮肤2 | **Schwarzes Kaninchen** |
| 弗里茨·鲁梅 | `fulici_2_n` | 皮肤2·无背景版 | **Schwarzes Kaninchen·无背景版** |
| 弗里茨·鲁梅 | `fulici_3` | 皮肤3 | **暮色邀约** |
| 弗里茨·鲁梅 | `fulici_3_n` | 皮肤3·无背景版 | **暮色邀约·无背景版** |
| 伏罗希洛夫 | `fuluoxiluofu_2` | 皮肤2 | **山间暖雪** |
| 伏罗希洛夫 | `fuluoxiluofu_2_n` | 皮肤2·无背景版 | **山间暖雪·无背景版** |
| 伏罗希洛夫 | `fuluoxiluofu_3` | 皮肤3 | **特殊的亲密预演** |
| 伏罗希洛夫 | `fuluoxiluofu_3_hx` | 皮肤3·和谐版 | **特殊的亲密预演·和谐版** |
| 伏罗希洛夫 | `fuluoxiluofu_3_n` | 皮肤3·无背景版 | **特殊的亲密预演·无背景版** |
| 伏罗希洛夫 | `fuluoxiluofu_3_n_hx` | 皮肤3·无背景版·和谐版 | **特殊的亲密预演·和谐版·无背景版** |
| 芙米露露 | `fumilulu_2` | 皮肤2 | **芙米露露(传颂之物)** |
| 扶桑 | `fusang_2` | 皮肤2 | **春之祝** |
| 扶桑 | `fusang_3` | 皮肤3 | **家有贤妻？** |
| 扶桑 | `fusang_g` | G | **扶桑.改** |
| 扶桑 | `fusang_h` | h | **愿思君所思，想君所想** |
| 扶桑 | `fusang_h_n` | h·无背景版 | **愿思君所思，想君所想·无背景版** |
| 抚顺 | `fushun_2` | 皮肤2 | **“钓”包游戏** |
| 抚顺 | `fushun_g` | G | **抚顺.改** |
| 抚顺 | `fushun_g_n` | G·无背景版 | **抚顺.改·无背景版** |
| 福煦 | `fuxu_2` | 皮肤2 | **虹彩的rendez-vous** |
| 福煦 | `fuxu_2_n` | 皮肤2·无背景版 | **虹彩的rendez-vous·无背景版** |
| 福煦 | `fuxu_3` | 皮肤3 | **耀眼的女管家** |
| 甘古特 | `gangute_2` | 皮肤2 | **坚定的执行者** |
| 甘古特 | `gangute_3` | 皮肤3 | **挚爱伏特加** |
| 甘古特 | `gangute_3_n` | 皮肤3·无背景版 | **挚爱伏特加·无背景版** |
| 甘古特 | `gangute_dark` | dark | **？？？** ⚠像垃圾串:全问号 |
| 冈依沙瓦号 | `gangyishawa_2` | 皮肤2 | **被封印的美人鱼** |
| 冈依沙瓦号 | `gangyishawa_2_n` | 皮肤2·无背景版 | **被封印的美人鱼·无背景版** |
| 冈依沙瓦号 | `gangyishawa_3` | 皮肤3 | **真我的显影** |
| 冈依沙瓦号 | `gangyishawa_3_n` | 皮肤3·无背景版 | **真我的显影·无背景版** |
| 高雄 | `gaoxiong_2` | 皮肤2 | **沙滩狂想曲** |
| 高雄 | `gaoxiong_3` | 皮肤3 | **春之意** |
| 高雄 | `gaoxiong_4` | 皮肤4 | **校园浪漫曲** |
| 高雄 | `gaoxiong_5` | 皮肤5 | **至高焦点** |
| 高雄 | `gaoxiong_5_n` | 皮肤5·无背景版 | **至高焦点·无背景版** |
| 高雄 | `gaoxiong_6` | 皮肤6 | **破魔舰术-神护-** |
| 高雄 | `gaoxiong_6_n` | 皮肤6·无背景版 | **破魔舰术-神护-·无背景版** |
| 高雄 | `gaoxiong_7` | 皮肤7 | **武者的“内在”修养** |
| 高雄 | `gaoxiong_7_n` | 皮肤7·无背景版 | **武者的“内在”修养·无背景版** |
| 高雄 | `gaoxiong_dark` | dark | **高雄** ⚠名字塌了(==船名) |
| 高雄 | `gaoxiong_h` | h | **神护樱华** |
| 葛城 | `gecheng_2` | 皮肤2 | **黎明辉祭** |
| 葛城 | `gecheng_2_n` | 皮肤2·无背景版 | **黎明辉祭·无背景版** |
| 葛城 | `gecheng_3` | 皮肤3 | **浅水游闲** |
| 葛城 | `gecheng_3_n` | 皮肤3·无背景版 | **浅水游闲·无背景版** |
| 格拉斯哥 | `gelasige_2` | 皮肤2 | **女仆小姐是同级生** |
| 格里德利 | `gelideli_2` | 皮肤2 | **圣诞摄影会！** |
| 格里芬 | `gelifen_2` | 皮肤2 | **紧张的放松疗愈** |
| 格里芬 | `gelifen_2_n` | 皮肤2·无背景版 | **紧张的放松疗愈·无背景版** |
| 戈里齐亚 | `geliqiya_2` | 皮肤2 | **办公室的“隔阂”** |
| 戈里齐亚 | `geliqiya_2_n` | 皮肤2·无背景版 | **办公室的“隔阂”·无背景版** |
| 戈里齐亚 | `geliqiya_3` | 皮肤3 | **间谍行动大失败！** |
| 戈里齐亚 | `geliqiya_3_hx` | 皮肤3·和谐版 | **间谍行动大失败！·和谐版** |
| 戈里齐亚 | `geliqiya_3_n` | 皮肤3·无背景版 | **间谍行动大失败！·无背景版** |
| 戈里齐亚 | `geliqiya_3_n_hx` | 皮肤3·无背景版·和谐版 | **间谍行动大失败！·和谐版·无背景版** |
| 哥伦比亚 | `gelunbiya_2` | 皮肤2 | **放学前的Odette** |
| 哥伦比亚 | `gelunbiya_3` | 皮肤3 | **草原纵横之旅** |
| 哥伦比亚 | `gelunbiya_3_n` | 皮肤3·无背景版 | **草原纵横之旅·无背景版** |
| 格罗斯特 | `geluosite_2` | 皮肤2 | **绛紫奢情** |
| 格罗斯特 | `geluosite_2_n` | 皮肤2·无背景版 | **绛紫奢情·无背景版** |
| 格罗斯特 | `geluosite_3` | 皮肤3 | **魅紫旋舞** |
| 格罗斯特 | `geluosite_3_n` | 皮肤3·无背景版 | **魅紫旋舞·无背景版** |
| 格奈森瑙 | `genaisennao_2` | 皮肤2 | **梦魇魅影** |
| 葛兹·冯·伯利欣根 | `gezi_2` | 皮肤2 | **赤红之月的幻想** |
| 葛兹·冯·伯利欣根 | `gezi_2_hx` | 皮肤2·和谐版 | **赤红之月的幻想·和谐版** |
| 葛兹·冯·伯利欣根 | `gezi_2_n` | 皮肤2·无背景版 | **赤红之月的幻想·无背景版** |
| 葛兹·冯·伯利欣根 | `gezi_2_n_hx` | 皮肤2·无背景版·和谐版 | **赤红之月的幻想·和谐版·无背景版** |
| 泛用型布里 | `gin_2` | 皮肤2 | **泛用型强化武装(工作用)** |
| 泛用型布里 | `gin_3` | 皮肤3 | **变身！魔法少女★buli！** |
| 泛用型布里 | `gin_3_n` | 皮肤3·无背景版 | **变身！魔法少女★buli！·无背景版** |
| 公主 | `gongzhu_2` | 皮肤2 | **晚酌时间** |
| 公主 | `gongzhu_2_n` | 皮肤2·无背景版 | **晚酌时间·无背景版** |
| 关岛 | `guandao_2` | 皮肤2 | **魅力舞台** |
| 关岛 | `guandao_2_n` | 皮肤2·无背景版 | **魅力舞台·无背景版** |
| 关岛 | `guandao_3` | 皮肤3 | **女忍者的危险综艺秀** |
| 关岛 | `guandao_3_hx` | 皮肤3·和谐版 | **女忍者的危险综艺秀·和谐版** |
| 关岛 | `guandao_3_n` | 皮肤3·无背景版 | **女忍者的危险综艺秀·无背景版** |
| 关岛 | `guandao_3_n_hx` | 皮肤3·无背景版·和谐版 | **女忍者的危险综艺秀·和谐版·无背景版** |
| 光辉 | `guanghui_2` | 皮肤2 | **永不落幕的茶会** |
| 光辉 | `guanghui_3` | 皮肤3 | **光辉的舞会** |
| 光辉 | `guanghui_4` | 皮肤4 | **异国的光辉** |
| 光辉 | `guanghui_5` | 皮肤5 | **钟情春日** |
| 光辉 | `guanghui_6` | 皮肤6 | **柔光雅乐** |
| 光辉 | `guanghui_6_n` | 皮肤6·无背景版 | **柔光雅乐·无背景版** |
| 光辉 | `guanghui_7` | 皮肤7 | **二人的学习时间** |
| 光辉 | `guanghui_7_n` | 皮肤7·无背景版 | **二人的学习时间·无背景版** |
| 光辉 | `guanghui_8` | 皮肤8 | **辉光下的甜蜜** |
| 光辉 | `guanghui_8_n` | 皮肤8·无背景版 | **辉光下的甜蜜·无背景版** |
| 光辉 | `guanghui_9` | 皮肤9 | **幽影徘徊之夜** |
| 光辉 | `guanghui_9_n` | 皮肤9·无背景版 | **幽影徘徊之夜·无背景版** |
| 光辉 | `guanghui_h` | h | **爱与希望的晨星** |
| 光辉 | `guanghui_idol` | idol | **光辉(μ兵装)** |
| 光辉 | `guanghui_idol_n` | idol·无背景版 | **光辉(μ兵装)·无背景版** |
| 光辉 | `guanghui_younv` | younv | **小光辉** |
| 光荣 | `guangrong_2` | 皮肤2 | **荣光的校园生活** |
| 光荣 | `guangrong_3` | 皮肤3 | **凉夜香雪** |
| 光荣 | `guangrong_3_n` | 皮肤3·无背景版 | **凉夜香雪·无背景版** |
| 古比雪夫 | `gubixuefu_2` | 皮肤2 | **银弦的向导兵** |
| 古比雪夫 | `gubixuefu_3` | 皮肤3 | **雨夜的蓝色心情** |
| 古比雪夫 | `gubixuefu_3_n` | 皮肤3·无背景版 | **雨夜的蓝色心情·无背景版** |
| 谷风 | `gufeng_2` | 皮肤2 | **海边的迷路少女** |
| 谷风 | `gufeng_4` | 皮肤4 | **闪闪发光大扫除** |
| 谷风 | `gufeng_4_n` | 皮肤4·无背景版 | **闪闪发光大扫除·无背景版** |
| 谷风 | `gufeng_g` | G | **谷风.改** |
| 鬼怒 | `guinu_2` | 皮肤2 | **新年的剑鬼** |
| 鬼怒 | `guinu_3` | 皮肤3 | **Token＆Ghost** |
| 鬼怒 | `guinu_3_n` | 皮肤3·无背景版 | **Token＆Ghost·无背景版** |
| 鬼怒 | `guinu_g` | G | **鬼怒.改** |
| 果敢 | `guogan_2` | 皮肤2 | **伞下的守护** |
| 果敢 | `guogan_2_hx` | 皮肤2·和谐版 | **伞下的守护·和谐版** |
| 果敢 | `guogan_2_n` | 皮肤2·无背景版 | **伞下的守护·无背景版** |
| 果敢 | `guogan_2_n_hx` | 皮肤2·无背景版·和谐版 | **伞下的守护·和谐版·无背景版** |
| 古手川唯 | `gushouchuan_2_tolove` | 皮肤2·tolove | **风纪委员的休息日** |
| 古手川唯 | `gushouchuan_2_tolove_n` | 皮肤2·tolove·无背景版 | **风纪委员的休息日·无背景版** |
| 古鹰 | `guying_g` | G | **古鹰.改** |
| 哈尔滨 | `haerbin_2` | 皮肤2 | **奔放的水天一色** |
| 哈尔滨 | `haerbin_3` | 皮肤3 | **奢享于盛夏之滨** |
| 哈尔滨 | `haerbin_3_n` | 皮肤3·无背景版 | **奢享于盛夏之滨·无背景版** |
| 哈尔滨 | `haerbin_h` | h | **牡丹红** |
| 哈尔滨 | `haerbin_h_n` | h·无背景版 | **牡丹红·无背景版** |
| 哈尔福德 | `haerfude_2` | 皮肤2 | **血族亲王的限定陪伴日** |
| 哈尔福德 | `haerfude_2_n` | 皮肤2·无背景版 | **血族亲王的限定陪伴日·无背景版** |
| 哈尔西·鲍威尔 | `haerxibaoweier_3` | 皮肤3 | **春节小福星！** |
| 海筹 | `haichou_2` | 皮肤2 | **醒梦芳醇** |
| 海筹 | `haichou_2_asmr` | 皮肤2·ASMR | **醒梦芳醇** |
| 海筹 | `haichou_2_n` | 皮肤2·无背景版 | **醒梦芳醇·无背景版** |
| 海风 | `haifeng_2` | 皮肤2 | **软绵绵治愈系** |
| 海风 | `haifeng_2_n` | 皮肤2·无背景版 | **软绵绵治愈系·无背景版** |
| 海风 | `haifeng_3` | 皮肤3 | **渐近的步伐** |
| 海风 | `haifeng_3_n` | 皮肤3·无背景版 | **渐近的步伐·无背景版** |
| 海伦娜 | `hailunna_2` | 皮肤2 | **正月与青鸟** |
| 海伦娜 | `hailunna_3` | 皮肤3 | **与君共舞** |
| 海伦娜 | `hailunna_4` | 皮肤4 | **耀眼的波纹** |
| 海伦娜 | `hailunna_4_n` | 皮肤4·无背景版 | **耀眼的波纹·无背景版** |
| 海伦娜 | `hailunna_5` | 皮肤5 | **桧木温香，暖意一刻** |
| 海伦娜 | `hailunna_5_n` | 皮肤5·无背景版 | **桧木温香，暖意一刻·无背景版** |
| 海伦娜 | `hailunna_alter` | alter | **海伦娜·META** |
| 海伦娜 | `hailunna_g` | G | **海伦娜.改** |
| 海伦娜 | `hailunna_h` | h | **纯白的奇迹** |
| 海伦娜 | `hailunna_younv` | younv | **小海伦娜** |
| 海圻 | `haiqi_2` | 皮肤2 | **清池乐舞** |
| 海容 | `hairong_2` | 皮肤2 | **枫染印象** |
| 海容 | `hairong_2_n` | 皮肤2·无背景版 | **枫染印象·无背景版** |
| 海天 | `haitian_2` | 皮肤2 | **书香水榭** |
| 海天 | `haitian_2_n` | 皮肤2·无背景版 | **书香水榭·无背景版** |
| 海天 | `haitian_3` | 皮肤3 | **翩若飞仙** |
| 海天 | `haitian_3_n` | 皮肤3·无背景版 | **翩若飞仙·无背景版** |
| 海天 | `haitian_4` | 皮肤4 | **秋夜漫游** |
| 海天 | `haitian_4_n` | 皮肤4·无背景版 | **秋夜漫游·无背景版** |
| 海天 | `haitian_5` | 皮肤5 | **巧手凝情伴香酥** |
| 海天 | `haitian_h` | h | **鸾凤和鸣** |
| 海天 | `haitian_h_n` | h·无背景版 | **鸾凤和鸣·无背景版** |
| 海豚号 | `haitunhao_2` | 皮肤2 | **复苏的魔咒** |
| 海豚号 | `haitunhao_2_n` | 皮肤2·无背景版 | **复苏的魔咒·无背景版** |
| 海王星 | `haiwangxing_2` | 皮肤2 | **圣诞麋鹿公主** |
| 海王星 | `haiwangxing_2_n` | 皮肤2·无背景版 | **圣诞麋鹿公主·无背景版** |
| 海王星 | `haiwangxing_3` | 皮肤3 | **海洋女王的迎接** |
| 海王星 | `haiwangxing_3_n` | 皮肤3·无背景版 | **海洋女王的迎接·无背景版** |
| 海王星 | `haiwangxing_4` | 皮肤4 | **兔警官办案中！** |
| 海王星 | `haiwangxing_4_n` | 皮肤4·无背景版 | **兔警官办案中！·无背景版** |
| 海咲 | `haixiao_2_doa` | 皮肤2·doa | **金色的特别摄影** |
| 海咲 | `haixiao_3_doa` | 皮肤3·doa | **夜空盛放之花** |
| 海咲 | `haixiao_3_doa_n` | 皮肤3·doa·无背景版 | **夜空盛放之花·无背景版** |
| 海咲 | `haixiao_doa` | doa | **海咲** ⚠名字塌了(==船名) |
| 海咲 | `haixiao_doa_wjz` | doa·wjz | **海咲** ⚠名字塌了(==船名) |
| 海因里希亲王 | `haiyinlixi_2` | 皮肤2 | **泳池边的救生兔(?)** |
| 海因里希亲王 | `haiyinlixi_2_n` | 皮肤2·无背景版 | **泳池边的救生兔(?)·无背景版** |
| 海因里希亲王 | `haiyinlixi_3` | 皮肤3 | **花火烂漫的春绘卷** |
| 海因里希亲王 | `haiyinlixi_3_n` | 皮肤3·无背景版 | **花火烂漫的春绘卷·无背景版** |
| 海因里希亲王 | `haiyinlixi_4` | 皮肤4 | **专属舞台·Heinrich** |
| 海因里希亲王 | `haiyinlixi_4_n` | 皮肤4·无背景版 | **专属舞台·Heinrich·无背景版** |
| 海因里希亲王 | `haiyinlixi_5` | 皮肤5 | **暗处的秘密老大？** |
| 海因里希亲王 | `haiyinlixi_5_n` | 皮肤5·无背景版 | **暗处的秘密老大？·无背景版** |
| 哈里森 | `halisen_2` | 皮肤2 | **提前开始的追逐赛？** |
| 哈里森 | `halisen_2_n` | 皮肤2·无背景版 | **提前开始的追逐赛？·无背景版** |
| 哈曼 | `haman_2` | 皮肤2 | **小小的夏日战争** |
| 哈曼 | `haman_3` | 皮肤3 | **舞会的傲娇妖精** |
| 哈曼 | `haman_3_n` | 皮肤3·无背景版 | **舞会的傲娇妖精·无背景版** |
| 哈曼 | `haman_4` | 皮肤4 | **兽耳喵喵拳！** |
| 哈曼 | `haman_4_n` | 皮肤4·无背景版 | **兽耳喵喵拳！·无背景版** |
| 哈曼 | `haman_5` | 皮肤5 | **圣诞Surprise！** |
| 哈曼 | `haman_6` | 皮肤6 | **Blushing Fellow** |
| 哈曼 | `haman_6_n` | 皮肤6·无背景版 | **Blushing Fellow·无背景版** |
| 哈曼 | `haman_g` | G | **哈曼.改** |
| 哈曼 | `hamanii_2` | 皮肤2 | **再一次(?)的夏日战争** |
| 哈曼 | `hamanii_3` | 皮肤3 | **哈曼的美味魔法** |
| 哈曼 | `hamanii_3_n` | 皮肤3·无背景版 | **哈曼的美味魔法·无背景版** |
| 哈曼 | `hamanii_n` | 无背景版 | **哈曼II·无背景版** |
| 豪 | `hao_2` | 皮肤2 | **Noble Rouge** |
| 豪 | `hao_2_n` | 皮肤2·无背景版 | **Noble Rouge·无背景版** |
| 豪 | `hao_4` | 皮肤4 | **Cookie·Maid·Princess** |
| 豪 | `hao_5` | 皮肤5 | **奢华之夜宴** |
| 豪 | `hao_5_hx` | 皮肤5·和谐版 | **奢华之夜宴·和谐版** |
| 好人理查德 | `haorenlichade_alter` | alter | **好人理查德** ⚠名字塌了(==船名) |
| 绀紫之心 | `hdn102_1` | 皮肤1 | **绀紫之心** ⚠名字塌了(==船名) |
| 绀紫之心 | `hdn102_2` | 皮肤2 | **女神的约定** |
| 圣黑之心 | `hdn202_1` | 皮肤1 | **圣黑之心** ⚠名字塌了(==船名) |
| 圣黑之心 | `hdn202_2` | 皮肤2 | **女神的微笑** |
| 圣黑之心 | `hdn202_2_hx` | 皮肤2·和谐版 | **女神的微笑·和谐版** |
| 布兰 | `hdn301_memory` | memory | **布兰** ⚠名字塌了(==船名) |
| 群白之心 | `hdn302_1` | 皮肤1 | **群白之心** ⚠名字塌了(==船名) |
| 群白之心 | `hdn302_2` | 皮肤2 | **女神的羞怯** |
| 贝露 | `hdn401_memory` | memory | **贝露** ⚠名字塌了(==船名) |
| 翡绿之心 | `hdn402_1` | 皮肤1 | **翡绿之心** ⚠名字塌了(==船名) |
| 翡绿之心 | `hdn402_2` | 皮肤2 | **女神的一刻** |
| 翡绿之心 | `hdn402_2_hx` | 皮肤2·和谐版 | **女神的一刻·和谐版** |
| 貉 | `he_2` | 皮肤2 | **金色的步行道** |
| 貉 | `he_2_n` | 皮肤2·无背景版 | **金色的步行道·无背景版** |
| 黑暗界 | `heianjie_2` | 皮肤2 | **虚幻的幸福** |
| 黑暗界 | `heianjie_3` | 皮肤3 | **变装魔法** |
| 黑太子 | `heitaizi_2` | 皮肤2 | **White Princess** |
| 黑太子 | `heitaizi_3` | 皮肤3 | **Fairmaid·Spring** |
| 黑太子 | `heitaizi_4` | 皮肤4 | **Pop The Cork** |
| 黑太子 | `heitaizi_4_n` | 皮肤4·无背景版 | **Pop The Cork·无背景版** |
| 黑太子 | `heitaizi_5` | 皮肤5 | **迷糊的侍者？** |
| 黑太子 | `heitaizi_5_n` | 皮肤5·无背景版 | **迷糊的侍者？·无背景版** |
| 黑太子 | `heitaizi_h` | h | **Love's Greeting（爱的礼赞）** ⚠长度异常 |
| 黑太子 | `heitaizi_h_n` | h·无背景版 | **Love's Greeting（爱的礼赞）·无背景版** ⚠长度异常 |
| BLACK★ROCK SHOOTER（后排） | `heiyansheshou_2` | 皮肤2 | **黑之女神** |
| BLACK★ROCK SHOOTER（后排） | `heiyansheshou_2_n` | 皮肤2·无背景版 | **黑之女神·无背景版** |
| BLACK★ROCK SHOOTER（后排） | `heiyansheshou_n` | 无背景版 | **BLACK★ROCK SHOOTER·无背景版** |
| BLACK★ROCK SHOOTER（后排） | `heiyansheshou_wjz` | wjz | **BLACK★ROCK SHOOTER** |
| 赫敏 | `hemin_2` | 皮肤2 | **纯白的悠闲假日** |
| 赫敏 | `hemin_2_n` | 皮肤2·无背景版 | **纯白的悠闲假日·无背景版** |
| 赫敏 | `hemin_3` | 皮肤3 | **温柔的纯白天使** |
| 赫敏 | `hemin_3_n` | 皮肤3·无背景版 | **温柔的纯白天使·无背景版** |
| 赫敏 | `hemin_4` | 皮肤4 | **女仆的优雅午后** |
| 赫敏 | `hemin_4_n` | 皮肤4·无背景版 | **女仆的优雅午后·无背景版** |
| 赫敏 | `hemin_5` | 皮肤5 | **百草堂少女** |
| 赫敏 | `hemin_5_n` | 皮肤5·无背景版 | **百草堂少女·无背景版** |
| 赫敏 | `hemin_6` | 皮肤6 | **甜蜜的浓醇冬日** |
| 赫敏 | `hemin_6_n` | 皮肤6·无背景版 | **甜蜜的浓醇冬日·无背景版** |
| 赫敏 | `hemin_h` | h | **晨曦的誓言** |
| 赫敏 | `hemin_h_n` | h·无背景版 | **晨曦的誓言·无背景版** |
| 和睦号 | `hemuhao_2` | 皮肤2 | **友好的弗兰肯** |
| 和睦号 | `hemuhao_2_n` | 皮肤2·无背景版 | **友好的弗兰肯·无背景版** |
| 仲裁者·赫米忒·IX | `hermit_alter` | alter | **仲裁者·赫米忒·IX** ⚠名字塌了(==船名) |
| 赫斯缇雅 | `hesitiya_2` | 皮肤2 | **God Vacation！** |
| 赫斯缇雅 | `hesitiya_2_n` | 皮肤2·无背景版 | **God Vacation！·无背景版** |
| 赫斯缇雅 | `hesitiya_wjz` | wjz | **赫斯缇雅** ⚠名字塌了(==船名) |
| 洪亮 | `hongliang_2` | 皮肤2 | **清晨的呼唤！** |
| 红色山脉 | `hongseshanmai_2` | 皮肤2 | **盲打练习：触觉麻将** |
| 红色山脉 | `hongseshanmai_2_n` | 皮肤2·无背景版 | **盲打练习：触觉麻将·无背景版** |
| 虎 | `hu_2` | 皮肤2 | **临水的辰星** |
| 虎 | `hu_2_asmr` | 皮肤2·ASMR | **临水的辰星** |
| 虎 | `hu_2_asmr_hx` | 皮肤2·ASMR·和谐版 | **临水的辰星·和谐版** |
| 虎 | `hu_2_hx` | 皮肤2·和谐版 | **临水的辰星·和谐版** |
| 虎 | `hu_2_n` | 皮肤2·无背景版 | **临水的辰星·无背景版** |
| 虎 | `hu_2_n_hx` | 皮肤2·无背景版·和谐版 | **临水的辰星·和谐版·无背景版** |
| 华甲 | `huajia_2` | 皮肤2 | **欢乐喜庆僵尸夜** |
| 华甲 | `huajia_2_hx` | 皮肤2·和谐版 | **欢乐喜庆僵尸夜·和谐版** |
| 华甲 | `huajia_2_n` | 皮肤2·无背景版 | **欢乐喜庆僵尸夜·无背景版** |
| 华甲 | `huajia_2_n_hx` | 皮肤2·无背景版·和谐版 | **欢乐喜庆僵尸夜·和谐版·无背景版** |
| 华甲 | `huajia_3` | 皮肤3 | **若漆之光** |
| 华甲 | `huajia_3_n` | 皮肤3·无背景版 | **若漆之光·无背景版** |
| 华甲 | `huajia_g` | G | **华甲.改** |
| 华甲 | `huajia_g_n` | G·无背景版 | **华甲.改·无背景版** |
| 花剑 | `huajian_2` | 皮肤2 | **幸运之夜** |
| 花剑 | `huajian_2_n` | 皮肤2·无背景版 | **幸运之夜·无背景版** |
| 华丽 | `huali_2` | 皮肤2 | **唇齿之间** |
| 华丽 | `huali_2_n` | 皮肤2·无背景版 | **唇齿之间·无背景版** |
| 环 | `huan_2_doa` | 皮肤2·doa | **女神的沐浴时间** |
| 环 | `huan_doa` | doa | **环** ⚠名字塌了(==船名) |
| 寰昌 | `huanchang_2` | 皮肤2 | **月下蹁跹** |
| 寰昌 | `huanchang_2_n` | 皮肤2·无背景版 | **月下蹁跹·无背景版** |
| 荒潮 | `huangchao_3` | 皮肤3 | **映照花火** |
| 荒潮 | `huangchao_3_n` | 皮肤3·无背景版 | **映照花火·无背景版** |
| 皇家财富号 | `huangjiacaifu_2` | 皮肤2 | **邪神（?）的“美餐”** |
| 皇家财富号 | `huangjiacaifu_2_n` | 皮肤2·无背景版 | **邪神（?）的“美餐”·无背景版** |
| 皇家财富号 | `huangjiacaifu_3` | 皮肤3 | **海边的约定** |
| 皇家财富号 | `huangjiacaifu_3_n` | 皮肤3·无背景版 | **海边的约定·无背景版** |
| 皇家方舟 | `huangjiafangzhou_2` | 皮肤2 | **沙滩守望者** |
| 皇家方舟 | `huangjiafangzhou_3` | 皮肤3 | **晚会的守护者** |
| 皇家方舟 | `huangjiafangzhou_4` | 皮肤4 | **新年的守护者** |
| 皇家方舟 | `huangjiafangzhou_5` | 皮肤5 | **咖啡馆的观察约会？** |
| 皇家方舟 | `huangjiafangzhou_5_n` | 皮肤5·无背景版 | **咖啡馆的观察约会？·无背景版** |
| 皇家方舟 | `huangjiafangzhou_6` | 皮肤6 | **乐园的秩序官** |
| 皇家方舟 | `huangjiafangzhou_6_n` | 皮肤6·无背景版 | **乐园的秩序官·无背景版** |
| 皇家方舟 | `huangjiafangzhou_alter` | alter | **皇家方舟·META** |
| 皇家方舟 | `huangjiafangzhou_g` | G | **皇家方舟.改** |
| 皇家方舟 | `huangjiafangzhou_h` | h | **纯白的守护者** |
| 皇家橡树 | `huangjiaxiangshu_2` | 皮肤2 | **忧郁少女想要逃避** |
| 皇家橡树 | `huangjiaxiangshu_2_n` | 皮肤2·无背景版 | **忧郁少女想要逃避·无背景版** |
| 皇家詹姆斯号 | `huangjiazhanmusi_2` | 皮肤2 | **初生禁忌的啜吸** |
| 皇家詹姆斯号 | `huangjiazhanmusi_2_hx` | 皮肤2·和谐版 | **初生禁忌的啜吸·和谐版** |
| 皇家詹姆斯号 | `huangjiazhanmusi_2_n` | 皮肤2·无背景版 | **初生禁忌的啜吸·无背景版** |
| 皇家詹姆斯号 | `huangjiazhanmusi_2_n_hx` | 皮肤2·无背景版·和谐版 | **初生禁忌的啜吸·和谐版·无背景版** |
| 幻想号 | `huanxianghao_2` | 皮肤2 | **颤动心房的“恐怖”** |
| 幻想号 | `huanxianghao_2_n` | 皮肤2·无背景版 | **颤动心房的“恐怖”·无背景版** |
| 华盛顿 | `huashengdun_2` | 皮肤2 | **微笑嘉年华** |
| 华盛顿 | `huashengdun_2_n` | 皮肤2·无背景版 | **微笑嘉年华·无背景版** |
| 华盛顿 | `huashengdun_3` | 皮肤3 | **夜间巡诊** |
| 华盛顿 | `huashengdun_3_hx` | 皮肤3·和谐版 | **夜间巡诊·和谐版** |
| 华盛顿 | `huashengdun_3_n` | 皮肤3·无背景版 | **夜间巡诊·无背景版** |
| 华盛顿 | `huashengdun_3_n_hx` | 皮肤3·无背景版·和谐版 | **夜间巡诊·和谐版·无背景版** |
| 花月 | `huayue_3` | 皮肤3 | **白昼月、盛夏之华** |
| 花月 | `huayue_4` | 皮肤4 | **春意·月华盎然** |
| 花月 | `huayue_4_n` | 皮肤4·无背景版 | **春意·月华盎然·无背景版** |
| 虎贲 | `huben_2` | 皮肤2 | **舞虎迎春** |
| 虎贲 | `huben_2_n` | 皮肤2·无背景版 | **舞虎迎春·无背景版** |
| 胡德 | `hude_2` | 皮肤2 | **照耀太阳的淑女** |
| 胡德 | `hude_3` | 皮肤3 | **五彩的Glorius** |
| 胡德 | `hude_3_n` | 皮肤3·无背景版 | **五彩的Glorius·无背景版** |
| 胡德 | `hude_4` | 皮肤4 | **晨曦的淑女** |
| 胡德 | `hude_4_hx` | 皮肤4·和谐版 | **晨曦的淑女·和谐版** |
| 胡德 | `hude_4_n` | 皮肤4·无背景版 | **晨曦的淑女·无背景版** |
| 胡德 | `hude_4_n_hx` | 皮肤4·无背景版·和谐版 | **晨曦的淑女·和谐版·无背景版** |
| 胡德 | `hude_5` | 皮肤5 | **白马与皇家骑士** |
| 胡德 | `hude_5_n` | 皮肤5·无背景版 | **白马与皇家骑士·无背景版** |
| 胡德 | `hude_6` | 皮肤6 | **仅予一人的华宴** |
| 胡德 | `hude_6_n` | 皮肤6·无背景版 | **仅予一人的华宴·无背景版** |
| 胡德 | `hude_h` | h | **蔷薇恋诗** |
| 彗星 | `huixing_g` | G | **彗星.改** |
| 霍比 | `huobi_2` | 皮肤2 | **小小学园偶像** |
| 火力 | `huoli_2` | 皮肤2 | **正义新星** |
| 火力 | `huoli_2_n` | 皮肤2·无背景版 | **正义新星·无背景版** |
| 火奴鲁鲁 | `huonululu_2` | 皮肤2 | **阳伞下的同桌** |
| 火奴鲁鲁 | `huonululu_3` | 皮肤3 | **盛夏的「灾难」** |
| 火奴鲁鲁 | `huonululu_4` | 皮肤4 | **大胆(?)的麋鹿小姐** |
| 火奴鲁鲁 | `huonululu_5` | 皮肤5 | **两人的夏日祭** |
| 火奴鲁鲁 | `huonululu_5_n` | 皮肤5·无背景版 | **两人的夏日祭·无背景版** |
| 狐提 | `huti_g` | G | **狐提.改** |
| 伊13 | `i13_3` | 皮肤3 | **放学后的观察作业** |
| 伊13 | `i13_3_n` | 皮肤3·无背景版 | **放学后的观察作业·无背景版** |
| 伊14 | `i14_2` | 皮肤2 | **千面皆虚无** |
| 伊14 | `i14_2_n` | 皮肤2·无背景版 | **千面皆虚无·无背景版** |
| 伊168 | `i168_2` | 皮肤2 | **祭典之日！** |
| 伊19 | `i19_2` | 皮肤2 | **启程的微风** |
| 伊19 | `i19_2_hx` | 皮肤2·和谐版 | **启程的微风·和谐版** |
| 伊19 | `i19_3` | 皮肤3 | **枕头天堂** |
| 伊19 | `i19_4` | 皮肤4 | **粉红甜心兔** |
| 伊19 | `i19_4_n` | 皮肤4·无背景版 | **粉红甜心兔·无背景版** |
| 伊25 | `i25_2` | 皮肤2 | **兔兔与珊瑚礁** |
| 伊25 | `i25_3` | 皮肤3 | **甘美的新春祝福** |
| 伊25 | `i25_3_n` | 皮肤3·无背景版 | **甘美的新春祝福·无背景版** |
| 伊26 | `i26_2` | 皮肤2 | **深海少女** |
| 伊26 | `i26_3` | 皮肤3 | **烟火大会前** |
| 伊26 | `i26_3_n` | 皮肤3·无背景版 | **烟火大会前·无背景版** |
| 伊404 | `i404_2` | 皮肤2 | **绛縢华舞** |
| 伊404 | `i404_2_n` | 皮肤2·无背景版 | **绛縢华舞·无背景版** |
| 伊404 | `i404_3` | 皮肤3 | **绛縢华舞** |
| 伊404 | `i404_3_n` | 皮肤3·无背景版 | **绛縢华舞·无背景版** |
| 伊56 | `i56_2` | 皮肤2 | **角落的向日葵** |
| 加富尔伯爵 | `jiafuerbojue_2` | 皮肤2 | **激战的盛夏海滩** |
| 加富尔伯爵 | `jiafuerbojue_2_hx` | 皮肤2·和谐版 | **激战的盛夏海滩·和谐版** |
| 加富尔伯爵 | `jiafuerbojue_2_n` | 皮肤2·无背景版 | **激战的盛夏海滩·无背景版** |
| 加富尔伯爵 | `jiafuerbojue_2_n_hx` | 皮肤2·无背景版·和谐版 | **激战的盛夏海滩·和谐版·无背景版** |
| 加古 | `jiagu_g` | G | **加古.改** |
| 加贺 | `jiahe_2` | 皮肤2 | **常夏的杀生石** |
| 加贺 | `jiahe_3` | 皮肤3 | **白狐贺正** |
| 加贺 | `jiahe_4` | 皮肤4 | **淡樱之息** |
| 加贺 | `jiahe_4_n` | 皮肤4·无背景版 | **淡樱之息·无背景版** |
| 加贺 | `jiahe_5` | 皮肤5 | **白羽风华** |
| 加贺 | `jiahe_6` | 皮肤6 | **鸾翔影集** |
| 加贺 | `jiahe_6_n` | 皮肤6·无背景版 | **鸾翔影集·无背景版** |
| 加贺 | `jiahe_7` | 皮肤7 | **狐舞白绢** |
| 加贺 | `jiahe_7_n` | 皮肤7·无背景版 | **狐舞白绢·无背景版** |
| 加贺 | `jiahe_h` | h | **苍染的君子兰** |
| 加里冒险号 | `jialimaoxian_2` | 皮肤2 | **赤月下的“晚餐会”** |
| 加里冒险号 | `jialimaoxian_2_n` | 皮肤2·无背景版 | **赤月下的“晚餐会”·无背景版** |
| 拉·加利索尼埃 | `jialisuoniye_2` | 皮肤2 | **无垢的Piscine** |
| 拉·加利索尼埃 | `jialisuoniye_3` | 皮肤3 | **黑猫与南瓜之夜** |
| 拉·加利索尼埃 | `jialisuoniye_3_hx` | 皮肤3·和谐版 | **黑猫与南瓜之夜·和谐版** |
| 拉·加利索尼埃 | `jialisuoniye_3_n` | 皮肤3·无背景版 | **黑猫与南瓜之夜·无背景版** |
| 拉·加利索尼埃 | `jialisuoniye_3_n_hx` | 皮肤3·无背景版·和谐版 | **黑猫与南瓜之夜·和谐版·无背景版** |
| 拉·加利索尼埃 | `jialisuoniye_4` | 皮肤4 | **春晓醉梦** |
| 拉·加利索尼埃 | `jialisuoniye_4_n` | 皮肤4·无背景版 | **春晓醉梦·无背景版** |
| 拉·加利索尼埃 | `jialisuoniye_alter` | alter | **拉·加利索尼埃·META ** |
| 拉·加利索尼埃 | `jialisuoniye_alter_hx` | alter·和谐版 | **拉·加利索尼埃·META ·和谐版** |
| 济安 | `jian_2` | 皮肤2 | **华灯夜游** |
| 济安 | `jian_2_n` | 皮肤2·无背景版 | **华灯夜游·无背景版** |
| 济安 | `jian_3` | 皮肤3 | **异域绮梦** |
| 济安 | `jian_3_hx` | 皮肤3·和谐版 | **异域绮梦·和谐版** |
| 济安 | `jian_3_n` | 皮肤3·无背景版 | **异域绮梦·无背景版** |
| 济安 | `jian_3_n_hx` | 皮肤3·无背景版·和谐版 | **异域绮梦·和谐版·无背景版** |
| 江风 | `jiangfeng_2` | 皮肤2 | **间奏·黑白** |
| 江风 | `jiangfeng_3` | 皮肤3 | **忠心的守护灵狐** |
| 江风 | `jiangfeng_3_n` | 皮肤3·无背景版 | **忠心的守护灵狐·无背景版** |
| 江风 | `jiangfeng_h` | h | **美梦构造论** |
| 建武 | `jianwu_2` | 皮肤2 | **妆点，只为今夜** |
| 建武 | `jianwu_2_n` | 皮肤2·无背景版 | **妆点，只为今夜·无背景版** |
| 建武 | `jianwu_3` | 皮肤3 | **妆点，只为今夜** |
| 建武 | `jianwu_3_n` | 皮肤3·无背景版 | **妆点，只为今夜·无背景版** |
| 建武 | `jianwu_4` | 皮肤4 | **彻夜的杰作** |
| 建武 | `jianwu_4_n` | 皮肤4·无背景版 | **彻夜的杰作·无背景版** |
| 樫野 | `jianye_2` | 皮肤2 | **温泉放松时间** |
| 樫野 | `jianye_2_hx` | 皮肤2·和谐版 | **温泉放松时间·和谐版** |
| 樫野 | `jianye_2_n` | 皮肤2·无背景版 | **温泉放松时间·无背景版** |
| 樫野 | `jianye_2_n_hx` | 皮肤2·无背景版·和谐版 | **温泉放松时间·和谐版·无背景版** |
| 樫野 | `jianye_3` | 皮肤3 | **绊倒的迷糊女仆** |
| 樫野 | `jianye_4` | 皮肤4 | **花绽之乐章** |
| 樫野 | `jianye_4_n` | 皮肤4·无背景版 | **花绽之乐章·无背景版** |
| 樫野 | `jianye_5` | 皮肤5 | **新鲜与甜蜜！** |
| 樫野 | `jianye_5_hx` | 皮肤5·和谐版 | **新鲜与甜蜜！·和谐版** |
| 樫野 | `jianye_5_n` | 皮肤5·无背景版 | **新鲜与甜蜜！·无背景版** |
| 樫野 | `jianye_5_n_hx` | 皮肤5·无背景版·和谐版 | **新鲜与甜蜜！·和谐版·无背景版** |
| 焦苏埃·卡尔杜齐 | `jiaosuai_2` | 皮肤2 | **定格的诗篇** |
| 焦苏埃·卡尔杜齐 | `jiaosuai_2_n` | 皮肤2·无背景版 | **定格的诗篇·无背景版** |
| 加斯科涅 | `jiasikenie_2` | 皮肤2 | **夏季环境应对外装** |
| 加斯科涅 | `jiasikenie_2_n` | 皮肤2·无背景版 | **夏季环境应对外装·无背景版** |
| 加斯科涅 | `jiasikenie_3` | 皮肤3 | **旅情机巧** |
| 加斯科涅 | `jiasikenie_3_n` | 皮肤3·无背景版 | **旅情机巧·无背景版** |
| 加斯科涅 | `jiasikenie_idol` | idol | **加斯科涅(μ兵装)** |
| 加斯科涅 | `jiasikenie_idolns` | idolns | **加斯科涅(μ兵装)** |
| 贾维斯 | `jiaweisi_2` | 皮肤2 | **青空下的微风** |
| 杰金斯 | `jiejinsi_3` | 皮肤3 | **星光与白雪的平安夜** |
| 杰金斯 | `jiejinsi_3_n` | 皮肤3·无背景版 | **星光与白雪的平安夜·无背景版** |
| 矶风 | `jifeng_2` | 皮肤2 | **新年合战** |
| 矶风 | `jifeng_3` | 皮肤3 | **战国组合！** |
| 矶风 | `jifeng_3_n` | 皮肤3·无背景版 | **战国组合！·无背景版** |
| 基辅 | `jifu_2` | 皮肤2 | **夜巷的银色奏鸣曲** |
| 基辅 | `jifu_2_n` | 皮肤2·无背景版 | **夜巷的银色奏鸣曲·无背景版** |
| 基辅 | `jifu_3` | 皮肤3 | **冰上的精灵** |
| 基辅 | `jifu_3_n` | 皮肤3·无背景版 | **冰上的精灵·无背景版** |
| 基洛夫 | `jiluofu_2` | 皮肤2 | **居家咖啡时间** |
| 基洛夫 | `jiluofu_2_n` | 皮肤2·无背景版 | **居家咖啡时间·无背景版** |
| 基洛夫 | `jiluofu_3` | 皮肤3 | **疾速截击** |
| 基洛夫 | `jiluofu_3_n` | 皮肤3·无背景版 | **疾速截击·无背景版** |
| 基洛夫 | `jiluofu_4` | 皮肤4 | **巅峰之星** |
| 基洛夫 | `jiluofu_4_n` | 皮肤4·无背景版 | **巅峰之星·无背景版** |
| 基洛夫·META（后排） | `jiluofu_alter_n` | 无背景版 | **基洛夫·META·无背景版** |
| 金伯利 | `jinboli_3` | 皮肤3 | **东煌之风** |
| 金刚 | `jingang_2` | 皮肤2 | **华鸟风月** |
| 金刚 | `jingang_3` | 皮肤3 | **Talent Hospital** |
| 金刚 | `jingang_3_n` | 皮肤3·无背景版 | **Talent Hospital·无背景版** |
| 金刚 | `jingang_4` | 皮肤4 | **微风的上学路** |
| 金刚 | `jingang_4_n` | 皮肤4·无背景版 | **微风的上学路·无背景版** |
| 金刚 | `jingang_5` | 皮肤5 | **海浪之下的意外** |
| 金刚 | `jingang_5_n` | 皮肤5·无背景版 | **海浪之下的意外·无背景版** |
| 金刚 | `jingang_idol` | idol | **金刚(μ兵装)** |
| 金刚 | `jingang_idol_n` | idol·无背景版 | **金刚(μ兵装)·无背景版** |
| 竞技神 | `jingjishen_g` | G | **竞技神.改** |
| 近江 | `jinjiang_2` | 皮肤2 | **逃脱失败……？** |
| 近江 | `jinjiang_2_hx` | 皮肤2·和谐版 | **逃脱失败……？·和谐版** |
| 近江 | `jinjiang_2_n` | 皮肤2·无背景版 | **逃脱失败……？·无背景版** |
| 近江 | `jinjiang_2_n_hx` | 皮肤2·无背景版·和谐版 | **逃脱失败……？·和谐版·无背景版** |
| 金鹿号 | `jinluhao_2` | 皮肤2 | **古堡中的恐怖淑女** |
| 金鹿号 | `jinluhao_2_n` | 皮肤2·无背景版 | **古堡中的恐怖淑女·无背景版** |
| 金鹿号 | `jinluhao_3` | 皮肤3 | **微笑的白色魅影** |
| 金鹿号 | `jinluhao_3_hx` | 皮肤3·和谐版 | **微笑的白色魅影·和谐版** |
| 金鹿号 | `jinluhao_3_n` | 皮肤3·无背景版 | **微笑的白色魅影·无背景版** |
| 金鹿号 | `jinluhao_3_n_hx` | 皮肤3·无背景版·和谐版 | **微笑的白色魅影·和谐版·无背景版** |
| 金鹿号 | `jinluhao_4` | 皮肤4 | **微笑的白色魅影** |
| 金鹿号 | `jinluhao_4_n` | 皮肤4·无背景版 | **微笑的白色魅影·无背景版** |
| 金色暗影 | `jinseanying_2_tolove` | 皮肤2·tolove | **朋友们的睡衣装备** |
| 金色暗影 | `jinseanying_2_tolove_n` | 皮肤2·tolove·无背景版 | **朋友们的睡衣装备·无背景版** |
| 金狮 | `jinshi_2` | 皮肤2 | **朦胧的宠溺时刻** |
| 金狮 | `jinshi_2_hx` | 皮肤2·和谐版 | **朦胧的宠溺时刻·和谐版** |
| 金狮 | `jinshi_2_n` | 皮肤2·无背景版 | **朦胧的宠溺时刻·无背景版** |
| 金狮 | `jinshi_2_n_hx` | 皮肤2·无背景版·和谐版 | **朦胧的宠溺时刻·和谐版·无背景版** |
| 棘鳍 | `jiqi_2` | 皮肤2 | **便利店大作战！** |
| 棘鳍 | `jiqi_3` | 皮肤3 | **五彩斑斓的宴会** |
| 吉尚 | `jishang_2` | 皮肤2 | **冰上的魔女** |
| 吉尚 | `jishang_2_n` | 皮肤2·无背景版 | **冰上的魔女·无背景版** |
| 吉尚 | `jishang_3` | 皮肤3 | **Milk&Kiss** |
| 吉尚 | `jishang_3_asmr` | 皮肤3·ASMR | **Milk&Kiss** |
| 吉尚 | `jishang_3_n` | 皮肤3·无背景版 | **Milk&Kiss·无背景版** |
| 旧金山 | `jiujinshan_3` | 皮肤3 | **Funny Bunny！** |
| 旧金山 | `jiujinshan_3_hx` | 皮肤3·和谐版 | **Funny Bunny！·和谐版** |
| 旧金山 | `jiujinshan_3_n` | 皮肤3·无背景版 | **Funny Bunny！·无背景版** |
| 旧金山 | `jiujinshan_3_n_hx` | 皮肤3·无背景版·和谐版 | **Funny Bunny！·和谐版·无背景版** |
| 旧金山 | `jiujinshan_4` | 皮肤4 | **It's showtime!** |
| 旧金山 | `jiujinshan_4_n` | 皮肤4·无背景版 | **It's showtime!·无背景版** |
| 旧金山 | `jiujinshan_wjz` | wjz | **旧金山** ⚠名字塌了(==船名) |
| 久远 | `jiuyuan_2` | 皮肤2 | **久远(传颂之物)** |
| 酒匂 | `jiuyun_2` | 皮肤2 | **团子的诱惑** |
| 酒匂 | `jiuyun_2_n` | 皮肤2·无背景版 | **团子的诱惑·无背景版** |
| 酒匂 | `jiuyun_3` | 皮肤3 | **丛林的清凉小憩** |
| 酒匂 | `jiuyun_3_n` | 皮肤3·无背景版 | **丛林的清凉小憩·无背景版** |
| 酒匂 | `jiuyun_4` | 皮肤4 | **俏佳人组曲** |
| 酒匂 | `jiuyun_4_n` | 皮肤4·无背景版 | **俏佳人组曲·无背景版** |
| 纪伊 | `jiyi_2` | 皮肤2 | **水边的诱惑** |
| 卷波 | `juanbo_2` | 皮肤2 | **元气RUN TIME！** |
| 卷波 | `juanbo_2_n` | 皮肤2·无背景版 | **元气RUN TIME！·无背景版** |
| 倔强 | `juejiang_2` | 皮肤2 | **沙滩上的魔法使(?)** |
| 骏河 | `junhe_3` | 皮肤3 | **偶遇的优等生** |
| 骏河 | `junhe_3_n` | 皮肤3·无背景版 | **偶遇的优等生·无背景版** |
| 骏河 | `junhe_4` | 皮肤4 | **“不情愿”的圣夜祭** |
| 骏河 | `junhe_4_n` | 皮肤4·无背景版 | **“不情愿”的圣夜祭·无背景版** |
| 骏河 | `junhe_5` | 皮肤5 | **百花庆云** |
| 君主 | `junzhu_2` | 皮肤2 | **素罗华威** |
| 君主 | `junzhu_3` | 皮肤3 | **赭红爵祿** |
| 君主 | `junzhu_4` | 皮肤4 | **都会神探** |
| 君主 | `junzhu_4_n` | 皮肤4·无背景版 | **都会神探·无背景版** |
| 君主 | `junzhu_5` | 皮肤5 | **海滩享受计划** |
| 君主 | `junzhu_5_n` | 皮肤5·无背景版 | **海滩享受计划·无背景版** |
| 卡尔斯鲁厄 | `kaersilue_g` | G | **卡尔斯鲁厄.改** |
| 凯尔圣 | `kaiersheng_2` | 皮肤2 | **阳光下的跑者** |
| 凯尔圣 | `kaiersheng_2_n` | 皮肤2·无背景版 | **阳光下的跑者·无背景版** |
| 凯尔圣 | `kaiersheng_3` | 皮肤3 | **神圣的怜悯并非恶事？** |
| 凯尔圣 | `kaiersheng_3_hx` | 皮肤3·和谐版 | **神圣的怜悯并非恶事？·和谐版** |
| 凯尔圣 | `kaiersheng_3_n` | 皮肤3·无背景版 | **神圣的怜悯并非恶事？·无背景版** |
| 凯尔圣 | `kaiersheng_3_n_hx` | 皮肤3·无背景版·和谐版 | **神圣的怜悯并非恶事？·和谐版·无背景版** |
| 朱利奥·凯撒 | `kaisa_2` | 皮肤2 | **锻炼达人？** |
| 朱利奥·凯撒 | `kaisa_3` | 皮肤3 | **阳光下的Alta marea** |
| 朱利奥·凯撒 | `kaisa_3_hx` | 皮肤3·和谐版 | **阳光下的Alta marea·和谐版** |
| 朱利奥·凯撒 | `kaisa_3_n` | 皮肤3·无背景版 | **阳光下的Alta marea·无背景版** |
| 朱利奥·凯撒 | `kaisa_3_n_hx` | 皮肤3·无背景版·和谐版 | **阳光下的Alta marea·和谐版·无背景版** |
| 卡菈·伊迪亚斯 | `kala_2` | 皮肤2 | **族长大厨** |
| 卡菈·伊迪亚斯 | `kala_2_n` | 皮肤2·无背景版 | **族长大厨·无背景版** |
| 喀琅施塔得 | `kalangshitade_2` | 皮肤2 | **突击行动开始！** |
| 喀琅施塔得 | `kalangshitade_2_n` | 皮肤2·无背景版 | **突击行动开始！·无背景版** |
| 喀琅施塔得 | `kalangshitade_3` | 皮肤3 | **动物特工** |
| 卡律布狄斯 | `kalvbudisi_2` | 皮肤2 | **治愈的红闺** |
| 卡律布狄斯 | `kalvbudisi_3` | 皮肤3 | **霞辉之华裳** |
| 卡律布狄斯 | `kalvbudisi_3_n` | 皮肤3·无背景版 | **霞辉之华裳·无背景版** |
| 卡律布狄斯 | `kalvbudisi_4` | 皮肤4 | **清凉的水花** |
| 卡律布狄斯 | `kalvbudisi_4_hx` | 皮肤4·和谐版 | **清凉的水花·和谐版** |
| 康克德 | `kangkede_2` | 皮肤2 | **红色苹果糖** |
| 康克德 | `kangkede_3` | 皮肤3 | **圣诞☆糖分天国** |
| 堪萨斯 | `kansasi_2` | 皮肤2 | **午夜休憩线** |
| 堪萨斯 | `kansasi_2_hx` | 皮肤2·和谐版 | **午夜休憩线·和谐版** |
| 堪萨斯 | `kansasi_2_n` | 皮肤2·无背景版 | **午夜休憩线·无背景版** |
| 堪萨斯 | `kansasi_2_n_hx` | 皮肤2·无背景版·和谐版 | **午夜休憩线·和谐版·无背景版** |
| 卡萨布兰卡 | `kasabulanka_2` | 皮肤2 | **啦啦队的休息时间** |
| 喀山 | `kashan_2` | 皮肤2 | **温煦晨光** |
| 喀山 | `kashan_2_n` | 皮肤2·无背景版 | **温煦晨光·无背景版** |
| 卡辛 | `kaxin_2` | 皮肤2 | **购物车大小姐** |
| 卡辛 | `kaxin_2_n` | 皮肤2·无背景版 | **购物车大小姐·无背景版** |
| 卡辛 | `kaxin_g` | G | **卡辛.改** |
| 科本斯 | `kebensi_2` | 皮肤2 | **心动营养灌输中** |
| 科本斯 | `kebensi_2_hx` | 皮肤2·和谐版 | **心动营养灌输中·和谐版** |
| 科本斯 | `kebensi_2_n` | 皮肤2·无背景版 | **心动营养灌输中·无背景版** |
| 科本斯 | `kebensi_2_n_hx` | 皮肤2·无背景版·和谐版 | **心动营养灌输中·和谐版·无背景版** |
| 可怖 | `kebu_2` | 皮肤2 | **阳光、大海、圣洁之青** |
| 可怖 | `kebu_2_n` | 皮肤2·无背景版 | **阳光、大海、圣洁之青·无背景版** |
| 可怖 | `kebu_3` | 皮肤3 | **静寂，微眠，安宁之白** |
| 科尔克 | `keerke_2` | 皮肤2 | **学园的雪之妖精** |
| 克莱蒙梭（前排） | `kelaimengsuo_2` | 皮肤2 | **金日煦风** |
| 克莱蒙梭（前排） | `kelaimengsuo_2_n` | 皮肤2·无背景版 | **金日煦风·无背景版** |
| 克莱蒙梭（前排） | `kelaimengsuo_n` | 无背景版 | **克莱蒙梭·无背景版** |
| 柯莱特 | `kelaite_2` | 皮肤2 | **飞高高的“自动”洗车法** |
| 柯莱特 | `kelaite_2_n` | 皮肤2·无背景版 | **飞高高的“自动”洗车法·无背景版** |
| 克拉伦斯·K·布朗森 | `kelalunsi_2` | 皮肤2 | **特殊连接测试** |
| 克拉伦斯·K·布朗森 | `kelalunsi_2_n` | 皮肤2·无背景版 | **特殊连接测试·无背景版** |
| 克雷文 | `keleiwen_2` | 皮肤2 | **操场边的拉拉队长** |
| 克利奥佩特拉 | `keliaopeitela_2` | 皮肤2 | **星辰与玫瑰** |
| 克利奥佩特拉 | `keliaopeitela_2_hx` | 皮肤2·和谐版 | **星辰与玫瑰·和谐版** |
| 克利奥佩特拉 | `keliaopeitela_2_n` | 皮肤2·无背景版 | **星辰与玫瑰·无背景版** |
| 克利奥佩特拉 | `keliaopeitela_2_n_hx` | 皮肤2·无背景版·和谐版 | **星辰与玫瑰·和谐版·无背景版** |
| 克利夫兰 | `kelifulan_2` | 皮肤2 | **恶魔降临之夜** |
| 克利夫兰 | `kelifulan_3` | 皮肤3 | **骑士之夜** |
| 克利夫兰 | `kelifulan_4` | 皮肤4 | **Road·Traveler** |
| 克利夫兰 | `kelifulan_5` | 皮肤5 | **新年对决！** |
| 克利夫兰 | `kelifulan_6` | 皮肤6 | **南方之旅** |
| 克利夫兰 | `kelifulan_6_n` | 皮肤6·无背景版 | **南方之旅·无背景版** |
| 克利夫兰 | `kelifulan_7` | 皮肤7 | **金色的指挥家** |
| 克利夫兰 | `kelifulan_7_n` | 皮肤7·无背景版 | **金色的指挥家·无背景版** |
| 克利夫兰 | `kelifulan_8` | 皮肤8 | **休息室的意外邂逅？** |
| 克利夫兰 | `kelifulan_8_n` | 皮肤8·无背景版 | **休息室的意外邂逅？·无背景版** |
| 克利夫兰 | `kelifulan_h` | h | **心动一刻** |
| 克利夫兰 | `kelifulan_idol` | idol | **克利夫兰(μ兵装)** |
| 克利夫兰 | `kelifulan_idolns` | idolns | **克利夫兰(μ兵装)** |
| 克利夫兰 | `kelifulan_younv` | younv | **小克利夫兰** |
| 科隆 | `kelong_g` | G | **科隆.改** |
| 科洛蒂娅·巴兰茨 | `keluodiya_2` | 皮肤2 | **晚安前的夜话** |
| 科洛蒂娅·巴兰茨 | `keluodiya_2_n` | 皮肤2·无背景版 | **晚安前的夜话·无背景版** |
| 科罗拉多 | `keluoladuo_2` | 皮肤2 | **科罗拉多** ⚠名字塌了(==船名) |
| 科罗拉多 | `keluoladuo_3` | 皮肤3 | **旅途的旋律** |
| 科罗拉多 | `keluoladuo_3_n` | 皮肤3·无背景版 | **旅途的旋律·无背景版** |
| 科罗拉多 | `keluoladuo_4` | 皮肤4 | **夕阳的咏叹调** |
| 科罗拉多 | `keluoladuo_4_n` | 皮肤4·无背景版 | **夕阳的咏叹调·无背景版** |
| 科罗拉多 | `keluoladuo_g` | G | **科罗拉多.改** |
| 科罗拉多 | `keluoladuo_g_n` | G·无背景版 | **科罗拉多.改·无背景版** |
| 可畏 | `kewei_2` | 皮肤2 | **海边的“皇家淑女”** |
| 可畏 | `kewei_2_n` | 皮肤2·无背景版 | **海边的“皇家淑女”·无背景版** |
| 可畏 | `kewei_3` | 皮肤3 | **梳妆的“大小姐”** |
| 可畏 | `kewei_4` | 皮肤4 | **值日时的春心萌动** |
| 可畏 | `kewei_4_n` | 皮肤4·无背景版 | **值日时的春心萌动·无背景版** |
| 可畏 | `kewei_5` | 皮肤5 | **凌乱的秘密加演** |
| 可畏 | `kewei_5_hx` | 皮肤5·和谐版 | **凌乱的秘密加演·和谐版** |
| 可畏 | `kewei_5_n` | 皮肤5·无背景版 | **凌乱的秘密加演·无背景版** |
| 可畏 | `kewei_5_n_hx` | 皮肤5·无背景版·和谐版 | **凌乱的秘密加演·和谐版·无背景版** |
| 可畏 | `kewei_6` | 皮肤6 | **纪念印记** |
| 可畏 | `kewei_6_n` | 皮肤6·无背景版 | **纪念印记·无背景版** |
| 可畏 | `kewei_idol` | idol | **可畏(μ兵装)** |
| 可畏 | `kewei_idol_n` | idol·无背景版 | **可畏(μ兵装)·无背景版** |
| 可畏 | `kewei_younv` | younv | **小可畏** |
| 可畏 | `kewei_younv_n` | younv·无背景版 | **小可畏·无背景版** |
| 试作型布里MKII | `kin_2` | 皮肤2 | **试作型先进兵装(摄影用)** |
| 恐怖 | `kongbu_2` | 皮肤2 | **万圣夜的恐怖** |
| 时崎狂三 | `kuangsan_2` | 皮肤2 | **双生蔷薇** |
| 时崎狂三 | `kuangsan_2_hx` | 皮肤2·和谐版 | **双生蔷薇·和谐版** |
| 时崎狂三 | `kuangsan_2_n` | 皮肤2·无背景版 | **双生蔷薇·无背景版** |
| 时崎狂三 | `kuangsan_2_n_hx` | 皮肤2·无背景版·和谐版 | **双生蔷薇·和谐版·无背景版** |
| 库珀 | `kubo_2` | 皮肤2 | **烈日的网球场** |
| 库珀 | `kubo_3` | 皮肤3 | **圣夜的温暖馈赠** |
| 库珀 | `kubo_3_n` | 皮肤3·无背景版 | **圣夜的温暖馈赠·无背景版** |
| 库尔斯克 | `kuersike_2` | 皮肤2 | **雾中雪狼** |
| 库尔斯克 | `kuersike_2_n` | 皮肤2·无背景版 | **雾中雪狼·无背景版** |
| 库尔斯克 | `kuersike_3` | 皮肤3 | **靡丽绮色** |
| 库尔斯克 | `kuersike_3_n` | 皮肤3·无背景版 | **靡丽绮色·无背景版** |
| 库拉索 | `kulasuo_2` | 皮肤2 | **东煌之雅** |
| 库拉索 | `kulasuo_g` | G | **库拉索.改** |
| 维托里奥·库尼贝尔蒂 | `kunibeierdi_2` | 皮肤2 | **猫的习性研究** |
| 维托里奥·库尼贝尔蒂 | `kunibeierdi_2_n` | 皮肤2·无背景版 | **猫的习性研究·无背景版** |
| 昆西 | `kunxi_2` | 皮肤2 | **炎夏凉风** |
| 昆西 | `kunxi_4` | 皮肤4 | **放学后的补习时间** |
| 昆西 | `kunxi_4_n` | 皮肤4·无背景版 | **放学后的补习时间·无背景版** |
| 拉德福特 | `ladefute_3` | 皮肤3 | **Candy Magic！** |
| 拉德福特 | `ladefute_3_n` | 皮肤3·无背景版 | **Candy Magic！·无背景版** |
| 拉菲 | `lafei_10` | 皮肤10 | **末日沉眠…** |
| 拉菲 | `lafei_10_hx` | 皮肤10·和谐版 | **末日沉眠…·和谐版** |
| 拉菲 | `lafei_10_n` | 皮肤10·无背景版 | **末日沉眠…·无背景版** |
| 拉菲 | `lafei_10_n_hx` | 皮肤10·无背景版·和谐版 | **末日沉眠…·和谐版·无背景版** |
| 拉菲 | `lafei_11` | 皮肤11 | **鸡肉卷，还有倦意…** |
| 拉菲 | `lafei_12` | 皮肤12 | **白日慵懒** |
| 拉菲 | `lafei_2` | 皮肤2 | **33娘** |
| 拉菲 | `lafei_3` | 皮肤3 | **雪兔与苹果糖** |
| 拉菲 | `lafei_4` | 皮肤4 | **白兔迎春** |
| 拉菲 | `lafei_5` | 皮肤5 | **兔兔店员？** |
| 拉菲 | `lafei_6` | 皮肤6 | **兔兔偶像·提不起劲** |
| 拉菲 | `lafei_8` | 皮肤8 | **野餐奇遇？** |
| 拉菲 | `lafei_9` | 皮肤9 | **大扫除的始末** |
| 拉菲 | `lafei_9_n` | 皮肤9·无背景版 | **大扫除的始末·无背景版** |
| 拉菲 | `lafei_g` | G | **拉菲.改** |
| 拉菲 | `lafei_h` | h | **白兔与誓约** |
| 拉斐尔 | `lafeier_2` | 皮肤2 | **爱与美的秘密珍藏** |
| 拉斐尔 | `lafeier_2_n` | 皮肤2·无背景版 | **爱与美的秘密珍藏·无背景版** |
| 拉斐尔 | `lafeier_3` | 皮肤3 | **共绘的魔术杰作** |
| 拉斐尔 | `lafeier_3_n` | 皮肤3·无背景版 | **共绘的魔术杰作·无背景版** |
| 拉菲II | `lafeiii_3` | 皮肤3 | **睡意满满忙碌DAY** |
| 拉菲II | `lafeiii_3_n` | 皮肤3·无背景版 | **睡意满满忙碌DAY·无背景版** |
| 拉菲II | `lafeiii_4` | 皮肤4 | **兔兔城主的巡游间隙** |
| 拉菲II | `lafeiii_4_n` | 皮肤4·无背景版 | **兔兔城主的巡游间隙·无背景版** |
| 拉菲II | `lafeiii_n` | 无背景版 | **拉菲II·无背景版** ⚠名字塌了(==船名) |
| 莱比锡 | `laibixi_2` | 皮肤2 | **前台接待·练习中** |
| 莱比锡 | `laibixi_2_n` | 皮肤2·无背景版 | **前台接待·练习中·无背景版** |
| 莱比锡 | `laibixi_g` | G | **莱比锡.改** |
| 莱姆号 | `laimuhao_2` | 皮肤2 | **魔蚀下的悸动** |
| 莱姆号 | `laimuhao_2_hx` | 皮肤2·和谐版 | **魔蚀下的悸动·和谐版** |
| 莱姆号 | `laimuhao_2_n` | 皮肤2·无背景版 | **魔蚀下的悸动·无背景版** |
| 莱姆号 | `laimuhao_2_n_hx` | 皮肤2·无背景版·和谐版 | **魔蚀下的悸动·和谐版·无背景版** |
| 莱莎琳·斯托特 | `laisha_2` | 皮肤2 | **熬夜的炼金术士** |
| 莱莎琳·斯托特 | `laisha_3` | 皮肤3 | **料理挑战！** |
| 莱莎琳·斯托特 | `laisha_3_n` | 皮肤3·无背景版 | **料理挑战！·无背景版** |
| 菈菈·撒塔琳·戴比路克 | `lala_2_tolove` | 皮肤2·tolove | **被束缚的王女殿下** |
| 菈菈·撒塔琳·戴比路克 | `lala_2_tolove_n` | 皮肤2·tolove·无背景版 | **被束缚的王女殿下·无背景版** |
| 兰利 | `lanli_g` | G | **兰利.改** |
| 兰利II | `lanliii_2` | 皮肤2 | **明媚休假进行时** |
| 兰利II | `lanliii_2_n` | 皮肤2·无背景版 | **明媚休假进行时·无背景版** |
| 蓝鳃鱼 | `lansaiyu_2` | 皮肤2 | **见习王牌守备！** |
| 蓝鳃鱼 | `lansaiyu_2_n` | 皮肤2·无背景版 | **见习王牌守备！·无背景版** |
| leftchicheng_alter | `leftchicheng_alter_n` | 无背景版 | **赤城·无背景版** |
| 雷 | `lei_2` | 皮肤2 | **樱花茶** |
| 雷 | `lei_3` | 皮肤3 | **祭典Ikatuchi** |
| 雷 | `lei_4` | 皮肤4 | **晨曦精灵Ikazuchi** |
| 雷 | `lei_4_n` | 皮肤4·无背景版 | **晨曦精灵Ikazuchi·无背景版** |
| 雷 | `lei_5` | 皮肤5 | **海天霞色之下** |
| 雷 | `lei_5_n` | 皮肤5·无背景版 | **海天霞色之下·无背景版** |
| 雷根斯堡 | `leigensibao_2` | 皮肤2 | **暗之龙，光之岸** |
| 雷根斯堡 | `leigensibao_2_n` | 皮肤2·无背景版 | **暗之龙，光之岸·无背景版** |
| 雷根斯堡 | `leigensibao_3` | 皮肤3 | **仓库中的暗之龙** |
| 雷根斯堡 | `leigensibao_3_n` | 皮肤3·无背景版 | **仓库中的暗之龙·无背景版** |
| 雷鸣 | `leiming_2` | 皮肤2 | **梦幻的阅读时光** |
| 雷鸣 | `leiming_2_n` | 皮肤2·无背景版 | **梦幻的阅读时光·无背景版** |
| 蕾妮雅 | `leiniya_2` | 皮肤2 | **夏日假期** |
| 蕾妮雅 | `leiniya_2_n` | 皮肤2·无背景版 | **夏日假期·无背景版** |
| 蕾妮雅 | `leiniya_wjz` | wjz | **蕾妮雅** ⚠名字塌了(==船名) |
| 勒马尔 | `lemaer_2` | 皮肤2 | **闪耀的夏天** |
| 勒马尔 | `lemaer_3` | 皮肤3 | **闪耀的幸福学园** |
| 勒马尔 | `lemaer_4` | 皮肤4 | **华丽的宴会登场** |
| 勒马尔 | `lemaer_4_n` | 皮肤4·无背景版 | **华丽的宴会登场·无背景版** |
| 勒马尔 | `lemaer_g` | G | **勒马尔.改** |
| 莲 | `lian_2` | 皮肤2 | **港区采访放送中！** |
| 莲 | `lian_2_n` | 皮肤2·无背景版 | **港区采访放送中！·无背景版** |
| 利安得 | `liande_g` | G | **利安得.改** |
| 里昂 | `liang_2` | 皮肤2 | **双人特训？** |
| 里昂 | `liang_2_n` | 皮肤2·无背景版 | **双人特训？·无背景版** |
| 凉波 | `liangbo_2` | 皮肤2 | **舞会前的着装准备** |
| 凉波 | `liangbo_2_n` | 皮肤2·无背景版 | **舞会前的着装准备·无背景版** |
| 凉月 | `liangyue_2` | 皮肤2 | **凉月、伴你在海边！** |
| 凉月 | `liangyue_2_n` | 皮肤2·无背景版 | **凉月、伴你在海边！·无背景版** |
| 凉月 | `liangyue_3` | 皮肤3 | **新年板羽球大战！** |
| 列克星敦 | `liekexingdun_2` | 皮肤2 | **春华佳人** |
| 列克星敦 | `liekexingdunii_2` | 皮肤2 | **轻飘飘的拂拭时光** |
| 列克星敦 | `liekexingdunii_2_n` | 皮肤2·无背景版 | **轻飘飘的拂拭时光·无背景版** |
| 列克星敦 | `liekexingdunii_n` | 无背景版 | **列克星敦II·无背景版** |
| 莉拉·德西亚斯 | `lila_2` | 皮肤2 | **月下的邂逅** |
| 绫波 | `lingbo_10` | 皮肤10 | **黯然礼装** |
| 绫波 | `lingbo_10_n` | 皮肤10·无背景版 | **黯然礼装·无背景版** |
| 绫波 | `lingbo_11` | 皮肤11 | **微速战斗姿势** |
| 绫波 | `lingbo_11_n` | 皮肤11·无背景版 | **微速战斗姿势·无背景版** |
| 绫波 | `lingbo_13` | 皮肤13 | **苍墨武鉴** |
| 绫波 | `lingbo_13_n` | 皮肤13·无背景版 | **苍墨武鉴·无背景版** |
| 绫波 | `lingbo_14` | 皮肤14 | **可乐，加上努力？** |
| 绫波 | `lingbo_15` | 皮肤15 | **跃动飞踢！** |
| 绫波 | `lingbo_15_hx` | 皮肤15·和谐版 | **跃动飞踢！·和谐版** |
| 绫波 | `lingbo_16` | 皮肤16 | **深蓝邀约** |
| 绫波 | `lingbo_16_n` | 皮肤16·无背景版 | **深蓝邀约·无背景版** |
| 绫波 | `lingbo_2` | 皮肤2 | **待宵的魔女** |
| 绫波 | `lingbo_4` | 皮肤4 | **乐队型鬼神** |
| 绫波 | `lingbo_5` | 皮肤5 | **新岁之鬼神** |
| 绫波 | `lingbo_6` | 皮肤6 | **一式水手风制服** |
| 绫波 | `lingbo_7` | 皮肤7 | **冷静偶像·迷惑中** |
| 绫波 | `lingbo_8` | 皮肤8 | **新年的愿望** |
| 绫波 | `lingbo_9` | 皮肤9 | **特殊潜入作战披风** |
| 绫波 | `lingbo_9_n` | 皮肤9·无背景版 | **特殊潜入作战披风·无背景版** |
| 绫波 | `lingbo_g` | G | **绫波.改** |
| 绫波 | `lingbo_h` | h | **鬼神之华裳** |
| 铃谷 | `linggu_3` | 皮肤3 | **Midnight Care** |
| 铃谷 | `linggu_3_n` | 皮肤3·无背景版 | **Midnight Care·无背景版** |
| 领航员-TB | `linghangyuan1_1` | 皮肤1 | **TB** |
| 领航员-TB | `linghangyuan1_5` | 皮肤5 | **超级AI-TC** |
| 领航员-TB | `linghangyuan3_2` | 皮肤2 | **数据集：无数的我** |
| 领航员-TB | `linghangyuan3_2_n` | 皮肤2·无背景版 | **数据集：无数的我·无背景版** |
| 绫濑 | `linglai_2` | 皮肤2 | **兔子小姐的更衣时间** |
| 绫濑 | `linglai_2_n` | 皮肤2·无背景版 | **兔子小姐的更衣时间·无背景版** |
| 灵敏 | `lingmin_2` | 皮肤2 | **天才生物机械师？** |
| 灵敏 | `lingmin_2_n` | 皮肤2·无背景版 | **天才生物机械师？·无背景版** |
| 灵敏 | `lingmin_alter` | alter | **灵敏** ⚠名字塌了(==船名) |
| 领洋者-娜比娅 | `lingyangzhe3_2` | 皮肤2 | **入浴的小恶魔** |
| 领洋者-娜比娅 | `lingyangzhe3_2_n` | 皮肤2·无背景版 | **入浴的小恶魔·无背景版** |
| 里诺 | `linuo_2` | 皮肤2 | **波涛的啦啦队长！** |
| 里诺 | `linuo_2_n` | 皮肤2·无背景版 | **波涛的啦啦队长！·无背景版** |
| 里诺 | `linuo_3` | 皮肤3 | **bunny·reno！** |
| 里诺 | `linuo_3_hx` | 皮肤3·和谐版 | **bunny·reno！·和谐版** |
| 里诺 | `linuo_3_n` | 皮肤3·无背景版 | **bunny·reno！·无背景版** |
| 里诺 | `linuo_3_n_hx` | 皮肤3·无背景版·和谐版 | **bunny·reno！·和谐版·无背景版** |
| 里诺 | `linuo_4` | 皮肤4 | **夏日番外篇** |
| 里诺 | `linuo_4_n` | 皮肤4·无背景版 | **夏日番外篇·无背景版** |
| 里诺 | `linuo_5` | 皮肤5 | **闪耀东煌之春** |
| 里诺 | `linuo_5_n` | 皮肤5·无背景版 | **闪耀东煌之春·无背景版** |
| 黎塞留 | `lisailiu_2` | 皮肤2 | **潮风的Fleuron** |
| 黎塞留 | `lisailiu_2_n` | 皮肤2·无背景版 | **潮风的Fleuron·无背景版** |
| 黎塞留 | `lisailiu_3` | 皮肤3 | **常緑Rêve prophétique** |
| 黎塞留 | `lisailiu_3_n` | 皮肤3·无背景版 | **常緑Rêve prophétique·无背景版** |
| 黎塞留 | `lisailiu_memory` | memory | **黎塞留** ⚠名字塌了(==船名) |
| 利托里奥 | `lituoliao_2` | 皮肤2 | **那不勒斯之光** |
| 利托里奥 | `lituoliao_2_n` | 皮肤2·无背景版 | **那不勒斯之光·无背景版** |
| 利托里奥 | `lituoliao_3` | 皮肤3 | **Calabria Aurea** |
| 利托里奥 | `lituoliao_3_hx` | 皮肤3·和谐版 | **Calabria Aurea·和谐版** |
| 利托里奥 | `lituoliao_4` | 皮肤4 | **居家私人时间** |
| 利托里奥 | `lituoliao_4_hx` | 皮肤4·和谐版 | **居家私人时间·和谐版** |
| 利托里奥 | `lituoliao_4_n` | 皮肤4·无背景版 | **居家私人时间·无背景版** |
| 利托里奥 | `lituoliao_4_n_hx` | 皮肤4·无背景版·和谐版 | **居家私人时间·和谐版·无背景版** |
| 利托里奥 | `lituoliao_5` | 皮肤5 | **雨中的等候** |
| 利托里奥 | `lituoliao_5_n` | 皮肤5·无背景版 | **雨中的等候·无背景版** |
| 琉·璃昂 | `liuliang_2` | 皮肤2 | **在夜晚的酒馆中** |
| 琉·璃昂 | `liuliang_2_n` | 皮肤2·无背景版 | **在夜晚的酒馆中·无背景版** |
| 琉·璃昂 | `liuliang_wjz` | wjz | **琉·璃昂** ⚠名字塌了(==船名) |
| 利物浦 | `liwupu_2` | 皮肤2 | **绮丽的祝福之风** |
| 利物浦 | `liwupu_2_n` | 皮肤2·无背景版 | **绮丽的祝福之风·无背景版** |
| 龙凤 | `longfeng_2` | 皮肤2 | **凤舞新年** |
| 龙凤 | `longfeng_2_hx` | 皮肤2·和谐版 | **凤舞新年·和谐版** |
| 龙骑兵 | `longqibing_2` | 皮肤2 | **清爽的夏日Choice** |
| 龙武 | `longwu_2` | 皮肤2 | **腾龙新春宴** |
| 龙武 | `longwu_2_n` | 皮肤2·无背景版 | **腾龙新春宴·无背景版** |
| 龙武 | `longwu_3` | 皮肤3 | **悠然碧海行** |
| 龙武 | `longwu_3_n` | 皮肤3·无背景版 | **悠然碧海行·无背景版** |
| 龙骧 | `longxiang_2` | 皮肤2 | **干物武士？** |
| 龙骧 | `longxiang_3` | 皮肤3 | **课后狩猎时间** |
| 龙骧 | `longxiang_4` | 皮肤4 | **降龙滑梯——！** |
| 龙骧 | `longxiang_4_n` | 皮肤4·无背景版 | **降龙滑梯——！·无背景版** |
| 陆奥 | `luao_2` | 皮肤2 | **战国风云少女** |
| 陆奥 | `luao_3` | 皮肤3 | **错误女仆范本？** |
| 陆奥 | `luao_3_n` | 皮肤3·无背景版 | **错误女仆范本？·无背景版** |
| 露露缇耶 | `lulutiye_2` | 皮肤2 | **露露缇耶(传颂之物)** |
| 鲁莽 | `lumang_2` | 皮肤2 | **盛夏Festival！** |
| 鲁莽 | `lumang_3` | 皮肤3 | **Dream.Dolce** |
| 鲁莽 | `lumang_3_n` | 皮肤3·无背景版 | **Dream.Dolce·无背景版** |
| 鲁莽 | `lumang_4` | 皮肤4 | **跃动的步伐** |
| 鲁莽 | `lumang_4_n` | 皮肤4·无背景版 | **跃动的步伐·无背景版** |
| 鲁莽 | `lumang_idol` | idol | **鲁莽(μ兵装)** |
| 鲁莽 | `lumang_idol_n` | idol·无背景版 | **鲁莽(μ兵装)·无背景版** |
| 露娜 | `luna_2_doa` | 皮肤2·doa | **沙滩上的女神** |
| 露娜 | `luna_2_doa_n` | 皮肤2·doa·无背景版 | **沙滩上的女神·无背景版** |
| 露娜 | `luna_doa` | doa | **露娜** ⚠名字塌了(==船名) |
| 伦敦 | `lundun_3` | 皮肤3 | **高效工作时间** |
| 伦敦 | `lundun_3_n` | 皮肤3·无背景版 | **高效工作时间·无背景版** |
| 伦敦 | `lundun_g` | G | **伦敦.改** |
| 伦敦 | `lundun_h` | h | **铂金之仪** |
| 罗德尼 | `luodeni_2` | 皮肤2 | **未来的海滨上将** |
| 罗德尼 | `luodeni_3` | 皮肤3 | **一日见习店员** |
| 罗德尼 | `luodeni_4` | 皮肤4 | **完美佳人** |
| 罗德尼 | `luodeni_h` | h | **幸福殿堂** |
| 罗德尼 | `luodeni_h_n` | h·无背景版 | **幸福殿堂·无背景版** |
| 罗恩 | `luoen_2` | 皮肤2 | **暗红色的微笑** |
| 罗恩 | `luoen_3` | 皮肤3 | **罗恩** ⚠名字塌了(==船名) |
| 罗恩 | `luoen_4` | 皮肤4 | **苍翠的安眠曲** |
| 罗恩 | `luoen_4_n` | 皮肤4·无背景版 | **苍翠的安眠曲·无背景版** |
| 罗恩 | `luoen_5` | 皮肤5 | **暗夜的悸动** |
| 罗恩 | `luoen_5_n` | 皮肤5·无背景版 | **暗夜的悸动·无背景版** |
| 罗恩 | `luoen_h` | h | **拥抱深渊** |
| 罗恩 | `luoen_h_n` | h·无背景版 | **拥抱深渊·无背景版** |
| 罗恩 | `luoen_idol` | idol | **罗恩(μ兵装)** |
| 罗恩 | `luoen_idol_n` | idol·无背景版 | **罗恩(μ兵装)·无背景版** |
| 罗马 | `luoma_2` | 皮肤2 | **午夜的白天鹅** |
| 罗马 | `luoma_2_n` | 皮肤2·无背景版 | **午夜的白天鹅·无背景版** |
| 罗马 | `luoma_4` | 皮肤4 | **罗马的假日** |
| 罗马 | `luoma_4_n` | 皮肤4·无背景版 | **罗马的假日·无背景版** |
| 罗马 | `luoma_ghost` | ghost | **罗马** ⚠名字塌了(==船名) |
| 鲁普雷希特亲王 | `lupuleixite_2` | 皮肤2 | **腾龙戏春？** |
| 鲁普雷希特亲王 | `lupuleixite_2_n` | 皮肤2·无背景版 | **腾龙戏春？·无背景版** |
| 鲁普雷希特亲王 | `lupuleixite_3` | 皮肤3 | **Midnight Pearl** |
| 鲁普雷希特亲王 | `lupuleixite_3_n` | 皮肤3·无背景版 | **Midnight Pearl·无背景版** |
| 路易九世 | `luyijiushi_2` | 皮肤2 | **华服的圣骑士** |
| 路易九世 | `luyijiushi_3` | 皮肤3 | **瑰丽的执勤人** |
| 路易九世 | `luyijiushi_3_n` | 皮肤3·无背景版 | **瑰丽的执勤人·无背景版** |
| 路易九世 | `luyijiushi_4` | 皮肤4 | **微醺的静谧时光** |
| 路易九世 | `luyijiushi_4_n` | 皮肤4·无背景版 | **微醺的静谧时光·无背景版** |
| 路易斯维尔 | `luyisiweier_2` | 皮肤2 | **梦幻推荐** |
| 路易斯维尔 | `luyisiweier_2_n` | 皮肤2·无背景版 | **梦幻推荐·无背景版** |
| 秋月律子 | `lvzi_2` | 皮肤2 | **盛夏时光·乒乓对决** |
| 秋月律子 | `lvzi_2_n` | 皮肤2·无背景版 | **盛夏时光·乒乓对决·无背景版** |
| 吕佐夫 | `lvzuofu_2` | 皮肤2 | **永夜的赤之贵族** |
| 吕佐夫 | `lvzuofu_2_n` | 皮肤2·无背景版 | **永夜的赤之贵族·无背景版** |
| 吕佐夫 | `lvzuofu_3` | 皮肤3 | **请趁热享用♪** |
| 吕佐夫 | `lvzuofu_3_n` | 皮肤3·无背景版 | **请趁热享用♪·无背景版** |
| 吕佐夫 | `lvzuofu_h` | h | **纯白的睡美人** |
| 吕佐夫 | `lvzuofu_h_n` | h·无背景版 | **纯白的睡美人·无背景版** |
| 马布尔黑德 | `mabuerheide_2` | 皮肤2 | **Boxing Girl！** |
| 马布尔黑德 | `mabuerheide_3` | 皮肤3 | **魅惑的缤纷雪夜** |
| 马布尔黑德 | `mabuerheide_4` | 皮肤4 | **29.5日的赏月时间** |
| 马布尔黑德 | `mabuerheide_4_n` | 皮肤4·无背景版 | **29.5日的赏月时间·无背景版** |
| 马布尔黑德 | `mabuerheide_5` | 皮肤5 | **雨天的非偶然相遇?** |
| 马布尔黑德 | `mabuerheide_5_n` | 皮肤5·无背景版 | **雨天的非偶然相遇?·无背景版** |
| 马格德堡 | `magedebao_2` | 皮肤2 | **艳阳闪耀的假日** |
| 马格德堡 | `magedebao_2_n` | 皮肤2·无背景版 | **艳阳闪耀的假日·无背景版** |
| 马格德堡 | `magedebao_3` | 皮肤3 | **扫除？喵喵骚乱！** |
| 马格德堡 | `magedebao_3_n` | 皮肤3·无背景版 | **扫除？喵喵骚乱！·无背景版** |
| 马可波罗 | `makeboluo_2` | 皮肤2 | **Lovely Million** |
| 马可波罗 | `makeboluo_2_hx` | 皮肤2·和谐版 | **Lovely Million·和谐版** |
| 马可波罗 | `makeboluo_2_n` | 皮肤2·无背景版 | **Lovely Million·无背景版** |
| 马可波罗 | `makeboluo_2_n_hx` | 皮肤2·无背景版·和谐版 | **Lovely Million·和谐版·无背景版** |
| 马可波罗 | `makeboluo_3` | 皮肤3 | **好戏开幕！惊奇Show** |
| 马可波罗 | `makeboluo_3_n` | 皮肤3·无背景版 | **好戏开幕！惊奇Show·无背景版** |
| 马拉尼 | `malani_3` | 皮肤3 | **东煌之仪** |
| 玛丽·西莱斯特号 | `mali_2` | 皮肤2 | **幽夜冥神** |
| 玛丽·西莱斯特号 | `mali_2_n` | 皮肤2·无背景版 | **幽夜冥神·无背景版** |
| 马里兰 | `malilan_2` | 皮肤2 | **马里兰** ⚠名字塌了(==船名) |
| 马里兰 | `malilan_3` | 皮肤3 | **真红鼓手** |
| 马里兰 | `malilan_3_n` | 皮肤3·无背景版 | **真红鼓手·无背景版** |
| 马里兰 | `malilan_g` | G | **马里兰.改** |
| 马里兰 | `malilan_g_n` | G·无背景版 | **马里兰.改·无背景版** |
| 玛莉萝丝 | `maliluosi_2_doa` | 皮肤2·doa | **浪花与小恶魔从者** |
| 玛莉萝丝 | `maliluosi_2_doa_n` | 皮肤2·doa·无背景版 | **浪花与小恶魔从者·无背景版** |
| 玛莉萝丝 | `maliluosi_3_doa` | 皮肤3·doa | **热气蒸腾的女神** |
| 玛莉萝丝 | `maliluosi_doa` | doa | **玛莉萝丝** ⚠名字塌了(==船名) |
| 玛莉萝丝 | `maliluosi_doa_wjz` | doa·wjz | **玛莉萝丝** ⚠名字塌了(==船名) |
| 满潮 | `manchao_2` | 皮肤2 | **缎带轻飘飘** |
| 满潮 | `manchao_2_n` | 皮肤2·无背景版 | **缎带轻飘飘·无背景版** |
| 曼彻斯特 | `manchesite_2` | 皮肤2 | **海边的片刻宁静** |
| 曼彻斯特 | `manchesite_2_n` | 皮肤2·无背景版 | **海边的片刻宁静·无背景版** |
| 曼彻斯特 | `manchesite_3` | 皮肤3 | **白衣“恶魔”的狂欢夜** |
| 曼彻斯特 | `manchesite_3_n` | 皮肤3·无背景版 | **白衣“恶魔”的狂欢夜·无背景版** |
| 冒险号 | `maoxianhao_2` | 皮肤2 | **多疑领主的晚宴** |
| 冒险号 | `maoxianhao_2_n` | 皮肤2·无背景版 | **多疑领主的晚宴·无背景版** |
| 猫音 | `maoyin_2` | 皮肤2 | **猫音(传颂之物)** |
| 卯月 | `maoyue_2` | 皮肤2 | **贪睡的天使** |
| 马塞纳 | `masaina_2` | 皮肤2 | **醉甜之泉** |
| 马塞纳 | `masaina_2_hx` | 皮肤2·和谐版 | **醉甜之泉·和谐版** |
| 马塞纳 | `masaina_2_n` | 皮肤2·无背景版 | **醉甜之泉·无背景版** |
| 马塞纳 | `masaina_2_n_hx` | 皮肤2·无背景版·和谐版 | **醉甜之泉·和谐版·无背景版** |
| 马赛曲 | `masaiqu_2` | 皮肤2 | **战斗天使的健身训练** |
| 马赛曲 | `masaiqu_2_n` | 皮肤2·无背景版 | **战斗天使的健身训练·无背景版** |
| 马萨诸塞 | `masazhusai_2` | 皮肤2 | **盛宴的准备** |
| 马耶·布雷泽 | `mayebuleize_2` | 皮肤2 | **糖分小憩** |
| 马耶·布雷泽 | `mayebuleize_2_n` | 皮肤2·无背景版 | **糖分小憩·无背景版** |
| 马耶·布雷泽 | `mayebuleize_3` | 皮肤3 | **女骑士的最后倔强！** |
| 马耶·布雷泽 | `mayebuleize_3_n` | 皮肤3·无背景版 | **女骑士的最后倔强！·无背景版** |
| 梅克伦堡 | `meikelunbao_2` | 皮肤2 | **作茧自缚** |
| 梅克伦堡 | `meikelunbao_2_hx` | 皮肤2·和谐版 | **作茧自缚·和谐版** |
| 梅克伦堡 | `meikelunbao_2_n` | 皮肤2·无背景版 | **作茧自缚·无背景版** |
| 梅克伦堡 | `meikelunbao_2_n_hx` | 皮肤2·无背景版·和谐版 | **作茧自缚·和谐版·无背景版** |
| 美因茨 | `meiyinci_2` | 皮肤2 | **薄雾轻纱** |
| 美因茨 | `meiyinci_2_n` | 皮肤2·无背景版 | **薄雾轻纱·无背景版** |
| 美因茨 | `meiyinci_3` | 皮肤3 | **静雅之所的安逸** |
| 美因茨 | `meiyinci_3_n` | 皮肤3·无背景版 | **静雅之所的安逸·无背景版** |
| 蒙彼利埃 | `mengbiliai_2` | 皮肤2 | **雪夜之花** |
| 蒙彼利埃 | `mengbiliai_3` | 皮肤3 | **魔境的公主？** |
| 蒙彼利埃 | `mengbiliai_3_n` | 皮肤3·无背景版 | **魔境的公主？·无背景版** |
| 蒙彼利埃 | `mengbiliai_4` | 皮肤4 | **微醺时的降温措施** |
| 蒙彼利埃 | `mengbiliai_4_n` | 皮肤4·无背景版 | **微醺时的降温措施·无背景版** |
| 孟菲斯 | `mengfeisi_2` | 皮肤2 | **海风之旅** |
| 孟菲斯 | `mengfeisi_3` | 皮肤3 | **Mystical Night** |
| 孟菲斯 | `mengfeisi_3_hx` | 皮肤3·和谐版 | **Mystical Night·和谐版** |
| 孟菲斯 | `mengfeisi_4` | 皮肤4 | **课间的微风** |
| 孟菲斯 | `mengfeisi_4_n` | 皮肤4·无背景版 | **课间的微风·无背景版** |
| 孟菲斯 | `mengfeisi_alter` | alter | **孟菲斯·META** |
| 梦梦·贝莉雅·戴比路克 | `mengmeng_2_tolove` | 皮肤2·tolove | **“梦”醒时分** |
| 梦梦·贝莉雅·戴比路克 | `mengmeng_2_tolove_n` | 皮肤2·tolove·无背景版 | **“梦”醒时分·无背景版** |
| 南梦芽 | `mengya_2` | 皮肤2 | **窗沿的美梦** |
| 南梦芽 | `mengya_3` | 皮肤3 | **晨间日常** |
| 南梦芽 | `mengya_3_n` | 皮肤3·无背景版 | **晨间日常·无背景版** |
| 妙风 | `miaofeng_2` | 皮肤2 | **忍者的紧急迫降修行！** |
| 妙风 | `miaofeng_2_n` | 皮肤2·无背景版 | **忍者的紧急迫降修行！·无背景版** |
| midchicheng_alter | `midchicheng_alter_n` | 无背景版 | **赤城·无背景版** |
| 米勒 | `mile_2` | 皮肤2 | **叛逆试验体M01** |
| 米勒 | `mile_2_n` | 皮肤2·无背景版 | **叛逆试验体M01·无背景版** |
| 米勒 | `mile_3` | 皮肤3 | **幽幽桥上，坏坏来袭！** |
| 米勒 | `mile_3_n` | 皮肤3·无背景版 | **幽幽桥上，坏坏来袭！·无背景版** |
| 名寄 | `mingji_2` | 皮肤2 | **Electric Affection** |
| 名寄 | `mingji_2_n` | 皮肤2·无背景版 | **Electric Affection·无背景版** |
| 明尼阿波利斯 | `mingniabolisi_2` | 皮肤2 | **野性派学生** |
| 明尼阿波利斯 | `mingniabolisi_3` | 皮肤3 | **极限运动X** |
| 明尼阿波利斯 | `mingniabolisi_3_n` | 皮肤3·无背景版 | **极限运动X·无背景版** |
| 明尼阿波利斯 | `mingniabolisi_4` | 皮肤4 | **圣夜的月下疾驰** |
| 明尼阿波利斯 | `mingniabolisi_4_n` | 皮肤4·无背景版 | **圣夜的月下疾驰·无背景版** |
| 明尼阿波利斯 | `mingniabolisi_h` | h | **Trapper white** |
| 明尼阿波利斯 | `mingniabolisi_h_hx` | h·和谐版 | **Trapper white·和谐版** |
| 名取 | `mingqu_2` | 皮肤2 | **沙滩乐园** |
| 名取 | `mingqu_2_n` | 皮肤2·无背景版 | **沙滩乐园·无背景版** |
| 名取 | `mingqu_3` | 皮肤3 | **喧闹之夜** |
| 名取 | `mingqu_3_n` | 皮肤3·无背景版 | **喧闹之夜·无背景版** |
| 明石 | `mingshi_2` | 皮肤2 | **正月，浴衣，赤字** |
| 明石 | `mingshi_3` | 皮肤3 | **黑猫来袭！** |
| 明石 | `mingshi_4` | 皮肤4 | **明石_在A1摊位喵！** |
| 明石 | `mingshi_5` | 皮肤5 | **欢迎光临Sofmap！** |
| 明石 | `mingshi_h` | h | **白猫的报恩** |
| 明斯克 | `mingsike_2` | 皮肤2 | **霹雳典狱长** |
| 命运女神 | `mingyunnvshen_2` | 皮肤2 | **晴空下的命运丝线** |
| 命运女神 | `mingyunnvshen_2_n` | 皮肤2·无背景版 | **晴空下的命运丝线·无背景版** |
| 命运女神 | `mingyunnvshen_g` | G | **命运女神.改** |
| 摩尔曼斯克 | `moermansike_2` | 皮肤2 | **纯白雪景** |
| 摩尔曼斯克 | `moermansike_2_n` | 皮肤2·无背景版 | **纯白雪景·无背景版** |
| 摩尔曼斯克 | `moermansike_3` | 皮肤3 | **一室幽香** |
| 摩尔曼斯克 | `moermansike_3_n` | 皮肤3·无背景版 | **一室幽香·无背景版** |
| 莫加多尔 | `mojiaduoer_2` | 皮肤2 | **静谧一隅的燥热** |
| 莫加多尔 | `mojiaduoer_2_hx` | 皮肤2·和谐版 | **静谧一隅的燥热·和谐版** |
| 莫加多尔 | `mojiaduoer_2_n` | 皮肤2·无背景版 | **静谧一隅的燥热·无背景版** |
| 莫加多尔 | `mojiaduoer_2_n_hx` | 皮肤2·无背景版·和谐版 | **静谧一隅的燥热·和谐版·无背景版** |
| 莫加多尔 | `mojiaduoer_3` | 皮肤3 | **嗅诊的护理天使** |
| 莫加多尔 | `mojiaduoer_3_n` | 皮肤3·无背景版 | **嗅诊的护理天使·无背景版** |
| 莫加多尔 | `mojiaduoer_4` | 皮肤4 | **共坠的渴慕** |
| 莫加多尔 | `mojiaduoer_4_hx` | 皮肤4·和谐版 | **共坠的渴慕·和谐版** |
| 莫加多尔 | `mojiaduoer_4_n` | 皮肤4·无背景版 | **共坠的渴慕·无背景版** |
| 莫加多尔 | `mojiaduoer_4_n_hx` | 皮肤4·无背景版·和谐版 | **共坠的渴慕·和谐版·无背景版** |
| 莫加多尔 | `mojiaduoer_5` | 皮肤5 | **共坠的渴慕** |
| 莫里 | `moli_g` | G | **莫里.改** |
| 莫里 | `moli_g_n` | G·无背景版 | **莫里.改·无背景版** |
| 莫里茨亲王 | `molici_2` | 皮肤2 | **神灯小姐的愿望游戏** |
| 莫里茨亲王 | `molici_2_n` | 皮肤2·无背景版 | **神灯小姐的愿望游戏·无背景版** |
| 莫里森 | `molisen_2` | 皮肤2 | **小熊整备中** |
| 莫里森 | `molisen_2_n` | 皮肤2·无背景版 | **小熊整备中·无背景版** |
| 莫里森 | `molisen_3` | 皮肤3 | **科技？忍术？** |
| 莫里森 | `molisen_3_n` | 皮肤3·无背景版 | **科技？忍术？·无背景版** |
| 莫妮卡 | `monika_2_doa` | 皮肤2·doa | **特别的红心Ace** |
| 莫妮卡 | `monika_doa` | doa | **莫妮卡** ⚠名字塌了(==船名) |
| 莫妮卡 | `monika_doa_wjz` | doa·wjz | **莫妮卡** ⚠名字塌了(==船名) |
| 莫斯科 | `mosike_2` | 皮肤2 | **待君落子之时** |
| 莫斯科 | `mosike_2_n` | 皮肤2·无背景版 | **待君落子之时·无背景版** |
| 摩耶 | `moye_2` | 皮肤2 | **凛然的猎心杀手** |
| 摩耶 | `moye_2_n` | 皮肤2·无背景版 | **凛然的猎心杀手·无背景版** |
| 木津 | `mujin_2` | 皮肤2 | **“落网”之龙** |
| 木津 | `mujin_2_hx` | 皮肤2·和谐版 | **“落网”之龙·和谐版** |
| 木津 | `mujin_2_n` | 皮肤2·无背景版 | **“落网”之龙·无背景版** |
| 木津 | `mujin_2_n_hx` | 皮肤2·无背景版·和谐版 | **“落网”之龙·和谐版·无背景版** |
| 睦月 | `muyue_2` | 皮肤2 | **驯鹿先生，出发！** |
| 睦月 | `muyue_3` | 皮肤3 | **糖果祭典！** |
| 睦月 | `muyue_4` | 皮肤4 | **春节的糖果** |
| 睦月 | `muyue_5` | 皮肤5 | **乐园、回忆与棉花糖** |
| 睦月 | `muyue_5_n` | 皮肤5·无背景版 | **乐园、回忆与棉花糖·无背景版** |
| 睦月 | `muyue_g` | G | **睦月.改** |
| 雫 | `na_2_doa_n` | 无背景版 | **于潮间嬉戏的少女·无背景版** |
| 那不勒斯 | `nabulesi_2` | 皮肤2 | **Dreamy Night** |
| 那不勒斯 | `nabulesi_2_hx` | 皮肤2·和谐版 | **Dreamy Night·和谐版** |
| 那不勒斯 | `nabulesi_2_n` | 皮肤2·无背景版 | **Dreamy Night·无背景版** |
| 那不勒斯 | `nabulesi_2_n_hx` | 皮肤2·无背景版·和谐版 | **Dreamy Night·和谐版·无背景版** |
| 纳尔逊 | `naerxun_2` | 皮肤2 | **月之魔女** |
| 纳尔逊 | `naerxun_3` | 皮肤3 | **蓝金的夏夜之光** |
| 纳尔逊 | `naerxun_3_n` | 皮肤3·无背景版 | **蓝金的夏夜之光·无背景版** |
| 纳尔逊 | `naerxun_g` | G | **纳尔逊.改** |
| 纳尔逊 | `naerxun_g_n` | G·无背景版 | **纳尔逊.改·无背景版** |
| 奈美子 | `naimeizi_2` | 皮肤2 | **街头的相遇** |
| 奈美子 | `naimeizi_2_n` | 皮肤2·无背景版 | **街头的相遇·无背景版** |
| 那珂 | `nake_2` | 皮肤2 | **激浪之夏！** |
| 娜娜·阿丝达·戴比路克 | `nana_2_tolove` | 皮肤2·tolove | **游戏时刻** |
| 娜娜·阿丝达·戴比路克 | `nana_2_tolove_n` | 皮肤2·tolove·无背景版 | **游戏时刻·无背景版** |
| 南安普顿 | `nananpudun_2` | 皮肤2 | **新年的LittleKnight** |
| 南安普顿 | `nananpudun_3` | 皮肤3 | **午后的休闲旋律** |
| 南安普顿 | `nananpudun_3_n` | 皮肤3·无背景版 | **午后的休闲旋律·无背景版** |
| 南安普顿 | `nananpudun_h` | h | **璀璨的启程** |
| 南达科他 | `nandaketa_2` | 皮肤2 | **剧场上的独奏** |
| 纳希莫夫海军上将 | `naximofu_2` | 皮肤2 | **聚光灯下的初体验** |
| 纳希莫夫海军上将 | `naximofu_2_hx` | 皮肤2·和谐版 | **聚光灯下的初体验·和谐版** |
| 纳希莫夫海军上将 | `naximofu_2_n` | 皮肤2·无背景版 | **聚光灯下的初体验·无背景版** |
| 纳希莫夫海军上将 | `naximofu_2_n_hx` | 皮肤2·无背景版·和谐版 | **聚光灯下的初体验·和谐版·无背景版** |
| 纳希莫夫海军上将 | `naximofu_3` | 皮肤3 | **新启之日** |
| 纳希莫夫海军上将 | `naximofu_3_n` | 皮肤3·无背景版 | **新启之日·无背景版** |
| 纳希莫夫海军上将 | `naximofu_4` | 皮肤4 | **机械师的满分应援** |
| 纳希莫夫海军上将 | `naximofu_4_n` | 皮肤4·无背景版 | **机械师的满分应援·无背景版** |
| 那智 | `nazhi_g` | G | **那智.改** |
| 那智 | `nazhi_g_n` | G·无背景版 | **那智.改·无背景版** |
| 内华达 | `neihuada_2` | 皮肤2 | **华贵的盛宴** |
| 内华达 | `neihuada_g` | G | **内华达.改** |
| 能代 | `nengdai_2` | 皮肤2 | **祭典的秘境?** |
| 能代 | `nengdai_3` | 皮肤3 | **阳光·沙滩·假日** |
| 能代 | `nengdai_3_n` | 皮肤3·无背景版 | **阳光·沙滩·假日·无背景版** |
| 能代 | `nengdai_4` | 皮肤4 | **夜响的绝园** |
| 能代 | `nengdai_4_n` | 皮肤4·无背景版 | **夜响的绝园·无背景版** |
| 能代 | `nengdai_5` | 皮肤5 | **宁静的六叠间** |
| 能代 | `nengdai_5_n` | 皮肤5·无背景版 | **宁静的六叠间·无背景版** |
| 能代 | `nengdai_6` | 皮肤6 | **冬雪沁香** |
| 能代 | `nengdai_6_n` | 皮肤6·无背景版 | **冬雪沁香·无背景版** |
| 能代 | `nengdai_7` | 皮肤7 | **需要少冰吗？** |
| 能代 | `nengdai_7_n` | 皮肤7·无背景版 | **需要少冰吗？·无背景版** |
| 能代 | `nengdai_8` | 皮肤8 | **香奢之约** |
| 能代 | `nengdai_8_n` | 皮肤8·无背景版 | **香奢之约·无背景版** |
| 能代 | `nengdai_9` | 皮肤9 | **月夜花泉** |
| 能代 | `nengdai_h` | h | **恋结奇谭** |
| 能代 | `nengdai_idol` | idol | **能代(μ兵装)** |
| 能代 | `nengdai_idol_n` | idol·无背景版 | **能代(μ兵装)·无背景版** |
| 鸟海 | `niaohai_2` | 皮肤2 | **清心风景** |
| 鸟海 | `niaohai_2_n` | 皮肤2·无背景版 | **清心风景·无背景版** |
| 鸟海 | `niaohai_3` | 皮肤3 | **偷心怪盗** |
| 鸟海 | `niaohai_3_n` | 皮肤3·无背景版 | **偷心怪盗·无背景版** |
| 尼古拉斯 | `nigulasi_2` | 皮肤2 | **尼古纳斯** |
| 尼古拉斯 | `nigulasi_3` | 皮肤3 | **装错的圣诞礼物** |
| 尼古拉斯 | `nigulasi_4` | 皮肤4 | **夏日清扫运动** |
| 尼古拉斯 | `nigulasi_5` | 皮肤5 | **放学后的“惊喜”？** |
| 尼古拉斯 | `nigulasi_5_n` | 皮肤5·无背景版 | **放学后的“惊喜”？·无背景版** |
| 尼古拉斯 | `nigulasi_g` | G | **尼古拉斯.改** |
| 妮娜·弗里德 | `nina_2` | 皮肤2 | **Cafe & Diner mode** |
| 妮娜·弗里德 | `nina_2_n` | 皮肤2·无背景版 | **Cafe & Diner mode·无背景版** |
| 妮娜·弗里德 | `nina_wjz` | wjz | **妮娜·弗里德** ⚠名字塌了(==船名) |
| 宁海 | `ninghai_2` | 皮肤2 | **食欲之夏** |
| 宁海 | `ninghai_3` | 皮肤3 | **月宫玉兔** |
| 宁海 | `ninghai_4` | 皮肤4 | **东煌姐妹！·N** |
| 宁海 | `ninghai_5` | 皮肤5 | **新年旅游！** |
| 宁海 | `ninghai_6` | 皮肤6 | **姹紫盛筵** |
| 宁海 | `ninghai_7` | 皮肤7 | **大宝的伙伴！** |
| 宁海 | `ninghai_8` | 皮肤8 | **慌乱的新春厨房** |
| 宁海 | `ninghai_8_n` | 皮肤8·无背景版 | **慌乱的新春厨房·无背景版** |
| 宁海 | `ninghai_g` | G | **宁海.改** |
| 宁海 | `ninghai_memory` | memory | **宁海** ⚠名字塌了(==船名) |
| 纽卡斯尔 | `niukasier_2` | 皮肤2 | **木槿风情** |
| 纽卡斯尔 | `niukasier_g` | G | **纽卡斯尔.改 ** |
| 纽伦堡 | `niulunbao_2` | 皮肤2 | **正月的漫游** |
| 纽伦堡 | `niulunbao_2_n` | 皮肤2·无背景版 | **正月的漫游·无背景版** |
| npcadaerbote | `npcadaerbote_3_n` | 皮肤3·无背景版 | **阿达尔伯特亲王·无背景版** |
| 阿尔萨斯 | `npcaersasi_3` | 皮肤3 | **阿尔萨斯** ⚠名字塌了(==船名) |
| 埃米尔·贝尔汀 | `npcaimierbeierding_5` | 皮肤5 | **埃米尔·贝尔汀** ⚠名字塌了(==船名) |
| npcaimudeng | `npcaimudeng_5` | 皮肤5 | **埃姆登** |
| npcaimudeng | `npcaimudeng_5_n` | 皮肤5·无背景版 | **埃姆登·无背景版** |
| npcantu | `npcantu_2` | 皮肤2 | **安土** |
| npcantu | `npcantu_2_hx` | 皮肤2·和谐版 | **安土·和谐版** |
| npcaogusite | `npcaogusite_4` | 皮肤4 | **奥古斯特·冯·帕塞瓦尔** |
| npcaogusite | `npcaogusite_4_n` | 皮肤4·无背景版 | **奥古斯特·冯·帕塞瓦尔·无背景版** |
| 本宁顿 | `npcbenningdun_2` | 皮肤2 | **本宁顿 ** |
| 布伦努斯 | `npcbulunnusi_3` | 皮肤3 | **布伦努斯** ⚠名字塌了(==船名) |
| 柴郡 | `npcchaijun_5_n` | 皮肤5·无背景版 | **柴郡 ·无背景版** |
| npcchuyue | `npcchuyue_3_n` | 皮肤3·无背景版 | **初月·无背景版** |
| npcfeiteliekaer | `npcfeiteliekaer_3` | 皮肤3 | **腓特烈·卡尔** |
| 关岛 | `npcguandao_3` | 皮肤3 | **关岛** ⚠名字塌了(==船名) |
| 光辉 | `npcguanghui_9` | 皮肤9 | **光辉** ⚠名字塌了(==船名) |
| npcjianye | `npcjianye_5_n` | 皮肤5·无背景版 | **樫野·无背景版** |
| npcjianye | `npcjianye_5_n_hx` | 皮肤5·无背景版·和谐版 | **樫野·和谐版·无背景版** |
| 加斯科涅 | `npcjiasikenie_3` | 皮肤3 | **加斯科涅** ⚠名字塌了(==船名) |
| npcjinluhao | `npcjinluhao_3` | 皮肤3 | **？？？** ⚠像垃圾串:全问号 |
| 君主 | `npcjunzhu_5` | 皮肤5 | **君主** ⚠名字塌了(==船名) |
| 柯莱特 | `npckelaite_2` | 皮肤2 | **柯莱特** ⚠名字塌了(==船名) |
| 可畏 | `npckewei_6` | 皮肤6 | **可畏** ⚠名字塌了(==船名) |
| 拉菲Ⅱ | `npclafeiii_4` | 皮肤4 | **拉菲Ⅱ** ⚠名字塌了(==船名) |
| 路易九世 | `npcluyijiushi_4` | 皮肤4 | **路易九世** ⚠名字塌了(==船名) |
| 马里兰 | `npcmalilan_3_n` | 皮肤3·无背景版 | **马里兰·无背景版** ⚠名字塌了(==船名) |
| npcmeiyinci | `npcmeiyinci_3` | 皮肤3 | **美因茨** |
| npcmeiyinci | `npcmeiyinci_3_hx` | 皮肤3·和谐版 | **美因茨·和谐版** |
| npcmeiyinci | `npcmeiyinci_3_n` | 皮肤3·无背景版 | **美因茨·无背景版** |
| npcmeiyinci | `npcmeiyinci_3_n_hx` | 皮肤3·无背景版·和谐版 | **美因茨·和谐版·无背景版** |
| npcmingji | `npcmingji_2` | 皮肤2 | **名寄** |
| 莫加多尔 | `npcmojiaduoer_2` | 皮肤2 | **莫加多尔** ⚠名字塌了(==船名) |
| npcrangbaer | `npcrangbaer_5_n` | 皮肤5·无背景版 | **让·巴尔·无背景版** |
| 萨里 | `npcsali_2` | 皮肤2 | **萨里** ⚠名字塌了(==船名) |
| npcshi | `npcshi_3` | 皮肤3 | **？？** ⚠像垃圾串:全问号 |
| npctianjinfeng | `npctianjinfeng_2` | 皮肤2 | **天津风** |
| 维克斯堡 | `npcweikesibao_2` | 皮肤2 | **维克斯堡** ⚠名字塌了(==船名) |
| npcweizhang | `npcweizhang_3_n` | 皮肤3·无背景版 | **尾张·无背景版** |
| npcweizhang | `npcweizhang_3_n_hx` | 皮肤3·无背景版·和谐版 | **尾张·和谐版·无背景版** |
| npcxinzexi | `npcxinzexi_4_n` | 皮肤4·无背景版 | **新泽西·无背景版** |
| 雅努斯 | `npcyanusi_7` | 皮肤7 | **雅努斯** ⚠名字塌了(==船名) |
| 厌战 | `npcyanzhan_4` | 皮肤4 | **厌战** ⚠名字塌了(==船名) |
| npcyunxian | `npcyunxian_3` | 皮肤3 | **云仙** |
| 努比亚人 | `nubiyaren_2` | 皮肤2 | **传统魔药调配** |
| 努比亚人 | `nubiyaren_2_hx` | 皮肤2·和谐版 | **传统魔药调配·和谐版** |
| 努比亚人 | `nubiyaren_2_n` | 皮肤2·无背景版 | **传统魔药调配·无背景版** |
| 努比亚人 | `nubiyaren_2_n_hx` | 皮肤2·无背景版·和谐版 | **传统魔药调配·和谐版·无背景版** |
| 努比亚人 | `nubiyaren_3` | 皮肤3 | **现代笨女仆挑战？！** |
| 努比亚人 | `nubiyaren_3_n` | 皮肤3·无背景版 | **现代笨女仆挑战？！·无背景版** |
| 女将 | `nvjiang_2` | 皮肤2 | **小小的管弦乐队** |
| 女将 | `nvjiang_g` | G | **女将.改** |
| 女天狗 | `nvtiangou_2_doa` | 皮肤2·doa | **红枫与温泉假日** |
| 女天狗 | `nvtiangou_2_doa_n` | 皮肤2·doa·无背景版 | **红枫与温泉假日·无背景版** |
| 女天狗 | `nvtiangou_doa` | doa | **女天狗** ⚠名字塌了(==船名) |
| 女天狗 | `nvtiangou_doa_wjz` | doa·wjz | **女天狗** ⚠名字塌了(==船名) |
| 欧根亲王 | `ougen_2` | 皮肤2 | **永不褪色的笑容** |
| 欧根亲王 | `ougen_3` | 皮肤3 | **百花缭乱** |
| 欧根亲王 | `ougen_4` | 皮肤4 | **Wein Kornblume** |
| 欧根亲王 | `ougen_5` | 皮肤5 | **Final Lap** |
| 欧根亲王 | `ougen_5_n` | 皮肤5·无背景版 | **Final Lap·无背景版** |
| 欧根亲王 | `ougen_6` | 皮肤6 | **沉醉于夜** |
| 欧根亲王 | `ougen_6_hx` | 皮肤6·和谐版 | **沉醉于夜·和谐版** |
| 欧根亲王 | `ougen_6_n` | 皮肤6·无背景版 | **沉醉于夜·无背景版** |
| 欧根亲王 | `ougen_7` | 皮肤7 | **闪耀达阵！** |
| 欧根亲王 | `ougen_7_n` | 皮肤7·无背景版 | **闪耀达阵！·无背景版** |
| 欧根亲王 | `ougen_8` | 皮肤8 | **微醺与试探的距离** |
| 欧根亲王 | `ougen_8_hx` | 皮肤8·和谐版 | **微醺与试探的距离·和谐版** |
| 欧根亲王 | `ougen_8_n` | 皮肤8·无背景版 | **微醺与试探的距离·无背景版** |
| 欧根亲王 | `ougen_8_n_hx` | 皮肤8·无背景版·和谐版 | **微醺与试探的距离·和谐版·无背景版** |
| 欧根亲王 | `ougen_h` | h | **命运交响曲** |
| 欧根亲王 | `ougen_idol` | idol | **欧根亲王(μ兵装)** |
| 欧根亲王 | `ougen_idol_n` | idol·无背景版 | **欧根亲王(μ兵装)·无背景版** |
| 欧根亲王 | `ougen_younv` | younv | **小欧根** |
| 欧若拉 | `ouruola_2` | 皮肤2 | **春之语** |
| 欧若拉 | `ouruola_3` | 皮肤3 | **黎明的赞歌** |
| 欧若拉 | `ouruola_4` | 皮肤4 | **渝城秘技** |
| 欧若拉 | `ouruola_h` | h | **良辰凤褂** |
| 派蒂 | `paidi_2_doa` | 皮肤2·doa | **毛茸茸乐园** |
| 派蒂 | `paidi_2_doa_n` | 皮肤2·doa·无背景版 | **毛茸茸乐园·无背景版** |
| 派蒂 | `paidi_doa` | doa | **派蒂** ⚠名字塌了(==船名) |
| 庞培·马格诺 | `pangpeimagenuo_2` | 皮肤2 | **八分音符的美梦** |
| 帕萨迪纳 | `pasadina_2` | 皮肤2 | **惊喜游戏间** |
| 帕萨迪纳 | `pasadina_2_n` | 皮肤2·无背景版 | **惊喜游戏间·无背景版** |
| 帕特莉夏·阿贝尔海姆 | `patelixia_2` | 皮肤2 | **虚实交映的放松时间** |
| 佩内洛珀 | `peineiluopo_2` | 皮肤2 | **嫣红深闺** |
| 佩内洛珀 | `peineiluopo_2_n` | 皮肤2·无背景版 | **嫣红深闺·无背景版** |
| 佩内洛珀 | `peineiluopo_3` | 皮肤3 | **盐系女仆？** |
| 佩内洛珀 | `peineiluopo_3_n` | 皮肤3·无背景版 | **盐系女仆？·无背景版** |
| 平海 | `pinghai_2` | 皮肤2 | **游兴之夏** |
| 平海 | `pinghai_3` | 皮肤3 | **桂花月兔** |
| 平海 | `pinghai_4` | 皮肤4 | **东煌姐妹！·P** |
| 平海 | `pinghai_5` | 皮肤5 | **美食大远征！** |
| 平海 | `pinghai_6` | 皮肤6 | **甜蜜嫣红** |
| 平海 | `pinghai_7` | 皮肤7 | **二宝的伙伴！** |
| 平海 | `pinghai_8` | 皮肤8 | **热闹的盛宴准备** |
| 平海 | `pinghai_8_n` | 皮肤8·无背景版 | **热闹的盛宴准备·无背景版** |
| 平海 | `pinghai_g` | G | **平海.改** |
| 平海 | `pinghai_memory` | memory | **平海** ⚠名字塌了(==船名) |
| 匹兹堡 | `pizibao_2` | 皮肤2 | **斟酒女郎的赌局** |
| 匹兹堡 | `pizibao_2_hx` | 皮肤2·和谐版 | **斟酒女郎的赌局·和谐版** |
| 匹兹堡 | `pizibao_2_n` | 皮肤2·无背景版 | **斟酒女郎的赌局·无背景版** |
| 匹兹堡 | `pizibao_2_n_hx` | 皮肤2·无背景版·和谐版 | **斟酒女郎的赌局·和谐版·无背景版** |
| 浦波 | `pubo_2` | 皮肤2 | **雪地先锋** |
| 朴茨茅斯冒险号 | `pucimaosi_2` | 皮肤2 | **精心准备的“惊喜”** |
| 朴茨茅斯冒险号 | `pucimaosi_2_hx` | 皮肤2·和谐版 | **精心准备的“惊喜”·和谐版** |
| 朴茨茅斯冒险号 | `pucimaosi_2_n` | 皮肤2·无背景版 | **精心准备的“惊喜”·无背景版** |
| 朴茨茅斯冒险号 | `pucimaosi_2_n_hx` | 皮肤2·无背景版·和谐版 | **精心准备的“惊喜”·和谐版·无背景版** |
| 浦风 | `pufeng_2` | 皮肤2 | **圣诞大将军** |
| 浦风 | `pufeng_2_hx` | 皮肤2·和谐版 | **圣诞大将军·和谐版** |
| 浦风 | `pufeng_3` | 皮肤3 | **战国乐队！** |
| 浦风 | `pufeng_3_n` | 皮肤3·无背景版 | **战国乐队！·无背景版** |
| 普利茅斯 | `pulimaosi_2` | 皮肤2 | **无暇的夏之心** |
| 普利茅斯 | `pulimaosi_3` | 皮肤3 | **纯白天使的全身检查** |
| 普利茅斯 | `pulimaosi_3_n` | 皮肤3·无背景版 | **纯白天使的全身检查·无背景版** |
| 普林斯顿 | `pulinsidun_2` | 皮肤2 | **浅海的特别训练** |
| 普林斯顿 | `pulinsidun_2_n` | 皮肤2·无背景版 | **浅海的特别训练·无背景版** |
| 普林斯顿 | `pulinsidun_3` | 皮肤3 | **心跳的糖果乐园** |
| 普林斯顿 | `pulinsidun_3_n` | 皮肤3·无背景版 | **心跳的糖果乐园·无背景版** |
| 普林斯顿 | `pulinsidun_4` | 皮肤4 | **驯鹿小姐的献礼** |
| 普林斯顿 | `pulinsidun_4_n` | 皮肤4·无背景版 | **驯鹿小姐的献礼·无背景版** |
| 恰巴耶夫 | `qiabayefu_2` | 皮肤2 | **拘束的白骑兵** |
| 恰巴耶夫 | `qiabayefu_2_n` | 皮肤2·无背景版 | **拘束的白骑兵·无背景版** |
| 恰巴耶夫 | `qiabayefu_3` | 皮肤3 | **白骑兵的假日** |
| 恰巴耶夫 | `qiabayefu_3_n` | 皮肤3·无背景版 | **白骑兵的假日·无背景版** |
| 恰巴耶夫 | `qiabayefu_4` | 皮肤4 | **夏夜青蓝** |
| 恰巴耶夫 | `qiabayefu_4_n` | 皮肤4·无背景版 | **夏夜青蓝·无背景版** |
| 恰巴耶夫 | `qiabayefu_5` | 皮肤5 | **白骑兵的旋律** |
| 恰巴耶夫 | `qiabayefu_5_n` | 皮肤5·无背景版 | **白骑兵的旋律·无背景版** |
| 恰巴耶夫 | `qiabayefu_dark` | dark | **？？？** ⚠像垃圾串:全问号 |
| 新条茜 | `qian_2` | 皮肤2 | **两人独处的休息日** |
| 新条茜 | `qian_3` | 皮肤3 | **秘密房间** |
| 新条茜 | `qian_3_n` | 皮肤3·无背景版 | **秘密房间·无背景版** |
| 千代田 | `qiandaitian_2` | 皮肤2 | **碧波灿烂之日** |
| 千代田 | `qiandaitian_2_n` | 皮肤2·无背景版 | **碧波灿烂之日·无背景版** |
| 千代田 | `qiandaitian_3` | 皮肤3 | **荷畔酒香** |
| 浅间 | `qianjian_2` | 皮肤2 | **绽放于至深之夜** |
| 浅间 | `qianjian_2_hx` | 皮肤2·和谐版 | **绽放于至深之夜·和谐版** |
| 浅间 | `qianjian_2_n` | 皮肤2·无背景版 | **绽放于至深之夜·无背景版** |
| 浅间 | `qianjian_2_n_hx` | 皮肤2·无背景版·和谐版 | **绽放于至深之夜·和谐版·无背景版** |
| 飞鸟川千濑 | `qianlai_2` | 皮肤2 | **与你同游的天空** |
| 飞鸟川千濑 | `qianlai_2_n` | 皮肤2·无背景版 | **与你同游的天空·无背景版** |
| 飞鸟川千濑 | `qianlai_3` | 皮肤3 | **洗衣房时光** |
| 飞鸟川千濑 | `qianlai_3_n` | 皮肤3·无背景版 | **洗衣房时光·无背景版** |
| 千乃 | `qiannai_2_doa` | 皮肤2·doa | **可爱动物装** |
| 千乃 | `qiannai_2_doa_n` | 皮肤2·doa·无背景版 | **可爱动物装·无背景版** |
| 千乃 | `qiannai_doa` | doa | **千乃** ⚠名字塌了(==船名) |
| 千岁 | `qiansui_2` | 皮肤2 | **夏阳璀璨之日** |
| 千岁 | `qiansui_2_hx` | 皮肤2·和谐版 | **夏阳璀璨之日·和谐版** |
| 千岁 | `qiansui_2_n` | 皮肤2·无背景版 | **夏阳璀璨之日·无背景版** |
| 千岁 | `qiansui_2_n_hx` | 皮肤2·无背景版·和谐版 | **夏阳璀璨之日·和谐版·无背景版** |
| 千岁 | `qiansui_3` | 皮肤3 | **水墨丽色** |
| 千岁 | `qiansui_4` | 皮肤4 | **莲池茶香** |
| 千岁 | `qiansui_4_hx` | 皮肤4·和谐版 | **莲池茶香·和谐版** |
| 前卫 | `qianwei_2` | 皮肤2 | **摇摆不定的伪装** |
| 前卫 | `qianwei_2_n` | 皮肤2·无背景版 | **摇摆不定的伪装·无背景版** |
| 如月千早 | `qianzao_2` | 皮肤2 | **水月镜花** |
| 如月千早 | `qianzao_2_n` | 皮肤2·无背景版 | **水月镜花·无背景版** |
| 英王乔治五世 | `qiaozhiwushi_2` | 皮肤2 | **温莎的玫瑰** |
| 齐柏林伯爵 | `qibolin_2` | 皮肤2 | **沙滩上的乌尔德** |
| 齐柏林伯爵 | `qibolin_3` | 皮肤3 | **红幔下的微醺** |
| 齐柏林伯爵 | `qibolin_3_n` | 皮肤3·无背景版 | **红幔下的微醺·无背景版** |
| 齐柏林伯爵 | `qibolin_younv` | younv | **小齐柏林** |
| 奇尔沙治 | `qiershazhi_2` | 皮肤2 | **Allnight Charge** |
| 奇尔沙治 | `qiershazhi_2_n` | 皮肤2·无背景版 | **Allnight Charge·无背景版** |
| 奇尔沙治 | `qiershazhi_3` | 皮肤3 | **Springtime Data** |
| 奇尔沙治 | `qiershazhi_3_n` | 皮肤3·无背景版 | **Springtime Data·无背景版** |
| 奇尔沙治 | `qiershazhi_h` | h | **Vow mode（誓言模式）** |
| 契卡洛夫 | `qikaluofu_2` | 皮肤2 | **黄昏的假日海滨** |
| 清波 | `qingbo_3` | 皮肤3 | **圣诞小红帽？** |
| 五河琴里 | `qinli_2` | 皮肤2 | **水边的女神** |
| 七省 | `qisheng_2` | 皮肤2 | **相依偎的温度** |
| 七省 | `qisheng_2_n` | 皮肤2·无背景版 | **相依偎的温度·无背景版** |
| 丘比特 | `qiubite_2` | 皮肤2 | **新番组之夜** |
| 企业 | `qiye_10` | 皮肤10 | **雨霁于心晴之时** |
| 企业 | `qiye_10_hx` | 皮肤10·和谐版 | **雨霁于心晴之时·和谐版** |
| 企业 | `qiye_2` | 皮肤2 | **驯鹿之主** |
| 企业 | `qiye_3` | 皮肤3 | **傲春之牡丹** |
| 企业 | `qiye_4` | 皮肤4 | **Anniversary Drive！** |
| 企业 | `qiye_5` | 皮肤5 | **翱翔的自由之翼** |
| 企业 | `qiye_6` | 皮肤6 | **英雄的礼服** |
| 企业 | `qiye_6_n` | 皮肤6·无背景版 | **英雄的礼服·无背景版** |
| 企业 | `qiye_7` | 皮肤7 | **Wind Catcher** |
| 企业 | `qiye_7_hx` | 皮肤7·和谐版 | **Wind Catcher·和谐版** |
| 企业 | `qiye_7_n` | 皮肤7·无背景版 | **Wind Catcher·无背景版** |
| 企业 | `qiye_8` | 皮肤8 | **旅行的启程** |
| 企业 | `qiye_8_n` | 皮肤8·无背景版 | **旅行的启程·无背景版** |
| 企业 | `qiye_9` | 皮肤9 | **天际的潜水者** |
| 企业 | `qiye_9_n` | 皮肤9·无背景版 | **天际的潜水者·无背景版** |
| 企业 | `qiye_dark` | dark | **企业** ⚠名字塌了(==船名) |
| 企业 | `qiye_dark_memory` | dark·memory | **企业** ⚠名字塌了(==船名) |
| 企业 | `qiye_h` | h | **誓约的星光** |
| 企业 | `qiye_younv` | younv | **小企业** |
| 确捷 | `quejie_2` | 皮肤2 | **自习室的Cyclamen** |
| 确捷 | `quejie_3` | 皮肤3 | **白玉佳人** |
| 确捷 | `quejie_4` | 皮肤4 | **盛夏的特别服务** |
| 确捷 | `quejie_4_n` | 皮肤4·无背景版 | **盛夏的特别服务·无背景版** |
| 让·巴尔 | `rangbaer_2` | 皮肤2 | **不羁的BloodStone** |
| 让·巴尔 | `rangbaer_3` | 皮肤3 | **秘密的Après midi** |
| 让·巴尔 | `rangbaer_3_n` | 皮肤3·无背景版 | **秘密的Après midi·无背景版** |
| 让·巴尔 | `rangbaer_4` | 皮肤4 | **舶刀Première neige** |
| 让·巴尔 | `rangbaer_4_n` | 皮肤4·无背景版 | **舶刀Première neige·无背景版** |
| 让·巴尔 | `rangbaer_5` | 皮肤5 | **灯映星展** |
| 让·巴尔 | `rangbaer_5_n` | 皮肤5·无背景版 | **灯映星展·无背景版** |
| 让·巴尔 | `rangbaer_memory` | memory | **让·巴尔** ⚠名字塌了(==船名) |
| 热心 | `rexin_2` | 皮肤2 | **热心的情人节** |
| 热心 | `rexin_3` | 皮肤3 | **Master·热心？** |
| 热心 | `rexin_3_n` | 皮肤3·无背景版 | **Master·热心？·无背景版** |
| 热心 | `rexin_g` | G | **热心.改** |
| rightchicheng_alter | `rightchicheng_alter_n` | 无背景版 | **赤城·无背景版** |
| 日向 | `rixiang_g` | G | **日向.改** |
| 瑞凤 | `ruifeng_2` | 皮肤2 | **幸运气球分发员** |
| 瑞凤 | `ruifeng_2_n` | 皮肤2·无背景版 | **幸运气球分发员·无背景版** |
| 瑞鹤 | `ruihe_2` | 皮肤2 | **祭华之鹤** |
| 瑞鹤 | `ruihe_2_n` | 皮肤2·无背景版 | **祭华之鹤·无背景版** |
| 瑞鹤 | `ruihe_3` | 皮肤3 | **飙速之鹤** |
| 瑞鹤 | `ruihe_3_n` | 皮肤3·无背景版 | **飙速之鹤·无背景版** |
| 瑞鹤 | `ruihe_4` | 皮肤4 | **急速飞驰Z** |
| 瑞鹤 | `ruihe_4_n` | 皮肤4·无背景版 | **急速飞驰Z·无背景版** |
| 瑞鹤 | `ruihe_memory` | memory | **瑞鹤** ⚠名字塌了(==船名) |
| 若叶 | `ruoye_2` | 皮肤2 | **限时圣诞Wakaba** |
| 若叶 | `ruoye_3` | 皮肤3 | **暖阳与午睡时光** |
| 若叶 | `ruoye_3_n` | 皮肤3·无背景版 | **暖阳与午睡时光·无背景版** |
| 若月 | `ruoyue_2` | 皮肤2 | **冒失的青鸟** |
| 若月 | `ruoyue_2_n` | 皮肤2·无背景版 | **冒失的青鸟·无背景版** |
| 若月 | `ruoyue_3` | 皮肤3 | **青鸟报春** |
| 若月 | `ruoyue_3_n` | 皮肤3·无背景版 | **青鸟报春·无背景版** |
| 如月 | `ruyue_2` | 皮肤2 | **新年祈愿** |
| 如月 | `ruyue_g` | G | **如月.改** |
| 天原凉子 | `ryouko_shallow` | shallow | **？？？?** ⚠像垃圾串:全问号 |
| 萨福克 | `safuke_g` | G | **萨福克.改** |
| 萨福克 | `safuke_xinshou` | xinshou | **萨福克** ⚠名字塌了(==船名) |
| 塞德利茨 | `saidelici_4` | 皮肤4 | **黯灭之系谱** |
| 塞德利茨 | `saidelici_4_n` | 皮肤4·无背景版 | **黯灭之系谱·无背景版** |
| 塞德利茨 | `saidelici_6` | 皮肤6 | **绽放的苍之华** |
| 塞德利茨 | `saidelici_6_n` | 皮肤6·无背景版 | **绽放的苍之华·无背景版** |
| 塞德利茨 | `saidelici_7` | 皮肤7 | **街头的清冽瞬间** |
| 塞德利茨 | `saidelici_7_n` | 皮肤7·无背景版 | **街头的清冽瞬间·无背景版** |
| 塞德利茨 | `saidelici_8` | 皮肤8 | **双面危局** |
| 塞德利茨 | `saidelici_8_n` | 皮肤8·无背景版 | **双面危局·无背景版** |
| 赛莉·古劳斯 | `saili_2` | 皮肤2 | **星月夜的妖精** |
| 塞瓦斯托波尔 | `saiwasituoboer_2` | 皮肤2 | **不止微醺？** |
| 塞瓦斯托波尔 | `saiwasituoboer_2_n` | 皮肤2·无背景版 | **不止微醺？·无背景版** |
| 萨拉娜 | `salana_2` | 皮肤2 | **萨拉娜(传颂之物)** |
| 萨拉托加 | `salatuojia_10` | 皮肤10 | **晨曦下的苍色** |
| 萨拉托加 | `salatuojia_10_n` | 皮肤10·无背景版 | **晨曦下的苍色·无背景版** |
| 萨拉托加 | `salatuojia_2` | 皮肤2 | **七海的憩日** |
| 萨拉托加 | `salatuojia_3` | 皮肤3 | **异国的偶像？** |
| 萨拉托加 | `salatuojia_4` | 皮肤4 | **虚拟偶像？** |
| 萨拉托加 | `salatuojia_5` | 皮肤5 | **碧海的偶像** |
| 萨拉托加 | `salatuojia_6` | 皮肤6 | **圣夜的偶像** |
| 萨拉托加 | `salatuojia_6_n` | 皮肤6·无背景版 | **圣夜的偶像·无背景版** |
| 萨拉托加 | `salatuojia_7` | 皮肤7 | **偶像迎春！** |
| 萨拉托加 | `salatuojia_7_n` | 皮肤7·无背景版 | **偶像迎春！·无背景版** |
| 萨拉托加 | `salatuojia_8` | 皮肤8 | **悠哉野餐时光** |
| 萨拉托加 | `salatuojia_9` | 皮肤9 | **杯面大使？** |
| 萨拉托加 | `salatuojia_h` | h | **敲响幸福之钟** |
| 萨拉托加 | `salatuojia_h_n` | h·无背景版 | **敲响幸福之钟·无背景版** |
| 萨里 | `sali_2` | 皮肤2 | **失序的迷糊时刻** |
| 萨里 | `sali_2_n` | 皮肤2·无背景版 | **失序的迷糊时刻·无背景版** |
| 三笠 | `sanli_2` | 皮肤2 | **樱都之风** |
| 三笠 | `sanli_3` | 皮肤3 | **大前辈招待中** |
| 三笠 | `sanli_3_n` | 皮肤3·无背景版 | **大前辈招待中·无背景版** |
| 三笠 | `sanli_4` | 皮肤4 | **赏樱日和 ** |
| 三笠 | `sanli_5` | 皮肤5 | **养精蓄锐的假日** |
| 三笠 | `sanli_5_n` | 皮肤5·无背景版 | **养精蓄锐的假日·无背景版** |
| 三笠 | `sanli_6` | 皮肤6 | **湛蓝回眸** |
| 三笠 | `sanli_6_n` | 皮肤6·无背景版 | **湛蓝回眸·无背景版** |
| 三笠 | `sanli_h` | h | **无垢舰裳** |
| 三笠 | `sanli_h_n` | h·无背景版 | **无垢舰裳·无背景版** |
| 三笠 | `sanli_memory` | memory | **三笠** ⚠名字塌了(==船名) |
| 三日月 | `sanriyue_2` | 皮肤2 | **僵尸小姐驾到！** |
| 三隈 | `sanwei_2` | 皮肤2 | **花辞·献舞** |
| 三隈 | `sanwei_2_n` | 皮肤2·无背景版 | **花辞·献舞·无背景版** |
| 瑟堡 | `sebao_2` | 皮肤2 | **布偶熊里面的是……？** |
| 瑟堡 | `sebao_2_hx` | 皮肤2·和谐版 | **布偶熊里面的是……？·和谐版** |
| 瑟堡 | `sebao_2_n` | 皮肤2·无背景版 | **布偶熊里面的是……？·无背景版** |
| 瑟堡 | `sebao_2_n_hx` | 皮肤2·无背景版·和谐版 | **布偶熊里面的是……？·和谐版·无背景版** |
| 沙恩霍斯特 | `shaenhuosite_2` | 皮肤2 | **雪豹与白梅** |
| 山城 | `shancheng_2` | 皮肤2 | **季夏攻势？** |
| 山城 | `shancheng_3` | 皮肤3 | **圣诞攻势！** |
| 山城 | `shancheng_4` | 皮肤4 | **盛装的黑猫** |
| 山城 | `shancheng_6` | 皮肤6 | **制服攻势！** |
| 山城 | `shancheng_7` | 皮肤7 | **看板娘攻势！？** |
| 山城 | `shancheng_8` | 皮肤8 | **假日攻势！** |
| 山城 | `shancheng_8_n` | 皮肤8·无背景版 | **假日攻势！·无背景版** |
| 山城 | `shancheng_g` | G | **山城.改** |
| 山城 | `shancheng_h` | h | **花嫁攻势！** |
| 山风 | `shanfeng_2` | 皮肤2 | **魔术时间到！** |
| 山风 | `shanfeng_2_n` | 皮肤2·无背景版 | **魔术时间到！·无背景版** |
| 神风 | `shenfeng_g` | G | **神风.改** |
| 圣地亚哥 | `shengdiyage_2` | 皮肤2 | **圣诞亚哥！** |
| 圣地亚哥 | `shengdiyage_g` | G | **圣地亚哥.改** |
| 圣地亚哥 | `shengdiyage_h` | h | **June Bride No.1！** |
| 圣地亚哥 | `shengdiyage_younv` | younv | **小圣地亚哥** |
| 圣哈辛托 | `shenghaxintuo_2` | 皮肤2 | **今日特别推荐** |
| 圣哈辛托 | `shenghaxintuo_2_n` | 皮肤2·无背景版 | **今日特别推荐·无背景版** |
| 圣胡安 | `shenghuan_2` | 皮肤2 | **Loinging Princess** |
| 圣胡安 | `shenghuan_2_n` | 皮肤2·无背景版 | **Loinging Princess·无背景版** |
| 胜利 | `shengli_2` | 皮肤2 | **女神的休憩日** |
| 胜利 | `shengli_3` | 皮肤3 | **春之女神的引导** |
| 胜利 | `shengli_3_hx` | 皮肤3·和谐版 | **春之女神的引导·和谐版** |
| 胜利 | `shengli_3_n` | 皮肤3·无背景版 | **春之女神的引导·无背景版** |
| 胜利 | `shengli_3_n_hx` | 皮肤3·无背景版·和谐版 | **春之女神的引导·和谐版·无背景版** |
| 胜利 | `shengli_4` | 皮肤4 | **晚夏良宵** |
| 圣路易斯 | `shengluyisi_2` | 皮肤2 | **春之华** |
| 圣路易斯 | `shengluyisi_2_hx` | 皮肤2·和谐版 | **春之华·和谐版** |
| 圣路易斯 | `shengluyisi_3` | 皮肤3 | **雪下之饮** |
| 圣路易斯 | `shengluyisi_4` | 皮肤4 | **Luxury Handle** |
| 圣路易斯 | `shengluyisi_5` | 皮肤5 | **邮轮上的诱人午后** |
| 圣路易斯 | `shengluyisi_5_n` | 皮肤5·无背景版 | **邮轮上的诱人午后·无背景版** |
| 圣马丁号 | `shengmading_2` | 皮肤2 | **光辉之影** |
| 圣马丁号 | `shengmading_2_n` | 皮肤2·无背景版 | **光辉之影·无背景版** |
| 圣女贞德 | `shengnvzhende_2` | 皮肤2 | **海之圣女** |
| 圣女贞德 | `shengnvzhende_2_hx` | 皮肤2·和谐版 | **海之圣女·和谐版** |
| 圣女贞德 | `shengnvzhende_2_n` | 皮肤2·无背景版 | **海之圣女·无背景版** |
| 圣女贞德 | `shengnvzhende_2_n_hx` | 皮肤2·无背景版·和谐版 | **海之圣女·和谐版·无背景版** |
| 圣女贞德 | `shengnvzhende_3` | 皮肤3 | **灯火佳期，江河共许** |
| 圣女贞德 | `shengnvzhende_3_n` | 皮肤3·无背景版 | **灯火佳期，江河共许·无背景版** |
| 圣塔菲 | `shengtafei_2` | 皮肤2 | **夜访八卦进行中！** |
| 圣塔菲 | `shengtafei_2_n` | 皮肤2·无背景版 | **夜访八卦进行中！·无背景版** |
| 声望 | `shengwang_2` | 皮肤2 | **韵致深雅** |
| 声望 | `shengwang_2_n` | 皮肤2·无背景版 | **韵致深雅·无背景版** |
| 声望 | `shengwang_alter` | alter | **声望·META** |
| 声望 | `shengwang_younv` | younv | **小声望** |
| 神速 | `shensu_2` | 皮肤2 | **悠哉游戏时光** |
| 神速 | `shensu_2_n` | 皮肤2·无背景版 | **悠哉游戏时光·无背景版** |
| 神速 | `shensu_4` | 皮肤4 | **夜班护士诊疗中** |
| 神速 | `shensu_4_n` | 皮肤4·无背景版 | **夜班护士诊疗中·无背景版** |
| 神通 | `shentong_2` | 皮肤2 | **军师大人@休假中** |
| 神通 | `shentong_4` | 皮肤4 | **“大灰狼”的谋算** |
| 神通 | `shentong_4_hx` | 皮肤4·和谐版 | **“大灰狼”的谋算·和谐版** |
| 神通 | `shentong_4_n` | 皮肤4·无背景版 | **“大灰狼”的谋算·无背景版** |
| 神通 | `shentong_4_n_hx` | 皮肤4·无背景版·和谐版 | **“大灰狼”的谋算·和谐版·无背景版** |
| 神通 | `shentong_alter` | alter | **神通·META** |
| 神通 | `shentong_alter_n` | alter·无背景版 | **神通·META·无背景版** |
| 神通 | `shentong_g` | G | **神通.改** |
| 深雪 | `shenxue_2` | 皮肤2 | **采购约会时间** |
| 深雪 | `shenxue_2_n` | 皮肤2·无背景版 | **采购约会时间·无背景版** |
| 深雪 | `shenxue_3` | 皮肤3 | **晴空下的可丽饼** |
| 深雪 | `shenxue_3_n` | 皮肤3·无背景版 | **晴空下的可丽饼·无背景版** |
| 深雪 | `shenxue_4` | 皮肤4 | **甜蜜的意外序曲** |
| 深雪 | `shenxue_4_n` | 皮肤4·无背景版 | **甜蜜的意外序曲·无背景版** |
| 射水鱼 | `sheshuiyu_2` | 皮肤2 | **不安分的邻座同学？** |
| 射水鱼 | `sheshuiyu_2_n` | 皮肤2·无背景版 | **不安分的邻座同学？·无背景版** |
| 射水鱼 | `sheshuiyu_3` | 皮肤3 | **兔兔特调** |
| 射水鱼 | `sheshuiyu_3_hx` | 皮肤3·和谐版 | **兔兔特调·和谐版** |
| 射水鱼 | `sheshuiyu_3_n` | 皮肤3·无背景版 | **兔兔特调·无背景版** |
| 射水鱼 | `sheshuiyu_3_n_hx` | 皮肤3·无背景版·和谐版 | **兔兔特调·和谐版·无背景版** |
| 狮 | `shi_2` | 皮肤2 | **沙滩的慵懒主宰** |
| 狮 | `shi_2_n` | 皮肤2·无背景版 | **沙滩的慵懒主宰·无背景版** |
| 狮 | `shi_3` | 皮肤3 | **夜巷中的诱引者** |
| 狮 | `shi_3_n` | 皮肤3·无背景版 | **夜巷中的诱引者·无背景版** |
| 史蒂芬·波特 | `shidifenbote_2` | 皮肤2 | **粉红干物兔** |
| 史蒂芬·波特 | `shidifenbote_2_n` | 皮肤2·无背景版 | **粉红干物兔·无背景版** |
| 什罗普郡 | `shiluopujun_g` | G | **什罗普郡.改** |
| 什罗普郡 | `shiluopujun_g_n` | G·无背景版 | **什罗普郡.改·无背景版** |
| 彼得·史特拉塞 | `shitelasai_2` | 皮肤2 | **节庆的Chronos** |
| 彼得·史特拉塞 | `shitelasai_2_n` | 皮肤2·无背景版 | **节庆的Chronos·无背景版** |
| 彼得·史特拉塞 | `shitelasai_3` | 皮肤3 | **Weiß Uhrzeiger** |
| 彼得·史特拉塞 | `shitelasai_4` | 皮肤4 | **书房的守护骑士** |
| 彼得·史特拉塞 | `shitelasai_4_n` | 皮肤4·无背景版 | **书房的守护骑士·无背景版** |
| 夜刀神十香 | `shixiang_2` | 皮肤2 | **小憩时光** |
| 夜刀神十香 | `shixiang_2_n` | 皮肤2·无背景版 | **小憩时光·无背景版** |
| 时雨 | `shiyu_2` | 皮肤2 | **进击，伊490！** |
| 时雨 | `shiyu_3` | 皮肤3 | **晚会幸运星！** |
| 时雨 | `shiyu_4` | 皮肤4 | **幸运Chocolate** |
| 时雨 | `shiyu_4_n` | 皮肤4·无背景版 | **幸运Chocolate·无背景版** |
| 时雨 | `shiyu_g` | G | **时雨.改** |
| 水无濑 | `shuiwulai_2` | 皮肤2 | **巫女的冥想修行** |
| 水无濑 | `shuiwulai_2_n` | 皮肤2·无背景版 | **巫女的冥想修行·无背景版** |
| 水星纪念 | `shuixingjinian_2` | 皮肤2 | **囚牢与诱惑** |
| 水星纪念 | `shuixingjinian_3` | 皮肤3 | **愉快的“待机”时间** |
| 水星纪念 | `shuixingjinian_3_n` | 皮肤3·无背景版 | **愉快的“待机”时间·无背景版** |
| 水星纪念 | `shuixingjinian_4` | 皮肤4 | **樱桃与休息时间** |
| 水星纪念 | `shuixingjinian_4_n` | 皮肤4·无背景版 | **樱桃与休息时间·无背景版** |
| 水星纪念 | `shuixingjinian_5` | 皮肤5 | **爱意满满巧克力** |
| 水星纪念 | `shuixingjinian_5_n` | 皮肤5·无背景版 | **爱意满满巧克力·无背景版** |
| 水星纪念 | `shuixingjinian_6` | 皮肤6 | **衣帽间里的小心思** |
| 水星纪念 | `shuixingjinian_6_n` | 皮肤6·无背景版 | **衣帽间里的小心思·无背景版** |
| 水星纪念 | `shuixingjinian_dark` | dark | **？？？** ⚠像垃圾串:全问号 |
| 水星纪念 | `shuixingjinian_g` | G | **水星纪念.改** |
| 水星纪念 | `shuixingjinian_g_n` | G·无背景版 | **水星纪念.改·无背景版** |
| 斯库拉 | `sikula_2` | 皮肤2 | **放学后的密谈？** |
| 斯库拉 | `sikula_3` | 皮肤3 | **闪耀于夜色之下** |
| 斯库拉 | `sikula_3_n` | 皮肤3·无背景版 | **闪耀于夜色之下·无背景版** |
| 斯库拉 | `sikula_4` | 皮肤4 | **侍女的裁决** |
| 斯库拉 | `sikula_4_hx` | 皮肤4·和谐版 | **侍女的裁决·和谐版** |
| 斯库拉 | `sikula_4_n` | 皮肤4·无背景版 | **侍女的裁决·无背景版** |
| 斯库拉 | `sikula_4_n_hx` | 皮肤4·无背景版·和谐版 | **侍女的裁决·和谐版·无背景版** |
| 「银狐」女士 | `silverfox_shadow` | shadow | **「银狐」女士** ⚠名字塌了(==船名) |
| 斯莫利 | `simoli_3` | 皮肤3 | **魔女快递** |
| 斯佩伯爵海军上将 | `sipeibojue_2` | 皮肤2 | **少女的星期日** |
| 斯佩伯爵海军上将 | `sipeibojue_3` | 皮肤3 | **平和的每一天** |
| 斯佩伯爵海军上将 | `sipeibojue_4` | 皮肤4 | **未知的晚会** |
| 斯佩伯爵海军上将 | `sipeibojue_5` | 皮肤5 | **铁血♥最可爱** |
| 斯佩伯爵海军上将 | `sipeibojue_younv` | younv | **小斯佩** |
| 斯佩伯爵海军上将 | `sipeibojue_younv_n` | younv·无背景版 | **小斯佩·无背景版** |
| 四糸乃 | `sisinai_2` | 皮肤2 | **秘密基地** |
| 四糸乃 | `sisinai_2_n` | 皮肤2·无背景版 | **秘密基地·无背景版** |
| 斯特拉斯堡 | `sitelasibao_2` | 皮肤2 | **赛场上的电子妖精** |
| 斯特拉斯堡 | `sitelasibao_2_hx` | 皮肤2·和谐版 | **赛场上的电子妖精·和谐版** |
| 斯特拉斯堡 | `sitelasibao_2_n` | 皮肤2·无背景版 | **赛场上的电子妖精·无背景版** |
| 斯特拉斯堡 | `sitelasibao_2_n_hx` | 皮肤2·无背景版·和谐版 | **赛场上的电子妖精·和谐版·无背景版** |
| 死亡主宰 | `siwangzhuzai_2` | 皮肤2 | **战士的小憩** |
| 死亡主宰 | `siwangzhuzai_n` | 无背景版 | **DEAD MASTER·无背景版** |
| 死亡主宰 | `siwangzhuzai_wjz` | wjz | **DEAD MASTER** |
| 四万十 | `siwanshi_2` | 皮肤2 | **热乎乎的龙神大人？** |
| 四万十 | `siwanshi_2_n` | 皮肤2·无背景版 | **热乎乎的龙神大人？·无背景版** |
| 四万十 | `siwanshi_3` | 皮肤3 | **优哉游哉的龙神大人** |
| 四万十 | `siwanshi_4` | 皮肤4 | **优哉游哉的龙神大人** |
| 四万十 | `siwanshi_4_n` | 皮肤4·无背景版 | **优哉游哉的龙神大人·无背景版** |
| 司战女神 | `sizhannvshen_2` | 皮肤2 | **女仆的战斗体验** |
| 司战女神 | `sizhannvshen_2_n` | 皮肤2·无背景版 | **女仆的战斗体验·无背景版** |
| 松鲷 | `songdiao_2` | 皮肤2 | **小店长的忙碌Time** |
| 松鲷 | `songdiao_2_n` | 皮肤2·无背景版 | **小店长的忙碌Time·无背景版** |
| 松风 | `songfeng_g` | G | **松风.改** |
| 穗香 | `suixiang_2_doa` | 皮肤2·doa | **礁石边的盛夏天使** |
| 穗香 | `suixiang_doa` | doa | **穗香** ⚠名字塌了(==船名) |
| 穗香 | `suixiang_doa_wjz` | doa·wjz | **穗香** ⚠名字塌了(==船名) |
| 苏塞克斯 | `susaikesi_2` | 皮肤2 | **艳阳与郁金香** |
| 苏塞克斯 | `susaikesi_3` | 皮肤3 | **葡萄酒与红玫瑰** |
| 苏维埃贝拉罗斯 | `suweiaibeilaluosi_2` | 皮肤2 | **消磨时间的方式** |
| 苏维埃贝拉罗斯 | `suweiaibeilaluosi_2_n` | 皮肤2·无背景版 | **消磨时间的方式·无背景版** |
| 苏维埃贝拉罗斯 | `suweiaibeilaluosi_3` | 皮肤3 | **涟漪与白纱** |
| 苏维埃贝拉罗斯 | `suweiaibeilaluosi_3_n` | 皮肤3·无背景版 | **涟漪与白纱·无背景版** |
| 苏维埃罗西亚 | `suweiailuoxiya_2` | 皮肤2 | **怠惰的监视者** |
| 苏维埃罗西亚 | `suweiailuoxiya_2_n` | 皮肤2·无背景版 | **怠惰的监视者·无背景版** |
| 苏维埃罗西亚 | `suweiailuoxiya_dark` | dark | **？？？** ⚠像垃圾串:全问号 |
| 苏维埃同盟 | `suweiaitongmeng_2` | 皮肤2 | **天幕危机** |
| 苏维埃同盟 | `suweiaitongmeng_2_n` | 皮肤2·无背景版 | **天幕危机·无背景版** |
| 苏维埃同盟 | `suweiaitongmeng_3` | 皮肤3 | **缠丝审讯** |
| 苏维埃同盟 | `suweiaitongmeng_3_hx` | 皮肤3·和谐版 | **缠丝审讯·和谐版** |
| 苏维埃同盟 | `suweiaitongmeng_3_n` | 皮肤3·无背景版 | **缠丝审讯·无背景版** |
| 苏维埃同盟 | `suweiaitongmeng_3_n_hx` | 皮肤3·无背景版·和谐版 | **缠丝审讯·和谐版·无背景版** |
| 苏维埃同盟 | `suweiaitongmeng_4` | 皮肤4 | **缠丝审讯** |
| 苏维埃同盟 | `suweiaitongmeng_4_n` | 皮肤4·无背景版 | **缠丝审讯·无背景版** |
| 苏维埃同盟 | `suweiaitongmeng_dark` | dark | **？？？** ⚠像垃圾串:全问号 |
| 苏维埃同盟 | `suweiaitongmeng_wjz` | wjz | **苏维埃同盟** ⚠名字塌了(==船名) |
| 塔尔图 | `taertu_2` | 皮肤2 | **多虑的盛夏** |
| 塔尔图 | `taertu_2_hx` | 皮肤2·和谐版 | **多虑的盛夏·和谐版** |
| 塔尔图 | `taertu_2_n` | 皮肤2·无背景版 | **多虑的盛夏·无背景版** |
| 塔尔图 | `taertu_2_n_hx` | 皮肤2·无背景版·和谐版 | **多虑的盛夏·和谐版·无背景版** |
| 太原 | `taiyuan_2` | 皮肤2 | **金蛇闹春** |
| 太原 | `taiyuan_3` | 皮肤3 | **共枕的心跳** |
| 太原 | `taiyuan_3_n` | 皮肤3·无背景版 | **共枕的心跳·无背景版** |
| 太原 | `taiyuan_g` | G | **太原.改** |
| 塔林 | `talin_2` | 皮肤2 | **是！长官！** |
| 塔林 | `talin_2_n` | 皮肤2·无背景版 | **是！长官！·无背景版** |
| 塔林 | `talin_3` | 皮肤3 | **Pilsner·Nostalgic** |
| 塔林 | `talin_3_n` | 皮肤3·无背景版 | **Pilsner·Nostalgic·无背景版** |
| 塔林 | `talin_4` | 皮肤4 | **情满月圆** |
| 塔林 | `talin_4_n` | 皮肤4·无背景版 | **情满月圆·无背景版** |
| 唐斯 | `tangsi_2` | 皮肤2 | **捣蛋的帮手？** |
| 唐斯 | `tangsi_2_n` | 皮肤2·无背景版 | **捣蛋的帮手？·无背景版** |
| 唐斯 | `tangsi_g` | G | **唐斯.改** |
| 探索者-艾普洛 | `tansuozhe_2` | 皮肤2 | **悠悠假日私语时** |
| 探索者-艾普洛 | `tansuozhe_2_n` | 皮肤2·无背景版 | **悠悠假日私语时·无背景版** |
| 塔什干 | `tashigan_2` | 皮肤2 | **受缚的巡洋舰** |
| 塔什干 | `tashigan_2_n` | 皮肤2·无背景版 | **受缚的巡洋舰·无背景版** |
| 塔什干 | `tashigan_3` | 皮肤3 | **天蓝色的休息日** |
| 塔什干 | `tashigan_3_n` | 皮肤3·无背景版 | **天蓝色的休息日·无背景版** |
| 塔什干 | `tashigan_4` | 皮肤4 | **独属于你的邀约** |
| 塔什干 | `tashigan_4_n` | 皮肤4·无背景版 | **独属于你的邀约·无背景版** |
| 塔什干 | `tashigan_dark` | dark | **？？？** ⚠像垃圾串:全问号 |
| 塔什干 | `tashigan_idol` | idol | **塔什干(μ兵装)** |
| 塔什干 | `tashigan_idol_n` | idol·无背景版 | **塔什干(μ兵装)·无背景版** |
| 特拉法尔加 | `telafaerjia_2` | 皮肤2 | **海风与夜语** |
| 特拉法尔加 | `telafaerjia_2_n` | 皮肤2·无背景版 | **海风与夜语·无背景版** |
| 特立尼达 | `telinida_2` | 皮肤2 | **更衣室里的捕猎者** |
| 特伦托 | `teluntuo_2` | 皮肤2 | **盛夏的多重诱惑？** |
| 特伦托 | `teluntuo_2_n` | 皮肤2·无背景版 | **盛夏的多重诱惑？·无背景版** |
| 藤波 | `tengbo_2` | 皮肤2 | **藤波的秘密穿搭** |
| 藤波 | `tengbo_2_n` | 皮肤2·无背景版 | **藤波的秘密穿搭·无背景版** |
| 忒修斯 | `texiusi_2` | 皮肤2 | **白羽报春** |
| 忒修斯 | `texiusi_2_n` | 皮肤2·无背景版 | **白羽报春·无背景版** |
| 天城 | `tiancheng_2` | 皮肤2 | **走水静莲** |
| 天城 | `tiancheng_2_n` | 皮肤2·无背景版 | **走水静莲·无背景版** |
| 天城 | `tiancheng_3` | 皮肤3 | **红鸢的闲暇片刻** |
| 天城 | `tiancheng_3_n` | 皮肤3·无背景版 | **红鸢的闲暇片刻·无背景版** |
| 天城 | `tiancheng_cv` | cv | **天城** ⚠名字塌了(==船名) |
| 天城 | `tiancheng_cv_2` | cv·皮肤2 | **落于王座之花** |
| 天城 | `tiancheng_cv_2_n` | cv·皮肤2·无背景版 | **落于王座之花·无背景版** |
| 天城 | `tiancheng_cv_3` | cv·皮肤3 | **碧波绮尾** |
| 天城 | `tiancheng_cv_3_n` | cv·皮肤3·无背景版 | **碧波绮尾·无背景版** |
| 天城 | `tiancheng_cv_h` | cv·h | **水月花烛** |
| 天城 | `tiancheng_cv_h_n` | cv·h·无背景版 | **水月花烛·无背景版** |
| 天后 | `tianhou_2` | 皮肤2 | **美味的祭典？** |
| 天后 | `tianhou_2_n` | 皮肤2·无背景版 | **美味的祭典？·无背景版** |
| 天津风 | `tianjinfeng_2` | 皮肤2 | **狐仙大人驾到** |
| 天津风 | `tianjinfeng_2_n` | 皮肤2·无背景版 | **狐仙大人驾到·无背景版** |
| 天津风 | `tianjinfeng_3` | 皮肤3 | **狐仙大人驾到** |
| 天津风 | `tianjinfeng_3_n` | 皮肤3·无背景版 | **狐仙大人驾到·无背景版** |
| 天狼星 | `tianlangxing_2` | 皮肤2 | **纯白蔷薇** |
| 天狼星 | `tianlangxing_3` | 皮肤3 | **盛夏的Seirios ** |
| 天狼星 | `tianlangxing_4` | 皮肤4 | **碧波青云** |
| 天狼星 | `tianlangxing_5` | 皮肤5 | **至高乐园的白兔** |
| 天狼星 | `tianlangxing_5_n` | 皮肤5·无背景版 | **至高乐园的白兔·无背景版** |
| 天狼星 | `tianlangxing_h` | h | **Alba Sirius** |
| 天狼星 | `tianlangxing_h_n` | h·无背景版 | **Alba Sirius·无背景版** |
| 天鹰 | `tianying_2` | 皮肤2 | **阳光与浅潮的假日** |
| 天鹰 | `tianying_2_hx` | 皮肤2·和谐版 | **阳光与浅潮的假日·和谐版** |
| 天鹰 | `tianying_2_n` | 皮肤2·无背景版 | **阳光与浅潮的假日·无背景版** |
| 天鹰 | `tianying_2_n_hx` | 皮肤2·无背景版·和谐版 | **阳光与浅潮的假日·和谐版·无背景版** |
| 天鹰 | `tianying_3` | 皮肤3 | **绿苑的优雅花园** |
| 天鹰 | `tianying_3_n` | 皮肤3·无背景版 | **绿苑的优雅花园·无背景版** |
| 提尔比茨 | `tierbici_2` | 皮肤2 | **冰雪消融的夏日** |
| 提尔比茨 | `tierbici_3` | 皮肤3 | **铁血的冰风** |
| 提尔比茨 | `tierbici_4` | 皮肤4 | **松之节句、白之冰华** |
| 提尔比茨 | `tierbici_4_n` | 皮肤4·无背景版 | **松之节句、白之冰华·无背景版** |
| 提尔比茨 | `tierbici_5` | 皮肤5 | **独秀的冰华** |
| 提尔比茨 | `tierbici_5_n` | 皮肤5·无背景版 | **独秀的冰华·无背景版** |
| 提尔比茨 | `tierbici_6` | 皮肤6 | **赛道上的等候** |
| 提尔比茨 | `tierbici_6_n` | 皮肤6·无背景版 | **赛道上的等候·无背景版** |
| 提康德罗加 | `tikangdeluojia_2` | 皮肤2 | **黑兔的舞台秀** |
| 提康德罗加 | `tikangdeluojia_2_hx` | 皮肤2·和谐版 | **黑兔的舞台秀·和谐版** |
| 提康德罗加 | `tikangdeluojia_2_n` | 皮肤2·无背景版 | **黑兔的舞台秀·无背景版** |
| 提康德罗加 | `tikangdeluojia_2_n_hx` | 皮肤2·无背景版·和谐版 | **黑兔的舞台秀·和谐版·无背景版** |
| 提康德罗加 | `tikangdeluojia_3` | 皮肤3 | **日光公主** |
| 提康德罗加 | `tikangdeluojia_3_n` | 皮肤3·无背景版 | **日光公主·无背景版** |
| 突击者 | `tujizhe_g` | G | **突击者.改** |
| 图林根 | `tulingen_2` | 皮肤2 | **月下的大清扫** |
| 图林根 | `tulingen_2_n` | 皮肤2·无背景版 | **月下的大清扫·无背景版** |
| 托里拆利 | `tuolichaili_2` | 皮肤2 | **阴暗的沙滩一角** |
| 托里拆利 | `tuolichaili_2_n` | 皮肤2·无背景版 | **阴暗的沙滩一角·无背景版** |
| 土佐 | `tuzuo_2` | 皮肤2 | **鸣子小夏** |
| 土佐 | `tuzuo_3` | 皮肤3 | **水色间的游曳** |
| 土佐 | `tuzuo_3_hx` | 皮肤3·和谐版 | **水色间的游曳·和谐版** |
| 土佐 | `tuzuo_3_n` | 皮肤3·无背景版 | **水色间的游曳·无背景版** |
| 土佐 | `tuzuo_3_n_hx` | 皮肤3·无背景版·和谐版 | **水色间的游曳·和谐版·无背景版** |
| U-101 | `u101_2` | 皮肤2 | **学园的Posaunist** |
| U-110 | `u110_2` | 皮肤2 | **Kleiner Hai** |
| U-110 | `u110_3` | 皮肤3 | **鲨鱼小可爱** |
| U-110 | `u110_3_n` | 皮肤3·无背景版 | **鲨鱼小可爱·无背景版** |
| U-110 | `u110_4` | 皮肤4 | **Girlish Idolish** |
| U-110 | `u110_4_n` | 皮肤4·无背景版 | **Girlish Idolish·无背景版** |
| U-110 | `u110_5` | 皮肤5 | **小鲨鱼的初梦** |
| U-110 | `u110_5_n` | 皮肤5·无背景版 | **小鲨鱼的初梦·无背景版** |
| U-110 | `u110_6` | 皮肤6 | **雪地小鲨鱼** |
| U-110 | `u110_6_n` | 皮肤6·无背景版 | **雪地小鲨鱼·无背景版** |
| U-1206 | `u1206_2` | 皮肤2 | **需要服务请按铃！** |
| U-1206 | `u1206_2_n` | 皮肤2·无背景版 | **需要服务请按铃！·无背景版** |
| U-2501 | `u2501_2` | 皮肤2 | **水幕后的珍宝** |
| U-2501 | `u2501_2_n` | 皮肤2·无背景版 | **水幕后的珍宝·无背景版** |
| U-31 | `u31_2` | 皮肤2 | **在一起回家之前** |
| U-31 | `u31_2_n` | 皮肤2·无背景版 | **在一起回家之前·无背景版** |
| U-37 | `u37_2` | 皮肤2 | **轻弹浅唱正月时** |
| U-37 | `u37_2_n` | 皮肤2·无背景版 | **轻弹浅唱正月时·无背景版** |
| U-37 | `u37_3` | 皮肤3 | **公路维和组，出击！** |
| U-37 | `u37_3_n` | 皮肤3·无背景版 | **公路维和组，出击！·无背景版** |
| U-410 | `u410_2` | 皮肤2 | **寒梅映春** |
| U-410 | `u410_2_n` | 皮肤2·无背景版 | **寒梅映春·无背景版** |
| U-410 | `u410_3` | 皮肤3 | **悠然应援练习** |
| U-410 | `u410_3_n` | 皮肤3·无背景版 | **悠然应援练习·无背景版** |
| U-47 | `u47_2` | 皮肤2 | **新晋骑行达人？** |
| U-47 | `u47_3` | 皮肤3 | **静谧一隅** |
| U-47 | `u47_3_n` | 皮肤3·无背景版 | **静谧一隅·无背景版** |
| U-47 | `u47_4` | 皮肤4 | **女仆极速达** |
| U-47 | `u47_5` | 皮肤5 | **赤月下的慵懒** |
| U-47 | `u47_5_hx` | 皮肤5·和谐版 | **赤月下的慵懒·和谐版** |
| U-47 | `u47_5_n` | 皮肤5·无背景版 | **赤月下的慵懒·无背景版** |
| U-47 | `u47_5_n_hx` | 皮肤5·无背景版·和谐版 | **赤月下的慵懒·和谐版·无背景版** |
| U-47 | `u47_6` | 皮肤6 | **锦鲤捕获作战** |
| U-47 | `u47_6_n` | 皮肤6·无背景版 | **锦鲤捕获作战·无背景版** |
| U-552 | `u552_2` | 皮肤2 | **导游？特工？特别观光服务！ ** |
| U-552 | `u552_2_n` | 皮肤2·无背景版 | **导游？特工？特别观光服务！ ·无背景版** |
| U-556 | `u556_2` | 皮肤2 | **嬉闹之夜！** |
| U-556 | `u556_3` | 皮肤3 | **Cruiserush Knight** |
| U-556 | `u556_3_hx` | 皮肤3·和谐版 | **Cruiserush Knight·和谐版** |
| U-556 | `u556_3_n` | 皮肤3·无背景版 | **Cruiserush Knight·无背景版** |
| U-556 | `u556_3_n_hx` | 皮肤3·无背景版·和谐版 | **Cruiserush Knight·和谐版·无背景版** |
| U-73 | `u73_3` | 皮肤3 | **理科实验时间！** |
| U-73 | `u73_4` | 皮肤4 | **早春的热情药剂** |
| U-73 | `u73_4_n` | 皮肤4·无背景版 | **早春的热情药剂·无背景版** |
| U-81 | `u81_2` | 皮肤2 | **静谧小夜曲** |
| U-81 | `u81_3` | 皮肤3 | **灯映满月** |
| U-96 | `u96_2` | 皮肤2 | **秘密的游戏时间** |
| U-96 | `u96_3` | 皮肤3 | **流汗吧，举重少女！** |
| U-96 | `u96_3_n` | 皮肤3·无背景版 | **流汗吧，举重少女！·无背景版** |
| U-96 | `u96_4` | 皮肤4 | **wolfen dolly** |
| U-96 | `u96_4_hx` | 皮肤4·和谐版 | **wolfen dolly·和谐版** |
| U-96 | `u96_4_n` | 皮肤4·无背景版 | **wolfen dolly·无背景版** |
| U-96 | `u96_4_n_hx` | 皮肤4·无背景版·和谐版 | **wolfen dolly·和谐版·无背景版** |
| unknown1 | `unknown1_hx` | 和谐版 | **？？？？？·和谐版** ⚠像垃圾串:全问号 |
| unknown2 | `unknown2_hx` | 和谐版 | **？？？？？·和谐版** ⚠像垃圾串:全问号 |
| 湊阿库娅 | `vtuber_aqua_2` | 皮肤2 | **海之女仆** |
| 百鬼绫目 | `vtuber_ayame_2` | 皮肤2 | **夏之百鬼** |
| 白上吹雪 | `vtuber_fubuki_2` | 皮肤2 | **沙滩之狐** |
| 白上吹雪 | `vtuber_fubuki_2_n` | 皮肤2·无背景版 | **沙滩之狐·无背景版** |
| 夏色祭 | `vtuber_matsuri_2` | 皮肤2 | **祭的居家日** |
| 大神澪 | `vtuber_mio_2` | 皮肤2 | **Summer Vacance** |
| 紫咲诗音 | `vtuber_shion_2` | 皮肤2 | **虚拟魔法使** |
| 时乃空 | `vtuber_sora_2` | 皮肤2 | **晴空之夏** |
| 顽皮 | `wanpi_2` | 皮肤2 | **乘风披挂跃琼霄** |
| 顽皮 | `wanpi_2_n` | 皮肤2·无背景版 | **乘风披挂跃琼霄·无背景版** |
| 维达号 | `weida_2` | 皮肤2 | **慵懒的黑天使** |
| 维达号 | `weida_2_n` | 皮肤2·无背景版 | **慵懒的黑天使·无背景版** |
| 威尔士亲王 | `weiershiqinwang_2` | 皮肤2 | **阳光照耀着温莎** |
| 威尔士亲王 | `weiershiqinwang_3` | 皮肤3 | **桂冠的胜利竞速** |
| 威尔士亲王 | `weiershiqinwang_3_n` | 皮肤3·无背景版 | **桂冠的胜利竞速·无背景版** |
| 威尔士亲王 | `weiershiqinwang_4` | 皮肤4 | **皇家式风流** |
| 威尔士亲王 | `weiershiqinwang_5` | 皮肤5 | **骑士旋律，少女星空** |
| 威尔士亲王 | `weiershiqinwang_5_n` | 皮肤5·无背景版 | **骑士旋律，少女星空·无背景版** |
| 维克斯堡 | `weikesibao_2` | 皮肤2 | **闪亮的赛车偶像** |
| 维克斯堡 | `weikesibao_2_n` | 皮肤2·无背景版 | **闪亮的赛车偶像·无背景版** |
| 维克斯堡 | `weikesibao_3` | 皮肤3 | **闪亮的赛车偶像** |
| 维克斯堡 | `weikesibao_3_hx` | 皮肤3·和谐版 | **闪亮的赛车偶像·和谐版** |
| 维托里奥·维内托 | `weineituo_2` | 皮肤2 | **拉斯佩齐亚之花** |
| 维托里奥·维内托 | `weineituo_2_n` | 皮肤2·无背景版 | **拉斯佩齐亚之花·无背景版** |
| 威奇塔 | `weiqita_2` | 皮肤2 | **“将军”的晚宴** |
| 威奇塔 | `weiqita_2_n` | 皮肤2·无背景版 | **“将军”的晚宴·无背景版** |
| 威奇塔 | `weiqita_3` | 皮肤3 | **万圣的支配者？** |
| 威奇塔 | `weiqita_3_n` | 皮肤3·无背景版 | **万圣的支配者？·无背景版** |
| 威奇塔 | `weiqita_alter` | alter | **威奇塔·META ** |
| 威奇塔 | `weiqita_alter_n` | alter·无背景版 | **威奇塔·META ·无背景版** |
| 威悉 | `weixi_2` | 皮肤2 | **黯调铅华** |
| 威悉 | `weixi_2_n` | 皮肤2·无背景版 | **黯调铅华·无背景版** |
| 威悉 | `weixi_3` | 皮肤3 | **暗金绣色** |
| 威悉 | `weixi_3_n` | 皮肤3·无背景版 | **暗金绣色·无背景版** |
| 威悉 | `weixi_4` | 皮肤4 | **碧波粼粼的乐园** |
| 威悉 | `weixi_4_n` | 皮肤4·无背景版 | **碧波粼粼的乐园·无背景版** |
| 威悉 | `weixi_5` | 皮肤5 | **Offtime Cafe** |
| 威悉 | `weixi_5_n` | 皮肤5·无背景版 | **Offtime Cafe·无背景版** |
| 威严 | `weiyan_2` | 皮肤2 | **囚牢里的危险兔** |
| 威严 | `weiyan_3` | 皮肤3 | **武器改造计划？** |
| 威严 | `weiyan_3_n` | 皮肤3·无背景版 | **武器改造计划？·无背景版** |
| 威严 | `weiyan_4` | 皮肤4 | **突袭！暗黑基地！** |
| 威严 | `weiyan_4_hx` | 皮肤4·和谐版 | **突袭！暗黑基地！·和谐版** |
| 威严 | `weiyan_4_n` | 皮肤4·无背景版 | **突袭！暗黑基地！·无背景版** |
| 威严 | `weiyan_4_n_hx` | 皮肤4·无背景版·和谐版 | **突袭！暗黑基地！·和谐版·无背景版** |
| 威严 | `weiyan_5` | 皮肤5 | **别样的品茶时光** |
| 威严 | `weiyan_5_n` | 皮肤5·无背景版 | **别样的品茶时光·无背景版** |
| 威严 | `weiyan_6` | 皮肤6 | **野兔和蒸汽房** |
| 威严 | `weiyan_6_n` | 皮肤6·无背景版 | **野兔和蒸汽房·无背景版** |
| 威严 | `weiyan_dark` | dark | **？？？** ⚠像垃圾串:全问号 |
| 尾张 | `weizhang_2` | 皮肤2 | **波光潋滟** |
| 尾张 | `weizhang_2_hx` | 皮肤2·和谐版 | **波光潋滟·和谐版** |
| 尾张 | `weizhang_2_n` | 皮肤2·无背景版 | **波光潋滟·无背景版** |
| 尾张 | `weizhang_2_n_hx` | 皮肤2·无背景版·和谐版 | **波光潋滟·和谐版·无背景版** |
| 尾张 | `weizhang_3` | 皮肤3 | **愿望为“爱”** |
| 尾张 | `weizhang_3_n` | 皮肤3·无背景版 | **愿望为“爱”·无背景版** |
| 文琴佐·焦贝蒂 | `wenqinzuojiaobeidi_3` | 皮肤3 | **“淑女”的邀约** |
| 文琴佐·焦贝蒂 | `wenqinzuojiaobeidi_3_n` | 皮肤3·无背景版 | **“淑女”的邀约·无背景版** |
| 文森斯 | `wensensi_2` | 皮肤2 | **悠哉进行曲** |
| 文森斯 | `wensensi_3` | 皮肤3 | **喵喵的美梦** |
| 文月 | `wenyue_2` | 皮肤2 | **迷糊的妖精** |
| 沃克兰 | `wokelan_2` | 皮肤2 | **天然纯真夏日骑士** |
| 沃克兰 | `wokelan_2_n` | 皮肤2·无背景版 | **天然纯真夏日骑士·无背景版** |
| 沃克兰 | `wokelan_3` | 皮肤3 | **全自动交响乐？** |
| 沃克兰 | `wokelan_3_n` | 皮肤3·无背景版 | **全自动交响乐？·无背景版** |
| 沃克兰 | `wokelan_4` | 皮肤4 | **异世界的“不速之客”** |
| 沃克兰 | `wokelan_4_hx` | 皮肤4·和谐版 | **异世界的“不速之客”·和谐版** |
| 沃克兰 | `wokelan_4_n` | 皮肤4·无背景版 | **异世界的“不速之客”·无背景版** |
| 沃克兰 | `wokelan_4_n_hx` | 皮肤4·无背景版·和谐版 | **异世界的“不速之客”·和谐版·无背景版** |
| 雾岛 | `wudao_2` | 皮肤2 | **放学后的退敌时间** |
| 雾岛 | `wudao_3` | 皮肤3 | **夏日的大胆尝试** |
| 雾岛 | `wudao_4` | 皮肤4 | **随性的闪耀之星** |
| 雾岛 | `wudao_5` | 皮肤5 | **雅致墨香** |
| 无敌 | `wudi_2` | 皮肤2 | **护花使者？** |
| 乌尔里希·冯·胡滕 | `wuerlixi_2` | 皮肤2 | **Mädchen Trümmer** |
| 乌尔里希·冯·胡滕 | `wuerlixi_2_n` | 皮肤2·无背景版 | **Mädchen Trümmer·无背景版** |
| 乌尔里希·冯·胡滕 | `wuerlixi_3` | 皮肤3 | **一骑绝尘** |
| 乌尔里希·冯·胡滕 | `wuerlixi_3_n` | 皮肤3·无背景版 | **一骑绝尘·无背景版** |
| 乌尔里希·冯·胡滕 | `wuerlixi_4` | 皮肤4 | **在教室中等待** |
| 乌尔里希·冯·胡滕 | `wuerlixi_4_n` | 皮肤4·无背景版 | **在教室中等待·无背景版** |
| 乌尔里希·冯·胡滕 | `wuerlixi_h` | h | **Liebestrank（迷魂酒/爱情魔药）** ⚠长度异常 |
| 乌尔里希·冯·胡滕 | `wuerlixi_h_n` | h·无背景版 | **Liebestrank（迷魂酒/爱情魔药）·无背景版** ⚠长度异常 |
| 乌戈里诺·维瓦尔迪 | `wugelini_2` | 皮肤2 | **意外捕获·稀有款！** |
| 无惧 | `wuju_2` | 皮肤2 | **炙焰冲刺！** |
| 无惧 | `wuju_2_n` | 皮肤2·无背景版 | **炙焰冲刺！·无背景版** |
| 乌璐露 | `wululu_2` | 皮肤2 | **乌璐露(传颂之物)** |
| 吾妻 | `wuqi_2` | 皮肤2 | **细语春霞** |
| 吾妻 | `wuqi_3` | 皮肤3 | **心向何方的指导课** |
| 吾妻 | `wuqi_3_hx` | 皮肤3·和谐版 | **心向何方的指导课·和谐版** |
| 吾妻 | `wuqi_3_n` | 皮肤3·无背景版 | **心向何方的指导课·无背景版** |
| 吾妻 | `wuqi_h` | h | **纯洁憧憬** |
| 五十铃 | `wushiling_2` | 皮肤2 | **童话之夜** |
| 五十铃 | `wushiling_3` | 皮肤3 | **暖洋洋的圣诞夜** |
| 五十铃 | `wushiling_5` | 皮肤5 | **过热事故？** |
| 五十铃 | `wushiling_6` | 皮肤6 | **急速！骑马战！** |
| 五十铃 | `wushiling_6_n` | 皮肤6·无背景版 | **急速！骑马战！·无背景版** |
| 五十铃 | `wushiling_g` | G | **五十铃.改** |
| 无畏 | `wuwei_2` | 皮肤2 | **无畏的一投** |
| 无畏 | `wuwei_2_n` | 皮肤2·无背景版 | **无畏的一投·无背景版** |
| 武藏 | `wuzang_2` | 皮肤2 | **堇色月影** |
| 武藏 | `wuzang_3` | 皮肤3 | **堇色兔的狙击游戏** |
| 武藏 | `wuzang_3_hx` | 皮肤3·和谐版 | **堇色兔的狙击游戏·和谐版** |
| 武藏 | `wuzang_3_n` | 皮肤3·无背景版 | **堇色兔的狙击游戏·无背景版** |
| 武藏 | `wuzang_3_n_hx` | 皮肤3·无背景版·和谐版 | **堇色兔的狙击游戏·和谐版·无背景版** |
| 武藏 | `wuzang_4` | 皮肤4 | **只为你献上的应援** |
| 武藏 | `wuzang_4_n` | 皮肤4·无背景版 | **只为你献上的应援·无背景版** |
| 武藏 | `wuzang_h` | h | **紫藤花的无瑕心意** |
| 武藏 | `wuzang_h_hx` | h·和谐版 | **紫藤花的无瑕心意·和谐版** |
| 武藏 | `wuzang_h_n` | h·无背景版 | **紫藤花的无瑕心意·无背景版** |
| 武藏 | `wuzang_h_n_hx` | h·无背景版·和谐版 | **紫藤花的无瑕心意·和谐版·无背景版** |
| 武藏 | `wuzang_s` | s | **武藏** ⚠名字塌了(==船名) |
| 霞.改 | `xia_2` | 皮肤2 | **新年暖洋洋** |
| 霞.改 | `xia_2_doa` | 皮肤2·doa | **水边的霞光** |
| 霞.改 | `xia_2_doa_n` | 皮肤2·doa·无背景版 | **水边的霞光·无背景版** |
| 霞.改 | `xia_3` | 皮肤3 | **开学晃悠悠** |
| 霞.改 | `xia_3_n` | 皮肤3·无背景版 | **开学晃悠悠·无背景版** |
| 霞.改 | `xia_doa` | doa | **霞** |
| 霞.改 | `xia_doa_wjz` | doa·wjz | **霞** |
| 霞.改 | `xia_g` | G | **霞.改** ⚠名字塌了(==船名) |
| 霞飞-战斗天使 | `xiafei_2` | 皮肤2 | **笼中的白雪公主** |
| 霞飞-战斗天使 | `xiafei_2_hx` | 皮肤2·和谐版 | **笼中的白雪公主·和谐版** |
| 霞飞-战斗天使 | `xiafei_2_n` | 皮肤2·无背景版 | **笼中的白雪公主·无背景版** |
| 霞飞-战斗天使 | `xiafei_2_n_hx` | 皮肤2·无背景版·和谐版 | **笼中的白雪公主·和谐版·无背景版** |
| 霞飞-战斗天使 | `xiafei_3` | 皮肤3 | **至高乐园** |
| 霞飞-战斗天使 | `xiafei_3_n` | 皮肤3·无背景版 | **至高乐园·无背景版** |
| 霞飞-战斗天使 | `xiafei_4` | 皮肤4 | **祝福的起步冲刺** |
| 霞飞-战斗天使 | `xiafei_4_hx` | 皮肤4·和谐版 | **祝福的起步冲刺·和谐版** |
| 霞飞-战斗天使 | `xiafei_hx` | 和谐版 | **霞飞·和谐版** |
| 响 | `xiang_2` | 皮肤2 | **正月小恶魔** |
| 香槟 | `xiangbin_2` | 皮肤2 | **初梦蓝彩** |
| 香迪 | `xiangdi_2_doa_n` | 无背景版 | **魅惑的特调饮品·无背景版** |
| 祥凤 | `xiangfeng_2` | 皮肤2 | **夜巡的魔女** |
| 祥凤 | `xiangfeng_g` | G | **祥凤.改** |
| 香格里拉 | `xianggelila_2` | 皮肤2 | **乐园的收藏家** |
| 香格里拉 | `xianggelila_3` | 皮肤3 | **失落世界的探险者** |
| 香格里拉 | `xianggelila_3_n` | 皮肤3·无背景版 | **失落世界的探险者·无背景版** |
| 翔鹤 | `xianghe_2` | 皮肤2 | **散花舞鹤** |
| 翔鹤 | `xianghe_3` | 皮肤3 | **疾速之鹤** |
| 翔鹤 | `xianghe_3_n` | 皮肤3·无背景版 | **疾速之鹤·无背景版** |
| 翔鹤 | `xianghe_4` | 皮肤4 | **飞雪织缘** |
| 翔鹤 | `xianghe_4_n` | 皮肤4·无背景版 | **飞雪织缘·无背景版** |
| 翔鹤 | `xianghe_h` | h | **鸣鹤衔禧** |
| 翔鹤 | `xianghe_h_n` | h·无背景版 | **鸣鹤衔禧·无背景版** |
| 翔鹤 | `xianghe_memory` | memory | **翔鹤** ⚠名字塌了(==船名) |
| 晓 | `xiao_2` | 皮肤2 | **北极的迷途** |
| 晓 | `xiao_3` | 皮肤3 | **摩托忍者，出击！** |
| 晓 | `xiao_4` | 皮肤4 | **驯鹿忍者派送中！** |
| 晓 | `xiao_4_n` | 皮肤4·无背景版 | **驯鹿忍者派送中！·无背景版** |
| 晓 | `xiao_5` | 皮肤5 | **压轴！忍者戏法！** |
| 晓 | `xiao_5_n` | 皮肤5·无背景版 | **压轴！忍者戏法！·无背景版** |
| 小天鹅 | `xiaotiane_2` | 皮肤2 | **海滨的十字星** |
| 小天鹅 | `xiaotiane_3` | 皮肤3 | **圣夜的赞美诗** |
| 小天鹅 | `xiaotiane_4` | 皮肤4 | **女仆体验周？** |
| 小天鹅 | `xiaotiane_5` | 皮肤5 | **冬日的约会** |
| 小天鹅 | `xiaotiane_6` | 皮肤6 | **皇家应援曲** |
| 小天鹅 | `xiaotiane_g` | G | **小天鹅.改** |
| 宵月 | `xiaoyue_2` | 皮肤2 | **运动会的准备** |
| 宵月 | `xiaoyue_3` | 皮肤3 | **爆竹除岁** |
| 宵月 | `xiaoyue_3_n` | 皮肤3·无背景版 | **爆竹除岁·无背景版** |
| 西北风 | `xibeifeng_2` | 皮肤2 | **独处的沙滩一角** |
| 西北风 | `xibeifeng_2_hx` | 皮肤2·和谐版 | **独处的沙滩一角·和谐版** |
| 西北风 | `xibeifeng_2_n` | 皮肤2·无背景版 | **独处的沙滩一角·无背景版** |
| 西北风 | `xibeifeng_2_n_hx` | 皮肤2·无背景版·和谐版 | **独处的沙滩一角·和谐版·无背景版** |
| 谢菲尔德 | `xiefeierde_2` | 皮肤2 | **二重生活？** |
| 谢菲尔德 | `xiefeierde_3` | 皮肤3 | **小憩一刻** |
| 谢菲尔德 | `xiefeierde_3_n` | 皮肤3·无背景版 | **小憩一刻·无背景版** |
| 谢菲尔德 | `xiefeierde_4` | 皮肤4 | **黑鸦的晚宴** |
| 谢菲尔德 | `xiefeierde_5` | 皮肤5 | **BulletBorne** |
| 谢菲尔德 | `xiefeierde_5_n` | 皮肤5·无背景版 | **BulletBorne·无背景版** |
| 谢菲尔德 | `xiefeierde_6` | 皮肤6 | **神秘决战** |
| 谢菲尔德 | `xiefeierde_6_n` | 皮肤6·无背景版 | **神秘决战·无背景版** |
| 谢菲尔德 | `xiefeierde_idol` | idol | **谢菲尔德(μ兵装)** |
| 谢菲尔德 | `xiefeierde_idolns` | idolns | **谢菲尔德(μ兵装)** |
| 西弗吉尼亚 | `xifujiniya_2` | 皮肤2 | **西弗吉尼亚** ⚠名字塌了(==船名) |
| 西弗吉尼亚 | `xifujiniya_3` | 皮肤3 | **海色摇滚** |
| 西弗吉尼亚 | `xifujiniya_3_hx` | 皮肤3·和谐版 | **海色摇滚·和谐版** |
| 西弗吉尼亚 | `xifujiniya_3_n` | 皮肤3·无背景版 | **海色摇滚·无背景版** |
| 西弗吉尼亚 | `xifujiniya_3_n_hx` | 皮肤3·无背景版·和谐版 | **海色摇滚·和谐版·无背景版** |
| 西弗吉尼亚 | `xifujiniya_g` | G | **西弗吉尼亚.改** |
| 西弗吉尼亚 | `xifujiniya_g_n` | G·无背景版 | **西弗吉尼亚.改·无背景版** |
| 夕立 | `xili_2` | 皮肤2 | **雪仗将军** |
| 夕立 | `xili_3` | 皮肤3 | **肉包杀手** |
| 夕立 | `xili_4` | 皮肤4 | **肉肉之宴！** |
| 夕立 | `xili_5` | 皮肤5 | **美梦环绕圣诞夜** |
| 夕立 | `xili_g` | G | **夕立.改** |
| 夕立 | `xili_g_hx` | G·和谐版 | **夕立.改·和谐版** |
| 夕立 | `xili_g_n` | G·无背景版 | **夕立.改·无背景版** |
| 夕立 | `xili_g_n_hx` | G·无背景版·和谐版 | **夕立.改·和谐版·无背景版** |
| 夕立 | `xili_h` | h | **所罗门的新娘** |
| 西连寺春菜 | `xiliansi_2_tolove` | 皮肤2·tolove | **静谧的谈心之夜** |
| 西连寺春菜 | `xiliansi_2_tolove_n` | 皮肤2·tolove·无背景版 | **静谧的谈心之夜·无背景版** |
| 夕暮 | `ximu_2` | 皮肤2 | **女仆练习生** |
| 夕暮 | `ximu_3` | 皮肤3 | **夕暮春华** |
| 夕暮 | `ximu_4` | 皮肤4 | **盛绽樱华** |
| 夕暮 | `ximu_5` | 皮肤5 | **海边嬉戏时间** |
| 夕暮 | `ximu_5_hx` | 皮肤5·和谐版 | **海边嬉戏时间·和谐版** |
| 夕暮 | `ximu_5_n` | 皮肤5·无背景版 | **海边嬉戏时间·无背景版** |
| 夕暮 | `ximu_5_n_hx` | 皮肤5·无背景版·和谐版 | **海边嬉戏时间·和谐版·无背景版** |
| 夕暮 | `ximu_6` | 皮肤6 | **庆典购物时** |
| 夕暮 | `ximu_6_n` | 皮肤6·无背景版 | **庆典购物时·无背景版** |
| 夕暮 | `ximu_g` | G | **夕暮.改** |
| 西姆斯 | `ximusi_g` | G | **西姆斯.改** |
| 西南风 | `xinanfeng_2` | 皮肤2 | **水手向西南进发！** |
| 西南风 | `xinanfeng_2_n` | 皮肤2·无背景版 | **水手向西南进发！·无背景版** |
| 新奥尔良 | `xinaoerliang_2` | 皮肤2 | **沉醉的干杯之夜** |
| 新奥尔良 | `xinaoerliang_2_hx` | 皮肤2·和谐版 | **沉醉的干杯之夜·和谐版** |
| 新奥尔良 | `xinaoerliang_2_n` | 皮肤2·无背景版 | **沉醉的干杯之夜·无背景版** |
| 新奥尔良 | `xinaoerliang_2_n_hx` | 皮肤2·无背景版·和谐版 | **沉醉的干杯之夜·和谐版·无背景版** |
| 兴登堡 | `xingdengbao_2` | 皮肤2 | **微醺胜负** |
| 兴登堡 | `xingdengbao_2_n` | 皮肤2·无背景版 | **微醺胜负·无背景版** |
| 兴登堡 | `xingdengbao_3` | 皮肤3 | **深阁舞戏** |
| 兴登堡 | `xingdengbao_3_n` | 皮肤3·无背景版 | **深阁舞戏·无背景版** |
| 星座 | `xingzuo_2` | 皮肤2 | **星选之夜** |
| 星座 | `xingzuo_2_n` | 皮肤2·无背景版 | **星选之夜·无背景版** |
| 信浓 | `xinnong_2` | 皮肤2 | **胧月十夜** |
| 信浓 | `xinnong_3` | 皮肤3 | **轰鸣的银轮** |
| 信浓 | `xinnong_3_hx` | 皮肤3·和谐版 | **轰鸣的银轮·和谐版** |
| 信浓 | `xinnong_3_n` | 皮肤3·无背景版 | **轰鸣的银轮·无背景版** |
| 信浓 | `xinnong_3_n_hx` | 皮肤3·无背景版·和谐版 | **轰鸣的银轮·和谐版·无背景版** |
| 信浓 | `xinnong_4` | 皮肤4 | **白沙幽梦** |
| 信浓 | `xinnong_5` | 皮肤5 | **幻梦奇术** |
| 信浓 | `xinnong_5_n` | 皮肤5·无背景版 | **幻梦奇术·无背景版** |
| 信浓 | `xinnong_6` | 皮肤6 | **相融一梦** |
| 新月 | `xinyue_g` | G | **新月.改** |
| 新月 | `xinyue_jp` | jp | **新月** ⚠名字塌了(==船名) |
| 新泽西 | `xinzexi_2` | 皮肤2 | **跃动的舞台时间！** |
| 新泽西 | `xinzexi_2_hx` | 皮肤2·和谐版 | **跃动的舞台时间！·和谐版** |
| 新泽西 | `xinzexi_2_n` | 皮肤2·无背景版 | **跃动的舞台时间！·无背景版** |
| 新泽西 | `xinzexi_2_n_hx` | 皮肤2·无背景版·和谐版 | **跃动的舞台时间！·和谐版·无背景版** |
| 新泽西 | `xinzexi_3` | 皮肤3 | **盛夏的闲暇** |
| 新泽西 | `xinzexi_3_n` | 皮肤3·无背景版 | **盛夏的闲暇·无背景版** |
| 新泽西 | `xinzexi_4` | 皮肤4 | **Let's Dance！月下起舞！** |
| 新泽西 | `xinzexi_4_n` | 皮肤4·无背景版 | **Let's Dance！月下起舞！·无背景版** |
| 新泽西 | `xinzexi_5` | 皮肤5 | **漆黑的超极速前奏** |
| 新泽西 | `xinzexi_5_n` | 皮肤5·无背景版 | **漆黑的超极速前奏·无背景版** |
| 新泽西 | `xinzexi_h` | h | **白雪之仪** |
| 新泽西 | `xinzexi_h_hx` | h·和谐版 | **白雪之仪·和谐版** |
| 凶猛 | `xiongmeng_2` | 皮肤2 | **艺术反叛** |
| 凶猛 | `xiongmeng_2_n` | 皮肤2·无背景版 | **艺术反叛·无背景版** |
| 熊野 | `xiongye_2` | 皮肤2 | **Fancy Wave** |
| 熊野 | `xiongye_3` | 皮肤3 | **激斗☆抽鬼牌派对** |
| 熊野 | `xiongye_3_n` | 皮肤3·无背景版 | **激斗☆抽鬼牌派对·无背景版** |
| 熊野 | `xiongye_4` | 皮肤4 | **一千零一夜之愿** |
| 希佩尔海军上将(μ兵装) | `xipeier_idol` | idol | **希佩尔海军上将(μ兵装)** ⚠名字塌了(==船名) |
| 希佩尔海军上将(μ兵装) | `xipeier_idolns` | idolns | **希佩尔海军上将(μ兵装)** ⚠名字塌了(==船名) |
| 希佩尔海军上将 | `xipeierhaijunshangjiang_3` | 皮肤3 | **阳光下的温泉街** |
| 希佩尔海军上将 | `xipeierhaijunshangjiang_3_n` | 皮肤3·无背景版 | **阳光下的温泉街·无背景版** |
| 希佩尔海军上将 | `xipeierhaijunshangjiang_g` | G | **希佩尔海军上将·改** |
| 希佩尔海军上将 | `xipeierhaijunshangjiang_g_n` | G·无背景版 | **希佩尔海军上将·改·无背景版** |
| 夕烧 | `xishao_2` | 皮肤2 | **蓝天碧海** |
| 夕烧 | `xishao_2_n` | 皮肤2·无背景版 | **蓝天碧海·无背景版** |
| 休斯敦 | `xiusidunii_2` | 皮肤2 | **新晋女仆已就绪** |
| 休斯敦 | `xiusidunii_2_n` | 皮肤2·无背景版 | **新晋女仆已就绪·无背景版** |
| 休斯敦 | `xiusidunii_n` | 无背景版 | **休斯敦II·无背景版** |
| 吸血鬼 | `xixuegui_2` | 皮肤2 | **春之风** |
| 吸血鬼 | `xixuegui_3` | 皮肤3 | **白衣小恶魔** |
| 吸血鬼 | `xixuegui_4` | 皮肤4 | **夜姬的正装?** |
| 吸血鬼 | `xixuegui_5` | 皮肤5 | **偶像小恶魔** |
| 吸血鬼 | `xixuegui_5_n` | 皮肤5·无背景版 | **偶像小恶魔·无背景版** |
| 吸血鬼 | `xixuegui_6` | 皮肤6 | **错乱的节日之宴** |
| 吸血鬼 | `xixuegui_6_n` | 皮肤6·无背景版 | **错乱的节日之宴·无背景版** |
| 吸血鬼 | `xixuegui_h` | h | **以罗伊的赐福** |
| 西雅图 | `xiyatu_2` | 皮肤2 | **绚烂的盛宴** |
| 西雅图 | `xiyatu_3` | 皮肤3 | **圣诞派对准备中！** |
| 西雅图 | `xiyatu_4` | 皮肤4 | **Sunfish Spell！** |
| 夕张 | `xizhang_g` | G | **夕张.改** |
| 雪不归 | `xuebugui_2` | 皮肤2 | **落日魔女** |
| 雪不归 | `xuebugui_2_n` | 皮肤2·无背景版 | **落日魔女·无背景版** |
| 雪风 | `xuefeng_2` | 皮肤2 | **秋千上的雪风大人** |
| 雪风 | `xuefeng_3` | 皮肤3 | **冬之雪风** |
| 雪风 | `xuefeng_h` | h | **春日的暖风** |
| 雪泉 | `xuequan_2` | 皮肤2 | **午后时光** |
| 雪泉 | `xuequan_2_n` | 皮肤2·无背景版 | **午后时光·无背景版** |
| 絮弗伦 | `xufulun_2` | 皮肤2 | **心跳加速Accident** |
| 絮弗伦 | `xufulun_2_n` | 皮肤2·无背景版 | **心跳加速Accident·无背景版** |
| 絮弗伦 | `xufulun_3` | 皮肤3 | **华美无双** |
| 絮弗伦 | `xufulun_3_n` | 皮肤3·无背景版 | **华美无双·无背景版** |
| 絮库夫 | `xukufu_2` | 皮肤2 | **购物时光！** |
| 絮库夫 | `xukufu_3` | 皮肤3 | **Loisirs balnéaires** |
| 絮库夫 | `xukufu_3_hx` | 皮肤3·和谐版 | **Loisirs balnéaires·和谐版** |
| 亚德 | `yade_2` | 皮肤2 | **清凉一夏** |
| 亚德 | `yade_2_n` | 皮肤2·无背景版 | **清凉一夏·无背景版** |
| 亚德 | `yade_3` | 皮肤3 | **魔女的心跳魔法** |
| 亚德 | `yade_3_hx` | 皮肤3·和谐版 | **魔女的心跳魔法·和谐版** |
| 亚德 | `yade_3_n` | 皮肤3·无背景版 | **魔女的心跳魔法·无背景版** |
| 亚德 | `yade_3_n_hx` | 皮肤3·无背景版·和谐版 | **魔女的心跳魔法·和谐版·无背景版** |
| 亚尔薇特 | `yaerweite_2` | 皮肤2 | **灼热中的秘密** |
| 亚尔薇特 | `yaerweite_2_n` | 皮肤2·无背景版 | **灼热中的秘密·无背景版** |
| 亚利桑那 | `yalisangna_2` | 皮肤2 | **异域的舞姬** |
| 亚利桑那 | `yalisangna_2_hx` | 皮肤2·和谐版 | **异域的舞姬·和谐版** |
| 亚利桑那 | `yalisangna_2_n` | 皮肤2·无背景版 | **异域的舞姬·无背景版** |
| 亚利桑那 | `yalisangna_2_n_hx` | 皮肤2·无背景版·和谐版 | **异域的舞姬·和谐版·无背景版** |
| 牙买加 | `yamaijia_2` | 皮肤2 | **地下行者** |
| 牙买加 | `yamaijia_3` | 皮肤3 | **Highway·Star** |
| 双海亚美 | `yamei_2` | 皮肤2 | **大太鼓、夏之华** |
| 双海亚美 | `yamei_2_n` | 皮肤2·无背景版 | **大太鼓、夏之华·无背景版** |
| 焰 | `yan_2` | 皮肤2 | **钓鱼大师** |
| 焰 | `yan_2_n` | 皮肤2·无背景版 | **钓鱼大师·无背景版** |
| 阳炎 | `yangyan_2` | 皮肤2 | **南瓜与万圣夜** |
| 阳炎 | `yangyan_g` | G | **阳炎.改** |
| 雅努斯 | `yanusi_3` | 皮肤3 | **万圣喵喵惊悚夜** |
| 雅努斯 | `yanusi_3_n` | 皮肤3·无背景版 | **万圣喵喵惊悚夜·无背景版** |
| 雅努斯 | `yanusi_4` | 皮肤4 | **踌躇的换衣时间** |
| 雅努斯 | `yanusi_4_hx` | 皮肤4·和谐版 | **踌躇的换衣时间·和谐版** |
| 雅努斯 | `yanusi_4_n` | 皮肤4·无背景版 | **踌躇的换衣时间·无背景版** |
| 雅努斯 | `yanusi_4_n_hx` | 皮肤4·无背景版·和谐版 | **踌躇的换衣时间·和谐版·无背景版** |
| 雅努斯 | `yanusi_5` | 皮肤5 | **夜中的明灯** |
| 雅努斯 | `yanusi_5_n` | 皮肤5·无背景版 | **夜中的明灯·无背景版** |
| 雅努斯 | `yanusi_6` | 皮肤6 | **台球桌上的猫与“兔”** |
| 雅努斯 | `yanusi_6_n` | 皮肤6·无背景版 | **台球桌上的猫与“兔”·无背景版** |
| 雅努斯 | `yanusi_7` | 皮肤7 | **云端的水光** |
| 雅努斯 | `yanusi_7_hx` | 皮肤7·和谐版 | **云端的水光·和谐版** |
| 雅努斯 | `yanusi_7_n` | 皮肤7·无背景版 | **云端的水光·无背景版** |
| 雅努斯 | `yanusi_7_n_hx` | 皮肤7·无背景版·和谐版 | **云端的水光·和谐版·无背景版** |
| 雅努斯 | `yanusi_h` | h | **曙色誓言** |
| 雅努斯 | `yanusi_h_n` | h·无背景版 | **曙色誓言·无背景版** |
| 厌战 | `yanzhan_2` | 皮肤2 | **战士的圣诞任务** |
| 厌战 | `yanzhan_3` | 皮肤3 | **Under Pleasure** |
| 厌战 | `yanzhan_4` | 皮肤4 | **西瓜两断** |
| 厌战 | `yanzhan_4_n` | 皮肤4·无背景版 | **西瓜两断·无背景版** |
| 厌战 | `yanzhan_g` | G | **厌战.改** |
| 易北 | `yibei_2` | 皮肤2 | **错失的高光时刻？** |
| 易北 | `yibei_2_n` | 皮肤2·无背景版 | **错失的高光时刻？·无背景版** |
| 易北 | `yibei_3` | 皮肤3 | **清纯的“反派小姐”？** |
| 伊吹 | `yichui_2` | 皮肤2 | **永梦的青女** |
| 伊吹 | `yichui_3` | 皮肤3 | **轻扬的风花** |
| 伊吹 | `yichui_4` | 皮肤4 | **新桃换旧符** |
| 伊吹 | `yichui_5` | 皮肤5 | **恬静无为** |
| 伊吹 | `yichui_7` | 皮肤7 | **夏日恋迹** |
| 伊吹 | `yichui_7_n` | 皮肤7·无背景版 | **夏日恋迹·无背景版** |
| 伊卡洛斯 | `yikaluosi_2` | 皮肤2 | **海底探险摄影会** |
| 伊卡洛斯 | `yikaluosi_2_hx` | 皮肤2·和谐版 | **海底探险摄影会·和谐版** |
| 伊卡洛斯 | `yikaluosi_2_n` | 皮肤2·无背景版 | **海底探险摄影会·无背景版** |
| 伊卡洛斯 | `yikaluosi_2_n_hx` | 皮肤2·无背景版·和谐版 | **海底探险摄影会·和谐版·无背景版** |
| 伊卡洛斯 | `yikaluosi_3` | 皮肤3 | **港区医院体验周?** |
| 伊卡洛斯 | `yikaluosi_4` | 皮肤4 | **女仆与猫与下午茶** |
| 伊卡洛斯 | `yikaluosi_4_n` | 皮肤4·无背景版 | **女仆与猫与下午茶·无背景版** |
| 伊丽莎白女王 | `yilishabai_2` | 皮肤2 | **女王的舞踏会** |
| 伊丽莎白女王 | `yilishabai_3` | 皮肤3 | **A Night At The Stage** |
| 伊丽莎白女王 | `yilishabai_3_n` | 皮肤3·无背景版 | **A Night At The Stage·无背景版** |
| 伊丽莎白女王 | `yilishabai_4` | 皮肤4 | **女王的学园命令** |
| 伊丽莎白女王 | `yilishabai_4_n` | 皮肤4·无背景版 | **女王的学园命令·无背景版** |
| 伊丽莎白女王 | `yilishabai_5` | 皮肤5 | **皇家进宝** |
| 伊丽莎白女王 | `yilishabai_5_n` | 皮肤5·无背景版 | **皇家进宝·无背景版** |
| 伊丽莎白女王 | `yilishabai_6` | 皮肤6 | **Maid·My·Highness** |
| 伊丽莎白女王 | `yilishabai_6_n` | 皮肤6·无背景版 | **Maid·My·Highness·无背景版** |
| 伊丽莎白女王 | `yilishabai_7` | 皮肤7 | **Seaside Orders** |
| 伊丽莎白女王 | `yilishabai_alter` | alter | **伊丽莎白女王·META ** |
| 伊丽莎白女王 | `yilishabai_alter_n` | alter·无背景版 | **伊丽莎白女王·META ·无背景版** |
| 伊莉丝 | `yilisi_2_doa` | 皮肤2·doa | **某位女神的午后** |
| 伊莉丝 | `yilisi_2_doa_n` | 皮肤2·doa·无背景版 | **某位女神的午后·无背景版** |
| 伊莉丝 | `yilisi_doa` | doa | **伊莉丝** ⚠名字塌了(==船名) |
| 印第安纳 | `yindianna_2` | 皮肤2 | **酒馆大劫案** |
| 印第安纳 | `yindianna_2_n` | 皮肤2·无背景版 | **酒馆大劫案·无背景版** |
| 鹰 | `ying_2` | 皮肤2 | **实习医生伊格** |
| 鹰 | `ying_2_hx` | 皮肤2·和谐版 | **实习医生伊格·和谐版** |
| 英格拉罕 | `yinggelahan_2` | 皮肤2 | **饮品研究员？** |
| 萤火虫 | `yinghuochong_2` | 皮肤2 | **铁面无私萤火虫！** |
| 萤火虫 | `yinghuochong_2_n` | 皮肤2·无背景版 | **铁面无私萤火虫！·无背景版** |
| 萤火虫 | `yinghuochong_g` | G | **萤火虫.改** |
| 萤火虫 | `yinghuochong_g_n` | G·无背景版 | **萤火虫.改·无背景版** |
| 应瑞 | `yingrui_2` | 皮肤2 | **寒松雪暖** |
| 应瑞 | `yingrui_2_n` | 皮肤2·无背景版 | **寒松雪暖·无背景版** |
| 应瑞 | `yingrui_3` | 皮肤3 | **松戏梅·其上** |
| 应瑞 | `yingrui_3_n` | 皮肤3·无背景版 | **松戏梅·其上·无背景版** |
| 应瑞 | `yingrui_4` | 皮肤4 | **碧波清夏** |
| 应瑞 | `yingrui_4_n` | 皮肤4·无背景版 | **碧波清夏·无背景版** |
| 应瑞 | `yingrui_g` | G | **应瑞·改** |
| 应瑞 | `yingrui_g_n` | G·无背景版 | **应瑞·改·无背景版** |
| 鹦鹉螺 | `yingwuluo_2` | 皮肤2 | **黑兔休息中** |
| 鹦鹉螺 | `yingwuluo_2_n` | 皮肤2·无背景版 | **黑兔休息中·无背景版** |
| 鹦鹉螺 | `yingwuluo_3` | 皮肤3 | **闪耀的水中之花** |
| 鹦鹉螺 | `yingwuluo_3_n` | 皮肤3·无背景版 | **闪耀的水中之花·无背景版** |
| 英仙座 | `yingxianzuo_2` | 皮肤2 | **生疏的执勤时间** |
| 英仙座 | `yingxianzuo_2_n` | 皮肤2·无背景版 | **生疏的执勤时间·无背景版** |
| 英仙座 | `yingxianzuo_3` | 皮肤3 | **慵懒的春光** |
| 英仙座 | `yingxianzuo_3_n` | 皮肤3·无背景版 | **慵懒的春光·无背景版** |
| 英雄 | `yingxiong_2` | 皮肤2 | **邻座的小恶魔** |
| 英雄 | `yingxiong_2_n` | 皮肤2·无背景版 | **邻座的小恶魔·无背景版** |
| 英勇 | `yingyong_2` | 皮肤2 | **小护士的时间** |
| 英勇 | `yingyong_3` | 皮肤3 | **英勇女王陛下？** |
| 英勇 | `yingyong_3_n` | 皮肤3·无背景版 | **英勇女王陛下？·无背景版** |
| 伊势 | `yishi_g` | G | **伊势.改** |
| 逸仙 | `yixian_2` | 皮肤2 | **膏发凝脂** |
| 逸仙 | `yixian_2_n` | 皮肤2·无背景版 | **膏发凝脂·无背景版** |
| 逸仙 | `yixian_3` | 皮肤3 | **清茶氤氲** |
| 逸仙 | `yixian_3_n` | 皮肤3·无背景版 | **清茶氤氲·无背景版** |
| 逸仙 | `yixian_4` | 皮肤4 | **细浪扶风** |
| 逸仙 | `yixian_4_n` | 皮肤4·无背景版 | **细浪扶风·无背景版** |
| 逸仙 | `yixian_g` | G | **逸仙.改** |
| 逸仙 | `yixian_h` | h | **凤冠霞帔** |
| 逸仙 | `yixian_memory` | memory | **逸仙** ⚠名字塌了(==船名) |
| 水濑伊织 | `yizhi_2` | 皮肤2 | **黄昏的小秘密** |
| 水濑伊织 | `yizhi_2_n` | 皮肤2·无背景版 | **黄昏的小秘密·无背景版** |
| 勇敢 | `yonggan_g` | G | **勇敢·改** |
| 勇敢 | `yonggan_g_n` | G·无背景版 | **勇敢·改·无背景版** |
| 勇气 | `yongqi_2` | 皮肤2 | **急送的心意** |
| 勇气 | `yongqi_2_n` | 皮肤2·无背景版 | **急送的心意·无背景版** |
| 由良 | `youliang_2` | 皮肤2 | **二重吸引?** |
| 有明 | `youming_2` | 皮肤2 | **四季团圆** |
| 有明 | `youming_2_n` | 皮肤2·无背景版 | **四季团圆·无背景版** |
| 有明 | `youming_g` | G | **有明.改** |
| 优米雅·利斯菲尔德 | `youmiya_2` | 皮肤2 | **我们家的甜点师** |
| 优米雅·利斯菲尔德 | `youmiya_2_n` | 皮肤2·无背景版 | **我们家的甜点师·无背景版** |
| 优米雅·利斯菲尔德 | `youmiya_wjz` | wjz | **优米雅·利斯菲尔德** ⚠名字塌了(==船名) |
| 怨仇 | `yuanchou_2` | 皮肤2 | **办公室的“意外”** |
| 怨仇 | `yuanchou_2_hx` | 皮肤2·和谐版 | **办公室的“意外”·和谐版** |
| 怨仇 | `yuanchou_2_n` | 皮肤2·无背景版 | **办公室的“意外”·无背景版** |
| 怨仇 | `yuanchou_2_n_hx` | 皮肤2·无背景版·和谐版 | **办公室的“意外”·和谐版·无背景版** |
| 怨仇 | `yuanchou_3` | 皮肤3 | **杯盏盈芳华** |
| 怨仇 | `yuanchou_3_n` | 皮肤3·无背景版 | **杯盏盈芳华·无背景版** |
| 约翰·罗杰斯 | `yuehanluojiesi_2` | 皮肤2 | **赛车女郎休憩中** |
| 约翰·罗杰斯 | `yuehanluojiesi_2_hx` | 皮肤2·和谐版 | **赛车女郎休憩中·和谐版** |
| 约翰·罗杰斯 | `yuehanluojiesi_2_n` | 皮肤2·无背景版 | **赛车女郎休憩中·无背景版** |
| 约翰·罗杰斯 | `yuehanluojiesi_2_n_hx` | 皮肤2·无背景版·和谐版 | **赛车女郎休憩中·和谐版·无背景版** |
| 约克 | `yueke_2` | 皮肤2 | **真理探寻者/truth seeker** |
| 约克 | `yueke_3` | 皮肤3 | **碧波的召唤者** |
| 约克 | `yueke_g` | G | **约克.改** |
| 约克 | `yueke_ger` | ger | **约克** ⚠名字塌了(==船名) |
| 约克 | `yueke_ger_2` | ger·皮肤2 | **朱月的破坏者** |
| 约克 | `yueke_ger_2_hx` | ger·皮肤2·和谐版 | **朱月的破坏者·和谐版** |
| 约克 | `yueke_ger_3` | ger·皮肤3 | **相伴于泳池之夜** |
| 约克 | `yueke_ger_3_n` | ger·皮肤3·无背景版 | **相伴于泳池之夜·无背景版** |
| 约克 | `yueke_ger_4` | ger·皮肤4 | **幻夜绮舞** |
| 约克 | `yueke_ger_4_n` | ger·皮肤4·无背景版 | **幻夜绮舞·无背景版** |
| 约克 | `yueke_h` | h | **莹白誓约** |
| 约克 | `yueke_h_n` | h·无背景版 | **莹白誓约·无背景版** |
| 约克城 | `yuekecheng_2` | 皮肤2 | **优雅与朦胧之夜** |
| 约克城 | `yuekecheng_3` | 皮肤3 | **圣者之翼** |
| 约克城 | `yuekecheng_3_n` | 皮肤3·无背景版 | **圣者之翼·无背景版** |
| 约克城 | `yuekecheng_alter` | alter | **约克城·META** |
| 约克城 | `yuekecheng_alter_n` | alter·无背景版 | **约克城·META·无背景版** |
| 约克城 | `yuekecheng_h` | h | **微风拂煦的未来** |
| 约克城 | `yuekecheng_h_n` | h·无背景版 | **微风拂煦的未来·无背景版** |
| 约克城 | `yuekechengii_2` | 皮肤2 | **白昼美人鱼** |
| 约克城 | `yuekechengii_2_n` | 皮肤2·无背景版 | **白昼美人鱼·无背景版** |
| 约克城 | `yuekechengii_3` | 皮肤3 | **交错的温柔时光** |
| 约克城 | `yuekechengii_3_n` | 皮肤3·无背景版 | **交错的温柔时光·无背景版** |
| 约克城 | `yuekechengii_4` | 皮肤4 | **交错的温柔时光** |
| 约克城 | `yuekechengii_4_n` | 皮肤4·无背景版 | **交错的温柔时光·无背景版** |
| 约克城 | `yuekechengii_n` | 无背景版 | **约克城II·无背景版** |
| 约克公爵 | `yuekegongjue_2` | 皮肤2 | **盛誉的光荣方程** |
| 约克公爵 | `yuekegongjue_3` | 皮肤3 | **永夜的卡罗拉** |
| 约克公爵 | `yuekegongjue_4` | 皮肤4 | **渊智的指路人** |
| 约克公爵 | `yuekegongjue_4_n` | 皮肤4·无背景版 | **渊智的指路人·无背景版** |
| 羽黑 | `yuhei_2` | 皮肤2 | **因祸得福？** |
| 羽黑 | `yuhei_3` | 皮肤3 | **误入“笼”中** |
| 云龙 | `yunlong_2` | 皮肤2 | **溶于重重夜色** |
| 云龙 | `yunlong_2_hx` | 皮肤2·和谐版 | **溶于重重夜色·和谐版** |
| 云龙 | `yunlong_2_n` | 皮肤2·无背景版 | **溶于重重夜色·无背景版** |
| 云龙 | `yunlong_2_n_hx` | 皮肤2·无背景版·和谐版 | **溶于重重夜色·和谐版·无背景版** |
| 云龙 | `yunlong_3` | 皮肤3 | **溶于重重夜色** |
| 云龙 | `yunlong_3_n` | 皮肤3·无背景版 | **溶于重重夜色·无背景版** |
| 云仙 | `yunxian_2` | 皮肤2 | **嬉水碧海** |
| 云仙 | `yunxian_2_n` | 皮肤2·无背景版 | **嬉水碧海·无背景版** |
| 云仙 | `yunxian_3` | 皮肤3 | **万船集怀** |
| 云仙 | `yunxian_3_hx` | 皮肤3·和谐版 | **万船集怀·和谐版** |
| 云仙 | `yunxian_3_n` | 皮肤3·无背景版 | **万船集怀·无背景版** |
| 云仙 | `yunxian_3_n_hx` | 皮肤3·无背景版·和谐版 | **万船集怀·和谐版·无背景版** |
| 云仙 | `yunxian_younv` | younv | **小云仙** |
| 云仙 | `yunxian_younv_n` | younv·无背景版 | **小云仙·无背景版** |
| Z1 | `z1_2` | 皮肤2 | **“叛逆”的优等生** |
| Z1 | `z1_g` | G | **Z1.改** |
| Z11 | `z11_2` | 皮肤2 | **求助时间到！** |
| Z11 | `z11_2_n` | 皮肤2·无背景版 | **求助时间到！·无背景版** |
| Z11 | `z11_3` | 皮肤3 | **鼓起勇气的诊断时间** |
| Z11 | `z11_3_n` | 皮肤3·无背景版 | **鼓起勇气的诊断时间·无背景版** |
| Z13 | `z13_2` | 皮肤2 | **战略性约会进行时 ** |
| Z13 | `z13_2_n` | 皮肤2·无背景版 | **战略性约会进行时 ·无背景版** |
| Z14 | `z14_2` | 皮肤2 | **夏日、晴空、意外迷路？！** |
| Z14 | `z14_2_n` | 皮肤2·无背景版 | **夏日、晴空、意外迷路？！·无背景版** |
| Z15 | `z15_2` | 皮肤2 | **水上的心跳“意外”** |
| Z15 | `z15_2_n` | 皮肤2·无背景版 | **水上的心跳“意外”·无背景版** |
| Z16 | `z16_2` | 皮肤2 | **必胜全垒打！** |
| Z16 | `z16_2_n` | 皮肤2·无背景版 | **必胜全垒打！·无背景版** |
| Z2 | `z2_2` | 皮肤2 | **异色的日常风景** |
| Z2 | `z2_2_n` | 皮肤2·无背景版 | **异色的日常风景·无背景版** |
| Z2 | `z2_3` | 皮肤3 | **夜色锦鲤** |
| Z23 | `z23_10` | 皮肤10 | **强化失败？！** |
| Z23 | `z23_10_hx` | 皮肤10·和谐版 | **强化失败？！·和谐版** |
| Z23 | `z23_10_n` | 皮肤10·无背景版 | **强化失败？！·无背景版** |
| Z23 | `z23_10_n_hx` | 皮肤10·无背景版·和谐版 | **强化失败？！·和谐版·无背景版** |
| Z23 | `z23_11` | 皮肤11 | **薯条，以及笑容！** |
| Z23 | `z23_12` | 皮肤12 | **舞会与黑蔷薇** |
| Z23 | `z23_12_n` | 皮肤12·无背景版 | **舞会与黑蔷薇·无背景版** |
| Z23 | `z23_13` | 皮肤13 | **案上墨戏** |
| Z23 | `z23_13_n` | 皮肤13·无背景版 | **案上墨戏·无背景版** |
| Z23 | `z23_2` | 皮肤2 | **哲学讲师** |
| Z23 | `z23_3` | 皮肤3 | **宴会上的优等生** |
| Z23 | `z23_4` | 皮肤4 | **标准笑容？** |
| Z23 | `z23_5` | 皮肤5 | **正经偶像·经纪人担当？** |
| Z23 | `z23_6` | 皮肤6 | **书架边的“风景”？** |
| Z23 | `z23_7` | 皮肤7 | **非正式沙滩排球赛** |
| Z23 | `z23_7_n` | 皮肤7·无背景版 | **非正式沙滩排球赛·无背景版** |
| Z23 | `z23_8` | 皮肤8 | **新设基地・茶店体验** |
| Z23 | `z23_8_n` | 皮肤8·无背景版 | **新设基地・茶店体验·无背景版** |
| Z23 | `z23_9` | 皮肤9 | **秘密的起居室** |
| Z23 | `z23_9_n` | 皮肤9·无背景版 | **秘密的起居室·无背景版** |
| Z23 | `z23_g` | G | **Z23.改** |
| Z23 | `z23_h` | h | **黑曜的嫁衣** |
| Z24 | `z24_2` | 皮肤2 | **「魔王」的祝祭** |
| Z24 | `z24_3` | 皮肤3 | **球场上的小恶魔** |
| Z24 | `z24_3_hx` | 皮肤3·和谐版 | **球场上的小恶魔·和谐版** |
| Z24 | `z24_3_n` | 皮肤3·无背景版 | **球场上的小恶魔·无背景版** |
| Z24 | `z24_3_n_hx` | 皮肤3·无背景版·和谐版 | **球场上的小恶魔·和谐版·无背景版** |
| Z24 | `z24_4` | 皮肤4 | **夜色下的赤红之舞** |
| Z24 | `z24_4_n` | 皮肤4·无背景版 | **夜色下的赤红之舞·无背景版** |
| Z25 | `z25_2` | 皮肤2 | **暑夏的海风** |
| Z26 | `z26_2` | 皮肤2 | **友好的分享时间** |
| Z26 | `z26_2_n` | 皮肤2·无背景版 | **友好的分享时间·无背景版** |
| Z28 | `z28_3` | 皮肤3 | **新年大杂烩！** |
| Z28 | `z28_4` | 皮肤4 | **森林中的派对** |
| Z35 | `z35_2` | 皮肤2 | **projekt Kirschblüte** |
| Z35 | `z35_3` | 皮肤3 | **店里的可爱天使** |
| Z35 | `z35_3_n` | 皮肤3·无背景版 | **店里的可爱天使·无背景版** |
| Z35 | `z35_4` | 皮肤4 | **由爱延展的天空** |
| Z35 | `z35_4_n` | 皮肤4·无背景版 | **由爱延展的天空·无背景版** |
| Z43 | `z43_2` | 皮肤2 | **两个人的秘密基地** |
| Z43 | `z43_2_n` | 皮肤2·无背景版 | **两个人的秘密基地·无背景版** |
| Z46 | `z46_2` | 皮肤2 | **夏之初体验** |
| Z46 | `z46_3` | 皮肤3 | **少女的借物竞赛** |
| Z46 | `z46_4` | 皮肤4 | **未知的闪亮舞台** |
| Z46 | `z46_4_n` | 皮肤4·无背景版 | **未知的闪亮舞台·无背景版** |
| Z46 | `z46_5` | 皮肤5 | **剪纸幻梦** |
| Z46 | `z46_6` | 皮肤6 | **无尽的尘埃之战** |
| Z46 | `z46_6_n` | 皮肤6·无背景版 | **无尽的尘埃之战·无背景版** |
| Z46 | `z46_7` | 皮肤7 | **哈梅林的吟游诗人** |
| Z46 | `z46_7_n` | 皮肤7·无背景版 | **哈梅林的吟游诗人·无背景版** |
| Z47 | `z47_2` | 皮肤2 | **跷跷板上的嬉戏时间** |
| Z47 | `z47_3` | 皮肤3 | **击球手★全垒打** |
| Z47 | `z47_3_n` | 皮肤3·无背景版 | **击球手★全垒打·无背景版** |
| Z52 | `z52_2` | 皮肤2 | **疾驰而来的兔小姐！** |
| Z52 | `z52_2_n` | 皮肤2·无背景版 | **疾驰而来的兔小姐！·无背景版** |
| Z52 | `z52_3` | 皮肤3 | **Sprintender Sommer！** |
| Z52 | `z52_3_n` | 皮肤3·无背景版 | **Sprintender Sommer！·无背景版** |
| Z9 | `z9_2` | 皮肤2 | **甜蜜饮品宣传中！** |
| Z9 | `z9_2_n` | 皮肤2·无背景版 | **甜蜜饮品宣传中！·无背景版** |
| 女灶神 | `zaoshen_2` | 皮肤2 | **清凉的赫斯提亚** |
| 曾克海军上将 | `zengkehaijunshangjiang_2` | 皮肤2 | **心动审讯练习中 ** |
| 曾克海军上将 | `zengkehaijunshangjiang_2_n` | 皮肤2·无背景版 | **心动审讯练习中 ·无背景版** |
| 扎拉 | `zhala_2` | 皮肤2 | **泳池边的“偶遇”** |
| 彰武 | `zhangwu_2` | 皮肤2 | **一枝春欲放** |
| 彰武 | `zhangwu_2_n` | 皮肤2·无背景版 | **一枝春欲放·无背景版** |
| 朝潮 | `zhaochao_2` | 皮肤2 | **樱花下的转校生** |
| 朝潮 | `zhaochao_4` | 皮肤4 | **雪朝与铃** |
| 朝潮 | `zhaochao_4_n` | 皮肤4·无背景版 | **雪朝与铃·无背景版** |
| 朝潮 | `zhaochao_5` | 皮肤5 | **轻舞云裳** |
| 朝潮 | `zhaochao_5_n` | 皮肤5·无背景版 | **轻舞云裳·无背景版** |
| 肇和 | `zhaohe_2` | 皮肤2 | **花枝映梅** |
| 肇和 | `zhaohe_2_n` | 皮肤2·无背景版 | **花枝映梅·无背景版** |
| 肇和 | `zhaohe_3` | 皮肤3 | **松戏梅·其下** |
| 肇和 | `zhaohe_3_n` | 皮肤3·无背景版 | **松戏梅·其下·无背景版** |
| 肇和 | `zhaohe_4` | 皮肤4 | **碧波耀阳** |
| 肇和 | `zhaohe_4_hx` | 皮肤4·和谐版 | **碧波耀阳·和谐版** |
| 肇和 | `zhaohe_4_n` | 皮肤4·无背景版 | **碧波耀阳·无背景版** |
| 肇和 | `zhaohe_4_n_hx` | 皮肤4·无背景版·和谐版 | **碧波耀阳·和谐版·无背景版** |
| 肇和 | `zhaohe_g` | G | **肇和·改** |
| 肇和 | `zhaohe_g_n` | G·无背景版 | **肇和·改·无背景版** |
| 朝凪 | `zhaozhi_2` | 皮肤2 | **午间的风平浪静** |
| 朝凪 | `zhaozhi_2_n` | 皮肤2·无背景版 | **午间的风平浪静·无背景版** |
| 镇海 | `zhenhai_2` | 皮肤2 | **奇奢华苑** |
| 镇海 | `zhenhai_2_hx` | 皮肤2·和谐版 | **奇奢华苑·和谐版** |
| 镇海 | `zhenhai_2_n` | 皮肤2·无背景版 | **奇奢华苑·无背景版** |
| 镇海 | `zhenhai_2_n_hx` | 皮肤2·无背景版·和谐版 | **奇奢华苑·和谐版·无背景版** |
| 镇海 | `zhenhai_3` | 皮肤3 | **潋滟水色** |
| 镇海 | `zhenhai_4` | 皮肤4 | **翠园佳绣** |
| 镇海 | `zhenhai_4_n` | 皮肤4·无背景版 | **翠园佳绣·无背景版** |
| 镇海 | `zhenhai_g` | G | **镇海.改** |
| 镇海 | `zhenhai_g_n` | G·无背景版 | **镇海.改·无背景版** |
| 镇海 | `zhenhai_h` | h | **锦帐良宵** |
| 镇海 | `zhenhai_h_n` | h·无背景版 | **锦帐良宵·无背景版** |
| 双海真美 | `zhenmei_2` | 皮肤2 | **性感嘉年华！** |
| 双海真美 | `zhenmei_2_n` | 皮肤2·无背景版 | **性感嘉年华！·无背景版** |
| 榛名 | `zhenming_2` | 皮肤2 | **授课前的自由时间** |
| 榛名 | `zhenming_3` | 皮肤3 | **绯红Innocence** |
| 榛名 | `zhenming_3_n` | 皮肤3·无背景版 | **绯红Innocence·无背景版** |
| 榛名 | `zhenming_4` | 皮肤4 | **雅致莲华** |
| 珍珠号 | `zhenzhuhao_2` | 皮肤2 | **魔堡中的堕天使** |
| 珍珠号 | `zhenzhuhao_2_hx` | 皮肤2·和谐版 | **魔堡中的堕天使·和谐版** |
| 珍珠号 | `zhenzhuhao_2_n` | 皮肤2·无背景版 | **魔堡中的堕天使·无背景版** |
| 珍珠号 | `zhenzhuhao_2_n_hx` | 皮肤2·无背景版·和谐版 | **魔堡中的堕天使·和谐版·无背景版** |
| 鸢一折纸 | `zhezhi_2` | 皮肤2 | **司掌魅惑的精灵** |
| 鸢一折纸 | `zhezhi_2_n` | 皮肤2·无背景版 | **司掌魅惑的精灵·无背景版** |
| 凪咲 | `zhixiao_2_doa` | 皮肤2·doa | **蓝天好心情** |
| 凪咲 | `zhixiao_doa` | doa | **凪咲** ⚠名字塌了(==船名) |
| 凪咲 | `zhixiao_doa_wjz` | doa·wjz | **凪咲** ⚠名字塌了(==船名) |
| 重剑 | `zhongjian_2` | 皮肤2 | **角落的小小骑士** |
| 重剑 | `zhongjian_2_n` | 皮肤2·无背景版 | **角落的小小骑士·无背景版** |
| 追风 | `zhuifeng_2` | 皮肤2 | **纸砚墨梅** |
| 追风 | `zhuifeng_3` | 皮肤3 | **夏日的全力一击** |
| 追风 | `zhuifeng_3_n` | 皮肤3·无背景版 | **夏日的全力一击·无背景版** |
| 追赶者 | `zhuiganzhe_2` | 皮肤2 | **东煌之道** |
| 追赶者 | `zhuiganzhe_3` | 皮肤3 | **Gamer Style** |
| 筑摩 | `zhumo_2` | 皮肤2 | **对局上的洞察者** |
| 筑摩 | `zhumo_2_hx` | 皮肤2·和谐版 | **对局上的洞察者·和谐版** |
| 筑摩 | `zhumo_2_n` | 皮肤2·无背景版 | **对局上的洞察者·无背景版** |
| 筑摩 | `zhumo_2_n_hx` | 皮肤2·无背景版·和谐版 | **对局上的洞察者·和谐版·无背景版** |
| 朱诺 | `zhunuo_2` | 皮肤2 | **白鸟花园之约** |
| 朱诺 | `zhunuo_2_n` | 皮肤2·无背景版 | **白鸟花园之约·无背景版** |
| 朱诺 | `zhunuo_g` | G | **朱诺.改** |
| 朱诺 | `zhunuo_g_n` | G·无背景版 | **朱诺.改·无背景版** |
| 朱塞佩·加里波第 | `zhusaipei_2` | 皮肤2 | **纯黑羽翼的雅致** |
| 朱塞佩·加里波第 | `zhusaipei_2_n` | 皮肤2·无背景版 | **纯黑羽翼的雅致·无背景版** |
| 筑紫 | `zhuzi_2_doa` | 皮肤2·doa | **Dream Machine** |
| 筑紫 | `zhuzi_2_doa_n` | 皮肤2·doa·无背景版 | **Dream Machine·无背景版** |
| 筑紫 | `zhuzi_doa` | doa | **筑紫** ⚠名字塌了(==船名) |
| 三浦 梓 | `zi_2` | 皮肤2 | **盛夏的休憩之所** |
| 三浦 梓 | `zi_2_shanluan` | 皮肤2·shanluan | **被困公主的忧郁** |
| 三浦 梓 | `zi_2_shanluan_n` | 皮肤2·shanluan·无背景版 | **被困公主的忧郁·无背景版** |
| 足柄 | `zubing_2` | 皮肤2 | **幕间小憩** |
| 足柄 | `zubing_3` | 皮肤3 | **缤纷之夏** |
| 足柄 | `zubing_3_n` | 皮肤3·无背景版 | **缤纷之夏·无背景版** |
| 最上 | `zuishang_g` | G | **最上.改** |
| 佐治亚 | `zuozhiya_2` | 皮肤2 | **南方的黑珍珠** |
| 佐治亚 | `zuozhiya_4` | 皮肤4 | **Lanier Swan** |
| 佐治亚 | `zuozhiya_6` | 皮肤6 | **雅色彩华** |

## 三、换不了的 78 条（表里查无该行，保留现标签）

| 船 | 皮肤键 | 现标签 |
|---|---|---|
| 绊爱 | `aijiang_rank` | rank |
| 斑鸠 | `banjiu_ex` | ex |
| 斑鸠 | `banjiu_wjz` | wjz |
| 宝多六花 | `baoduoliuhua_wjz` | wjz |
| 赤城 | `chicheng_heihua` | heihua |
| 天海春香 | `chunxiang_wjz` | wjz |
| 大青花鱼 | `daqinghuayu_idolns` | idolns |
| 飞鸟 | `feiniao_ex` | ex |
| 飞鸟 | `feiniao_wjz` | wjz |
| 貉 | `he_wjz` | wjz |
| 卡菈·伊迪亚斯 | `kala_wjz` | wjz |
| 科洛蒂娅·巴兰茨 | `keluodiya_wjz` | wjz |
| 莱莎琳·斯托特 | `laisha_wjz` | wjz |
| 莲 | `lian_wjz` | wjz |
| 莉拉·德西亚斯 | `lila_wjz` | wjz |
| 领航员-TB | `linghangyuan1_2` | 皮肤2 |
| 领航员-TB | `linghangyuan1_3` | 皮肤3 |
| 领航员-TB | `linghangyuan1_4` | 皮肤4 |
| 领航员-TB | `linghangyuan1_6` | 皮肤6 |
| 领航员-TB | `linghangyuan2_1` | 皮肤1 |
| 领航员-TB | `linghangyuan2_2` | 皮肤2 |
| 领航员-TB | `linghangyuan2_3` | 皮肤3 |
| 领航员-TB | `linghangyuan2_4` | 皮肤4 |
| 领航员-TB | `linghangyuan2_5` | 皮肤5 |
| 领航员-TB | `linghangyuan31_1` | 皮肤1 |
| 领航员-TB | `linghangyuan31_2` | 皮肤2 |
| 领航员-TB | `linghangyuan32_1` | 皮肤1 |
| 领航员-TB | `linghangyuan32_2` | 皮肤2 |
| 领航员-TB | `linghangyuan33_1` | 皮肤1 |
| 领航员-TB | `linghangyuan33_2` | 皮肤2 |
| 领洋者-娜比娅 | `lingyangzhe1_1` | 皮肤1 |
| 领洋者-娜比娅 | `lingyangzhe1_2` | 皮肤2 |
| 领洋者-娜比娅 | `lingyangzhe21_1` | 皮肤1 |
| 领洋者-娜比娅 | `lingyangzhe22_1` | 皮肤1 |
| 领洋者-娜比娅 | `lingyangzhe22_2` | 皮肤2 |
| 领洋者-娜比娅 | `lingyangzhe31_1` | 皮肤1 |
| 领洋者-娜比娅 | `lingyangzhe31_2` | 皮肤2 |
| 领洋者-娜比娅 | `lingyangzhe32_1` | 皮肤1 |
| 领洋者-娜比娅 | `lingyangzhe32_2` | 皮肤2 |
| 领洋者-娜比娅 | `lingyangzhe32_3` | 皮肤3 |
| 秋月律子 | `lvzi_wjz` | wjz |
| 南梦芽 | `mengya_wjz` | wjz |
| 那不勒斯 | `nabulesi_blueprint` | blueprint |
| 奈美子 | `naimeizi_wjz` | wjz |
| 领洋者-娜比娅 | `npclingyangzhe3_2` | 皮肤2 |
| 帕特莉夏·阿贝尔海姆 | `patelixia_wjz` | wjz |
| 飞鸟川千濑 | `qianlai_wjz` | wjz |
| 如月千早 | `qianzao_wjz` | wjz |
| 赛莉·古劳斯 | `saili_wjz` | wjz |
| 斯库拉 | `sikula_h` | h |
| 苏维埃贝拉罗斯 | `suweiaibeilaluosi_wjz` | wjz |
| 探索者-艾普洛 | `tansuozhe1_1` | 皮肤1 |
| 探索者-艾普洛 | `tansuozhe1_2` | 皮肤2 |
| 探索者-艾普洛 | `tansuozhe21_1` | 皮肤1 |
| 探索者-艾普洛 | `tansuozhe21_2` | 皮肤2 |
| 探索者-艾普洛 | `tansuozhe22_1` | 皮肤1 |
| 探索者-艾普洛 | `tansuozhe22_2` | 皮肤2 |
| 探索者-艾普洛 | `tansuozhe31_1` | 皮肤1 |
| 探索者-艾普洛 | `tansuozhe31_2` | 皮肤2 |
| 探索者-艾普洛 | `tansuozhe32_1` | 皮肤1 |
| 探索者-艾普洛 | `tansuozhe32_2` | 皮肤2 |
| 探索者-艾普洛 | `tansuozhe32_3` | 皮肤3 |
| 维托里奥·维内托 | `weineituo_wjz` | wjz |
| 尾张 | `weizhang_h` | h |
| 信浓 | `xinnong_h` | h |
| 夕烧 | `xishao_ex` | ex |
| 夕烧 | `xishao_wjz` | wjz |
| 雪不归 | `xuebugui_ex` | ex |
| 雪不归 | `xuebugui_wjz` | wjz |
| 雪泉 | `xuequan_ex` | ex |
| 雪泉 | `xuequan_wjz` | wjz |
| 双海亚美 | `yamei_wjz` | wjz |
| 焰 | `yan_ex` | ex |
| 英格拉罕 | `yinggelahan_3` | 皮肤3 |
| 水濑伊织 | `yizhi_wjz` | wjz |
| 云仙 | `yunxian_wjz` | wjz |
| 双海真美 | `zhenmei_wjz` | wjz |
| 三浦 梓 | `zi_wjz` | wjz |
