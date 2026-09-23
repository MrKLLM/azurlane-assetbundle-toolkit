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
| `.diag/azdata_ship_{skin_template,data_statistics,data_template}.json` | 9.2 MB | **已知明文**（社区 dump）——自证用的黄金基准 |
| `files/il2cpp/unity.ver` | 36 B | `447c407d-09a0-4c15-987b-4a8d452240d4`，metadata ↔ so 的配对 id |

## 判据（唯一验收标准）

**`ship_skin_template` 解密结果必须与 `.diag/azdata_ship_skin_template.json` 逐字段一致。**

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
| **`XorShift64`** | 自研 PRNG，**最可能是密钥流发生器** |
| **`ctXor`** | XOR 辅助函数 |
| `Decrypt128` / `DecryptData` / `DecryptValue` / `DecryptKeyExchange` | 解密函数族 |
| **`ReadCfgFile`** | 配置文件读取入口 —— 逆算法从这里跟进 |
| `CriWareDecrypter` / `DecryptAcb` | CRIWARE 音频解密（ACB 那条线的对照，**不是** sharecfgdata） |
| `AesCryptoServiceProvider` / `RijndaelManaged` / `Rfc2898DeriveBytes` / `MD5CryptoServiceProvider` | 大概率是 .NET 自带 System.Security.Cryptography 常驻链接，**不能当使用证据** |
| `CryptoCheckValue` / `CryptoHeaderSize` | 待定，可能是保护层 |

## 推进路线

1. **解析 metadata 头** → 取 stringLiteral 堆，dump 游戏自身的字符串字面量（硬编码密钥最可能在这里）。
2. 判定 version=31 的性质：偏移量自洽 → 是新 Unity，走标准 Il2CppDumper 分支；不自洽 → 被改过头，得手写解析器。
3. 定位 `ReadCfgFile` / `XorShift64` / `ctXor` 的方法体：需要 Il2CppDumper（GitHub 被墙，走 `cn-blocked-resource-mirror-fetch`）产出方法 RVA，再用 objdump/Ghidra 读 `.text`。
4. 逆算法 + 密钥 → **用 `ship_skin_template` 自证**（见判据）。
5. 解 `ship_skin_words` 取台词 → 交画廊字幕用。

## 落盘约定

- 探针/工具脚本放本目录（编号前缀 `01_`、`02_`…），**不放 `.diag/`**——本项目的东西必须入库。
- 大件中间产物（解密明文、dumper 输出）放 `.diag/sharecfg_re/`（gitignore），README 里只留结论与判据。
