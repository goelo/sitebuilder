# Roblox 游戏趋势监控

通过 [Rolimons API](https://rolimons.com/) 采集 Roblox 游戏在线人数数据，自动分析趋势并生成**建站候选清单**。

用于在建站 SOP 的 Step 1 之前，先用数据筛选出值得做的游戏。

## 工具

| 脚本 | 用途 | 运行频率 |
|------|------|----------|
| `scripts/collect.py` | 采集 Rolimons 游戏在线数据，写入 SQLite | 每小时 |
| `scripts/trend-analysis.py` | 分析趋势，产出报告 + 建站清单 | 每天一次 |

## 零依赖

两个脚本**只用 Python 标准库**（`sqlite3`、`urllib`、`json`、`pathlib`），不需要 `pip install` 任何东西。

```
python3 --version   # 需要 Python 3.10+
```

## 快速开始

### 1. 采集数据

```bash
cd roblox-monitor
python3 scripts/collect.py
```

首次运行会自动创建数据库 `data/roblox-trends.db`。

输出示例：
```
[2026-03-27T15:00:00Z] 开始采集...
[2026-03-27T15:00:01Z] 获取到 8034 个游戏
[2026-03-27T15:00:02Z] ✅ 写入 7923 条快照（新游戏 50，变化 120，跳过 7863）
[2026-03-27T15:00:02Z] 📊 数据库: 7923 条快照, 8034 个游戏
```

### 2. 生成趋势报告

采集至少 24 小时数据后，运行分析：

```bash
python3 scripts/trend-analysis.py
```

产出两个文件：
- `data/reports/trend-2026-03-27.md` — 可读的 Markdown 报告
- `data/reports/buildlist-2026-03-27.json` — 结构化建站清单

### 3. 定时运行（推荐）

用 crontab 把采集设成每小时自动跑：

```bash
crontab -e
```

添加：
```
# 每小时第5分钟采集
5 * * * * cd /path/to/roblox-monitor && python3 scripts/collect.py >> data/collect.log 2>&1

# 每天早上6点生成趋势报告
0 6 * * * cd /path/to/roblox-monitor && python3 scripts/trend-analysis.py >> data/analysis.log 2>&1
```

## 目录结构

```
roblox-monitor/
├── README.md
├── scripts/
│   ├── collect.py           # 数据采集
│   └── trend-analysis.py    # 趋势分析
└── data/                    # 运行后自动创建
    ├── roblox-trends.db     # SQLite 数据库
    └── reports/
        ├── trend-YYYY-MM-DD.md       # 日报
        └── buildlist-YYYY-MM-DD.json # 建站清单
```

## 数据库结构

### `snapshots` — 在线人数快照

| 列 | 类型 | 说明 |
|----|------|------|
| `game_id` | TEXT | Rolimons 游戏 ID |
| `name` | TEXT | 游戏名 |
| `players` | INTEGER | 在线人数 |
| `timestamp` | TEXT | 采集时间 (UTC ISO-8601) |

### `first_seen` — 游戏首次出现时间

| 列 | 类型 | 说明 |
|----|------|------|
| `game_id` | TEXT (PK) | Rolimons 游戏 ID |
| `name` | TEXT | 游戏名 |
| `first_date` | TEXT | 首次采集日期 (YYYY-MM-DD) |

## 采集逻辑

`collect.py` 并不是每次都全量写入，而是做 diff：

1. 拉取 Rolimons API 全量游戏列表
2. 对比每个游戏的上次快照人数
3. **只有人数变化超过 5% 时才写入新快照**
4. 新游戏首次出现时直接写入

这样数据库不会无脑膨胀，同时保留所有有意义的变化。

## 建站清单筛选逻辑

`trend-analysis.py` 会把游戏分成 4 个桶：

| 桶 | 条件 | 含义 |
|----|------|------|
| 🚀 爆发 | vs72h ≥ 50% 或 vs7d ≥ 80%，且 24h 均值 ≥ 3000 | 正在起飞的大盘 |
| 📈 小盘起飞 | vs72h ≥ 20% 或 vs7d ≥ 30%，且 500 ≤ 24h 均值 < 30000 | 小盘有爆发迹象 |
| 🌤 大盘回暖 | 24h 均值 ≥ 30000，且 vs72h 或 vs7d ≥ 10% | 大盘回升 |
| 🆕 新游戏 | 首次出现 ≤ 14 天，且 24h 均值 ≥ 200 或峰值 ≥ 1000 | 值得关注的新盘 |

最终按分数排序，取 Top 10 作为**建站候选清单**。

评分公式：`score = size(0~5) + growth`，其中：
- `size = min(avg_24h / 20000, 5)` — 盘子越大分越高，上限 5
- `growth = max(vs72h, vs7d) / 10` — 增速越高分越高

## 报告示例

```markdown
# Roblox 趋势报告 | 2026-03-27 (UTC)

## 🎯 今日建站清单 Top 10

1. **Example Game** 🚀 爆发 ⭐8.5
   👥 24h均值: 45,230 | 峰值: 52,100
   📊 vs72h: +65.2% | vs7d: +120.3%

2. **Another Game** 📈 上升 🆕 新7d ⭐6.2
   👥 24h均值: 3,450 | 峰值: 8,200
   📊 vs72h: +42.1% | vs7d: +85.6%
```

## 与建站 SOP 的关系

这套工具产出的 `buildlist-YYYY-MM-DD.json` 可以直接喂给建站 SOP 的 Step 1：

```
数据采集 → 建站清单 → Step1 游戏研究 → Step2 关键词 → ... → Step8 部署
```

## 注意事项

- Rolimons API 是非官方的，可能随时变更或限流
- 数据库会随时间增长，建议定期清理旧快照（保留最近 30 天即可）
- `collect.py` 默认全天候采集，不做时间窗口限制
