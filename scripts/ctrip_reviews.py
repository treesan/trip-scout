"""
携程酒店差评抓取 - Playwright + API 双轨模式

封装 vendor/ctrip/ 模块，供 trip-scout 差评分析流程调用。

用法:
    # 扫码登录（首次使用）
    python scripts/ctrip_reviews.py login
    python scripts/ctrip_reviews.py login --show       # 弹浏览器窗口扫码

    # 检查登录状态
    python scripts/ctrip_reviews.py check-login

    # 搜索酒店（获取hotelId）—— 问道API说"无该店"时的兜底方案
    python scripts/ctrip_reviews.py search "乌鲁木齐福朋喜来登酒店"
    python scripts/ctrip_reviews.py search "奎屯亚朵" --show
    python scripts/ctrip_reviews.py search "赛里木湖 酒店" --limit 5

    # 抓取差评分析
    python scripts/ctrip_reviews.py <hotelId> [--months 12] [--pages 20]
    python scripts/ctrip_reviews.py <hotelId> --no-api  # 强制浏览器模式
    python scripts/ctrip_reviews.py <hotelId> --show    # 显示浏览器窗口（调试用）

    # 登出
    python scripts/ctrip_reviews.py logout

输出: JSON 到 stdout, 含分类统计+近期趋势+踩雷风险。
hotelId 从携程酒店详情页 URL 获取(如 hotels.ctrip.com/hotels/detail?hotelid=XXXX)。
也可通过 search 子命令搜索获取。
"""
import argparse
import json
import sys
import os

# Windows GBK 终端兼容
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# vendored 模块路径: 项目根/vendor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vendor"))

from ctrip.login import check_login, login, logout
from ctrip.reviews import fetch_and_analyze, search_hotel_id


def out(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _search_hotels(query, headless=True, limit=10):
    """搜索携程酒店，返回 hotelId 列表。

    两种模式：
    1. 精确搜索（酒店名）：调用 search_hotel_id，返回单个 hotelId
    2. 模糊搜索（目的地+关键词）：浏览器模式搜索携程，返回多个结果
    """
    # 先尝试精确搜索（酒店名 → 单个hotelId）
    try:
        hotel_id = search_hotel_id(query, client=None)
        if hotel_id:
            return {
                "query": query,
                "hotelId": hotel_id,
                "hotelName": query,
                "matchType": "exact",
                "note": "精确匹配，可直接用于差评抓取",
            }
    except Exception:
        pass  # 精确搜索失败，降级到模糊搜索

    # 模糊搜索：打开携程酒店搜索页，提取搜索结果列表
    from ctrip.client import CtripClient
    import time as _time

    client = CtripClient(headless=headless)
    client.start()
    try:
        page = client.page
        page.goto('https://hotels.ctrip.com/', wait_until='networkidle', timeout=20000)
        _time.sleep(3)

        # 在搜索框输入关键词
        search_input = page.locator('#_allSearchKeyword')
        search_input.click()
        _time.sleep(0.5)
        search_input.fill(query)
        _time.sleep(3)

        # 从下拉列表提取多个搜索结果
        results = page.evaluate("""(limit) => {
            const items = document.querySelectorAll('.search_list_hotel');
            const out = [];
            for (let i = 0; i < Math.min(items.length, limit); i++) {
                const item = items[i];
                const url = item.getAttribute('url') || '';
                const word = item.getAttribute('word') || '';
                const hotelIdMatch = url.match(/hotel\\/(\\d+)/) || url.match(/hotelId=(\\d+)/);
                if (hotelIdMatch) {
                    out.push({
                        hotelId: hotelIdMatch[1],
                        hotelName: word || url,
                        url: url
                    });
                }
            }
            return out;
        }""", limit)

        return {
            "query": query,
            "matchType": "fuzzy",
            "results": results,
            "count": len(results) if results else 0,
            "note": "模糊搜索结果，选择目标酒店后用 hotelId 抓取差评" if results else "未找到匹配酒店，尝试更精确的关键词",
        }
    except Exception as e:
        return {"query": query, "error": str(e), "matchType": "fuzzy"}
    finally:
        client.close()


def main():
    # 手动路由: 第一个参数如果是已知子命令则路由，否则当作 hotelId
    SUBCOMMANDS = {"login", "check-login", "logout", "search"}

    args = sys.argv[1:]
    if not args:
        _print_help()
        return 1

    first = args[0]

    # 子命令路由
    if first == "login":
        p = argparse.ArgumentParser(prog="ctrip_reviews.py login", description="扫码登录携程")
        p.add_argument("--show", action="store_true", help="弹浏览器窗口扫码(推荐首次使用)")
        p.add_argument("--timeout", type=int, default=120, help="扫码超时秒数(默认120)")
        ns = p.parse_args(args[1:])
        result = login(headless=not ns.show, timeout=ns.timeout)
        out(result)
        return 0 if result.get("status") == "logged_in" else 1

    if first == "check-login":
        ok, username = check_login()
        out({"is_logged_in": ok, "username": username})
        return 0 if ok else 1

    if first == "logout":
        result = logout()
        out(result)
        return 0

    if first == "search":
        p = argparse.ArgumentParser(prog="ctrip_reviews.py search", description="搜索携程酒店获取hotelId")
        p.add_argument("query", help="酒店名称或搜索关键词(如'乌鲁木齐福朋喜来登酒店'或'赛里木湖 酒店')")
        p.add_argument("--show", action="store_true", help="显示浏览器窗口")
        p.add_argument("--limit", type=int, default=10, help="最多返回结果数(默认10)")
        ns = p.parse_args(args[1:])

        result = _search_hotels(query=ns.query, headless=not ns.show, limit=ns.limit)
        out(result)
        return 0 if result.get("hotelId") or result.get("results") else 1

    if first in ("--help", "-h"):
        _print_help()
        return 0

    # 默认: 差评分析 — first 是 hotelId
    p = argparse.ArgumentParser(
        description="携程酒店差评抓取分析 (Playwright + API 双轨)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/ctrip_reviews.py login             # 扫码登录携程
  python scripts/ctrip_reviews.py login --show      # 弹浏览器窗口扫码
  python scripts/ctrip_reviews.py check-login       # 检查登录状态
  python scripts/ctrip_reviews.py search "乌鲁木齐福朋喜来登酒店"  # 搜索酒店获取hotelId
  python scripts/ctrip_reviews.py search "赛里木湖 酒店" --limit 5  # 模糊搜索
  python scripts/ctrip_reviews.py 17509632          # 抓取酒店差评(默认API优先)
  python scripts/ctrip_reviews.py 17509632 --pages 30  # 抓取更多页
  python scripts/ctrip_reviews.py 17509632 --no-api # 强制浏览器模式
  python scripts/ctrip_reviews.py 17509632 --show   # 显示浏览器窗口(调试)
  python scripts/ctrip_reviews.py logout            # 清除登录状态
        """,
    )
    p.add_argument("hotelId", help="携程酒店ID")
    p.add_argument("--months", type=int, default=12, help="分析近N个月(默认12)")
    p.add_argument("--pages", type=int, default=20, help="最多翻页数(默认20)")
    p.add_argument("--no-api", action="store_true", help="强制浏览器模式，不尝试API")
    p.add_argument("--show", action="store_true", help="显示浏览器窗口(调试用)")
    p.add_argument("--all", action="store_true", help="抓取全部评论(不仅差评)")

    ns = p.parse_args(args)

    result = fetch_and_analyze(
        hotel_id=ns.hotelId,
        months=ns.months,
        max_pages=ns.pages,
        negative_only=not ns.all,
        headless=not ns.show,
        prefer_api=not ns.no_api,
    )
    out(result)

    # 如果抓取失败，返回非零退出码
    if "error" in result:
        return 1
    return 0


def _print_help():
    print("""携程酒店差评抓取分析 (Playwright + API 双轨)

用法:
  python scripts/ctrip_reviews.py login               # 扫码登录携程
  python scripts/ctrip_reviews.py login --show        # 弹浏览器窗口扫码
  python scripts/ctrip_reviews.py check-login         # 检查登录状态
  python scripts/ctrip_reviews.py search "酒店名"      # 搜索酒店获取hotelId
  python scripts/ctrip_reviews.py search "城市 关键词" --limit 5  # 模糊搜索
  python scripts/ctrip_reviews.py <hotelId>           # 抓取酒店差评(默认API优先)
  python scripts/ctrip_reviews.py <hotelId> --pages 30
  python scripts/ctrip_reviews.py <hotelId> --no-api  # 强制浏览器模式
  python scripts/ctrip_reviews.py <hotelId> --show    # 显示浏览器窗口(调试)
  python scripts/ctrip_reviews.py logout              # 清除登录状态

hotelId 获取方式:
  1. search 子命令: python scripts/ctrip_reviews.py search "酒店全名"
  2. 携程酒店详情页URL: hotels.ctrip.com/hotels/detail?hotelid=XXXX

首次使用需先登录: python scripts/ctrip_reviews.py login --show""")


if __name__ == "__main__":
    sys.exit(main())
