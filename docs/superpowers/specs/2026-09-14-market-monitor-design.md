# 大盘监测系统 Design Spec
**Date:** 2026-09-14  
**Status:** ✅ Final — 三轮专家审阅全部通过  
**Targets:** SPY, QQQ (Nasdaq)

---

## 1. 目标

盘前跑一次综合分析，盘中实时监测，透过大单异动、筹码分布、大额期权异动、新闻情绪四个维度，由 Claude AI 解读并给出当日高低点预测区间，结果呈现在 Netlify Dashboard 并推送至 Discord。

---

## 2. 架构概览

```
数据源层
  Polygon WebSocket  →  盘中实时 tick（SPY/QQQ）+ 期权逐笔成交
  Polygon REST       →  期权链快照、大单、日线 K 线
  Polygon News API   →  财经新闻头条
  Polygon REST       →  VIX/VVIX 实时报价
  ES/NQ 期货         →  Polygon REST（开盘前走势）
  NewsAPI            →  财经头条补充（Polygon News 延迟高时备用）
  Reddit (PRAW)      →  r/wallstreetbets + r/stocks 情绪
  X API v2           →  市场情绪关键词（可选，Basic $100/月限额低）
  经济日历           →  Trading Economics / Polygon 日历（数据发布时间点）

后端 (FastAPI · Railway Hobby $5/月)
  block_detector.py  →  股票大单聚合过滤（$20M / $50M 两档）
  options.py         →  期权扫描（✂️ FlowScanner，60–70% 需重写适配 Polygon）
  flow.py            →  异动检测（✂️ FlowScanner）
  chip_profile.py    →  VPOC + VAH/VAL + GEX/Max Pain
  sentiment.py       →  PCR（OI + Volume 分开）+ Reddit + 新闻情绪聚合
  interpreter.py     →  Claude API 解读 → 高低点预测
  call_queue.py      →  双 worker 队列：Whale 专用 worker + 常规 worker
  discord.py         →  Discord webhook 推送
  scheduler.py       →  AsyncIOScheduler 定时任务
  routes.py          →  REST API 供前端 polling（配置 CORS allow_origins）
  redis_cache.py     →  Redis 原子写入快照（Railway Redis plugin，独立 service）

前端 (Next.js · Netlify)
  静态导出，每 60 秒 polling 后端 API
  显示快照 written_at 时间戳，过期超过 2 分钟显示警告
```

---

## 3. 数据流

```
9:15 ET（开盘前）
  Polygon REST → 隔夜期权链快照（分页拉取）、日线 Volume Profile
  Polygon REST → ES/NQ 期货隔夜走势、VIX/VVIX 水平
  经济日历 → 今日数据发布时间点（CPI/NFP/FOMC 等）
  Reddit/X → 情绪快照；Polygon News → 隔夜头条
  Whale worker → Claude API → 生成早盘报告（区间预测 + 解读）
  Discord → 推送早盘报告

9:30–16:00 ET（盘中）
  Polygon WebSocket → 实时 tick 流（断线时 exponential backoff 重连）
  每分钟 → block_detector（聚合窗口） / chip_profile / PCR 更新
  每 10 分钟 → options 期权链增量更新（避免 rate limit）
  快照原子写入 Redis（含 written_at 时间戳）
  Whale 阈值触发 → Whale worker → Claude API → Discord 即时推送
                   （同一标的 5 分钟冷却）
  每小时整点（10:00–15:00 ET）→ 常规 worker → Claude API → 简报 → Discord
  前端每 60 秒 polling /api/snapshot → Dashboard 刷新

16:00 ET（收盘）
  Whale worker → Claude API → 收盘总结（优先级最高）
  Discord → 推送日报
  Redis 快照标记为历史（供次日开盘前参考）
```

---

## 4. 各模块设计

### 4.1 大单检测 `block_detector.py`
- 数据源：Polygon WebSocket `T.*`（逐笔成交实时流）；REST `/v3/trades` 补充
- **聚合逻辑**：单笔 tick 通常远不到 $20M，需在 **30 秒滑动窗口**内聚合同方向（买/卖）同价位的连续成交，累计 notional 达到阈值才触发；同时需去重（相同 exchange + timestamp 的重复 tick 过滤）
- **方向判定**：使用 Polygon `T.*` 的 `conditions` 字段中的 aggressor side 标记（买方主导 = 流入，卖方主导 = 流出）；无 aggressor 标记时降级为 tick rule（成交价 ≥ 上一笔 → 买方，反之 → 卖方）
- 阈值（symbol 参数化）：
  - 提醒档：聚合 notional ≥ $20M
  - Whale 档：聚合 notional ≥ $50M
- 输出：`{symbol, size, price, notional, side, window_start, window_end}`
- Discord 只推送 Whale 档；Dashboard 两档均显示

### 4.2 期权扫描 `options.py` + `flow.py`
- 数据源：`/v3/snapshot/options/{underlyingAsset}`（含 OI、IV、Greeks）
- **✅ 套餐确认**：Developer 套餐已包含完整 Greeks（delta/gamma/theta/vega），GEX 计算直接使用真实 Gamma，无需降级估算
- **拉取策略**：每 **10 分钟**全量分页拉取（`limit=250`，SPY 约 20–60 次请求），而非每分钟，避免耗尽 rate limit
- 基础逻辑从 FlowScanner 移植，预估 60–70% 需重写以适配 Polygon 字段结构及 condition codes
- 识别类型：Sweep（快速扫单）、Block（大宗期权）；额外标注 OTM 深虚值大单
- 阈值（symbol 参数化）：
  - 提醒档：Premium ≥ $500K
  - Whale 档：Premium ≥ $1M
- 输出：`{symbol, expiry, strike, type, premium, flow_type, iv, otm_pct, timestamp}`

### 4.3 筹码分布 `chip_profile.py`

**Volume Profile / VPOC + VAH/VAL**
- 历史数据：启动时用 Polygon REST `/v2/aggs/ticker/{ticker}/range/1/day/` 拉取过去 20 天日线，缓存到 Redis
- 盘中实时：WebSocket tick 流累积当日分钟成交量，叠加历史数据
- 按价格区间（**$0.10 固定 bucket**，非百分比）聚合成交量；SPY 日内 tick 量级大，固定 $0.10 精度足够且不产生歧义，计算：
  - **VPOC**：最高成交量价位
  - **VAH / VAL**（标准 Market Profile 定义）：以 VPOC 为中心**双向扩展**，每次选择上方或下方中成交量较大的 bucket 加入，直到累积成交量覆盖总量的 **70%**；VAH = 区域上边界，VAL = 区域下边界
  - 价格在 VPOC 上方 → 标注多头控制；下方 → 标注空头控制

**GEX / Max Pain**
- GEX 正确公式：`Gamma × OI × 合约乘数(100) × 现价`
  - GEX > 0（dealer long gamma）→ 价格均值回归，波动收敛
  - GEX < 0（dealer short gamma）→ 趋势加速，波动放大
  - **绝对值门槛**：`|GEX_net| < 5亿` 时视为中性区，不触发 dealer gamma 解读（避免接近零时的方向噪音）
- Max Pain = 使当前到期日所有期权卖方总损失最小的行权价（主要影响到期日收盘，日内参考权重低）
- 输出：`{symbol, vpoc, vah, val, vpoc_bias, max_pain, gex_net, gex_signal, gex_levels: [{price, gex}]}`

### 4.4 情绪聚合 `sentiment.py`

**Put/Call Ratio (PCR) — 分两种，阈值不同**

| 类型 | 计算方式 | 偏多信号 | 偏空信号 | 用途 |
|------|---------|---------|---------|------|
| OI PCR | Put OI / Call OI（存量） | < 0.7 | > 1.3 | 反映累积仓位偏向（慢信号）|
| Volume PCR | Put Volume / Call Volume（当日流量）| < 0.8 | > 1.2 | 反映当日情绪（快信号）|

- **Reddit**：PRAW 拉取 r/wallstreetbets + r/stocks 热门帖，VADER 情绪打分
- **X API v2**：可选，若有订阅则加入；无则跳过
- **新闻**：Polygon News API 主力；NewsAPI 作备用
- 输出：`{oi_pcr, oi_pcr_signal, vol_pcr, vol_pcr_signal, reddit_bullish_pct, top_headlines: [...]}`

### 4.5 AI 解读 `interpreter.py`
- 模型：`claude-sonnet-4-6`（system prompt 使用 prompt caching）
- 所有调用经由 `call_queue.py` 双 worker 队列分发
- 触发时机：9:15 开盘前 / 每小时整点 / 16:00 收盘 / Whale 档异动（5 分钟冷却）
- User prompt 传入数据：大单净流、VPOC/VAH/VAL、GEX 方向与信号、期权异动摘要、OI PCR + Volume PCR、**VIX 水平 + VVIX/VIX 比值**（比值高 → 恐慌为短期脉冲）、ES/NQ 期货（仅早盘）、新闻头条、经济日历（仅早盘）
- 强制输出结构：
  ```json
  {
    "support": 576,
    "resistance": 588,
    "bias": "bullish",
    "key_level": 583,
    "trigger_long": "9:45 前守住 578 VPOC 且大单净流为正",
    "trigger_short": "跌破 578 且 GEX 转负",
    "confidence": "medium",
    "summary": "...(100字以内)"
  }
  ```

### 4.6 Discord 推送 `discord.py`
- 使用 Discord webhook（无需 bot token）
- 四种消息类型：
  1. **早盘报告**（9:15）：完整分析 + 区间预测 + 触发条件 + 今日经济日历
  2. **即时异动**：Whale 档大单/期权触发，embed 卡片（同一标的 5 分钟冷却）
  3. **每小时简报**：数据快照 + VIX + OI/Volume PCR + AI 一句话更新
  4. **收盘总结**（16:00）：全天回顾 + 预测准确度评估

### 4.7 稳定性设计

**WebSocket 断线重连 `polygon_ws.py`**
- 心跳检测：30 秒无数据则触发重连
- Exponential backoff：1s → 2s → 4s → 8s → 最大 60s
- 重连后从 Redis 快照恢复上下文，不丢失已累积数据

**Redis 原子写入 `redis_cache.py`**
- 先写临时 key `snapshot:{symbol}:tmp`，写完后 `RENAME` 至 `snapshot:{symbol}:latest`（原子操作，防止脏读）
- payload 包含 `written_at` ISO 时间戳
- TTL 10 分钟（写入频率每分钟，给足缓冲）
- Railway Redis 作**独立 service**，与 FastAPI 主 service 分离

**Claude API 双 Worker 队列 `call_queue.py`**
- **Whale worker**（1 个）：专处理 Whale 异动 + 开盘报告 + 收盘总结，maxsize=10
- **常规 worker**（1 个）：处理每小时简报，maxsize=10
- Whale worker 满载时丢弃多余 Whale 任务（保留最新），常规 worker 满载时丢弃简报
- 最坏延迟：Whale worker 串行 10 任务 × 8s = 80s（可接受，极端情况）

**调度器 `scheduler.py`**
- 使用 `AsyncIOScheduler`，与 FastAPI event loop 兼容
- startup event 重新注册所有任务，确保 Railway 重启后恢复

**CORS 配置 `main.py`**
- FastAPI 需显式配置 `CORSMiddleware`：
  ```python
  allow_origins=["https://*.netlify.app", "https://your-domain.com"]
  ```

**Symbol 参数化**
- 所有模块接受 `symbols: list[str]` 参数，当前默认 `["SPY", "QQQ"]`
- 未来加个股只需改配置，无需修改核心逻辑

---

## 5. 前端 Dashboard（Next.js → Netlify）

### 页面结构
- 顶部导航：SPY / QQQ 实时价 + 涨跌 + 时间 + LIVE 状态 + 快照时间戳（过期 > 2 分钟显示橙色警告）
- AI 解读横幅：支撑 / 压力 / 触发条件 / 方向偏向 / 置信度
- 双卡片行：SPY 和 QQQ（报价 + 净流 + VPOC + GEX 方向）
- 辅助指标行：VIX + VVIX/VIX 比值 + OI PCR + Volume PCR + 今日经济日历事件
- 三栏：期权异动列表（含 OTM 标注）| 筹码分布 VPOC/VAH/VAL | 情绪 & 新闻
- 底部：大单净流时间线（绿=净流入，红=净流出）

### 刷新策略
- 前端每 60 秒 polling `/api/snapshot`
- 后端宕机时返回 Redis 上一次快照
- 显示 `written_at` 时间戳，超过 2 分钟未更新显示"数据可能延迟"警告

---

## 6. 阈值汇总（可配置）

| 类型 | 提醒档 | Whale 档 | 备注 |
|------|--------|---------|------|
| 股票大单（聚合）| $20M | $50M | 30 秒窗口聚合同向成交 |
| 期权 Premium | $500K | $1M | 行业主流阈值 |
| OI PCR 偏多 | < 0.7 | — | 存量仓位信号 |
| OI PCR 偏空 | > 1.3 | — | 存量仓位信号 |
| Volume PCR 偏多 | < 0.8 | — | 当日流量情绪 |
| Volume PCR 偏空 | > 1.2 | — | 当日流量情绪 |
| GEX 中性区 | \|GEX_net\| < 5亿 | — | 低于此值不触发 dealer 解读 |

---

## 7. 技术栈

| 层级 | 技术 |
|------|------|
| 后端语言 | Python 3.11 |
| 后端框架 | FastAPI |
| 后端部署 | Railway Hobby（两个 service 各 $5/月，合计约 **$10/月**：FastAPI + Redis）|
| 缓存 / 持久化 | Redis（Railway Redis plugin，独立 service）|
| 调度 | APScheduler（AsyncIOScheduler）|
| 前端框架 | Next.js 14（静态导出）|
| 前端部署 | Netlify |
| 主数据源 | Polygon.io（Stock + Options Developer）|
| 辅助情绪 | Reddit PRAW + X API v2（可选）|
| 新闻备援 | NewsAPI |
| AI 解读 | Claude API（claude-sonnet-4-6）|
| 通知 | Discord Webhook |
| 期权扫描骨架 | FlowScanner（options.py + flow.py，预估 60–70% 重写）|

---

## 8. 不在范围内（Out of Scope）

- 实际下单 / 交易执行
- 个股监测（仅 SPY / QQQ；symbol 参数化已为扩展预留）
- 历史回测
- 移动端 App

---

## 9. 已知风险与注意事项

| 风险 | 影响 | 对策 |
|------|------|------|
| FlowScanner 移植量大 | 工期延误 | 先实现 Polygon 原生版本，再移植 FlowScanner 逻辑 |
| Polygon WebSocket 断线 | 数据丢失 | Exponential backoff 重连 + Redis 快照恢复 |
| Claude API 并发 | 推送延迟 | 双 worker 队列，Whale 独立通道 |
| X API v2 限额不足 | 情绪数据缺失 | X 设为可选，无订阅跳过不报错 |
| Railway 重启丢任务 | 漏推简报 | startup event 重新注册 APScheduler 任务 |
| Polygon Developer 套餐 Greeks | ✅ 已验证包含 delta/gamma/theta/vega | 直接使用，无需降级 |
| 期权链分页 rate limit | 数据不完整 | 每 10 分钟拉取一次，非每分钟 |
| Redis 脏读 | 前端显示损坏数据 | 原子写入（tmp key → RENAME）|
