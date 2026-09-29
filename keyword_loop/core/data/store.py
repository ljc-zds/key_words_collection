import sqlite3
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import KeywordCandidate, KeywordObservation
from .checkpoint import CollectionCheckpoint


@dataclass(frozen=True)
class DailyRunStatus:
    target: int
    queued: int
    accepted: int
    rejected: int

    @property
    def remaining(self) -> int:
        return max(self.target - self.accepted, 0)


class KeywordStore:
    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS keywords (
                keyword TEXT NOT NULL, market TEXT NOT NULL, volume INTEGER, kd INTEGER,
                intent TEXT, retrieved_at TEXT NOT NULL, PRIMARY KEY (keyword, market)
            );
            CREATE TABLE IF NOT EXISTS semrush_related_candidates (
                keyword TEXT NOT NULL, database_name TEXT NOT NULL,
                parent_keyword TEXT NOT NULL, payload_json TEXT NOT NULL,
                retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (keyword, database_name, parent_keyword)
            );
            CREATE TABLE IF NOT EXISTS provenance (
                keyword TEXT NOT NULL, market TEXT NOT NULL, root TEXT NOT NULL,
                result_type TEXT NOT NULL, PRIMARY KEY (keyword, market, root, result_type)
            );
            CREATE TABLE IF NOT EXISTS collection_failures (
                root TEXT PRIMARY KEY, reason TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ranking_keyword_provenance (
                keyword TEXT NOT NULL, product_domain TEXT NOT NULL,
                PRIMARY KEY (keyword, product_domain)
            );
            CREATE TABLE IF NOT EXISTS pipeline_state (
                name TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kd_enrichment (
                keyword TEXT NOT NULL, market TEXT NOT NULL, score REAL,
                keyword_volume INTEGER, keyword_type TEXT, payload_json TEXT NOT NULL,
                explanation_json TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                PRIMARY KEY (keyword, market)
            );
            CREATE TABLE IF NOT EXISTS keyword_validation (
                keyword TEXT NOT NULL, market TEXT NOT NULL, stage TEXT NOT NULL,
                payload_json TEXT NOT NULL, retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (keyword, market, stage)
            );
            CREATE TABLE IF NOT EXISTS discovery_source_acceptance (
                keyword TEXT NOT NULL, market TEXT NOT NULL, source TEXT NOT NULL,
                accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (keyword, market)
            );
            CREATE TABLE IF NOT EXISTS daily_runs (
                run_date TEXT PRIMARY KEY, target INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'running', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS daily_run_keywords (
                run_date TEXT NOT NULL, keyword TEXT NOT NULL, market TEXT NOT NULL,
                source_bucket TEXT NOT NULL, ordinal INTEGER NOT NULL,
                semrush_decision TEXT, semrush_reason TEXT,
                intent_decision TEXT, intent_reason TEXT,
                PRIMARY KEY (run_date, keyword, market)
            );
            """
        )

    def record(self, item: KeywordObservation) -> None:
        self.connection.execute(
            """INSERT INTO keywords VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(keyword, market) DO UPDATE SET volume=excluded.volume, kd=excluded.kd,
            intent=excluded.intent, retrieved_at=excluded.retrieved_at""",
            (item.keyword, item.market, item.average_volume, item.kd, item.intent, item.retrieved_at),
        )
        self.connection.execute("INSERT OR IGNORE INTO provenance VALUES (?, ?, ?, ?)", (item.keyword, item.market, item.root, item.result_type))
        self.connection.commit()

    def record_failure(self, root: str, reason: str) -> None:
        self.connection.execute(
            "INSERT INTO collection_failures(root, reason) VALUES (?, ?) ON CONFLICT(root) DO UPDATE SET reason=excluded.reason, recorded_at=CURRENT_TIMESTAMP",
            (root, reason),
        )
        self.connection.commit()

    def failures(self) -> list[tuple[str, str]]:
        return self.connection.execute("SELECT root, reason FROM collection_failures ORDER BY root").fetchall()

    def record_ranking_keyword(self, keyword: str, product_domain: str) -> None:
        self.connection.execute("INSERT OR IGNORE INTO ranking_keyword_provenance VALUES (?, ?)", (keyword, product_domain))
        self.connection.commit()

    def ranking_consensus(self, keyword: str) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM ranking_keyword_provenance WHERE keyword=?", (keyword,)).fetchone()[0]

    def daily_candidates(self, *, minimum_volume: int, maximum_kd: int, limit: int) -> list[KeywordCandidate]:
        rows = self.connection.execute(
            """SELECT k.keyword, k.volume, k.kd, k.intent, k.market, k.retrieved_at,
            GROUP_CONCAT(DISTINCT p.root), GROUP_CONCAT(DISTINCT p.result_type)
            FROM keywords k JOIN provenance p ON p.keyword=k.keyword AND p.market=k.market
            WHERE (k.volume >= 30000 AND k.kd <= 60)
               OR (k.volume >= 10000 AND k.volume < 30000 AND k.kd <= 45)
               OR (k.volume >= 5000 AND k.volume < 10000 AND k.kd <= 30)
            GROUP BY k.keyword, k.market
            ORDER BY k.volume DESC, k.kd ASC, COUNT(DISTINCT p.root) DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [KeywordCandidate(row[0], row[1], row[2], row[3], row[4], tuple(sorted(row[6].split(","))), tuple(sorted(row[7].split(","))), row[5]) for row in rows]

    def get_state(self, name: str, default: str = "") -> str:
        row = self.connection.execute("SELECT value FROM pipeline_state WHERE name=?", (name,)).fetchone()
        return str(row[0]) if row else default

    def set_state(self, name: str, value: str) -> None:
        self.connection.execute("INSERT INTO pipeline_state(name,value) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (name, value))
        self.connection.commit()

    def save_collection_checkpoint(self, checkpoint: CollectionCheckpoint) -> None:
        self.set_state(f"collection_checkpoint:{checkpoint.source}", checkpoint.serialize())

    def collection_checkpoint(self, source: str) -> CollectionCheckpoint | None:
        value = self.get_state(f"collection_checkpoint:{source}")
        return CollectionCheckpoint.deserialize(value) if value else None

    def record_enrichment(self, keyword: str, market: str, payload: dict, explanation: tuple[str, str, str], retrieved_at: str) -> None:
        self.connection.execute("""INSERT INTO kd_enrichment VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(keyword,market) DO UPDATE SET score=excluded.score, keyword_volume=excluded.keyword_volume,
            keyword_type=excluded.keyword_type, payload_json=excluded.payload_json,
            explanation_json=excluded.explanation_json, retrieved_at=excluded.retrieved_at""",
            (keyword, market, payload.get("score"), payload.get("keywordVolume"), payload.get("keywordType"),
             json.dumps(payload, ensure_ascii=False), json.dumps(explanation, ensure_ascii=False), retrieved_at))
        self.connection.commit()

    def record_semrush_related(self, keyword: str, database: str, parent: str, payload: dict) -> None:
        """Keep provider-specific candidates and every distinct discovery parent."""
        self.connection.execute(
            """INSERT INTO semrush_related_candidates
            (keyword,database_name,parent_keyword,payload_json) VALUES (?,?,?,?)
            ON CONFLICT(keyword,database_name,parent_keyword) DO UPDATE SET
            payload_json=excluded.payload_json, retrieved_at=CURRENT_TIMESTAMP""",
            (keyword, database, parent, json.dumps(payload, ensure_ascii=False)),
        )
        self.connection.commit()

    def record_validation(self, keyword: str, market: str, stage: str, payload: dict) -> None:
        self.connection.execute(
            """INSERT INTO keyword_validation(keyword,market,stage,payload_json) VALUES (?,?,?,?)
            ON CONFLICT(keyword,market,stage) DO UPDATE SET payload_json=excluded.payload_json,
            retrieved_at=CURRENT_TIMESTAMP""",
            (keyword, market, stage, json.dumps(payload, ensure_ascii=False)),
        )
        self.connection.commit()

    def validation(self, keyword: str, market: str, stage: str) -> dict | None:
        row = self.connection.execute(
            "SELECT payload_json FROM keyword_validation WHERE keyword=? AND market=? AND stage=?",
            (keyword, market, stage),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def approved_discovery_keywords(self) -> set[tuple[str, str]]:
        """Return unique candidates that still pass Similarweb and Semrush gates."""
        rows = self.connection.execute(
            """SELECT DISTINCT k.keyword, k.market
            FROM keywords k
            JOIN keyword_validation v ON v.keyword=k.keyword AND v.market=k.market
            WHERE v.stage='semrush'
              AND json_extract(v.payload_json, '$.gate_decision')='保留'
              AND (
                   (k.volume >= 30000 AND k.kd <= 60)
                OR (k.volume >= 10000 AND k.volume < 30000 AND k.kd <= 45)
                OR (k.volume >= 5000 AND k.volume < 10000 AND k.kd <= 30)
              )"""
        ).fetchall()
        return {(str(keyword), str(market)) for keyword, market in rows}

    def record_source_acceptance(self, source: str, keyword: str, market: str) -> bool:
        """Assign a validated keyword to its first qualifying discovery source."""
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO discovery_source_acceptance(keyword,market,source) VALUES (?,?,?)",
            (" ".join(keyword.lower().split()), market, source),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def source_accepted_count(self, source: str) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM discovery_source_acceptance WHERE source=?", (source,)
            ).fetchone()[0]
        )

    @staticmethod
    def _date_text(run_date: date | str) -> str:
        return run_date.isoformat() if isinstance(run_date, date) else str(run_date)

    def start_daily_run(self, run_date: date | str, *, target: int = 60) -> None:
        self.connection.execute(
            """INSERT INTO daily_runs(run_date,target) VALUES (?,?)
            ON CONFLICT(run_date) DO UPDATE SET target=excluded.target, updated_at=CURRENT_TIMESTAMP""",
            (self._date_text(run_date), target),
        )
        self.connection.commit()

    def queue_daily_keyword(self, run_date: date | str, keyword: str, market: str, source_bucket: str) -> bool:
        day = self._date_text(run_date)
        normalized = " ".join(keyword.lower().split())
        next_ordinal = self.connection.execute(
            "SELECT COALESCE(MAX(ordinal),0)+1 FROM daily_run_keywords WHERE run_date=?", (day,)
        ).fetchone()[0]
        cursor = self.connection.execute(
            """INSERT OR IGNORE INTO daily_run_keywords
            (run_date,keyword,market,source_bucket,ordinal) VALUES (?,?,?,?,?)""",
            (day, normalized, market, source_bucket, next_ordinal),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def record_daily_gate(self, run_date: date | str, keyword: str, market: str, stage: str, decision: str, reason: str) -> None:
        if stage not in {"semrush", "intent"}:
            raise ValueError("daily hard gate must be semrush or intent")
        column = "semrush" if stage == "semrush" else "intent"
        self.connection.execute(
            f"UPDATE daily_run_keywords SET {column}_decision=?, {column}_reason=? WHERE run_date=? AND keyword=? AND market=?",
            (decision, reason, self._date_text(run_date), " ".join(keyword.lower().split()), market),
        )
        self.connection.commit()

    def unresolved_semrush_keywords(self) -> list[tuple[str, str, str, str]]:
        """Return every queued candidate that has not yet reached Semrush, oldest first."""
        return [
            (str(run_date), str(keyword), str(market), str(source_bucket))
            for run_date, keyword, market, source_bucket in self.connection.execute(
                """SELECT run_date, keyword, market, source_bucket
                FROM daily_run_keywords
                WHERE semrush_decision IS NULL
                ORDER BY run_date, ordinal"""
            )
        ]

    def daily_run_status(self, run_date: date | str) -> DailyRunStatus:
        day = self._date_text(run_date)
        row = self.connection.execute("SELECT target FROM daily_runs WHERE run_date=?", (day,)).fetchone()
        if row is None:
            raise KeyError(f"daily run not found: {day}")
        queued, accepted, rejected = self.connection.execute(
            """SELECT COUNT(*),
            SUM(CASE WHEN semrush_decision='保留' AND intent_decision='保留' THEN 1 ELSE 0 END),
            SUM(CASE WHEN semrush_decision='淘汰' OR intent_decision='淘汰' THEN 1 ELSE 0 END)
            FROM daily_run_keywords WHERE run_date=?""",
            (day,),
        ).fetchone()
        return DailyRunStatus(int(row[0]), int(queued or 0), int(accepted or 0), int(rejected or 0))

    def daily_accepted_candidates(self, run_date: date | str) -> list[KeywordCandidate]:
        rows = self.connection.execute(
            """SELECT k.keyword, k.volume, k.kd, k.intent, k.market, k.retrieved_at,
            GROUP_CONCAT(DISTINCT p.root), GROUP_CONCAT(DISTINCT p.result_type)
            FROM daily_run_keywords d
            JOIN keywords k ON k.keyword=d.keyword AND k.market=d.market
            JOIN provenance p ON p.keyword=k.keyword AND p.market=k.market
            WHERE d.run_date=? AND d.semrush_decision='保留' AND d.intent_decision='保留'
              AND EXISTS (SELECT 1 FROM keyword_validation v WHERE v.keyword=d.keyword AND v.market=d.market AND v.stage='serper')
              AND EXISTS (SELECT 1 FROM keyword_validation v WHERE v.keyword=d.keyword AND v.market=d.market AND v.stage='ai_screen'
                          AND json_extract(v.payload_json, '$.decision')='保留')
              AND EXISTS (SELECT 1 FROM kd_enrichment k2 WHERE k2.keyword=d.keyword AND k2.market=d.market)
            GROUP BY k.keyword, k.market
            ORDER BY MIN(d.ordinal)""",
            (self._date_text(run_date),),
        ).fetchall()
        return [KeywordCandidate(row[0], row[1], row[2], row[3], row[4], tuple(sorted(row[6].split(","))), tuple(sorted(row[7].split(","))), row[5]) for row in rows]
