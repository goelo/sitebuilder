#!/usr/bin/env python3
"""
Roblox 趋势数据采集 — 每小时运行
调用 Rolimons API，将游戏在线数据写入 SQLite
只在榜单更新时段运行，且只在人数变化时写入
"""

import sqlite3
import json
import urllib.request
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "roblox-trends.db"
API_URL = "https://api.rolimons.com/games/v1/gamelist"

# 变化阈值：人数变化超过5%才写入
CHANGE_THRESHOLD = 0.05


def is_in_update_window():
    """检查当前是否在榜单更新时段（北京时间）"""
    now = datetime.now(timezone.utc)
    bj_hour = (now.hour + 8) % 24
    bj_min = now.minute
    t = bj_hour * 60 + bj_min
    
    # 00:30-03:10 或 17:40-20:30
    w1 = (0 * 60 + 30) <= t < (3 * 60 + 10)
    w2 = (17 * 60 + 40) <= t < (20 * 60 + 30)
    return w1 or w2


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            game_id TEXT NOT NULL,
            name TEXT NOT NULL,
            players INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_ts 
        ON snapshots(timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_game_ts 
        ON snapshots(game_id, timestamp)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS first_seen (
            game_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            first_date TEXT NOT NULL
        )
    """)
    conn.commit()


def fetch_rolimons():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    if not data.get("success"):
        raise ValueError("API returned success=false")
    return data


def get_last_snapshot(conn):
    """获取每个游戏的最新快照"""
    cursor = conn.execute("""
        SELECT game_id, players 
        FROM snapshots 
        WHERE timestamp = (SELECT MAX(timestamp) FROM snapshots)
    """)
    return {row[0]: row[1] for row in cursor.fetchall()}


def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # 时间窗口检查已移除 - 全天候采集，依赖 diff 检查避免数据膨胀
    # if not is_in_update_window():
    #     print(f"[{ts}] ⏸️  不在更新时段，跳过采集")
    #     sys.exit(0)
    
    print(f"[{ts}] 开始采集...")

    # 采集
    try:
        data = fetch_rolimons()
    except Exception as e:
        print(f"[{ts}] ❌ API 请求失败: {e}")
        sys.exit(1)

    games = data.get("games", {})
    game_count = len(games)
    print(f"[{ts}] 获取到 {game_count} 个游戏")

    # 写入 SQLite
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)

    # 获取上次快照
    last_snapshot = get_last_snapshot(conn)
    
    # 只写入有变化的游戏
    rows = []
    new_games = []
    changed_games = []
    
    for game_id, info in games.items():
        name = info[0] if isinstance(info, list) else info.get("name", "")
        players = info[1] if isinstance(info, list) else info.get("players", 0)
        
        # 新游戏或人数变化 >5%
        if game_id not in last_snapshot:
            rows.append((game_id, name, players, ts))
            new_games.append(name)
        else:
            last_players = last_snapshot[game_id]
            if last_players == 0:
                change_pct = 1.0 if players > 0 else 0.0
            else:
                change_pct = abs(players - last_players) / last_players
            
            if change_pct >= CHANGE_THRESHOLD:
                rows.append((game_id, name, players, ts))
                changed_games.append((name, last_players, players, change_pct))

    if rows:
        conn.executemany(
            "INSERT INTO snapshots (game_id, name, players, timestamp) VALUES (?, ?, ?, ?)",
            rows
        )

    # 更新 first_seen
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for game_id, info in games.items():
        name = info[0] if isinstance(info, list) else info.get("name", "")
        conn.execute(
            "INSERT OR IGNORE INTO first_seen (game_id, name, first_date) VALUES (?, ?, ?)",
            (game_id, name, today)
        )

    conn.commit()

    # 统计
    total_first_seen = conn.execute("SELECT COUNT(*) FROM first_seen").fetchone()[0]
    total_snapshots = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    conn.close()

    print(f"[{ts}] ✅ 写入 {len(rows)} 条快照（新游戏 {len(new_games)}，变化 {len(changed_games)}，跳过 {game_count - len(rows)}）")
    print(f"[{ts}] 📊 数据库: {total_snapshots} 条快照, {total_first_seen} 个游戏")


if __name__ == "__main__":
    main()
