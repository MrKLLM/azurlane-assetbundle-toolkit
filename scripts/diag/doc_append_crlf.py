# -*- coding: utf-8 -*-
"""往 CRLF 行尾的长文档**追加**一段，且绝不改动已有任何一行。

为什么单独一个脚本：本仓库的 `docs/*.md` 与 `PROJECT_STATUS.md` 是 CRLF，
而 python 里用 `open(...).write(s + text)` 会把新段落写成 LF ⇒
`git diff` 上看不出问题，但下次任何"整文件重写"的补丁脚本都会因为
`assert old in s` 匹配不上而静默失败（本轮真实踩过：heredoc 写出的补丁 assert 全红）。
本脚本读入时 `newline=''`（不翻译行尾），按文件自身的行尾写回。

    py -3 scripts/diag/doc_append_crlf.py docs/WORKFLOWS.md 段落.txt
    py -3 scripts/diag/doc_append_crlf.py --check docs/WORKFLOWS.md   # 只看行尾与行数

追加完必须自己核对：`git diff --numstat <文件>` 应当是「新增 N / 删除 0」。
"""
import argparse
import io
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("block", nargs="?", help="要追加的文本文件（- 表示读 stdin）")
    ap.add_argument("--check", action="store_true", help="只报告行尾与行数，不写盘")
    a = ap.parse_args()

    s = io.open(a.file, encoding="utf-8", newline="").read()
    crlf = "\r\n" in s
    nl = "\r\n" if crlf else "\n"
    lines = s.count("\n") + 1
    if a.check or not a.block:
        print("%s: %d 行，行尾=%s，混合行尾=%s"
              % (a.file, lines, "CRLF" if crlf else "LF",
                 "\n" in s.replace("\r\n", "") and crlf))
        return 0
    text = sys.stdin.read() if a.block == "-" else io.open(a.block, encoding="utf-8").read()
    text = text.rstrip("\r\n")
    with io.open(a.file, "w", encoding="utf-8", newline="") as f:
        f.write(s + nl + nl.join(text.split("\n")) + nl)
    print("追加 %d 行到 %s（行尾=%s）；请核对 git diff --numstat 应为「新增 %d / 删除 0」"
          % (len(text.split("\n")), a.file, "CRLF" if crlf else "LF", len(text.split("\n")) + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
