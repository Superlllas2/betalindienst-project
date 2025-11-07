"""Analysis helpers for Betalindienst Fraud Sentinel.

This module exposes utilities to inspect CSV and JSON transaction data and
produce a structured fraud analysis summary used by the FastAPI backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import math

import pandas as pd


MAX_EVIDENCE_ITEMS = 10


AMOUNT_SYNONYMS = ["amount", "amt", "value", "sum", "transaction_amount"]
CURRENCY_SYNONYMS = ["currency", "curr"]
TIMESTAMP_SYNONYMS = ["timestamp", "time", "date", "datetime", "created_at"]
PAYER_SYNONYMS = ["payer", "payer_id", "sender", "from", "customer_id"]
PAYEE_SYNONYMS = ["payee", "payee_id", "recipient", "to", "vendor_id"]
TX_ID_SYNONYMS = ["tx_id", "transaction_id", "id", "reference", "ref"]

RULE_WEIGHTS = {
    "duplicate_transaction_ids": 35,
    "structuring_activity": 25,
    "near_threshold_activity": 20,
    "night_time_activity": 10,
    "non_positive_amounts": 10,
}


@dataclass
class FileAnalysis:
    """Container for the analysis of a single file."""

    flags: List[Dict] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    score_components: Dict[str, int] = field(default_factory=dict)
    total_rows: int = 0
    night_rows: int = 0


@dataclass
class AggregateAnalysis:
    """Aggregated view across all processed files."""

    flags: List[Dict] = field(default_factory=list)
    duplicate_count: int = 0
    near_threshold_count: int = 0
    night_rows: int = 0
    total_rows: int = 0
    structuring_buckets: int = 0
    rules_triggered: int = 0
    score_components: Dict[str, int] = field(default_factory=dict)

    def register_file(self, file_analysis: FileAnalysis) -> None:
        self.flags.extend(file_analysis.flags)
        self.duplicate_count += int(file_analysis.metrics.get("duplicate_ids", 0))
        self.near_threshold_count += int(file_analysis.metrics.get("near_threshold", 0))
        self.structuring_buckets += int(file_analysis.metrics.get("structuring_buckets", 0))
        self.total_rows += file_analysis.total_rows
        self.night_rows += file_analysis.night_rows
        self.rules_triggered += len(file_analysis.flags)

        for rule, weight in file_analysis.score_components.items():
            if weight:
                self.score_components[rule] = RULE_WEIGHTS.get(rule, 0)

    def final_score(self) -> int:
        return min(100, sum(self.score_components.values()))

    def night_percentage(self) -> float:
        if not self.total_rows:
            return 0.0
        return (self.night_rows / self.total_rows) * 100


def _sanitize_column_map(df: pd.DataFrame) -> Dict[str, str]:
    """Infer a map of semantic column names to actual DataFrame columns."""

    lowered = {col.lower(): col for col in df.columns}

    def find_column(candidates: List[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate in lowered:
                return lowered[candidate]
        return None

    column_map = {
        "amount": find_column(AMOUNT_SYNONYMS),
        "currency": find_column(CURRENCY_SYNONYMS),
        "timestamp": find_column(TIMESTAMP_SYNONYMS),
        "payer": find_column(PAYER_SYNONYMS),
        "payee": find_column(PAYEE_SYNONYMS),
        "transaction_id": find_column(TX_ID_SYNONYMS),
    }

    return column_map


def _numeric_series(df: pd.DataFrame, column: Optional[str]) -> Optional[pd.Series]:
    if not column or column not in df.columns:
        return None
    series = pd.to_numeric(df[column], errors="coerce")
    if series.notna().any():
        return series
    return None


def _datetime_series(df: pd.DataFrame, column: Optional[str]) -> Optional[pd.Series]:
    if not column or column not in df.columns:
        return None
    series = pd.to_datetime(df[column], errors="coerce", utc=False)
    if series.notna().any():
        return series
    return None


def _limited_evidence(rows: List[Dict]) -> List[Dict]:
    return rows[:MAX_EVIDENCE_ITEMS]


def _row_payload(df: pd.DataFrame, idx: int, columns: List[str]) -> Dict:
    payload = {"row": int(idx) + 1}
    for col in columns:
        if col and col in df.columns:
            value = df.iloc[idx][col]
            if pd.isna(value):
                continue
            payload[col] = value if not isinstance(value, (pd.Timestamp,)) else value.isoformat()
    return payload


def analyze_dataframe(df: pd.DataFrame) -> FileAnalysis:
    df = df.reset_index(drop=True)
    column_map = _sanitize_column_map(df)
    amount_series = _numeric_series(df, column_map["amount"])
    timestamp_series = _datetime_series(df, column_map["timestamp"])

    file_analysis = FileAnalysis(total_rows=len(df))

    # Metrics initialisation
    file_analysis.metrics.update(
        {
            "duplicate_ids": 0,
            "near_threshold": 0,
            "structuring_buckets": 0,
        }
    )

    # Rule: Non-positive amounts
    if amount_series is not None:
        mask = amount_series <= 0
        if mask.any():
            indices = mask[mask].index.tolist()
            evidence_columns = [column_map["transaction_id"], column_map["amount"], column_map["payer"], column_map["timestamp"]]
            evidence = _limited_evidence([
                _row_payload(df, idx, evidence_columns) for idx in indices
            ])
            file_analysis.flags.append(
                {
                    "rule": "non_positive_amounts",
                    "explanation": "Transactions with non-positive amounts detected.",
                    "evidence": evidence,
                }
            )
            file_analysis.score_components["non_positive_amounts"] = RULE_WEIGHTS["non_positive_amounts"]
        else:
            file_analysis.score_components.setdefault("non_positive_amounts", 0)
    else:
        file_analysis.score_components.setdefault("non_positive_amounts", 0)

    # Rule: Near-threshold clustering
    if amount_series is not None and len(df) > 0:
        mask = (amount_series >= 995) & (amount_series < 1000)
        count = int(mask.sum())
        file_analysis.metrics["near_threshold"] = count
        if count:
            threshold = min(3, max(1, math.ceil(len(df) * 0.02)))
            if count >= threshold:
                indices = mask[mask].index.tolist()
                evidence_columns = [column_map["transaction_id"], column_map["amount"], column_map["timestamp"], column_map["payer"]]
                evidence = _limited_evidence([
                    _row_payload(df, idx, evidence_columns) for idx in indices
                ])
                file_analysis.flags.append(
                    {
                        "rule": "near_threshold_activity",
                        "explanation": "Cluster of transactions just below reporting threshold detected.",
                        "evidence": evidence,
                    }
                )
                file_analysis.score_components["near_threshold_activity"] = RULE_WEIGHTS["near_threshold_activity"]
            else:
                file_analysis.score_components.setdefault("near_threshold_activity", 0)
        else:
            file_analysis.score_components.setdefault("near_threshold_activity", 0)
    else:
        file_analysis.metrics["near_threshold"] = 0
        file_analysis.score_components.setdefault("near_threshold_activity", 0)

    # Rule: Duplicate transaction IDs
    tx_col = column_map["transaction_id"]
    if tx_col and tx_col in df.columns:
        duplicates = df[tx_col].astype(str).value_counts()
        repeated = duplicates[duplicates > 1]
        dup_count = int(repeated.sum() - len(repeated)) if not repeated.empty else 0
        file_analysis.metrics["duplicate_ids"] = dup_count
        if dup_count:
            evidence_rows: List[Dict] = []
            for value in repeated.index:
                indices = df.index[df[tx_col].astype(str) == str(value)].tolist()
                for idx in indices:
                    payload = _row_payload(df, idx, [tx_col, column_map["amount"], column_map["timestamp"], column_map["payer"], column_map["payee"]])
                    payload[tx_col] = df.iloc[idx][tx_col]
                    evidence_rows.append(payload)
                    if len(evidence_rows) >= MAX_EVIDENCE_ITEMS:
                        break
                if len(evidence_rows) >= MAX_EVIDENCE_ITEMS:
                    break
            file_analysis.flags.append(
                {
                    "rule": "duplicate_transaction_ids",
                    "explanation": "Duplicate transaction identifiers detected across records.",
                    "evidence": evidence_rows,
                }
            )
            file_analysis.score_components["duplicate_transaction_ids"] = RULE_WEIGHTS["duplicate_transaction_ids"]
        else:
            file_analysis.score_components.setdefault("duplicate_transaction_ids", 0)
    else:
        file_analysis.metrics["duplicate_ids"] = 0
        file_analysis.score_components.setdefault("duplicate_transaction_ids", 0)

    # Rule: Night-time activity
    if timestamp_series is not None:
        night_mask = timestamp_series.dt.hour.between(0, 5, inclusive="both")
        night_count = int(night_mask.sum())
        file_analysis.night_rows = night_count
        if night_count:
            percent = (night_count / len(df)) * 100 if len(df) else 0
            if night_count >= 10 or percent > 10:
                indices = night_mask[night_mask].index.tolist()
                evidence = _limited_evidence([
                    _row_payload(df, idx, [column_map["transaction_id"], column_map["timestamp"], column_map["amount"], column_map["payer"]])
                    for idx in indices
                ])
                file_analysis.flags.append(
                    {
                        "rule": "night_time_activity",
                        "explanation": "Significant concentration of transactions during night-time hours (00:00-06:00).",
                        "evidence": evidence,
                    }
                )
                file_analysis.score_components["night_time_activity"] = RULE_WEIGHTS["night_time_activity"]
            else:
                file_analysis.score_components.setdefault("night_time_activity", 0)
        else:
            file_analysis.score_components.setdefault("night_time_activity", 0)
    else:
        file_analysis.night_rows = 0
        file_analysis.score_components.setdefault("night_time_activity", 0)

    # Rule: Structuring (many small payments in short window)
    payer_col = column_map["payer"]
    if payer_col and timestamp_series is not None and amount_series is not None:
        mask_small = amount_series < 100
        df_small = df[mask_small].copy()
        if not df_small.empty:
            df_small["__hour_bucket"] = timestamp_series[mask_small].dt.floor("H")
            grouping = df_small.groupby([payer_col, "__hour_bucket"])
            flagged = []
            for (payer, hour), group in grouping:
                if len(group) >= 5:
                    flagged.append((payer, hour, group))
            file_analysis.metrics["structuring_buckets"] = len(flagged)
            if flagged:
                evidence = []
                for payer, hour, group in flagged:
                    sample_indices = group.index.tolist()[:MAX_EVIDENCE_ITEMS]
                    evidence.append(
                        {
                            "payer": payer,
                            "hour": hour.isoformat() if isinstance(hour, pd.Timestamp) else str(hour),
                            "count": len(group),
                            "rows": [int(idx) + 1 for idx in sample_indices],
                        }
                    )
                    if len(evidence) >= MAX_EVIDENCE_ITEMS:
                        break
                file_analysis.flags.append(
                    {
                        "rule": "structuring_activity",
                        "explanation": "Repeated small-value transactions from the same payer within a one-hour window detected.",
                        "evidence": evidence,
                    }
                )
                file_analysis.score_components["structuring_activity"] = RULE_WEIGHTS["structuring_activity"]
            else:
                file_analysis.score_components.setdefault("structuring_activity", 0)
        else:
            file_analysis.metrics["structuring_buckets"] = 0
            file_analysis.score_components.setdefault("structuring_activity", 0)
    else:
        file_analysis.metrics["structuring_buckets"] = 0
        file_analysis.score_components.setdefault("structuring_activity", 0)

    return file_analysis


def _load_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=None, engine="python", dtype=str)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _load_json(path: Path) -> Optional[pd.DataFrame]:
    with open(path, "r", encoding="utf-8") as handle:
        try:
            payload = json.load(handle)
        except json.JSONDecodeError:
            return None
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return pd.DataFrame(payload)
    if isinstance(payload, list) and not payload:
        return pd.DataFrame(payload)
    return None


def analyze_file(path: Path, suffix: str) -> Tuple[bool, Optional[str], Optional[FileAnalysis]]:
    """
    Analyse a given file. Returns a tuple of (analyzed, reason, analysis_result).

    analyzed: True when analysis succeeded
    reason: string detailing why analysis was skipped or failed (when analyzed is False)
    analysis_result: FileAnalysis object when analysis succeeded
    """

    suffix = suffix.lower()
    try:
        if suffix == ".csv":
            df = _load_csv(path)
        elif suffix == ".json":
            df = _load_json(path)
            if df is None:
                return False, "json_not_tabular", None
        else:
            return False, "not_analyzed", None
    except Exception:
        return False, "parse_error", None

    if df is None:
        return False, "empty", None

    analysis = analyze_dataframe(df)
    return True, None, analysis


def build_result(job_id: str, files_meta: List[Dict]) -> Dict:
    aggregate = AggregateAnalysis()
    analyzed_files = 0

    for meta in files_meta:
        analysis: Optional[FileAnalysis] = meta.get("analysis")
        if analysis:
            aggregate.register_file(analysis)
            analyzed_files += 1

    suspiciousness = aggregate.final_score() if analyzed_files else 0

    kpis = [
        {
            "key": "suspiciousness",
            "title": "Suspiciousness",
            "value": suspiciousness,
            "hint": "Weighted rule score",
        },
        {
            "key": "dup_ids",
            "title": "Duplicate IDs",
            "value": aggregate.duplicate_count,
        },
        {
            "key": "near_threshold",
            "title": "Near Threshold",
            "value": aggregate.near_threshold_count,
        },
        {
            "key": "night_pct",
            "title": "Night-time",
            "value": f"{aggregate.night_percentage():.1f}%",
        },
        {
            "key": "structuring_buckets",
            "title": "Structuring Buckets",
            "value": aggregate.structuring_buckets,
        },
    ]

    result = {
        "summary": {
            "job_id": job_id,
            "total_files": len(files_meta),
            "analyzed_files": analyzed_files,
            "suspiciousness": suspiciousness,
            "rules_triggered": aggregate.rules_triggered,
        },
        "kpis": kpis,
        "flags": aggregate.flags,
        "files": [
            {
                "filename": meta["filename"],
                "size_bytes": meta["size"],
                "mimetype": meta.get("mimetype"),
                "analyzed": bool(meta.get("analysis")),
                "rejected_reason": meta.get("rejected_reason"),
            }
            for meta in files_meta
        ],
    }

    return result
