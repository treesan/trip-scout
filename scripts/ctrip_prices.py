"""
携程酒店价格抓取 - Playwright浏览器模式

批量获取指定酒店在指定日期范围的双床含早价格。
从携程酒店详情页DOM提取房型价格信息。

用法:
    python scripts/ctrip_prices.py <hotelId> --check-in 2026-09-26 --check-out 2026-09-27
    python scripts/ctrip_prices.py <hotelId> --check-in 2026-09-26 --check-out 2026-09-27 --show
    python scripts/ctrip_prices.py --batch hotels.json  # 批量模式

输出: JSON到stdout，含双床含早价格、最低价、房型详情。
"""
import argparse
import json
import sys
import os
import time
import re

# Windows GBK 终端兼容
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# vendored 模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vendor"))

from ctrip.client import CtripClient


def extract_prices_from_page(page, hotel_id, check_in, check_out):
    """从携程酒店详情页提取价格信息"""
    result = {
        "hotelId": hotel_id,
        "checkIn": check_in,
        "checkOut": check_out,
        "twinBedWithBreakfast": None,
        "twinBedNoBreakfast": None,
        "lowestPrice": None,
        "allPrices": [],
        "roomDetails": [],
    }

    # 等待页面加载
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    # 展开所有房型：点击"展开更多房型"按钮，滚动加载
    try:
        # 滚动到房型区域
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
        time.sleep(1)

        # 多次点击"展开更多房型"按钮
        for _ in range(5):
            clicked = page.evaluate(r"""() => {
                const btns = document.querySelectorAll('button, a, div, span');
                for (const btn of btns) {
                    const text = (btn.innerText || '').trim();
                    if (text.includes('展开更多') || text.includes('查看更多房型') ||
                        text.includes('更多房型') || text.includes('全部房型') ||
                        text.includes('展示额外') || text.includes('查看全部')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
            if clicked:
                time.sleep(2)
            else:
                break

        # 再次滚动到底部加载更多
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
    except Exception:
        pass

    # 提取页面中所有价格和房型信息
    data = page.evaluate(r"""() => {
        const body = document.body.innerText;
        const prices = [];
        const re = /¥([\d,]{3,5})/g;
        let m;
        while ((m = re.exec(body)) !== null) {
            const val = parseInt(m[1].replace(/,/g, ''));
            if (val >= 100 && val <= 9999) prices.push(val);
        }
        prices.sort((a, b) => a - b);
        const uniquePrices = [...new Set(prices)].slice(0, 15);

        // 从页面文本中提取房型块（每个房型是一个文本块）
        // 携程房型格式: "房型名\n可住人数\n床型\n窗户\n面积\n...\n早餐类型\n取消政策\n...\n¥价格\n预订"
        const textBlocks = [];
        // 尝试按房型容器分割
        const roomContainers = document.querySelectorAll(
            '[class*="room-item"], [class*="RoomItem"], [class*="roomItem"], ' +
            '[data-room-id], [class*="hotel-room"], [class*="RoomList"] > div, ' +
            'tr[class*="room"], [class*="room-card"]'
        );

        if (roomContainers.length > 0) {
            roomContainers.forEach(el => {
                const text = (el.innerText || '').trim();
                if (text.length > 20 && text.length < 1000) {
                    textBlocks.push(text);
                }
            });
        }

        // 如果结构化容器没找到，用全文按"房型名"模式分割
        if (textBlocks.length === 0) {
            // 按双换行分割，找含价格和床型的块
            const blocks = body.split(/\n{2,}/);
            for (const block of blocks) {
                if (block.includes('¥') && (block.includes('床') || block.includes('房'))) {
                    textBlocks.push(block.substring(0, 300));
                }
            }
        }

        // 从每个文本块中提取结构化房型信息
        const structuredRooms = [];
        for (const block of textBlocks) {
            const priceMatches = [...block.matchAll(/¥([\d,]{3,5})/g)];
            const isTwin = /双床|2张.*床|两.*床|twin|2×1/i.test(block);
            const bedMatch = block.match(/(\d+)张([\d.]+)米([^\n]*)/);
            const hasBreakfast = /含早|双早|2份早餐|2份.*早|含.*早|breakfast/i.test(block);
            const noBreakfast = /无早|不含早|无早餐|无.*早/i.test(block);
            const areaMatch = block.match(/([\d.]+)平方米/);

            // 提取房型名（通常是第一行）
            const firstLine = block.split('\n')[0].trim();

            // 提取价格：找"2份早餐"或"含早"后面最近的价格，或"无早餐"后面最近的价格
            let bfPrice = null;
            let noBfPrice = null;

            // 按早餐类型分割文本找对应价格
            const bfSections = block.split(/(2份早餐|含双早|含早|双早)/);
            const noBfSections = block.split(/(无早|不含早|无早餐)/);

            for (const sec of bfSections) {
                if (/2份早餐|含双早|含早|双早/.test(sec)) {
                    // 找这个section后面最近的价格
                    const afterBf = bfSections[bfSections.indexOf(sec) + 1] || '';
                    const pm = afterBf.match(/¥([\d,]{3,5})/);
                    if (pm) bfPrice = parseInt(pm[1].replace(/,/g, ''));
                }
            }

            for (const sec of noBfSections) {
                if (/无早|不含早|无早餐/.test(sec)) {
                    const afterNoBf = noBfSections[noBfSections.indexOf(sec) + 1] || '';
                    const pm = afterNoBf.match(/¥([\d,]{3,5})/);
                    if (pm) noBfPrice = parseInt(pm[1].replace(/,/g, ''));
                }
            }

            // 如果没找到含早价格，但有"优惠"模式: "¥569\n¥481" (原价→折后价)
            // 含早行通常格式: "2份早餐\n...\n优惠88\n\n¥569\n¥481\n预订"
            if (!bfPrice && hasBreakfast) {
                // 找含早标记附近的价格
                const bfIdx = block.search(/2份早餐|含双早|含早/);
                if (bfIdx >= 0) {
                    const afterText = block.substring(bfIdx);
                    const pm = afterText.match(/¥([\d,]{3,5})/);
                    if (pm) bfPrice = parseInt(pm[1].replace(/,/g, ''));
                }
            }

            if (priceMatches.length > 0) {
                structuredRooms.push({
                    name: firstLine.substring(0, 80),
                    isTwinBed: isTwin,
                    bedInfo: bedMatch ? `${bedMatch[1]}张${bedMatch[2]}米${bedMatch[3]}` : '',
                    hasBreakfast: hasBreakfast,
                    noBreakfast: noBreakfast,
                    bfPrice: bfPrice,
                    noBfPrice: noBfPrice,
                    area: areaMatch ? areaMatch[1] : '',
                    allPrices: priceMatches.map(m => parseInt(m[1].replace(/,/g, ''))),
                    snippet: block.substring(0, 200)
                });
            }
        }

        return {
            prices: uniquePrices,
            structuredRooms: structuredRooms
        };
    }""")

    result["allPrices"] = data.get("prices", [])
    structured = data.get("structuredRooms", [])

    if result["allPrices"]:
        result["lowestPrice"] = result["allPrices"][0]

    # 从结构化房型数据中找双床含早
    twin_rooms = [r for r in structured if r.get("isTwinBed")]

    # 优先找双床含早的bfPrice
    twin_with_bf = [r for r in twin_rooms if r.get("hasBreakfast") and r.get("bfPrice")]
    if twin_with_bf:
        twin_with_bf.sort(key=lambda x: x["bfPrice"])
        result["twinBedWithBreakfast"] = twin_with_bf[0]["bfPrice"]
        result["twinBedWithBreakfastRoom"] = twin_with_bf[0].get("name", "")
        result["twinBedWithBreakfastBedInfo"] = twin_with_bf[0].get("bedInfo", "")

    # 双床不含早
    twin_no_bf = [r for r in twin_rooms if r.get("noBreakfast") and r.get("noBfPrice")]
    if twin_no_bf:
        twin_no_bf.sort(key=lambda x: x["noBfPrice"])
        result["twinBedNoBreakfast"] = twin_no_bf[0]["noBfPrice"]

    # 如果双床含早没有bfPrice但有hasBreakfast标记，取allPrices中最低价
    if not result.get("twinBedWithBreakfast"):
        twin_has_bf = [r for r in twin_rooms if r.get("hasBreakfast")]
        if twin_has_bf:
            # 取含早房型allPrices中最后一个（通常是折后价）
            all_p = []
            for r in twin_has_bf:
                all_p.extend(r.get("allPrices", []))
            if all_p:
                all_p.sort()
                result["twinBedWithBreakfast"] = all_p[-1] if len(all_p) > 1 else all_p[0]
                result["twinBedWithBreakfastRoom"] = twin_has_bf[0].get("name", "")
                result["twinBedWithBreakfastBedInfo"] = twin_has_bf[0].get("bedInfo", "")

    # 保存所有房型结构化数据供调试
    result["structuredRooms"] = structured

    return result


def _extract_twin_bed_price_from_text(text, with_breakfast=True):
    """从页面文本中用正则提取双床含早/不含早价格"""
    if not text:
        return None

    # 常见模式: "双床房 含双早 ¥599" 或 "双床房·含早 ¥499" 等
    if with_breakfast:
        patterns = [
            r'双床[房间]?\s*[·•\-]?\s*含[双两]?早\s*[¥￥]([\d,]{3,5})',
            r'双床[房间]?\s*[·•\-]?\s*含早\s*[¥￥]([\d,]{3,5})',
            r'含[双两]?早\s*[·•\-]?\s*双床[房间]?\s*[¥￥]([\d,]{3,5})',
            r'[¥￥]([\d,]{3,5})\s*双床[房间]?\s*含[双两]?早',
        ]
    else:
        patterns = [
            r'双床[房间]?\s*[·•\-]?\s*无早\s*[¥￥]([\d,]{3,5})',
            r'双床[房间]?\s*[·•\-]?\s*不含早\s*[¥￥]([\d,]{3,5})',
            r'无早\s*[·•\-]?\s*双床[房间]?\s*[¥￥]([\d,]{3,5})',
        ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1).replace(",", ""))

    return None


def fetch_hotel_price(hotel_id, check_in, check_out, headless=True):
    """获取单个酒店在指定日期的价格"""
    client = CtripClient(headless=headless)
    client.start()
    try:
        url = f"https://hotels.ctrip.com/hotels/detail/?hotelId={hotel_id}&checkIn={check_in}&checkOut={check_out}"
        client.navigate(url)
        result = extract_prices_from_page(client.page, hotel_id, check_in, check_out)
        return result
    except Exception as e:
        return {"hotelId": hotel_id, "checkIn": check_in, "checkOut": check_out, "error": str(e)}
    finally:
        client.close()


def fetch_batch(batch_data, headless=True):
    """批量获取多个酒店的价格

    batch_data格式:
    [
        {"hotelId": "132338651", "name": "万达锦华", "checkIn": "2026-09-26", "checkOut": "2026-09-27"},
        ...
    ]
    """
    client = CtripClient(headless=headless)
    client.start()
    results = []
    try:
        for item in batch_data:
            hotel_id = item["hotelId"]
            check_in = item["checkIn"]
            check_out = item["checkOut"]
            name = item.get("name", "")

            url = f"https://hotels.ctrip.com/hotels/detail/?hotelId={hotel_id}&checkIn={check_in}&checkOut={check_out}"
            client.navigate(url)
            result = extract_prices_from_page(client.page, hotel_id, check_in, check_out)
            result["name"] = name
            results.append(result)
            print(f"✅ {name} ({hotel_id}) {check_in}→{check_out}: 双床含早={result.get('twinBedWithBreakfast', 'N/A')} 最低={result.get('lowestPrice', 'N/A')}", file=sys.stderr)
    except Exception as e:
        print(f"❌ 批量抓取出错: {e}", file=sys.stderr)
    finally:
        client.close()
    return results


def main():
    p = argparse.ArgumentParser(description="携程酒店价格抓取 (Playwright浏览器模式)")
    p.add_argument("hotelId", nargs="?", help="携程酒店ID")
    p.add_argument("--check-in", required=False, help="入住日期 YYYY-MM-DD")
    p.add_argument("--check-out", required=False, help="离店日期 YYYY-MM-DD")
    p.add_argument("--batch", help="批量模式: JSON文件路径，含hotelId/checkIn/checkOut/name数组")
    p.add_argument("--show", action="store_true", help="显示浏览器窗口(调试)")
    p.add_argument("--output", "-o", help="输出JSON文件路径(默认stdout)")

    ns = p.parse_args()

    headless = not ns.show

    if ns.batch:
        # 批量模式
        with open(ns.batch, "r", encoding="utf-8") as f:
            batch_data = json.load(f)
        results = fetch_batch(batch_data, headless=headless)
    elif ns.hotelId and ns.check_in and ns.check_out:
        # 单酒店模式
        results = fetch_hotel_price(ns.hotelId, ns.check_in, ns.check_out, headless=headless)
    else:
        p.print_help()
        return 1

    output = json.dumps(results, ensure_ascii=False, indent=2)
    if ns.output:
        with open(ns.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"结果已保存到 {ns.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
