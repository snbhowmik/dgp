"""Sealing protocol: generates ground-truth sealed descriptions and computes SHA-256 hashes."""

import hashlib
import os
from typing import Dict, List, Tuple
import yaml
from dgp.config import WorldConfig


def generate_sealed_doc(
    world_id: str,
    config: WorldConfig,
    seed: int,
    mapping_note: str,
) -> dict:
    """Generate the confidential unblinding document for sealed/world_xx.yaml."""
    timeline = []
    for s in config.shocks:
        timeline.append({
            "event_name": s.name,
            "event_type": s.event_type,
            "start_week": s.start_week,
            "duration_weeks": s.duration_weeks,
            "impact_multiplier": s.impact_factor,
            "description": s.description,
        })

    # Catalog pilot SKU launches
    for sku in config.skus:
        if sku.status in ("pilot", "rnd") and sku.expected_launch_date:
            timeline.append({
                "event_name": f"Product Launch / Pilot: {sku.sku_id}",
                "event_type": "product_launch",
                "launch_date": sku.expected_launch_date,
                "product_line": sku.product_line,
                "description": f"Introduction of {sku.product_line} ({sku.sku_id}) into designated regional cold chains.",
            })

    doc = {
        "world_id": world_id,
        "internal_config_name": config.world_name,
        "seed": seed,
        "description": config.description,
        "blind_assignment_note": mapping_note,
        "core_mechanics": {
            "demand_growth_rate_annual": config.demand_growth_rate_annual,
            "seasonality_sensitivity": config.seasonality_sensitivity,
            "word_of_mouth_strength": config.wom_strength,
            "d2c_repeat_rate": config.d2c_repeat_rate,
            "d2c_subscriber_fraction": config.d2c_subscriber_fraction,
            "coman_activation_threshold": config.coman_activation_threshold,
            "marketing_responsiveness": config.marketing_responsiveness,
            "nps_baseline": config.nps_baseline,
        },
        "notable_events_and_shocks": timeline,
        "facilities": [
            {
                "facility_id": f.facility_id,
                "product_line": f.product_line,
                "nominal_batches_per_week": f.nominal_batches_per_week,
                "planned_yield_per_batch_kg": f.planned_yield_per_batch_kg,
                "base_failure_rate": f.failure_rate,
                "base_partial_rate": f.partial_rate,
            }
            for f in config.facilities
        ],
        "coman_partners": [
            {
                "coman_id": c.coman_id,
                "product_line": c.product_line,
                "available_from": c.available_from,
                "lead_time_weeks": c.lead_time_weeks,
                "min_commit_kg_per_week": c.min_commit_kg_per_week,
                "max_kg_per_week": c.max_kg_per_week,
                "unit_cost_inr_per_kg": c.unit_cost_inr_per_kg,
            }
            for c in config.coman_contracts
        ],
        "b2b_accounts_summary": {
            "total_accounts": len(config.b2b_accounts),
            "pipeline_count": sum(1 for b in config.b2b_accounts if b.status_at_end == "pipeline"),
            "active_count": sum(1 for b in config.b2b_accounts if b.status_at_end == "active"),
            "churned_count": sum(1 for b in config.b2b_accounts if b.status_at_end == "churned"),
            "paused_count": sum(1 for b in config.b2b_accounts if b.status_at_end == "paused"),
        },
    }
    return doc


def write_and_hash_sealed(sealed_dir: str, world_id: str, doc: dict) -> Tuple[str, str]:
    """Write sealed doc to YAML and return (filepath, sha256_hash)."""
    os.makedirs(sealed_dir, exist_ok=True)
    out_path = os.path.join(sealed_dir, f"{world_id}.yaml")
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, sort_keys=False, default_flow_style=False)

    # Compute sha256
    h = hashlib.sha256()
    with open(out_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return out_path, h.hexdigest()
