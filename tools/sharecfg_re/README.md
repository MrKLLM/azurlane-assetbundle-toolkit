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

### 下一步（按期望收益排序，2026-09-24 第 2 次收口）

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
