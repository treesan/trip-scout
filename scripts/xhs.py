#!/usr/bin/env python3
"""
trip-scout 小红书口碑验证+路线搜索入口（纯 API 版本）

基于 Spider_XHS (https://github.com/cv-cat/Spider_XHS) 的纯 HTTP API 方案，
直接调用小红书 API，无需浏览器自动化。优势：
- 无浏览器自动化 → 无 CDP 痕迹 → 被风控检测风险低
- 逆向 XHS 签名算法 (x-s/x-t/x-s-common) → 直接 API 调用
- 速度快（无需渲染页面）

用法:
    python scripts/xhs.py check-login                    # 检查cookie有效性
    python scripts/xhs.py qrcode                          # QR码登录（纯API，终端显示）
    python scripts/xhs.py set-cookie --cookie "a1=...;web_session=..."  # 手动设置cookie
    python scripts/xhs.py search "那拉提英迪格 避雷" --limit 10
    python scripts/xhs.py feed <note_url_or_id>           # 笔记详情

输出: JSON 到 stdout, 错误到 stderr。
"""
import argparse
import json
import os
import sys
import time

# Windows GBK 终端兼容
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# vendor 路径: 项目根/vendor/xhs_api 是 Spider_XHS 核心，
# 项目根/vendor/xhs_api 下的 apis/ 和 xhs_utils/ 作为顶级包
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_vendor_dir = os.path.join(_project_root, "vendor", "xhs_api")
sys.path.insert(0, _vendor_dir)

# NODE_PATH: PyExecJS 调用 node 执行签名 JS 时需要找到 crypto-js/jsdom
_node_modules = os.path.join(_vendor_dir, "node_modules")
if os.path.isdir(_node_modules) and "NODE_PATH" not in os.environ:
    os.environ["NODE_PATH"] = _node_modules

# CWD: xhs_xray.js 内部 require('./xhs_xray_pack1.js') 等使用相对路径，
# PyExecJS 执行 node 时的 CWD 必须是 vendor/xhs_api/ 才能解析这些 require
# 保存原始 CWD，在需要时切换（只在首次 import vendor 模块前切换）
_original_cwd = os.getcwd()
os.chdir(_vendor_dir)

# Cookie 持久化路径
DEFAULT_COOKIE_PATH = os.path.expanduser("~/.xiaohongshu/cookies.json")


def _load_cookie_str():
    """从文件加载 cookie 字符串"""
    if not os.path.exists(DEFAULT_COOKIE_PATH):
        return None
    try:
        with open(DEFAULT_COOKIE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 兼容两种格式：字符串或 {"cookie_str": "..."}
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            return data.get("cookie_str") or data.get("cookies_str")
        return None
    except Exception:
        return None


def _save_cookie_str(cookie_str):
    """保存 cookie 字符串到文件"""
    os.makedirs(os.path.dirname(DEFAULT_COOKIE_PATH), exist_ok=True)
    with open(DEFAULT_COOKIE_PATH, 'w', encoding='utf-8') as f:
        json.dump({"cookie_str": cookie_str}, f, ensure_ascii=False, indent=2)


def out(data):
    print(json.dumps(data, ensure_ascii=False))


def cmd_check_login(args):
    """检查 cookie 是否有效"""
    cookie_str = _load_cookie_str()
    if not cookie_str:
        out({"is_logged_in": False, "username": None, "error": "未设置cookie，请先运行 qrcode 或 set-cookie"})
        return 1

    from apis.xhs_pc_apis import XHS_Apis
    api = XHS_Apis()
    success, msg, res_json = api.get_user_self_info2(cookie_str)

    if success and res_json:
        user_info = res_json.get("data", {})
        nickname = user_info.get("nickname", "未知")
        red_id = user_info.get("red_id", "未知")
        out({"is_logged_in": True, "username": nickname, "red_id": red_id})
        return 0
    else:
        out({"is_logged_in": False, "username": None, "error": msg})
        return 1


def cmd_qrcode(args):
    """QR码登录（纯API，无需浏览器）"""
    from apis.xhs_pc_login_apis import XHSLoginApi

    login_api = XHSLoginApi()
    cookies_str = login_api.qrcode_login(show_in_terminal=not args.no_terminal)

    if cookies_str:
        _save_cookie_str(cookies_str)
        out({"success": True, "message": "登录成功，cookie已保存", "cookie_length": len(cookies_str)})
        return 0
    else:
        out({"success": False, "message": "登录失败"})
        return 1


def cmd_set_cookie(args):
    """手动设置 cookie 字符串（从浏览器 DevTools 复制）"""
    if not args.cookie:
        print("错误: 请提供 cookie 字符串", file=sys.stderr)
        return 1

    cookie_str = args.cookie.strip()
    if not cookie_str:
        print("错误: cookie 字符串为空", file=sys.stderr)
        return 1

    # 验证 cookie 包含必要字段
    if 'a1=' not in cookie_str:
        print("警告: cookie 中未找到 a1 字段，可能无效", file=sys.stderr)

    _save_cookie_str(cookie_str)
    out({"success": True, "message": "cookie已保存", "cookie_length": len(cookie_str)})
    return 0


def cmd_search(args):
    """搜索笔记"""
    cookie_str = _load_cookie_str()
    if not cookie_str:
        out({"error": "未设置cookie，请先运行 qrcode 或 set-cookie"})
        return 1

    from apis.xhs_pc_apis import XHS_Apis
    api = XHS_Apis()

    # 映射排序方式
    sort_map = {"综合": 0, "最新": 1, "最多点赞": 2, "最多评论": 3, "最多收藏": 4}
    sort_type = sort_map.get(args.sort_by, 0)

    # 映射笔记类型
    type_map = {"不限": 0, "视频笔记": 1, "普通笔记": 2}
    note_type = type_map.get(args.note_type, 0)

    # 映射时间范围
    time_map = {"不限": 0, "一天内": 1, "一周内": 2, "半年内": 3}
    note_time = time_map.get(args.publish_time, 0)

    success, msg, res_json = api.search_some_note(
        query=args.keyword,
        require_num=args.limit,
        cookies_str=cookie_str,
        sort_type_choice=sort_type,
        note_type=note_type,
        note_time=note_time,
    )

    if success and res_json:
        results = []
        for item in res_json:
            note_card = item.get("note_card", item)
            results.append({
                "id": item.get("id", note_card.get("note_id", "")),
                "title": note_card.get("display_title", ""),
                "type": note_card.get("type", ""),
                "liked_count": note_card.get("interact_info", {}).get("liked_count", "0"),
                "user": note_card.get("user", {}).get("nickname", ""),
                "xsec_token": item.get("xsec_token", ""),
                "xsec_source": item.get("xsec_source", "pc_search"),
            })
        out({"count": len(results), "results": results})
        return 0
    else:
        out({"error": msg, "count": 0, "results": []})
        return 1


def cmd_feed(args):
    """获取笔记详情"""
    cookie_str = _load_cookie_str()
    if not cookie_str:
        out({"error": "未设置cookie，请先运行 qrcode 或 set-cookie"})
        return 1

    from apis.xhs_pc_apis import XHS_Apis
    api = XHS_Apis()

    # 构造 URL（如果输入的是 note_id 而非完整 URL）
    # 需要 xsec_token 才能获取详情，支持两种方式：
    # 1. 直接传完整 URL（含 xsec_token）：从搜索结果复制
    # 2. 传 note_id + --xsec-token 参数
    note_id = args.note_id
    xsec_token = args.xsec_token or ""
    xsec_source = args.xsec_source or "pc_search"

    if note_id.startswith("http"):
        url = note_id
    else:
        url = f"https://www.xiaohongshu.com/explore/{note_id}"
        if xsec_token:
            url += f"?xsec_token={xsec_token}&xsec_source={xsec_source}"

    success, msg, res_json = api.get_note_info(url, cookie_str)

    if success and res_json:
        data = res_json.get("data", {})
        # 提取笔记详情
        note_data = data.get("items", [{}])[0].get("note_card", data)

        result = {
            "id": note_data.get("note_id", ""),
            "title": note_data.get("title", ""),
            "desc": note_data.get("desc", ""),
            "type": note_data.get("type", ""),
            "user": {
                "nickname": note_data.get("user", {}).get("nickname", ""),
                "user_id": note_data.get("user", {}).get("user_id", ""),
            },
            "interact_info": note_data.get("interact_info", {}),
            "image_list": [
                {"url": img.get("url_default", img.get("url", "")), "width": img.get("width", 0), "height": img.get("height", 0)}
                for img in note_data.get("image_list", [])
            ],
            "tag_list": note_data.get("tag_list", []),
            "time": note_data.get("time", 0),
            "last_update_time": note_data.get("last_update_time", 0),
        }

        # 可选：加载评论
        if args.load_comments:
            try:
                c_success, c_msg, c_data = api.get_note_all_out_comment(
                    note_data.get("note_id", ""),
                    "",  # xsec_token 需要从搜索结果获取
                    cookie_str
                )
                if c_success:
                    result["comments"] = c_data[:args.max_comments]
            except Exception:
                pass

        out(result)
        return 0
    else:
        out({"error": msg})
        return 1


def build_parser():
    p = argparse.ArgumentParser(
        description="trip-scout 小红书口碑验证+路线搜索（纯API版本）",
        epilog="注意: 本方案使用直接HTTP API调用，无需浏览器，降低被风控检测的风险"
    )
    p.add_argument("--cookie-file", help=f"cookie文件路径, 默认 {DEFAULT_COOKIE_PATH}")
    sub = p.add_subparsers(dest="command", required=True)

    # check-login
    sub.add_parser("check-login", help="检查cookie是否有效").set_defaults(func=cmd_check_login)

    # qrcode
    qr = sub.add_parser("qrcode", help="QR码登录（纯API，终端显示二维码）")
    qr.add_argument("--no-terminal", action="store_true", help="不显示终端二维码，改为弹出图片窗口")
    qr.set_defaults(func=cmd_qrcode)

    # set-cookie
    sc = sub.add_parser("set-cookie", help="手动设置cookie（从浏览器DevTools复制）")
    sc.add_argument("--cookie", required=True, help="cookie字符串，如 'a1=xxx; web_session=xxx'")
    sc.set_defaults(func=cmd_set_cookie)

    # search
    s = sub.add_parser("search", help="搜索笔记")
    s.add_argument("keyword", help="搜索关键词")
    s.add_argument("--sort-by", default="综合", choices=["综合", "最新", "最多点赞", "最多评论", "最多收藏"])
    s.add_argument("--note-type", default="不限", choices=["不限", "视频笔记", "普通笔记"])
    s.add_argument("--publish-time", default="不限", choices=["不限", "一天内", "一周内", "半年内"])
    s.add_argument("--limit", type=int, default=10, help="返回结果数量")
    s.set_defaults(func=cmd_search)

    # feed
    f = sub.add_parser("feed", help="获取笔记详情")
    f.add_argument("note_id", help="笔记ID或完整URL（URL需含xsec_token，从search结果获取）")
    f.add_argument("--xsec-token", help="xsec_token（从search结果获取，不带则详情可能为空）")
    f.add_argument("--xsec-source", default="pc_search", help="xsec_source（默认pc_search）")
    f.add_argument("--load-comments", action="store_true", help="加载评论")
    f.add_argument("--max-comments", type=int, default=20, help="最大评论数")
    f.set_defaults(func=cmd_feed)

    return p


def main():
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except ImportError as e:
        print(json.dumps({
            "error": f"依赖缺失: {e}",
            "hint": "请安装依赖: pip install PyExecJS loguru && cd vendor/xhs_api && npm install"
        }, ensure_ascii=False), file=sys.stderr)
        return 1
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
