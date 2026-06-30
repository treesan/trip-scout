#!/usr/bin/env python3
"""
trip-scout 携程酒店差评抓取与分析

复用携程内部 REST API getHotelCommentList(源自 Z-an-K/ctrip-review-crawler, MIT),
纯 requests 调用, 无浏览器, 能精准抓差评(filterInfo id:3)。

用法:
    python scripts/ctrip_reviews.py <hotelId> [--months 12] [--pages 20]

输出: JSON 到 stdout, 含分类统计+近期趋势+踩雷风险。
hotelId 从携程酒店详情页 URL 获取(如 hotels.ctrip.com/hotels/detail?hotelid=XXXX)。
"""
import argparse
import json
import sys
from datetime import datetime, timedelta

import requests

API_URL = "https://m.ctrip.com/restapi/soa2/33278/getHotelCommentList"
HEADERS = {
    "Content-type": "application/json",
    "Origin": "https://hotels.ctrip.com",
    "Referer": "https://hotels.ctrip.com",
    "accept": "*/*",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36",
}
HEAD_BLOCK = {
    "platform": "PC", "cver": "0", "cid": "", "bu": "HBU", "group": "ctrip",
    "aid": "", "sid": "", "ouid": "", "locale": "zh-CN", "timezone": "8",
    "currency": "CNY", "pageId": "102003", "vid": "", "guid": "", "isSSR": False,
}

# 差评分类关键词(复用 references/review-analysis.md)
CATEGORIES = {
    "成长性": ["装修味", "甲醛", "新开业", "磨合", "还在提升", "还在调试",
              "设施还在完善", "员工培训", "刚开业", "开业才", "味道"],
    "可接受": ["排队", "等待久", "价格贵", "性价比", "停车远", "停车不便",
              "位置偏", "交通不便", "隔音", "房间小", "早餐一般", "wifi",
              "空调声音", "水压"],
    "本质性": ["脏", "卫生差", "有虫", "蟑螂", "老鼠", "异味", "态度差",
              "态度恶劣", "服务差", "不处理", "推诿", "不安全", "门锁坏",
              "消防", "安全隐患", "与实际不符", "欺诈", "强制消费", "涨价",
              "设施损坏", "热水没有", "空调坏了", "电视坏了", "被子薄", "冷醒"],
    "系统性": ["原来", "原名", "改名", "翻牌", "换管理", "管理混乱",
              "员工流动", "换人", "挂大牌", "品牌标准", "加盟", "个体"],
}


def fetch_comments(hotel_id: str, page_index: int, negative_only: bool = True):
    """抓单页评论。negative_only=True 用差评筛选(id:3)。"""
    filter_info = [{"id": 3, "filterType": 1}] if negative_only else [{"id": 4, "filterType": 1}]
    payload = {
        "hotelId": str(hotel_id), "pageIndex": page_index, "pageSize": 10,
        "repeatComment": 1, "needStaticInfo": False,
        "functionOptions": ["integratedTopComment"],
        "filterInfo": filter_info, "orderBy": 1, "head": HEAD_BLOCK,
    }
    try:
        r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json().get("data", {})
        return data.get("commentList", [])
    except Exception as e:
        print(json.dumps({"error": f"page {page_index}: {e}"}, ensure_ascii=False), file=sys.stderr)
        return []


def classify(text: str, rating: float = None) -> str:
    """把单条差评归类。命中哪类返回哪类, 多类命中按严重度高者优先。
    rating≤1.5 的极低分默认归本质性(必有硬伤), 除非命中成长性。"""
    if not text:
        text = ""
    # 先查成长性(装修味等, 即使低分也可能是新店磨合)
    for kw in CATEGORIES["成长性"]:
        if kw in text:
            return "成长性"
    # 系统性(加盟/翻牌/管理混乱)优先于本质性
    for kw in CATEGORIES["系统性"]:
        if kw in text:
            return "系统性"
    # 本质性
    for kw in CATEGORIES["本质性"]:
        if kw in text:
            return "本质性"
    # 极低分兜底: rating≤1.5 必有硬伤, 归本质性
    if rating is not None and float(rating) <= 1.5:
        return "本质性"
    # 宽松匹配: 卫生/管理/服务+差/乱/塌
    for kw in ["卫生一般", "卫生差", "管理乱", "管理一塌", "设施差", "服务差", "差到不行"]:
        if kw in text:
            return "本质性"
    return "可接受"


def analyze(hotel_id: str, months: int, max_pages: int):
    cutoff = datetime.now() - timedelta(days=months * 30)
    all_comments = []
    for page in range(1, max_pages + 1):
        cl = fetch_comments(hotel_id, page, negative_only=True)
        if not cl:
            break
        all_comments.extend(cl)
        # 早停: 若某页最早评论已超 cutoff, 不必再翻(但差评页按时间倒序, 继续翻拿更早的)
        # 简单起见翻满 max_pages 或无数据停
        if len(cl) < 10:
            break

    # 筛近 N 月 + 解析
    recent = []
    for c in all_comments:
        date_str = (c.get("createDate") or "")[:10]  # YYYY-MM-DD
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if d >= cutoff:
            recent.append({
                "date": date_str,
                "rating": c.get("rating"),
                "content": (c.get("content") or "").strip(),
                "category": classify(c.get("content") or "", c.get("rating")),
            })

    # 分类统计
    cat_count = {c: 0 for c in CATEGORIES}
    for r in recent:
        cat_count[r["category"]] = cat_count.get(r["category"], 0) + 1
    total = len(recent)

    # 近3月趋势
    three_mo_ago = datetime.now() - timedelta(days=90)
    recent_3mo = sum(1 for r in recent if datetime.strptime(r["date"], "%Y-%m-%d") >= three_mo_ago)

    # 踩雷风险
    essential = cat_count.get("本质性", 0)
    systemic = cat_count.get("系统性", 0)
    if total == 0:
        risk = "未知(无差评或抓取失败)"
    elif (essential + systemic) / total > 0.5:
        risk = "🔴高"
    elif (essential + systemic) / total > 0.2:
        risk = "🟡中"
    else:
        risk = "🟢低"

    return {
        "hotelId": hotel_id,
        "negativeReviewsInPeriod": total,
        "periodMonths": months,
        "categoryBreakdown": cat_count,
        "categoryPercent": {k: round(v / total * 100, 1) for k, v in cat_count.items()} if total else {},
        "last3MonthsCount": recent_3mo,
        "trendNote": "近3个月差评突增=近期恶化⚠️" if recent_3mo > total * 0.4 and total >= 5 else "近3个月差评占比正常",
        "踩雷风险": risk,
        "sampleReviews": [
            {"date": r["date"], "rating": r["rating"], "category": r["category"],
             "content": r["content"][:200]}
            for r in sorted(recent, key=lambda x: x["date"], reverse=True)[:5]
        ],
    }


def main():
    p = argparse.ArgumentParser(description="携程酒店差评抓取分析")
    p.add_argument("hotelId", help="携程酒店ID")
    p.add_argument("--months", type=int, default=12, help="分析近N个月(默认12)")
    p.add_argument("--pages", type=int, default=20, help="最多翻页数(默认20)")
    args = p.parse_args()
    result = analyze(args.hotelId, args.months, args.pages)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
