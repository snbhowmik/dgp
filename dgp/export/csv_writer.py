"""Export simulation outputs to Contract v1.0.0 CSVs and manifest.json."""

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List


CSV_HEADERS = {
    "regions.csv": ["region_id", "region_name", "tier", "cold_chain_available"],
    "skus.csv": [
        "sku_id",
        "product_line",
        "pack_size_kg",
        "status",
        "expected_launch_date",
        "shelf_life_days",
        "unit_cost_inr_per_kg",
        "list_price_d2c_inr_per_kg",
    ],
    "product_matrix.csv": ["sku_id", "channel", "region_id", "eligible_from", "eligible_to"],
    "orders.csv": [
        "order_id",
        "order_date",
        "channel",
        "region_id",
        "sku_id",
        "customer_id",
        "account_id",
        "requested_qty_kg",
        "fulfilled_qty_kg",
        "unit_price_inr",
        "status",
        "promised_date",
        "delivered_date",
    ],
    "capacity_batches.csv": [
        "batch_id",
        "start_date",
        "end_date",
        "facility_id",
        "product_line",
        "planned_yield_kg",
        "actual_yield_kg",
        "outcome",
    ],
    "capacity_plan.csv": [
        "week_start",
        "facility_id",
        "product_line",
        "planned_batches",
        "planned_yield_per_batch_kg",
    ],
    "coman_contracts.csv": [
        "coman_id",
        "product_line",
        "available_from",
        "lead_time_weeks",
        "min_commit_kg_per_week",
        "max_kg_per_week",
        "unit_cost_inr_per_kg",
        "min_active_weeks",
    ],
    "coman_activity.csv": ["coman_id", "week_start", "requested_kg", "delivered_kg"],
    "b2b_accounts.csv": [
        "account_id",
        "account_type",
        "region_id",
        "regions_served",
        "outlets_count",
        "status",
        "onboarded_date",
        "contract_start",
        "contract_end",
        "committed_kg_per_month",
        "contract_price_inr_per_kg",
        "shortfall_penalty_inr_per_kg",
        "requested_start_date",
        "requested_kg_per_month",
    ],
    "marketing_daily.csv": [
        "date",
        "region_id",
        "channel",
        "campaign_type",
        "campaign_id",
        "spend_inr",
        "impressions",
        "clicks",
        "unique_visitors",
        "bounces",
        "leads",
        "qualified_leads",
        "conversions",
        "attributed_revenue_inr",
    ],
    "marketing_plan.csv": ["week_start", "region_id", "channel", "campaign_type", "planned_spend_inr"],
    "customers.csv": [
        "customer_id",
        "region_id",
        "acquired_date",
        "acquisition_campaign_type",
        "persona_segment",
        "churned_date",
        "is_subscriber",
    ],
    "nps_responses.csv": ["response_date", "channel", "region_id", "customer_or_account_id", "score"],
}


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def write_csv_table(filepath: str, filename: str, rows: List[Any]):
    """Write list of row dataclasses (with to_csv_dict) to CSV."""
    headers = CSV_HEADERS[filename]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            d = r.to_csv_dict() if hasattr(r, "to_csv_dict") else r
            writer.writerow(d)


def export_drop(
    out_dir: str,
    world_id: str,
    history_start: str,
    history_end: str,
    plan_end: str,
    tables: Dict[str, List[Any]],
    timestamp: str = None,
) -> Dict[str, str]:
    """
    Export all 13 CSV tables and manifest.json into out_dir.
    Returns dict of filename -> sha256.
    """
    os.makedirs(out_dir, exist_ok=True)
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    file_hashes: Dict[str, str] = {}

    for filename, headers in CSV_HEADERS.items():
        filepath = os.path.join(out_dir, filename)
        rows = tables.get(filename, [])
        write_csv_table(filepath, filename, rows)
        file_hashes[filename] = compute_sha256(filepath)

    manifest_data = {
        "world_id": world_id,
        "contract_version": "1.0.0",
        "history_start": history_start,
        "history_end": history_end,
        "plan_end": plan_end,
        "generated_at": timestamp,
        "files": file_hashes,
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        f.write("\n")

    return file_hashes
