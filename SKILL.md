---
name: trip-scout
description: >
  个人/家庭自驾游规划和机酒搜索助手。飞猪+携程双平台搜索，智能酒店筛选（品牌信任梯度、
  加盟/直营识别、差评分析、黑榜），自进化学习。用于搜索机票、酒店，比价，
  酒店推荐，查看历史入住记录。触发词：搜机票、搜酒店、找酒店、订机票、
  机酒搜索、travel search、flight search、hotel search。
---

# Trip Scout

个人/家庭自驾游规划和机酒搜索助手。核心能力：**双平台搜索 + 智能酒店筛选 + 自进化学习**。

## Shared Memory

## Shared Memory

**首次运行必须先初始化运行时记忆**(确保 `~/.trip-scout/` 目录和模板文件存在):

```bash
python scripts/init_memory.py
```

该脚本:首次运行从 `templates/` 拷贝 MEMORY.md/blacklist.md 到 `~/.trip-scout/`; 已存在则跳过(不覆盖用户数据)。新用户 clone 后跑一次即可开箱可用。

初始化后读取 `~/.trip-scout/MEMORY.md`。用于：
- 用户偏好（出发城市、品牌梯度、价格区间、会员权益）
- 入住历史（已住酒店、体验评分、品牌信任变化）
- 学到的规则（加盟识别、差评分类、黑名单）

首次使用需编辑 MEMORY.md 填入个人会员权益和偏好（携程/万豪/亚朵/华住会等级、出发城市）。

每次完成搜索/入住反馈后更新该文件。黑名单酒店写入 `~/.trip-scout/blacklist.md`。

详细格式见 `references/memory-format.md`。

## Phase 1: 航班搜索

读 `references/flight-search.md`。

核心流程：
1. 从用户输入提取：出发城市、目的地、日期、人数
2. 并行调用飞猪 `flyai search-flight` + 携程问道 API
3. 合并结果，按价格排序
4. 给出明确建议（不是罗列全部）
5. 更新搜索历史

## Phase 2: 酒店搜索与智能筛选

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

## Phase 3: 信任体系维护

读 `references/hotel-trust-system.md` + `references/review-analysis.md`。

触发时机：
- 用户说"再也不住" → 拉黑 + 降品牌信任
- 用户说"这个不错" → 升品牌信任
- 发现加盟翻牌 → 标记风险 + 检查同品牌其他店
- 入住后反馈 → 更新 MEMORY.md

## Phase 4: 飞书参考（可选）

用户提到"参考之前的攻略"时触发。

读取飞书文件夹「旅行攻略」：
```bash
lark-cli drive +inspect --url 'https://my.feishu.cn/drive/folder/AhBBfyHLulWjdwdR3ZKcqMHBngd'
```

提取历史行程中的酒店评价、目的地信息、路线规划作为搜索参考。

## 输出格式规范

### 航班搜索输出

```markdown
## ✈️ [出发] → [目的地] | [日期]

| 平台 | 航班 | 时间 | 价格 | 备注 |
|------|------|------|------|------|
| 飞猪 | XX1234 | 08:00-10:30 | ¥680 | 直飞 |
| 携程 | XX1234 | 08:00-10:30 | ¥720 | 直飞, 可选座 |

### 💡 建议
[一句话明确推荐]
```

### 酒店搜索输出

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

## Dependencies

| 工具 | 用途 | 安装 |
|------|------|------|
| `flyai-cli` | 飞猪搜索 | `npm i -g @fly-ai/flyai-cli` |
| 问道 API | 携程搜索 | curl + JSON(无需安装) |
| `lark-cli` | 飞书读取 | 见 [lark-shared](https://github.com/...) |
| **Playwright** | 小红书口碑验证(内置 vendor) | `pip install -r requirements.txt && playwright install chromium` |
| **requests** | 携程差评抓取(内置 API 调用) | 已含在 requirements.txt |

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

# 4. 首次用小红书需扫码登录(cookie 存 ~/.xiaohongshu/cookies.json)
python scripts/xhs.py qrcode --show
python scripts/xhs.py check-login   # 验证登录态

# 5. 编辑个人偏好(可选)
# 按需填写 ~/.trip-scout/MEMORY.md 的会员权益和出发城市
```

小红书能力已 vendored 进 `vendor/xiaohongshu/`(源自 [DeliciousBuding/xiaohongshu-skill](https://github.com/DeliciousBuding/xiaohongshu-skill), MIT), 仅内化酒店口碑验证所需核心模块(client/login/search/feed), **不依赖外部 skill 路径**。通过 `scripts/xhs.py` 入口调用:
```bash
python scripts/xhs.py search "那拉提英迪格 避雷" --limit 10
python scripts/xhs.py feed <feed_id> <xsec_token>
```

## Resources

- `references/flight-search.md` — 航班搜索工作流
- `references/hotel-search.md` — 酒店搜索 + 筛选工作流
- `references/hotel-trust-system.md` — 信任体系 + 加盟识别 + 黑榜
- `references/review-analysis.md` — 差评分析引擎
- `references/xhs-hotel-research.md` — 小红书口碑交叉验证(过滤软文、反哺攻略)
- `references/memory-format.md` — 记忆格式 + 自进化规则
- `vendor/xiaohongshu/` — 内置小红书 Playwright 客户端(MIT, 源自 DeliciousBuding/xiaohongshu-skill)
- `scripts/xhs.py` — 小红书口碑验证入口(check-login/qrcode/search/feed)
- `scripts/ctrip_reviews.py` — 携程酒店差评抓取分析(API调用, 近12月差评分类量化)
- `scripts/init_memory.py` — 首次运行初始化运行时记忆
- `templates/MEMORY.md` + `templates/blacklist.md` — 运行时记忆模板(含内置规则, 个人数据留空)
