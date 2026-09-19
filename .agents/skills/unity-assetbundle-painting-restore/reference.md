# 参考手册：坐标系约定与 PPtr 解析规则

本文件是 `unity-assetbundle-painting-restore` 技能的详细参考，承载两类最容易踩坑的完整规则。SKILL.md 只保留速查表，动手前先读对应章节。

## 一、Y 翻转坐标系总表（最核心的坑）

Unity 纹理 raw data 与标准 PNG 的行序**相反**，不同导出路径的 flip 约定不同，混用即产生"整层颠倒"。

| 场景 | 导出/读取方式 | 约定 | 依据 |
|---|---|---|---|
| 立绘部件纹理（供合成管线自用） | `decoded_texture(flip=False)` | PIL 数组**第 0 行 = v=0 = Unity 底部** | 保留 Unity 自底坐标序，后续 rect 切片数学全程 Y-up，不再翻转 |
| 无 mesh 整图部件裁剪（root 背景层等） | 按 `m_Rect` 直接切片 | `arr = A[rect.y : rect.y+h]`，bbox y0 = rect.y | `m_Rect.y` 本身就是自底坐标；若再 `th-rect.y-h` + `[::-1]` 就是**双重翻转**→整层颠倒 |
| 有 mesh 部件回贴 | mesh UV 重心插值光栅化 | 与 flip=False 数组同序（Y-up） | UV 的 v=0 对应数组第 0 行 |
| Spine atlas 页纹理（供 spine-webgl/DeskSpine 用） | `flip=True` 导出 PNG | 标准 PNG 语义：**行 0 = 顶** | Spine 运行时按标准 PNG 采样；Unity raw data 序导出则播放时颠倒 |
| UnityPy 直接 `image_data()` | 默认已 flip（行 0 = 顶） | 注意与手动 flip=False 路径不要混用 | 两条路径坐标系不同源必错 |

**记忆口诀**：自用合成链路 = flip=False + 全程 Y-up 不回头；给外部运行时的资源（Spine 页）= flip=True 转标准 PNG。

**方向验证方法**：与旧版已知可用的输出（如 `Output/Spine/`）逐像素比对；或用含明确上下特征的样本（甲板/天空）目视。

## 二、PPtr / externals 完整解析规则

### 依赖表（权威映射源）

- `AssetBundles/dependencies` 单包内 MonoBehaviour 携带官方「资源名 → deps 列表」全量依赖表，导出为 `Output/dependency_manifest.json`。
- manifest 类 bundle 的 deps 列表是**字母序**，只是元数据摘要，**不能**用来解析 FileID。

### PPtr 二元组

prefab 里所有资源引用为 `m_Sprite / m_Texture / m_Mesh = (FileID, PathID)`：

1. **FileID = 0** → 对象住在当前 SerializedFile 内，按 PathID 直接匹配。
2. **FileID = N (N≥1)** → 取 `SerializedFile.externals[N-1]` 的 CAB 名（如 `CAB-a7f3...`）→ 用 CAB 名反查所在 bundle 文件（依赖表 / 全量扫描 CAB→包映射）→ 在该包内按 PathID 精确匹配对象。
3. PathID 匹配不可省略：一个纹理包常有多个 mesh/sprite，按顺序、面积、命名猜都会错拿（2b 的 rw 节点 FileID=2 → externals[1] 才是正确的 `2b_rw_tex`，按 manifest 字母序会错配成 `bj1_tex`）。

### 特殊包结构（碧蓝航线）

| 包 | 结构 | 要点 |
|---|---|---|
| `paintingface/<name>` | 包内 Texture2D+Sprite 命名 `1..N` | 即表情差分序列；face 节点 PPtr 直接指向该包；差分输出 `{name}_face{k}.png` |
| `spinepainting/<name>` | **内联型**：主包含 skel/atlas/tex | 如 `2b_2` |
| `spinepainting/<name>` | **分离型**：资源在 `<name>_res` 包 | 如 `aersasi`；只找主包会"放不出" |
| spine 无后缀变体 | 包内文件无 `.skel.bytes` / `.atlas.txt` 后缀 | 如 `beierfasite_g`；**skel 头部也是 ASCII 文本**，不能靠扩展名或"是否 ASCII"区分，按内容特征嗅探（atlas 有 `size:`/绑定页名行，skel 有版本串如 `3.8.99` + 二进制节结构） |

### face 兜底约束

纹理找不到时，仅对 `go_name == 'face'` 的节点去 `paintingface/<bundle_name>`（无 `_tex` 后缀命名）兜底；对全部缺纹理节点兜底会把 UI 热区错误匹配出可见纹理。

## 三、批量运维细则

- **UnityPy 版本回退（新脚本必设）**：游戏把 UnityFS 头部 `unity_version` 伪装成 `5.x.x`，每个读 bundle 的入口脚本头部照抄 v2 脚本写法：`from UnityPy import config` + `config.FALLBACK_UNITY_VERSION = "2022.3.62f3"`。验证：运行日志出现 `UnityVersionFallbackWarning` 即生效；或拿一个此前失败的包（如 `bg/bg_project_explorer_cg1`）做样本重导确认能出图。排查加载失败时第一步 `grep FALLBACK_UNITY_VERSION scripts/` 核对每个入口脚本。
- **编码**：分离进程（Start-Process 重定向）stdout 默认 GBK，任何非 ASCII print（哪怕一个 `✓`）都会 UnicodeEncodeError 令整轮记为失败（图像实际已写出）。主进程 `sys.stdout.reconfigure(encoding='utf-8')` + 子进程 env `PYTHONIOENCODING=utf-8`，双保险。
- **PowerShell 经 Git Bash**：命令串含 `$_`、`$env:` 会被 bash 提前展开成空值——凡含 `$` 的 PS 逻辑一律写成 `.ps1` 文件再 `powershell -File` 执行（参考 `scripts/kill_stale_run.ps1`）。
- **重启批处理前先确认旧进程已终止**，否则双进程并发写同一输出目录产生混合产物；错误产物移入 `.trash/<描述>_<日期>/` 而不是删除。
- **命令行参数**：可能带 `\r`（CRLF 文件喂参），main 入口统一 `strip()`，否则伪装成"文件不存在"。
- **断点续跑**：`run_v2_full.py` 按输出目录已有产物跳过；重跑前若代码语义变更须先清旧产物（移回收目录），否则新旧算法产物混在一个目录无法分辨。
- **进度监控**：`tail Output/run_v2_full.progress.log`；跑完做随机抽样拼图（`make_contact_sheet.py`）+ 失败清单逐条排查（ERRORS.log）。

## 四、历史教训对照（为什么禁止手调参数）

| 样本 | v1 手调参数 | v2 数据驱动结果 |
|---|---|---|
| feiteliekaer_3 | S=0.844 + dx=160 + dy=-190 | 零参数自动躺正浮床 |
| hailunna_4 | BUNDLE_BJ_ABSOLUTE=(1.50,1447,1244) | 零参数酒杯自动落栏杆扶手后 |
| 2b | 逐层面积猜测排序 | externals 反查 + PathID 匹配，层序比例全对 |

结论：v1 时代所有"调参"都是在补偿解析错误。v2 若某样本不对，唯一正确动作是回到第一/二章找解析姿势问题。
