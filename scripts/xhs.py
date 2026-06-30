#!/usr/bin/env python3
"""
trip-scout 小红书口碑验证入口

封装 vendored xiaohongshu-skill 的核心命令(check-login/qrcode/search/feed),
供 hotel-search 流程的"小红书交叉验证"步骤调用。

用法:
    python scripts/xhs.py check-login
    python scripts/xhs.py qrcode                 # 弹窗扫码登录
    python scripts/xhs.py search "那拉提英迪格 避雷" --limit 10
    python scripts/xhs.py feed <feed_id> <xsec_token>

输出: JSON 到 stdout, 错误到 stderr。
"""
import argparse
import json
import sys

# Windows GBK 终端兼容
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# vendored 模块路径: 项目根/vendor
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vendor"))

from xiaohongshu import login, search, feed
from xiaohongshu.client import DEFAULT_COOKIE_PATH


def out(data):
    print(json.dumps(data, ensure_ascii=False))


def cmd_check_login(args):
    ok, username = login.check_login(cookie_path=args.cookie or DEFAULT_COOKIE_PATH)
    out({"is_logged_in": ok, "username": username})
    return 0


def cmd_qrcode(args):
    # headless=False 弹浏览器窗口扫码; True 存二维码到文件
    result = login.login(
        headless=not args.show,
        cookie_path=args.cookie or DEFAULT_COOKIE_PATH,
    )
    out(result)
    return 0


def cmd_search(args):
    results = search.search(
        keyword=args.keyword,
        sort_by=args.sort_by,
        note_type=args.note_type,
        publish_time=args.publish_time,
        search_scope=args.search_scope,
        location=args.location,
        limit=args.limit,
        headless=not args.show,
        cookie_path=args.cookie or DEFAULT_COOKIE_PATH,
    )
    out({"count": len(results), "results": results})
    return 0


def cmd_feed(args):
    detail = feed.feed_detail(
        feed_id=args.feed_id,
        xsec_token=args.xsec_token or "",
        load_comments=args.load_comments,
        max_comments=args.max_comments,
        headless=not args.show,
        cookie_path=args.cookie or DEFAULT_COOKIE_PATH,
    )
    out(detail)
    return 0 if detail else 1


def build_parser():
    p = argparse.ArgumentParser(description="trip-scout 小红书口碑验证")
    p.add_argument("--cookie", help="cookie 文件路径, 默认 ~/.xiaohongshu/cookies.json")
    p.add_argument("--show", action="store_true", help="显示浏览器窗口(默认无头)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("check-login", help="检查登录状态").set_defaults(func=cmd_check_login)

    qr = sub.add_parser("qrcode", help="扫码登录")
    qr.set_defaults(func=cmd_qrcode)

    s = sub.add_parser("search", help="搜索笔记")
    s.add_argument("keyword")
    s.add_argument("--sort-by", default="综合")
    s.add_argument("--note-type", default="不限")
    s.add_argument("--publish-time", default="不限")
    s.add_argument("--search-scope", default="不限")
    s.add_argument("--location", default="不限")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(func=cmd_search)

    f = sub.add_parser("feed", help="笔记详情")
    f.add_argument("feed_id")
    f.add_argument("xsec_token", nargs="?", default="")
    f.add_argument("--load-comments", action="store_true")
    f.add_argument("--max-comments", type=int, default=20)
    f.set_defaults(func=cmd_feed)

    return p


def main():
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
