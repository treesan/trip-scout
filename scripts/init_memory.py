#!/usr/bin/env python3
"""
trip-scout 运行时记忆初始化

首次运行时调用, 确保 ~/.trip-scout/ 目录及模板文件存在。
已存在的文件不覆盖(保留用户数据)。

用法: python scripts/init_memory.py
"""
import os
import shutil
import sys

RUNTIME_DIR = os.path.expanduser("~/.trip-scout")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
FILES = ["MEMORY.md", "blacklist.md"]


def main():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    created = []
    for fname in FILES:
        dst = os.path.join(RUNTIME_DIR, fname)
        if os.path.exists(dst):
            continue
        src = os.path.join(TEMPLATE_DIR, fname)
        if not os.path.exists(src):
            print(f"warn: 模板缺失 {src}", file=sys.stderr)
            continue
        shutil.copy(src, dst)
        created.append(fname)

    if created:
        print(f"已初始化运行时记忆: {', '.join(created)} @ {RUNTIME_DIR}")
        print("首次使用请编辑 ~/.trip-scout/MEMORY.md 填入你的会员权益和偏好。")
    else:
        print(f"运行时记忆已就绪: {RUNTIME_DIR}(MEMORY.md + blacklist.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
