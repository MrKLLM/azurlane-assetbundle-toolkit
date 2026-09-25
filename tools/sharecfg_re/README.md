# sharecfg_re —— 逆向 `sharecfgdata/*` 解密（独立小项目）

**目标**：解出 `files/AssetBundles/sharecfgdata/` 里 34 张配置表的明文，**首要目标是 `ship_skin_words`（皮肤台词表，字幕文本源）**。

**为什么值得做**：一次解通，台词文本、声优中文姓名、阵营名表、9.7.385 新皮肤归属一次全解决，且是一手权威数据。爬 wiki 只是二手兜底。

## 素材（已全部在手，**不需要跑模拟器**）

| 文件 | 大小 | 用途 |
|---|---|---|
| `files/il2cpp/libil2cpp.so` | 121.8 MB | ELF64，**已剥离 `.symtab`**（只有 `.dynsym` 2695 个 `il2cpp_*` 运行时 API）→ 游戏自身方法无符号，必须靠 metadata 反查 |
| `files/il2cpp/Metadata/global-metadata.dat` | 18.2 MB | 魔数 `FAB11BAF` 正常，**version=31**（比常见 24–29 高，待判定是新 Unity 还是被改过头） |
| `files/il2cpp/Resources/*.dll-resources.dat` | 1 MB | .NET 附属库资源；出现 **Newtonsoft.Json** 与 **I18N.CJK** → 解密后是 JSON 交给 Newtonsoft，且要处理中文编码 |
| `files/AssetBundles/sharecfgdata/*` | 34 张 | 密文表本身 |
| `inputs/azdata/azdata_ship_{skin_template,data_statistics,data_template}.json` | 9.2 MB | **已知明文**（社区 dump）——自证用的黄金基准 |
| `files/il2cpp/unity.ver` | 36 B | `447c407d-09a0-4c15-987b-4a8d452240d4`，metadata ↔ so 的配对 id |

## 判据（唯一验收标准）

**`ship_skin_template` 解密结果必须与 `inputs/azdata/azdata_ship_skin_template.json` 逐字段一致。**

有一张已知明文的表存在，任何候选算法都要立刻拿它自证——不许「看起来像明文」就宣布成功。解对了再上 `ship_skin_words`。

## 已排除的假设（别再走这些弯路）

### 密文侧（对 `sharecfgdata/ship_skin_template`，有已知明文可校验）

| 假设 | 判据 | 结果 |
|---|---|---|
| 是 UnityFS / AssetBundle | UnityPy 加载 | 0 对象 |
| 单字节常量 XOR / 加 / 减 | 256 密钥 × 已知明文子串搜索 | 0 命中 |
| 短重复密钥 XOR（周期 1–32） | 按周期分组算 IC | 全周期 0.0152，**无尖峰** |
| 位置线性相关变换（`xor i` / `±i` / `i>>2` / `i>>8`） | 中文 UTF-8 三连密度 | 全打成随机（IC 0.0039） |
| 前一字节自同步（`xor prev` / `~prev` / `sub prev`，滞后 1–8） | 同上 | 最好 0.0027，远不可用 |
| 裸 zlib / raw deflate / bz2 / lz4.block（偏移 0–63） | 直接解 | 全失败 |
| 明文是 UTF-16 中文 | 已知串 `安土`/`皮肤`/`name`/`painting` 搜索 | 全 -1，按 UTF-16LE 解出是乱码 CJK |
| 单字母表替换（保 IC） | IC 从明文 0.044 → 0.015 | IC 被打平，不成立 |

实测特征：**熵 6.73**（真压缩/强加密 ≈ 8.0）、**IC 0.015**（明文 0.044 / 随机 0.0039）、256 种字节全出现。
→ 结论：**有真实密钥流的加密，密钥不在密文里**。纯数据侧已榨干。

### scripts64 / scripts32 两时间垫（同密钥流假设）

- 两文件前 32 字节**完全相同**、32–39 字节不同（8 字节随机值，非长度）、40–63 字节又相同，之后全随机。
- 逐字节 XOR：零率 **0.391% = 1/256**（完全随机），最长连续零段仅 32 字节。
- → **不能反推密钥流**（要么同密钥但 32/64 位编译后明文逐字节不同，要么每文件不同 nonce）。即使拿到 56 字节已知明文，对 AES-CTR / ChaCha 也只能换到对应位置的密钥流。

## 已定位的线索（metadata 标识符，137850 个 token 里筛出来的）

| 标识符 | 判断 |
|---|---|
| ~~**`XorShift64`**~~ | **已否证（09-24）**：它在 dump.cs 里紧邻 `Mul128Fold64`/`Avalanche`/`rrmxmx`/`Hash64Long$BurstManaged`，是 **Unity.Collections 的 xxHash3**（Burst）内部函数，与 sharecfgdata 无关 |
| ~~**`ctXor`**~~ | **已否证（09-24）**：`ClipperLib.ClipType.ctXor = 3`，几何裁剪库的枚举，不是 XOR 辅助函数 |
| ~~`Decrypt128`/`DecryptData`~~ / `DecryptValue` | `Decrypt(IntPtr L)` / `SetDecryptionKey(IntPtr L)` **已否证（09-24）**：都是 CRIWARE 音频（`CriWare_CriAtomEx*Wrap`）的 Lua 绑定，只管 ACB |
| **`ReadCfgFile`** | 属于 `FileHelper`（TypeDefIndex 731，RVA `0x3B6DE93`），同目录另有 `.cctor`/`ReadBytes` |
| **`LuaConfDataReader`** | **真正的配置读取类**（TypeDefIndex 1133）：`Header_32 byte[5]` / `Header_64 byte[5]` / `Footer byte[26]` + `ReadData(configName,startPos,size)` / `ReadBufferFromCSharp` / `GetConfigPath` / `confDataCacheFolderPath` |
| `AesCryptoServiceProvider` / `RijndaelManaged` / `Rfc2898DeriveBytes` / `MD5CryptoServiceProvider` | 大概率是 .NET 自带 System.Security.Cryptography 常驻链接，**不能当使用证据** |
| `CryptoCheckValue` / `CryptoHeaderSize` | 属 Ionic.Zip（DotNetZip）的 ZIP 传统加密字段，**不是** sharecfgdata 保护层 |

## 2026-09-24 实测更新：**"整体加密"这个前提被证伪，问题重新定性为"自定义二进制记录流"**

先记下三件把昨天结论直接推翻的事，再给新模型。

### (1) 环境事实纠正：`libil2cpp.so` 是 **x86-64**，不是 ARM64

实测 ELF 头：`EI_class=2, e_type=3(ET_SHARED), e_machine=0x3E(x86-64)`，来自 **x86 安卓模拟器（MuMu）**。
两个直接后果：

- 函数起始地址是 `0x3C1577A` 这种**非 4 字节对齐**值——x86 变长指令的正常现象，**不是"metadata 头被改过"的证据**；昨天挂心的 version=31 判定，实际 Il2CppDumper 已能正常跑通（136,652 个方法全部解出）。
- 本机 mingw 的 objdump / capstone 直接可用，**不需要**为 ARM 找交叉工具链。

`.diag/sharecfg_re/dump/` 里其实**早就躺着完整产物**（`dump.cs` 44MB 带每个方法的 RVA/Offset、`il2cpp.h`、`script.json`、`stringliteral.json` 29101 条字面量、80 个 DummyDll）——昨天把"跑 Il2CppDumper"记成待办，白绕了一轮。新增工具 `08_disasm_method.py` 把 dump.cs 与 so 接起来（符号→机器码，解析 ELF 段表、`.rela.dyn` 重定位、字面量 blob），并缓存 `method_index.json`。

### (2) C# 侧**零解密**已由机器码证实（不再是推断）

- `LuaConfDataReader.ReadBufferFromCSharp` → `GetConfigPath` = **`Path.Combine(confDataCacheFolderPath, configName)`** 尾调用，随后 `new FileStream(...)` + `new BinaryReader(...)`，reader 存进 `Dictionary<string,BinaryReader> readerDict`。**链上没有任何 crypto stream。**
- `ReadData` → `CheckArraySize` + `ReadBufferFromCSharp` + `Buffer.BlockCopy`，纯搬运。
- `.cctor`（RVA `0x3C1577A`）确实是 `Array::New(5)/(5)/(0x1a)` + `RuntimeHelpers.InitializeArray`，三个句柄 `0x80000023`/`0x80000005`/`0x80000027` 是 **FIELD 元数据 token**（不是 fieldDefaultValues 下标——昨天按 `&0x7fffffff` 当条目号解，所以取出等差序列，那条否证是对的但归因错了）。

### (3) 盘上没有明文，也确实不可能有——adb 分支已彻底封死

用 MuMu（已运行，`127.0.0.1:16384`/`:7555`，**`su -c id` = uid 0**）做只读勘察：

- 游戏进程（pid 2929）fd 表显示 29 张表**直接从 `AssetBundles/sharecfgdata/` 只读打开**（`fd 256 -> .../ship_skin_words`），全盘 `find` 无 `confdata`/`sharecfg` 缓存目录，`/data/data/<pkg>/{files,cache,...}` 逐目录看过只有 SDK/埋点。→ **`confDataCacheFolderPath` 就是 AssetBundles 根本身**，"设备上有解密缓存可捞"这个假设作废。
- 设备上的表与本地 md5 逐张一致，版本 **9.7.385**，`version-s.txt=64`。→ 本地 dump 就是最新，不存在"旧版明文"旁路。
- Lua 侧无任何明文落地；运行时是 **tolua#/LuaJIT**（`lib/x86_64/libtolua.so`，logcat 有 `LuaInterface.ToLua:Print`、`LuaState:PCall`）。
- 意外收获：`originsource/cipher/soundstory2_jp.txt` 是**纯 UTF-8 明文台词**，格式 `台词文本#起始#结束`——正是语音字幕对齐结构，可作为 `ship_skin_words` 解出后的**目标格式参照**；同目录 `.cpk` magic `CPK @UTF` 是标准 CRIWARE 未加密（"cipher" 只是目录名）。`files/hashes*.csv` 是 **MD5 清单**（已验证 txt 的 md5 与记录一致），可用来校验本地 dump 完整性。

### (4) 已知明文自撞：三张有基准的表**全部 0 命中**（并纠正我自己的一个方法论错误）

`09_plaintext_probe.py`：从 `inputs/azdata/*.json` 逐字抽 **4634 个中文串 + 5680 个 ASCII 键名**，UTF-8 / UTF-16LE / GBK 三种编码撞**它自己那张表**：

| 表 | 中文命中 | ASCII 键名命中 | IC | 熵 | 可打印串占比 |
|---|---|---|---|---|---|
| ship_skin_template | **0** | **0** | 0.0152 | 6.726 | 2.15% |
| ship_data_statistics | **0** | **0** | 0.0249 | 6.245 | **0.00%** |
| ship_data_template | **0** | **0** | 0.0213 | 6.133 | **0.00%** |

⚠️ **方法论教训（写进 TROUBLESHOOTING）**：第一版我把从 `ship_skin_template` 抽的词表去撞 `gametip`/`ship_skin_words`，得到"0 命中"就当成加密证据——**词表与表内容本来不同源，0 命中不说明任何问题**。已知明文检验必须**逐表自撞**，只有手里有基准的那 3 张表的结果才算数。

### (5) 我自己的一个假信号，以及它反向暴露的真结构

`10_pad_and_ecb_probe.py` 初测"32 张表两两 XOR 零率中位 1.84%、最高 4.98%（随机基线 0.391%）"，我当场判"存在共密钥流"。**这个判定是错的，是我阈值定松了**：`11_consensus_keystream.py` 补了零假设对照——32 张表**只共享字节分布**时的预测两两相等率 = 分布 IC = **1.904%**，实测中位 1.84% 完全落在预测值里；逐列共识度均值只有 **0.102**，8192 列里只有 11 列 >90%（就是那 8 字节尾 + 构造性相同的前导）。→ **不存在共密钥流，两时间垫 / 列共识反推密钥流两条路都封死**（用众数当伪密钥流解密后仍无中文，熵不降）。

但同一个探针的第 3 步给出了**真正的结构信号**，而且它本身就否证了"整体流加密"：

- **单文件内 16 字节块大量重复**：gametip 里 `90998f9389099d9f8e99078f9907a0b9` 重复 **506** 次、`4eff000051ff010151ff020251ff0303` 重复 **499** 次。按实测 IC 算，iid 流下这类 16B 碰撞的期望值是 1e-6 量级——**差 9 个数量级，加密流不可能有这种重复。**
- **昨天说的"Footer 8 字节"根本不是文件封尾**：`8e 99 07 8f 99 07 a0 b9` 在 gametip 出现 **7929** 次、`ship_skin_template` **2865** 次、`ship_skin_words` **2601** 次——它是**每条记录里的常量段**。
- **记录数与表行数对上**：`ship_skin_template` 该标记 2865 次（azdata 基准行数 **2863**），相邻间隔中位 ~1400B，2865×1400 ≈ 4.01MB vs 实际 4,066,129B ✓；gametip 7929 次 × ~172B ≈ 1.36MB = 文件全长 ✓。
- **头部已是可解的定长记录**：body 起点由公共前导 `4e ff 00 00 | 51 ff 01 01 | 51 ff 02 02 | 51 ff 03 03 | 4d fe …` 给出，按 LE32 读是 `0x0000FF4E, 0x0101FF51, 0x0202FF51, 0x0303FF51`——即 **4 字节记录 [tag 可打印 ASCII 0x4c..0x57][递减计数 ff→fe→fd→fc][k][k]**；文件更前面是变长头（`8b 44 05 05 00 00 00 b7 03 8e 08` / `43 02 02 00 00 00 06 07`，含 LEB128 样式的 3/4/5 字节小整数）。

**新定性**：这不是"整表 AES/密钥流"，而是**变长记录流 + 明文索引头**，其中数值/索引区基本是明文（所以有大量重复块和可解记录），**只有文本载荷区被变换**（所以中文 0 命中、整体熵被抬到 6.7~7.8）。这也和 C# 侧只做 `(startPos,size)` **定点切片读**完全自洽：Lua 先读索引区定位行，再只读需要的那段。

### (6) 会话后半：找到了 Lua 包的解密函数 `www()`，并再加三条否证

调用链已用机器码打通（`08_disasm_method.py` 逐跳追）：

```
LuaScriptMgr.Load                RVA 0x3D9C784
  → PathMgr.getLuaBundle         → 字面量 'scripts32' / 'scripts64'（PathMgr.is32Bit() 选）
  → PathMgr.ReadAllBytes         → PathUtil.ReadAllBytes
       = File.Exists ? File.ReadAllBytes : BetterStreamingAssets.ReadAllBytes   ← C# 仍无解密
  → **www(byte[] BytesBuffer)**   RVA 0x3D9CA20   ← 唯一的 byte[]→byte[] 变换，在这里
  → LuaScriptMgr.LoadABFromBytes → AssetBundle
```

`www` 已反出骨架（x86-64，`0x3D9CA20` 起）：

* 取数组**末尾 4 字节**按小端拼成一个长度值 `len`（`B[n-4] | B[n-3]<<8 | B[n-2]<<16 | B[n-1]<<24`），并 `n -= len` —— 末尾 4 字节是**明文长度 trailer**，其后是填充；
* `Array::New(0x13)` 分配 **19 字节**密钥，再用 `RuntimeHelpers.InitializeArray` 从全局 `0x71E4C10`（一个 FIELD token）装载内联常量；
* 之后是逐字节还原主循环（`0x3D9CCD5` 起，本轮未逐条读完）。

⚠️ 但**盘上的 `scripts64` 末尾 4 字节 = `99 07 a0 b9` = 0xB9A00799，不是合法长度** →
`www` 的输入**不是**我们手里这份 `files/AssetBundles/scripts64` 原文件，中间还有一层
（很可能就是 `LuaConfDataReader` 的 `Header_32[5]` / `Footer[26]` 封帧，或 BSA 归档条目与 loose 文件不同）。
这条是**下一步的第一个待验证假设**，不是结论。

新否证三条（都带对照，`09`/`12`/`15` 号脚本）：

| 假设 | 判据 | 结果 |
|---|---|---|
| 已知明文以某种常见编码直接躺在表里 | 用**该表自己的** azdata 词表自撞（4634 中文串 × UTF-8/16LE/16BE/GBK） | 3 张有基准的表**全部 0 命中**；另加整串位平移 1..7 也 0 |
| 短周期重复密钥（周期 2/3/4/6/8/12） | 用 UTF-8 三字节区间约束做**可分**逐残差类求 key，看合法率与真中文 | 合法率最高只到 0.012（真汉字文本应 0.2+），已知明文 0 命中 → **否证** |
| v31 fieldDefaultValues 可按 token rid 索引 | `224340 % 12 == 0` 自证步长 12；但按 rid 取回仍是等差字节、`typeIndex` 列恒 30420 | **未解出正确索引法**；`Header/Footer`/`www` 的 19 字节 key 仍拿不到 |

lag 自相关（15 号脚本前置实测）：`ship_skin_words`/`gametip` 在 **3/6/9/12** 上倍频尖峰
（lag3 = 3.96× / 7.11×），`ship_skin_template` 在 **4/8/12/16/32** 上尖峰。
前者与"UTF-8 三字节汉字"同型、后者与 4 字节记录同型 —— 但短周期 XOR 已被上面第 2 行判否，
所以这更像**明文自身的结构周期**被某种逐字段变换保住，而不是密钥周期。

### (7) 2026-09-24 进程内存取证（用户放行，全程只读）——**没拿到明文，但拿到了更好的路**

工具 `16_mem_hunt.py`（`maps` / `selftest` / `dump` / `hunt`）。过程与实测：

- **先踩到一个真 bug 并被阳性对照抓住**：`adb shell` 通道会把 `\n` 改写成 `\r\n`
  （请求 262144 字节回 266643）。改用 `exec-out`，并把对照做成**逐字节比对**
  （取 `global-metadata.dat` 的 `off==0` 映射区前 4KB 与本地文件比）→ **PASS**。
  ⚠️ 任何"从设备流式读二进制"的活都必须先过这一关，别用 `shell`。
- **量**：pid 2968，可读区域 2706 个 / 虚拟 3128MB，其中匿名区(堆/栈/JIT) 1299 个 / 1960.6MB；
  全量拉匿名区耗时 **6m52s**（≈17MB/s），落到 `.diag/sharecfg_re/memdump/`（gitignore）。
- **否证（重要）**：1958.5MB 匿名内存里，**azdata 的 300 个已知明文中文词 0 命中**。
  → 内存里**没有整表驻留的解密配置**，"从 RAM 直接白拿明文"这条路不成立。
  与 C# 侧证据自洽：`ReadData(name,startPos,size)` 是**按需切片读**，解出的值只短暂存在
  于 Lua 字符串里，游戏当前停在登录/主界面，皮肤表根本没被整表加载。
- **但拿到了资源地图**（内存里的路径字符串，逐条实测）：
  `assets/luabuilds/android/normal/sharecfg/ship_skin_words.lua.bytes`、
  `.../sharecfg/ship_skin_template.lua.bytes`、`ship_skin_template_column_time.lua`、
  `assets/luabuilds/android/normal/gamecfg/{buff,dungeon,skill}`、
  `assets/AssetBundles/scripts64`、`/storage/emulated/0/Android/data/.../sharecfgdata/gametip`。
  → **证实 `www()` 的输出是一个装着 TextAsset 的 AssetBundle，Lua 按表分文件**，
  且 `PathMgr.EncryptSuffix` 的 `.bytes` 命名规则得到印证。
- **新的主路径（下一步做这个）**：内存里有**大量 LuaJIT 字节码**——`\x1bLJ` 在两个区域各出现
  **5153 / 6838 次**（另有 `WorldShipRepairCommand.lua`、`W1138.lua`、`WORLD302A.lua` 等 chunk 名紧邻）。
  既然字节码已经在内存里是**解密后的形态**，就不必破解 `scripts64` 容器：
  **直接从内存提取 `sharecfg` 相关模块的字节码，反汇编/读常量池**，即可拿到配置解析算法与那把 key。

### (8) 2026-09-24 第二轮内存取证（游戏停在有台词的界面）：**拿到明文了，但不是从容器里解出来的**

进程已换（pid 2968 → 3769），旧快照隔离进 `memdump/run1_pid2968/`，并给 `16_mem_hunt.py`
补了 `--force`（原实现"文件存在且同大小就跳过"会让**重启后的进程复用上一时刻的快照**当新证据）。
新快照 1472 区域 / 2308.4MB。

**实测正获**：

1. **解密后的中文配置文本确实在内存里**（带区域与偏移）：
   `3769_...44d2e000_...45e7f000.bin`（17.32MB）内 `1913年型战列巡洋舰——马塞纳`@0x6f75c8、
   `{namecode:134}.改`@0x975a88、`{namecode:181}.改`；`...4306c000_...44d2d000.bin`（28.75MB）内
   `{namecode:38}级轻巡洋舰——{namecode:306}`@0x1a95c38。→ 上一轮"0 命中"是**游戏当时没加载**，
   不是内存里没有。**结论：按需切片读的表，只要走到对应界面就会在 RAM 里留下明文。**
2. **LuaJIT 字节码确实在内存里**：`\x1bLJ` 共 11109 次，其中 **11095 次后跟合法版本字节 01/02**
   （随机巧合的概率约 0.8%）→ 是真字节码。
3. **整棵 Lua 配置模块树的名字都在内存里**：`assets/luabuilds/android/normal/gamecfg/**.lua`
   命中 39075 个不同名字（`gamecfg/buff/buff_106040.lua`、`gamecfg/story/…`、`gamecfg/dungeon/…`、
   `gamecfg/academygraph.lua`、`gamecfg/activity/entrancedata.lua`…），
   另有 **`ShareCfg.<表名>` 注册表 754 处**（`ShareCfg.ship_skin_words`、`ShareCfg.ship_skin_words_extra`、
   `ShareCfg.ship_skin_template_column_time`、`ShareCfg.roll_attr`、`ShareCfg.guild_store`…），
   以及列名/错误串 `WORD_TYPE_SKILL`、`voice_actor_CN`、`ship_skin_template not exist: 603022 603021`。
   → **`gamecfg/**.lua` 很可能是"每张表一个 Lua 文件"的明文形态配置**，与 `sharecfgdata/` 二进制容器并存。
   如果台词也在 `gamecfg` 里，**整条"解容器"路线可能都不需要**。

**实测否证**：设备上 `scripts64`/`scripts32` 头 32 字节与本地副本**完全一致**（仍是密文，
且两文件头部彼此相同），只是体积比本地大 ~19.7 万字节、mtime 是今天 18:38（被更新过）。
→ "游戏把解密结果写回原路径"不成立；内存里那个 `scripts64__<md5>.temp` 只是加载期临时名，盘上已无残留。

**工具缺陷（已修）**：`17_mem_lj_scan.py` 第一版把 chunk 名正则写成必须以 `@`/`=` 开头，
实际内存里是**裸路径名** → 整轮扫成"0 个模块"。这是脚本的错，不是内存的错；已改成前缀可选。

### (9) 解码粒度实测：**台词明文大量驻留内存，"从内存捞"具备交付价值**

在 pid 3769 快照（2.25GB，>1MB 的区域）上量驻留量：

| 指标 | 数值 |
|---|---|
| 去重后的中文串（≥4 字节） | **104,836 种** |
| `指挥官` 出现次数 | **6,712** |
| 台词时间戳样式 `#n#n` | **14,058** |

抽样即台词本体：`指挥官难道是在侦查敌情` / `只是在检查刚入库的点心而已` / `街头的相遇`。
→ **不是"点一行驻留一行"**，用户不可能点到上万条；表在被访问后是大范围驻留的。

⚠️ 两个必须说清的限度（别把这条当成"台词表已到手"）：
1. 104,836 是**所有表**的中文串合计，不是台词行数——抽样里同时出现道具/家具名
   （`普通热水器`、`装满巧克力豆的墙柱`）与活动说明（`参与特别作战累积活动道具`）。
2. **文本与归属分离**：内存里拿到的是字符串，"这句属于哪个皮肤 id"存在 Lua 表结构里，
   串本身不带 key。所以交付前必须解决**归属**，两条路：
   (a) 按 GCstr/表结构邻接性在内存里重建 (skin_id, 台词, 起, 止)；
   (b) 拿到解析器后回原表解，归属自然齐。
   `#n#n` 计数 14,058 也需复核——它可能同时命中 `</color>` 之类的其它样式，不能直接当台词条数。

### (10) 台词行拼接尝试：**"文本#起#止"整行形态不成立**，原因已查明

`18_mem_words_harvest.py`（两种模式互校）在 2.25GB 快照上实测：

| 检验 | 结果 |
|---|---|
| 中文/ASCII 连续串 | 2,269,786 条 |
| 通过"长度前缀 + NUL"的 GCstr 结构校验 | 仅 6,274 条（**0.276%**） |
| `#起#止` 锚点向左回扫能接到中文文本（整行形态） | **0 条** |

⚠️ 两个诚实的限定：整行 0 命中**不等于**内存里没有台词——裸锚点 `#n#n` 上一轮实测有 14,058 个，
只是它们**前面接不到文本**；而 0.276% 的 GCstr 通过率说明**我这个校验本身不足以当裁判**
（LuaJIT `GCstr` 的 `len` 字段偏移我按 8..48 字节回扫都没能覆盖住大部分真串），
所以"结构确认率低"不能用来否定"内存里有 Lua 字符串"。

**直接看邻接结构得到的真相**（取已确认台词 `只是在检查刚入库的点心而已`，
位于区域 `...049537000_00000052bfd000.bin @0x7b3973c`）：

- 它**前面 96 字节还是别的台词正文**（`…{namecode:75}没偷懒哦，`、`（难道是指挥官？）“咕噜”。`），
  **句与句之间没有 NUL、没有 `#起#止`** → 多条台词是**首尾相接连续存放**的（像一整块序列化缓冲），
  不是"一条一个字符串对象"。这就是整行模式必然 0 命中的原因。
- ±8KB 内另有 16 条中文串，密集分布在 -7084/-7024/-6971/-6953/-6882，内容同为用户台词。
- **文本里带的是 `{namecode:NNN}` 占位符**（`{namecode:75}`、`{namecode:143}`、
  `{namecode:38}级轻巡洋舰——{namecode:306}`），**不含皮肤 id** → 归属信息不在文本里。

**结论与改道**：靠"在内存里切台词行"拿不到 (皮肤id, 台词, 起, 止) 四元组；
内存能给的是一整块**已解码的台词正文**（含 namecode 占位符）。因此：
1. 短期可交付的是**台词正文语料**（去占位符后可用于字幕/检索），但**无法按皮肤归位**；
2. 要拿到归属与时间轴，仍须回到**解析器**路线（`gamecfg/**.lua` 字节码 或 `www()`）；
3. 附带价值：`{namecode:NNN}` 正是"数值码→名字"的另一张表，**§6 待办 7 的阵营码问题**
   可能需要一起从这张 namecode 表解。



### (11) `{namecode:NNN}` 查明：**配对oracle 成立**，namecode 是"码→舰名/级名"索引

`19_namecode_probe.py` 实测（2.25GB 快照，锚点 `级轻巡洋舰——`）：

- **码空间**：出现过的码 **340 种**，总引用 **4077 次**，范围 **2..10006**；
  高频 97(173)、98(159)、91(82)、18(69)、22(68)、11(64)、408(56)、50(52)、6(49)…
  → 编号跨度与分布都**不符合** `build_ship_meta.py` 里那套 nationality(1..115) 码，
    说明 namecode 是**另一张"码→名字"表**的索引，不是阵营码本身。
- **模板与成品同时驻留**（这是关键）：模板 `{namecode:38}级轻巡洋舰——{namecode:306}` 与
  已解析成品 `克利夫兰级轻巡洋舰——帕萨迪纳`、`迪盖·特鲁因级轻巡洋舰——迪盖·特鲁因`、
  `南安普顿级轻巡洋舰——南安普顿，舷号C83`、`…谢菲尔德，舷号C24`、`确捷级轻巡洋舰——确捷，舷号08`
  都在内存里 → **占位符是在运行时被替换的，替换结果留在 RAM 里**，所以存在可用的对齐 oracle。

**还没证明的（别过度解读）**：上面 5 条成品与那条模板**不是同一行**，所以**还不能由此得出 38=克利夫兰**
这类具体映射。要拿到映射必须做"同一行的模板↔成品"配对，两条可行路：
1. 按**邻近性/结构位置**配对：同一行的模板与成品在堆里通常相邻或被同一表结构引用；
2. 直接定位那张**名字数组表**（GCtab 数组部分是连续的 GCstr 指针），按序号读出整表——
   一次拿全 340+ 个码，比逐对配更划算。

**与 §6 待办 7 的关系**：目前证据只说明 namecode 表能给出**舰名/级名**，
阵营名是否也在同一张表里**未证**；要判这条，只需看某个已知阵营的码能否在其中对上。

### (12) 邻近配对法判否：模板与成品**不在同一分配区**，成品样本仅个位数

`20_namecode_pairs.py`（按"同一行模板串与成品串在堆里相邻"配对，窗口 ±8KB，
要求窗口内唯一才记观测，>=3 条独立观测且无冲突才入表）实测：

| 量 | 值 |
|---|---|
| 模板命中 | **178 处** |
| 可配对观测 | **0 条** |
| 歧义丢弃 | **0 条** |

"配对 0 且歧义也是 0"这个组合本身就是诊断：说明**含模板的那些区域里一条成品都找不到**，
不是"配对歧义"，而是**两类串根本分布在不同分配区**（配置表原文 vs 显示期拼接产物）。
叠加 19 号只搜到 **5 条成品**（成品只在"玩家真正看过的那几行"才存在，且会被 GC 掉），
邻近配对这条路在当前快照下不成立。

**由此得到的硬约束**：想靠内存配对拿映射，缺的是**成品样本量**，不是算法。
两条可选路：
1. **扩大成品样本**：在皮肤详情里连续翻几十个不同舰种的皮肤再抓快照，
   把成品从个位数抬到几百条；然后改用**结构求解**（同 A 码的舰必属同一级，
   与我们已知的舰级归属做图匹配），不依赖邻近性。
2. **直接定位名字数组表**：找 GCtab 数组部分（连续 8 字节指针指向中文 GCstr），
   按序号整表读出，一次拿全 340+ 码。

外部裁判集合已备好：`Output/ship_meta.json` 递归收集到 **4030 个已知名字**，可直接用于校验。

### (13) 路 B（直接扫 Lua 名字表）**判否**，但换来一个更值钱的判断

先说工具的不可信处：`21_namecode_table.py` 依赖"GC64 指针的类型标签在 bit40..43"这个**我凭记忆写的
假设**，从未验证。所以改用**测量代替假设**：取一条已确认台词 `帕萨迪纳`（VA `0x43effd04`，
位于区域 `...4306c000_...44d2d000.bin` 内偏移 `0xe93d04`），在全快照所有 u64 里搜
"低 48 位 == 该 VA 减去某个对象头偏移"。

| 头偏移假设 | 命中 |
|---|---|
| -8 / -16 / -24 / -28 / -32 / -40 / -48 | **全部 0** |
| 直接等于数据 VA | **0**（上一轮已测） |

→ 快照里**没有任何指针指向这条串**。再结合"该串前 32 字节仍是别的台词正文"
（`…个惊喜需要指挥官和`），结论是：

**这批台词文本不是逐条分配的 Lua GCstr，而是一整块连续解码缓冲。**

这条否证顺带否掉了 (12) 里"扩大成品样本再配对"的可行性前提——成品不是独立字符串对象，
所以"表"也不会长成 GCtab 指针数组的样子。

**改道（下一步做这个）**：去找**那块连续缓冲本身的边界与内部记录结构**。
它比任何指针表都更接近"解码后的表本体"：
1. 从已知偏移向两侧扩展，用"是否仍是可读 UTF-8 文本/小整数"定边界，量出这块缓冲多大；
2. 在里面找**记录分隔符**（上一轮已知句与句之间没有 NUL，说明分隔符是别的字节或长度前缀）；
3. 若同一块里还有别段（阵营名、舰名列表），`{namecode}` 的映射表**可能就在这块缓冲的某一段里**——
   这比猜 Lua 内存布局靠谱得多，因为它就是配置本体。

### (14) 路 B 的真正收获：内存里有 **`sharecfg/<表名>.lua` 文件清单**，含 `ship_skin_words.lua`

修好 17 号脚本的正则后（"0 个模块" → **6390 个模块**，说明上一轮那个 0 是脚本的错），
改用"按名字反查所在块"，实测：

- 含 `sharecfg` 的 `.lua` 名 **776 种**，逐个对应一张配置表：
  `assets/luabuilds/android/normal/sharecfg/{achievement_data, activity_7_day, activity_banner,
  activity_clue, ...}.lua`，并且**直接命中 `ship_skin_words.lua` 与 `ship_skin_words_extra.lua`**。
- 这些名字**不在 LuaJIT 字节码块里**（同区域 4KB 内无 `LJ` 头，776 种全是"无"），
  而是以 `00*6 + 名字 + 00` 的形态出现 → 这是一张**文件清单（名字→数据）**，
  即解密后的 `scripts64` 包在内存里的索引。

**由此统一解释 (10)/(13) 的"一整块连续文本"**：那块连续台词缓冲很可能就是
**`ship_skin_words.lua` 的文件内容本体**（Lua 源文件本身就是一大段连续文本）。
若是，则它里面**本来就带着 skin id 与台词的对应关系**（Lua 表的 key），
(13) 里"文本与归属分离"这个障碍会自动消失——归属不在别处，就在那段源码文本里。

**下一步（很具体）**：按清单条目里名字字段前后的 `offset/size` 字段，定位 `ship_skin_words.lua`
对应的内容缓冲，直接把它作为 Lua 源码读出来；读出来就是可用的台词表，不需要再解 `sharecfgdata` 容器。

### (15) `www()` 主循环读出 + 两条判否（含一次我自己差点又吃下的假绿灯）

**拿到的（可直接采信）**

- **`Header_64 = 1b 4c 4a 02 02`** —— 这是**直接观察**到的：内存里一批配置块以这 5 字节开头，
  紧跟的 body 与磁盘 `sharecfgdata` 逐字节同语法（`23_container_align.py` 双向最长连续匹配
  146 字节）。之前 `LJ` 被我当成 LuaJIT 字节码（"11095 个合法版本字节"）——**那是这个容器魔数**，
  17/22 号脚本据此得到的"字节码模块/常量池"结论全部作废。
- `www()`（RVA `0x3D9CA20`）骨架：尾部 4 字节小端 = 明文长度（其后是填充）→ `Array.Copy` 搬数据 →
  `Array::New(0x13)` 建 **19 字节**常量数组 → 一个反馈循环。

**先更正我自己的一条错判**：我一度说"那个反馈循环不作用于文件数据"，**这是错的**——
`0x3D9CB90` 把 `Array::New(len)` 的结果写进静态槽 `+0x10`，而循环读写的正是 `[[klass+0xb8]+0x10]`，
所以**它就是作用在 `www()` 的输出缓冲上**。而且种子是硬编码常量：**`mov ebp, 0xeb` = 235**（`0x3D9CC33`）。
完整算法因此是**参数无关、已完全拿到**的：

```
state = 235
for i in range(n):
    c = buf[i]
    buf[i] = ((state >> 8) ^ c) & 0xFF
    state = ((state + c) * 205 + 207) & 0xFFFFFFFF
```

**判否 1（改判后的正确说法）：这套算法不适用于 sharecfgdata，也不适用于盘面上的 scripts64/32。**
实测：拿它对 `gametip`/`weapon_name`/`ship_skin_words`/`ship_skin_template` 从偏移
0/8/9/10/11/12/16/24 起变换，可打印率 0.37~0.38（随机水平）、无中文；
对 `scripts64`/`scripts32` **穷举起始偏移 0..4095**，没有任何起点能产出 `UnityFS` 或 `00 00 00 07`。
→ `www()` 的输入**既不是配置表、也不是盘面上这份 scripts 文件**，外面那层封装（或 19 字节数组参与的
额外一步）仍未解出。这是当前唯一的堵点。

（下面这段是当时的错误推理，保留以免重犯：）循环体是
`c=buf[i]; out=(state>>8)^c; state=(state+c)*0xCD+0xCF`（205/207），但它读写的地址是
`[[klass+0xb8]+0x10]`，即**静态字段里的第三个数组**，不是文件缓冲。
实测拿它按 `state=0` 跑磁盘文件：可打印率 0.36~0.38（随机水平）、无中文 → 判否。
它更像是**密钥流/种子发生器**。

**判否 2：从内存盲扫 19 字节数组，且"校准"本身是假的。**
`24_find_key_array.py` 想用已知的 `Header_64` 校准 IL2CPP 数组对象头（`max_length`@+24、数据@+32），
报"校准通过 2 处"。但把那 2 处的上下文打出来就露馅了：
`…0b 00 00 00 57 37 33 32 30 30 31 2e 6c 75 61` = "**W732001.lua**"、
`…0e …31 30 31 30 38 38 33 2e 6c 75 61` = "**1010883.lua**" —— 那个 `05 00 00 00`
只是别的结构里恰好等于 5 的整数。**"值对上了"不等于"布局对上了"**，据此捞出的 byte[19] 候选
全是 `GlobalSign Root CA`、`Unity.TextM`、成对堆指针之类的无关物。**本条判否，脚本保留但结论作废。**

**方法账**：这是本项目第 5 个"假绿灯"家族实例（前 4 个见 §24 与 (5)）。共同形状都是
**拿一个局部巧合去支撑一个结构性结论**。对策已固化：校准样本必须**同时**通过
"值匹配 + 周边结构合理（klass/monitor 是指针、bounds 合理）"两道，缺一即判未校准。

### (16) 2026-09-24 `www()` 的调用方查明：**唯一调用方 = `LuaScriptMgr.Load`**

> ## ⛔ 本节曾被写入两条**错误结论**，先更正再读（同日自查，靠 `--xref LuaScriptMgr.LoadABFromBytes`）
>
> **错误 1（致命）**：我写"`www()` 的输出直喂 `luaL_loadbuffer`，故'输出须含 `UnityFS`'这条判据
> **本身不可达**"。**这是错的，那条判据是可达、可用的。**
> 真因是我**没有逐条读完** `LuaScriptMgr.Load` 的收尾就直接断言：`0x3D9C8F6` 处其实是
> `4c 89 fe / mov rsi, r15`（把 www 的输出搬进 arg1），`0x3D9C8F9` 是 `mov rdx, rbx`，
> **真正的 call 在 `0x3D9C8FC` → `LuaScriptMgr.LoadABFromBytes`**（`dump.cs`:
> `private IEnumerator LoadABFromBytes(byte[] bytes, Action<AssetBundle> callback)`），
> 下一条 `0x3D9C909` 就是 `MonoBehaviour.StartCoroutine`。`test al,al`、`0x35ae110`、
> `"@"+filename` 全是我编的。**www() 的输出去向 = AssetBundle**，所以
> **`UnityFS` 恰恰是正确的验收判据**。(6) 当初画的链条（`→ LoadABFromBytes → AssetBundle`）从头到尾是对的。
>
> **错误 2**：我写"19 字节数组只被读 byte[4] 当种子"。`0x3D9CB2C` 之后那段我同样没读完：
> `Array::New(0x13)` + `InitializeArray` 之后，`0x3D9CC12-0x3D9CC19` 是
> `mov cl,[r14+rbp]; mov [rax+rdx+0x20],cl` 的**逐字节拷贝**循环，不是"取一个字节"。
> 该数组到底怎么参与，**状态回到"未读完"**，见下方「下一步」。
>
> **仍然成立、且是本轮真收获的部分**：① `www()` 全库**唯一**调用方是 `LuaScriptMgr.Load`
> （`--xref`，且已验索引 `VA` 零缺失、`RVA==VA==Offset+0x4000` 恒等）；② `Load` 的输入侧
> = `PathUtil.GetLuaBundle()` → `PathUtil.ReadAllBytes()`（`0x3d9c9c3`/`0x3d9ca16` 两处尾调用）；
> ③ **密钥流只依赖种子低 16 位**（闭合性 2000×9 自检 0 不一致），故"有效种子 = 65536 个"可**真穷举**，
> 这条**不依赖**上面两处错误，是纯递推式性质；④ 由此得到的否证比 (15) 的"起点穷举"硬：
> **65536 个有效种子 × 偏移 0..4095，`UnityFS` 0 命中**（64 位约束，期望假命中 1.5e-11）。
>
> **这条否证现在的正确读法**：它说的不是"判据无效"，而是**盘面上这份 39MB 的 `scripts64`/`scripts32`
> 不是 `www()` 的输入**——与 (6) 早已独立指出的"盘上 `scripts64` 末 4 字节 = `0xB9A00799`，
> 不是合法长度 trailer"是**同一结论的两条独立证据**。(6) 给的候选（`LuaConfDataReader` 的
> `Header_32[5]`/`Footer[26]` 封帧，或 BSA 归档条目 ≠ loose 文件）**依然是活的，仍是主堵点**。
>
> **方法账（这次是反面教材）**：本项目第 **7** 个假绿灯家族实例，且形状最新——
> **"我以为我读过那条机器码"**。前 6 个是"拿局部巧合支撑结构结论"，这一个是
> **拿没读完的指令序列凭印象补全，还写成了'一条机器码就能定死'**。
> 对策：**凡要据此改判整条分支的去向（输入/输出边界），必须把该调用点前后指令逐条贴出来引用，
> 缺一条就不许写"定死"**；本轮漏的就是 `0x3D9C8CD-0x3D9C8F9` 这 13 条里的 callee 身份。

**拿到的（可直接采信）**

- **`www()` 的唯一调用方是 `LuaScriptMgr.Load`**：
  `py -3 tools/sharecfg_re/08_disasm_method.py --xref "UnitySourceGeneratedAssemblyMonoScriptTypes_v1.www"`
  → 全库 **1 处**：`call @0x03D9C8C5  宿主=LuaScriptMgr.Load`。
  （`UnitySourceGeneratedAssemblyMonoScriptTypes_v1` 是 Il2CppDumper 的错归类；`www`、`Load`、
  `LoadABFromBytes` RVA 全在 `0x3D9D248` 邻域，同属 `LuaScriptMgr` 那个源文件。
  索引 136652 个方法 **`VA` 字段零缺失、`RVA==VA==Offset+0x4000` 恒等**，故"宿主方法"归属可信。）
- **`Load` 的输入侧**（逐条读到的两处尾调用）：
  `0x3d9c9c3 jmp PathUtil.GetLuaBundle` →（(6) 记录该函数返回字面量 `scripts32`/`scripts64`，按 `PathMgr.is32Bit()` 选）
  → `0x3d9ca16 jmp PathUtil.ReadAllBytes`。
- **`Load` 的输出侧**：`www()` 结果 → `0x3d9c8fc call LoadABFromBytes(byte[], Action<AssetBundle>)`
  → `0x3d9c909 StartCoroutine`。**即 www() 的产物是一个 AssetBundle。**
- **封装位谓词**（`0x3d9c7d2-0x3d9c8b1` 区间，`len>=14`、`m = bytes[len-14]&~0x80`、
  `m==0 且 bytes[0]==0x1B 且 bytes[1:4]=="lua"` 则跳过 www）：这段是逐条读过的，**但既然同函数
  别处我读漏过，此谓词在用作判据前应再独立复核一遍**。`\x1blua` 这个字面量确实从 `0x7185F00` 解出
  （`1b 6c 75 61 00`），与 Lua 字节码签名 `\x1BLua` 只差大小写。



**`LuaScriptMgr.Load` 的真实形状（RVA 0x3D9C784；只列我逐条贴得出指令的部分）**

```
0x3d9c9c3  jmp  PathUtil.GetLuaBundle      ; 取要读的东西的名字（(6): 字面量 scripts32/scripts64）
0x3d9ca16  jmp  PathUtil.ReadAllBytes      ; → byte[] bytes
0x3d9c8c5  call www(bytes)                 ; → rax = byte[]，0x3d9c8ca mov r15, rax
0x3d9c8f6  mov  rsi, r15                   ; arg1 = www 的输出
0x3d9c8f9  mov  rdx, rbx
0x3d9c8fc  call LuaScriptMgr.LoadABFromBytes(byte[] bytes, Action<AssetBundle> callback)
0x3d9c909  call MonoBehaviour.StartCoroutine
0x3d9c920  call LuaFileUtils.get_Instance  ; 失败路径（抛 LuaException）
```

→ **`www()` 的产物被交给 `AssetBundle.LoadFromMemory`（协程版）**。
→ 因此 **(15)/(6) 定的判据"输出须含 `UnityFS`"是正确且可达的**，本轮一度宣布它"不可达"是错的（见本节顶部更正）。
→ 顺带一个此前没被写清的事实：`Load` 这个函数名叫 `Load` 但**签名是 `byte[] → AssetBundle`**，
  它**不是** Lua 的 `require` 加载器；`(14)` 那 776 项 `sharecfg/<表名>.lua` 与它的关系**尚未证实**，
  不要再把 `www()` 叫作"Lua 文本解密封"——它的输出是个 AB 容器。

**19 字节数组 / 种子的具体参与方式：状态回退为「未读完」**

本轮两次试图给结论都在同一段指令上出错（先"19 字节内联密钥"、后"只取 byte[4] 当种子"），
原因是 `www()` 的后半段（约 `0x3D9CB48`–`0x3D9CCD5`）我并没有逐条读完：
`Array::New(0x13)` + `InitializeArray` 之后紧接的是
`0x3D9CC12 mov cl,[r14+rbp]` / `0x3D9CC19 mov [rax+rdx+0x20],cl` 的**逐字节拷贝**循环
（rbp 递增、边界 `r12+rbp < len-4`），说明那个数组参与的是**整段搬运**而不是取一个字节。

- **仍然可信**：`0x3D9CC33` 的 `mov ebp, 0xEB`（= 235，(15) 与本轮两次独立引用同一地址）。
- **不可信 / 待重读**：种子的完整表达式（是否还叠加末字节与数组内容）、19 字节数组的内容与用途、
  以及"循环上界来自 `bytes[len-13]`"这类 trailer 语义。
  → 见「下一步」第 1 项，**必须先做完这件事再谈任何解密**。

**"起点 0..4095 穷举"那条否证原本有个漏洞，这次补掉了**

之前只穷举了起始偏移、没穷举种子，而种子刚被证明是逐文件的 → 结论可被"你种子没试对"推翻。
新发现（已做零假设检验）：`out[i]` 只取 `state>>8` 的 **bit 8..15**，而
`state=(state+c)*205+207` 是仿射、**只向高位进位** → bit 8..15 永远只由 `state` 的低 16 位决定
→ **整条密钥流只依赖种子的低 16 位，有效种子恰好 65536 个**。于是"没试对种子"这个可能性
可以被**穷举封死**，不必再抽样。

`26_www_wrapper.py` 的做法不是扫种子而是**反解**：target 首字节钉死 `state₀` 的 bit8..15，
只剩 256 个候选，逐字节过滤 —— 与对 65536 个有效种子做全量检验完全等价。

**三条对照，其中两条在真跑之前各抓到一个真 bug**

- **低 16 位闭合自检**：2000 组随机 buffer × 每组 8 个"只改种子高 16 位"的变体，输出须逐字节相同 → 0 不一致。
- **反解阳性对照**：400 次随机 (buffer, seed, off) 埋点，反解须命中原 seed。
  **第一版这里就是红的**：过滤循环把上一步的 state 又当 seed append 回去，400/400 全失败。
- **埋针对照**：在真 `scripts64` 里种 5 处 www 加密的 `UnityFS\0`，须 5/5 抓到。
  **第一版 0/5** —— 抓到第二个 bug：我加密时让 state 用**明文**字节推进，而 `www()` 里 `c`
  读的是**密文**字节（`c=b[i]` 在覆写之前）。加密方向必须用写下去的 c 推进。

三条任一不过，脚本 `exit 3` 并**拒绝输出否证结论**。

**实测（`--max-off 4096`，scripts64 与 scripts32 各一轮）**

| 目标前缀 | 约束 | 期望假命中 | 命中 (64 / 32) |
|---|---|---|---|
| `UnityFS\0` | 64 bit | 1.5e-11 | **0 / 0** |
| `\x1blua`（小写） | 32 bit | 0.062 | 1 / 0（off=815，后 36 字节全随机 → 巧合） |
| `\x1bLuaT` | 40 bit | 2.4e-4 | 0 / 0 |
| `local ` | 48 bit | 9.5e-7 | 0 / 0 |
| `--[` | 24 bit | 16 | 12 / 21（**正好落在预测噪声带** → 对照自洽） |

**结论（本轮真正得到的，与本轮一度写下的相比已缩水）**

1. ✅ **`www()` 的作用域边界定了**：输入 = `PathUtil.ReadAllBytes(GetLuaBundle())`，
   输出 = `AssetBundle.LoadFromMemory`。**它是一个把加密 AB 容器还原成 AssetBundle 的解密封。**
   (6) 画的链条成立，本轮没有改判，只是把它钉得更死（全库唯一调用方）。
2. ✅ **`www()` 的输入不是盘面上这份 `scripts64`/`scripts32`**，现在有**两条独立证据**：
   (6) 的 trailer 不合法（末 4 字节 `0xB9A00799` 当长度荒谬），以及本轮的
   **65536 个有效种子 × 偏移 0..4095 反解 `UnityFS` 全 0 命中**（64 位约束，期望假命中 1.5e-11）。
   两文件头 4 字节均为 `52 aa 2a a5`（既非 `1b 4c 4a` 也非 `UnityFS`），与之一致。
   → **"中间还有一层封装"这个堵点没有解除，仍是主堵点**；(6) 给的候选（`LuaConfDataReader`
   的 `Header_32[5]`/`Footer[26]` 封帧，或 BSA 归档条目 ≠ loose 文件）**继续有效**。
3. ❌ 撤回：~~"www 是 Lua 文本解密封、判据不可达、配置分支方向性错误"~~ —— 见本节顶部更正。
   (14) 那 776 项 `sharecfg/<表名>.lua` 与 `www()` 的关系**未被本轮证实也未被否证**，
   因为 `Load` 的产物是 AB 而不是 Lua chunk；`sharecfg/*.lua` 若要经 `require` 进 Lua VM，
   走的应是 `LuaFileUtils`（`Load` 的失败分支里确实调了它，`0x3d9c920`），**那是另一个函数**。

### 下一步（第 6 次收口 —— 顺序不可颠倒，第 1 项是本轮自己欠下的债）

1. **把 `www()` 的 `0x3D9CB48`–`0x3D9CCD5` 逐条读完**（本轮两次错判都出在这段没读完）。
   必须回答三件事，且**每条都要能贴出指令原文**：
   ① 19 字节数组（`Array::New(0x13)` + `InitializeArray`）到底参与什么——它后面紧接的是
   逐字节拷贝循环，说明是**整段搬运**而非取一字节；② 主循环真正的起始/结束边界与上界来源
   （trailer 语义：`0x3D9CB00-0x3D9CB12` 那段读末 4 字节并 `sub` 的动作）；③ 种子除了
   `0x3D9CC33` 的 `mov ebp,0xEB` 之外还叠了什么。
   → 只有 (15) 那三条递推式被完整复核后，第 2 项的搜索空间结论才算成立。
2. **有了确定的种子公式，再回答"www 的输入是哪一段"**：正确做法不是继续在这 39MB 上试偏移，
   而是**顺着 `PathMgr.is32Bit()` → `GetLuaBundle()` → `ReadAllBytes()`** 把
   `File.Exists ? File.ReadAllBytes : BetterStreamingAssets.ReadAllBytes` 这条分支落实：
   设备上不落散文件 → 走 **BSA 归档**，故 www 的输入是 **BSA 归档里 `scripts64` 那一条目的解压结果**。
   要拿的是 **BSA 归档的条目表**（`BetterStreamingAssets` 是知名开源库，头/表结构有公开实现可读），
   而不是猜自定义 trailer。
3. 用 `26_www_wrapper.py` 的反解器（**判据 = `UnityFS`，它是对的**）在真正取到的候选缓冲上验一次；
   命中即整条链闭合。噪声带目标（`--[` 24 位、期望 16）保留，用来持续给仪器自检。
4. 仍**不做**"扫内存猜结构"类尝试（(15) 两次、本轮又一次）。

#### 附：第 5 次收口时的清单（留痕；两项结论**已被本轮推翻**）

1. **从"怎么用"反推**：读 `www()` 里 `Array::New(0x13)` 之后到主循环之前那段
   （约 `0x3D9CB2C`–`0x3D9CC44`），确认 19 字节数组是被逐字节索引当密钥、还是只用来算 LCG 种子。
   → ~~结论：只取 byte[4] 加进种子~~ **作废**：那段没读完，实际紧接的是逐字节拷贝循环。回到待办第 1 项。
2. 顺藤找**真正作用在 `Array.Copy` 目标缓冲上的那段循环**。→ 确认**就是 `www()` 内那个拷贝 + 主循环**，
   且 `www()` 的输出进 `LoadABFromBytes` → AssetBundle。(15) 的"循环作用于输出缓冲"改判成立。
3. 不再做"扫内存猜结构"类尝试——已连续两次产出假信号。



#### 附：第 4 次收口时的清单（留痕；第 1 项已做完，结论见 (10)）

1. **写抽取器**：按 GCstr 结构（长度前缀 + 内容 + NUL）从堆里成对捞出
   `台词串` 与紧邻的 `#起#止` 结构，产出候选 (文本, 起, 止) 三元组表，看能否凑出
   `soundstory2_jp.txt` 那种 `文本#起始#结束` 行格式。
2. 归属：若 1 只能拿到文本+时间而拿不到皮肤 id，则转 (b)——用 `gamecfg/**.lua` 字节码
   或 `www()` 拿到解析器，回原表解。
3. 验收判据不变：与权威基准逐字段一致；**没有基准的台词表**要用"游戏内界面抽验若干条"代替。



#### 附：第 3 次收口时的清单（留痕；已被上面第 4 次更新）

1. **查 `gamecfg` 是不是配置的明文形态**：把 `assets/luabuilds/android/normal/gamecfg/...lua` 的字节码
   blob 切出来反解常量池；若台词以 Lua 表常量存在，直接就能取到，**不必碰 sharecfgdata 容器**。
2. 若 1 不成：用 `16_mem_hunt.py` 在**皮肤详情/台词界面**再抓一次，专挑 `ShareCfg.ship_skin_words`
   附近区域按 GCstr 结构还原整表（已证实明文驻留，这条路现在是有底的）。
3. 仍留着：读完 `www()` 主循环 + 验证封帧假设（离线）。



#### 附：第 2 次收口时的清单（留痕；已被上面第 3 次收口更新）

1. **从内存提取 LuaJIT 字节码**：按 `\x1bLJ` 头切出 blob，解析头部与 BC 常量池，
   找 `sharecfg` / `gamecfg` 相关模块；重点看它的字符串常量里有没有密钥与 `(startPos,size)` 的用法。
2. 若字节码提取受阻，再回到离线路线：读完 `www()` 主循环 + 验证"首 5 / 末 26 字节封帧"假设。
3. 若 1/2 都拿到解析器，**验收仍用唯一判据**：解出的 `ship_skin_template` 与 azdata 基准逐字段一致。



#### 附：第 1 次收口时列的清单（保留留痕；第 4 项今天已做完，结论见 (7)）

1. **验证"外层封帧"假设**：把 `scripts64` 去掉首 5 / 末 26 字节后，末尾 4 字节是否变成合法长度、
   解出来是否 `UnityFS`。若成立 → `www` 的 19 字节 key 一拿到就能直接开 Lua。
2. **把 `www` 的主循环逐条读完**（`0x3D9CCD5` 起），确认变换形态（XOR/加/查表/是否带位置相关项）。
3. **拿 19 字节 key**：要么把 v31 `fieldDefaultValues` 索引法解出来，要么——已知明文攻击：
   UnityFS 头 12 字节是固定串 `00 00 00 07 55 6e 69 74 79 46 53 00`，
   若 `www` 是纯周期 19 XOR，则 `K[0..11] = C[0..11] ^ 那 12 字节`，**不需要 metadata 就能凑出大半个 key**。
4. ~~进程内存取证（需用户放行）~~ → **已放行并做完（见 (7)）**：没有整表明文，但有 LuaJIT 字节码。



### 追加排除的假设汇总（2026-09-24，供下个会话直接当"已试清单"）

| 假设 | 判据 | 结果 |
|---|---|---|
| 跨 32 表共密钥流（两时间垫） | 实测两两相等率 1.84% vs "仅共享字节分布"预测 **1.904%**；逐列共识均值 0.102 | **不成立**，正信号是分布巧合 |
| 众数≈密钥流（明文列众数为 0x00） | 用列众数当 K 做 xor/sub/add 解密：熵不降、IC 未回到文本量级、中文 0 命中 | 不成立 |
| 整体流加密 / 整体压缩 | 单文件内 16B 块重复 500+ 次（iid 期望 1e-6）；LE32 头记录可解 | **不成立**，改为"明文索引 + 变换后的文本载荷" |
| `XorShift64` 是密钥流发生器 | dump.cs 上下文 = xxHash3(Burst) | 否证 |
| `ctXor` 是 XOR 辅助函数 | `ClipperLib.ClipType` 枚举 | 否证 |
| `Decrypt`/`SetDecryptionKey` 属配置解密 | 都在 `CriWare_*Wrap` 里（音频） | 否证 |
| 句柄 `&0x7fffffff` = fieldDefaultValues 条目号 | 解出等差序列 | 否证，正确解读是 **FIELD token**（`0x80xxxxxx`） |
| adb 可捞到盘上解密缓存 | 进程 fd 表直接指向 `sharecfgdata/`；全盘 find 无缓存目录 | 否证，**唯一剩下的明文位置是进程内存** |
| **盘面 `scripts64`/`scripts32` 整文件就是 `www()` 的输入** | ①(6) 末 4 字节 `0xB9A00799` 不是合法长度 trailer；②本轮 65536 个有效种子 × 偏移 0..4095 反解 `UnityFS` **0 命中**（64 位约束，期望假命中 1.5e-11）；③两文件头 4 字节均 `52 aa 2a a5` | **两条独立证据否证**。堵点仍是"输入侧那层封装"（(6) 指向 BSA 归档条目 / `Header_32[5]`+`Footer[26]`），未解除 |
| ~~`www()` 是 Lua 文本解密封、"输出须含 UnityFS"这条判据不可达~~ | **我 09-24 本轮写下的错误结论**：把 `0x3D9C8F6` 处的 `mov rsi,r15` 当成 `call`，凭空造出 `luaL_loadbuffer`。真 callee 在 `0x3D9C8FC` = `LoadABFromBytes` → AssetBundle | **作废**。`UnityFS` 是**正确且可达**的判据；详见 (16) 顶部更正块 |



## 当前状态（2026-09-23 收口）：**未破解，零明文字节到手**

> ⚠️ 本节多条判断已被上面「2026-09-24 实测更新」修正（`XorShift64`/`ctXor` 是假线索、"Footer 是文件封尾"、"共密钥流"、"32/64 指记录位宽"）；保留原文只为留痕。
> 仍然成立的两条：**盘上一个明文字节都没读到**；以及**已知明文自证判据**（下表）。

**战略结论修正（09-24）**：昨天写的是「C# 侧零解密、真正的解析在 Lua 侧 → 主战场是解 scripts32/scripts64」。
机器码证实了前半句，但后半句的优先级要改：既然 sharecfgdata **本身不是整体加密**（明文索引 + 变换后的文本载荷），
那"必须先拿到 Lua 源码"不如"先定位载荷区的变换边界与步长"来得便宜——**内存取证**一次能同时拿到
解出的配置**和** Lua 解析器源码，是当前的主路径。


已完成的是**问题定位**，不是破解。**一个明文字节都没读到**，`ship_skin_words` 仍打不开。

⚠️ 别把两件事混了：**语音「音频」已拿到 253 皮肤 / 5914 个 ogg，但那不是靠逆向配置表** —— 是靠
「ACB 里的 cue 名与 model3 动作组名逐字同名」这个巧合直接对上的（见 `docs/WORKFLOWS.md` WF-17）。
**台词文本**（字幕要的东西）才是本项目的目标，仍然没有。

**战略结论：C# 侧只是按 `(startPos,size)` 取切片的搬运工，零解密零解码，真正的解析在 Lua 侧**
→ 下一步主战场是解 `scripts32`/`scripts64`（熵 8.000 的加密 Lua 包），**本项目尚未开始这一步**。

### 2026-09-23 追加的实测事实

- `.cctor`（RVA `0x3C1577A`）反汇编出**三个常量的长度**：`Header_32 = byte[5]`、`Header_64 = byte[5]`、
  **`Footer = byte[26]`**（名字里的 32/64 指**记录位宽**，不是字节数）。
- **32 张表（不是 34）尾 8 字节完全一致** = `8e 99 07 8f 99 07 a0 b9`；但**尾 26 字节 32 种各不相同**
  → `Footer`(26B) **不是** sharecfgdata 的尾，更可能是 `confDataCacheFolderPath` 那套运行时缓存的封帧。
- 头是**可变长 + LEB128 变长整数**：body 起点有 8 / 9 / 10 / 11 四种（`gametip`、`weapon_name` 短 1 字节，
  `world_chapter` 10、`activity_coloring` 11）；`byte[4]` 恒 0、`byte[2]==byte[3]` 恒成立（两例外为 0）。
- **body 是均匀的 4 字节记录流**，32 张表**最长公共前缀 = 16 字节**（`4e ff 00 00 51 ff 01 01 51 ff 02 02 51 ff 03 03`），
  之后立即分化但形态不变：`[tag 0x4c..0x57][缓慢递减字节 ff→fe→fd…][严格递增记录号][另一累计量]`。
- **记录变长**：`(size-头-尾)/行数 = 1076.28 / 507.39 / 1420.23`，全非整数。
- 已知行数 2863/4119/3968（±1）在头 32B + body 前 4KB 按 8 种编码全未命中——**但本地是 9.7.385、
  azdata 基准是 381，行数本就可能不同，此条不算硬否证**。
- `fieldDefaultValues` 记录布局自检：候选步长 8/12/16/24 中，**步长 12 完全自洽**
  （fieldIndex 与 dataIndex 均在范围且严格单调，综合 4.000；8/16 单调性仅 ~0.49）。

### 追加排除的假设（2026-09-23）

| 假设 | 判据 | 结果 |
|---|---|---|
| 那 7 个 32-hex 串是 AES-128 密钥 | ×4 头部偏移 ×4 模式（ECB/CBC-零IV/CBC-key当IV/CTR）= 112 组合 | 最高可打印 **0.385 ≈ 随机 0.37**，全噪声。更可能是 `CryptoCheckValue` 的 MD5 校验值 |
| metadata 里搜得到 Header/Footer 常量 | 在 metadata、libil2cpp.so、**全部 80 个 DummyDll** 里搜连续字节 | **全部未命中** → 常量是 `.cctor` 内联立即数，搜 blob 这条路无效 |
| `(句柄 & 0x7fffffff) → fieldDefaultValues 条目号` | 按此取出的是 `34 36 38 3a…`、`00 02 04 06…` 等差序列（typeIndex 恒 30420） | **不是 S-box，是这个句柄解码法错了**；索引映射待定 |
| `scripts32`/`scripts64` 同密钥流（两时间垫） | 逐字节 XOR：零率 **0.391% = 1/256**、最长零段仅 32 字节 | 无从反推密钥流；且即使拿到 56 字节已知明文，对 AES-CTR/ChaCha 也只能换到对应位置 |

## 推进路线

> ⚠️ 本节是 09-23 写的，第 1–3 步**已完成**（metadata 已解析、version=31 判定为正常、Il2CppDumper 已跑通并可用 `08_disasm_method.py` 逐方法反汇编）。当前有效的路线见上面「下一步（按期望收益排序）」。

1. **解析 metadata 头** → 取 stringLiteral 堆，dump 游戏自身的字符串字面量（硬编码密钥最可能在这里）。
2. 判定 version=31 的性质：偏移量自洽 → 是新 Unity，走标准 Il2CppDumper 分支；不自洽 → 被改过头，得手写解析器。
3. 定位 `ReadCfgFile` / `XorShift64` / `ctXor` 的方法体：需要 Il2CppDumper（GitHub 被墙，走 `cn-blocked-resource-mirror-fetch`）产出方法 RVA，再用 objdump/Ghidra 读 `.text`。
4. 逆算法 + 密钥 → **用 `ship_skin_template` 自证**（见判据）。
5. 解 `ship_skin_words` 取台词 → 交画廊字幕用。

## 落盘约定

- 探针/工具脚本放本目录（编号前缀 `01_`、`02_`…），**不放 `.diag/`**——本项目的东西必须入库。
- 大件中间产物（解密明文、dumper 输出）放 `.diag/sharecfg_re/`（gitignore），README 里只留结论与判据。
- **方法账**：(16) 那条「用调用方判作用域 + 把否证做成穷举级 + 三条对照」的流程已固化进
  `docs/WORKFLOWS.md` **WF-18**；本项目只留数据与结论，不重复抄流程。
