---
name: trip-scout
description: >
  个人/家庭机酒搜索和自驾游行程规划助手。双场景驱动：场景一（机酒搜索）飞猪+携程双平台搜索，
  智能酒店筛选（品牌信任梯度、加盟/直营识别、差评分析、黑榜），自进化学习；
  场景二（自驾游行程规划）小红书路线推荐→酒店联动调整→地图渲染（H5行程页+高德专属地图双轨）→飞书攻略生成。
  触发词：搜机票、搜酒店、找酒店、订机票、机酒搜索、自驾游、行程规划、路线推荐、
  road trip、trip plan、travel search、flight search、hotel search。
---

# Trip Scout

个人/家庭机酒搜索和自驾游行程规划助手。核心能力：**场景驱动的旅行助手**。

## 场景路由

根据用户意图选择场景：

| 用户意图 | 场景 |
|---------|------|
| 搜机票、搜酒店、机酒搜索、flight/hotel search | **场景一：机酒搜索** |
| 自驾游、行程规划、路线推荐、road trip、trip plan、X天X路线 | **场景二：自驾游行程规划** |
| 用户说"帮我规划行程""推荐路线""做个攻略" | **场景二：自驾游行程规划** |
| 用户同时提到机酒和行程 | 先走场景二，其中机酒搜索复用场景一能力 |

---

## 场景一：机酒搜索

### Phase 1: 航班搜索

读 `references/flight-search.md`。

核心流程：
1. 从用户输入提取：出发城市、目的地、日期、人数
2. 并行调用飞猪 `flyai search-flight` + 携程问道 API
3. 合并结果，按价格排序
4. 给出明确建议（不是罗列全部）
5. 更新搜索历史

### Phase 2: 酒店搜索与智能筛选

读 `references/hotel-search.md`。

核心流程：
1. 确认搜索条件（目的地、日期、人数、预算）
2. 并行调用飞猪 `flyai search-hotel` + 携程问道 API
   - **价格是酒店筛选最重要的一项**：携程问道可查指定酒店精确房型含早价（非区间），Phase 1/2/3 日期变动重验证都用它，比 ctrip_prices.py(Playwright需登录)更轻量。详见 `references/hotel-search.md` "问道查指定酒店房型含早价格"
3. **黑名单过滤** — 直接移除已拉黑酒店
4. **品牌信任过滤** — 低信任品牌需额外验证
5. **差评分析** — 区分成长性差评 vs 本质性差评（必须先调用 `python scripts/ctrip_reviews.py <hotelId>`，详见 `references/review-analysis.md`）
6. **加盟/直营判断** — 加盟翻牌标注⚠️
7. **小红书交叉验证（可选）** — TOP3 真实口碑校准踩雷风险(读 `references/xhs-hotel-research.md`)。**小红书不可用时跳过此步**，以携程差评为主判据
   - 判断方式：`python scripts/xhs.py check-login` 失败 → 跳过
   - 小红书可用时：纯 API 方案（无浏览器自动化，降低被风控检测风险），读 `references/xhs-hotel-research.md`
8. 综合排序（信任等级 × 质价比 × 亲子友好度）
9. 输出推荐 + 外选 + 已过滤原因

### Phase 3: 信任体系维护

读 `references/hotel-trust-system.md` + `references/review-analysis.md`。

触发时机：
- 用户说"再也不住" → 拉黑 + 降品牌信任
- 用户说"这个不错" → 升品牌信任
- 发现加盟翻牌 → 标记风险 + 检查同品牌其他店
- 入住后反馈 → 更新 MEMORY.md

### Phase 4: 飞书参考（可选）

用户提到"参考之前的攻略"时触发。

读取飞书文件夹「旅行攻略」：
```bash
lark-cli drive +inspect --url 'https://my.feishu.cn/drive/folder/AhBBfyHLulWjdwdR3ZKcqMHBngd'
```

提取历史行程中的酒店评价、目的地信息、路线规划作为搜索参考。
行程总览表中的"酒店住后评价"列是酒店知识库的重要更新来源。

---

## 场景二：自驾游行程规划

端到端工作流：路线推荐 → 酒店联动规划 → 机酒搜索 → 地图生成 → 飞书攻略

读 `references/trip-planning.md`（通用方法论）和 `references/road-trip-planning.md`（自驾游增量方法论）。

所有用户交互遵循**四拍格式**：Re-ground → Simplify → Recommend → Options。

### Phase 1: 路线推荐（多轮对话调整）

用户以自然语言提问后，进入多轮路线对比和调整循环，**用户明确确认路线后才进入 Phase 2**。

1. **解析约束** — 从提问中提取：时间、出发地、目的地/方向、人数、亲子需求、驾驶偏好
2. **风险评估** — 识别路线中的最大变数（季节性封路/天气敏感/预约瓶颈），按风险前置原则确定游玩方向（读 `references/road-trip-planning.md` 风险前置原则）
   - ⚠️ **预约通行检查**（独库公路北段等需预约路段）— 2026年6月25日起独库北段必须预约通行，未预约罚款200元+记1分。这是比封路更致命的风险：封路还能等，约不到就完全走不了
   - 预约通行检查清单：路线是否经过需预约路段？预约时段是否匹配行程？住宿点是否在预约入口附近？降级方案是否预设？
   - 详见 `references/road-trip-planning.md` "预约通行与封路通知获取"章节
3. **异地还车决策** — 检查路线沿途是否有可用机场（高德POI搜索"机场"），评估异地还车 vs 环线回原点的成本和时间对比，输出取还车节点方案（读 `references/road-trip-planning.md` 异地还车策略）
4. **路线搜索** — 优先小红书API，降级互联网搜索
   - **小红书路线搜索**（优先）— 复用 `scripts/xhs.py`，使用路线专用搜索词模板（读 `references/xhs-route-search.md`）
     ```
     "{区域} 自驾游路线"          # 首选
     "{区域} {天数}天 自驾游"      # 按天数过滤
     "{区域} 亲子自驾游"           # 亲子过滤
     "{具体路线名} 路线图"         # 如已知路线名
     "{区域} 自驾游 避坑"          # 避坑版
     ```
   - **互联网搜索**（降级）— 小红书不可用时（`check-login` 失败），用 `WebSearch` 搜索 `"{区域} 自驾游路线 攻略"`，从马蜂窝/携程游记/穷游/知乎获取路线信息
   - 降级时筛选标准不变（保留路线信号/丢弃非路线信号），但信息结构化程度较低，需更多人工判断
5. **筛选和适配** — 结合用户画像（从 MEMORY.md 读取出行模式、驾驶节奏偏好等）筛选路线
6. **高德API校正** — 用 amap-lbs-skill 校正每段路线的里程/时长/过路费
   ```bash
   export AMAP_WEBSERVICE_KEY="$AMAP_WEBSERVICE_KEY"
   amap-lbs-skill route-planning \
     --type=driving --origin=lng,lat --destination=lng,lat
   ```
   > `route-planning.js` 来自 amap-lbs-skill（`openclaw skills install @lbs-amap/amap-lbs-skill`），安装后用 `node <skill-dir>/scripts/route-planning.js` 调用，下同。
7. **快速酒店可行性检查** — 对每条候选路线的每个住宿点，用 wendao-skill 和 flyai 快速搜索，确认**有无符合用户最低标准的酒店**（评分≥4.5、携程4钻及以上、品牌信任体系内品牌），标注 ✅(有合格酒店)/⚠️(选择少)/❌(无合格酒店，需调整住宿点)。此阶段**不做精确对比、智能筛选和差评分析**，只确认最低门槛通过
8. **提取路线图片** — 从小红书笔记详情提取图片URL（`image_list`字段），取前3张用于"🖼️ 参考路线图"。小红书不可用时跳过此步
9. **生成高德地图路线URL** — 用 `ditu.amap.com/dir` indexed via 格式生成路线预览链接（优先生成环线一条URL，途经点超5个才拆两段），详见 `references/xhs-route-search.md`
10. **输出候选路线** — 2-3条可选路线，含每日行程概要、驾驶里程/时长、住宿点建议、酒店可行性、🖼️参考路线图、📍路线地图预览、⚠️风险评估+降级方案、✈️异地还车方案
11. **多轮对话调整** — 用户基于路线图预览反馈调整（换方向、加减天数、调整住宿点、换路线、选异地还车），重新生成路线URL和表格，直到用户明确说"确认这条路线"
12. 用户确认后进入 Phase 2

> **Phase 1 只用路线地图预览URL**（`ditu.amap.com/dir`），不生成专属地图。专属地图有5条lineList渲染上限，适合最终确认后生成（Phase 4B），不适合路线对比阶段。路线预览URL支持11+途经点完整渲染，用户一次点击就能看全路线走向，快速对齐直观感受。

### Phase 2: 酒店联动规划

混合模式：快速先验（Phase 1 已完成）+ 完整后验

**⚠️ Phase 2 是差评分析引擎的触发起点**。Phase 1 只做快速可行性检查，不触发差评分析。进入 Phase 2 后，每个候选酒店都必须跑完整差评分析流程（读 `references/review-analysis.md`）。

**携程差评获取流程**（Phase 2 触发时执行）：
1. 首次使用检查登录态：`python scripts/ctrip_reviews.py check-login`
2. 未登录则提示用户：`python scripts/ctrip_reviews.py login --show`（扫码登录，Cookie自动持久化，路径由脚本管理）
3. 获取hotelId（两种方式，问道说"无该店"时必须用方式b）：
   - a. Python API：`from ctrip.reviews import search_hotel_id; search_hotel_id("酒店全名")`
   - b. CLI search命令（问道兜底）：`python scripts/ctrip_reviews.py search "酒店名或目的地关键词"` — 全局搜索框方式，详见 `references/review-analysis.md`
4. 抓取差评（双轨并用，实战经验2026-07-08）：
   - `python scripts/ctrip_reviews.py <hotelId> --months 12 --pages 20`（API模式，拿总评论数+差评率）
   - `python scripts/ctrip_reviews.py <hotelId> --no-api --months 12 --pages 3`（浏览器模式，拿精确差评做分类分析）
   - ⚠️ **API模式用评分≤3过滤会漏90%差评**（携程差评定义≠评分≤3），差评内容分析必须用浏览器模式
5. 酒店对比时必须全方位对比（日期/房型/价格/差评），详见 `references/hotel-search.md` 酒店全方位对比规则
6. 详见 `references/review-analysis.md` 携程差评量化规则

**完整后验**（用户选定路线后）：
1. 对每个住宿点跑完整酒店搜索+筛选流程（**复用场景一 Phase 2 全部能力**）
2. 若住宿点无合格酒店 → 自动搜索周边有好酒店的地方
   - 高德POI搜索周边城镇（2小时内车程，可配置1小时）
     ```bash
     amap-lbs-skill poi-search \
       --keywords=镇 --location=lng,lat --radius=100000
     ```
   - 对候选城镇做快速酒店可行性检查
   - 选出有合格酒店且对行程影响最小的城镇
   - 联动调整前后日行程
3. 用高德API重新计算受影响路段
4. 输出调整说明：为什么改、改到哪里、新方案的影响

**酒店联动调整原则**：
- 住宿品质优先于路线完美——不能为了"到原定目的地"而住在差酒店
- 调整住宿点后，确保前后日驾驶量仍在合理范围（亲子≤300km/4-5h）
- 明确告知用户调整原因和影响

### Phase 3: 机酒搜索（复用场景一能力）

- 航班搜索：复用场景一 Phase 1（如需飞到取车点）
- 酒店确认：复用场景一 Phase 2（最终确认每个住宿点的酒店选择）
- 用户确认所有酒店和航班后，进入 Phase 4

**D1住宿规则（自驾游强制）**：飞行抵达日必须住飞行目的地城市，不安排当天开车赶路。原因：
1. 取车+熟悉车辆需1-2h，加上午餐/休息，当天再开3h+太赶
2. 飞行日住宿飞行目的地，D2早上租车出发，行程更从容
3. 机票时段选择更多（不用抢早班赶路），价格也更便宜

**机酒联动日期优化**：用户给出日期范围（如"9.25-10.7之间选9天"）时，不能直接定出发日期。需：
1. 在范围内搜索多条出发/回程日期组合的机票价格
2. 结合酒店价格波动（国庆/旺季前后差2-3倍），计算每条日期组合的机酒总费用
3. 输出总费用最低的推荐出发日期 + 其他日期组合的费用对比
4. 详见 `references/flight-search.md` 机酒联动日期优化

### Phase 4: 行程地图生成（双轨方案）

**行前参考**：H5行程页（高德JSAPI 2.0）+ **行中导航**：高德专属地图（远程MCP Server）

#### 4A: H5行程页（行前参考）

基于 `assets/template.html`（高德JSAPI 2.0 + Apple Design System），生成行程地图H5页面。

1. 填充行程数据（每日景点、住宿、路线段）
2. 每段自驾路线标注里程/时长/过路费/路况
3. 路线段用实线连接（区别于步行/打车的虚线），每天用不同颜色
4. 集成"📍 专属地图"按钮 — 用户点击即可在手机高德App中打开专属地图
5. 输出到 `output/{trip-name}/index.html`

#### 4B: 高德专属地图（行中导航）

通过远程MCP Server的 `maps_schema_personal_map` 工具生成专属地图，用户在手机高德App中打开后可一键导航/打车/探店。

**接入方式**：Streamable HTTP（远程MCP Server，15个工具含专属地图）
```
URL: https://mcp.amap.com/mcp?key={AMAP_MAPS_API_KEY}
```

**配置教程**（二选一，按你使用的AI编程助手选择）：

Claude Code — 编辑 `~/.claude/settings.json`：
```json
{
  "mcpServers": {
    "amap-maps": {
      "url": "https://mcp.amap.com/mcp?key=YOUR_AMAP_MAPS_API_KEY"
    }
  }
}
```

OpenClaw — 编辑 `~/.openclaw/openclaw.json`：
```json
{
  "mcp": {
    "servers": {
      "amap-maps": {
        "enabled": true,
        "transport": "streamable-http",
        "url": "https://mcp.amap.com/mcp?key=YOUR_AMAP_MAPS_API_KEY"
      }
    }
  }
}
```

> `AMAP_MAPS_API_KEY` 需在高德开放平台（https://console.amap.com）申请，选择"Web服务"类型。

**调用 `maps_schema_personal_map`**：
```json
{
  "orgName": "伊犁小环线10天自驾游",
  "lineList": [
    {
      "title": "D1-D2 乌鲁木齐→独山子→赛里木湖",
      "pointInfoList": [
        {"name": "乌鲁木齐", "lon": 87.617, "lat": 43.825, "poiId": "B03DF0S7YM"},
        {"name": "独山子区", "lon": 84.887, "lat": 44.328, "poiId": "B01CB012FK"},
        {"name": "赛里木湖", "lon": 81.387, "lat": 44.617, "poiId": "B038D0LN3D"}
      ]
    },
    {
      "title": "D3-D4 赛里木湖→博乐→伊宁",
      "pointInfoList": [
        {"name": "赛里木湖", "lon": 81.387, "lat": 44.617, "poiId": "B038D0LN3D"},
        {"name": "博乐市", "lon": 82.051, "lat": 44.854, "poiId": "B038D0LPVE"},
        {"name": "伊宁市", "lon": 81.278, "lat": 43.908, "poiId": "B03E70M9B5"}
      ]
    }
  ]
}
```

⚠️ **lineList渲染上限**：通过 `maps_schema_personal_map` API生成的专属地图，高德App端最多渲染5条lineList（实测6条和7条只渲染前5条，11条只渲染前5条）。**如行程天数超过5天，合并相邻天数为行程阶段**，确保 `lineList.length ≤ 5`。合并规则：
- 按行程阶段分组（去程/环线/回程），每组1-2天
- 每条lineList的 `pointInfoList` 包含该阶段所有关键点位（起终点+住宿点+核心景点）
- `title` 使用"D1-D2 起点→途经→终点"格式，保留天数信息
- **回程段必须与最后一段合并在同一条lineList中**，否则段间不画连线

⚠️ **专属地图路线连线限制**：高德专属地图的路线连线由API自动计算，**不支持自定义路线**。季节性道路（如独库公路）高德默认绕行，专属地图中的连线会走绕行路线而非实际行驶路线。解决方案：
- **专属地图定位**：行中导航+探店+打车，点位标注正确即可
- **H5行程页定位**：行前参考，可用 AMap.Polyline 画自定义路线（含独库公路），展示真实行驶轨迹
- 用户行中导航时，在高德App中手动选择独库公路路线即可

返回：`amapuri://workInAmap/createWithToken?polymericId=mcp_xxx&from=MCP`

**专属地图功能**：
- 所有行程点位标注在高德地图上
- 一键导航到每个目的地
- 一键打车到下一站
- 查看POI详细信息（评分/电话/营业时间）
- 行中实时导航和探店

**poiId获取方式**：通过 `maps_text_search` 或 `maps_around_search` 搜索POI获取poiId，或通过 `maps_geo` 地理编码获取坐标后查找附近POI。

#### 远程MCP Server与amap-lbs-skill的分工

| 用途 | 工具 | 说明 |
|------|------|------|
| 驾车路线校正（里程/时长/过路费） | **amap-lbs-skill** `route-planning.js` | 支持途经点（waypoints），远程MCP不支持 |
| POI搜索+地理编码 | **远程MCP** `maps_text_search` / `maps_geo` | MCP工具，直接调用 |
| **专属地图生成** | **远程MCP** `maps_schema_personal_map` | npm包无此功能，只有远程版有 |
| 导航唤端 | **远程MCP** `maps_schema_navi` | 生成导航链接 |
| 打车唤端 | **远程MCP** `maps_schema_take_taxi` | 生成打车链接 |
| 周边城镇搜索（酒店联动） | **amap-lbs-skill** `poi-search.js` | 支持location+radius参数 |
| 天气查询 | **远程MCP** `maps_weather` | npm包无此功能 |

Location types: `food` | `spot` | `drink` | `hotel` | `transport` | `road-trip`

### Phase 5: 飞书攻略生成

全自动生成飞书文档旅行攻略，使用 lark-doc skill：

```bash
lark-cli docs +create --api-version v2 --content '<title>标题</title>...'
```

**文档结构**（综合4个真实攻略模板提炼）：
```
# {emoji} {年份}{假期}·{目的地}{类型}

## 📋 行程总览
表格：日期 | 行程 | 住宿 | 驾驶里程 | 驾驶时长 | 备注 | 酒店住后评价（最高10分）
- 总驾车里程 + 高速免费提示
- 高德地图驾车路线规划API逐段校正声明
- 路线地图截图

## 🌤️ 每日天气与穿衣指南（如可获取）

## 📅 每日详细行程
### D1 · {日期}（{星期}）| {行程描述}
- ⏰ 时间安排（按用户偏好，默认9:30出发）
- 🏨 住宿详情
- 🌟 沿途亮点/活动
- 🛣️ 行驶路线（起点→终点 | Xkm | Xh | ¥过路费 | 路况）

## 💰 费用预算表
### 🚗 交通（租车费/油费/过路费/异地还车费/机票）
### 🏨 住宿
### 🎫 景区门票
### 🍜 餐饮
### 合计 + 每家分摊

## ⚠️ 关键风险与应对
## 📋 预约通行提醒（如有需预约路段：预约平台/时段/抢号时间/错峰策略/封路确认流程）
## 🎒 出行准备清单（通用+亲子增量+高原增量）
## 🔑 方案亮点
```

**租车提醒**（不集成搜索，用户自行在一嗨或神州等平台选择）：
- 全险必买 | 儿童安全座椅确认 | 异地还车费 | 车型选择（如7座MPV）
- 油量规则（满油取满油还）| 车型锁定（提前3天APP+电话确认）

**酒店住后评价闭环**：
- 行程总览表含"酒店住后评价（最高10分）"列
- 行程结束后用户在飞书文档中补充评价
- 系统读取评价 → 更新 `~/.trip-scout/MEMORY.md` 入住历史
- 评分≤3 → 更新 `~/.trip-scout/blacklist.md`
- 评价数据反哺酒店知识库，为下次选酒店参考

---

## Shared Memory

**首次运行必须先初始化运行时记忆**(确保 `~/.trip-scout/` 目录和模板文件存在):

```bash
python scripts/init_memory.py
```

该脚本:首次运行从 `templates/` 拷贝 MEMORY.md/blacklist.md 到 `~/.trip-scout/`; 已存在则跳过(不覆盖用户数据)。新用户 clone 后跑一次即可开箱可用。

初始化后读取 `~/.trip-scout/MEMORY.md`。用于：
- 用户偏好（出发城市、品牌梯度、价格区间、会员权益、出行模式）
- 入住历史（已住酒店、体验评分、品牌信任变化）
- 学到的规则（加盟识别、差评分类、黑名单）
- 酒店住后评价（从飞书攻略的行程总览表读取）

首次使用需编辑 MEMORY.md 填入个人会员权益和偏好（携程/万豪/亚朵/华住会等级、出发城市）。

每次完成搜索/入住反馈后更新该文件。黑名单酒店写入 `~/.trip-scout/blacklist.md`。

详细格式见 `references/memory-format.md`。

---

## 输出格式规范

### 航班搜索输出（场景一 Phase 1 / 场景二 Phase 3）

```markdown
## ✈️ [出发] → [目的地] | [日期]

| 平台 | 航班 | 出发机场 | 到达机场 | 时间 | 价格 | 备注 |
|------|------|---------|---------|------|------|------|
| 飞猪 | XX1234 | 双流T2 | 天山 | 08:00-10:30 | ¥680 | 直飞 |
| 携程 | XX1234 | 双流T2 | 天山 | 08:00-10:30 | ¥720 | 直飞, 可选座 |

### 💡 建议
[一句话明确推荐，含机场选择理由]
```

⚠️ **出发/到达机场全名+航站楼必须输出**，同城市多机场（成都双流/天府等）必须区分，标注距市区距离。近郊机场贵≤¥100/人时优先选近郊。

### 酒店搜索输出（场景一 Phase 2 / 场景二 Phase 2）

```markdown
## 🏨 [目的地] | [日期范围]

### ⭐ 首选推荐

**[酒店名]**
- 平台: 飞猪 ¥XXX/晚 | 携程 ¥XXX/晚
- 品牌: [品牌]（[信任等级]）| 类型: [直营/加盟/待确认]
- 开业: [年份] | 评分: 携程 [X.X]
- 亮点: [亲子设施、特色等]
- 差评分析: [成长性差评占比/本质性差评/无]
- 预订: [飞猪链接] | [携程链接]

### 📋 备选方案
1. **[酒店名]** — 飞猪 ¥XXX | 携程 ¥XXX | [年份]开业 | [X.X]分 | [直营/加盟]

### ❌ 已过滤
- **[酒店名]**: [过滤原因]

### ⚠️ 品牌提示
- [如有品牌信任变化提示]
```

### 路线推荐输出（场景二 Phase 1）

```markdown
## 🗺️ [目的地]自驾游路线推荐 | [天数]天

### 路线A: [路线名]（推荐）
| 天数 | 行程 | 住宿 | 驾驶 | 酒店可行性 |
|------|------|------|------|-----------|
| D1 | 成都→丹巴 | 丹巴 | 364km/5h/¥105 | ✅ |
| D2 | 丹巴→新都桥 | 新都桥 | 145km/3h/¥0 | ⚠️ |

### 🖼️ 参考路线图（小红书笔记图片）
> 以下图片来自小红书路线攻略笔记，可能包含路线示意图、行程表或风景照（非地图图片属概率性误差）
- [路线图1]({图片URL}) — 来源：{笔记标题}
- [路线图2]({图片URL}) — 来源：{笔记标题}

### 📍 路线地图预览（高德地图）
> 点击链接在高德地图中查看完整路线，途经点已预设
- [完整环线]({高德地图URL}) — {起点}→...→{终点} | {总里程}km环线
- ⚠️ {季节性路段标注，如"独山子→唐布拉走独库北段，高德默认绕行，需手动选择"}

### ⚠️ 风险评估
| 风险路段 | 风险类型 | 建议 | 降级方案 |
|---------|---------|------|---------|
| 独库公路北段 | **预约通行+季节性封路** | D2先走(风险前置)，提前1-7天预约 | 抢不到预约→绕行赛里木湖方向，多走1天 |

### 📋 预约通行提醒（如有需预约路段）
- **需预约路段**：独库公路北段（乌苏驿—乔尔玛—那拉提，约185km）
- **预约平台**："游新疆一码游"微信小程序 / "新疆交警"公众号
- **预约时段**：8:00-10:00 / 10:00-12:00 / 12:00-14:00 / 14:00-16:00 / 16:00-19:00
- **抢号时间**：每天凌晨0:00释放第7天名额，旺季热门时段紧张，建议定闹钟
- **错峰策略**：抢不到上午时段→选16:00-19:00（名额充足+雪山夕阳）
- **封路确认**：出发前1天+当天早上查"新疆路网"公众号确认路况

### 🔄 调整选项
> 觉得路线不合适？告诉我想怎么调：
- 换方向（正向/反向游玩）
- 增减天数
- 调整住宿点
- 换一条路线

### 路线B: [路线名]
[同上格式，含🖼️参考路线图、📍路线地图预览、⚠️风险评估]

### 💡 建议
[结合用户画像的推荐理由，含风险前置分析]
```

**高德地图路线URL生成规则**（已验证）：

| 规则 | 说明 |
|------|------|
| 格式 | `ditu.amap.com/dir?type=car&policy=1&from[lnglat]=...&from[name]=...&to[lnglat]=...&to[name]=...&via[i][lnglat]=...&via[i][name]=...` |
| 途经点 | indexed via 格式（`via[0]`, `via[1]`, ...），最多5个途经点稳定可用 |
| **环线优先** | **优先生成一条完整环线URL**（起终点相同），用户一次点击看全路线 |
| 分段降级 | 仅当途经点超5个导致显示不全时，拆为"去程段"+"返程段"两段 |
| 季节性路段 | 独库公路等季节性道路高德无法自动规划，需标注⚠️"需在高德App中手动选择" |
| ❌ 不可用格式 | `uri.amap.com/navigation`（重定向丢途经点）、`vian/vialons/vialats/vianames`（App也不识别）、`via=合并格式`（只解析第一个） |

### 酒店联动调整输出（场景二 Phase 2）

```markdown
## 🔄 住宿调整：[原住宿点] → [新住宿点]

- 原因: [原住宿点]无合格酒店（搜索结果均评分<4.5或差评率高）
- 调整: 改住[新住宿点]（距原点驾车X分钟）
- 影响: D[X]多开Xkm，D[X+1]少开Xkm，总里程不变
- 新酒店: [酒店名]（[品牌] [信任等级]）¥XXX/晚
```

## Dependencies

| 工具 | 用途 | 安装 |
|------|------|------|
| `flyai-cli` | 飞猪搜索 | `npm i -g @fly-ai/flyai-cli` |
| `wendao-skill` | 携程问道搜索 | `openclaw skills install @trips-ai/wendao-skill` |
| `lark-cli` | 飞书读取/生成 | 见 [lark-shared](https://github.com/...) |
| **Playwright** | 携程差评/价格抓取(内置 vendor/ctrip) | `pip install -r requirements.txt && playwright install chromium` |
| **PyExecJS** | 小红书API签名(vendor/xhs_api) | 已含在 requirements.txt |
| **Node.js** | 小红书API签名JS执行 | 系统安装，PyExecJS底层调用 |
| **requests** | 携程差评API抓取+小红书API调用 | 已含在 requirements.txt |
| **amap-lbs-skill** | 高德驾车路线规划+POI搜索（支持途经点） | `openclaw skills install @lbs-amap/amap-lbs-skill` |
| **amap-mcp-remote** | 高德专属地图+导航+打车（远程MCP Server，15个工具） | Streamable HTTP，见4B配置教程 |
| **神州租车API** | 租车搜索（一嗨/神州异地还车费已免除） | 见 [开发者文档](https://developer.zuche.com/api.do) |

### 开箱即用说明(clone 后)

```bash
# 1. Python 依赖(携程差评抓取+小红书API+通用)
pip install -r requirements.txt
playwright install chromium   # 仅携程差评/价格抓取需要

# 2. 初始化运行时记忆(从 templates/ 拷贝模板, 首次必跑)
python scripts/init_memory.py

# 3. 环境变量
export FLYAI_API_KEY="..."        # 飞猪
export WENDAO_API_KEY="..."       # 携程问道
export AMAP_WEBSERVICE_KEY="..."  # 高德地图(自驾游路线规划)

# 4. 配置高德远程MCP Server(专属地图+导航+打车)
# Claude Code — 编辑 ~/.claude/settings.json:
# "amap-maps": {
#   "url": "https://mcp.amap.com/mcp?key=YOUR_AMAP_MAPS_API_KEY"
# }
# OpenClaw — 编辑 ~/.openclaw/openclaw.json:
# "amap-maps": {
#   "enabled": true,
#   "transport": "streamable-http",
#   "url": "https://mcp.amap.com/mcp?key=YOUR_AMAP_MAPS_API_KEY"
# }
# AMAP_MAPS_API_KEY 需在高德开放平台(console.amap.com)申请"Web服务"类型
# 远程MCP Server提供15个工具(含maps_schema_personal_map专属地图)
# npm包(@amap/amap-maps-mcp-server)只有12个工具，无专属地图功能

# 5. 首次用小红书需设置cookie(两种方式二选一)
# 方式a: QR码登录(纯API，终端显示二维码)
python scripts/xhs.py qrcode
# 方式b: 手动设置cookie(从浏览器DevTools复制)
python scripts/xhs.py set-cookie --cookie "a1=xxx; web_session=xxx"
# 验证登录态
python scripts/xhs.py check-login

# 6. 首次用携程差评抓取需扫码登录(cookie 由脚本自动管理)
python scripts/ctrip_reviews.py login --show   # 弹浏览器窗口扫码
python scripts/ctrip_reviews.py check-login    # 验证登录态
# ⚠️ 必须先登录，否则脚本返回空数据(携程对无Cookie请求静默返回totalCount=0)
# 搜索酒店(获取hotelId): python scripts/ctrip_reviews.py search "酒店名"
# 问道说"无该店"时用search命令验证: python scripts/ctrip_reviews.py search "伊宁绿发洲际酒店"

# 7. 编辑个人偏好(可选)
# 按需填写 ~/.trip-scout/MEMORY.md 的会员权益和出发城市
```

小红书能力已 vendored 进 `vendor/xhs_api/`(源自 [Spider_XHS](https://github.com/cv-cat/Spider_XHS), MIT), 采用**纯 HTTP API 方案**（逆向签名算法，直接API调用，无浏览器自动化，降低被风控检测风险）。通过 `scripts/xhs.py` 入口调用:
```bash
python scripts/xhs.py search "那拉提英迪格 避雷" --limit 10     # 酒店口碑
python scripts/xhs.py search "川西小环线 自驾游路线" --limit 20  # 路线搜索
python scripts/xhs.py feed <note_url_or_id>                      # 笔记详情
```
⚠️ 签名JS文件(`xhs_main_260411.js`等)可能随小红书前端更新而失效，需从 Spider_XHS 上游同步更新。
小红书不可用时，酒店口碑验证跳过（以携程差评为主），路线搜索降级为互联网搜索。

高德地图能力**双轨并行**：

**amap-lbs-skill**（驾车路线规划，支持途经点）：
```bash
# 安装: openclaw skills install @lbs-amap/amap-lbs-skill
# 以下命令中 <skill-dir> 指向 amap-lbs-skill 安装目录

# 驾车路线规划(里程/时长/过路费)
node <skill-dir>/scripts/route-planning.js \
  --type=driving --origin=lng,lat --destination=lng,lat

# 带途经点
node <skill-dir>/scripts/route-planning.js \
  --type=driving --origin=lng,lat --destination=lng,lat --waypoints=lng,lat;lng,lat

# POI搜索(周边城镇/景点)
node <skill-dir>/scripts/poi-search.js \
  --keywords=镇 --city=丹巴 --offset=10

# 周边搜索(酒店联动调整)
node <skill-dir>/scripts/poi-search.js \
  --keywords=镇 --location=lng,lat --radius=100000
```

**远程MCP Server**（专属地图+导航+打车，Streamable HTTP接入）：
```
URL: https://mcp.amap.com/mcp?key={AMAP_MAPS_API_KEY}
工具: 15个（含 maps_schema_personal_map / maps_schema_navi / maps_schema_take_taxi）
配置: 见 Phase 4B 配置教程（Claude Code / OpenClaw 二选一）
文档: https://developer.amap.com/api/mcp-server/summary
```

## Resources

- `references/flight-search.md` — 航班搜索工作流
- `references/hotel-search.md` — 酒店搜索 + 筛选工作流
- `references/hotel-trust-system.md` — 信任体系 + 加盟识别 + 黑榜
- `references/review-analysis.md` — 差评分析引擎
- `references/xhs-hotel-research.md` — 小红书酒店口碑交叉验证
- `references/xhs-route-search.md` — 小红书自驾游路线搜索（路线专用搜索词+筛选标准）
- `references/trip-planning.md` — 通用行程规划方法论
- `references/road-trip-planning.md` — 自驾游增量方法论（驾驶节奏/路线三角/车辆规划/路况风险/预约通行与封路通知）
- `references/dianping-research.md` — 大众点评调研工作流
- `references/memory-format.md` — 记忆格式 + 自进化规则
- `vendor/xhs_api/` — 内置小红书纯 API 客户端(MIT, 源自 cv-cat/Spider_XHS，逆向签名算法，直接HTTP API调用)
- `vendor/ctrip/` — 内置携程 Playwright+API 双轨客户端(基于 hu1102/ctrip_hotel API + xcccccc68/selenium-ctrip-hotel-reviews 浏览器方案 + biaowuqiong/ctrip-hotel-skill Playwright MCP 方案)
- `scripts/xhs.py` — 小红书口碑验证+路线搜索入口
- `scripts/ctrip_reviews.py` — 携程酒店差评抓取分析
- `scripts/init_memory.py` — 首次运行初始化运行时记忆
- `assets/template.html` — 行程地图H5模板(高德JSAPI 2.0, 支持 road-trip 路线段+专属地图按钮)
- `templates/MEMORY.md` + `templates/blacklist.md` — 运行时记忆模板
