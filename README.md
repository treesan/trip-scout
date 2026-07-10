# Trip Scout 🧭

> 个人 / 家庭机酒搜索与自驾游行程规划助手 — 双场景驱动：机酒搜索 + 自驾游行程规划

Trip Scout 是一个多平台 AI Skill（Claude Code / OpenClaw），帮你搜机票、选酒店、避雷加盟翻牌、规划自驾行程，并从每次旅行中学习你的偏好。

## ✨ 特性

### 场景一：机酒搜索

- **双平台搜索** — 飞猪 + 携程问道并行比价，给明确建议而非罗列
- **酒店信任体系** — 品牌信任梯度、加盟/直营识别、差评分类（成长性 vs 本质性）、黑榜
- **小红书交叉验证** — TOP3 酒店真实口碑校准，过滤软文、反哺避雷
- **携程差评量化** — 内置 API 抓取近 12 月差评并分类量化

### 场景二：自驾游行程规划

- **小红书路线推荐** — 搜索经典自驾游路线，结合用户画像亲子友好筛选
- **酒店联动调整** — 住宿点无好酒店时自动搜索周边替代，路线随酒店调整
- **高德路线校正** — 驾车里程/时长/过路费精确数据，亲子驾驶节奏校验
- **行程地图生成** — Leaflet 移动端优先地图，含路线段标注（里程/时长/费用/路况）
- **飞书攻略生成** — 全自动创建飞书文档，含行程总览表和酒店住后评价列
- **灵活行程** — 输出参考行程而非脚本，旅途中天气/疲劳/心情随时可调整

### 自进化

- **记忆体系** — 记录偏好 / 入住历史 / 学到的规则，越用越懂你
- **酒店住后评价闭环** — 行程结束后评价反哺知识库，为下次选酒店参考
- **跨行程积累** — 品牌信任、避雷规则、美食偏好持续沉淀

## 📦 安装

### Claude Code

克隆到 Claude Code 的 skills 目录（或 symlink 过去）：

```bash
git clone https://github.com/treesan/trip-scout.git ~/.claude/skills/trip-scout
cd ~/.claude/skills/trip-scout

# 1. Python 依赖(携程差评/价格抓取+小红书API+通用)
pip install -r requirements.txt
playwright install chromium   # 仅携程价格抓取需要(差评用移动端REST API,无需浏览器)
cd vendor/xhs_api && npm install && cd ../..  # 小红书签名JS的Node.js依赖

# 2. 初始化运行时记忆(从 templates/ 拷贝模板,首次必跑)
python scripts/init_memory.py

# 3. 环境变量
export FLYAI_API_KEY="..."          # 飞猪
export WENDAO_API_KEY="..."         # 携程问道
export AMAP_WEBSERVICE_KEY="..."    # 高德地图(自驾游路线规划)

# 4. 首次用小红书需扫码登录(cookie 存 ~/.xiaohongshu/cookies.json)
python scripts/xhs.py qrcode
python scripts/xhs.py check-login
```

### OpenClaw

```bash
# 方式一: symlink 到 OpenClaw skills 目录(开发推荐)
ln -s /path/to/trip-scout ~/.openclaw/skills/trip-scout

# 方式二: 从 ClawHub 安装(发布后可用)
# 在 OpenClaw 中搜索 trip-scout 安装
```

安装后同上初始化 Python 依赖和运行时记忆。高德地图能力使用已安装的 [amap-lbs-skill](https://clawhub.ai/lbs-amap/skills/amap-lbs-skill)。

## 🚀 使用

直接对 AI 说自然语言即可，系统自动识别场景：

**机酒搜索**（触发词：搜机票、搜酒店、找酒店、订机票、机酒搜索）：

- "帮我搜 7/15 北京到伊宁的机票，2 人"
- "那拉提 7/20-7/22 找个亲子友好的酒店，预算 800/晚"
- "奎屯亚朵是加盟还是直营？查下差评"

**自驾游行程规划**（触发词：自驾游、行程规划、路线推荐、road trip）：

- "中秋节3天川西小环线自驾游路线推荐"
- "下个周末两天推荐成都周边亲子度假游"
- "2026.9.25-10.7 成都出发新疆自驾游路线推荐"
- "帮我规划伊犁 7 天自驾行程，2 大 1 小，偏好自然风光"

## 📁 结构

```
SKILL.md              # Skill 入口与场景路由
references/
  flight-search.md       # 航班搜索工作流
  hotel-search.md        # 酒店搜索 + 筛选工作流
  hotel-trust-system.md  # 信任体系 + 加盟识别
  review-analysis.md     # 差评分析引擎
  xhs-hotel-research.md  # 小红书酒店口碑验证
  xhs-route-search.md    # 小红书路线搜索（自驾游专用）
  trip-planning.md       # 通用行程规划方法论
  road-trip-planning.md  # 自驾游增量方法论
  dianping-research.md   # 大众点评调研工作流
  memory-format.md       # 记忆格式 + 自进化规则
scripts/
  init_memory.py         # 首次运行初始化运行时记忆
  xhs.py                 # 小红书口碑验证+路线搜索入口
  ctrip_reviews.py       # 携程差评抓取分析
  ctrip_prices.py        # 携程酒店价格抓取
assets/
  template.html          # 行程地图模板(Leaflet + Apple Design, 支持road-trip)
templates/               # 运行时记忆模板(MEMORY.md / blacklist.md)
vendor/xhs_api/          # 内置小红书纯API客户端(MIT, 源自 cv-cat/Spider_XHS, 逆向签名算法)
vendor/ctrip/            # 内置携程Playwright+API双轨客户端
```

运行时数据存放在 `~/.trip-scout/`（首次 `init_memory.py` 自动创建），不入库。

## 🙏 致谢

- [cv-cat/Spider_XHS](https://github.com/cv-cat/Spider_XHS) — 小红书纯 HTTP API 客户端（MIT，逆向签名算法，已内化核心模块至 vendor/xhs_api/）
- [hiyeshu/trip-map-builder](https://github.com/hiyeshu/trip-map-builder)  — 旅行行程规划技能：规划 → 小红书调研 → 交互式地图页面

## 📄 License

MIT — 见 [LICENSE](LICENSE)
