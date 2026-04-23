"""
SQLite 데이터베이스 레이어 — 가계부 앱
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "gaegabu.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    날짜       TEXT,
    연월       TEXT,
    통장       TEXT,
    적요       TEXT,
    거래유형   TEXT,
    거래금액   REAL,
    대분류     TEXT,
    소분류     TEXT,
    is_fixed   INTEGER DEFAULT 0,
    메모       TEXT DEFAULT '',
    uploaded_at TEXT DEFAULT (datetime('now')),
    UNIQUE(날짜, 통장, 적요, 거래금액)
);

CREATE TABLE IF NOT EXISTS portfolio_assets (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    자산명    TEXT NOT NULL,
    유형      TEXT DEFAULT '기타',
    매입가    REAL DEFAULT 0,
    수량      REAL DEFAULT 1,
    현재가    REAL DEFAULT 0,
    목표비중  REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS monthly_returns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    연월       TEXT NOT NULL UNIQUE,
    총평가금액 REAL DEFAULT 0,
    순기여금   REAL DEFAULT 0,
    메모       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS savings_goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    목표명      TEXT NOT NULL,
    월목표금액  REAL DEFAULT 0,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pension_config (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    현재나이         INTEGER DEFAULT 35,
    은퇴나이         INTEGER DEFAULT 60,
    수령나이         INTEGER DEFAULT 65,
    월납입액         REAL DEFAULT 0,
    예상수익률       REAL DEFAULT 5.0,
    국민연금_예상월액 REAL DEFAULT 0,
    목표월생활비     REAL DEFAULT 3000000,
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tax_deduction (
    연도      INTEGER NOT NULL,
    항목      TEXT NOT NULL,
    납입금액  REAL DEFAULT 0,
    PRIMARY KEY (연도, 항목)
);

CREATE TABLE IF NOT EXISTS budgets (
    소분류      TEXT PRIMARY KEY,
    월예산금액  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS overrides (
    적요      TEXT PRIMARY KEY,
    대분류    TEXT,
    소분류    TEXT,
    is_fixed  INTEGER DEFAULT 0
);
"""


class Database:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._init_db()
        self.migrate_from_json()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ── Transactions ──────────────────────────────────────────────────────
    def save_transactions(self, df: pd.DataFrame) -> int:
        inserted = 0
        with self._connect() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO transactions
                           (날짜,연월,통장,적요,거래유형,거래금액,대분류,소분류,is_fixed,메모)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            str(row.get("날짜", "")),
                            str(row.get("연월", "")),
                            str(row.get("_통장", "")),
                            str(row.get("적요", "")),
                            str(row.get("거래 유형", "")),
                            float(row.get("거래금액", 0) or 0),
                            str(row.get("대분류", "")),
                            str(row.get("소분류", "")),
                            int(bool(row.get("IsFixed", False))),
                            str(row.get("메모", "")),
                        ),
                    )
                    if conn.execute("SELECT changes()").fetchone()[0]:
                        inserted += 1
                except Exception:
                    pass
        return inserted

    def load_transactions(self, yearmonth: Optional[str] = None) -> pd.DataFrame:
        sql = "SELECT * FROM transactions"
        params: list = []
        if yearmonth:
            sql += " WHERE 연월 = ?"
            params.append(yearmonth)
        sql += " ORDER BY 날짜 DESC"
        with self._connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def get_available_months(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT 연월 FROM transactions ORDER BY 연월 DESC"
            ).fetchall()
        return [r[0] for r in rows]

    def has_transactions(self) -> bool:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        return count > 0

    def update_transaction_by_key(
        self, 날짜: str, 통장: str, 적요: str, 거래금액: float, updates: dict
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE transactions
                   SET 대분류=?, 소분류=?, is_fixed=?, 메모=?
                   WHERE 날짜=? AND 통장=? AND 적요=? AND 거래금액=?""",
                (
                    updates.get("대분류"), updates.get("소분류"),
                    int(bool(updates.get("IsFixed", False))),
                    updates.get("메모", ""),
                    날짜, 통장, 적요, 거래금액,
                ),
            )

    # ── Portfolio ─────────────────────────────────────────────────────────
    def get_assets(self) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query("SELECT * FROM portfolio_assets ORDER BY id", conn)

    def upsert_asset(self, asset: dict) -> None:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            if asset.get("id"):
                conn.execute(
                    """UPDATE portfolio_assets
                       SET 자산명=?, 유형=?, 매입가=?, 수량=?, 현재가=?, 목표비중=?, updated_at=?
                       WHERE id=?""",
                    (
                        asset["자산명"], asset.get("유형", "기타"),
                        float(asset.get("매입가", 0)), float(asset.get("수량", 1)),
                        float(asset.get("현재가", 0)), float(asset.get("목표비중", 0)),
                        now, asset["id"],
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO portfolio_assets (자산명,유형,매입가,수량,현재가,목표비중,updated_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        asset["자산명"], asset.get("유형", "기타"),
                        float(asset.get("매입가", 0)), float(asset.get("수량", 1)),
                        float(asset.get("현재가", 0)), float(asset.get("목표비중", 0)),
                        now,
                    ),
                )

    def delete_asset(self, asset_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM portfolio_assets WHERE id=?", (asset_id,))

    # ── Monthly Returns ───────────────────────────────────────────────────
    def get_monthly_returns(self) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(
                "SELECT * FROM monthly_returns ORDER BY 연월 ASC", conn
            )

    def upsert_monthly_return(
        self, yearmonth: str, total_eval: float,
        net_contribution: float = 0, memo: str = ""
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO monthly_returns (연월,총평가금액,순기여금,메모)
                   VALUES (?,?,?,?)
                   ON CONFLICT(연월) DO UPDATE SET
                   총평가금액=excluded.총평가금액,
                   순기여금=excluded.순기여금,
                   메모=excluded.메모""",
                (yearmonth, total_eval, net_contribution, memo),
            )

    def delete_monthly_return(self, yearmonth: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM monthly_returns WHERE 연월=?", (yearmonth,))

    # ── Savings Goals ─────────────────────────────────────────────────────
    def get_savings_goals(self) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(
                "SELECT * FROM savings_goals WHERE is_active=1 ORDER BY id", conn
            )

    def upsert_savings_goal(self, goal: dict) -> None:
        with self._connect() as conn:
            if goal.get("id"):
                conn.execute(
                    "UPDATE savings_goals SET 목표명=?, 월목표금액=? WHERE id=?",
                    (goal["목표명"], float(goal.get("월목표금액", 0)), goal["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO savings_goals (목표명,월목표금액) VALUES (?,?)",
                    (goal["목표명"], float(goal.get("월목표금액", 0))),
                )

    def delete_savings_goal(self, goal_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE savings_goals SET is_active=0 WHERE id=?", (goal_id,)
            )

    # ── Pension ───────────────────────────────────────────────────────────
    def get_pension_config(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pension_config WHERE id=1"
            ).fetchone()
        if row:
            return dict(row)
        return {
            "현재나이": 35, "은퇴나이": 60, "수령나이": 65,
            "월납입액": 0, "예상수익률": 5.0,
            "국민연금_예상월액": 0, "목표월생활비": 3000000,
        }

    def save_pension_config(self, config: dict) -> None:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO pension_config
                   (id,현재나이,은퇴나이,수령나이,월납입액,예상수익률,국민연금_예상월액,목표월생활비,updated_at)
                   VALUES (1,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                   현재나이=excluded.현재나이, 은퇴나이=excluded.은퇴나이,
                   수령나이=excluded.수령나이, 월납입액=excluded.월납입액,
                   예상수익률=excluded.예상수익률,
                   국민연금_예상월액=excluded.국민연금_예상월액,
                   목표월생활비=excluded.목표월생활비,
                   updated_at=excluded.updated_at""",
                (
                    int(config.get("현재나이", 35)), int(config.get("은퇴나이", 60)),
                    int(config.get("수령나이", 65)), float(config.get("월납입액", 0)),
                    float(config.get("예상수익률", 5.0)),
                    float(config.get("국민연금_예상월액", 0)),
                    float(config.get("목표월생활비", 3000000)), now,
                ),
            )

    # ── Tax Deduction ─────────────────────────────────────────────────────
    def get_tax_deductions(self, year: int) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(
                "SELECT * FROM tax_deduction WHERE 연도=? ORDER BY 항목",
                conn, params=(year,),
            )

    def upsert_tax_deduction(self, year: int, item: str, amount: float) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO tax_deduction (연도,항목,납입금액) VALUES (?,?,?)
                   ON CONFLICT(연도,항목) DO UPDATE SET 납입금액=excluded.납입금액""",
                (year, item, amount),
            )

    # ── Budgets ───────────────────────────────────────────────────────────
    def get_budgets(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT 소분류, 월예산금액 FROM budgets"
            ).fetchall()
        return {r[0]: int(r[1]) for r in rows}

    def save_budgets(self, budgets: dict) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM budgets")
            for sub, amt in budgets.items():
                if amt and int(amt) > 0:
                    conn.execute(
                        "INSERT OR REPLACE INTO budgets (소분류,월예산금액) VALUES (?,?)",
                        (str(sub), int(amt)),
                    )

    # ── Overrides ─────────────────────────────────────────────────────────
    def get_overrides(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT 적요,대분류,소분류,is_fixed FROM overrides"
            ).fetchall()
        return {
            r[0]: {"대분류": r[1], "소분류": r[2], "IsFixed": bool(r[3])}
            for r in rows
        }

    def save_overrides(self, overrides: dict) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM overrides")
            for jeok, v in overrides.items():
                conn.execute(
                    "INSERT OR REPLACE INTO overrides (적요,대분류,소분류,is_fixed) VALUES (?,?,?,?)",
                    (
                        jeok, v.get("대분류", ""), v.get("소분류", ""),
                        int(bool(v.get("IsFixed", False))),
                    ),
                )

    # ── Migration ─────────────────────────────────────────────────────────
    def migrate_from_json(self) -> None:
        overrides_path = BASE_DIR / "overrides.json"
        budgets_path = BASE_DIR / "budgets.json"

        with self._connect() as conn:
            ov_count = conn.execute("SELECT COUNT(*) FROM overrides").fetchone()[0]
            bd_count = conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0]

        if ov_count == 0 and overrides_path.exists():
            try:
                data = json.loads(overrides_path.read_text(encoding="utf-8"))
                self.save_overrides(data)
            except Exception:
                pass

        if bd_count == 0 and budgets_path.exists():
            try:
                data = json.loads(budgets_path.read_text(encoding="utf-8"))
                self.save_budgets({k: int(v) for k, v in data.items() if v})
            except Exception:
                pass


# ── 싱글턴 ────────────────────────────────────────────────────────────────
def get_db() -> Database:
    try:
        import streamlit as st
        if "_gaegabu_db" not in st.session_state:
            st.session_state["_gaegabu_db"] = Database()
        return st.session_state["_gaegabu_db"]
    except Exception:
        if not hasattr(get_db, "_instance"):
            get_db._instance = Database()  # type: ignore[attr-defined]
        return get_db._instance  # type: ignore[attr-defined]
