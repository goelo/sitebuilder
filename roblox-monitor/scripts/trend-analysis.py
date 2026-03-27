#!/usr/bin/env python3
"""Roblox 趋势分析（SOP Step2）

目标：从 data/roblox-trends.db 里读取 snapshots（Rolimons 在线人数快照），计算
- 24h/72h/7d 均值
- 24h 峰值
- vs72h / vs7d 变化率

产出：
- data/reports/trend-YYYY-MM-DD.md
- data/reports/buildlist-YYYY-MM-DD.json

说明：这是 Step2 的“自动日报版”，不做 Brave/LLM 竞品分析；字段里保留 competitors 等，先留空。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "roblox-trends.db"
REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# “新游戏”窗口：用于从趋势数据里标记“近期才出现的新盘”。
# - ≤7 天：超新（优先验证）
# - ≤14 天：新（仍算新盘）
FRESH_GAME_DAYS = 7
NEW_GAME_DAYS = 14


def _age_days(first_date: str | None, today_utc: str) -> int | None:
    if not first_date:
        return None
    try:
        fd = datetime.strptime(first_date, "%Y-%m-%d").date()
        td = datetime.strptime(today_utc, "%Y-%m-%d").date()
        return (td - fd).days
    except Exception:
        return None


@dataclass
class GameRow:
    game_id: str
    name: str
    avg_24h: int
    avg_72h: int
    avg_7d: int
    peak_24h: int
    first_date: str | None

    def pct_vs72h(self) -> float:
        if self.avg_72h <= 0:
            return 0.0
        return (self.avg_24h - self.avg_72h) / self.avg_72h * 100.0

    def pct_vs7d(self) -> float:
        if self.avg_7d <= 0:
            return 0.0
        return (self.avg_24h - self.avg_7d) / self.avg_7d * 100.0


def _round_int(x):
    return int(round(x)) if x is not None else 0


def load_games(conn: sqlite3.Connection, now_utc: datetime) -> list[GameRow]:
    t24 = (now_utc - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t72 = (now_utc - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t7d = (now_utc - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 取每个 game_id 最新 name，同时计算窗口均值/峰值
    q = f"""
    WITH base AS (
      SELECT game_id,
             MAX(timestamp) AS last_ts
      FROM snapshots
      GROUP BY game_id
    ),
    last_name AS (
      SELECT s.game_id, s.name
      FROM snapshots s
      JOIN base b ON b.game_id = s.game_id AND b.last_ts = s.timestamp
    ),
    w24 AS (
      SELECT game_id, AVG(players) AS avg_24h, MAX(players) AS peak_24h
      FROM snapshots
      WHERE timestamp >= ?
      GROUP BY game_id
    ),
    w72 AS (
      SELECT game_id, AVG(players) AS avg_72h
      FROM snapshots
      WHERE timestamp >= ?
      GROUP BY game_id
    ),
    w7d AS (
      SELECT game_id, AVG(players) AS avg_7d
      FROM snapshots
      WHERE timestamp >= ?
      GROUP BY game_id
    )
    SELECT n.game_id,
           n.name,
           COALESCE(w24.avg_24h, 0) AS avg_24h,
           COALESCE(w72.avg_72h, 0) AS avg_72h,
           COALESCE(w7d.avg_7d, 0) AS avg_7d,
           COALESCE(w24.peak_24h, 0) AS peak_24h,
           fs.first_date
    FROM last_name n
    LEFT JOIN w24 ON w24.game_id = n.game_id
    LEFT JOIN w72 ON w72.game_id = n.game_id
    LEFT JOIN w7d ON w7d.game_id = n.game_id
    LEFT JOIN first_seen fs ON fs.game_id = n.game_id
    WHERE COALESCE(w24.avg_24h, 0) > 0
    ;
    """

    rows = []
    for r in conn.execute(q, (t24, t72, t7d)):
        rows.append(
            GameRow(
                game_id=str(r[0]),
                name=str(r[1]),
                avg_24h=_round_int(r[2]),
                avg_72h=_round_int(r[3]),
                avg_7d=_round_int(r[4]),
                peak_24h=int(r[5]) if r[5] is not None else 0,
                first_date=str(r[6]) if r[6] is not None else None,
            )
        )
    return rows


def classify(g: GameRow, today_utc: str):
    age = _age_days(g.first_date, today_utc)
    is_fresh = age is not None and age <= FRESH_GAME_DAYS
    is_new = age is not None and age <= NEW_GAME_DAYS

    vs72 = g.pct_vs72h()
    vs7d = g.pct_vs7d()

    # 简单规则：先给“爆发”留给高增速/高量级
    if (vs72 >= 50 or vs7d >= 80) and g.avg_24h >= 3000:
        return "爆发", is_new, is_fresh, age

    # 小盘起飞：增速不错但盘子不算大
    if (vs72 >= 20 or vs7d >= 30) and 500 <= g.avg_24h < 30000:
        return "小盘起飞", is_new, is_fresh, age

    # 大盘回暖：盘子大，回升
    if g.avg_24h >= 30000 and (vs72 >= 10 or vs7d >= 10):
        return "大盘回暖", is_new, is_fresh, age

    # 默认：其他上升/平稳不纳入重点
    return "其他", is_new, is_fresh, age


def score(g: GameRow) -> float:
    # 只用数据打分：增速为主，盘子为辅
    vs72 = g.pct_vs72h()
    vs7d = g.pct_vs7d()
    size = min(g.avg_24h / 20000.0, 5.0)  # 0~5
    growth = max(vs72, vs7d) / 10.0       # 10% -> 1
    return round(size + growth, 1)


def qualifies_new_bucket(g: GameRow) -> bool:
    # 新游戏榜不要塞进 24h 只有几十人的噪音词。
    # 给新盘更多曝光，但至少要有一点量或增长信号。
    return g.avg_24h >= 200 or g.peak_24h >= 1000 or max(g.pct_vs72h(), g.pct_vs7d()) >= 20


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    
    # 使用数据库最新时间戳作为基准，而不是当前时间
    cursor = conn.cursor()
    max_ts = cursor.execute("SELECT MAX(timestamp) FROM snapshots").fetchone()[0]
    if not max_ts:
        raise SystemExit("No data in database")
    
    try:
        now_utc = datetime.strptime(max_ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        now_utc = datetime.strptime(max_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    today_utc = now_utc.strftime("%Y-%m-%d")
    
    print(f"📊 Using database latest timestamp as anchor: {max_ts}")
    
    conn.row_factory = sqlite3.Row
    games = load_games(conn, now_utc)
    conn.close()

    buckets = {
        "爆发": [],
        "小盘起飞": [],
        "大盘回暖": [],
        "新游戏": [],
    }

    scored = []
    for g in games:
        bucket, is_new, is_fresh, age = classify(g, today_utc)
        s = score(g)
        scored.append((s, g, bucket, is_new, is_fresh, age))
        if is_new and qualifies_new_bucket(g):
            buckets["新游戏"].append((s, g))
        if bucket in buckets and bucket != "其他":
            buckets[bucket].append((s, g))

    # Top10 建站清单：优先 爆发/小盘起飞/新游戏，再按分数
    candidates = [x for x in scored if x[2] in ("爆发", "小盘起飞", "大盘回暖") or x[3]]
    candidates.sort(key=lambda x: (x[0], x[1].avg_24h), reverse=True)
    top10 = candidates[:10]

    # 输出 buildlist json（字段对齐旧格式，但留空不可得字段）
    buildlist = []
    for s, g, bucket, is_new, is_fresh, age in top10:
        if is_fresh:
            new_tag = " + 新游戏(≤7d)"
        elif is_new:
            new_tag = " + 新游戏(≤14d)"
        else:
            new_tag = ""

        buildlist.append(
            {
                "name": g.name,
                "game_id": g.game_id,
                "avg_24h": g.avg_24h,
                "peak_24h": g.peak_24h,
                "seo_score": None,
                "competition": None,
                "competitors": [],
                "has_codes": None,
                "page_type": None,
                "reason": f"数据驱动候选：{bucket}{new_tag} | vs72h {g.pct_vs72h():+.1f}% | vs7d {g.pct_vs7d():+.1f}%",
            }
        )

    buildlist_path = REPORT_DIR / f"buildlist-{today_utc}.json"
    buildlist_path.write_text(json.dumps(buildlist, ensure_ascii=False, indent=2))

    # 输出 markdown
    def fmt_line(i, s, g: GameRow, bucket, is_new, is_fresh):
        flags = []
        if bucket == "爆发":
            flags.append("🚀 爆发")
        if bucket == "小盘起飞":
            flags.append("📈 上升")
        if bucket == "大盘回暖":
            flags.append("🌤 回暖")
        if is_fresh:
            flags.append("🆕 新7d")
        elif is_new:
            flags.append("🆕 新14d")
        flag_txt = " ".join(flags) if flags else ""
        return (
            f"{i}. **{g.name}** {flag_txt} ⭐{s}\n"
            f"   👥 24h均值: {g.avg_24h:,} | 峰值: {g.peak_24h:,}\n"
            f"   📊 vs72h: {g.pct_vs72h():+.1f}% | vs7d: {g.pct_vs7d():+.1f}%\n"
        )

    lines = []
    lines.append(f"# Roblox 趋势报告 | {today_utc} (UTC)\n")
    lines.append("## 🎯 今日建站清单 Top 10\n")
    for idx, (s, g, bucket, is_new, is_fresh, age) in enumerate(top10, 1):
        lines.append(fmt_line(idx, s, g, bucket, is_new, is_fresh))

    for section in ["爆发", "小盘起飞", "大盘回暖", "新游戏"]:
        items = buckets[section]
        items.sort(key=lambda x: (x[0], x[1].avg_24h), reverse=True)
        if not items:
            continue
        title = {
            "爆发": "## 🚀 爆发期",
            "小盘起飞": "## 📈 小盘起飞",
            "大盘回暖": "## 🌤 大盘回暖",
            "新游戏": "## 🆕 新游戏",
        }[section]
        lines.append("\n" + title + "\n")
        # 控制输出规模
        limit = 50 if section == "爆发" else 10 if section == "小盘起飞" else 5 if section == "大盘回暖" else 10 if section == "新游戏" else 10
        for i, (s, g) in enumerate(items[:limit], 1):
            if section == "爆发":
                lines.append(
                    f"{i}. {g.name} — 24h均值 {g.avg_24h:,} | 24h峰值 {g.peak_24h:,} | vs72h {g.pct_vs72h():+.1f}% | vs7d {g.pct_vs7d():+.1f}% | ⭐{s}"
                )
            elif section == "小盘起飞":
                lines.append(
                    f"{i}. {g.name} — 24h均值 {g.avg_24h:,} | 24h峰值 {g.peak_24h:,} | vs72h {g.pct_vs72h():+.1f}%"
                )
            elif section == "大盘回暖":
                lines.append(
                    f"{i}. {g.name} — 24h均值 {g.avg_24h:,} | vs72h {g.pct_vs72h():+.1f}%"
                )
            elif section == "新游戏":
                first = g.first_date or "未知"
                lines.append(f"{i}. {g.name} — 24h均值 {g.avg_24h:,} | 首次出现 {first}")
            else:
                lines.append(
                    f"{i}. {g.name} — 24h均值 {g.avg_24h:,} | vs72h {g.pct_vs72h():+.1f}% | vs7d {g.pct_vs7d():+.1f}%"
                )

    report = "\n".join(lines).strip() + "\n"
    report_path = REPORT_DIR / f"trend-{today_utc}.md"
    report_path.write_text(report)

    print(f"✅ 生成报告: {report_path}")
    print(f"✅ 生成建站清单: {buildlist_path}")


if __name__ == "__main__":
    main()
