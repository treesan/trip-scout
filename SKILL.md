---
name: trip-scout
description: >
  个人/家庭机酒搜索和自驾游行程规划助手。双场景驱动：场景一（机酒搜索）飞猪+携程双平台搜索，
  智能酒店筛选（品牌信任梯度、加盟/直营识别、差评分析、黑榜），自进化学习；
  场景二（自驾游行程规划）小红书路线推荐→酒店联动调整→地图渲染→飞书攻略生成。
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
3. **黑名单过滤** — 直接移除已拉黑酒店
4. **品牌信任过滤** — 低信任品牌需额外验证
5. **差评分析** — 区分成长性差评 vs 本质性差评
6. **加盟/直营判断** — 加盟翻牌标注⚠️
7. **小红书交叉验证** — TOP3 真实口碑校准踩雷风险(读 `references/xhs-hotel-research.md`)
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

### Phase 1: 路线推荐

用户以自然语言提问后：

1. **解析约束** — 从提问中提取：时间、出发地、目的地/方向、人数、亲子需求、驾驶偏好
2. **小红书路线搜索** — 复用 `scripts/xhs.py`，使用路线专用搜索词模板（读 `references/xhs-route-search.md`）
   ```
   "{区域} 自驾游路线"          # 首选
   "{区域} {天数}天 自驾游"      # 按天数过滤
   "{区域} 亲子自驾游"           # 亲子过滤
   "{具体路线名} 路线图"         # 如已知路线名
   "{区域} 自驾游 避坑"          # 避坑版
   ```
3. **筛选和适配** — 结合用户画像（从 MEMORY.md 读取出行模式、驾驶节奏偏好等）筛选路线
4. **高德API校正** — 用 amap-lbs-skill 校正每段路线的里程/时长/过路费
   ```bash
   export AMAP_WEBSERVICE_KEY="$AMAP_WEBSERVICE_KEY"
   node ~/.openclaw/skills/amap-lbs-skill/scripts/route-planning.js \
     --type=driving --origin=lng,lat --destination=lng,lat
   ```
5. **快速酒店可行性检查** — 对每条候选路线的每个住宿点做快速检查（有无评分≥4.5的酒店），标注 ✅/⚠️/❌
6. **输出候选路线** — 2-3条可选路线，含每日行程概要、驾驶里程/时长、住宿点建议、酒店可行性
7. 用户选择后进入 Phase 2

### Phase 2: 酒店联动规划

混合模式：快速先验（Phase 1 已完成）+ 完整后验

**完整后验**（用户选定路线后）：
1. 对每个住宿点跑完整酒店搜索+筛选流程（**复用场景一 Phase 2 全部能力**）
2. 若住宿点无合格酒店 → 自动搜索周边有好酒店的地方
   - 高德POI搜索周边城镇（2小时内车程，可配置1小时）
     ```bash
     node ~/.openclaw/skills/amap-lbs-skill/scripts/poi-search.js \
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

### Phase 4: 行程地图生成

基于 `assets/template.html`（Leaflet + Apple Design System），生成每日行程地图页。

1. 填充 `HOTEL` 对象和 `DAYS` 数组
2. 每段自驾路线用 `road-trip` location type，包含字段：
   - `distance`: 驾驶里程（如 "364km"）
   - `driveTime`: 驾驶时长（如 "5h06min"）
   - `toll`: 过路费（如 105）
   - `roadType`: 路况（如 "217省道"）
3. 路线段在地图上用实线连接（区别于步行/打车的虚线）
4. 输出到 `output/{trip-name}/index.html`

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

### 航班搜索输出（场景一 Phase 1）

```markdown
## ✈️ [出发] → [目的地] | [日期]

| 平台 | 航班 | 时间 | 价格 | 备注 |
|------|------|------|------|------|
| 飞猪 | XX1234 | 08:00-10:30 | ¥680 | 直飞 |
| 携程 | XX1234 | 08:00-10:30 | ¥720 | 直飞, 可选座 |

### 💡 建议
[一句话明确推荐]
```

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

### 路线B: [路线名]
[同上格式]

### 💡 建议
[结合用户画像的推荐理由]
```

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
| 问道 API | 携程搜索 | curl + JSON(无需安装) |
| `lark-cli` | 飞书读取/生成 | 见 [lark-shared](https://github.com/...) |
| **Playwright** | 小红书口碑验证(内置 vendor) | `pip install -r requirements.txt && playwright install chromium` |
| **requests** | 携程差评抓取(内置 API 调用) | 已含在 requirements.txt |
| **amap-lbs-skill** | 高德驾车路线规划+POI搜索 | `openclaw skills install @lbs-amap/amap-lbs-skill` |

### 开箱即用说明(clone 后)

```bash
# 1. Python 依赖(小红书口碑验证)
pip install -r requirements.txt
playwright install chromium

# 2. 初始化运行时记忆(从 templates/ 拷贝模板, 首次必跑)
python scripts/init_memory.py

# 3. 环境变量
export FLYAI_API_KEY="..."        # 飞猪
export WENDAO_API_KEY="..."       # 携程问道
export AMAP_WEBSERVICE_KEY="..."  # 高德地图(自驾游路线规划)

# 4. 首次用小红书需扫码登录(cookie 存 ~/.xiaohongshu/cookies.json)
python scripts/xhs.py qrcode --show
python scripts/xhs.py check-login   # 验证登录态

# 5. 编辑个人偏好(可选)
# 按需填写 ~/.trip-scout/MEMORY.md 的会员权益和出发城市
```

小红书能力已 vendored 进 `vendor/xiaohongshu/`(源自 [DeliciousBuding/xiaohongshu-skill](https://github.com/DeliciousBuding/xiaohongshu-skill), MIT), 仅内化酒店口碑验证所需核心模块(client/login/search/feed), **不依赖外部 skill 路径**。通过 `scripts/xhs.py` 入口调用:
```bash
python scripts/xhs.py search "那拉提英迪格 避雷" --limit 10     # 酒店口碑
python scripts/xhs.py search "川西小环线 自驾游路线" --limit 20  # 路线搜索
python scripts/xhs.py feed <feed_id> <xsec_token>
```

高德地图能力使用已安装的 [amap-lbs-skill](https://clawhub.ai/lbs-amap/skills/amap-lbs-skill):
```bash
# 驾车路线规划(里程/时长/过路费)
node ~/.openclaw/skills/amap-lbs-skill/scripts/route-planning.js \
  --type=driving --origin=lng,lat --destination=lng,lat

# 带途经点
node ~/.openclaw/skills/amap-lbs-skill/scripts/route-planning.js \
  --type=driving --origin=lng,lat --destination=lng,lat --waypoints=lng,lat;lng,lat

# POI搜索(周边城镇/景点)
node ~/.openclaw/skills/amap-lbs-skill/scripts/poi-search.js \
  --keywords=镇 --city=丹巴 --offset=10

# 周边搜索(酒店联动调整)
node ~/.openclaw/skills/amap-lbs-skill/scripts/poi-search.js \
  --keywords=镇 --location=lng,lat --radius=100000
```

## Resources

- `references/flight-search.md` — 航班搜索工作流
- `references/hotel-search.md` — 酒店搜索 + 筛选工作流
- `references/hotel-trust-system.md` — 信任体系 + 加盟识别 + 黑榜
- `references/review-analysis.md` — 差评分析引擎
- `references/xhs-hotel-research.md` — 小红书酒店口碑交叉验证
- `references/xhs-route-search.md` — 小红书自驾游路线搜索（路线专用搜索词+筛选标准）
- `references/xhs-research.md` — 小红书调研工作流（OpenCLI + Chrome CDP方案）
- `references/trip-planning.md` — 通用行程规划方法论
- `references/road-trip-planning.md` — 自驾游增量方法论（驾驶节奏/路线三角/车辆规划/路况风险）
- `references/dianping-research.md` — 大众点评调研工作流
- `references/memory-format.md` — 记忆格式 + 自进化规则
- `vendor/xiaohongshu/` — 内置小红书 Playwright 客户端(MIT, 源自 DeliciousBuding/xiaohongshu-skill)
- `scripts/xhs.py` — 小红书口碑验证+路线搜索入口
- `scripts/ctrip_reviews.py` — 携程酒店差评抓取分析
- `scripts/init_memory.py` — 首次运行初始化运行时记忆
- `assets/template.html` — 行程地图模板(Leaflet + Apple Design System, 支持 road-trip 路线段)
- `templates/MEMORY.md` + `templates/blacklist.md` — 运行时记忆模板
