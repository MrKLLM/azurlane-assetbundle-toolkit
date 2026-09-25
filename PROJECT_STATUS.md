# 碧蓝航线 AssetBundles 解包项目 — 进度总结

> **生成时间**: 2026-09-25 03:10（本轮：**sharecfg_re 第 (19) 轮——`www()` 三段端到端复现，trailer 字节序纠正 + 两条旧否证作废，配置表判定为"容器层不需解密"**，见 §6 第 7 条；同日 (18) 轮为 19×int32 密钥到手）。
> 下面 ①~④ 是上一轮（2026-09-24）**Live2D 动作数据全量重导**的明细，结论仍然有效；同日的 sharecfg_re (16) 轮记在 §6 第 7 条。
> ① **结果**：全库 `clips 8154 / shell 7（=§2.5 记录的资产层真为空的 7 条，无新增失败）/ misassign 0 / PartOpacity 79 模型`，
>   曲线总数 **944,136 → 2,662,615（×2.82）**，与唯一经人工目视验收的样本 `antu_2`（98→278，×2.83）同比例；
>   `fix_model3.py` 全库补登 `Touch*` 判定区（`HitAreas` min 3 / max 78 / mean 12.3，0 悬空引用 / 0 未引用文件）；
>   **浏览器回归全绿**：`l2d_sweep.py` 全量 **总计 269 | 失败 0 | 默认动作未启动 0 | 切动作未生效 0**（1560s）。
> ② **事故（见 `TROUBLESHOOTING.md` §25）**：脱离启动时 `L2D_OUT_DIR` 未被子进程读到（同一条 ps1 里另两个配方变量都生效，
>   机制不可复现），重导**跳过「临时目录→审计→备份换入」原地覆写**了 `Output/Live2D`。已核实 `.diag/l2d_new`
>   （269 模型 / 曲线 944,136，与本文档记录的覆写前总数**逐字相等**）即覆写前状态，复制为
>   `Output/_OLD_bak/l2d_motion_pre_swap_20260924/` 恢复回滚能力；按「**写向一律走 argv**」给 `extract_motions.py` 加 `--out`，
>   `--all` 不给 `--out`/`--into-production` 即拒绝；并补了进度行 `[i/n]`+flush 与固定 `[SUMMARY]` 终判行。
> ③ **新入库工具**：`scripts/diag/wait_for_detached.ps1`（按命令行匹配 `python.exe` 工作进程判活——启动器 PID 与
>   `Wait-Process` 抛错都会误判）、`clean_diag_profiles.py`、`check_inputs.py`、`l2d_voice_inventory.py`。
> ④ **权威基准 `l2d_ref_diff` 判据已按 §26 重定义并实测**：旧判据给出 153 FAIL 而同一批数据文件级审计与浏览器回归全绿，根因是「关键帧不一致」把参考版 60fps 重采样算成硬错误 + 组→文件按 `files[0]` 盲配。现在 FAIL 只认真缺陷（漏组 / 配对成功下曲线缺失 / 偏差中位>0.5）、新增 **`INCOMPLETE`**（比到的组 <应比的 60% 不得当通过）、12s→30s 墙钟硬超时（12s 会把能成的请求误判成"参考库没有"，是修判据时我自己引入的新假绿灯）、`.diag/refcache` 缓存、`[i/n]` flush + 每 10 个增量落盘、`--only` 分批。**全库已跑完（269/269）**：`PASS 7 / WARN 54 / FAIL 16 / INCOMPLETE 4 / SKIP 188`——参考库真实覆盖率只有 **81/269≈30%**（旧文档「约 8/14」是抽样说法，已按实测更正）→ **这条闸门天生只能覆盖三成模型，不能当全量保证**；16 个 FAIL 里 15 个是 `effect` 组的阶跃段问题（§27），1 个 `aijier_2` 是资产层真为空的预期差异；4 个 INCOMPLETE 全是参考库缺组。5 个已知样本改前后结论一致（PASS 3 / WARN 1 / SKIP 1），`abeikelongbi_3` 由误报 FAIL 转为覆盖完整的 WARN。
> ⚠️ **本轮新开的问题（非重导引入，已取证）**：判定区补登到几十个后，`hit_verify` 抽样 8 模型 **46/58**。
>   **根因不是「前端缺面积最小规则」（那条 09-23 就有了），而是 `fix_model3.py` 登记判定区完全不做几何校验**（只看 `"Touch"+名` 在不在 moc3 字节里）→ 全库 3309 框里 **95 个退化框**（面积或宽高≈0，集中在 8 个模型）、**67/269 模型有完全相同几何的框**；退化框面积≈0 在「取最小者胜」下永远赢，可点宽度却只有 ±2e-6 → **点不中却抢走合法大框的点击**。
>   **已修**：前端 `geomOf` 过滤退化框（判定与可视化同源）+ `hit_verify` 四类化（改用产品自己的 `hitAt`）→ 同 8 模型 `HIT 32 / SHADOWED 20 / WIRING 0 / OUTSIDE 6`，**WIRING=0 说明事件链路没有缺陷**。
>   ⏳ **残留是产品语义选择、等你裁定**（A2 核心三框优先 / A3 重叠标记合并成随机一条 / A4 维持现状）：`lafeiii_3` 的 Body 被 `touch_idle4` 的**真实小框**合法遮住，过滤退化框修不了它。**基线标定等你定了再做，否则标两遍。** 全文见 `TROUBLESHOOTING.md` §27。
> 上一轮 2026-09-23(16:20)：**Live2D 动作数据根因修复（TROUBLESHOOTING §21）+ 运行时四补丁**——主因是 `motion3.json` 的贝塞尔控制点被写成**归一化分数**而运行时按**绝对(时间,值)**直读不做还原（每条贝塞尔先猛蹿到≈0 再跳目标值，即"部件各动各的"），安土 idle 逐曲线偏差中位 **1.376→0.0**；次因是只读 `m_StreamedClip` 丢掉 `m_ConstantClip` 的 180 条定值曲线（`genericBindings` 序=[streamed][dense][constant]，补全后 **idle 曲线 98→278** 与参考版逐字段一致）；外部权威基准=l2d.su 同模型导出（覆盖约 8/14）；运行时四补丁=采纳 `Meta.Loop`+对齐 `groups.idle`（废除 idle 看守者）、删 `_startMotion` 的 `stopAllMotions` 恢复交叉淡化、关闭运行时自加的 Cubism2 假呼吸层（安土组件清单里**没有 Breath**）、命中判定改真实四边形；model3 三项对齐=淡入淡出交回运行时默认（idle 2s/动作 0.5s，idle 拆 **FadeIn 2.0/FadeOut 0.5**）、补 `EyeBlink`/`LipSync` 组、**判定区 3→57**（与核心三框零重叠）。当时仅 `antu_2` 换入。
> 同日早些 2026-09-23：**Live2D 交互根因三连修 + l2d.su 三件套移植**。① `hitAt` 缺「点在框内」判定 → 点空白触发最近部位被打断（用户报"悬停乱触发/做得赶"），回归脚本 `interact_verify` 断言键笔误致恒绿灯；② vendored pixi-live2d-display 0.4.0 cubism4 模块 `setIsLoop()` 有定义无调用 → `Meta.Loop` 失效、**所有动作只播一轮**，前端加 **idle 看守者**（时长-120ms 交叉淡入重开）解决；③ **坐标系大坑**：`getDrawableVertexPositions` 返回 V=Cubism 原生（中心原点/y向上），`toLocal/ppu` 是 P（左上/y向下），差「平移半边+Y翻转」——旧命中与测试脚本在同一错误映射下**自洽闭环**（点胸口实际触发头部动作但 806/807 全绿）；已统一 P2V/V2P 换算（证据 `.diag/_probe_affine.json`），修复后判定框贴模型、真实路径全量回归。同日移植 l2d.su 三件套：**判定区可视化**（彩色框+标签逐帧跟随物理）+ **参数·部件检查器**（464 参数滑杆+270 部件透明度，变相表情系统，含过滤/复位）。验证=12s 静默采样 currentGroup 全程 idle、interact_verify 4 模型全过、hit_verify 全量复跑见下、判定区截图比对。详见 §19/§20。上一轮 2026-09-22：**换入此前重建待发的 9 个 Live2D bundle** → `Output/Live2D` 达 269 模型；逐字段 diff 证零回退、9/9 内容判据全绿。上一轮 2026-09-21 主线：**Live2D 动作层根因重建**——旧产物 5037/8154 条是空壳、其余 3117 条曲线名全错位，即用户所见"乱飘/乱闪/没反应"；
> 已按 `crc32("Parameters/<GO>")↔genericBindings` 权威映射全量重生成（曲线总数 179,072→856,870，审计 0 空壳 / 0 错位），
> 并把此前整层丢弃的**部件可见性(PartOpacity/换装拼接)曲线**写进 motion3.json（79 模型）。详见 §2.5、§9.5、`docs/TROUBLESHOOTING.md` §17。
> 同日闭环：§6.7 全量 260 皮肤部位点击验证 767/768、§6.9 脸部白块 34 张换入、story_review 31 条自机落地、§8 变体后缀语义纠正、WF-15 增量重跑 + 13 个诊断工具入库。历史流水已移出本文件至 `docs/archive/`）
> **上一里程碑** 2026-09-20（385 变更美术定向重建）：换入 11 单位（立绘2/Spine3/Live2D4/表情2，全新增零覆盖，对照逐字节零回退）；根因修复=dependency_manifest 重生成(86449条)+两脚本补 UnityPy fallback；index/thumbs 已增量。遗留：3 个新 Spine 未做 CG_v2 全屏导出。
> **上上里程碑** 2026-09-19：§6 第5~6条 A 收尾完成，`Output/ship_meta.json` 已产出，Live2D 运行时已备妥。
> **用途**: 跨会话对接。**v1 时代历史已外迁 `docs/archive/PROJECT_STATUS_历史归档.md`**，本文只保留当前状态与主线。当前待办见 §6。
>
> **【2026-09-21 交接状态】§6 待办 1~10 全部闭环**（上一轮提交 `0c6bb47`→`4154da9`；本轮 Live2D 动作重建提交 `03d65ef`→`c97b644`）。① **§6.9 脸部白块换入 34 张**——扫描 2221 候选得 35 洞 → 对比图交用户过目 → `leiniya_wjz` 经确认排除（靠**收紧门控**自动排除，不写例外名单）；端到端校验：34 张内容一致 / 68 URL 200 / 其余 4454 张 mtime 未变（备份 `Output/_OLD_bak/facefix_20260920/`）。② **story_review 勾选落地**——31 条自机进 `EXTRA_SHIP` 且白名单优先于塞壬分支，ship 850→881 / story 158→127，非类别字段零回退。③ **§6.7 Live2D 关闭并追加两轮修复**——动作播放（`startMotion` 传参陷阱）+ **按部位点击触发**（HitAreas；全量 260 皮肤 **767/768**、259/260 模型全中，残留歧义 1 例 `z46_3` 已记录）+ 交互层三修（裸滚轮劫持页面 / 点空白乱播兜底 / `pointercancel` 缺失致拖拽卡死）。④ **§8 变体后缀语义纠正**——`_hx`=和谐版、`_n`=无背景版，画廊 1746 条 label 改准、逐字段 diff 无意外变化。⑤ **治理沉淀**——新增 `docs/WORKFLOWS.md` **WF-15 游戏版本更新增量重跑**（含承重文件白名单）；13 个可复用诊断工具从 `.diag` 归档入 `scripts/diag/`；`.diag/` 正式 gitignore；AGENTS.md 加「清理前核对白名单」硬规则；技能 1 新建（`live2d-web-runtime-integration`）+ 3 更新（headless-cdp / unity-assetbundle / safe-pipeline）。⑥ **（同日第二轮）Live2D 动作层根因重建**——查明 57% 动作是空壳 + 其余曲线名全错位（两处静默失败，非前端问题），按 `crc32("Parameters/<GO>")↔genericBindings` 权威映射全量重生成并换入（曲线 179,072→856,870，审计 0 空壳/0 错位），并把官方换装拼接层 PartOpacity 曲线写进 motion3.json；判据从「动作启动了」升级为「曲线有内容且值在变」。⑦ **（09-21 第三轮）9 个未还原 bundle 已重建到临时目录、按用户决定暂不换入**——`.diag/l2d_new9/` 里 852 clip / 0 空壳 / 0 错位 / 87,266 曲线，随时可换入（见 WF-7 第 7 步）；同轮查出**「4 个模型无判定区」是误判**（见 §6.11）。**在途 0 项**（09-21 的「9 个模型换入」「HitAreas 规则修正(§6.11)」及「`l2d_sweep` 逐条驱动全量浏览器回归」均已于 2026-09-22 完成）。
> **【2026-09-22 已换入】9 个从未还原的 live2d bundle 正式换入 `Output/Live2D/`**（benningdun_2 / bunao_3 / feiteliekaer_4 / gangyishawa_3 / guanghui_9 / pulimaosi_3 / sebao_2 / shi_3 / wuzang_4）：从 `.diag/l2d_new9/` 逐目录复制（**全新目录零覆盖**，复制前后逐文件 sha256 一致，901 文件 / ~487MB）→ `build_gallery_index.py` 重建 index（临时目录 `GALLERY_OUT_DIR` 先建、与换入前基线**逐字段 diff**：ship/skin 集合不变、非 live2d 字段变化 **0**、仅 9 卡各 +1 `live2d`/`live2dBase` + 计数 260→269，随后发布到 `Output/gallery_v2/`，旧 index 备份 `Output/_OLD_bak/gallery_index_pre_l2d9_20260922/`）→ `make_thumbs.py` 增量 **0 重建 / 4719 skip**（正图未动）→ 浏览器内容判据抽验。**关键验证教训**：运行时把每条 idle 解析成 `isLoop:false`（全 269 模型一致的既有管线特性，非本轮引入），idle 只播一次即回静帧——若按旧法等到 ~12s 后再两次快照比对，短 idle(5~8s) 已播完 → 假报 `moved=0`（本轮一度据此**误判 bunao_3/guanghui_9 坏了**）。改为**播放窗口内高频密采全参数、取跨帧 min/max** 后：**9/9 模型 idle 均驱动参数**（benningdun_2 45 / bunao_3 57 / feiteliekaer_4 90 / gangyishawa_3 58 / guanghui_9 143 / pulimaosi_3 50 / sebao_2 29 / shi_3 75 / wuzang_4 144 条参数值变化），全绿。⚠️ 注：§6.7「260/260」为换入前口径，现 269；新 9 模型的 HitAreas 仍是占位 Id（点部位走兜底），真判定区待 §6.11 修。`.diag/l2d_new9/`（467MB）已冗余，可清理。
> **【其它待办】**~~§6.11 HitAreas 生成规则漏了 `touch_*` 组名~~ **已于 2026-09-22 修复落地**（13 模型真实判定区、全库 806/807）｜**官方交互层**：用 `CubismRaycastable` 真点击区替换现在猜的 `Touch*` drawable HitAreas、以及 `CubismExpressionController` 表情还原（注意运行时不读 pose3.json/exp 需验证）｜§6 待办 7「晶环联盟阵营码」三选一（A 逆向 sharecfgdata 加密 / B 走 381 旁路 / C 搁置）｜**剧情 CG 混进 `Paintings_v2/`** 的识别与分离（用户指出"脸黑的基本都是剧情 CG"，与缺脸是两类问题，见 §6.8）｜**结构隐患**：~~`azdata_*.json` 权威元数据源仍住在可被清理的 `.diag/`~~（**2026-09-24 已迁 `inputs/azdata/` + sha256 台账 `MANIFEST.json` + 校验 `scripts/diag/check_inputs.py`；数据本体仍不入库**，理由：9.2MB 游戏配置属资产、zlib 后 0.67MB 虽小但仓库原则是「只承载可复现的工具与知识」）——剩余一项：18 个核心脚本硬编码 `D:\Azur Lane Assets` 绝对路径（建议改 `__file__` 推导）｜**语音产物口径已定：无需单独备份**（可确定性再生，体检 `scripts/diag/l2d_voice_inventory.py`），不可复原的只有 `inputs/azdata`｜低优先：声优中文姓名回填、UI/图标批量导出、`organize.py`。

---

## 1. 项目概览

- 对碧蓝航线 Unity AssetBundle 解包、分类、导出、还原。
- 源路径 `D:\Azur Lane Assets\files\AssetBundles`，196 子目录 / ~86,890 文件 / ~26.6 GB（94.6% 无后缀二进制 blob）。
- **当前主线 = v2 数据驱动管线**（见 §9）：零猜测、零手调，已全量收官。

### 仓库治理 ✅
- 忽略规则收敛为「保留源码与文档，忽略游戏资产与生成产物」：忽略 `files/`、`Output/`、`tools/`、`.micode/`、`.mimocode/`。
- 生成产物与资产元数据已从 Git 索引移除，避免再次提交游戏资产。

---

## 2. 各部分进度

### 2.1 目录扫描 ✅
86,849 文件 / 26.62 GB / ~30 类；输出 `asset_manifest.json`(25MB)。脚本 `scripts/scan_assets.py`。

### 2.2 立绘导出 ✅
43,520 导出 / 0 失败。脚本 `scripts/export_assets.py`（UnityPy）。（v1 合成产物已被 v2 取代，见 §9.2。）

### 2.3 背景导出 ✅
1,897 张（bg 1,302 + helpbg 364 + commonbg 111 + loadingbg 50 + loadingbg_hx 13 + newshipbg 14 + worldhelpbg 29 + lotterybg 12 + backyardbg 2）。输出 `Output/Raw/{bg,commonbg,loadingbg,helpbg,...}/`。
> 2026-09-16 随源包更新全量重导 1897/1897；修复 `export_assets.py` 漏设 `FALLBACK_UNITY_VERSION` 导致较新包加载失败的问题。

### 2.4 音频导出 ✅
4,370 WAV / 0 失败 / ~14GB。`.b` 是 CRIWARE ACB，vgmstream 解码。分类 BGM 536 / CV 2,696 / Other 1,136 / SE 2。脚本 `scripts/export_cue_audio.py`。

### 2.5 Live2D 模型还原 ✅（2026-09-21 动作层重建；2026-09-22 补齐 9 个 bundle → 269 模型）
269/269 还原、纹理拼接正确、HitAreas 已全库补登真判定区。输出 `Output/Live2D/{舰名}/`，**4.7GB**（2026-09-24 实测，曲线补齐后从 ~3.9GB 涨上来）。脚本 `reconstruct_live2d.py` / `fix_model3.py` / `extract_motions.py`。
| 指标 | 数值 |
|---|---|
| motion 文件 | **8154** 条（0 未引用 / 0 悬空引用；shell 仅剩 7 条资产层真为空，见下） |
| 曲线总数 | **2,662,615**（2026-09-24 全量重导：944,136 → 2,662,615，×2.82，与唯一人工验收样本 `antu_2` 98→278 的 ×2.83 同比例） |
| PartOpacity 换装曲线 | 79 模型（`gaoxiong_7` 3548 条、`kebensi_2` 2940 条、`chaijun_3` 2492 条等），此前整层丢弃 |
| 审计 | shell **7** / misassign **0** / `clips 8154`（`scripts/diag/l2d_motion_audit.py`，2026-09-24 全库） |
| HitAreas（model3） | min 3 / max 78 / mean 12.3，**无 0 判定区模型**（2026-09-24 `fix_model3.py` 全库补登 `Touch*`） |
| 资产层真为空的 clip | 7（*_3 的 effect、wuqi_3 的 idle11 等），已从 model3 引用剔除 |
> **2026-09-21 根因重建**：旧产物 5037/8154 条动作是 `"Curves": []` 空壳（`num_keys>100` 护栏误杀帧 0），
> 其余 3117 条**曲线名全部错位**（按"curve idx==参数序号从0连续"取名，实际稀疏）→ 就是"乱飘/乱闪/没反应"。
> 现改为 `genericBindings[i].path == crc32("Parameters/<GameObject名>")` 权威映射 + 贝塞尔 + 结构自检。
> 旧数据备份 `Output/_OLD_bak/l2d_motion_20260921_141226/`。详见 `docs/TROUBLESHOOTING.md` §17。
> ⚠️ 旧结论「B 类 12 模型属 motion 质量、资产无缺口」作废：除上述 7 条外均可解出，是解析器缺陷不是资产缺陷。
已知限制：StreamedClip 未完全逆向；HitAreas 用 moc3 `Touch<X>` drawable 而非官方 `CubismRaycastable` 真点击区（**2026-09-22 §6.11 修后全部 269 模型均带真实 HitAreas**，仅 `z46_3` Special 框嵌 Body 属模型自带歧义）；0.226% 绑定（疑 Drawable 颜色）运行时无对应 target，跳过。
> **网页交互层状态（2026-09-23 §6.12 + §21）**：点击命中已修「四边形包含 + V/P 坐标系换算」，idle 循环已交回运行时（前端零定时器），动作切换恢复交叉淡化，运行时自加的假呼吸层已关闭，另有判定区可视化与参数·部件检查器；改前端前**必读 WF-16**（五条硬规则 + 回归五件套）。
> ~~⚠️ §21 的根因修复目前只在 `antu_2` 一个模型上换入验证、其余 268 个模型仍是旧数据~~ → **2026-09-24 已全量落到 269 个模型**（覆写过程有事故，见下一条与 `TROUBLESHOOTING.md` §25）。当时判定的两个系统性错误（贝塞尔控制点写成归一化分数 → 部件各动各的；只读 `m_StreamedClip` 丢定值曲线 → 切动作时参数回不到静止位）现已在全库消除，`aerbien_3` 这类曲线数从 445/640 补齐到 640/640。
> **✅ 2026-09-24 全量重导已落到 269 个模型（含事故记录）**：`antu_2` 样本 104/104 与已验收生产数据逐字节一致 → 全量 `clips 8154 / shell 7（=资产层真为空的 7 条）/ misassign 0 / PartOpacity 79 模型`、曲线总数 **944,136→2,662,615**。**过程有事故**：脱离启动时 `L2D_OUT_DIR` 未被子进程读到，重导**跳过了「临时目录→审计→备份换入」直接原地覆写** `Output/Live2D`（同一条 ps1 里另两个配方变量都生效，机制不可复现）；已核实 `.diag/l2d_new`（269 模型 / 曲线 944,136，与本文档记录的覆写前总数逐字相等）即覆写前状态并复制为 `Output/_OLD_bak/l2d_motion_pre_swap_20260924/` 恢复回滚，闸门补跑在正式目录上，并按「写向一律走 argv」给 `extract_motions.py` 加了 `--out`（不给即拒绝 `--all`）。根因与教训见 **`TROUBLESHOOTING.md` §25**。
⏳ **9 个 bundle 已于 2026-09-22 换入**：benningdun_2 / bunao_3 / feiteliekaer_4 / gangyishawa_3 / guanghui_9 / pulimaosi_3 / sebao_2 / shi_3 / wuzang_4——9 张卡的 `live2d` 字段已进 index.json，`Output/Live2D` 现 **269 个模型**。换入后逐字段 diff 证**非 live2d 字段零变化**（ship/skin 集合不变、仅 9 卡 +9 live2d 项）；**内容判据全绿：9/9 模型加载 + idle 驱动参数（加密采样各 45/57/90/58/143/50/29/75/144 条参数值变化）**。⚠️ 关键教训：运行时把每条 idle 解析成 `isLoop:false`（全 269 模型一致的既有管线特性，非本轮引入），idle 只播一次即回静；故**验证必须在播放窗口内高频采样**，若等 ~12s 后两次快照比对会因短 idle(5~8s) 已播完回到静帧而假报 `moved=0`（本轮曾据此误判 bunao_3/guanghui_9，密采证伪）。临时产物 `.diag/l2d_new9/`（467MB）已冗余可清理。

### 2.6 Spine 动态立绘 ✅（v2 提取 + 全屏 CG 导出 + viewer 修复，2026-09-19）
`scripts/extract_spine_v2.py` 双结构兼容提取到 `Output/Spine_v2/`，232 主包。gallery 内 `spine-all.js`(3.8) 分层实时播放。**2026-09-19 三修复**：①相机视口（`SceneRenderer.resize()` 不更新 viewport → 比例怪）②`my` 变量遮蔽 TDZ（假「N 层失败」+ 取消失效）③过滤 0 秒空占位动画、默认播 `normal`、缺动画层回落 normal；另支持 JSON 骨架（beierfasite_g）。**全屏 CG 导出**：`cg_export.html` 渲染 setup pose 批量落盘 `Output/CG_v2/` **231/231 成功**（含二次像素包围盒构图修正）。

### 2.7 UI/图标导出 ⏳ 未处理
`ui/` 4,059 文件 + 各 icon 目录数万，可复用 `export_assets.py`。优先级最低。

### 2.8 资源分类整理 ⏳ 未处理
`scripts/organize.py` 已写未跑，需所有导出完成后进行。

### 2.9 Wiki 舰船数据 ✅
862 舰 / JSON(name,faction,ship_type,rarity) / `Output/WikiData/ship_data.json`。脚本 `scrape_wiki_fast.py`(8线程92秒)。已知：148 艘缺阵营（联动/特殊舰）。

---

## 3. 已加工资产清单

| 类别 | 文件数 | 大小 | 说明 |
|---|---|---|---|
| Paintings_v2 | 4,486 | ~15 GB | v2 静态立绘（当前正式产物） |
| Spine_v2 | 232 主包 | — | v2 Spine 提取 |
| Live2D | 256 | ~3.5 GB | Live2D 模型 |
| Audio | 4,370 | ~14 GB | BGM/CV/Other/SE |
| Raw/bg 等 | ~1,900 | ~2 GB | 背景/加载/帮助图原件 |
| gallery_v2 | ~4,500 | ~190 MB | 本地浏览平台 |
| files/AssetBundles | 86,849 | 26.6 GB | 源数据（只读） |

（v1 旧产物与调试目录已归档/清理；`.trash` 内旧 bug 产物已于 2026-09-16 彻底删除，释放 8.9GB。**2026-09-20 清理**：`.diag` 内 17 个 headless Chrome profile 缓存 + 历次立绘修复的一次性调试输出目录 + 本次 B 会话临时文件、`Output/_OLD_bak`(三次修复换入前备份 918MB)、`Output/` 下 bj_*/layout_2b/run_v2_full.*.log 零散件，共 **126 项送回收站、释放 7.3GB**；errors 流水并入 `docs/ERRORS.log`。保留 azdata 权威缓存/`dependency_manifest_385.json`/`run_cg_export.py`。重复资产(Paintings_v2 50 个逐字节重复 252MB 等)因被画廊按文件名引用，本轮未动。**2026-09-20 硬链接去重**：Paintings_v2/Paintingface/CG_v2 内 519 组逐字节相同文件（`npcX`==`X`、部分`_asmr`/`_hx`==本体、`left/mid/rightchicheng_alter` 三视图同图等），531 个重复文件转 NTFS 硬链（`os.link`，失败回退 copy），物理实省 **~358MB**；路径与内容不变，逐文件 nlink+sha256 校验 + 起 http.server 对全部 531 路径 GET 200/长度/哈希三重核对全通过，画廊引用零破坏。）

---

## 4. 工具链

| 工具 | 版本 | 用途 | 状态 |
|---|---|---|---|
| Python | 3.11 / 3.13 | 运行脚本 | ✅（v2 用 `py -3`） |
| UnityPy | 1.25.3 | 读取/导出 AssetBundle | ✅ 用户级 pip |
| Pillow | 12.x | 图像处理 | ✅ |
| ffmpeg | 7.1 | 音视频处理 | ✅ |
| vgmstream | v2117 | CRIWARE 音频解码 | ✅ |
| ALPA | 1.0.5.1 | 立绘注入/预览（参考真值） | ✅ 需 Java 17 |
| AssetStudio | v2.4.1 | 可视化预览/导出 | ✅ |
| spine-all.js | 3.8 | Spine 运行时（gallery 复用） | ✅ |

---

## 5. 关键文件清单

**核心脚本**：`scan_assets.py`、`export_assets.py`、`export_cue_audio.py`、`reconstruct_live2d.py`/`fix_model3.py`/`extract_motions.py`(★2026-09-21 权威映射重写)/`apply_live2d_motions.py`(★临时目录→备份换入)、`compose_paintings_v2.py`(★v2)、`extract_spine_v2.py`(★v2)、`export_dependency_manifest.py`、`build_gallery_index.py`、`make_thumbs.py`、`deploy_gallery.py`(gallery_src→Output)、`mumu_sync.py`、`ship_name_map.py`、`scrape_wiki_fast.py`。

**可复用诊断/验证工具 `scripts/diag/`**（18 件）：`scan_faces.py`(脸洞扫描)、`make_face_cmp.py`/`make_review_sheet.py`(改前后对比图/复核总表)、`l2d_motion_audit.py`(★全量动作健康审计：空壳/错位/PartOpacity/时长，`L2D_OUT_DIR` 可审任意产物目录)、`l2d_ab.py`(★同一模型新旧 motion 的渲染级 A/B，**只在换入前构成对照**)、`l2d_diff_dirs.py`(★两个产物目录逐 clip gained/changed/lost)、`l2d_sweep.py`(★全量加载+动作内容判据扫描；**2026-09-22 重写为 Python 侧逐条 evaluate + 每 N 模型重载页面**，修掉旧版「单次 evaluate 卡第一条不返回」与「单 Chrome ~110 后 WebGL 断连」，全库 269/269 一次跑通)、`l2d_verify.py`/`l2d_click.py`(抽样与真实点击路径无头校验)、`hit_verify.py`(按部位点击触发断言，支持 `--only`；2026-09-23 起合成点击经 V2P 走**真实路径**)、`interact_verify.py`(滚轮/拖拽/兜底/空白/部位五项交互断言)、`l2d_coord_forensics.py`(★**2026-09-23 新增**：坐标系取证——可见头/胸/髋三点反查应落 Head/Special/Body，专治「张冠李戴」且不构成自洽闭环)、`l2d_inspector_verify.py`(★**2026-09-23 新增**：判定区可视化+参数·部件面板+滑杆往返+过滤器四项验收)、`run_cg_export.py`(Spine CG 批量导出驱动)、`dedup_plan.py`/`dedup_apply.py`/`dedup_httpverify.py`(硬链去重三件套)、`gen_story_md.py`(复核清单生成)。**游戏版本更新怎么跑 → WF-15**；**Live2D 动作重建怎么跑 → WF-7**；**Live2D 网页交互改动/回归怎么跑 → WF-16**。

**文档**（导航见根目录 `README.md`，写入路由见 `AGENTS.md`）：
- `docs/DEV_LOG.md` 操作手册 · `docs/WORKFLOWS.md` 可复用工作流 · `docs/TROUBLESHOOTING.md` 踩坑 · `docs/ERRORS.log` 错误流水
- `docs/tools/` ALPA、AssetStudio 使用说明
- **项目技能库 `.agents/skills/`**（8 个，入库）：`live2d-web-runtime-integration`(新建)、`unity-assetbundle-painting-restore`、`headless-chrome-cdp-batch-export`、`safe-pipeline-fix-targeted-rerun`、`windows-hardlink-dedup-verify`、`windows-local-server-launcher`、`cn-blocked-resource-mirror-fetch`、`project-doc-governance`——做同类任务前先查这里，别从零摸索
- `docs/archive/` 历史归档（含 `PROJECT_STATUS_历史归档.md`、旧目录审计报告、旧 Spine 交接）

**数据**：`asset_manifest.json`、`Output/dependency_manifest.json`(86,398 条官方依赖表)、`Output/WikiData/ship_data.json`、`Output/gallery_v2/index.json`。

---

## 6. 接下来的任务

### ★ 2026-09-16~21 gallery_v2 质量复核（1~10 全部闭环；11 为 09-21 新查出、用户决定暂缓；换入待发项见头部）

1. ✅ **静态立绘「嵌套容器错位」（2026-09-18）**：`layout_all` 仿射多减 `p_local[0]`，修 `52782a7`，85 张换入（备份 `Output/_OLD_bak/affected_20260918/`）。
2. ✅ **i404 型「背景缝隙」（2026-09-19）**：无 mesh 部件误用 `mRawSpriteSize` 当画框，改 textureRect 拉伸铺满 RectTransform，10 张换入（备份 `framefix_20260919/`）。painting 本身即半景特写，完整 CG 走 Spine 线（第 4 条）。
3. ✅ **mesh 越框裁头（2026-09-19，用户报「库尔斯克缺块」）**：`rasterize_mesh` 把内容钳在画框内，而 mesh 顶点可合法越框（kuersike_rw 头部伸出框顶 713px）→ 改按内容 AABB 输出（安全钳 ±2~3 倍框）。扫描 4490 包：84 皮肤越框、**55 张画面实际变化已换入**（29 张越框部分全透明逐像素同旧图；5 张画布按预期变大找回内容）；对照 5 皮肤 maxdiff=0。备份 `Output/_OLD_bak/meshfix_20260919/`，清单 `.diag/mesh_overflow.txt`，对比图 `.diag/cmp_meshfix/`。
4. ✅ **Spine 动态 + 全屏 CG 导出（2026-09-19）**：viewer 三修（相机视口 `camera.setViewport`、`my` 变量遮蔽 TDZ、0 秒空动画过滤+默认 normal）+ JSON 骨架支持；`cg_export.html` 两段式构图批量导出 **231/231** → `Output/CG_v2/`，画廊默认展示 CG 可切原件，缩略图 `<key>_cg.webp`。详见 WORKFLOWS WF-14。
5. 🟡 **元数据重建（A 收尾已完成：`Output/ship_meta.json` 已产出，交接点=B）**：
   - **脚本**：`scripts/build_ship_meta.py`（默认 `--diag` 只读，`--write` 产 `Output/ship_meta.json`）。运行：`PYTHONIOENCODING=utf-8 python scripts/build_ship_meta.py --write`。产物键=画廊 bundleID（Paintings_v2/Spine_v2/Live2D/CG_v2 目录名并集，共 4492），值=`{cn,en,faction,type,rarity,voice_actor,category,base_painting,source[,数值码]}`。
   - **桥接路径（⚠️已实测校正，覆盖 §6 旧假设）**：磁盘 stem —剥变体后缀(`_n/_hx/…/罗马数字紧跟`)→ 基 `painting` → `skin[painting].ship_group` →（`stats.skin_id` 命中皮肤的组，实测 4118/4119）→ 舰级 `nationality/rarity/type/english_name`。**旧记录里“用 `ship_group` 直接反查 stats”不成立**（1270 个 ship_group 仅 268 落在 stats 键）；**变体皮肤须经 `ship_group` 归并到舰**，不能靠自身 skin.id。
   - **成品实测**：source 分档 painting 2493 + suffix 1786 + fallback(ship_name_map) 136 + manual 2 = **4417 有中文 cn（98.3%）**；残 **75 unresolved** 全为剧情/NPC/测试（aijiang*、linghangyuan*、lingyangzhe*、npc*、error13、magician、2b/a2 联动变体）→ 归第 6 条 story。分类 **ship 4065 / story 427**。阵营分布 重樱824/白鹰729/皇家622/铁血492…，空阵营 0。
   - **数值码→中文标签表已写进脚本常量**（NATIONALITY/RARITY/TYPE，对齐游戏内筛选词表）：nationality 1白鹰 2皇家 3重樱 4铁血 5东煌 6撒丁帝国 7北方联合 8自由鸢尾 9维希教廷 11郁金王国 96飓风 97META 98其他(布里) 102~115各联动；rarity 2普通 3稀有 4精锐 5超稀有 6海上传奇 18超稀有；type 1驱逐…24风帆。游戏筛选里的「晶环联盟」本快照(9.7.381)无对应码 → 前端归「其他」。
   - **✅ 两个决策已定**：① `voice_actor` = **只存数字 id**（CV 姓名表未缓存，以后再补映射）；② 非核心码(98/111~115) = **经验名 + 兜底原样保留**，不逐个核。
   - **✅ B 已完成（2026-09-20）**：`build_gallery_index.py` 元数据主源切 `ship_meta.json`，舰名/阵营/舰种/稀有度取 ship_meta（未解析条目回落 `SHIP_NAME_MAP`+Wiki，如 `kelei`→可畏/皇家保住了），`category` 已落 index.json。**根因**：`build_ship_meta.py` 舰名原取 `ship_skin_template.name`（皮肤名，含 433 个 `{namecode}` 占位符 + 皮肤主题标题），改取 `ship_data_statistics.name`（实测 0 占位符），237 舰级占位符归零（`weizhang`→尾张、`linggu`→铃谷、`xinzexi`→新泽西、`antu`→安土，名称与阵营一致）；`META/灰烬`（`_alter` 形态）经 `normalize` 守卫拆为 56 独立卡。逐船四字段零回退。⏭️ **下一步 = C**：前端按 `category` 分「舰船/剧情角色」+ 筛选器；D Live2D 动作播放。
6. ✅ **剧情角色与舰船分级（已随 B/C 落地并经用户复核精修，2026-09-20）**：`category` 进 index.json，前端「类别」分段控件 + 网格分区。**分类精修**（`build_gallery_index.reclassify` 后处理，因单一字段不可靠）：塞壬/BOSS/NPC（名字含 `？` 或 id 前缀 unknown/sairen/npc/linghangyuan/…）→ 剧情且**清空阵营/舰种/稀有度**（修 `unknown1` 假俾斯麦误判舰船）；有阵营 / 命中维基名单 / 皮肤带 `_doa/_tolove/_idol` 联动偶像标记 / 白名单 → 舰船（把 U艇/Z驱/I潜/Hololive/SSSS/DOA/海王星/可畏/加斯科涅 等误判剧情船捞回）。精修后 **ship 850 / story 158**（→ 2026-09-20 用户勾选 31 条自机后 **ship 881 / story 127**，见 §6.9 末条）。`build_ship_meta` 加 `NAME_FIX`（贾斯科涅→加斯科涅 官方译名）。⏭️ 新发现遗留：**I-168 皮肤2 脸部白块**（paintingface 独立部件未叠，见 §6.9）。
7. ✅ **Live2D 动作播放接入（2026-09-20 完成，交接点 D 关闭）**：`gallery_src/index.html` 的 `renderLive2D` 由「只显示贴图」改为真实播放——懒加载 `vendor/live2d/` 三脚本（cubismcore 5.1.0 + pixi 6.5.2 + pixi-live2d-display 0.4.0）→ `PIXI.Application` + `Live2DModel.from(model3.json)` → 动作下拉（全组）+ 重播/复位/全屏 + 滚轮缩放(光标锚点)/拖拽平移/双击复位，默认播 `idle`。`renderView`/`closeShip` 均加 `stopLive2D()` 销毁并解绑监听。**无头 Chrome+CDP 抽样验证**（`scripts/diag/l2d_verify.py`、`scripts/diag/l2d_click.py`，截图 `.diag/l2d_shots/`）：6 模型（lafeiii_3 50组/adaerbote_3 40/aersasi_2 34/abeikelongbi_3 20/ninghai_4/pinghai_4）加载与切动作全通过；真实点击路径 3 例断言标签高亮与「显示尺寸≤容器」；缺目录降级不崩、来回切换 `destroyed+reloaded` 正常。踩坑（vendor 路径误用 `P`、`fit()` 用含 scale 的 `mdl.width` 致正反馈放大、监听器泄漏、headless rAF 节流需手动 `app.render()` 才能测出动画）见 `docs/TROUBLESHOOTING.md` §13。磁盘 260 模型全部有 `idle` 与有效 motion（§2.5「B 类 12 个」是动作质量非缺文件），未做特判。**→ 后续（同日）**：用户实测反馈「动作触发不了」，根因是 `startMotion(g, null, false)` 传参错（index=null 使库取 `motion[group][null]`→undefined 静默失败；priority=false 被当 0 而低于当前优先级被拒），已修为显式 `index 0`+`MotionPriority.FORCE`（提交 `49fd336`）。**全量 260 无头扫描（`scripts/diag/l2d_sweep.py`）：0 失败 / 默认动作启动 260/260 / 切动作生效 260/260**，动作组数 20~120（中位 21）。⚠️ 教训：判「动画是否在播」必须读 `motionManager.state.currentGroup` 非空且等 ~1.5s（startMotion 内部要 fetch motion3.json）——只看帧哈希会因 headless rAF 节流假阴性、因 physics/眨眼假阳性。**→ 又后续（同日）**：用户问「怎么点都不触发」，查明原实现只认 `tap*` 组名，而模型实际用 `HitAreas`+`touch_head/body/special`（多数无 tap 前缀）→ 已改为**按部位点击触发对应动作**（同游戏）：读 `model3.json` 的 `HitAreas[].Name`（256 模型 768 判定区，**Name 与动作组名 768/768 精确匹配**），点击瞬间实时取该 Id 对应 drawable 的顶点包围盒，多个包含框中取**归一化中心距离最近**者（框会重叠/嵌套且随呼吸物理位移，故不能按顺序取首个、也不能缓存坐标）；无 HitAreas 者回落 `tap*/touch*`。验证 `scripts/diag/hit_verify.py`（无头派发 pointerdown/up 到各部位中心，断言 `state.currentGroup`==部位名）：**40 模型 120/120 全中**（此前按顺序+缓存坐标仅 13/18）；**全量 260 皮肤复跑 = 767/768 命中、259/260 模型全中**，唯一残留 `z46_3`（Special 框嵌在 Body 框内，属模型自带歧义）。详见 `docs/TROUBLESHOOTING.md` §15。**→ 交互层修复（同日，用户实测反馈"皮肤3 模型偏移乱动 / 点空白蹦出 touch_drag8"）**：三处设计错误已改 —— ① 滚轮被 `preventDefault` 劫持，鼠标经过模型时滚列表会变成"模型一路放大到 12 倍并累积平移"→ 改为 **Ctrl/⌘/Alt+滚轮**才缩放，裸滚轮还给页面；② 兜底动作对全部模型生效导致"点哪儿都蹦个 touch_drag*"→ 兜底**只给无 `HitAreas` 的 4 个模型**（chaijun_6/antu_2/baifeng_3/jinluhao_3）（⚠️ 09-21 更正：这 4 个并非「资产没有判定区」，是我们的 HitAreas 生成规则漏了 `touch_*` 组名，故此处"只给 4 个"低估了范围 → 见 §6.11），有判定区者点框外什么都不播；③ 只处理 `pointerup` 未处理 `pointercancel`/`blur`，拖拽态会卡住导致"鼠标一动模型就飘"→ 已补，并把平移量钳制在视野 60% 内。命中判定加 **2% 容差**（吸收测试派发的几十毫秒位移；8% 会把视觉空白的角落判成命中，画布四周有大量透明边距）。**全量 260 复跑（含 2% 容差）：767/768、259/260 全中**，`kelaimengsuo_2` 已被容差修好。**已知歧义 1 例**：`z46_3` 的 Special 框整个嵌在 Body 框内，"最近中心"与"最小框"两种 tie-break 在 yingrui_3/z46_3 上互相矛盾，按游戏原生"按顺序取第一个"同样歧义 → 记录不过拟合。交互回归 `scripts/diag/interact_verify.py` 4 模型（含用户报的 aersasi_2/aersasi_3/anninvwang_2）**ALL PASS**；坑见 `docs/TROUBLESHOOTING.md` §16。
8. ⏸️ **missd（D小姐）「黑影」——用户澄清后仍搁置（2026-09-20 补注）**：当年报的「脸黑」**多半是剧情 CG 混进立绘目录**所致（脸黑的基本都是剧情 CG），与 §6.9 的「缺脸」是两类问题，排查时须先区分。missd 本身是**剧情角色**；它在 §6.9 脸洞清单里的那张确属真缺脸（改前整个头是黑色剪影），已随该批换入修复。CG 混入 painting 这条线索仍未处理。
9. ✅ **I-168 皮肤2 脸部白块（2026-09-20 用户报告 → 已修复并换入 34 张）**：
   - **现象**：`Output/Paintings_v2/i168_2.png` 脸上是不透明白色矩形；默认 `i168.png` 正常（脸烤进 `_rw`）。
   - **根因链（已探包证实）**：painting 包里有个 GameObject 名为 `face` 的节点，但其 `MonoBehaviour.m_Sprite` 是**空的（path=0/file=0）**；`compose_paintings_v2.parse_painting` 第 268 行 `if not path_id: continue` 把它跳过了。真脸在**独立的 `paintingface/<name>` 包**（i168 有 5 张表情 `1`~`5`、i168_2 有 7 张 `0`~`6`，均 ~115×108 / 169×218），游戏运行时把它贴到 face 槽。凡 `_rw` 把脸留成白洞的皮肤（如 i168_2）合成后就缺脸→白块；`_rw` 已烤脸的（i168）不受影响。`paintingface/` 共 **2246 包**，受影响子集待扫描。
   - **✅ 修复已实现（2026-09-20，`compose_paintings_v2.py`）**：`parse` 后取 face 节点 rect（`go_names[pid]=='face'`）；`render()` 画完部件后，**仅当 face rect 区域是透明洞（`frac_op<0.5`）才**从 `paintingface/<name>` 取默认脸（`FACE_DEFAULT=1`，可 env 覆盖）按 rect 叠上。已加 `compose(save=False)` + `FACE_APPLIED` 全局供扫描判定。**样本双验证**：`i168`（已烤脸）判假不叠→对照 **maxdiff=0 零回退**；`i168_2`（脸洞）判真→脸正确填上（位置/表情对）。⚠️ 洞是**透明(alpha0)**不是白，早期按「不透明白」判据全错，改 frac_op 才对。
   - **✅ 已换入（2026-09-20，用户过目对比图后确认）**：34 张换入 `Output/Paintings_v2/`（备份 `Output/_OLD_bak/facefix_20260920/`，34 文件），缩略图只删这 34 张的 `<stem>.webp` 后跑 `make_thumbs.py` 增量重建（ok=34 skip=4685 err=0，`_cg` 缩略图未动）。**`leiniya_wjz` 经用户确认排除**——它改前已是完整清晰的另一表情（睁红眼紧张微笑），叠层会换成闭眼=回退。排除方式是**收紧门控**而非手工例外表：判据从「整框不透明率 `frac_op<0.5`」改为「**脸谱自身落笔处**下方『不透明+有彩色(sat≥30)』实画占比 `FACE_ART_MAX=0.5` 超过即不叠」（旧判据错在 face rect 常含大片透明背景，已烤脸的 leiniya 整框率 49% 恰好跌破 0.5 而误叠）。改后重渲 35 张比对：**只有 leiniya_wjz 行为改变**且其输出与旧产物逐像素相同，其余 34 张与首轮临时渲染完全一致。
   - **换入后校验（全通过）**：34 张磁盘内容==临时渲染；`leiniya_wjz` 与旧产物一致；起 http.server 对 68 个 URL（34 png + 34 webp）GET 200 且长度与磁盘一致；34 张缩略图宽高比与正图一致（8 张画布变高者 `botelan_2`/`beiqi`/`ajiakesi_2`/`qifeng`/`xukufu_2`/`wenqinzuojiaobeidi`/`haerxibaoweier`/`xipeier_idolns` 属「整张头被裁掉→头部找回」，包围盒向上扩展所致）；其余 **4454 张 painting mtime 未变**=零误伤。换入前已确认这 34 张**均非硬链接**（`st_nlink==1`），无串改孪生风险。
   - **`missd` 结论（用户澄清）**：它确是**真缺脸**（改前整个头是黑色剪影，改后出黄眼+口罩），已随本批换入。用户说明：先前 §6.8 报的「脸黑」多半是**剧情 CG 混进立绘目录**所致（脸黑的基本都是剧情 CG），与本次「缺脸」是两类问题，需区分。
   - **✅ 勾选已落地（2026-09-20）**：`story_review.md` 用户勾定 **31 条自机**（拉菲III/I 系潜艇 6 艘/伊织 hdn101·102/兰利III/绊爱系 5 条/Hololive 7 条/2b·a2/探索者/领航员3/羚羊者3/匆忙/苏维埃同盟new）→ 全部进 `build_gallery_index.EXTRA_SHIP`，并把白名单判定**提到塞壬前缀分支之前**（否则会被清空阵营/舰种/稀有度）。重建后 ship 850→**881** / story 158→**127**，逐船 diff 非类别字段回退 **0**（`congmang` 反而恢复出 皇家/驱逐/精锐）。用户备注：`npc*` 前缀者暂不确定，本轮未动。

10. ✅ **Live2D 动作层根因重建（2026-09-21，用户报"乱飘/乱闪/没反应"）**：
   - **两个静默失败**：① `extract_motions.py` 的 `num_keys>100` 护栏误杀 StreamedClip **帧 0**（time=-3.4e38 的参考姿态帧，一帧写完全部曲线，大模型 380~520 key）→ 整条动作解成 `None` → `reconstruct_live2d.py` 的 `"Curves": []` 占位文件静默留存。实测 **5037/8154 条（61.8%）是空壳**，260 模型仅 1 个全真。② 曲线名按「curve idx == moc3 参数序号（从 0 连续）」取，实际稀疏（`lingbo/idle` = 0,1,2,8,9,12,…）→ 其余 **3117 条非空壳文件的曲线名无一正确**（眼睛数据写进眉毛参数）。
   - **权威映射（本轮新逆向）**：curve idx ↔ `AnimationClip.m_ClipBindingConstant.genericBindings[i]` 同序，`binding.path = crc32("Parameters/<GameObject名>")`（部件 `crc32("Parts/"+名)`）。跨模型 946,274 绑定解析率 99.77%，91.7% clip 参数序号严格递增。`CubismParameter.m_Name` 为空，真名在 GameObject，`_unmanagedIndex` 才是参数序号。
   - **修了什么**：`extract_motions.py` 重写（去护栏/参考姿态帧作 t=0 基准/crc32 权威 Target+Id/真实 Duration+Loop/Unity 切线→Cubism 贝塞尔且 dv≈0 退化线性/**按运行时消费方式重放的结构自检**/解出 0 条即报错退出）；`reconstruct_live2d.py` 不再写占位壳；`fix_model3.py` 剪悬空引用 + `L2D_OUT_DIR` 开关；前端 fit 基准改 `internalModel.width/height`、非 idle 动作按时长回落 idle（须 FORCE）。
   - **官方"拼接逻辑"落地**：79 模型的 **PartOpacity**（换装/部件可见性）曲线已写进 motion3.json——实测运行时 `pixi-live2d-display 0.4.0` **不读 pose3.json / model3 的 Pose**，只认 motion 的 `Target:"PartOpacity"`，故只能走这条路。
   - **换入与校验**：临时目录 `.diag/l2d_new` 全量重跑 → 审计 shell 0 / misassign 0 → **换入前**用浏览器 A/B（`scripts/diag/l2d_ab.py`）对 lingbo/aerbien_3/bisimai_2/gaoxiong_7 做新旧对照：旧数据 `ParamEyeLOpen=0` 静止（眼睛是闭着的）、`aerbien_3` 完全不动，新数据正常眨眼/呼吸且 `bisimai_2` 带出 PartOpacity → `apply_live2d_motions.py --yes` 换入（旧数据 **move** 备份 `Output/_OLD_bak/l2d_motion_20260921_141226/`）。曲线总数 179,072 → **856,870**；生产目录复核：7295 文件 / 0 空壳 / 0 未引用 / 0 悬空引用。
     （注：换入后再跑 A/B 时 old/new 两侧读的是同一批新数据，**不构成新旧对照**；那条 `heitaizi_2` 加载失败是 9s 等待不够的偶发，不是数据问题。）
   - ✅ **全量浏览器回归已补跑（2026-09-22）**：`l2d_sweep.py` 旧版把整轮循环塞进一次 `Runtime.evaluate` 会卡在第一条不返回（且单 Chrome ~110 个后 WebGL 断连）；已重写为 **Python 侧逐条 evaluate + 每 60 模型重载页面**，内容判据改为「clip 播放窗口内密采全参数、取跨帧 min/max>1e-3 的参数条数>0」（避开 idle 非循环晚采样假阴）。全库跑 **269/269：失败 0 / 默认动作未启动 0 / 切动作未生效 0 / 未驱动参数(疑似空壳静态) 0**（耗时 ~25 分钟，明细 `.diag/l2d_sweep.json`）。至此本轮结论依据=全量文件级审计(8154 clip) + 换入前浏览器 A/B + **全量逐条内容判据回归**三证齐。
   - **⚠️ 此前 §6.7 的「260/260 动作启动、767/768 命中」判据作废**：`currentGroup` 变了不代表动作有效，空壳也能启动。判据已升级为「`_motionData.curveCount>0` 且曲线目标值随时间变化」（`scripts/diag/l2d_sweep.py` 已改）。
   - 详见 `docs/TROUBLESHOOTING.md` §17；技能 `live2d-web-runtime-integration` 已补 §6.5「motion 权威映射」与 §7 内容判据。

11. ✅ **HitAreas 生成规则修正——真实按部位点击判定区已落地（2026-09-22 实施）**：
   - **根因（09-21 查出）**：`chaijun_6/antu_2/baifeng_3/jinluhao_3` + 09-22 换入的 9 个新模型，moc3 里**都有** `TouchHead/TouchBody/TouchSpecial` **drawable**（非仅部件），动作组也**都有** `touch_head/touch_body/touch_special`；老模型组名叫 `Head/Body/Special`。而当初生成真 HitAreas 的路径只认前者、且不在现役管线，`fix_model3.py` 只补占位 Id `HitArea/HitArea2`（前端 `getDrawableIndex` 取不到 → 判定区被过滤空 → 走兜底）。故此前「4 个模型无判定区」是误判，实际 **13 个**（9 新 + 4 旧）。
   - **修法（已实施进 `fix_model3.py`）**：HitAreas = 「moc3 含 `Touch<X>` drawable」∩「该模型真实存在的动作组（候选 `X`/`tap_X`/`touch_x`/小写回落，Name 用**实际组名**）」；**保守只替换占位 HitAreas（Id ⊆ {HitArea,HitArea2}）→ 256 个既有正确产物一律不动**。
   - **验收全绿**：① 跑 `fix_model3.py` 全库 → 逐字节 diff 证**仅 13 个 model3.json 变、且只 `HitAreas` 字段变**（256 个 mtime 未动）；② `hit_verify.py` 全库分块复跑覆盖 **269/269**、**806/807 命中**（较基线 767/768 净增 39 = 13 模型×3 新启用，全部命中）；③ **13 个模型点头/身/特各 3/3 命中**；点框外不播（前端 `fallbackG=hitAreas.length?null:...`，判定区非空后兜底自动关闭）。**唯一残留 1 例仍是 `z46_3` Special 框嵌 Body 框**（§6.7/§16 已知歧义，非本轮引入、未回退）。旧 index 无需重建（model3.json 画廊直读）。回滚备份 `.diag/m3_snap/*.bak`。明细见 `docs/TROUBLESHOOTING.md` §18。

12. ✅ **Live2D 网页交互根因三连修 + l2d.su 三件套移植（2026-09-23，用户实测反馈）**：
   - **① 命中缺包含判定**：`hitAt` 取「全图最近框」→ 点画布任意处都触发最近部位，动作被反复打断（用户感受「快/赶着完成」）。修：框内包含（2% 容差）才参与竞选，框外 null。连带查出 `interact_verify` 断言键笔误（查 `noFallbackGroup`，实际是 `noAction`）→「点空白不播」半年来**恒绿灯从未真验**。
   - **② 运行时永不循环**：vendored pixi-live2d-display 0.4.0 cubism4 模块 `setIsLoop()` **只有定义、全 bundle 无调用点** → `Meta.Loop` 无效，**所有动作（含 idle）只播一轮**，idle 4s 后回静帧。修：前端 **idle 看守者 `armIdleLoop`**（按 `Duration-120ms` 交叉淡入重开，token 与 `scheduleIdle` 互锁，销毁作废）。
   - **③ 坐标系张冠李戴（最深的一个）**：`getDrawableVertexPositions()` = V（Cubism 原生：画布中心原点、y 向上），`toLocal()/ppu` = P（左上原点、y 向下），差「平移半边+Y 翻转」。旧命中与 `hit_verify` 在**同一错误映射下自洽闭环** → 806/807 全绿但点胸口实际触发头部动作。修：产品侧 `P2V` 统一换算；验证脚本 `V2P` 合成点击（测真路径）；新增 `l2d_coord_forensics.py` 用「可见头/胸/髋三点反查」当**不经过被测映射的独立锚点**。
   - **三件套移植**（对齐 l2d.su）：**判定区可视化**（彩色框+标签，ticker 逐帧跟随呼吸/物理；蓝=Head 绿=Body 橙=Special）、**参数·部件检查器**（464 参数滑杆+270 部件透明度，含过滤/一键复位；手调参数=变相表情系统，部分替代未还原的 `CubismExpressionController`）、右键防误触。
   - **验证**：`l2d_coord_forensics` head→Head/chest→Special/hip→Body 全中且 identity 全空；`l2d_inspector_verify` 四项全 true；`interact_verify` 4 模型 ALL PASS；`hit_verify` 全量 **269 皮肤 806/807**（唯一 `z46_3` 框嵌框歧义，模型自带）。**⚠️ §6.11 与 §6.7 的「767/768 / 806/807」旧口径都建立在错误坐标映射上——数字同为 806/807，但含义已从「自洽闭环」升级为「与可见内容对齐」。**
   - 详见 `docs/TROUBLESHOOTING.md` §19/§20、`docs/WORKFLOWS.md` **WF-16**、技能 `live2d-web-runtime-integration` §3.2b/§4/§8。提交 `36a9c40` → `30514d7`。

> 诊断产物/缓存均在 `.diag/`（不入库，本机可继续用）。画廊前端改动走 `gallery_src/` → `scripts/deploy_gallery.py`。


### 既有待办

**优先级低**
5. UI/图标批量导出（~2 万）、3D 宿舍资源、资源分类整理 `organize.py`。
6. **声优中文姓名补全**：`ship_meta.json` 的 `voice_actor` 现为数字 id（皮肤表只给 id，CV 姓名表未缓存）。以后需要显示声优名时，从 azurlane-data 或游戏配置补一张 `voice_actor_id → 中文声优` 表回填（§6 第 5 条决策①）。
7. ⚠️ **阵营「晶环联盟」码待定——原方案前提已证伪，挂起待决策（2026-09-20）**：
   - ~~待资产同步后从游戏配置解析~~ → **同步已完成**（9.7.385，95 文件，2026-09-20，mumu_sync diff 归零）；但今日实测游戏 `sharecfgdata/*` 配置包为**自定义加密**（非 UnityFS，非常量 XOR，UnityPy 解析出 0 对象），本机无解法；azurlane-data 社区快照最新提交仍 **9.7.381**（无 385、无阵营名表）。→ **目前不存在任何可直读的 385 解密配置源**。
   - **✅ 已定走 A（2026-09-23，独立小项目 `tools/sharecfg_re/`）**：逆向 sharecfgdata。**已定位真目标** = 台词表 `sharecfgdata/ship_skin_words`（字幕文本源）+ 入口 `LuaConfDataReader.ReadData(configName, startPos, size)` / `ReadBufferFromCSharp`。**关键结论：C# 侧只是按 (startPos,size) 取切片的搬运工，零解密零解码，真正解析在 Lua 侧**（`scripts32/scripts64`，熵 8.000）。素材全在本机 `files/il2cpp/{libil2cpp.so 121.8MB, Metadata/global-metadata.dat 18.2MB}`（x86-64，本机 objdump 可反汇编），**不需要跑模拟器**；Il2CppDumper v6.7.46 已跑通（原生支持 metadata v31），产物在 `.diag/sharecfg_re/dump/`。已排除的假设与判据全在 `tools/sharecfg_re/README.md` 与 `docs/TROUBLESHOOTING.md` §22。**唯一验收判据：解出的 `ship_skin_template` 必须与 `inputs/azdata/azdata_ship_skin_template.json` 逐字段一致。**
   - ✅ **2026-09-25 突破（(18) 轮）：`www()` 的 19×int32 内联密钥已到手并通过行为验证。** 路径：`global-metadata.dat` 的节序在 **v31 里比 v24–29 多一对**（旧脚本按记忆里的表读 → 上一轮"默认值堆只有 21388 字节、里面没有 `1b4c4a`"那条否证打在了**错区域**，见 §29），重对齐后 `fieldDefaultValues` = @9,515,896 / 224,340 B / **12 字节记录 `(fieldIndex, typeIndex, dataIndex)`**（18,695 条：fieldIndex 逆序数 **0**、dataIndex **100% 单调**、max 879,148 ≤ 堆 879,152 → 布局由三条独立自检钉死），堆 @9,740,240 / 879,152 B；**blob 长度用相邻 dataIndex 之差切**（堆是 packed 的），于是**不需要** token→fieldIndex 映射就能按内容取数组真值。
     整堆里长度恰为 76 字节的 blob **只有 2 个**（一个是 ASCII 报错文本），另一个 = rec#17654 / fieldIndex 67773。把 Phase C 机器码逐指令落成 `walk()` 后：**`scripts64` 与 `scripts32` 的头 8 字节 `52 aa 2a a5 af 67 94 88` → `UnityFS\0`**，而全库 91,642 个 AB 里**只有这 2 个文件头 8 字节被密文覆盖**（其余 86,561 个直接是明文 `UnityFS`）→ 归属由"用法"证明，不靠索引推断。三条对照全过（闭合 5000/5000、阳性、把密文种进真实文件头 4/4 找回偏移 0）。
     顺带钉死的事实：`Array::New` 的两个调用（`int[2]` 数据块 / `int[19]` 密钥）**共用同一个元素 klass slot `0x717DB78`** ⇒ 密钥确为 19×int32=76B；Phase C = **ECB 逐 8 字节块**、`delta=0xF90042FB`、`sum₀=0x0DFF7A0A`、**2 轮**、`z` 初值取本块 `v[0]`、密钥下标 `(p&3)^e`；Phase A/B 的 235 反馈流作用在**按末 4 字节长度取出的尾段切片（写进一个静态暂存数组）**，不是作用在返回缓冲上 ⇒ 上一轮"对 scripts64 穷举 0..4095 起点"测的是错对象。
     ⚠️ **仍未打通**：修好头 8 字节后 UnityPy 报到 `No valid Unity version found` ⇒ 偏移 8 之后还有一层（ECB/235 流的各起点组合均已试出垃圾），`scripts64` 末 4 字节读成的长度也不自洽（19.6 亿 > 文件长）。**下一个问题已收窄为"8..N 字节用的是哪层"**。新增 `tools/sharecfg_re/28`（内容定位+记录自检）、`29`（Phase C 落地+三重对照），`08` 加 `--at`（反汇编 il2cpp 内部调用 thunk，dump.cs 里没符号）。
     另：堆内有 4 个**容器格式完整实例**（rec#14718/14719/14722/14723，长 1056/872/872/1051），两两成对只差第 5 个头部字节 ⇒ **高置信推断 `Header_64 = 1b 4c 4a 02 02`（与已知值一致）、`Header_32 = 1b 4c 4a 02 0a`**；注意**没有**任何长度恰为 5 或 26 的 blob 直接等于它们，所以这两个值仍是推断而非取到真值，`Footer` 内容仍未到手。三数组长度 5/5/26 由 `Array::New(5)/(5)/(0x1a)` 钉死（dump.cs 给不了数组长度）。
     仍未解：32 张表的 11 字节公共后缀在全文件 **0 命中**，与 26 字节 `Footer` 的包含关系对不上；32 张表的中段 32B 针在 metadata 里 **0/32 命中**（阴性对照已过）⇒ metadata 里没有整表副本。
   - ✅ **2026-09-25 (19) 轮：`www()` 三段已在真实文件上端到端复现，两条旧否证作废。** `30_www_endtoend_reproduce.py` 五条判据（A1 L 自洽 / A2 块0=`UnityFS\0` / **A3 AB 自报 fileSize == 模型算出的返回缓冲长度** / A4 尾段过 235 流得容器魔数 / A5 假密钥阴性对照）**scripts64 与 scripts32 双双全过**。
     ① **trailer 是大端不是小端**：`(17)` 轮与本轮初都按 `LE32` 读，得 `L=19.6 亿 > 文件长`，据此下的"**盘上整份 scripts 不是 www 的输入**"作废；真值 `L = BE32 = 6517`，返回缓冲 = `new byte[filesize-4-L]`（`0x3D9CB12 sub esi,r14d` 的 `esi` 此刻是 `len-4` 而非 `len`）。
     ② **"可打印率 0.37 = 随机 ⇒ 流不适用"是坏判据**：A4 解出的**确定是真明文**的 6512 字节，可打印率只有 **0.216**。
     ③ **A3 是本轮最硬的性质**（不含任何未知量、两边各自独立可算）：解出偏移 34 处 `02 59 48 d4` = 39,405,780 = `filesize-4-L`，两个文件各自命中。
     ④ **对"配置要不要解密"给出正面结论**：A4 的参照载荷与 `sharecfgdata/aircraft_template` 正文在**同一偏移**上骨架逐字节相同（`…05 05 00 00 … 4e ff 00 00 51`），字符串区同一种 `0x80-0xBF` 游程编码 ⇒ **容器层不需要解密，剩下的是记录/字符串文法**（全 256 单字节 XOR 在两边都 0 命中，非常量 XOR）。**台词路线由此从"破解加密"改成"解文法"，且手上第一次有了同格式的已知良好参照。**
     ⑤ `08` 号新增 `--xrefslot`（按数据 VA 反查 rip 引用）：密钥槽 `0x71E4C10` 全库仅 `www()` 一处使用 ⇒ 没有第二个共用该密钥的例程。
     ⚠️ 新反例待解释：`scripts64` 尾段头部是 `1b 4c 4a 02 0a`、`scripts32` 尾段是 `…02 02`，与 (18) 轮据堆内配对推断的 32/64 归属**方向相反**；两个头部值本轮首次以真明文出现，配对仍需另找证据。
     全文见 `docs/TROUBLESHOOTING.md` **§30** + `docs/WORKFLOWS.md` WF-19。
   - 🔎 **2026-09-25 (20) 轮：第 9 字节往后那一层已定性 —— 是 Unity 中国版 ArchiveStorage 加密，不是自研流密码。**
     `31_decrypt_scripts_bundle.py` 按 ECB **全量**解（向量化与 30 号标量实现逐块对比 8192 块 0 不一致），
     解出 `>i4 @34 == ALEN` 两个文件各自命中 ⇒ 偏移 32 之后解对；**只有偏移 8..31 这 24 字节是垃圾**，
     其长度恰为 `version + "5.x.x" + "2022.3.51f1" + i64 高位` = **扫描器指纹区（被单独改写）**。
     用同构建成文包（`files/AssetBundles/ammo`）的这 24 字节补回后，UnityPy 改报
     **`The BundleFile is encrypted, but no key was provided!`**（特征串 `#$unity3dchina!@`，即 PGR/Unity 中国 ASM）。
     **剩余唯一缺口 = 16 字节 ASM 密钥**：UnityPy 自带 `brute_force_key` 的候选集写死 `\w{16}`（太窄），
     故 `33_asm_key_scan.py` 改用固定目标 `AES_K(key_sig)==data_sig^SIGN` 做**全窗口穷举**：
     `global-metadata.dat` 逐字节 18.2M 窗口 **0 命中 ⇒ 密钥不在 metadata 里**（带穷举范围的否证）；
     `libil2cpp.so` 121.8MB 后台扫中。新增依赖 `pycryptodome`。详见 **§31**。
     ⚠️ **本条里"真身是 Unity 中国版 ASM 加密"已降级为"很可能是半解密文件的假象"**（同日第三次改判，见 §31 追加）：
     第三方 `LL.Salt` 反编译显示 `Make` 末尾是 **`num=(num+1)%4`——XXTEA 的模式按块号 4 循环**，且 mode3 额外吃块偏移；
     游戏侧同构（`0x3D9D1E8 and r11d,3` + 四路分发），**而我只实现过 mode 0** ⇒ 块 0 与块 4（4%4=0）解对、
     块 1/2/3 全错，正好解释所有异常；且 `LL.Salt` 的钥匙是 `Init(key, delta)` **调用方注入**，
     文件里根本没有钥匙 ⇒ metadata/libil2cpp.so/Salt 三处全窗口穷举 0 命中属必然，**密钥搜索线正式停**。
     **下一步 = 把 mode 1/2/3 按 `0x3D9D028` / `0x3D9D0B9` / `0x3D9CE87` 逐指令落成代码，按 %4 整文件解，再交 UnityPy 复验。**
   - ⚠️ **2026-09-24 进展（未破解，但问题重新定性）**：① "整体加密"这个前提**被证伪**——单文件内 16 字节块重复数百次（iid 期望 1e-6）、头部是可解的 4 字节记录 + LEB128，收敛为「**明文索引 + 逐字段变换**」；② 密文侧全部榨干且**每条都配对照**：已知明文逐表自撞（4634 串 × 4 编码）0 命中、跨表共密钥流（实测 1.84% vs 零假设预测 1.904% → 我上一轮的"存在共密钥流"是阈值松造成的假信号）、段内恒定密钥（差分签名，阴性对照同 0）、短周期 XOR（p=2..12 可分求解）、标准压缩按记录边界试解压、ECB/替换 全部出局；③ C# 零解密已由**机器码**证实；`www()`（RVA `0x3D9CA20`）经 `--xref` 查明**全库唯一调用方是 `LuaScriptMgr.Load`**，其产物经 `LoadABFromBytes` 变成 **AssetBundle** → 判据"输出须含 `UnityFS`"**成立且正确**（本轮一度误判它"不可达"，同日已推翻，教训见 `TROUBLESHOOTING.md` §28）；`www()` 实为三段：按末 4 字节取尾段 → `state=235` 反馈流 → **另有 TEA 族 Feistel 解头 8 字节，密钥是 `Array::New(0x13)` 的 19 个 int32（76 字节内联，(15) 误记为"19 字节"）**；盘上 `scripts64/32` 经 68.3 万个自洽候选全量反解确认**不是 www 的输入**（⚠️ (18) 轮限定：这条只对"把整文件当 235 流的尾段容器"成立；其**头 8 字节确实是那条 TEA 支的输入**（同一算法同一密钥解出 `UnityFS`），但整文件末 4 字节读出的长度不自洽 ⇒ 走的是哪个投递路径仍未定，见上），新事实：32 张配置表**公共后缀恰 11 字节**（固定 Footer 非长度）；④ adb 旁路封死（进程 fd 直接指向 `sharecfgdata/`，无解密缓存；设备与本地 md5 一致=9.7.385；**`su` 可得 uid 0**）。新增 `08`~`15` 号工具（反汇编器 + 6 个探针）。~~**待用户放行**：进程内存取证~~ **已放行并于 09-24 跑过四轮**（拿到明文但均非从容器解出，见 `tools/sharecfg_re/README.md` (7)~(16)）；同日新增 `16`~`26` 号工具，主线已收敛为「查 `sharecfg/<表名>.lua` 是否经 `LuaScriptMgr.Load` 读入」。
   - 现状维持：ship_meta 前端仍归「其他」。同理受影响：385 新皮肤在 381 快照无记录，归属也卡在同一决策上。
   - 不受影响、可独立推进：§6 交接点 B→C→D 主线；以及「385 变更美术的定向重建」（立绘/Spine/Live2D 包本身是明文 UnityFS，已同步在手）。**（2026-09-20 已完成，见头部）**
8. ✅ **ship_meta `{namecode:XX}` 占位符名（已于 2026-09-20 随 B 根因修复关闭）**：根因=`build_ship_meta.py` 舰名取 `ship_skin_template.name`（皮肤名，含占位符）——**改取 `ship_data_statistics.name`（0 占位符）**后，237 个 ship 级占位符全归零、名称与阵营自洽（`weizhang`→尾张、`xinzexi`→新泽西 等）。残余 ~52 占位符全为 `story` 类（NPC/剧情/2b 联动变体，本就无 stats 舰名，非缺漏）。详见 §6 第 5 条 B 已完成。
9. ✅ **Live2D 动作数据全量重导已落到 269 个模型（2026-09-24 完成；过程含一次覆写事故，见下）**
   根因、证据、已排除假设、天花板全部写在 **`docs/TROUBLESHOOTING.md` §21**；操作与判据在 **`docs/WORKFLOWS.md` WF-16**；覆写事故与教训见 **§25**。
   **✅ 2026-09-24 全量完成**：`clips 8154 / shell 7（=真为空的 7 条，无新增失败）/ misassign 0 / PartOpacity 79 模型`、曲线 **944,136→2,662,615**、`fix_model3` 全库补登 `Touch*`、`l2d_sweep` 全量 **269 | 失败 0 | 未启动 0 | 未生效 0**。
   ⚠️ **本项已闭环但引出两件事**：① **`hit_verify` 全库基线已于 2026-09-24 标定完成**（269 模型 / 3309 部位：HIT 2338 / INGROUP 905 / **WIRING 0** / OUTSIDE 0 / NOTCLICKABLE 66；旧「806/807」口径作废，今后判据是 WIRING 必须为 0，详见 §27）——原问题（抽样 8 模型 **46/58**）。取证后**根因不是「缺面积最小规则」**（`index.html` 的 `hitAt` 早已是「重叠取面积最小者」），而是 **`fix_model3.py` 登记判定区时完全不做几何校验**（只看 `"Touch"+名` 是否出现在 moc3 字节里，fix_model3.py:152）→ 全库 3309 个框里 **95 个退化框**（面积或宽/高≈0，集中在 8 个模型）、**67/269 模型存在完全相同几何的框**；退化框在「取最小面积」规则下永远胜出，但其可点宽度只有 ~2e-6 容差 → **真人点不到却能抢走合法大框的点击**（`lafeiii_3` 点 Body 播出 `touch_idle4` 就是这么来的）。已做：前端 `geomOf` 过滤退化框（判定与可视化同源，一处改两处生效）+ `hit_verify` 四类化（改用产品自己的 `hitAt`，实测 **WIRING=0** → 事件链路无缺陷，未命中全部能被几何解释）。**残留是产品语义选择、不是 bug**：`lafeiii_3` 25 框 = HIT 6 / SHADOWED 13 / OUTSIDE 6，Body 被 `touch_idle4` 的**真实小框**合法遮住（过滤退化框修不了这种合法重叠）→ 三条路（A2/A3/A4）→ **用户已裁定 A3（重叠即随机）并于 2026-09-24 落地**：`hitAt` 改为在含点候选里随机挑一条并避开上一次刚播的那条，新增 `window.__L2_HITALL` 供探针断言用；实测 4 候选点连调 8 次出 4 条且相邻不重复、70 部位 WIRING=0。**但真重叠很少**（静止态网格：`jianwu_2` 3 点 / `antu_2` 4 点 / `lafeiii_3` 0 点）—— `lafeiii_3` 当初的错响应其实是退化框抢点击，A 已解决。全库标定见 §6 第 9 条。详见 `TROUBLESHOOTING.md` §27；② 权威基准 `--all` 的全库重跑成本远超估计（29/269 用掉 55 分钟 → 约 9 小时，因每个模型要取其全部动作组 ≈ 2700+ 次请求），靠 `.diag/refcache` 关机后可续跑。
   **2026-09-23 实测复核（确认仍是 1/269，且给出可复现判据）**：`Output/Live2D/*/motion/*.motion3.json` 最后修改日期分布 = **2026-09-21：268 个模型 / 2026-09-23：1 个模型**；`idle` 曲线条数 `antu_2=278`（新，含 `m_ConstantClip` 定值曲线）对 `yingrui_3=117`、`lafeiii_3=109`、`jian_3=120`、`z46_3=86`、`ninghai_4=76`、`taiyuan_2=75`、`qiye_7=41`（旧，只读 streamed）。
   ⚠️ **这不只是画质问题**：§21 根因② 说明「缺曲线的参数切动作时会停在上一个动作留下的值上」，而旧模型 idle 只有 41~120 条曲线（安土 278 条）→ **其余 268 个模型的非 idle 参数残留只会比安土更严重**。本轮修的「参数残留复位」目前**只在安土一个模型上实测过**，全量重导与它是同一件事的两半。
   **2026-09-24 样本闸门已过（`.diag/l2d_fix`，5 模型）——全量待用户放行**：`antu_2` 重导 104/104 文件与已人工验收的生产数据**逐字节一致**（配方确定性得证）；审计 shell 0 / misassign 0 全过；权威基准 `gaoxiong_7`/`lingbo` **PASS**（偏差中位 0.0）、`aerbien_3` 由 **FAIL→WARN**（曲线 445/640→**640/640**、关键帧不一致 195→**0**、偏差中位 **2.88→0.128**、>0.5 占比 95.1%→40.8%，仍超 12% 线：该模型 Unity 侧键稀疏、线性近似损失大，属严格改善不是回退）；`z46_3` 参考库无此模型。单模型 ~3.5s → 全量 269 约 **20 分钟**。
   **建议顺序：先做本项全量重导，再重标定 `hit_verify` 基线**（重导会改判定区数量与动作，顺序反过来基线要重测两遍）。
   **待做（按序）**：
   1. 备份：`Output/Live2D/*/motion/` 整目录 → `Output/_OLD_bak/l2d_motion_pre_21_<日期>/`（Output 不在版本控制内，**必须备份**）。
   2. 全量重导：`L2D_MOTION_LINEAR=1 L2D_MOTION_EMIT_CONST=1 py -3 scripts/extract_motions.py --all`
      ⚠️ **必须用 `L2D_MOTION_LINEAR=1`（关键帧+线性），不是 `ABSOLUTE_CP`**——安土实测：线性版对参考版偏差中位 0.0、>0.5 占比 3.8%~9.6%；而绝对贝塞尔版有 88/278 条曲线偏差>0.5、最甚 296 个参数单位（更差）。`ABSOLUTE_CP` 只是留给后续实验的开关，未通过验收。
      ⚠️ 该脚本直接写 `Output/Live2D`，**先用 `L2D_OUT_DIR` 指到临时目录试跑几个模型**，再沿用 `apply_live2d_motions.py`「只换 `motion/` 子目录」的做法换入。退出码非 0 = 有 clip 解出 0 曲线，绝不静默。
   3. 全量补 model3：**换入后**在正式目录上跑 `py -3 scripts/fix_model3.py`（临时目录里没有 model3.json，指过去等于空跑；幂等；本轮新增三项——非 idle 删硬写淡入淡出、idle 拆成 `FadeInTime:2.0/FadeOutTime:0.5`、补 EyeBlink/LipSync 组、补登全部 `Touch*` 判定区）。
   4. 验收：**`L2D_OUT_DIR=<临时目录> py -3 scripts/diag/l2d_ref_diff.py --all` 必须 PASS**（⚠️ 不带 `L2D_OUT_DIR` 比的是正式目录＝自证清白；2026-09-24 前该工具在只含 `motion/` 的临时目录上会**全 SKIP 却退出 0**，三处假绿灯见 `TROUBLESHOOTING.md` §24）（判据：组/曲线零缺失、**关键帧零不一致**、偏差中位 ≤0.5、偏差>0.5 占比 ≤12%）。参考库只覆盖部分模型，404 自动跳过。
   5. 回归：WF-16 五件套全跑，`hit_verify` 基线 **806/807**。⚠️ 判定区从 3 个扩到几十个后 `hit_verify` 断言范围变大，**基线必须重新标定**——先读 §21「与核心三框零重叠」的实测结论再判断是否真回退。
      **2026-09-23 现状：基线尚未重标定。** 本轮跑出的 `821/843` **不可用作基线**——真实断言数应是 **861**（`843 = 262×3 + antu_2 的 57 + 6 个模型被记成 0`），那 6 个「nAreas=0」经核实是**脚手架误读**（8777 服务器当时不在跑，Chrome 返回导航失败页），产品侧这 6 个模型的 HitAreas 都是 3 个。已知的真实待查项是 **17 个模型的 `Body→Special`**（含旧基线里的 `z46_3`）与 **antu_2 的 5 处 57 框内歧义**。判别式与根因见 WF-16 踩坑段。
   6. 派生产物：`make_thumbs.py` 遇已存在文件会 skip（换图必须删旧 webp）；index 若受动作数影响需重跑 `build_gallery_index.py` + `deploy_gallery.py`。
   **换入侧闸门（2026-09-24 加装）**：`apply_live2d_motions.py` 现要求**显式**给源目录（`L2D_SRC_DIR`，也认 `L2D_OUT_DIR`），不给即拒绝；换入前若源目录曲线总数少于正式目录，判为陈旧产物直接拦下（本轮修的是「漏读定值曲线＋空壳占位」，只可能变多）。干跑末行 `曲线总数: 旧 N → 新 M` 是人读的第二道闸。
   **一个已知未决问题**（不要当成新引入的 bug）：
   - 参考版约 **7% 的贝塞尔段无法从 Unity 数据还原**（四种切线候选公式最高只拟合 16.7%，且那是平凡情形）→ 只能用线性弦近似，表现为缓动略少。**这是数据源天花板，别再攻**。
   ~~播完 `touch_idle*` 后判定区集体出画不恢复~~ → **2026-09-23 已修**：非 idle 参数残留复位（`gallery_src/index.html` 的 `paramSets` 登记 + 回 idle 后写回 moc3 默认值），探针 after 出画数回到 53 == before、位移 0；根因与两条踩坑见 §21 末段，可复用做法见技能 `live2d-web-runtime-integration` §3.8/§7.2。
10. ⏳ **Live2D 动作语音：全量导出 + 出声验收 + 技能沉淀（2026-09-23）**
   管线与判据见 **`docs/WORKFLOWS.md` WF-17**，命令语义与实测证据见 **`docs/TROUBLESHOOTING.md` §23**。
   **✅ 2026-09-23 两个闸门都已过**：
   1. **耳朵验收已过**：用户实听确认「点动作有声音」（此前一轮报"完全无声"实为**改完没部署**，见 WF-17 踩坑首条）。
   2. **全量已跑完**：`--all` 覆盖 270 个 Live2D 皮肤 → **253 个命中 ACB 并导出**、**17 个无 ACB**、**0 个"有 ACB 但动作组零交集"**；产物 **5914 个 ogg / 323 MB**，映射表 `Output/gallery_v2/l2d_voice.json` 含 **253 个皮肤**。
   脚本已入库（commit `727fe04`）：`scripts/extract_live2d_voice.py`（新增 `--all` 旗标——原先只认 `L2D_VOICE_ALL=1` 环境变量，用 `Start-Process` 脱离进程起时不继承环境变量，导致第一次"看起来起起来了"实际直接走用法分支 `exit 1`）、`scripts/diag/l2d_voice_probe.py`。
   **仍待办**：① `touch_body→touch_1` / `touch_special→touch_2` 两条别名仍是语义推断，待用户按耳朵裁定（**改映射即可、不必重导音频**，因为文件名用 cue 名）；② **口型未做**（vendored 库无音频驱动口型，需自接 WebAudio 包络写 `ParamMouthOpenY`）；③ **Spine 与静态立绘的配音仍缺**——同一批 ACB 里有 `detail`/`get`/`expedition`/`task`/`profile`/`upgrade`/`feeling1-5`/`present_like`/`title` 等触发名，数据在手未导出未接线；④ 详情页语音归并还依赖那张 719 条的社区 `CV_MAP`（安土都不在表里 → `voices=[]`），可改用 skin id 推导一并修掉。
   **顺带待裁定**：`touch_body→touch_1`、`touch_special→touch_2` 两条别名现为语义推断；`ship_skin_words` 若解出（§22 在途）即可给权威映射。
   **技能沉淀决议（勿再新建）**：自动推荐连发 4 条（`criware-acb-live2d-voice-extraction` / `criware-acb-voice-extraction` / `criware-acb-voice-bank-extraction` / `criware-voice-cue-extraction`）实为**同一份内容的四个副本**，相对 WF-17 净新增仅三点（库原生 `definitions[g][0].Sound` 注入、本库无音频驱动口型、语音表异步到达的首播竞态）。闸门过了之后**并进 `live2d-web-runtime-integration` 新开 §9「动作语音」**，与 WF-17/§23 重复的段落一律改为引用；若坚持独立技能，命名取 #3。⚠️ 该技能住在项目 `.agents/skills/`，而 `skill_manage` 只认用户技能目录 → **须直接改文件**。落笔时修掉两处事实：`-i` 不是"不给就时长翻倍"（本批语音实测无 loop 点），以及探针脚本要先入库才能被技能引用。

---

## 7. 新会话对接指南

新会话发送：
```
我在做碧蓝航线 AssetBundles 解包项目。
进度: D:\Azur Lane Assets\PROJECT_STATUS.md
规则: D:\Azur Lane Assets\AGENTS.md（含文档写入路由表）
当前主线: v2 数据驱动管线（§9）+ gallery_v2（§10）
下一步: [具体任务]
```
要点：静态立绘 / Spine 已由 v2 全量收官，Live2D 动作层已于 2026-09-21 按权威映射重建完毕，**2026-09-23 网页交互层三个根因（命中包含判定 / idle 循环 / V-P 坐标系）已修并回归**。接手前先读 §9 理解「游戏数据自洽、不要猜坐标/不要按位置猜参数名」这一核心结论。**验动效一律看内容**（曲线条数、Id 是否命中参数表、值是否随时间变化），不要只看 `currentGroup`/组名标签——空壳也能"启动"，这个坑已踩过一次（`docs/TROUBLESHOOTING.md` §17、`docs/WORKFLOWS.md` WF-7）。**验交互一律用独立锚点**——合成点击若与被测映射同源会自洽闭环、全绿也说明不了对齐（§20、WF-16）。历史 v1 调试见 `docs/archive/`，一般无需再读。

---

## 8. 技术备忘

**立绘命名**：`{舰名}`默认皮 / `_2`第2套 / `_tex`纹理 / `_n`夜战 / `_hx`换色 / `_rw`人物 / `_bj`背景 / `_front`前景 / `_jz`舰装 / `_alter`改造 / `_hei`黑化。多数脸烤进 `_rw`（仅 ~4% 有独立 face 部件）。
> **⚠️ 语义纠正（用户 2026-09-20 实测确认，别再按字面理解）**：**`_hx`「换色」实为和谐版**（内容被和谐处理后的立绘，不是调色变体）；**`_n`「夜战」实为不显示背景的立绘**（同一皮肤的无背景版，不是夜间场景）。二者都不是"另一套皮肤"。
> **✅ 画廊标签已改准（2026-09-20）**：`build_gallery_index.VARMAP` 由 `{'hx':'换色','n':'夜战'}` 改为 `{'hx':'和谐版','n':'无背景版'}`，重建 index 后 **1746 条皮肤 label 更新**，逐字段 diff 确认**非 label 字段变化 0**、船集合与皮肤集合完全不变、无「夜战/换色」残留。组合态形如 `皮肤2·无背景版·和谐版`。

**Live2D 结构**：`Output/Live2D/{name}/` = `{name}.model3.json` + `.moc3` + `.physics3.json` + `texture_*.png` + `motion/*.motion3.json`。

**PPtr 解析**：`m_Sprite=(FileID,PathID)`；FileID=0 本包，FileID=N → `SerializedFile.externals[N-1]` 的 CAB 名（≠ manifest deps 字母序）。

---

## 9. 当前主线：v2 数据驱动管线 ✅（2026-09-15，取代 v1 攻关路线）

### 9.1 匹配机制（游戏本体权威答案）★核心突破
- `AssetBundles/dependencies`(6.4MB 单包) 内 MonoBehaviour 携带 **86,398 条官方依赖表** → `Output/dependency_manifest.json`。
- 部件→纹理包 = deps + externals；对象定位 = PathID 精确匹配（一包多 mesh 不再错拿）；放置 = 统一 Unity UI 数学（anchor/pivot/sizeDelta/anchoredPosition/localScale 全递归；有 mesh 部件按画框 `mRawSpriteSize` 非等比映射 rect，无 mesh 部件 textureRect 直接拉伸铺满 rect）。
- 逆向关键：新版 bundle header `unity_version` 伪装成 `5.x.x`，真实 `2022.3.62f3` → 需 `UnityPy.config.FALLBACK_UNITY_VERSION="2022.3.62f3"`。静态立绘 = **纯 UI 结构**（RectTransform/CanvasRenderer，无 MeshRenderer），游戏把每个部件位置/大小/anchor/pivot 全写死，合成不需猜坐标。

### 9.2 静态立绘 v2（`scripts/compose_paintings_v2.py`）⚠️
零猜测、零手调。疑难样本 7/7 目视正确；v1 需手调的 feiteliekaer_3 / xili_alter / hailunna_4 现无参数自动正确。表情差分 `--faces all` 输出 `{name}_face{k}.png`。
> ✅ **嵌套容器错位已修（2026-09-18）**：带中间容器（`layers`/`Touch`）的皮肤子层曾被 `layout_all` 仿射多减 `p_local[0]` 甩偏（非 sortingOrder 问题），修复提交 `52782a7`，扫描 85/4486 受影响已全部换入。
> ✅ **i404 型背景缝隙已修（2026-09-19）**：无 mesh 部件误用 `mRawSpriteSize` 当画框致视差背景带压窄，改按 textureRect 拉伸铺满 RectTransform，10 张受影响已换入（见 §6 第 2 条）。注意 painting 本身即半景特写，完整 CG 走 Spine 线。
**全量收官**：4300 → **4486**（补合成 190，成功 186 / 失败 4 为非主皮肤杂项包，已加过滤）。输出 `Output/Paintings_v2/`。

### 9.3 六个系统性根因修复 ★教训（全部代码级、零逐角色参数）
1. 无 mesh 整图部件**双重 Y 翻转** → root 背景层颠倒。修：`arr = A[rect.y : rect.y+h]`。
2. Spine atlas 页纹理需 **`flip=True`**（运行时按行0=顶采样）。
3. Windows 分离进程 stdout 默认 GBK，`print('✓')` 抛错致全量**假失败** → `sys.stdout.reconfigure('utf-8')` + 子进程 `PYTHONIOENCODING=utf-8`。
4. `layout_all` **root scale 只乘子层未乘 root 自身** → 层间比例错。修：局部空间纯 anchor 数学 + 仿射映射世界 + 自身 scale 绕 pivot（负=镜像）+ root 屏幕适配 scale 归一为 1。
5. 无 mesh 部件**误用 `mRawSpriteSize` 当画框** → i404 型视差背景带（记录切分前原图尺寸）被压窄留黑洞。修：按 UI Image 语义 textureRect 拉伸铺满 RectTransform；mesh 部件才用 frame。
6. `rasterize_mesh` **把内容钳死在画框内** → mesh 顶点合法越框的皮肤（kuersike_rw 头部伸出框顶 713px）被裁头、纹理矩形露缝。修：按内容实际 AABB 输出（±2~3 倍框安全钳），越框部分由 render() 仿射照常映射。
> 结论再次印证：游戏数据自洽，所有错位都是解析姿势不对。（完整明细含文件行号与验证样本，见 `docs/archive/PROJECT_STATUS_历史归档.md` 末尾「完整明细存档」。）

### 9.4 Spine v2（`scripts/extract_spine_v2.py`）✅
双结构兼容（内联型 + 分离 `_res` 型）+ 外部页纹理按 deps 补齐 → `Output/Spine_v2/`。全量 **232 主包**完成。skel 3.8.99，皮肤为多部件骨骼（B/M/T）需分层合成。

### 9.5 Live2D 核查 ✅（2026-09-21 结论已更正）
266 个 live2d 包本地零缺失、自包含。**旧结论「剩余仅 motion 质量（§2.5 B 类 12 模型）」是错的**：
motion 大面积失效源于我们自己的解析器（帧 0 护栏 + 曲线名按位置猜），不是资产缺口；
已按 `genericBindings`/`crc32` 权威映射全量重建（见 §2.5 与 `docs/TROUBLESHOOTING.md` §17）。
资产层真为空的只有 7 条 clip（`effect` / `idle11` 一类占位动画）。

---

## 10. 本地资产浏览平台 `Output/gallery_v2` ✅（2026-09-15）

- **形态**：本地网页（源 28GB / Paintings 15GB，上线不现实），参照 l2d.su，中文名展示 静态立绘 + Spine + Live2D + 语音。
- **数据**：`build_gallery_index.py`（合并四类 + `ship_name_map` 拼音→中文 812 条 → `index.json/js`；Spine 皮肤附 `cg` 字段指向 `CG_v2/`）+ `make_thumbs.py`（Paintings_v2 + CG_v2 → 380px WebP，CG 缩略图 `<stem>_cg.webp`）。结果 954 船 / 4489 皮肤 / spine 231 / CG 231 / live2d 256 / 语音 268。
- **前端** `index.html`：网格懒加载 + 搜索/阵营/舰种/稀有度筛选 + **类别分段（全部/舰船/剧情角色，主网格按 `category` 分区渲染各带小标题计数）**；详情四标签。「静态立绘」对 Spine 皮肤默认展示全屏 CG（可切换回 painting 原件），支持**滚轮缩放(光标锚点)/拖拽平移/双击100%/全屏浏览/复位**；Spine 标签 `vendor/spine/spine-all.js`(3.8) 分层 WebGL 播放（相机视口/动画过滤已修，**支持全屏**）。服务器统一响应 `Cache-Control: no-cache`，改版后浏览器不再吃旧缓存。
- **源码治理**：画廊前端源码在**仓库内 `gallery_src/`**（唯一权威版本），改完跑 `scripts/deploy_gallery.py` 同步到 `Output/gallery_v2/`（运行目录，gitignore）。CG 导出页 `cg_export.html` 同样入 `gallery_src/`；服务器 `_gallery_server.py` 提供 `POST /save_cg` 落盘接口，`--export` 参数直开导出页。
- **运行**：`启动资产浏览器.bat`（→ `_gallery_server.py`：8777 端口 + `allow_reuse_address` + 端口占用即复用 + 结尾 `pause`，杜绝闪退）。file:// 下立绘/语音可看，Spine `fetch` 被 CORS 拦需走 .bat。
- **限制**：~~Live2D 暂只显示贴图~~ **已接动作播放**（2026-09-20，`vendor/live2d/` 三脚本本地就位，见 §6.7）；Live2D/Spine 标签均需走本地服务器（file:// 下 fetch 被 CORS 拦）。

---

> **历史归档**：v1 时代攻关路线、多部件合成已知问题清单（Bug#1-#4）、7-30/7-31 修复记录、bj 背景层专项、调参工具 v3-v6 会话流水、旧 Spine Viewer 调试史 → 全部见 `docs/archive/PROJECT_STATUS_历史归档.md`。
