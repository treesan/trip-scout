# 大众点评调研工作流 (OpenCLI)

## 前提

大众点评用于餐厅硬信号：口味、排队、踩雷、价格、区域和是否值得。小红书只补氛围、近期体验、拍照和软性提醒。

OpenCLI 已提供大众点评 browser adapter，目标站点是 `www.dianping.com`。

## 环境要求

- Chrome 已登录 `dianping.com`
- 已安装 OpenCLI Browser Bridge 扩展
- 优先使用 PC 站；移动站对非移动 UA 限制较多

## 搜索餐厅

围绕当天主区域搜索，不搜泛词。

```bash
opencli dianping search "银座 午餐" --city 东京 --limit 5 -f json
opencli dianping search "有乐町 晚餐" --city 东京 --limit 5 -f json
opencli dianping search "新宿 居酒屋" --city 东京 --limit 5 -f json
```

命令格式：

```bash
opencli dianping search "<keyword>" --city <name-or-id> --limit <n> -f json
```

`--city` 可用中文、拼音或大众点评 cityId；省略时使用当前 cookie 里的城市。

## 查看店铺详情

搜索结果里的 `shop_id` 可以继续查详情。

```bash
opencli dianping shop <shop_id> -f json
opencli dianping detail <shop_id> -f json
```

也可以传完整店铺 URL：

```bash
opencli dianping shop "https://www.dianping.com/shop/<shop_id>"
```

## 判断标准

优先看：

- `rating`：基础稳定性
- `reviews`：评价量，太少说明信号弱
- `price`：是否符合预算
- `cuisine`：是否适合当前这顿饭
- `district`：是否落在当天区域
- 评价关键词：排队、踩雷、服务、游客店、性价比、是否值得专门去

不要为了高分店扭曲路线。餐厅默认是当天区域里的补给点，只有预约餐、强目的餐、用户明确指定的店，才允许成为路线锚点。

## 写回格式

每顿饭只保留 2-3 个候选。

```md
午餐区域：银座 / 有乐町
主推：店名 A
- 大众点评：评分稳定，评价量够，适合午餐，不需要专门绕路
- 小红书：近期反馈氛围好，拍照友好

备选：店名 B
- 大众点评：离地铁近，排队风险低
- 小红书：更像工作日简餐
```

## 常见坑

- 只按评分选店，不看它是否在当天区域
- 为了一家店反向规划半天路线
- 把小红书种草当成餐厅硬口碑
- 忽略排队、预约和营业时间
- 搜索词太泛，得到一堆游客店

## 官方参考

- https://github.com/jackwener/OpenCLI/blob/main/docs/adapters/browser/dianping.md
