# PROJECT_STATUS.md 外迁归档（2026-09-26）

> 逐字从 `PROJECT_STATUS.md` 迁出，**不要编辑本文件**（编辑会让"零信息丢失"失效）。
> 迁出原因：AGENTS.md「PROJECT_STATUS.md 体量红线」——逐日会话记录、已解决 bug 的长篇排查、调参流水
> 不得留在状态文档；本文只保留当前进度快照。
> 同日对应的**结论性知识**都在 `docs/TROUBLESHOOTING.md` §17~§46 与 `docs/WORKFLOWS.md` WF-6/7/14/15/16/17/19/20，
> 本文件只是原始流水的备份，供追溯当时怎么做的、当时错过什么。

## 迁出清单

- `A1 历轮会话流水` — 原第 15-39 行（25 行）
- `A2 2026-09-21/09-22 交接状态两段` — 原第 42-43 行（2 行）
- `A3 §3 里那段 2026-09-20 磁盘清理与硬链去重流水` — 原第 136-136 行（1 行）
- `A4 §6 质量复核 第 1~4 条` — 原第 175-178 行（4 行）
- `A5 §6 质量复核 第 6~12 条` — 原第 190-224 行（35 行）
- `A6 既有待办 第 7 条` — 原第 234-296 行（63 行）
- `A7 既有待办 第 9 条` — 原第 298-318 行（21 行）


---

<!-- A1 历轮会话流水（09-20~09-26 上午：硬链/vendor 台账/覆写事故/9 bundle 换入/坐标三连修 等） | 原第 15-39 行，共 25 行 -->

> 上一轮（17:10）：**画廊前端/复刻缺口两处静默失败源一起封掉，并当场抓到护栏自己的漏洞** → ① `gallery_src` ↔ `Output/gallery_v2` 全部 4 文件改为硬链接（`deploy_gallery.py` 三态化：默认 copy 修复 / `--check` / `--relink` 换链，脏文件自动跳过），改正本即刻生效，「改了等于没改」这类失效物理消失。**但上线 3 小时就被一次整文件写回断开**，而当时 `--check` 只比内容 → 打印"已一致（独立副本）"后 `exit 0`，**对唯一会真实发生的失效给绿灯**；判据已改为结构性（4 个文件必须全同 inode，断链即 `exit 1`），并立"改正本一律原地编辑"的约定进 AGENTS.md 第 1 条。`index.html` 现处"已断链、内容仍一致"，待并行会话提交后 `--relink` 补。② vendor 四库复刻缺口封台账 `gallery_src/vendor/MANIFEST.json` + `scripts/fetch_gallery_vendor.py`（3 库 URL 当日按 sha256 命中；**哈希与字节数双双对上才落盘**），⚠️ 唯 `spine-all.js` 无可用哈希源、待拍板；③ pre-commit 加闸 1「暂存区出现 `Output/`、`files/` 即拦，`DOC_CHECK_SKIP` 也绕不过」+ `.gitignore:Output/` 写明真实理由。全部含失败分支实测：写入穿透、断链报红、拒绝覆盖、合成台账四条、hook 四用例、真实 8777 回环。提交 `8bc301f`/`d5b784a` 已双推（GitHub 的 ssh:443 被重置，改 HTTPS 显式 URL 推通）。§43 / WF-16。）更早一轮：**用户再报两例** → ① 本宁顿 Live2D「话没说完就被掐回初始态」= 语音挂在 `definitions[g][0].Sound` 上、被库按"下一条动作 dispose 上一条"托管，动作 5.17s 一到就把 9.24s 的 ogg 在 `currentTime=4.48s` 处 pause；动作时长本身忠实（`Meta.Duration`==曲线末帧==源 clip），改由页面自持 Audio 解耦（§41 / WF-17 追加）。② 阿罗芒什 Spine 缺下半身 = **viewer 与 CG 导出从未调用 `setSkin`**，而 spine-ts 3.8 的附件时间线经当前 skin 解析；新增全量扫描 `spine_skin_scan.py` 测得 **331 part 中受影响 4 个**（yunlong_2 缺 69 槽 / feiteliedadi_5 52 / 阿罗芒什 47 / 月城II_4 14），按"动画跑起来后曾挂上附件的槽位数"自动选 skin + 加皮肤下拉（§42 / WF-14 追加）。另修了回归工具自身两类假失败（固定等待不够 + 900ms 读异步 currentGroup），WF-16 五件套 2/3/4 项全绿，第 5 项全量点击在跑。更早：Live2D 贴图索引错绑 5 例修复 + 269/269 闸门 + 目视 26/269。）
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


---

<!-- A2 2026-09-21/09-22 交接状态两段 | 原第 42-43 行，共 2 行 -->

> **【2026-09-21 交接状态】§6 待办 1~10 全部闭环**（上一轮提交 `0c6bb47`→`4154da9`；本轮 Live2D 动作重建提交 `03d65ef`→`c97b644`）。① **§6.9 脸部白块换入 34 张**——扫描 2221 候选得 35 洞 → 对比图交用户过目 → `leiniya_wjz` 经确认排除（靠**收紧门控**自动排除，不写例外名单）；端到端校验：34 张内容一致 / 68 URL 200 / 其余 4454 张 mtime 未变（备份 `Output/_OLD_bak/facefix_20260920/`）。② **story_review 勾选落地**——31 条自机进 `EXTRA_SHIP` 且白名单优先于塞壬分支，ship 850→881 / story 158→127，非类别字段零回退。③ **§6.7 Live2D 关闭并追加两轮修复**——动作播放（`startMotion` 传参陷阱）+ **按部位点击触发**（HitAreas；全量 260 皮肤 **767/768**、259/260 模型全中，残留歧义 1 例 `z46_3` 已记录）+ 交互层三修（裸滚轮劫持页面 / 点空白乱播兜底 / `pointercancel` 缺失致拖拽卡死）。④ **§8 变体后缀语义纠正**——`_hx`=和谐版、`_n`=无背景版，画廊 1746 条 label 改准、逐字段 diff 无意外变化。⑤ **治理沉淀**——新增 `docs/WORKFLOWS.md` **WF-15 游戏版本更新增量重跑**（含承重文件白名单）；13 个可复用诊断工具从 `.diag` 归档入 `scripts/diag/`；`.diag/` 正式 gitignore；AGENTS.md 加「清理前核对白名单」硬规则；技能 1 新建（`live2d-web-runtime-integration`）+ 3 更新（headless-cdp / unity-assetbundle / safe-pipeline）。⑥ **（同日第二轮）Live2D 动作层根因重建**——查明 57% 动作是空壳 + 其余曲线名全错位（两处静默失败，非前端问题），按 `crc32("Parameters/<GO>")↔genericBindings` 权威映射全量重生成并换入（曲线 179,072→856,870，审计 0 空壳/0 错位），并把官方换装拼接层 PartOpacity 曲线写进 motion3.json；判据从「动作启动了」升级为「曲线有内容且值在变」。⑦ **（09-21 第三轮）9 个未还原 bundle 已重建到临时目录、按用户决定暂不换入**——`.diag/l2d_new9/` 里 852 clip / 0 空壳 / 0 错位 / 87,266 曲线，随时可换入（见 WF-7 第 7 步）；同轮查出**「4 个模型无判定区」是误判**（见 §6.11）。**在途 0 项**（09-21 的「9 个模型换入」「HitAreas 规则修正(§6.11)」及「`l2d_sweep` 逐条驱动全量浏览器回归」均已于 2026-09-22 完成）。
> **【2026-09-22 已换入】9 个从未还原的 live2d bundle 正式换入 `Output/Live2D/`**（benningdun_2 / bunao_3 / feiteliekaer_4 / gangyishawa_3 / guanghui_9 / pulimaosi_3 / sebao_2 / shi_3 / wuzang_4）：从 `.diag/l2d_new9/` 逐目录复制（**全新目录零覆盖**，复制前后逐文件 sha256 一致，901 文件 / ~487MB）→ `build_gallery_index.py` 重建 index（临时目录 `GALLERY_OUT_DIR` 先建、与换入前基线**逐字段 diff**：ship/skin 集合不变、非 live2d 字段变化 **0**、仅 9 卡各 +1 `live2d`/`live2dBase` + 计数 260→269，随后发布到 `Output/gallery_v2/`，旧 index 备份 `Output/_OLD_bak/gallery_index_pre_l2d9_20260922/`）→ `make_thumbs.py` 增量 **0 重建 / 4719 skip**（正图未动）→ 浏览器内容判据抽验。**关键验证教训**：运行时把每条 idle 解析成 `isLoop:false`（全 269 模型一致的既有管线特性，非本轮引入），idle 只播一次即回静帧——若按旧法等到 ~12s 后再两次快照比对，短 idle(5~8s) 已播完 → 假报 `moved=0`（本轮一度据此**误判 bunao_3/guanghui_9 坏了**）。改为**播放窗口内高频密采全参数、取跨帧 min/max** 后：**9/9 模型 idle 均驱动参数**（benningdun_2 45 / bunao_3 57 / feiteliekaer_4 90 / gangyishawa_3 58 / guanghui_9 143 / pulimaosi_3 50 / sebao_2 29 / shi_3 75 / wuzang_4 144 条参数值变化），全绿。⚠️ 注：§6.7「260/260」为换入前口径，现 269；新 9 模型的 HitAreas 仍是占位 Id（点部位走兜底），真判定区待 §6.11 修。`.diag/l2d_new9/`（467MB）已冗余，可清理。


---

<!-- A3 §3 里那段 2026-09-20 磁盘清理与硬链去重流水 | 原第 136-136 行，共 1 行 -->

（v1 旧产物与调试目录已归档/清理；`.trash` 内旧 bug 产物已于 2026-09-16 彻底删除，释放 8.9GB。**2026-09-20 清理**：`.diag` 内 17 个 headless Chrome profile 缓存 + 历次立绘修复的一次性调试输出目录 + 本次 B 会话临时文件、`Output/_OLD_bak`(三次修复换入前备份 918MB)、`Output/` 下 bj_*/layout_2b/run_v2_full.*.log 零散件，共 **126 项送回收站、释放 7.3GB**；errors 流水并入 `docs/ERRORS.log`。保留 azdata 权威缓存/`dependency_manifest_385.json`/`run_cg_export.py`。重复资产(Paintings_v2 50 个逐字节重复 252MB 等)因被画廊按文件名引用，本轮未动。**2026-09-20 硬链接去重**：Paintings_v2/Paintingface/CG_v2 内 519 组逐字节相同文件（`npcX`==`X`、部分`_asmr`/`_hx`==本体、`left/mid/rightchicheng_alter` 三视图同图等），531 个重复文件转 NTFS 硬链（`os.link`，失败回退 copy），物理实省 **~358MB**；路径与内容不变，逐文件 nlink+sha256 校验 + 起 http.server 对全部 531 路径 GET 200/长度/哈希三重核对全通过，画廊引用零破坏。）


---

<!-- A4 §6 质量复核 第 1~4 条（已闭环：容器错位/i404 缝隙/mesh 越框/Spine+CG 导出） | 原第 175-178 行，共 4 行 -->

1. ✅ **静态立绘「嵌套容器错位」（2026-09-18）**：`layout_all` 仿射多减 `p_local[0]`，修 `52782a7`，85 张换入（备份 `Output/_OLD_bak/affected_20260918/`）。
2. ✅ **i404 型「背景缝隙」（2026-09-19）**：无 mesh 部件误用 `mRawSpriteSize` 当画框，改 textureRect 拉伸铺满 RectTransform，10 张换入（备份 `framefix_20260919/`）。painting 本身即半景特写，完整 CG 走 Spine 线（第 4 条）。
3. ✅ **mesh 越框裁头（2026-09-19，用户报「库尔斯克缺块」）**：`rasterize_mesh` 把内容钳在画框内，而 mesh 顶点可合法越框（kuersike_rw 头部伸出框顶 713px）→ 改按内容 AABB 输出（安全钳 ±2~3 倍框）。扫描 4490 包：84 皮肤越框、**55 张画面实际变化已换入**（29 张越框部分全透明逐像素同旧图；5 张画布按预期变大找回内容）；对照 5 皮肤 maxdiff=0。备份 `Output/_OLD_bak/meshfix_20260919/`，清单 `.diag/mesh_overflow.txt`，对比图 `.diag/cmp_meshfix/`。
4. ✅ **Spine 动态 + 全屏 CG 导出（2026-09-19）**：viewer 三修（相机视口 `camera.setViewport`、`my` 变量遮蔽 TDZ、0 秒空动画过滤+默认 normal）+ JSON 骨架支持；`cg_export.html` 两段式构图批量导出 **231/231** → `Output/CG_v2/`，画廊默认展示 CG 可切原件，缩略图 `<key>_cg.webp`。详见 WORKFLOWS WF-14。


---

<!-- A5 §6 质量复核 第 6~12 条（已闭环：剧情分级/动作播放/missd/脸白块/动作层重建/HitAreas/交互三连修） | 原第 190-224 行，共 35 行 -->

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


---

<!-- A6 既有待办 第 7 条：晶环联盟码 + sharecfg 逆向攻关全日志（§30~§37 / WF-19 / WF-20） | 原第 234-296 行，共 63 行 -->

7. ✅ **阵营「晶环联盟」码已定：nationality = 12（2026-09-25 闭环，取证过程见 §37 补；本条历史保留在下文）**：
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
   - ✅ **2026-09-25 (21)~(23) 轮：`sharecfgdata` 文法已破，台词中文明文到手。** 全文见 **`docs/TROUBLESHOOTING.md` §33**，操作与判据见 **`docs/WORKFLOWS.md` WF-20**。
     (21)(22)：四模式 `%4` 全部逐指令落成 → `scripts64` 整包 UnityPy 可开 → 发现 UnityPy `TextAsset.m_Script` 是**有损** str（UTF-8 `replace`，高字节全毁）⇒ 改走 `get_raw_data()` 无损取法，**774 个 sharecfg Lua 表已全量落盘** `.diag/sharecfg_re/cfg_json` 同级 `lua_out/`（§32）。
     **(23) 本轮**：突破口是**公开同族实现** `Fernando2603/AzurLaneDataExtractor`（0-star，直接离线读 `sharecfgdata/<表>`）——二十轮统计攻击没读出来的文法，一次外部检索命中。按其"格式事实"**自研** reader（`tools/sharecfg_re/37_parse_sharecfgdata.py`；该仓库**无 LICENSE ⇒ 不得 vendor 源码**）：
     容器 = **记录帧 `ULEB(len)` + 假 LuaJIT BC 头 + 平铺 kgc 常量流**；tag `00`nil/`01`表/`02`true/`03`ULEB int/`04`double/其余字符串；**字符串 = `ULEB(长+5)` + 逐字节 `^(255-i)`，i 每串归零** ⇒ 二十轮来的「0x80–0xBF 高字节游程」= ASCII 套递减掩码，既非压缩亦非文字编码。
     **三条独立判据全过**：① 帧覆盖**残差 0**（`ship_skin_words` 5,615,904/5,615,904、`ship_skin_template` 4,066,129/4,066,129，空记录 0）；② 解出的 32+1 个高频字段与外部人工 schema **逐项吻合**（连联动扩展键都在）；③ **值级交叉验证** `drop_descrip` 非空 2565 条 → **93.6% 整串命中**独立基准 `azdata…skin_template.desc`（差额归因 385 vs 381 版本差）。产物：**2601 行台词 / 40,897 个含中文字段值**。
     **「70 倍体积差」这个提问本身是错的**：Lua 侧同一掩码解出的 12 条串是 `cs/base/all/__namecode__/__stream__/confNEO/__name/<表名>/setmetatable/rawget/pg` ⇒ **Lua 侧是"读取桩"，磁盘侧才是数据本体**；且磁盘侧只有 32 个文件 vs Lua 侧 774 张表，比值 3.0~496 无恒定关系 ⇒ "压缩/编码膨胀"整类解释当场出局。
     **需更正的两条旧否证**：§31「不是 LuaJIT 字节码」只对磁盘侧成立（Lua 侧按 `Azurlane-LuaHelper` 是**真 BC + 指令首字节 256 项 S-box 置换**，我方探针按标准 tag 走必然 0 命中）；§32 的 GB18030 判否结论仍对，但真理由是"数据在掩码之下"，不是"随机字节的正常产出率"。
     ⏳→✅ **唯一剩余缺口 = 嵌套字段的装配**（`smoke`/`bound_bone`/`couple_encourage` 在常量流里是打散分片，装配关系写在假 BC 指令区 4B/条，第 2 字节 `ff→fe→fd→fc` = 栈回引距离）⇒ **`ship_skin_template` 逐字段验收（`--verify`）目前 id 交集 0、只解出标量字段**，需要解这套栈码（有 2863 条已知答案当校验集）或走 S-box 路线。 **（本行的「id 交集 0」已被下面 B 段推翻，保留以免重犯）**
   - ✅ **同日 B 段：帧模型全库成立 + 原验收判据对标量字段已达标**（细节见 `docs/TROUBLESHOOTING.md` §33 追加段）。
     ① `--all` 跑完 32 张表 **140 MB / 220,568 条记录，帧覆盖残差 32/32 全为 0** ⇒ 帧模型不再是抽样结论。
     ② **验收**：`ship_skin_template` **2863/2865 条记录的 id 命中基准**（多出的 2 条 = 385 新增皮肤），
        **标量 138,669 对 = 直接一致 94,443 + 缺键取默认 44,190 + 不一致 36 → 一致率 99.974%**；
        36 处逐条看过全是 **381 快照 vs 385 设备** 的内容差（`name` 标枪→`PINKLOVE★Heart Lancer`、`desc` CL-12→CL-13、`prefab` `_3`→`_4`）⇒ **标量部分验收已闭环**。
     ③ 三条新硬判据：**`kgc` = 常量区顶层条目精确条数且末条必须停在记录末**（可把偏差定位到第几条）；
        **`01` 按位置分义**（顶层=表头、值位=bool false；证据 `01`+`19` 恰为 "spine_offset_profile" 的长度字节）；
        **空值不落盘**（31.9% 的字段对是"键不存在=取默认值"，混算会把一致率假压 30 个点）。
     ④ 缺口精确化：**只有 21 个容器字段名（占字段对 10.3%）的值不内联**，装配关系在假 BC 指令区；
        参考实现自己也没解（源码注释 "SchemaReader is not gonna work with op codes"），它靠**人写字段表 + 按键定位取值**。
        ⇒ 下一步二选一：**(a) 解那套 4 字节栈码**（一次性通吃 21 个字段）或 **(b) 只给要用的表写字段表**（便宜、够用）。
     ⑤ 导出层已换成与 `--verify` 同源的「键定位 + 只接受标量」路径（`--scalar-all --yes`）并做**逐表改前/改后对比**：
        **零回退**（没有任何一张表的含中文行数下降），含中文行合计 **42,959 → 69,435（+62%）**；
        `barrage_template_1/2/3` 从 0 字段救回 17 字段；`ship_skin_template` 含中文 0→2860 行、
        `expedition_data_template` 0→16133、`world_chapter_template` 0→643；`ship_skin_words` 新旧逐指标同数（2601/2569/93.6%）。
        已知限制（见 §33 末）：**词表是超集**（中位字段数可 > 真实字段数，多的是跨记录共享的值串代号），
        权威字段表只能用基准键或人写字段表；**21 个容器字段仍只读到第一片**。
   - ⚠️ **2026-09-24 进展（未破解，但问题重新定性）**：① "整体加密"这个前提**被证伪**——单文件内 16 字节块重复数百次（iid 期望 1e-6）、头部是可解的 4 字节记录 + LEB128，收敛为「**明文索引 + 逐字段变换**」；② 密文侧全部榨干且**每条都配对照**：已知明文逐表自撞（4634 串 × 4 编码）0 命中、跨表共密钥流（实测 1.84% vs 零假设预测 1.904% → 我上一轮的"存在共密钥流"是阈值松造成的假信号）、段内恒定密钥（差分签名，阴性对照同 0）、短周期 XOR（p=2..12 可分求解）、标准压缩按记录边界试解压、ECB/替换 全部出局；③ C# 零解密已由**机器码**证实；`www()`（RVA `0x3D9CA20`）经 `--xref` 查明**全库唯一调用方是 `LuaScriptMgr.Load`**，其产物经 `LoadABFromBytes` 变成 **AssetBundle** → 判据"输出须含 `UnityFS`"**成立且正确**（本轮一度误判它"不可达"，同日已推翻，教训见 `TROUBLESHOOTING.md` §28）；`www()` 实为三段：按末 4 字节取尾段 → `state=235` 反馈流 → **另有 TEA 族 Feistel 解头 8 字节，密钥是 `Array::New(0x13)` 的 19 个 int32（76 字节内联，(15) 误记为"19 字节"）**；盘上 `scripts64/32` 经 68.3 万个自洽候选全量反解确认**不是 www 的输入**（⚠️ (18) 轮限定：这条只对"把整文件当 235 流的尾段容器"成立；其**头 8 字节确实是那条 TEA 支的输入**（同一算法同一密钥解出 `UnityFS`），但整文件末 4 字节读出的长度不自洽 ⇒ 走的是哪个投递路径仍未定，见上），新事实：32 张配置表**公共后缀恰 11 字节**（固定 Footer 非长度）；④ adb 旁路封死（进程 fd 直接指向 `sharecfgdata/`，无解密缓存；设备与本地 md5 一致=9.7.385；**`su` 可得 uid 0**）。新增 `08`~`15` 号工具（反汇编器 + 6 个探针）。~~**待用户放行**：进程内存取证~~ **已放行并于 09-24 跑过四轮**（拿到明文但均非从容器解出，见 `tools/sharecfg_re/README.md` (7)~(16)）；同日新增 `16`~`26` 号工具，主线已收敛为「查 `sharecfg/<表名>.lua` 是否经 `LuaScriptMgr.Load` 读入」。
   - 🔎 **2026-09-25 推进一半（见 §34）**：阵营名**不是表字段**，而是 `gametip` 里一段按数字 id 索引的短文案（`1200 东煌 / 1201 撒丁帝国 / 1202 北方联合 / 1205 自由鸢尾 / 1206 维希教廷 / 1207 鸢尾教国 / 1210 KizunaAI / 1211 hololive / 1213 偶像大师 / 1215 SSSS / 1218 META / 1219 闪乱神乐 / 1224 danmachi / **1226 晶环联盟**`）。但 `nationality` 码→这段 id **不是位置对应**（码 1=白鹰、3=重樱、97=`·META`、101=海王星…）；**5 个码全部定名（2026-09-25 用户按舰名裁定 + 我按 gametip 文案号对齐）**：`12`=晶环联盟、`99`=塞壬、`101`=联动-超次元游戏海王星、`104`=联动-KizunaAI、`117`=联动-尼尔：自动再述；已写进 NATIONALITY 并重写 ship_meta（逐字段比对仅 faction 变 2 处、删除 0）。`晶环联盟`=文案号 1226，最可能对应码 12，但这是推断、未替你写死。另 `world_port_data.port_camp` 反推这条**已否证**（同一个 camp 同时给出白鹰/皇家/北方联合）。原方案"从游戏配置解析阵营名表"仍不成立——**没有码→名的表**。
   - ✅ **同轮顺手解掉本子项的"385 新皮肤归属"**：盘上比 381 基准多 2 条并已读出全文——`101267 金月桂香`(painting `aierdeliqi_9`, group 10126, CV 54)、`101532 幽幽桥上，坏坏来袭！`(painting `mile_3`, group 10153, CV 446)。
   - 现状维持：ship_meta 前端仍归「其他」。同理受影响：385 新皮肤在 381 快照无记录，归属也卡在同一决策上。
   - 不受影响、可独立推进：§6 交接点 B→C→D 主线；以及「385 变更美术的定向重建」（立绘/Spine/Live2D 包本身是明文 UnityFS，已同步在手）。**（2026-09-20 已完成，见头部）**


---

<!-- A7 既有待办 第 9 条：Live2D 动作全量重导的已完成 runbook 与旧基线讨论 | 原第 298-318 行，共 21 行 -->

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


---

<!-- A8 头部被取代的两段轮次摘要（同日 13:20 那轮：语音 v2 落地 + 叠脸换判据；09-26 那轮：Spine 取景连修两类 + CG_v2 全量重导）——结论已在 §45~§49 / §2.6 / WF-14 / WF-21 | 原第 14-29 行，共 16 行 -->

> 上一轮（同日 13:20）：修两条待办 —— ① **语音 v2 落地**（前端接线 + 全量导出 3995 皮肤 / 843 包 / 39,531 音频，
>   零回退闸门通过；"走设备补取缺包"已否证，见 §49）；② **叠脸门控换判据**（`moermansike_2` 灰梯形是源纹理占位块，
>   新判据在 47 个目视裁定样本上 47/47 全对，见 §48）。
> 更早轮次：语音覆盖面取证与 v2 管线入库见 §47 / WF-21；**Spine 取景连修两类 + CG_v2 全量重导** →
> ① `boundsOf` 把"挂了附件"当成"会画出来"：整屏闪黑/闪白遮罩（最大 32967×29970 单位、setup 与整条
> 21s 动画的 41 个采样点上 alpha 恒为 0）一个像素不落却决定取景框，全库 **13/328** 受影响、最大 9.6 倍
> （四万十画面长轴占满 0.157→0.842）。② 同日再修**不透明纯色巨幕**（黑底板 alpha=1、真的在渲染）：
> 判据换成"区域纹素 × slot 颜色后有没有非近黑落笔"，全库再修 **17/325**（最大 2.79 倍；安土、阿罗芒什
> 从"一大片黑里嵌一小块"变成铺满）。两轮都是 12~28 个皮肤逐个开真实弹窗截图**逐张看图**，
> 对照皮肤指标**逐字相同** = 零误伤。CG 导出页接同一套判据，备份 234 张（md5 全等）后跑 3 个样本
> （`2b_2` 逐字节相同、安土内容占满 0.372→0.917、阿罗芒什 0.351→0.826），**已按建议全量重导：
> 234/234 完成 0 失败，64 张变化 / 170 张逐字节相同，逐张量内容占满 → 变好 19 / 持平 45 / 变差 0。
> **三条否证入库**：判据若问"整条动画里曾否可见"，在阳性对照上等于没修；首帧 `readPixels` 在弹窗里会把
> mojiaduoer_5 放大成一屏模糊色块；`fill` 指标会被纯黑巨幕顶成满分（必须同时看 `fillInk`）。
> 另把怨仇 mojibake 的归因**再更正一次**：它写在日志原始字节里（`0xFF00+原字节`），是浏览器内 skel
> 字符串解码路径产出的，不是我终端的 GBK 假象。上一轮（用户三问 + CG 全量重导 234/234）见 2.5/2.6。）


---

<!-- A9 头部三段被取代的轮次摘要（09-27 18:50 台词正文接画廊 / 18:10 陈旧立绘换入+语音裁定 / 奇尔沙治判定区幽灵标签与 Touch* 停放位）——结论已在 §51~§54、§6 第 10/12/13 条与 WF-22 里 | 原第 17-27 行，共 11 行 -->

> 上一轮（同日 18:50）：**台词正文接进画廊 + 两个全局开关 + 「全屏没字幕」已修** ——
> 三格共用底部字幕条**逐字**对齐、点立绘=出声+上字幕、「点击出声 / 显示台词」两条独立可关（localStorage 持久化）、
> `voiceCount` 口径换成 `skin_voice`/`skin_words`（268→860 组船，**已换入**，备份在 `Output/_OLD_bak/gallery_index_pre_talk_20260927/`）。
> 见 **§54 / WF-22 / §6 第 13 条**。
> 上一轮（同日 18:10）：**9 张陈旧立绘已全数换入、语音 84 类已裁定关闭** —— 全库 4488 张「盘上 == 当前管线」不变式恢复，普查工具与换入工具均入库（§52/§53）。再上一轮 —— 
> ① 用户报"奇尔沙治皮肤2 角落里有判定区根本点不到"。真因是 `drawAreas` 把标签 x 无条件夹进视口，
>   于是画布外几千像素处的按钮把**名字**贴到了屏幕右边缘；现多边形仍按 `__L2_HITUSE()` 全画、
>   标签只在框与视口相交时画（新增同源判据 `__L2_HITSHOW()`）。命中链路与 `model3.json` 数据一字未动。
> ② **旧结论"出画的 `Touch*` 是编辑器遗留停放标记"作废**：逐动作组实测证明它们是**换装/互动按钮的停放位**，
>   播对应动作时随部件进画面才可点（`qiershazhi_2` 静止态 4/26 → 播 `idle1/main_*` 时 7~10 个）。
>   换装的落地形态 = 各 clip 用定值曲线锁住 `TouchSiwa`/`Paramaixin` 这类开关参数。详见 **§51**，待办见 §6 第 12 条。


---

<!-- A10 头部被取代的两段轮次摘要（09-27 21:40 头黑换入 48 张 + 敦刻尔克纠正）——结论已在 §55/§56/§9.3 第 7 条 | 原第 3-16 行，共 14 行 -->

> **生成时间**: 2026-09-27 21:40（同日续：**静态立绘「头部发黑」根因修掉并换入 48 张** ——
> `parse_painting` 从不读 `GameObject.m_IsActive`，于是把游戏里**关着**的层一律画上去：
> `shadow` 纯黑剪影 26 处（= 用户报的头黑）、`shop_hx`/`*_shophx` "NOT ABLE TO DISPLAY" 遮挡条 60+ 处、
> `chicheng_alter_rw1..4` 备用画法 16 处。全库 4488 张里 **125 张命中 → 只有 48 张画面真的会变**
> （73 张的白条本就被 `is_lighting` 挡着 ⇒ **命中数 ≠ 换入数**）。旁证：`_n`（无背景版）的 `bj` 节点
> 恒 `m_IsActive=False`，与用户 09-20 纠正的语义完全对上 ⇒ 这是游戏的真开关，不是启发式。
> 两条硬护栏：**`face` 槽豁免**（它恒关、运行时才激活，是 §48 叠层的输入）、
> **全层关闭的 4 张不清空**（`qiye_4`/`kelifulan_4`/`qiye_dark_memory`/`unknown2_memory`，见 §6 第 15 条）。
> 零回退对照 12 张逐字节全等；换入走 `painting_swap_in.py --break-hardlink`（赤城·改 8 个文件原本
> 两两共享 2 个 inode，过滤后 8 份渲染全不同 ⇒ 必须断链，否则顺 inode 串改共享者），
> 四道硬检查全绿、附带伤害 0、缩略图 ok=48 err=0；**落码后**再把 125 张重渲一遍与已验证结果逐字节比对。
> 同日另修 **敦刻尔克被标成「皇家·驱逐」**：配置表脏行 `stats.id=900106`（name 写敦刻尔克、
> english_name 却是 HMS Vampire）钻了「组内取 min(id)」的空子；改成「先要求 `skin_id` == 组内基皮肤」后
> **970 组只有 1 组改判**，闸门加的是**方向性判据**而非例外名单。见 **§55 / §56 / §9.3 第 7 条**。


---

<!-- A11 §2.5 里被取代的 motion 空壳流水与 9 bundle 换入/贴图错绑/目视 流水（结论在 §17/§25/§40） | 原第 65-69 行，共 5 行 -->

> **2026-09-21 根因重建**：旧产物 5037/8154 条动作是 `"Curves": []` 空壳（`num_keys>100` 护栏误杀帧 0），
> 其余 3117 条**曲线名全部错位**（按"curve idx==参数序号从0连续"取名，实际稀疏）→ 就是"乱飘/乱闪/没反应"。
> 现改为 `genericBindings[i].path == crc32("Parameters/<GameObject名>")` 权威映射 + 贝塞尔 + 结构自检。
> 旧数据备份 `Output/_OLD_bak/l2d_motion_20260921_141226/`。详见 `docs/TROUBLESHOOTING.md` §17。
> ⚠️ 旧结论「B 类 12 模型属 motion 质量、资产无缺口」作废：除上述 7 条外均可解出，是解析器缺陷不是资产缺陷。


---

<!-- A11b §2.5 九 bundle 换入 + 贴图索引错绑 + 全量重导事故 + 目视覆盖 流水（结论在 §25/§40/WF-16） | 原第 74-82 行，共 9 行 -->

> ~~⚠️ §21 的根因修复目前只在 `antu_2` 一个模型上换入验证、其余 268 个模型仍是旧数据~~ → **2026-09-24 已全量落到 269 个模型**（覆写过程有事故，见下一条与 `TROUBLESHOOTING.md` §25）。当时判定的两个系统性错误（贝塞尔控制点写成归一化分数 → 部件各动各的；只读 `m_StreamedClip` 丢定值曲线 → 切动作时参数回不到静止位）现已在全库消除，`aerbien_3` 这类曲线数从 445/640 补齐到 640/640。
> **✅ 2026-09-24 全量重导已落到 269 个模型（含事故记录）**：`antu_2` 样本 104/104 与已验收生产数据逐字节一致 → 全量 `clips 8154 / shell 7（=资产层真为空的 7 条）/ misassign 0 / PartOpacity 79 模型`、曲线总数 **944,136→2,662,615**。**过程有事故**：脱离启动时 `L2D_OUT_DIR` 未被子进程读到，重导**跳过了「临时目录→审计→备份换入」直接原地覆写** `Output/Live2D`（同一条 ps1 里另两个配方变量都生效，机制不可复现）；已核实 `.diag/l2d_new`（269 模型 / 曲线 944,136，与本文档记录的覆写前总数逐字相等）即覆写前状态并复制为 `Output/_OLD_bak/l2d_motion_pre_swap_20260924/` 恢复回滚，闸门补跑在正式目录上，并按「写向一律走 argv」给 `extract_motions.py` 加了 `--out`（不给即拒绝 `--all`）。根因与教训见 **`TROUBLESHOOTING.md` §25**。
⏳ **9 个 bundle 已于 2026-09-22 换入**：benningdun_2 / bunao_3 / feiteliekaer_4 / gangyishawa_3 / guanghui_9 / pulimaosi_3 / sebao_2 / shi_3 / wuzang_4——9 张卡的 `live2d` 字段已进 index.json，`Output/Live2D` 现 **269 个模型**。换入后逐字段 diff 证**非 live2d 字段零变化**（ship/skin 集合不变、仅 9 卡 +9 live2d 项）。
> ✅ **2026-09-26 更正：上面那句「内容判据全绿：9/9 模型加载 + idle 驱动参数」是代理指标假绿灯，作废。** 当时唯一没做的检查是**看画面**，而这 9 个里有 5 个（benningdun_2 / feiteliekaer_4 / sebao_2 / shi_3 / wuzang_4）从换入第一天起就渲染成"几十个部件碎片叠一堆"，用户于 2026-09-26 才报出来。
> **根因**：`model3.json` 的 `Textures` 按 UnityPy 对象**枚举序**落盘，而 moc3 只按**索引**消费它 → 整套贴图错位。全库扫描：乱序的恰好 5 个、坏的也恰好这 5 个，其余 264 个碰巧枚举有序。
> **修法**：`fix_model3.py` 补上归一段（WF-6 三个月前就写了这条决策但从未实现）；闸门 `scripts/diag/l2d_texorder_check.py`（只读检查，乱序退出码 1，`--apply` 才写）现 **269/269 升序**。看图工具 `scripts/diag/l2d_shot_models.py` 新增（走画廊真实入口按 canvas clip 截图）。
> **验证**：5 个修复后逐个目视全部成形（海滩跑车 / 棋盘格卧室 / 暗室桌面 / 后巷 / 演唱会舞台）；对照 `bunao_3`、`pulimaosi_3` 未被写入、截图与修复前一致；语义 diff 证 5 个文件除 `Textures` 顺序外零字段变化，原件备份 `.diag/m3_snap/*.bak_texorder`。详见 `TROUBLESHOOTING.md` §40。
> **目视覆盖 26/269**，按 `(moc3 版本 × 贴图数)` **15 个分桶全覆盖**（修复 5 + 对照 2 + 枚举序最乱 5 + 分桶抽样 14），未发现新增破损。⚠️ 结论边界：这只证"贴图索引绑定这一类故障全库已无残留"，**不等于** 269 个模型没有别的视觉缺陷（其余 243 个未被目视覆盖，非绑定类问题仍按个案查）。
> ⚠️ 另记一条当时的真教训（与画面无关，仍有效）：运行时把每条 idle 解析成 `isLoop:false`（全 269 模型一致的既有管线特性），idle 只播一次即回静；故**动效验证必须在播放窗口内高频采样**，等 ~12s 后两次快照比对会因短 idle(5~8s) 已播完回到静帧而假报 `moved=0`（本轮曾据此误判 bunao_3/guanghui_9，密采证伪）。临时产物 `.diag/l2d_new9/`（467MB）已冗余可清理。


---

<!-- A12 §6 第 10 条 语音 v2 全过程流水（09-23 闸门/①②③④/否证台账/技能沉淀决议）——结论在 §47/§49/§53/§54 与 WF-17/21/22 | 原第 201-251 行，共 51 行 -->

   **仍待办**：① ~~两条别名仍是语义推断，待按耳朵裁定~~ **2026-09-25 已由游戏自己的表证实并升级为表驱动**（`extract_live2d_voice.py` 的 `ALIAS` 改读 `inputs/gamecfg/character_voice.json`）：`character_voice` 给出 `touch→resource_key=touch_1 / l2d_action=touch_body`、`touch2→touch_2 / touch_special`，另有第三条 `headtouch→touch_head / l2d_action=touch_head`（此前画廊无此认知）⇒ 且**同一张表又认出 6 条此前不知道的别名**(`battle→warcry`/`complete→expedition`/`hp_warning→hp`/`mission→task`/`wedding→propose`/`win_mvp→mvp`)，要重导语音映射才吃得到（单皮肤 `--report` A/B 已过，写盘待放行）。见 §35 与 WF-17 追加。② **口型未做**（vendored 库无音频驱动口型，需自接 WebAudio 包络写 `ParamMouthOpenY`）；③ **Spine 与静态立绘的配音仍缺** ⚠️ 2026-09-26 已定位四层根因并备好管线（**全量导出待放行**，见下方"语音 v2 暂停点"）；④ 详情页语音归并还依赖那张 719 条的社区 `CV_MAP`（安土都不在表里 → `voices=[]`），可改用 skin id 推导一并修掉 —— 同日取证：`index.json` 里 **740/1008 组船 `voiceCount=0`**，链条 `CV_MAP(719)→中文名→拼音` 一路漏，而磁盘实有 **938 个船级语音包**（平均 ~35 条 cue/包）。

   **语音 v2 已落地（2026-09-27：①②③ 完成并验收，④ 否证）**：
   - **新脚本已入库**：`scripts/extract_cv_voice.py` —— 按**船级语音包去重**解码（`Audio/CV2/cv-<n>/<cue>.ogg`，皮肤只写引用，不再一份皮肤一份音频），覆盖全部皮肤而非仅 Live2D 目录；产 `Output/gallery_v2/skin_voice.json` = `{皮肤:{cv,idx,src,l2d:{动作组:[路径]},tap:{touch_body|touch_special|touch_head},lines:[{cat,label,f,ev}]}}`。
   - **修掉的系统性语义错**：cue 名尾部 `_N` 是**皮肤序号**（= skin id 末位），旧脚本 `VARIANT_SUF=['','_1','_2']` 当成随机变体全导、前端 `Math.random()` 抽一条 ⇒ 三皮肤船 2/3 概率播到**别的皮肤**的台词，`_9`（改造皮肤）永远取不到。取证见 §47。
   - ✅ **① 前端接线已应用并部署**（2026-09-27）：`git apply scripts/diag/voice-v2-frontend.patch` → 64 增 24 删，
     三格（静态立绘 / Spine / Live2D）共用一条语音条；前端不再 `Math.random()` 抽条目，改为按导出侧选好的本皮肤序号直取。
     `deploy_gallery.py` 已 copy 刷平（改正本必断链，提交后 `--relink` 补回）。
   - ✅ **② 全量导出已跑完**（脱离宿主进程 + 进度行轮询，实测约 75 分钟 / jobs=3）：
     解码 **843 包**（0 失败），产物 `Output/Audio/CV2/cv-<n>/*.ogg` + `Output/gallery_v2/skin_voice.json`。
   - ✅ **②b 定位器修复后增量重跑（2026-09-27 下午）**：原口径"499 无解 = 234 缺包 + 265 快照滞后"
     **整条是误判**——真因是 `azdata` 皮肤表里 `painting` 有大写（`2B`/`A2`/`HDN101`）而磁盘目录名小写，
     查表大小写敏感导致 145 张明明有包的皮肤被判无解（§53）。修完：
     **可定位 3995 → 4140、无解 499 → 354、包 843 → 889、音频 41,193 个 / 2424.5 MB**；
     闸门通过（真丢组 0 / 磁盘缺失 0 / <2KB 占位 0），映射逐字段比对 **消失 0 / 新增 145 / 变化 79**
     （79 全是 `sibling-tier → row`，包号与序号未变）。新工具 `--skip-done` 让这种重跑从 75 分钟降到几分钟。
   - ✅ **已裁定关闭 + 2026-09-27 晚按可救性拆细（§57）**：354 无解 = **196 缺主包**（本地+设备两侧都无，
     只能等下发，§49）+ **36 只有变体包**（音频已用 `voiceExtra` 挂上，**正文齐全但没进前端 ⇒ 新待办**）
     + **55 剥身份后缀才命中**（`_wjz` 无舰装 / `_ex` / `_heihua` / `_idolns` / `_pt` / `_blueprint`；
     **确认不能做**：游戏把画法单独立行的那 29 行既无包也无词，剥后缀 = 拿基础皮肤的台词冒充它的）
     + **54 表里查无此名**（领航员/指挥官等 NPC 皮肤）+ **13 该船无 CV**。
     工具 `scripts/diag/voice_gap_audit.py`（只读，复用 `resolve()`）。旧口径「84 张后缀 / 224 缺包 / 16 无 CV」已作废。
   - ✅ **③ 零回退闸门通过**（`scripts/diag/l2d_voice_diff_check.py`，退出码即结论）：
     (皮肤,组) **3263 → 79323**、皮肤 253 → 3995、**磁盘缺失 0 / <2KB 占位 0**；
     闸门抓到 **4 个"丢组"（全是 `touch_head`）**，逐条查证是**旧表把别的皮肤序号的台词派给了本皮肤**
     （如 `bulaimodun_2`(序号3) 拿到 `touch_head_2.ogg`，那其实是 `bulaimodun_4` 的）⇒ 新表删掉属**修正**；
     已把这条裁定写成**规则**（按 cue 尾部 `_N` 与本皮肤 `idx` 比对）而不是例外名单 ⇒ **真丢组 0**。
     另新增 7 个类别各 252 皮肤（`detail/feeling1-5/upgrade`）。
     **浏览器实播验收**（新工具 `scripts/diag/voice_v2_verify.py`，走真实 UI 路径 + CDP 包住 `window.Audio`）：
     静态立绘 `congmang_2_hei` / Live2D `ninghai_4` / Spine `huanchang_2` 三格各点一次，
     全部 `paused=false` + `currentTime` 在涨 + `err=null`，且**文件名正是本皮肤序号档**
     （`touch_1_1.ogg` / `expedition_3.ogg`）；无语音皮肤 `sairenboss14_jz` 显式显示 🔇。
     WF-16 回归子集同跑：`interact_verify` ALL PASS、`l2d_inspector_verify` 判据全 true、
     `hit_verify --only antu_2,ninghai_4,lafeiii_3` **WIRING=0**。
   - ⚠️ **验收脚本自身差点报假绿灯（已修）**：`let SV` 不挂到 `window` 上，探针用 `window.SV` 取恒为 `undefined`
     ⇒ 三个视图一个都没挑到样本、只有"无语音"那条空洞通过，输出却是一片 ✅。
     通用形状：**探针取不到页面状态时必须让它硬失败，不能让"没测到"长得像"测过了"**。
   - 原计划四步（09-26 记）：① 接补丁 → ② 起全量 → ③ 零回退闸门 + WF-16 → ④ 走设备补取缺包。**①②③ 已完成（上三条），④ 已否证（下条）**。

   - **④ 已否证（2026-09-27，设备侧也没有 ⇒ 这条路是死的）**：那 66 个缺号里 **59 个在设备上连 `cv-N-*` 前缀文件都没有**；
     7 个只有 `-battle/-gift` 变体（本地同样有），真正缺的主包 `cv-N.b` **两侧都不存在**。
     设备 `AssetBundles/cue` 4958 个 vs 本地 4726，设备独有 232 个只属于 `cv-970113` 一个号（+ 一批 bgm/宿舍音），
     **与 66 个缺号交集为 0**。⇒ 对应 234 张皮肤在现有资产下真的无解，只能等游戏下发或走 CDN（**未拍板，暂不做**）；
     画廊侧应显式标"无语音源"而不是静默留空。全过程与否证台账见 **§49**。
     顺带修掉一个承重 bug：`scripts/mumu_sync.py` 里 `subprocess.run(...)` 的 `encoding=` 关键字重复
     → **SyntaxError，该脚本自写下起从未成功运行过**（连 `--help` 都起不来）；
     已把 `py -3 -m compileall -q scripts gallery_src` 纳入收尾验证（此前没有任何环节编译过全部脚本）。
     另有 **265 张**是本地 azdata 快照查不到 `painting` 行（2b/a2 等联动），要靠设备侧更新后的皮肤表才能定位，与补包是两件事。
   - ~~已知缺口 499 = 234 + 265（快照滞后）~~ → **265 那条已作废**（§53）；现为 **354 = 224 缺包（两侧无源）+ 84 待裁定后缀 + 16 无 CV + 30 其它**；289 张只能同船回退取包号，其皮肤序号按"包内实存序号档 − 已被同船占用的"分配（`src=sibling-tier/-base`），分不到退回基础档。
   **顺带待裁定 → ✅ 2026-09-25 全部闭环**：`ALIAS` 已改读游戏自己的 `character_voice` 表（§35/§36），并**全量重导完成**：(皮肤,动作组) **2504→3263（+759 = 253×3）**、文件条目 5914→6948、**丢组 0 / 磁盘缺失 0 / <2KB 占位 0**（374.2 MB）；浏览器实播 `complete/mission/wedding/touch_body` 四组全部真出声（`paused=false`+`cur` 在走+`err=null`，§38）。新增到皮肤的语音类别：`complete`(→expedition)、`mission`(→task)、`wedding`(→propose)。
   **技能沉淀决议（勿再新建）**：自动推荐连发 4 条（`criware-acb-live2d-voice-extraction` / `criware-acb-voice-extraction` / `criware-acb-voice-bank-extraction` / `criware-voice-cue-extraction`）实为**同一份内容的四个副本**，相对 WF-17 净新增仅三点（库原生 `definitions[g][0].Sound` 注入、本库无音频驱动口型、语音表异步到达的首播竞态）。闸门过了之后**并进 `live2d-web-runtime-integration` 新开 §9「动作语音」**，与 WF-17/§23 重复的段落一律改为引用；若坚持独立技能，命名取 #3。⚠️ 该技能住在项目 `.agents/skills/`，而 `skill_manage` 只认用户技能目录 → **须直接改文件**。落笔时修掉两处事实：`-i` 不是"不给就时长翻倍"（本批语音实测无 loop 点），以及探针脚本要先入库才能被技能引用。


---

<!-- A13 §6 第 11 条 摩尔曼斯克叠脸 + 陈旧立绘普查/换入 流水（结论在 §48/§52 与 §2.2 不变式） | 原第 253-282 行，共 30 行 -->

   - **根因不是待办猜的 ②③**：face 槽矩形与灰块外接框重合、`_front` 层在脸区一个像素都没画（逐层单独落盘核对）。
     真因是待办假设 ① 的精确版——**判据演进留下的隐形漏检**：09-20 那轮扫的 2221 候选用旧判据（整框不透明率），
     `moermansike_2` 该值 1.000 → 判"已烤好"根本没进候选；同日收紧成"不透明**且** sat≥30"后
     **只重渲了旧清单里那 35 张，全库从未重扫**。
   - **灰块是源纹理本来就有**（导出 `painting/moermansike_2_tex` 按 face 槽框裁出来目视确认），
     游戏运行时靠 face 槽叠真脸 ⇒ 叠脸方向正确，不是遮丑。当前管线重渲该皮肤 → 脸正常。
   - **顺带查出更大的问题**：用 sat≥30 判据全库重扫，前 200 候选报 **98 个"脸洞"=49%**（旧判据全库仅 1.6%），
     抽样 24 张逐张目视**全部是底图已烤好完整脸** ⇒ §14 那次收紧把错误方向从"漏叠"换成"大面积过叠"，
     且从没在"旧清单外"人群上回归过。**判据已换**成两段式：
     `洞 = 脸谱落笔处不透明占比<0.5 或 MAD(底图 vs 脸谱逐像素色差)>30`；
     闸门 `scripts/diag/face_gate_labels_check.py` 在 47 个目视裁定样本上 **47/47 全对**
     （好脸侧 MAD 最大 12.3 / 真洞侧最小 62.6，阈值 30 落在空档），`leiniya_wjz` 仍不叠。全过程见 **§48**。
   - ✅ **已换入（2026-09-27）**：全库重扫 2221 候选 → **46 洞**（其中 **13 个是旧判据完全看不见的"不透明灰块"类**）；
     `painting_face_rerun.py` 逐张重渲与在盘比 md5 → **33 张逐字节相同（零回退硬证据）/ 13 张有差异**；
     13 张逐张目视全是"改前没脸、改后正常" → 备份 `Output/_OLD_bak/painting_facefix_20260927/` 后换入
     （逐文件 `st_nlink==1`、逐张校验 == 临时渲染、全目录快照证明只有这 13 个 mtime 变了）→
     只删这 13 张缩略图后 `make_thumbs.py` 增量重建（ok=16 err=0）。结果与逐张对比图见 **§48 末段**。
   - ✅ **陈旧普查已跑完（2026-09-27，4488 张 / 94 分钟 / 0 渲染失败）**：全库只有 **9 张**与当前管线不一致，
     且**没有一张是叠脸引起的**。用"历代脚本分别重渲、看在盘能被哪个提交逐字节复现"定因：
     **7 张漏掉了 09-19 的 mesh 越框修复、2 张（`moli_g`/`moli_g_n`）漏掉了 09-18 的嵌套容器修复**
     ⇒ 当年那两批定向换入（85 张 / 55 张）各自漏了 7 张和 2 张；`z43` 是 09-20 叠过脸、新判据不再叠（两版近乎相同）。
     全过程与否证见 **§52**；`anninvwang`/`dengken` 的最大色差只有 5~6/255（重采样舍入级，肉眼不可见）。
     ✅ **已全数换入（2026-09-27 用户拍板"全换"）**：走新工具 `scripts/diag/painting_swap_in.py`，
     四道硬检查全绿（nlink=1 / 备份 md5 全等 / 换入后与渲染一致 / 全目录快照清单外 0 个），
     备份 `Output/_OLD_bak/painting_stalefix_20260927/`，缩略图增量重建 ok=9 err=0。
     **复测 9/9 与当前管线逐字节相同 ⇒ 全库 4488 张"盘上 == 当前管线"不变式已恢复**，
     这条普查从此可当每次系统性修复的回归闸门。
   - ✅ **另三条管线查过、都干净**：Spine_v2 抽 9 个包（跨 09-15 与 09-20 两批）重抽后**逐文件哈希全一致**；
     CG_v2 产物 09-26 21:39 晚于 `cg_export.html` 最后提交 21:29；Live2D 的 `extract_motions.py`
     在 09-24 全量重导之后的那次提交（`4ec3274`）**只加了 CLI 安全闸与进度 flush、没动曲线逻辑**。

<!-- A14 头部两条被取代的 09-28 轮次摘要（A+C 台词 44 张 + 画廊取景/视角记忆）——结论已在 §59/§60、§2.5/§2.6 与 WF-16 追加段里 | 原第 4-5 行，共 2 行 -->
> 本轮（并行会话，A+C）：**44 张「有表行、主包未下发」的皮肤补上「仅台词」档** + **修掉一个已上线一天的内容缺陷**——台词里的 `{namecode:NN}` 从没展开，**862 个能播的皮肤字幕里就在显示 `{namecode:98}`**；`name_code`(456 行) 已发布进 `inputs/gamecfg/` 并入台账，生成侧展开 6672 处、产物零残留，页面加 `residue` 断言（**§60**）。C 项：54 张「查无此名」= 领航员/领洋者/探索者等 NPC 皮肤，NPC 族在皮肤表里的 62 行**全部** 0 包 0 词 ⇒ 🔇 是对的，不改代码。索引零回退闸门：皮肤标量 31000 项 / 船标量 9072 项逐字未变；`talk_verify` 14 条判据全绿。
> 同日并行轮（画廊取景/视角记忆）：**画廊前端「打开皮肤缩得有点小」两层根因修掉 + 视角记忆**（**§59** / WF-16 追加）——弹窗上限 1100×880 → `min(1900px,96vw)×min(1400px,96vh)`（2560×1600 上占屏 43%×55% → 74%×87%）、Live2D 改按 drawable 顶点框∩画布的内容框取景、Spine 留白 1.1→1.05、静态立绘解除「永不放大」上限（双击仍 1:1）；**A/B 实测内容绝对像素 10/10 变大 x1.69~x3.89、零回退样本**（工具 `scripts/diag/gallery_framing_ab.py`）；三视图相机按 `皮肤|标签页` 持久化（只存尺度无关量）+ 顶部新全局开关「记住视角」+ 弹层快捷键 `←→/1-4/F/R`；顺带修掉「进一次全屏就抹掉用户缩放」这条老失效。


---

<!-- A15 段 | 2026-09-29 由 PROJECT_STATUS.md 逐字外迁（服务器半死取证轮 + 文档瘦身）；以下每块与 `git show 8de3cf0:PROJECT_STATUS.md` 对应行区间逐字相同 -->


<!-- 头部三条轮次摘要（09-29 视觉定稿 / 354 张无语音裁定 §57 / 只画开着的层 §55+§56） | 原第 4-6 行，共 3 行 -->

> **本轮（2026-09-29，画廊视觉定稿并刷进正本）**：背景被连否五版后定稿为**「静止时一帧都不画、划过才起浪」** 的 CPU 波动方程水面（判据：静止两帧逐像素相同）；卡片与导航栏从"磨砂白卡"改成**玻璃拟态**（面板 alpha 0.05 + 折射边墙 + 常驻斜反光，模糊只挂进视口的 24 张卡）；控件选中态从整块填色改成**材质态**；交互改成 iOS 丝滑（全表零过冲曲线、按下只等比轻压）。修掉 3 条真缺陷（纹理削顶吃掉白沫 / 指针瞬移被当成快速划动 / 阻尼按帧算导致低帧率永不平），见 **§62**。探针判据 16→24 条并整方向翻面，正本 `EXIT=0`。
> 上一轮：**354 张「🔇 无语音」按可救性拆细并裁定关闭**（§57）——196 缺主包（两侧都无源，等下发）/ 36 只有变体包（正文齐全却没进前端 ⇒ 新待办）/ 55 剥后缀才命中（**确认不能做**）/ 54 表里查无此名（NPC 皮肤）/ 13 该船无 CV；工具 `scripts/diag/voice_gap_audit.py`。
> 再上一轮：静态立绘「只画游戏里开着的层」根因修掉、换入 48 张（**§55**）；敦刻尔克被标成「皇家·驱逐」→ 改成「先要求 `skin_id` == 组内基皮肤」，970 组只有 1 组改判（**§56**）。更早：台词字幕 + 两个全局开关 + 索引新口径已换入（**§54** / WF-22 / §6 第 13 条）。


<!-- §2.5 四条已闭环事故注记（幽灵标签 §51 / 语音被掐 §41 / 代理指标假绿灯 §40 / 全量重导覆写事故 §25）+ 与上表重复的目视覆盖行 | 原第 58-62 行，共 5 行 -->

> ✅ **2026-09-27 判定区可视化的"幽灵标签"已修**：`drawAreas` 旧代码把标签 x 无条件夹进视口，于是画布外几千像素处的换装按钮把**名字**贴到了屏幕右边缘（框本身看不见）→ 用户报"角落里有判定区却点不到"。现**多边形仍按 `__L2_HITUSE()` 全画，标签只在框与视口相交时画**（另暴露 `__L2_HITSHOW()` 供探针同源比对）。命中链路与 `model3.json` 数据**一字未动**。判据：`qiershazhi_2` 标签 16→3、`wuzang_4` 78→4、`antu_2` 57→4，对照组 `chuyue_2` 8→8、`lafeiii_3` 10→10（零误杀）；`hit_verify` **全量 269 模型 / 3309 部位 WIRING 0 / OUTSIDE 0**（可点中率 97.1%，随机抽查 202 模型 0 不合格）。详见 **§51**。
> ✅ **2026-09-26 语音被掐已修**：语音原先注入 `definitions[g][0].Sound`，被库的 SoundManager 按"下一条动作 dispose 上一条"托管 → 动作一结束话就断（实测 `benningdun_2/touch_head` 在 `currentTime=4.48s` 处被 `pause`，而该 ogg 长 9.24s；该皮肤有 6 组超标）。现改由页面自持 `Audio` 元素，只有用户再次触发或切标签/换皮肤才打断，运行时回落 idle 不打断。**动作时长本身是忠实的**（`Meta.Duration` == 曲线末帧 == 源 clip），不要往数据层找原因。详见 §41 / WF-17 追加。
> ✅ **代理指标教训（仍有效）**：「9/9 模型加载 + idle 驱动参数」曾给过假绿灯——5 个模型其实是「几十个部件碎片叠一堆」，根因是 `model3.json` 的 `Textures` 按枚举序落盘而 moc3 按索引消费；现由 `fix_model3.py` 归一段 + 闸门 `l2d_texorder_check.py`（269/269 升序）兜住，见 §40。
> ✅ **2026-09-24 全量重导已落到 269 个模型**：曲线 944,136→2,662,615、shell 7、misassign 0；覆写过程有一次事故（`L2D_OUT_DIR` 没被子进程读到 → 跳过备份直接原地覆写），教训与回滚见 §25，「写向一律走 argv」已成硬约定。
> **目视覆盖 26/269**，按 `(moc3 版本 × 贴图数)` 15 桶全覆盖、零新增破损；⚠️ 边界：只证「贴图绑定」这一类，其余 243 个未目视，非绑定类问题仍按个案查。


<!-- §2.6 2026-09-26 Spine 三修流水（补 setSkin §42 / CG 按 animFrame 全量重导 / 弹窗取景 boundsOf §45） | 原第 67-69 行，共 3 行 -->

> ✅ **2026-09-26 补 `setSkin`（此前 viewer 与 CG 导出一次都没调过）**：spine-ts 3.8 的附件时间线经**当前 skin** 解析，不设 skin ⇒ 命名 skin 独有的部件整块不显示。用户报「阿罗芒什缺下半身」即此。全量扫描 `scripts/diag/spine_skin_scan.py`：**331 part 中受影响 4 个**（`yunlong_2` 缺 69 槽 / `feiteliedadi_5` 52 / `aluomangshi_2` 47 / `yuekechengii_4` 14，补回的是大腿/小腿/脚趾/躯干）。viewer 现按「动画跑起来后曾挂上附件的槽位数」自动选 skin，并加「皮肤」下拉可人工比（阿罗芒什 `1` vs `2` 覆盖数打平 201/201）。同视口对照证：设 skin 前后**画面大小不变**，只是腿回来了。详见 §42 / WF-14 追加。
> ✅ **2026-09-26 CG_v2 已按 `animFrame` 全量重导**：`cg_export.html` 加上与 viewer 同一套 skin 选择 + 新增默认关闭的 `?animFrame=1`（取默认动画第 0 帧）。**关键取证**：光加 `setSkin` 对 CG 导出**无效**——CG 渲染 setup pose，而 setup 附件取自 `slotData.attachmentName`、与 skin 无关（`aluomangshi_2` 四种 skin 下 setup 附件恒为 145，腿一条不回来）；腿是动画第 0 帧的 AttachmentTimeline 挂上去的（设 skin + apply 后 201）。备份 `Output/_OLD_bak/CG_v2_pre_animframe_20260926/`（231 张逐文件 md5 全等）→ detached 全量重导 **234/234 完成 0 失败**（含 3 张以前没有的：`jinluhao_4`/`xianghe_4`/`yueke_ger_4`），229/231 内容变化、未变的正是 `yuanchou_2`/`yuanchou_2_hx`（怨仇，符合预期）。逐张看图：`aluomangshi_2` 下半身回来、控制组 `2b_2` 仍满幅无回退。
> ✅ **2026-09-26 修弹窗取景：`boundsOf` 不再把"挂了附件"当成"会画出来"**（§45 / WF-14 追加）。整屏闪黑/闪白遮罩（实测最大 32967×29970 单位）setup alpha=0、一个像素不落，却决定取景框 → 弹窗里画面缩成中间一小块。全量扫描 `scripts/diag/spine_framing_scan.py`：**328 part 中受影响 13 个**（>1.05 倍），5 个 >1.5 倍、3 个 >3 倍，最大 9.6 倍；其余 315 个包围盒逐字不变。修法 1 行（用 `slot.data.color.a`，不能用会被动画改写的 `slot.color.a`）。**逐张看图 13+3 全部无裁切回退**：四万十长轴占满 0.157→0.842、法戈 0.165→0.706。两条否证已入库：「沿所有动画采样曾 alpha>0」在阳性对照上等于没修；首帧 `readPixels` 收紧在弹窗里会把 `mojiaduoer_5` 放大成一屏模糊色块（纹理首帧未上传完）。


<!-- §6 第 5 条元数据重建的改造流水（桥接路径校正 / 成品分档实测 / 76 处手抄表错名纠正 / 索引层加法兜底） | 原第 157-160 行，共 4 行 -->

   - **桥接路径（⚠️已实测校正，覆盖 §6 旧假设）**：磁盘 stem —剥变体后缀(`_n/_hx/…/罗马数字紧跟`)→ 基 `painting` → `skin[painting].ship_group` →（`stats.skin_id` 命中皮肤的组，实测 4118/4119）→ 舰级 `nationality/rarity/type/english_name`。**旧记录里“用 `ship_group` 直接反查 stats”不成立**（1270 个 ship_group 仅 268 落在 stats 键）；**变体皮肤须经 `ship_group` 归并到舰**，不能靠自身 skin.id。
   - **成品实测（2026-09-25 解析优先级改造后）**：bundleID 4495 条，source 分档 painting 2493 + suffix 1788 + **painting_ci 119 + suffix_ci 46**（大小写不敏感回退）+ **npc_table 36 + npc_family 8 + family 2**（秘书舰 NPC 表 / 同族前缀）= **4492 有名字（99.93%）**，仅剩 **3 个真无源**：`_ab`、`unknown`、`tansuozhe21_2`。改造前是 painting 2493 + suffix 1788 + fallback(手抄表) 136 + manual 2 + unresolved 76。分类 ship 4221 / story 274；阵营分布 重樱824/白鹰729/皇家622/铁血492…，空阵营 0。
   - **顺带纠正 76 处手抄表错名**（`SHIP_NAME_MAP` 被配置表接管）：`hdn101` 伊织→涅普顿（整条 hdn 系列原错位一档）、`lafeiii` 拉菲III→拉菲II、`i13` I-13→伊13、`missr` R小姐→好人理查德、`haixiao` 海啸→海咲。第三方裁判：新值命中维基名表 70/76、旧值 13/76、**「只有旧值命中」0 条**。画廊侧已生效：组名修正 24 组、补阵营 38 组、组/皮肤集合零丢失（`with_cn` 899→910）。
   - **✅ 索引层那一截已接上（2026-09-25 同日第二轮）**：`build_gallery_index.py` 的组名新增**最后一级加法兜底**——`base` 是合成前缀（`linghangyuan1`/`nabulesi` 这类不是任何 stem 的组键）时，取同 base 兄弟里来源档属于 `AUTHORITATIVE_CN` 的那条 cn；刻意排在 `SHIP_NAME_MAP` 之后 ⇒ **只可能把"当前显示拼音"的组变成有名，既有名字一律不动**。画廊组 `with_cn` 910→**984**（+74 组），组/皮肤集合零变化、已有名组四字段零改动（逐条比对过）。顺带查出**第二层根因**：5 个秘书舰换装（`linghangyuan1_1/_5`、`linghangyuan3_2`、`lingyangzhe3_2`、`tansuozhe_2`）本来被皮肤表精确命中，而皮肤行 `name` 是**皮肤标题**（TB / 超级AI-TC / 数据集：无数的我 / 入浴的小恶魔 / 悠悠假日私语时）→ `build_ship_meta` 改为：该立绘同时在秘书舰 NPC 表里时实体名取表内 `name`，皮肤标题留在 `skin_name`，并记 `name_via=npc_table:<表键>` 供审计（8 条含 `_n` 变体）。


<!-- §6 第 5 条 B 阶段完成流水（含已作废的「下一步 = C / D」） | 原第 165-165 行，共 1 行 -->

   - **✅ B 已完成（2026-09-20）**：`build_gallery_index.py` 元数据主源切 `ship_meta.json`，舰名/阵营/舰种/稀有度取 ship_meta（未解析条目回落 `SHIP_NAME_MAP`+Wiki，如 `kelei`→可畏/皇家保住了），`category` 已落 index.json。**根因**：`build_ship_meta.py` 舰名原取 `ship_skin_template.name`（皮肤名，含 433 个 `{namecode}` 占位符 + 皮肤主题标题），改取 `ship_data_statistics.name`（实测 0 占位符），237 舰级占位符归零（`weizhang`→尾张、`linggu`→铃谷、`xinzexi`→新泽西、`antu`→安土，名称与阵营一致）；`META/灰烬`（`_alter` 形态）经 `normalize` 守卫拆为 56 独立卡。逐船四字段零回退。⏭️ **下一步 = C**：前端按 `category` 分「舰船/剧情角色」+ 筛选器；D Live2D 动作播放。


<!-- §6 第 10 条 语音 v1/v2 全过程流水（两闸门 / 脚本入库 / v2 889 包 / 皮肤序号语义错 / 过程踩坑） | 原第 193-201 行，共 9 行 -->

   **✅ 2026-09-23 两个闸门都已过**：
   1. **耳朵验收已过**：用户实听确认「点动作有声音」（此前一轮报"完全无声"实为**改完没部署**，见 WF-17 踩坑首条）。
   2. **全量已跑完**：`--all` 覆盖 270 个 Live2D 皮肤 → **253 个命中 ACB 并导出**、**17 个无 ACB**、**0 个"有 ACB 但动作组零交集"**；产物 **5914 个 ogg / 323 MB**，映射表 `Output/gallery_v2/l2d_voice.json` 含 **253 个皮肤**。
   脚本已入库（commit `727fe04`）：`scripts/extract_live2d_voice.py`（新增 `--all` 旗标——原先只认 `L2D_VOICE_ALL=1` 环境变量，用 `Start-Process` 脱离进程起时不继承环境变量，导致第一次"看起来起起来了"实际直接走用法分支 `exit 1`）、`scripts/diag/l2d_voice_probe.py`。
   - ✅ **语音 v2 全线完成（2026-09-27）**：`scripts/extract_cv_voice.py` 按**船级语音包去重**解码 →
     `Audio/CV2/cv-<n>/*.ogg` + `Output/gallery_v2/skin_voice.json`；**889 包 / 41,193 个音频 / 2424.5 MB / 可定位 4140 皮肤**，零回退闸门（真丢组 0 / 磁盘缺失 0 / <2KB 占位 0）+ 三格实播全过。
     修掉的系统性语义错：cue 尾部 `_N` 是**皮肤序号**——旧脚本当随机变体全导、前端 `Math.random()` 抽一条 ⇒ 三皮肤船 2/3 概率播到**别的皮肤**的台词（取证 §47）。
   - 剩余 354 无解的**构成与裁定见 §57**（本条上方那条），「走设备补取」已否证（§49）。
   - 过程流水（75 分钟全量、定位器大小写误判 145 张、`mumu_sync.py` 的 `encoding=` 重复关键字 SyntaxError、探针 `let SV` 不挂 window 造成的假绿灯、4 个"丢组"裁定成规则、技能沉淀决议）**已逐字外迁 A12 段**；可复用做法在 WF-17/21/22，根因在 §47/§49/§53/§54。


<!-- §6 第 11 条 摩尔曼斯克叠脸根因 + 判据换两段式 + 陈旧普查换入 流水 | 原第 203-205 行，共 3 行 -->

   - **根因是"判据演进留下的隐形漏检"**：09-20 那轮扫的 2221 候选用旧判据（整框不透明率），`moermansike_2` 该值 1.000 → 判"已烤好"根本没进候选；同日收紧成"不透明**且** sat≥30"后**只重渲了旧清单里那 35 张，全库从未重扫**。灰块是源纹理本来就有，游戏运行时靠 face 槽叠真脸 ⇒ 叠脸方向正确。
   - **判据已换**成两段式 `洞 = 脸谱落笔处不透明占比<0.5 或 MAD(底图 vs 脸谱)>30`，闸门 `scripts/diag/face_gate_labels_check.py` 在 47 个目视裁定样本上 **47/47 全对**（阈值 30 落在空档）。全库重扫 2221 候选 → 46 洞（13 张换入，其中 13 个是旧判据完全看不见的"不透明灰块"类），33 张逐字节相同 = 零回退硬证据。全过程见 **§48**。
   - ✅ **陈旧普查已跑完并全数换入（2026-09-27）**：全库 4488 张 / 94 分钟 / 0 渲染失败，只有 **9 张**与当前管线不一致（7 张漏 09-19 mesh 越框修复、2 张漏 09-18 嵌套容器修复），**没有一张是叠脸引起的**。走 `scripts/diag/painting_swap_in.py` 四道硬检查换入 ⇒ **全库 4488 张「盘上 == 当前管线」不变式已恢复，这条普查从此可当每次系统性修复的回归闸门**。Spine_v2 / CG_v2 / Live2D 三条管线抽查也都干净。见 **§52**。


<!-- §6 第 13 条 台词字幕/开关/索引新口径 的验收与换入明细流水 | 原第 221-233 行，共 13 行 -->

     - ✅ 覆盖面：**4129/4140** 皮肤配上正文、**73,705** 条（语音表 12.4 万条槽位里约 61% 游戏本来没写词）。
     - ✅ 验收全绿：三格各点一次 + **直接点立绘** + 开关矩阵两条反向证据 + 阴性对照（摸头有声无词⇒不弹空框）
       + 语音页逐行比对（含"每行 `<audio>` 可见高度"，光数行放过了一次 `flex:1` 把播放器压成 0 高）
       + 无语音皮肤显式 🔇 + 持久化（用非常规组合验）。
     - ✅ **全屏没字幕已修**：三格「全屏」按钮 `requestFullscreen()` 的是 `#mView`，字幕原先挂在 `.content` 上
       ⇒ 全屏时不在被渲染的那棵子树里。现挂进 `#mView`；并用 CDP **可信鼠标事件**真进一次全屏量到
       `fullscreenElement=mView` + 字幕 282×62 可见（直接 evaluate 调 `requestFullscreen` 会被权限拒，不算测过）。
     - ✅ **已换入（2026-09-27 19:05 用户放行）**：备份 `Output/_OLD_bak/gallery_index_pre_talk_20260927/index.{json,js}`
       （sha256 `e79ed546bb41` / `58b78bf27249`）→ 覆盖 `Output/gallery_v2/index.{json,js}`（943,728B / 857,039B，
       与构建产物逐字节相同）。换入后复验：`congmang_2_hei` 语音标签从置灰变可用，语音页 **32 行 / 16 条正文**逐行对齐、
       每行播放器可见；`lafei`（主包缺失、只有变体包）走「其它已导出语音」分支 1 行可播 ⇒ 换口径没把旧导出弄丢；
       `kelei` 语音 0（旧口径把可畏的包派给它，属修正）。全套 `talk_verify` 12 条判据全绿。
     - 提交 `52e2797`/`92bef91` 由并行会话**接管快照入库**（当时本会话仍在写 `talk_verify.py`），文档债已在本次补齐。


<!-- §6 第 16 条 44 张「仅台词」档 + namecode 占位符展开 的落地明细 | 原第 261-267 行，共 7 行 -->

     - ✅ 落地（全加法，**没动**那条 75 分钟语音管线）：词表第二趟 **44 张 / 565 条正文**（爱宕 11、拉菲 17、
       加贺 11、声望/加贺·战列/七宝琳/UI 角色 5）；索引 `voiceText`（皮肤级+船级，只在无音频皮肤上写）；
       前端 tab 判据 `voiceCount>0 || voiceText>0` + 语音页「仅台词」一节 + `talkCount` 兜底。
       台词行**不带播放器**（探针反向证据：`audio == 变体包条数`、`无播放器台词行 == 台词数`）。
     - ✅ **顺带修掉一个已上线一天的内容缺陷**：台词正文里的 `{namecode:NN}` 从没展开，
       **862 个能播的皮肤字幕里就在显示 `{namecode:98}`**。发布 `name_code`（456 行，带零假设证成对齐）
       进 `inputs/gamecfg/` 并入台账，生成侧展开 6672 处，产物零残留 + 页面 `residue` 断言。见 **§60**。


<!-- §6 第 18 条 按钮/交互反馈层重做 全案（五条真缺陷原文 + 建议做法 + 判据工具 + 两条假回退坑）——已于 09-29 视觉定稿轮关闭 | 原第 308-337 行，共 30 行 -->

18. ⏳ **画廊「按钮 / 交互反馈」层重做**（2026-09-27 立项，**用户指定次日开工**）：
     - **先记一条否证，别重走**：同日做过一整版**视觉语言重做**（暖墨底 + 单一铜金强调、字阶、卡片三行化、
       头部一行、查看器底换掉棋盘格），样板页 `index_b.html` 已给用户看过并**被否**（"B版不如之前"）
       ⇒ **整体换色这条路已试且被拒**；方向改为**只动按钮与交互反馈，配色基调与布局不动**。
       样板代码与成对截图留 `.diag/uishots/`（`before_*` vs `b3_*`、`sbs_grid.png` / `sbs_modal.png`）。
     - **本轮 grep 出来的五条真缺陷**（都是量过的，不是感觉）：
       ① **同一个"选中"语义有 5 种颜色**：`.seg button.on`=`--acc2` 蓝、`.srcbar/.vbox button.on`=
          硬编码 `#2b6cb0`（连 token 都没走）、`.opt button.on`=`--ok` 绿、`.spine-bar button.on`=`--acc` 红、
          `.skin.on`=红边框、`.tab.on`=红下划线。
       ② **Live2D / Spine 两条控制条其实是浏览器原生按钮**：CSS 里 `.spine-bar select,.spine-bar button`
          **只设了 `font-size`/`padding`，没有 `background`/`border`**，而 `#l2bar` 的 class 就是 `spine-bar`
          （`index.html:608`）⇒ 那排「重播/复位/全屏/判定区/参数·部件」是 UA 浅灰底，
          与静态立绘那条 `.srcbar` 的深色 chips 是两套视觉。
       ③ **零按压反馈**：全文 `:active` 命中 **0 次**。
       ④ **零键盘焦点可见性**：`:focus-visible` **0 次**，且 `input,select{outline:none}` 连默认焦点环一起杀了
          ⇒ 本轮新加的 `←/→ / 1-4 / F / R` 与 Tab 导航都没有视觉反馈；hover 只有 `.card/.close/.skin` 三处，
          三条控制条上约 20 个按钮**全无 hover**。
       ⑤ **toggle 与动作混在一排且外观不可区分**：`判定区`/`参数·部件`/三个全局开关是状态开关，
          `重播`/`复位`/`全屏` 是瞬时动作，外观一模一样。
     - **建议做法（待验证，不是结论）**：先做"一个语义一种表现"（选中一色 / 可点一 hover / 按压一 `:active`
       / 键盘焦点一 `focus-visible` 环），再给 `.spine-bar button` 补齐与其它条一致的基样式，
       最后用**形状或图标**而不是颜色去区分 toggle 与动作。
     - **判据与工具已就位**：`py -3 scripts/diag/gallery_ui_shots.py`（同机成对截图，默认 2560×1600 对齐实机；
       ⚠️ 它按 `--pages a,b` 跑，对照页用 `git show HEAD:gallery_src/index.html > Output/gallery_v2/index_x.html` 现造现删）；
       `py -3 scripts/diag/hit_verify.py --page <对照页>`（本轮新增该参数，用于判 WIRING 是不是本轮引入）；
       交互零回退仍跑 `interact_verify` / `l2d_inspector_verify` / `hit_verify` 三件套。
     - ⚠️ **两条本轮踩到、明天直接避开的坑**：① 判据别用「占视口比例」——视口形状被改动改掉时会假报回退，
       用**绝对像素**（详见 WF-16 追加段）；② **别把长任务写成 `py -3 x.py 2>&1 | tail -25`**：
       `tail` 会吞掉中间明细，且 `$?` 取的是 `tail` 的退出码不是 python 的——本轮就是这么把
       一个 `WIRING=2`（实为探针抖动）读成了 `EXIT=0` 假绿灯。


<!-- 头部两条指针行被就地更新（A1~A13→A1~A15、§25~§62→§25~§63），旧文本逐字留此 | 原第 7-8 行，共 2 行 -->

> 历轮会话流水（2026-09-20 ~ 09-27）已**逐字**外迁 `docs/archive/2026-09-26_PROJECT_STATUS_外迁归档.md`（A1~A13 段）；
> 结论性知识在 `docs/TROUBLESHOOTING.md` §25~§62 与 `docs/WORKFLOWS.md` WF-14~WF-22。本文只留当前状态。


<!-- §6 待办第 4 条「文档越红线」的原始待办文本（本轮已关闭并就地改写成结论） | 原第 148-151 行，共 4 行 -->

4. ⚠️ **本文档仍越过 400 行红线**（本轮两条 09-28 顶部摘要逐字外迁 A14 段 + §10 视觉行压回快照，
   但新结论净增 3 行 → 437→440）。**只靠"写得更省"已经压不下去了**，
   溢出主体是 §6 第 5 条元数据历史与 §10 长条目。下一个独立任务：用 `project-doc-governance`
   技能逐字外迁，压回 400 行内。


<!-- A16 §6 第 17 条 Spine parts 按 glob 猜 的完整待办原文（含五步实施清单与开工时机约定）——已于 2026-09-29 落地，做法在 WF-14 追加、踩坑在 §64 | 原第 247-282 行，共 36 行 -->

17. ⚠️ **Spine 的 parts 列表是按目录 glob 猜的 ⇒ 15 个和谐版 CG 与本体逐像素完全相同**
     （2026-09-27 查第 14 条时顺带查出，**未修、待放行**，取证见 **§58**）：
     `build_gallery_index.py:187` 用 `glob('Output/Spine_v2/<folder>/*.skel')` 决定"由哪几层合成"，
     但同目录里还躺着 `_hx` 等**变体**的 skel——它们不是层，是另一张画。viewer 与 `cg_export.html`
     共用这份列表 ⇒ 本体与和谐版被叠在一起画。
     **权威答案在 prefab 里**：`spinepainting/<name>` 的 `SkeletonGraphic` 节点列表才是真分层，
     且 `_hx` 是**替换某一层**（`huajia_2_hx` 的 prefab = `[2B, 2M, 2T_hx]`）而不是多加一层。
     硬指标：234 个 Spine 目录里 **30 个** parts 含"变体后缀且基名也在列表"；
     `CG_v2` 里 **15 对**本体/`_hx` 的导出图**逐像素完全相同**。
     判据（区分真分层与误叠）：健康的多 part 皮肤各 part **槽位名互不相交**
     （`bailong`/`aimudeng_4` 重名率 0%、`lafeier` 3.4%），被误叠的 30~48%。
     **✅ 全库比对已跑完**（新工具 `scripts/diag/spine_parts_prefab_diff.py`，只读，明细 **§58.1**）：
     234 个目录里 **多画 30 / 少画 0 / 层文件缺失 0** ⇒ glob 是**纯过包含**，
     修法是"过滤到 prefab 列表"，不会丢内容。另量出两类画廊从没读过的 prefab 字段：
     **各层缩放不一致的只有 5 个目录**（`duyisibao_2`/`guandao`/`moermansike_3`/`qiershazhi_3`/
     `xinzexi_4`，都是 `B` 层 2.0~2.5× 而 `T` 层 1.0×）——⚠️ 原始数字"9 个非单位变换"是虚高的，
     统一缩放/位移会被取景归一化吃掉，**只有各层之间不一致才真的改变画面**（明细 §58.1）；
     位移不一致的 2 个差值仅约 2px 可忽略。**3 个目录起始动画不是 `normal`**
     （`buleisite`=`idle`；`pulimaosi` 两层各播各的 `idle2`/`normal`）。
     层数分布：1 层 191 / 2 层 29 / 3 层 11 / 5 层 1 / 7 层 2。
     **实施清单（待办本体，按顺序）**：
     1. `scripts/extract_spine_v2.py` 导出时把 prefab 的权威层列表**落进每个目录**
        （`Output/Spine_v2/<folder>/parts.json`：层名 + localScale + startingAnimation + initialSkinName），
        让"谁写"和"谁读"都只认这一份，避免 `build_gallery_index` 直接依赖 26GB 源包。
     2. `build_gallery_index.py:187` 改读 `parts.json`；**缺文件要报错，不许回落 glob**——
        回落等于把这个 bug 留着。
     3. viewer 与 `cg_export.html` 按 `parts.json` 的 localScale 摆层（缩放可直接用；位移先过 §9.1
        那套 UI 数学，只有 `duyisibao_2`/`guandao` 两个目录需要且差值 ~2px，可最后做）；
        起始动画按 `startingAnimation` 逐层设（`buleisite`=`idle`、`pulimaosi` 两层各一）。
     4. 重导 `CG_v2` 受影响的 **30 个目录**（含那 15 对逐像素相同的）；备份 + 零回退闸门照 WF-15。
     5. 验收：`spine_parts_prefab_diff.py` 重跑必须**多画 0 / 少画 0**；15 对 `_hx` CG 必须**不再相同**；
        对照组 `bailong`/`aimudeng_4`/`tianjinfeng_2` 的 CG 必须**逐字节不变**。
     ⏸️ **开工时机**：等并行会话把它在 `gallery_src/index.html` 与 `build_gallery_index.py`
     上的未提交改动落地后再动这两个文件，避免同一文件撞车（2026-09-27 用户拍板）。
     ⚠️ 它 voiceText 那轮（§60）已提交，但**之后还有一轮** `index.html`（弹窗尺寸/缩放记忆）在途
     ⇒ 开工前先 `git status` 复核这两个文件是否已干净。


<!-- A17 §6 顶部「当前真实状态 / 执行状态」段里那批**已被后续真跑取代**的原文（含 22:48 那版整段状态行、15:53 前暂存区 4 张、首轮 1154 条规模、§74 五条明细、15:20 那版"其余 10 档仍未跑"）——结论都在 docs/TROUBLESHOOTING.md §74/§79/§80/§81，此处仅按"归档=逐字外迁"留底 | 原第 32-41 行，共 10 行 -->

**当前真实状态（§79）**：源包已同步（92679）、清单已复原（972 条 → 立绘 179 张）；第 2 步重导**已真跑**（179 张 / 3 分 34 秒 / 渲染期 725MB·3 进程，失败 0）；review 现在报「线上新增 **12** · 内容有变 0 · 逐字节相同 167」——**这次更新的真实新内容就是这 12 张**（6 艘船 × 本体+无背景），167 张是保守网重渲后与线上逐字节相同（顺带证明没改坏）。根因是 `st_review` 只把"线上已有且内容不同"算进换入清单 ⇒ 新皮肤永远进不去、swap-in 永远"清单为空"。**这 12 张已签字换入**（正式区 4488 → 4500，备份 `pipeline_20261001_2248/`，WF-16 六件套真跑全绿 2分13秒）。换入时又露出两层（见 **§80**）：`painting_swap_in` 不容"正式区没有这个文件"、`regress` 命中了**换入之前**的 done 缓存报假绿 ⇒ 新增 `Stage.check`，**验收类阶段结果永不缓存**。控制台新增「这次新增了什么」板块（判据 96→103）：第一次跑就报出 12 行**元数据缺**——图已进正式区、`ship_meta.json` 还没换入 ⇒ 待办是签 `meta`（顺带 `deps` 已换过）。——用户两次按的都是第 4 步那颗换入，于是 `swap-in: 清单为空`；**§77 已把路径收进 `scripts/paths.py`**（`AL_ASSETS_ROOT` 换机器、12 个文件接上、`mumu_sync --only` 按类型拉取且与 `--list-out` 硬互斥），闸门 `py -3 scripts/diag/check_paths.py`：链路 0 处写死、43 个一次性脚本记为欠账不判红；**§78 资产台账已落地**（`scripts/asset_ledger.py` + `ledger/`，闸门 23 条）："已还原"= 产物在 **且** 溯源记录的源包大小+md5 与盘上现状对得上；`prune` 默认 dry-run、`--apply` 还要 `--yes`、`dependencies`/`hashes*`/AB 根下 41 个散包永不删；删过的写 `pruned.json`，`mumu_sync` 据此**不再把它们报成新增**（设备上大小变了的照旧算新版本）；`export`/`import` 是换设备的迁移单元。建账时被抓出两处"少记"（只扫第一层、漏 AB 根下散包），已进判据。
已换入的只有 15:53 前留在暂存区的 4 张（备份 `Output/_OLD_bak/pipeline_20261001_1810/`）。
本轮实测规模：1154 条变更路径 → **立绘 14 张 / Spine 2 个 / Live2D 4 个模型**，大头全在设备侧（diff 42~69 秒）。
修掉五条：`affected.txt` 从来没人写 ⇒"增量"静默等于全量；退化出的全量路径炸在已改名的
`Output/Paintings_Synthesized` ⇒ **默认跑到立绘就判红、整条线跑不完**；`audio`/`cg` 收了 `approved` 却不检查
⇒ 签字门空转、`cg` 带 `--redo` 会直接全量覆写 `Output/CG_v2`；`run()` 的 `capture_output` 把子进程输出憋到结束
⇒ 子进程跑动期间前台零进度（实测 diff 那 69 秒零输出，靠 25 秒静默心跳兜住）；超时只杀直接子进程会漏 Chrome 树。
**执行状态（2026-10-01 15:20）**：`preflight` / `pull`（含签字拉完 1036 个新包）/ `deps` **已真实跑过**，
其余 10 个阶段（`meta`/`paintings`/`spine`/`live2d`/`audio`/`cg`/`review`/`swap-in`/`derive`/`regress`）
**仍未真跑过一轮**；设备侧已同步完（新增 0 / 变更 0），范围清单 1154 条有效。


<!-- A18 §6 顶部「控制台执行侧」那几轮（§71 资源体检 / §74 首次真跑五条 / §75 假绿灯第三层）的逐轮流水原文——结论逐条在 docs/TROUBLESHOOTING.md §71/§74/§75，此处按"归档=逐字外迁"留底 | 原第 15-31 行，共 17 行 -->

**控制台执行侧（2026-10-01 体检，见 §71）**：为回答"跑一次要多少 G / 每次都全覆盖写吗"量了真实峰值
——13 阶段全串行、同一时刻 1 个子进程、**稳态约 0.7GB**（立绘 50 包 0.63GB/17s ≈ 1.25 秒/张 ⇒ 全量 4488 张
≈1.5 小时、一把梭全量 4~6 小时约 41GB 写入；旧文档"耗时数十小时"已纠正），**跟 MuMu 不冲突**（只有第 1 步要设备）。
**⚠️ 其中"依赖表 43 分钟"是我报错的数**：`deps` 实测 **3 秒 / 0.20GB**（只读 dependencies 一个包），43 分钟是 §50 的立绘全库重扫。
**用户当天真跑了一轮**（14:45 签字拉 1036 包 ⇒ 91643→92679），第一次跑撞出**五条**并全部修掉（见 **§74**）：
0 变更被误判红（且差点把真清单冲空）、上面那个错耗时数、依赖表超集闸门被游戏自己删的 4 个
`iconframe` 条目卡死 ⇒ 改成按**消费域**分级、进度台「剩余」首次跑必盲 ⇒ 阶段带 `est`/`rate`（只填量过的）
+ 来源标注，阶段头打 `[i/N]`+预计+每阶段实际耗时，`run()` 加 25 秒静默心跳。
**第五条最疼**：`fingerprint()` 把依赖表哈希算进去 ⇒ 「拉包 → 换入依赖表 → 跑导出」这条唯一正确的顺序
会把刚写好的范围清单判成过期，再叠上"零结果"分支 ⇒ **1154 条真清单被空清单覆盖**（`.diag/` 无 git 兜底）。
已按两条独立证据复原（依赖表键差 797 条 + 有源包无产物的 12 张 + mtime 保守网）= **972 条 / 立绘 179 张**；
新鲜度改为只比 `bundles=`，`write_scope` 空结果一律保住非空旧清单并备份成 `affected.prev.txt`。
**假绿灯挖到第三层（见 §75）**：主屏曾对用户宣布「这次更新已经换完了」，而第 2 步 179 张一张没重导 ——
① 第 4 步的结语只看第 4 步 ⇒ 改成必须看全部 13 档并按步点名差在哪；② `verdict` 只盖指纹章 ⇒ 再盖一枚
范围章（`scope=`清单内容哈希）；③ **跳过缓存 `done` 也认了错的范围**（这条最疼，它不是骗界面，是真的会少跑）
⇒ 两处盖章、没盖章的旧条目一律不算这轮（失效方向必须是"多跑一次"）。判据 `panel_ui_probe` 88→**90 条**，
两条配对：不许宣布完成 + 必须报出数量与差项（含糊不等于诚实）。


<!-- A19 本轮**就地改写**掉的旧表述留底（"当前真实状态"段、"derive 跑在 meta 之前 ⇒ 重跑即可"那条被 §82 否证的欠账、第五轮界面段）——改写的原文也留一份，不靠记性 | 原第 32、38-40、42 行，共 5 行 -->

**当前真实状态（§79）**：源包已同步（92679）、清单已复原（972 条 → 立绘 179 张）；第 2 步重导**已真跑**（179 张 / 3 分 34 秒 / 渲染期 725MB·3 进程，失败 0）；review 现在报「线上新增 **12** · 内容有变 0 · 逐字节相同 167」——**这次更新的真实新内容就是这 12 张**（6 艘船 × 本体+无背景），167 张是保守网重渲后与线上逐字节相同（顺带证明没改坏）。根因是 `st_review` 只把"线上已有且内容不同"算进换入清单 ⇒ 新皮肤永远进不去、swap-in 永远"清单为空"。**这 12 张已签字换入**（正式区 4488 → 4500，备份 `pipeline_20261001_2248/`，WF-16 六件套真跑全绿 2分13秒）。换入时又露出两层（见 **§80**）：`painting_swap_in` 不容"正式区没有这个文件"、`regress` 命中了**换入之前**的 done 缓存报假绿 ⇒ 新增 `Stage.check`，**验收类阶段结果永不缓存**。控制台新增「这次新增了什么」板块（判据 96→103）：第一次跑就报出 12 行**元数据缺**——图已进正式区、`ship_meta.json` 还没换入 ⇒ **`meta` 已签字换入**（23:16，受保护档 4287 条 → 字段改动 0 处、权威闸门绿、2 秒），12 行舰名/阵营全部取到；紧接着跑了一次**只读** audio 审计（见 **§81**）：12 张里 **10 张靠"同船回退"解析**（`_h`=誓约/婚装皮肤，与三套新皮肤一样在本地 azdata 快照里**没有表行**，`idx` 定不下来），`l2d_voice_inventory` 缺失 0 / 孤儿 0 双向真绿，`Output/Audio` 一个字节没动。三条未决（要不要维持 🔇、`_alter` 该不该从剥后缀表里摘出去、面板语音列的代理指标）都在 §81 末段。——用户两次按的都是第 4 步那颗换入，于是 `swap-in: 清单为空`；**§77 已把路径收进 `scripts/paths.py`**（`AL_ASSETS_ROOT` 换机器、12 个文件接上、`mumu_sync --only` 按类型拉取且与 `--list-out` 硬互斥），闸门 `py -3 scripts/diag/check_paths.py`：链路 0 处写死、43 个一次性脚本记为欠账不判红；**§78 资产台账已落地**（`scripts/asset_ledger.py` + `ledger/`，闸门 23 条）："已还原"= 产物在 **且** 溯源记录的源包大小+md5 与盘上现状对得上；`prune` 默认 dry-run、`--apply` 还要 `--yes`、`dependencies`/`hashes*`/AB 根下 41 个散包永不删；删过的写 `pruned.json`，`mumu_sync` 据此**不再把它们报成新增**（设备上大小变了的照旧算新版本）；`export`/`import` 是换设备的迁移单元。建账时被抓出两处"少记"（只扫第一层、漏 AB 根下散包），已进判据。
⚠️ **一处顺序性欠账**：`derive`（22:48:16）跑在 `meta` 换入（23:13:43）**之前** ⇒ 画廊索引里那 12 行的 `label`
还是回落值（`h`、`h（无背景版）`、`皮肤9（无背景版）`、`alter`、`皮肤3`）、`voiceCount` 为空 ⇒
**下一件事是重跑 `derive`** 让索引吃到新 `ship_meta.json`（`build_gallery_index.py` 的 `--expect` 闸门按值钉死允许改名的条目）。
跑之前先 `py -3 scripts/diag/test_pipeline_gating.py`（56 条判据）。**§76 又挖出一条接线缺失**：卡片上的「签字放行」复选框只有那颗「单独跑」会读，主按钮「重跑到待确认」发的 `approve` 永远是空的 ⇒ 用户勾了等于没勾。现在勾选存 `SIGNED`、主按钮带上并二次确认、主屏那行小字显示"已勾签字：…"；另外设备不可达且范围清单有效时 `pull` 判绿沿用清单，不再把已同步完的人卡在第 1 档。。**语音产物口径已定：无需单独备份**（可确定性再生，体检 `scripts/diag/l2d_voice_inventory.py`），不可复原的只有 `inputs/azdata`｜**控制台界面（2026-10-01 第五轮，见 §73 / WF-23 追加）**：用户否掉第四轮的「常驻漂移」（「我要的就是渐进式显影」）⇒ 星野**退回显影式**（静止全黑、划过才亮、约 520ms 淡净、淡净回**同一张**帧），配色保留 B 的**海军蓝 + 蓝白**（五个状态色 rgb 不动），光效回到 **conic 边框光束 + 控件内柔光 + 磁吸**；新增**三态自定义光标**（默认/可点/主行动，内联 SVG、深色描边打底）与**进度台**（只在真在跑时出现的一条细带：阶段 N/M · 已用 · 内存〔整棵进程树工作集〕· 剩余〔各阶段历史均值，缺样本报「≥」下限〕）；帮助抽屉里**为设计辩护的文案删掉**（用户要求别把提示词写进界面）。`scripts/diag/panel_ui_probe.py` 契约改回「渐进式显影」并新增 9 条进度台判据，**86 条全绿**。｜低优先：声优中文姓名回填、UI/图标批量导出、`organize.py`。


<!-- A20 §6 顶部「当前真实状态」这一大段 2026-10-01~10-02 的逐轮叙述（§79 换入 12 张 → §81 audio 只读审计
     分档 → §82 derive 否证 + 星空/说明书 → §83 权威源切换 → §84 后缀三分类 → §85 台词层同源）
     ——结论逐条在 docs/TROUBLESHOOTING.md §79~§85，此处按"归档=逐字外迁"留底 | 原第 19-50 行，共 32 行 -->

**当前真实状态（§79）**：源包已同步（92679）、清单已复原（972 条 → 立绘 179 张）；第 2 步重导**已真跑**（179 张 / 3 分 34 秒 / 渲染期 725MB·3 进程，失败 0）；review 现在报「线上新增 **12** · 内容有变 0 · 逐字节相同 167」——**这次更新的真实新内容就是这 12 张**（6 艘船 × 本体+无背景），167 张是保守网重渲后与线上逐字节相同（顺带证明没改坏）。根因是 `st_review` 只把"线上已有且内容不同"算进换入清单 ⇒ 新皮肤永远进不去、swap-in 永远"清单为空"。**这 12 张已签字换入**（正式区 4488 → 4500，备份 `pipeline_20261001_2248/`，WF-16 六件套真跑全绿 2分13秒）。换入时又露出两层（见 **§80**）：`painting_swap_in` 不容"正式区没有这个文件"、`regress` 命中了**换入之前**的 done 缓存报假绿 ⇒ 新增 `Stage.check`，**验收类阶段结果永不缓存**。控制台新增「这次新增了什么」板块（判据 96→103）：第一次跑就报出 12 行**元数据缺**——图已进正式区、`ship_meta.json` 还没换入 ⇒ **`meta` 已签字换入**（23:16，受保护档 4287 条 → 字段改动 0 处、权威闸门绿、2 秒），12 行舰名/阵营全部取到；紧接着跑了一次**只读** audio 审计（见 **§81**）：12 张里 **10 张靠"同船回退"解析**（`_h`=誓约/婚装皮肤，与三套新皮肤一样在本地 azdata 快照里**没有表行**，`idx` 定不下来），`l2d_voice_inventory` 缺失 0 / 孤儿 0 双向真绿，`Output/Audio` 一个字节没动。三条未决（要不要维持 🔇、`_alter` 该不该从剥后缀表里摘出去、面板语音列的代理指标）都在 §81 末段。
**10-02 复核（见 §82）**：`_alter` 那条**已定案**——设备侧权威表里改造皮肤是**独立行、独立 cv**
（`npclingmin_alter` id 900549，cv 90054 ≠ 灵敏 70109），所以它属"另一个发声实体"，该从 `VAR` 剥后缀表里摘出去；
同一份表（`.diag/sharecfg_re/cfg_json_scalar/ship_skin_template.json`，2865 行）**已经有 azdata 快照缺的
`aierdeliqi_9`=金月桂香 / `mile_3`=幽幽桥上，坏坏来袭！** ⇒ 权威源切换的取证已完成，接线待放行。
誓约皮肤固定占 `idx=8`；信浓/尾张/斯库拉的 `_h` 与英格拉罕第 3 套**连设备侧都没有行**——10-02 已按建议启动游戏到主界面
（无下载任务、`sharecfgdata` 整目录仍是 09-24），且这三个名字在**全部**已解出的表里都查不到
⇒ 判定为**游戏提前下发、尚未开放**的资源，"没有台词/没有皮肤名"是正确状态，不是我们漏抽（裸 grep 恒 0 命中不算证据，串是 `^(255-i)` 编码的，必须走 `37_parse_sharecfgdata.py`）。
**B 已落地（只读侧）**：`inputs/gamecfg/ship_skin_template.json`（2865 行，`42_publish_gamecfg.py` 发布）+ `scripts/skin_table.py`
逐字段合并口（设备覆盖、快照补齐、断言不丢行），`build_ship_meta` / `extract_cv_voice` 已接上；
实测差异 **条目零增减、20 处全是皮肤名升级**（含消掉 3 个 `{namecode}` 占位符），
`aierdeliqi_9_n`/`mile_3_n` 的语音从"同船回退 `idx=None`"变成"停在真行 `cv=10126 idx=7` / `cv=10153 idx=2`"；
闸门 `ship_meta_authority_diff` 为此新增**「快照缺行→权威表已有行」方向性判据**（远→近才放行，反向必拦），
配套反向对照测试 `scripts/diag/test_meta_gate_proofs.py` 8 例全过。**13:06 已换入正式区**
（`meta` 2 秒闸门绿 → `derive` 5 秒 index 闸门绿 + `deploy --check 4/4` → `regress` 2 分 03 秒 WF-16 五件全绿）；
画廊索引条目 4503→4503（零增减）、`aierdeliqi_9_n`/`mile_3_n` 各新增变体包语音 `voiceExtra`
——为此把第三个读点 `build_gallery_index.py` 的 `SKIN_ROWS` 也接进了同一个合并口。
**C 已裁定并落地解析侧（见 §84）**：用户口径「改造=同一角色的另一套皮肤（可回退到本体），黑化=独立发声实体（不可回退）」
⇒ 后缀改成三分类（`ART_SUF`/`ALTER_SUF`/`HEI_SUF`）+ `art_chain()` **逐层**剥（旧 `VAR` 一次剥光整串后缀是根因）。
实测 4506 个皮肤名里**行为变化 49 处**：换包 37（如 `birui_alter_n` 30402→970405）、改判无解 12（黑化），
可解析 4152→4140 / 无解 354→366；`test_voice_owner.py` 11 例（含"黑化绝不出现在可解析集合"这条全库不变式）。
清单 `.diag/pipeline/voice_owner_AB.tsv`。**已重导并换入（14:04）**：`audio` ✅（增量 12 秒，889 包全命中复用；
我上轮说的"≈75 分钟"是冷导出口径，已纠正）、`derive` ✅、`regress` ✅。
真跑又露出两条：① `skin_voice.json` 原来**只合并不撤回**，12 个黑化版仍挂着本体的包 ⇒ 加"只撤本轮看过的键、
且算不出归属或包号已变"的撤回逻辑（映射 4152→4140，正好 −12）；② 零回退闸门把 `voiceText None→12`（补全）
叫成回退、又把"旧包无从判定"当成"证明丢了本船语音" ⇒ 加 `empty()` 方向判据 + "无从判定"独立一档并要求替代证据
（撤语音后仍有台词），24 处红降到 0 红 + 1 条"需人看"。索引计数 `with_voice` 860→859、`voice_text_skins` 44→56。
**台词层也有同一份错派（见 §85，已修）**：`build_skin_words.py` 原来自己写了一遍贪婪剥后缀
（注释还写着"不做身份后缀剥离"），12 个黑化键的台词指向本体的行 ⇒ 归属规则收成**一份**
`extract_cv_voice.row_candidates()`，两层共用；闸门那条"撤语音后仍有台词"的替代证据**不合格**
（被错派台词自己满足）⇒ 改按实体规则判。重导后 12 个黑化键语音 0 / 台词 0 / 两张映射里都不存在，
`voice_text_skins` 回到 44，`derive` ✅ `regress` ✅。**已知重复未并**：`build_gallery_index.VAR_TAIL`（语义不同、有闸门覆盖）。——用户两次按的都是第 4 步那颗换入，于是 `swap-in: 清单为空`；**§77 已把路径收进 `scripts/paths.py`**（`AL_ASSETS_ROOT` 换机器、12 个文件接上、`mumu_sync --only` 按类型拉取且与 `--list-out` 硬互斥），闸门 `py -3 scripts/diag/check_paths.py`：链路 0 处写死、43 个一次性脚本记为欠账不判红；**§78 资产台账已落地**（`scripts/asset_ledger.py` + `ledger/`，闸门 23 条）："已还原"= 产物在 **且** 溯源记录的源包大小+md5 与盘上现状对得上；`prune` 默认 dry-run、`--apply` 还要 `--yes`、`dependencies`/`hashes*`/AB 根下 41 个散包永不删；删过的写 `pruned.json`，`mumu_sync` 据此**不再把它们报成新增**（设备上大小变了的照旧算新版本）；`export`/`import` 是换设备的迁移单元。建账时被抓出两处"少记"（只扫第一层、漏 AB 根下散包），已进判据。
