"""Contract v1.0.0 Validator and consistency verification suite."""

import csv
import json
import os
import re
from datetime import date, datetime
from typing import Dict, List, Set, Tuple
from dgp.export.csv_writer import CSV_HEADERS, compute_sha256


FORBIDDEN_WORDS = [
    "true_",
    "regime",
    "viral",
    "elasticity",
    "shock",
    "ground_truth",
    "unobserved",
]

ALLOWED_TIERS = {"metro", "tier1", "tier2"}
ALLOWED_PRODUCT_LINES = {"cultivated_chicken", "mycelium", "seaweed", "microbial"}
ALLOWED_SKU_STATUSES = {"rnd", "pilot", "production", "retired"}
ALLOWED_CHANNELS = {"D2C", "B2B"}
ALLOWED_ORDER_STATUSES = {"fulfilled", "partial", "waitlisted", "cancelled_stockout", "cancelled_other"}
ALLOWED_BATCH_OUTCOMES = {"success", "partial", "failed"}
ALLOWED_B2B_TYPES = {"restaurant", "qsr_chain", "hotel", "caterer", "distributor", "other"}
ALLOWED_B2B_STATUSES = {"active", "pipeline", "churned", "paused"}
ALLOWED_CAMPAIGN_TYPES = {"ppc", "native", "social", "influencer", "email", "trade"}


class ValidationError(Exception):
    pass


class ContractValidator:
    """Validates an output drop directory against Data Contract v1.0.0."""

    def __init__(self, drop_dir: str):
        self.drop_dir = drop_dir
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run complete validation suite. Returns (success, errors, warnings)."""
        self.errors = []
        self.warnings = []

        self._check_file_completeness_and_manifest()
        self._check_forbidden_words()
        
        # Load tables
        tables = self._load_tables()
        if self.errors:
            return False, self.errors, self.warnings

        self._validate_regions(tables["regions.csv"])
        self._validate_skus(tables["skus.csv"])
        self._validate_product_matrix(tables["product_matrix.csv"], tables)
        self._validate_b2b_accounts(tables["b2b_accounts.csv"], tables)
        self._validate_customers(tables["customers.csv"], tables)
        self._validate_capacity_batches(tables["capacity_batches.csv"])
        self._validate_capacity_plan(tables["capacity_plan.csv"])
        self._validate_coman(tables["coman_contracts.csv"], tables["coman_activity.csv"])
        self._validate_marketing_daily(tables["marketing_daily.csv"], tables)
        self._validate_marketing_plan(tables["marketing_plan.csv"], tables)
        self._validate_orders(tables["orders.csv"], tables)
        self._validate_nps(tables["nps_responses.csv"], tables)
        self._validate_capacity_fulfillment_conservation(tables)

        return len(self.errors) == 0, self.errors, self.warnings

    def _check_file_completeness_and_manifest(self):
        manifest_path = os.path.join(self.drop_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            self.errors.append("manifest.json is missing")
            return

        with open(manifest_path, "r", encoding="utf-8") as f:
            try:
                manifest = json.load(f)
            except Exception as e:
                self.errors.append(f"manifest.json is invalid JSON: {e}")
                return

        # Check required fields in manifest
        req_keys = ["world_id", "contract_version", "history_start", "history_end", "plan_end", "generated_at", "files"]
        for k in req_keys:
            if k not in manifest:
                self.errors.append(f"manifest.json missing required key: {k}")

        if manifest.get("contract_version") != "1.0.0":
            self.errors.append(f"manifest.json contract_version must be 1.0.0, got: {manifest.get('contract_version')}")

        # Check that no extra character fields leaked into manifest
        allowed_manifest_keys = set(req_keys)
        for k in manifest.keys():
            if k not in allowed_manifest_keys:
                self.errors.append(f"manifest.json contains unauthorized key: {k}")

        # Check all 13 CSV files exist and match hashes
        files_dict = manifest.get("files", {})
        for fname in CSV_HEADERS.keys():
            fpath = os.path.join(self.drop_dir, fname)
            if not os.path.exists(fpath):
                self.errors.append(f"Required CSV file missing: {fname}")
            else:
                computed_hash = compute_sha256(fpath)
                recorded_hash = files_dict.get(fname)
                if computed_hash != recorded_hash:
                    self.errors.append(f"SHA-256 mismatch for {fname}: recorded {recorded_hash}, computed {computed_hash}")

    def _check_forbidden_words(self):
        """Ensure no ground-truth, regime, or simulation artifact terms leaked into CSV files."""
        for root, _, files in os.walk(self.drop_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                    for word in FORBIDDEN_WORDS:
                        if word in content:
                            self.errors.append(f"Forbidden term '{word}' found in {fname}")

    def _load_tables(self) -> Dict[str, List[Dict[str, str]]]:
        tables = {}
        for fname, expected_headers in CSV_HEADERS.items():
            fpath = os.path.join(self.drop_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header != expected_headers:
                    self.errors.append(f"{fname} headers do not match contract. Expected {expected_headers}, got {header}")
                f.seek(0)
                dict_reader = csv.DictReader(f)
                tables[fname] = list(dict_reader)
        return tables

    def _validate_regions(self, rows: List[Dict[str, str]]):
        if not rows:
            self.errors.append("regions.csv is empty")
        ids = set()
        for r in rows:
            rid = r["region_id"]
            if not rid:
                self.errors.append("regions.csv has empty region_id")
            if rid in ids:
                self.errors.append(f"Duplicate region_id in regions.csv: {rid}")
            ids.add(rid)
            if r["tier"] not in ALLOWED_TIERS:
                self.errors.append(f"Invalid tier '{r['tier']}' in regions.csv")
            if r["cold_chain_available"] not in ("true", "false"):
                self.errors.append(f"Invalid cold_chain_available boolean '{r['cold_chain_available']}' in regions.csv")

    def _validate_skus(self, rows: List[Dict[str, str]]):
        if not rows:
            self.errors.append("skus.csv is empty")
        ids = set()
        for r in rows:
            sid = r["sku_id"]
            if sid in ids:
                self.errors.append(f"Duplicate sku_id in skus.csv: {sid}")
            ids.add(sid)
            if r["product_line"] not in ALLOWED_PRODUCT_LINES:
                self.errors.append(f"Invalid product_line '{r['product_line']}' in skus.csv")
            if r["status"] not in ALLOWED_SKU_STATUSES:
                self.errors.append(f"Invalid status '{r['status']}' in skus.csv")
            try:
                ps = float(r["pack_size_kg"])
                if ps <= 0:
                    self.errors.append(f"pack_size_kg must be > 0 in skus.csv: {ps}")
                uc = float(r["unit_cost_inr_per_kg"])
                lp = float(r["list_price_d2c_inr_per_kg"])
                sl = int(r["shelf_life_days"])
                if sl <= 0:
                    self.errors.append(f"shelf_life_days must be > 0: {sl}")
            except ValueError as e:
                self.errors.append(f"Number parsing error in skus.csv: {e}")

    def _validate_product_matrix(self, rows: List[Dict[str, str]], tables: Dict[str, List[Dict[str, str]]]):
        valid_skus = {r["sku_id"] for r in tables.get("skus.csv", [])}
        valid_regions = {r["region_id"] for r in tables.get("regions.csv", [])}

        for r in rows:
            if r["sku_id"] not in valid_skus:
                self.errors.append(f"product_matrix.csv invalid FK sku_id: {r['sku_id']}")
            if r["region_id"] not in valid_regions:
                self.errors.append(f"product_matrix.csv invalid FK region_id: {r['region_id']}")
            if r["channel"] not in ALLOWED_CHANNELS:
                self.errors.append(f"product_matrix.csv invalid channel: {r['channel']}")
            # Date validation
            try:
                date.fromisoformat(r["eligible_from"])
                if r["eligible_to"]:
                    date.fromisoformat(r["eligible_to"])
            except ValueError as e:
                self.errors.append(f"Invalid date in product_matrix.csv: {e}")

    def _validate_b2b_accounts(self, rows: List[Dict[str, str]], tables: Dict[str, List[Dict[str, str]]]):
        valid_regions = {r["region_id"] for r in tables.get("regions.csv", [])}
        acc_ids = set()

        for r in rows:
            aid = r["account_id"]
            if aid in acc_ids:
                self.errors.append(f"Duplicate account_id in b2b_accounts.csv: {aid}")
            acc_ids.add(aid)

            if r["account_type"] not in ALLOWED_B2B_TYPES:
                self.errors.append(f"Invalid account_type '{r['account_type']}' in b2b_accounts.csv")
            if r["status"] not in ALLOWED_B2B_STATUSES:
                self.errors.append(f"Invalid status '{r['status']}' in b2b_accounts.csv")
            if r["region_id"] not in valid_regions:
                self.errors.append(f"Invalid FK region_id '{r['region_id']}' in b2b_accounts.csv")

            for reg in r["regions_served"].split("|"):
                if reg and reg not in valid_regions:
                    self.errors.append(f"regions_served contains unknown region_id '{reg}' in b2b_accounts.csv")

            if r["status"] == "pipeline":
                if not r["requested_start_date"] or not r["requested_kg_per_month"]:
                    self.errors.append(f"Pipeline account {aid} must have requested_start_date and requested_kg_per_month")

    def _validate_customers(self, rows: List[Dict[str, str]], tables: Dict[str, List[Dict[str, str]]]):
        valid_regions = {r["region_id"] for r in tables.get("regions.csv", [])}
        cust_ids = set()

        for r in rows:
            cid = r["customer_id"]
            if cid in cust_ids:
                self.errors.append(f"Duplicate customer_id in customers.csv: {cid}")
            cust_ids.add(cid)

            if r["region_id"] not in valid_regions:
                self.errors.append(f"Invalid FK region_id '{r['region_id']}' in customers.csv")

            acq = r["acquisition_campaign_type"]
            if acq and acq not in ALLOWED_CAMPAIGN_TYPES:
                self.errors.append(f"Invalid acquisition_campaign_type '{acq}' in customers.csv")

            if r["is_subscriber"] not in ("true", "false"):
                self.errors.append(f"Invalid is_subscriber '{r['is_subscriber']}' in customers.csv")

    def _validate_capacity_batches(self, rows: List[Dict[str, str]]):
        for r in rows:
            if r["outcome"] not in ALLOWED_BATCH_OUTCOMES:
                self.errors.append(f"Invalid outcome '{r['outcome']}' in capacity_batches.csv")
            py = float(r["planned_yield_kg"])
            ay = float(r["actual_yield_kg"])
            if r["outcome"] == "failed" and ay > 0.0:
                self.errors.append(f"Failed batch {r['batch_id']} must have actual_yield_kg = 0, got {ay}")
            if ay < 0 or py <= 0:
                self.errors.append(f"Yield values invalid in batch {r['batch_id']}")

    def _validate_capacity_plan(self, rows: List[Dict[str, str]]):
        for r in rows:
            d = date.fromisoformat(r["week_start"])
            if d.weekday() != 0:
                self.errors.append(f"capacity_plan.csv week_start {r['week_start']} is not a Monday")

    def _validate_coman(self, contracts: List[Dict[str, str]], activity: List[Dict[str, str]]):
        valid_coman_ids = {c["coman_id"] for c in contracts}
        for a in activity:
            if a["coman_id"] not in valid_coman_ids:
                self.errors.append(f"coman_activity.csv unknown FK coman_id: {a['coman_id']}")
            d = date.fromisoformat(a["week_start"])
            if d.weekday() != 0:
                self.errors.append(f"coman_activity.csv week_start {a['week_start']} is not a Monday")
            req = float(a["requested_kg"])
            dlv = float(a["delivered_kg"])
            if req < 0 or dlv < 0:
                self.errors.append(f"Negative quantities in coman_activity.csv: {a}")

    def _validate_marketing_daily(self, rows: List[Dict[str, str]], tables: Dict[str, List[Dict[str, str]]]):
        valid_regions = {r["region_id"] for r in tables.get("regions.csv", [])}
        for r in rows:
            if r["region_id"] not in valid_regions:
                self.errors.append(f"marketing_daily.csv invalid FK region_id: {r['region_id']}")
            if r["channel"] not in ALLOWED_CHANNELS:
                self.errors.append(f"marketing_daily.csv invalid channel: {r['channel']}")
            if r["campaign_type"] not in ALLOWED_CAMPAIGN_TYPES:
                self.errors.append(f"marketing_daily.csv invalid campaign_type: {r['campaign_type']}")

            # Funnel consistency check
            uv = int(r["unique_visitors"])
            bnc = int(r["bounces"])
            leads = int(r["leads"])
            ql = int(r["qualified_leads"])
            conv = int(r["conversions"])

            if bnc > uv:
                self.errors.append(f"Funnel violation in marketing_daily: bounces ({bnc}) > unique_visitors ({uv})")
            if leads > (uv - bnc):
                self.errors.append(f"Funnel violation in marketing_daily: leads ({leads}) > unique_visitors - bounces ({uv - bnc})")
            if ql > leads:
                self.errors.append(f"Funnel violation in marketing_daily: qualified_leads ({ql}) > leads ({leads})")
            if conv > leads:
                self.errors.append(f"Funnel violation in marketing_daily: conversions ({conv}) > leads ({leads})")

    def _validate_marketing_plan(self, rows: List[Dict[str, str]], tables: Dict[str, List[Dict[str, str]]]):
        valid_regions = {r["region_id"] for r in tables.get("regions.csv", [])}
        for r in rows:
            d = date.fromisoformat(r["week_start"])
            if d.weekday() != 0:
                self.errors.append(f"marketing_plan.csv week_start {r['week_start']} is not a Monday")
            if r["region_id"] not in valid_regions:
                self.errors.append(f"marketing_plan.csv invalid FK region_id: {r['region_id']}")

    def _validate_orders(self, rows: List[Dict[str, str]], tables: Dict[str, List[Dict[str, str]]]):
        valid_regions = {r["region_id"] for r in tables.get("regions.csv", [])}
        valid_skus = {r["sku_id"] for r in tables.get("skus.csv", [])}
        valid_customers = {r["customer_id"] for r in tables.get("customers.csv", [])}
        valid_accounts = {r["account_id"] for r in tables.get("b2b_accounts.csv", [])}

        for r in rows:
            ch = r["channel"]
            if ch not in ALLOWED_CHANNELS:
                self.errors.append(f"orders.csv invalid channel: {ch}")

            if ch == "D2C":
                if not r["customer_id"] or r["customer_id"] not in valid_customers:
                    self.errors.append(f"orders.csv D2C order {r['order_id']} invalid FK customer_id: '{r['customer_id']}'")
                if r["account_id"]:
                    self.errors.append(f"orders.csv D2C order {r['order_id']} must have empty account_id")
            else:
                if not r["account_id"] or r["account_id"] not in valid_accounts:
                    self.errors.append(f"orders.csv B2B order {r['order_id']} invalid FK account_id: '{r['account_id']}'")
                if r["customer_id"]:
                    self.errors.append(f"orders.csv B2B order {r['order_id']} must have empty customer_id")

            if r["region_id"] not in valid_regions:
                self.errors.append(f"orders.csv invalid FK region_id: {r['region_id']}")
            if r["sku_id"] not in valid_skus:
                self.errors.append(f"orders.csv invalid FK sku_id: {r['sku_id']}")

            st = r["status"]
            if st not in ALLOWED_ORDER_STATUSES:
                self.errors.append(f"orders.csv invalid status: {st}")

            req = float(r["requested_qty_kg"])
            ful = float(r["fulfilled_qty_kg"])

            if req < ful:
                self.errors.append(f"orders.csv invariant violated: requested ({req}) < fulfilled ({ful}) in {r['order_id']}")
            if ful < 0:
                self.errors.append(f"orders.csv negative fulfilled_qty_kg: {ful} in {r['order_id']}")

            # Status consistency
            if st == "fulfilled" and abs(req - ful) > 1e-4:
                self.errors.append(f"Order {r['order_id']} status is fulfilled but requested != fulfilled ({req} vs {ful})")
            if st == "partial" and (ful <= 0 or ful >= req):
                self.errors.append(f"Order {r['order_id']} status is partial but fulfilled is {ful} (requested {req})")
            if st in ("waitlisted", "cancelled_stockout", "cancelled_other") and ful > 0:
                self.errors.append(f"Order {r['order_id']} status is {st} but fulfilled is {ful} > 0")

            if ful > 0 and not r["delivered_date"]:
                self.errors.append(f"Order {r['order_id']} has fulfilled_qty > 0 but missing delivered_date")
            if ful == 0 and r["delivered_date"]:
                self.errors.append(f"Order {r['order_id']} has fulfilled_qty = 0 but delivered_date is set: {r['delivered_date']}")

    def _validate_nps(self, rows: List[Dict[str, str]], tables: Dict[str, List[Dict[str, str]]]):
        valid_regions = {r["region_id"] for r in tables.get("regions.csv", [])}
        valid_custs = {r["customer_id"] for r in tables.get("customers.csv", [])}
        valid_accs = {r["account_id"] for r in tables.get("b2b_accounts.csv", [])}

        for r in rows:
            if r["region_id"] not in valid_regions:
                self.errors.append(f"nps_responses.csv invalid region_id: {r['region_id']}")
            score = int(r["score"])
            if score < 0 or score > 10:
                self.errors.append(f"nps_responses.csv score must be 0-10, got: {score}")

            target = r["customer_or_account_id"]
            if r["channel"] == "D2C":
                if target not in valid_custs:
                    self.errors.append(f"nps_responses.csv D2C unknown customer_id: {target}")
            else:
                if target not in valid_accs:
                    self.errors.append(f"nps_responses.csv B2B unknown account_id: {target}")

    def _validate_capacity_fulfillment_conservation(self, tables: Dict[str, List[Dict[str, str]]]):
        """
        Verify aggregate capacity conservation:
        Total fulfilled kg over history must be <= total actual batch yields + total co-man delivered.
        """
        batches = tables.get("capacity_batches.csv", [])
        total_in_house_yield = sum(float(b["actual_yield_kg"]) for b in batches)

        coman = tables.get("coman_activity.csv", [])
        total_coman_delivered = sum(float(c["delivered_kg"]) for c in coman)

        orders = tables.get("orders.csv", [])
        total_fulfilled = sum(float(o["fulfilled_qty_kg"]) for o in orders)

        total_production = total_in_house_yield + total_coman_delivered

        if total_fulfilled > total_production + 1e-4:
            self.errors.append(
                f"Physical conservation violation: Total fulfilled kg ({total_fulfilled:.2f}) "
                f"exceeds total realized output ({total_production:.2f})"
            )
