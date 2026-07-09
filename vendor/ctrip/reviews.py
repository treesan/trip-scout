"""
携程酒店评论抓取模块

通过 Playwright 浏览器操控携程网页，提取酒店差评数据。
支持：
- 差评筛选(filterInfo id:3)
- 按时间排序
- 自动翻页
- 分类统计(成长性/可接受/本质性/系统性)
- 近3月趋势分析
- 踩雷风险评估
"""
import json
import os
import sys
import time
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from .client import CtripClient, DEFAULT_COOKIE_PATH

# Type hints - 使用 TYPE_CHECKING 避免循环导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page

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
    # 极低分兜底
    if rating is not None:
        try:
            if float(rating) <= 1.5:
                return "本质性"
        except (ValueError, TypeError):
            pass
    # 宽松匹配
    for kw in ["卫生一般", "卫生差", "管理乱", "管理一塌", "设施差", "服务差", "差到不行"]:
        if kw in text:
            return "本质性"
    return "可接受"


def search_hotel_id(hotel_name: str, city_id: int = 0, client: CtripClient = None) -> Optional[str]:
    """
    通过携程全局搜索框获取酒店ID

    流程：打开携程首页 → 在顶部搜索框输入酒店名 → 从下拉列表url属性提取hotelId

    下拉列表DOM：div.search_list_hotel，url属性格式：
      "http://hotels.ctrip.com/hotel/{hotelId}.html?cityid={cityId}"

    Args:
        hotel_name: 酒店名称（如"乌鲁木齐福朋喜来登酒店"）
        city_id: 未使用（保留兼容）
        client: 已启动的CtripClient（如提供则复用，否则新建）

    Returns:
        hotelId字符串，找不到返回None
    """
    should_close = client is None
    if client is None:
        client = CtripClient(headless=True)
        client.start()

    try:
        page = client.page

        # 打开携程酒店首页
        page.goto('https://hotels.ctrip.com/', wait_until='networkidle', timeout=20000)
        time.sleep(3)

        # 在顶部全局搜索框输入酒店名
        search_input = page.locator('#_allSearchKeyword')
        search_input.click()
        time.sleep(0.5)
        search_input.fill(hotel_name)
        time.sleep(3)  # 等待下拉列表加载

        # 从下拉列表提取hotelId
        result = page.evaluate("""(hotelName) => {
            const items = document.querySelectorAll('.search_list_hotel');
            const shortName = hotelName.substring(0, 4);

            // 优先匹配名称精确的
            for (const item of items) {
                const url = item.getAttribute('url') || '';
                const word = item.getAttribute('word') || '';
                const hotelIdMatch = url.match(/hotel\\/(\\d+)/) || url.match(/hotelId=(\\d+)/);
                const hotelId = hotelIdMatch ? hotelIdMatch[1] : '';
                if (word.includes(shortName) && hotelId) {
                    return {hotelId, word, method: 'exact'};
                }
            }

            // 降级：第一个有hotelId的结果
            for (const item of items) {
                const url = item.getAttribute('url') || '';
                const word = item.getAttribute('word') || '';
                const hotelIdMatch = url.match(/hotel\\/(\\d+)/) || url.match(/hotelId=(\\d+)/);
                const hotelId = hotelIdMatch ? hotelIdMatch[1] : '';
                if (hotelId) {
                    return {hotelId, word, method: 'first'};
                }
            }

            return null;
        }""", hotel_name)

        if result and result.get('hotelId'):
            print(f"找到hotelId={result['hotelId']} ({result['word']}, {result['method']})", file=sys.stderr)
            return result['hotelId']

        # 降级：如果全局搜索框没找到，尝试目的地+酒店名搜索
        # 输入目的地城市，然后输入酒店名
        print("全局搜索未找到，尝试目的地+酒店名搜索...", file=sys.stderr)

        page.goto('https://hotels.ctrip.com/', wait_until='networkidle', timeout=20000)
        time.sleep(3)

        # 输入目的地
        dest_input = page.locator('input[placeholder="目的地"]').first
        dest_input.click()
        time.sleep(1)
        # 从酒店名中提取城市（假设前2-3个字是城市名）
        city = hotel_name[:3] if len(hotel_name) >= 3 else hotel_name[:2]
        dest_input.fill(city)
        time.sleep(2)
        # 选择下拉中的城市
        page.evaluate("""(city) => {
            const items = document.querySelectorAll('[class*="suggest"] li, [class*="Suggest"] li, [class*="dest"] li');
            for (const item of items) {
                if (item.textContent.includes(city.substring(0, 2))) { item.click(); return; }
            }
        }""", city)
        time.sleep(1)

        # 输入酒店名
        hotel_keyword = hotel_name.replace(city, '').replace('酒店', '').strip()
        hotel_input = page.locator('input[placeholder*="位置/品牌/酒店"]').first
        hotel_input.click()
        time.sleep(1)
        hotel_input.fill(hotel_keyword)
        time.sleep(2)

        # 点击搜索
        search_btn = page.locator('button:has-text("搜索")').first
        if search_btn.count() > 0:
            search_btn.click()
        else:
            hotel_input.press('Enter')
        time.sleep(12)

        # 从搜索结果页提取hotelId
        results2 = page.evaluate("""(hotelName) => {
            const els = document.querySelectorAll('[data-offline-hotelid]');
            const shortName = hotelName.substring(0, 4);
            for (const el of els) {
                const id = el.getAttribute('data-offline-hotelid');
                const text = el.textContent.substring(0, 100).trim();
                if (text.includes(shortName) && id) return id;
            }
            // 降级：第一个
            const first = els[0];
            return first ? first.getAttribute('data-offline-hotelid') : null;
        }""", hotel_name)

        return results2

    finally:
        if should_close:
            client.close()


def _try_api_fetch(hotel_id: str, page_index: int, cookies_str: str) -> List[Dict]:
    """
    尝试用 API 方式抓取评论（如果浏览器cookie可用的话）。
    使用移动端 API: soa2/34308/getHotelCommentInfo

    Returns:
        评论列表，失败返回空列表
    """
    try:
        import requests
    except ImportError:
        return []

    url = "https://m.ctrip.com/restapi/soa2/34308/getHotelCommentInfo"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://m.ctrip.com",
        "Referer": f"https://m.ctrip.com/webapp/hotel/j/hoteldetail/dianping/{hotel_id}.html",
        "Cookie": cookies_str,
    }
    payload = {
        "hotelId": hotel_id,
        "sceneTypes": ["CommentList"],
        "commentFilterOptions": {
            "pageIndex": page_index,
            "pageSize": 10,
            "keyWord": "",
            "commonStatisticList": ["1"],  # 全部评论
            "orderBy": "1",
            "rooms": [],
            "travelTypes": [],
            "filterDateTypeList": [],
            "repeatComment": 1,
        },
        "head": {
            "cid": "09031148113011295299",
            "ctok": "", "cver": "1.0", "lang": "01", "sid": "8888", "syscode": "09",
            "auth": "", "xsid": "",
            "extension": [
                {"name": "sotpLocale", "value": "zh-CN"},
                {"name": "sotpRegion", "value": "CN"},
                {"name": "sotpGroup", "value": "ctrip"},
                {"name": "sotpBu", "value": "hbu"},
                {"name": "locale", "value": "zh-CN"},
                {"name": "pageId", "value": "228032"},
                {"name": "htl-bu", "value": "HBU"},
                {"name": "htl-timeZone", "value": "8"},
            ],
            "platform": "H5", "group": "ctrip", "bu": "HBU", "locale": "zh-CN",
            "region": "CN", "currency": "CNY",
            "appId": "100054203", "timeZone": "8", "pageId": "228032",
            "isEnforceSyscode": True, "isSSR": False,
        },
    }

    try:
        r = __import__("requests").post(url, json=payload, headers=headers, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("ResponseStatus", {}).get("Ack") != "Success":
            return []
        groups = data.get("data", {}).get("groupList", [])
        total_count = data.get("data", {}).get("totalCount", 0)
        comments = []
        for g in groups:
            if "commentList" in g:
                for item in g["commentList"]:
                    # 移动端API评分在 ratingInfo.ratingAll
                    rating_info = item.get("ratingInfo", {})
                    rating_all = rating_info.get("ratingAll", rating_info.get("fullRating", None))
                    # 差评筛选：ratingAll <= 3 视为差评（移动端API不支持差评标签筛选）
                    comments.append({
                        "id": item.get("id"),
                        "content": (item.get("content") or "").strip(),
                        "rating": rating_all,
                        "createDate": item.get("createDate", ""),
                        "checkinDate": item.get("checkinDate", ""),
                        "roomName": item.get("roomName", ""),
                    })
        # 返回评论列表和总数
        return comments
    except Exception:
        return []


class ReviewsFetcher:
    """携程酒店评论浏览器抓取器"""

    # 携程酒店评论页URL模板
    HOTEL_REVIEW_URL = "https://hotels.ctrip.com/hotels/detail/comment/{hotel_id}"

    def __init__(self, client: CtripClient):
        self.client = client

    def fetch_reviews_browser(
        self,
        hotel_id: str,
        max_pages: int = 20,
        negative_only: bool = True,
    ) -> List[Dict]:
        """
        通过浏览器抓取酒店差评

        流程（已验证DOM结构）：
        1. 酒店详情页 → 点击<h2>点评tab → 弹出drawer抽屉
        2. 抽屉内点击"差评(55)"按钮（class Y6jbaTqhIt3qdU3xFKfj，active class HteG2KwV0zK560YQAbkY）
        3. 提取差评列表（class yRvZgc0SICPUbmdb2L2a），含评分/内容/日期/房型
        4. 翻页（分页器 class E7ufy5rNpuXnxgcwkjPa）

        Args:
            hotel_id: 携程酒店ID
            max_pages: 最多翻页数
            negative_only: 是否只看差评

        Returns:
            评论列表
        """
        page = self.client.page

        # 1. 导航到酒店详情页
        url = f"https://hotels.ctrip.com/hotels/detail/?hotelId={hotel_id}"
        self.client.navigate(url)
        time.sleep(5)

        # 2. 点击"点评"tab（<h2 class="onlineTab_tabNavgation_item">点评</h2>）
        # 这会弹出drawer抽屉
        try:
            clicked = page.evaluate("""() => {
                const tabs = document.querySelectorAll('h2[class*="onlineTab_tabNavgation_item"]');
                for (const t of tabs) {
                    if (t.textContent.trim() === '点评') { t.click(); return true; }
                }
                return false;
            }""")
            if clicked:
                time.sleep(5)
                print("已点击点评tab", file=sys.stderr)
            else:
                # 备选：通过文本查找
                comment_tab = page.locator('h2:has-text("点评")')
                if comment_tab.count() > 0:
                    comment_tab.first.click()
                    time.sleep(5)
                    print("已点击点评tab(文本匹配)", file=sys.stderr)
                else:
                    print("未找到点评tab", file=sys.stderr)
        except Exception as e:
            print(f"点击点评tab失败: {e}", file=sys.stderr)

        # 3. 在抽屉内点击差评标签
        # 两个位置都有差评按钮：
        #   - 页面内: button.reivewTags_reviewTag-item（点击会弹出抽屉）
        #   - 抽屉内: button.Y6jbaTqhIt3qdU3xFKfj（点击切换差评筛选）
        if negative_only:
            try:
                time.sleep(2)
                # 先尝试抽屉内的差评按钮
                clicked = page.evaluate("""() => {
                    const btns = document.querySelectorAll('button.Y6jbaTqhIt3qdU3xFKfj');
                    for (const btn of btns) {
                        if (btn.textContent.includes('差评')) { btn.click(); return 'drawer-btn'; }
                    }
                    // 备选：页面内的差评按钮（会触发抽屉弹出）
                    const outerBtns = document.querySelectorAll('button[class*="reivewTags_reviewTag-item"]');
                    for (const btn of outerBtns) {
                        if (btn.textContent.includes('差评')) { btn.click(); return 'outer-btn'; }
                    }
                    // 兜底：任何包含"差评"的button
                    const allBtns = document.querySelectorAll('button');
                    for (const btn of allBtns) {
                        if (btn.textContent.includes('差评')) { btn.click(); return 'any-btn'; }
                    }
                    return null;
                }""")
                time.sleep(5)
                if clicked:
                    print(f"已点击差评标签({clicked})", file=sys.stderr)
                else:
                    print("未找到差评标签，尝试继续抓取全部评论", file=sys.stderr)
            except Exception as e:
                print(f"点击差评标签失败: {e}", file=sys.stderr)

        # 4. 提取差评列表 + 翻页
        all_comments = []
        seen_keys = set()

        for pg in range(1, max_pages + 1):
            comments = self._extract_reviews_from_page(page)
            if not comments:
                if pg == 1:
                    # 首次提取失败，尝试滚动抽屉内容区
                    try:
                        page.evaluate("""() => {
                            const content = document.querySelector('[class*="drawer_drawerContainer-content"]');
                            if (content) {
                                const inner = content.querySelector('div');
                                if (inner) inner.scrollTop = inner.scrollHeight;
                            }
                        }""")
                        time.sleep(2)
                        comments = self._extract_reviews_from_page(page)
                    except Exception:
                        pass
                if not comments:
                    break

            # 去重
            new_comments = []
            for c in comments:
                key = c.get("content", "")[:50]
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_comments.append(c)

            all_comments.extend(new_comments)
            print(f"第{pg}页: 新增{len(new_comments)}条差评 | 累计{len(all_comments)}条", file=sys.stderr)

            # 5. 点击下一页
            if not self._click_next_page(page):
                break

            time.sleep(random.uniform(1.5, 3.0))

        return all_comments

    def _extract_reviews_from_page(self, page) -> List[Dict]:
        """从抽屉内提取差评列表

        抽屉内差评DOM结构（DOM验证 2026-07-08）：

        评论列表容器: div.dfoDA5kEcrM1Xd3n4SqY
        每条评论: div.yRvZgc0SICPUbmdb2L2a
          ├─ 用户信息区: div.fv1x8oSY77gj7tSX5QWM
          │   ├─ 用户名: div.b9MY20ntrfhSadoEoJpq > div > div (纯文本如"阿鹏")
          │   └─ 房型/日期/类型: ul.wl5HTVzzG2JXWejYiabW > li > span (4个li)
          ├─ 内容区: div.RkvqTN_AeMa_BEIZyYbx
          │   ├─ 评分: div.MLiQc9R1hSDl3AuzxunL > div > div > strong (如"2.3")
          │   ├─ 评论文字: div > div > div.tpHRPkB7n9UV_c7A5t6h (第一条)
          │   └─ 图片: div > div > ul > li > img
          └─ 底部: div.dEebu8jRxvgK9lGI7aSA
              └─ 发布日期: div > div (如"2026年6月22日发布")

        注意：携程class名是随机hash，但同一次页面加载内稳定。
        策略：先定位评论列表容器的class，然后用结构化遍历提取。
        """
        try:
            comments_data = page.evaluate("""() => {
                const results = [];
                const seen = new Set();

                // 提取单条评论数据的通用函数
                function extractReviewData(child, seen) {
                    // 提取评分 — 找 strong 元素（评分数字如 2.3）
                    let rating = '';
                    const strongs = child.querySelectorAll('strong');
                    for (const s of strongs) {
                        const text = s.textContent.trim();
                        if (/^\\d+\\.?\\d*$/.test(text) && parseFloat(text) <= 5) {
                            rating = text;
                            break;
                        }
                    }

                    // 提取房型+入住日期 — 找 ul 中的 li > span
                    let roomName = '';
                    let checkinDate = '';
                    const infoList = child.querySelector('ul');
                    if (infoList) {
                        const spans = infoList.querySelectorAll('span');
                        for (const sp of spans) {
                            const text = sp.textContent.trim();
                            if (text.includes('入住')) {
                                checkinDate = text.replace(/^于/, '').replace(/入住$/, '');
                            } else if (text.includes('房') || text.includes('套')) {
                                roomName = text;
                            }
                        }
                    }

                    // 提取评论内容 — 用innerText然后剥离元数据
                    let content = '';
                    const metaTexts = new Set();
                    // 用户名
                    const nameEl = child.querySelector('div > div > div');
                    if (nameEl && nameEl.textContent.trim().length < 20 && nameEl.children.length === 0) {
                        metaTexts.add(nameEl.textContent.trim());
                    }
                    // 房型/入住日期/出行类型/点评数
                    const infoSpans = child.querySelectorAll('ul span');
                    for (const sp of infoSpans) {
                        const t = sp.textContent.trim();
                        if (t) metaTexts.add(t);
                    }
                    // 评分
                    if (rating) metaTexts.add(rating);
                    // 有用/发布
                    const bottomEls = child.querySelectorAll('span, div');
                    for (const el of bottomEls) {
                        const t = el.textContent.trim();
                        if (t.includes('有用') || t.includes('发布') || t.includes('展开更多')) {
                            metaTexts.add(t);
                        }
                    }

                    // 从innerText提取正文
                    const allLines = child.innerText.split('\\n').map(l => l.trim()).filter(l => l);
                    const contentLines = [];
                    let pastRating = false;
                    for (const line of allLines) {
                        if (metaTexts.has(line)) continue;
                        if (/^\\d+\\.?\\d*$/.test(line) && parseFloat(line) <= 5) { pastRating = true; continue; }
                        if (line.includes('入住') || line.includes('条点评')) continue;
                        if (pastRating) {
                            if (line.includes('酒店回复')) break;
                            if (line.includes('展开更多')) continue;
                            if (line.includes('有用')) break;
                            if (/\\d{4}年\\d{1,2}月\\d{1,2}日发布/.test(line)) break;
                            contentLines.push(line);
                        }
                    }
                    content = contentLines.join('\\n').trim();

                    // 降级: 如果上面没提取到，用评分后的innerText
                    if (!content || content.length < 10) {
                        const fullText = child.innerText.trim();
                        const ratingIdx = fullText.indexOf(rating);
                        if (ratingIdx >= 0) {
                            const afterRating = fullText.substring(ratingIdx + rating.length).trim();
                            const replyIdx = afterRating.indexOf('酒店回复');
                            const usefulIdx = afterRating.indexOf('有用');
                            const dateIdx = afterRating.search(/\\d{4}年\\d{1,2}月\\d{1,2}日发布/);
                            let endIdx = afterRating.length;
                            if (replyIdx > 0) endIdx = Math.min(endIdx, replyIdx);
                            if (usefulIdx > 0) endIdx = Math.min(endIdx, usefulIdx);
                            if (dateIdx > 0) endIdx = Math.min(endIdx, dateIdx);
                            content = afterRating.substring(0, endIdx).replace(/展开更多/g, '').trim();
                        }
                    }

                    // 提取发布日期
                    let publishDate = '';
                    const allText = child.querySelectorAll('div, span');
                    for (const el of allText) {
                        const text = el.textContent.trim();
                        const dm = text.match(/(\\d{4})年(\\d{1,2})月(\\d{1,2})日发布/);
                        if (dm) {
                            publishDate = dm[1] + '-' + dm[2].padStart(2, '0') + '-' + dm[3].padStart(2, '0');
                            break;
                        }
                        if (!publishDate && text.includes('入住')) {
                            const ym = text.match(/(\\d{4})年(\\d{1,2})月/);
                            if (ym) publishDate = ym[1] + '-' + ym[2].padStart(2, '0');
                        }
                    }

                    // 去重
                    const key = content.substring(0, 50);
                    if (content.length > 5 && !seen.has(key)) {
                        seen.add(key);
                        return {
                            content: content.substring(0, 500),
                            rating: rating,
                            createDate: publishDate || checkinDate,
                            roomName: roomName,
                        };
                    }
                    return null;
                }

                // 策略1: 抽屉内差评列表（通过分页器定位容器）
                // 找到评论列表容器：包含多个评论项，且有分页器
                // 通过分页器定位列表（分页器 UL 内有 LI 文字 1,2,3...）
                const pagers = document.querySelectorAll('ul');
                let reviewContainer = null;
                for (const ul of pagers) {
                    const lis = ul.querySelectorAll('li');
                    let pageNumCount = 0;
                    for (const li of lis) {
                        if (/^\\d+$/.test(li.textContent.trim())) pageNumCount++;
                    }
                    if (pageNumCount >= 3) {
                        // 找到分页器，其父元素就是评论列表容器
                        reviewContainer = ul.parentElement;
                        break;
                    }
                }

                // 策略1.5: 无分页器时，通过差评标签按钮的兄弟元素定位评论列表
                // DOM结构：content area > [评分概览, 筛选/排序, 热门提及(含差评按钮), 评论列表]
                // 评论列表是"热门提及"的下一个兄弟元素
                if (!reviewContainer) {
                    const badBtn = document.querySelector('button.Y6jbaTqhIt3qdU3xFKfj.HteG2KwV0zK560YQAbkY');
                    if (badBtn) {
                        // 从差评按钮向上找，检查每层的nextElementSibling是否含评论项
                        // 评论项特征：包含strong(评分≤5) + ul(房型信息)
                        let node = badBtn.parentElement;
                        for (let depth = 0; depth < 6 && node; depth++) {
                            let sibling = node.nextElementSibling;
                            while (sibling) {
                                const text = sibling.textContent;
                                // 排除非评论区域
                                if (!text.includes('筛选') && !text.includes('排序方式')
                                    && !text.includes('热门提及') && !text.includes('住客印象')
                                    && !text.includes('超棒') && !text.includes('条评论')) {
                                    // 查找评论项：包含strong评分+ul房型的div
                                    const reviewItems = Array.from(sibling.querySelectorAll('div')).filter(d => {
                                        const s = d.querySelector('strong');
                                        if (!s) return false;
                                        const rt = s.textContent.trim();
                                        return /^\\d+\\.?\\d*$/.test(rt) && parseFloat(rt) <= 5 && d.querySelector('ul');
                                    });
                                    if (reviewItems.length > 0) {
                                        // 去重：只保留最外层评论项（不被其他评论项包含）
                                        const topItems = reviewItems.filter(item =>
                                            !reviewItems.some(other => other !== item && other.contains(item))
                                        );
                                        for (const child of topItems) {
                                            const result = extractReviewData(child, seen);
                                            if (result) results.push(result);
                                        }
                                        break;
                                    }
                                }
                                sibling = sibling.nextElementSibling;
                            }
                            if (results.length > 0) break;
                            node = node.parentElement;
                        }
                    }
                }

                if (reviewContainer) {
                    // 评论项是容器的直接子div（排除分页器UL）
                    const children = reviewContainer.children;
                    for (const child of children) {
                        // 跳过分页器
                        if (child.tagName === 'UL' || child.tagName === 'DIV' && child.querySelectorAll('li').length > 3 && child.offsetHeight < 100) continue;
                        if (child.offsetHeight < 100) continue;  // 跳过小元素
                        const result = extractReviewData(child, seen);
                        if (result) results.push(result);
                    }
                }

                // 策略2: 降级 — 轮播评论（无评分，6条）
                if (results.length === 0) {
                    const swiperItems = document.querySelectorAll('[class*="reviewSwiper_reviewSwiper-item"]');
                    for (const item of swiperItems) {
                        const fullText = item.innerText.trim();
                        if (fullText.length < 10) continue;
                        // 去掉日期
                        let content = fullText.replace(/\\d{4}年\\d{1,2}月\\d{1,2}日/g, '').trim();
                        const key = content.substring(0, 50);
                        if (content.length > 5 && !seen.has(key)) {
                            seen.add(key);
                            // 尝试提取日期
                            const dm = fullText.match(/(\\d{4})年(\\d{1,2})月(\\d{1,2})日/);
                            let dateISO = '';
                            if (dm) dateISO = dm[1] + '-' + dm[2].padStart(2, '0') + '-' + dm[3].padStart(2, '0');
                            results.push({
                                content: content.substring(0, 500),
                                rating: '',
                                createDate: dateISO,
                                roomName: '',
                            });
                        }
                    }
                }

                return results;
            }""")

            return comments_data if comments_data else []

        except Exception as e:
            print(f"提取评论失败: {e}", file=sys.stderr)
            return []

    def _click_next_page(self, page) -> bool:
        """点击下一页按钮 — 抽屉内分页器

        分页器DOM: ul.E7ufy5rNpuXnxgcwkjPa
          ├─ li: 上一页(箭头)
          ├─ li: 当前页(1) — class 含 active 标识 (I1eEuqjh1PxMGIoYYnBM)
          ├─ li: 2, 3, 4, 5
          └─ li: 下一页(箭头)
        """
        try:
            # 方法1: 通过JS查找分页器并点击下一页
            clicked = page.evaluate("""() => {
                const pagers = document.querySelectorAll('ul');
                for (const ul of pagers) {
                    const lis = ul.querySelectorAll('li');
                    let pageNumCount = 0;
                    for (const li of lis) {
                        if (/^\\d+$/.test(li.textContent.trim())) pageNumCount++;
                    }
                    if (pageNumCount >= 2) {
                        // 找到分页器，找当前页的下一个
                        let foundCurrent = false;
                        for (const li of lis) {
                            const text = li.textContent.trim();
                            if (foundCurrent && /^\\d+$/.test(text)) {
                                li.click();
                                return 'next-page-' + text;
                            }
                            // 当前页通常有特殊class或被标记
                            if (li.className && (li.className.includes('active') || li.className.includes('Active')
                                || li.className.includes('I1eEuqjh1PxMGIoYYnBM'))) {
                                foundCurrent = true;
                            }
                        }
                        // 如果没找到active的li，尝试最后一个li（下一页箭头）
                        if (lis.length > 0) {
                            const lastLi = lis[lis.length - 1];
                            const a = lastLi.querySelector('a');
                            if (a) { a.click(); return 'next-arrow'; }
                            lastLi.click();
                            return 'last-li';
                        }
                    }
                }
                return null;
            }""")
            if clicked:
                time.sleep(3)
                return True

        except Exception:
            pass

        return False

    def fetch_reviews_api(
        self,
        hotel_id: str,
        max_pages: int = 20,
    ) -> List[Dict]:
        """
        通过API抓取评论（需要有效的Cookie）

        优先使用浏览器cookie转为API cookie字符串，然后调用移动端API。
        速度比浏览器快得多。
        """
        # 从浏览器上下文获取cookie
        cookies = self.client.context.cookies()
        if not cookies:
            print("无Cookie，API模式不可用", file=sys.stderr)
            return []

        # 转换为cookie字符串
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

        all_comments = []
        for pg in range(1, max_pages + 1):
            comments = _try_api_fetch(hotel_id, pg, cookie_str)
            if not comments:
                break
            all_comments.extend(comments)
            print(f"API 第{pg}页: 获取{len(comments)}条评论 | 累计{len(all_comments)}条", file=sys.stderr)
            time.sleep(random.uniform(0.5, 1.5))

        return all_comments


def analyze_reviews(
    comments: List[Dict],
    months: int = 12,
    negative_only: bool = True,
) -> Dict[str, Any]:
    """
    分析评论数据，输出分类统计+趋势+踩雷风险

    Args:
        comments: 评论列表
        months: 分析近N个月
        negative_only: True=只分析差评(评分≤3), False=分析全部

    Returns:
        分析结果字典
    """
    cutoff = datetime.now() - timedelta(days=months * 30)

    # 差评阈值：评分≤3视为差评
    NEGATIVE_RATING_THRESHOLD = 3.0

    # 筛近N月 + 解析
    recent = []
    total_in_period = 0  # 统计期间内总评论数（含好评）
    for c in comments:
        content = (c.get("content") or "").strip()
        if not content:
            continue

        date_str = (c.get("createDate") or "")[:10]
        rating_val = c.get("rating")

        # 评分可能是数字或dict(旧格式兼容)
        if isinstance(rating_val, dict):
            rating_num = rating_val.get("ratingAll", rating_val.get("fullRating", None))
        else:
            rating_num = rating_val

        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            # 尝试其他日期格式
            try:
                d = datetime.strptime(date_str, "%Y年%m月%d日")
            except (ValueError, TypeError):
                # 无日期的评论
                is_in_period = True
                d = None

        is_in_period = d is None or d >= cutoff
        if not is_in_period:
            continue

        total_in_period += 1

        # 差评筛选：negative_only=True时，只保留评分≤阈值的评论
        # 浏览器模式无评分数据时，不做评分过滤（全部保留给分类引擎处理）
        is_negative = True  # 默认保留
        if rating_num is not None and str(rating_num).strip() != '':
            # 有评分数据：评分≤阈值视为差评
            try:
                is_negative = float(rating_num) <= NEGATIVE_RATING_THRESHOLD
            except (ValueError, TypeError):
                is_negative = True  # 无法解析评分，保留
        # 无评分数据（浏览器模式）时不做过滤，全部保留

        if negative_only and not is_negative:
            continue

        recent.append({
            "date": date_str,
            "rating": rating_num,
            "content": content,
            "category": classify(content, rating_num),
        })

    # 分类统计
    cat_count = {c: 0 for c in CATEGORIES}
    for r in recent:
        cat_count[r["category"]] = cat_count.get(r["category"], 0) + 1
    total = len(recent)

    # 近3月趋势
    three_mo_ago = datetime.now() - timedelta(days=90)
    recent_3mo = 0
    for r in recent:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            if d >= three_mo_ago:
                recent_3mo += 1
        except (ValueError, TypeError):
            pass

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
        "negativeReviewsInPeriod": total,
        "totalReviewsInPeriod": total_in_period,
        "negativeRate": round(total / total_in_period * 100, 1) if total_in_period else 0,
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


def fetch_and_analyze(
    hotel_id: str,
    months: int = 12,
    max_pages: int = 20,
    negative_only: bool = True,
    headless: bool = True,
    cookie_path: str = DEFAULT_COOKIE_PATH,
    prefer_api: bool = True,
) -> Dict[str, Any]:
    """
    一站式抓取+分析

    Args:
        hotel_id: 携程酒店ID
        months: 分析近N个月
        max_pages: 最多翻页数
        negative_only: 是否只看差评
        headless: 是否无头模式
        cookie_path: Cookie文件路径
        prefer_api: 优先尝试API模式（更快）

    Returns:
        分析结果字典
    """
    client = CtripClient(headless=headless, cookie_path=cookie_path)
    try:
        client.start()
        fetcher = ReviewsFetcher(client)

        # 先尝试API模式（快）
        comments = []
        method = "browser"
        if prefer_api:
            comments = fetcher.fetch_reviews_api(hotel_id, max_pages=max_pages)
            if comments:
                method = "api"
                print(f"API模式成功，获取{len(comments)}条评论", file=sys.stderr)

        # API失败则降级到浏览器模式
        if not comments:
            print("API模式无数据，降级到浏览器模式...", file=sys.stderr)
            comments = fetcher.fetch_reviews_browser(
                hotel_id, max_pages=max_pages, negative_only=negative_only
            )

        if not comments:
            return {
                "hotelId": hotel_id,
                "error": "未能获取评论数据（可能未登录或hotelId无效）",
                "method": method,
                "negativeReviewsInPeriod": 0,
                "踩雷风险": "未知(抓取失败)",
            }

        result = analyze_reviews(comments, months=months, negative_only=negative_only)
        result["hotelId"] = hotel_id
        result["method"] = method
        result["totalFetched"] = len(comments)
        return result

    finally:
        client.close()
