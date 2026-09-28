"""Biokraft DGP CLI tool."""

import argparse
import os
import sys
from dgp.config import WorldConfig
from dgp.world import WorldSimulator
from dgp.export.csv_writer import export_drop
from dgp.validate.validator import ContractValidator
from dgp.sealed import generate_sealed_doc, write_and_hash_sealed


WORLD_ASSIGNMENTS = [
    ("world_01", "worlds/cfg_ordinary_growth.yaml", 42001, "Baseline ordinary trajectory with modest steady growth and standard festival dynamics"),
    ("world_02", "worlds/cfg_high_marketing_viral.yaml", 42002, "High marketing sensitivity with crowdsourced virality spikes, high referral rate, and fast customer acquisition"),
    ("world_03", "worlds/cfg_volatile_macro.yaml", 42003, "High macroeconomic and seasonal volatility, strong fasting dips, high price sensitivity and elevated churn"),
    ("world_04", "worlds/cfg_production_bottleneck.yaml", 42004, "Severe bioreactor yield volatility, summer contamination shocks, and heavy co-man reliance under shortfall pressure"),
    ("world_05", "worlds/cfg_structural_break.yaml", 42005, "Structural break midway: cold-chain regulatory opening into new regions and mycelium commercial pilot launch"),
    ("world_06", "worlds/cfg_b2b_concentration.yaml", 42006, "High B2B account concentration with massive QSR chains, shortfall penalties, and severe channel allocation conflict"),
]


def cmd_generate(args):
    print(f"Loading world config from {args.world}...")
    cfg = WorldConfig.load_yaml(args.world)
    print(f"Simulating '{cfg.world_name}' (Seed: {args.seed}, Extension: {args.extension_weeks} weeks)...")
    
    sim = WorldSimulator(cfg, args.seed)
    tables, h_start, h_end, p_end = sim.run_simulation(extension_weeks=args.extension_weeks)

    world_id = os.path.basename(os.path.normpath(args.out))
    print(f"Exporting Contract v1.0.0 drop to {args.out}...")
    print(f"History: {h_start} to {h_end} | Forward Plan: through {p_end}")

    file_hashes = export_drop(
        out_dir=args.out,
        world_id=world_id,
        history_start=h_start,
        history_end=h_end,
        plan_end=p_end,
        tables=tables,
    )

    print(f"Drop successfully exported to {args.out} (13 CSVs + manifest.json).")
    return 0


def cmd_validate(args):
    drop_dir = args.drop_dir
    print(f"Validating drop at {drop_dir} against Data Contract v1.0.0...")
    validator = ContractValidator(drop_dir)
    success, errors, warnings = validator.validate_all()

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  [WARN] {w}")

    if not success:
        print(f"\nVALIDATION FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  [ERROR] {err}")
        return 1
    else:
        print("\nVALIDATION PASSED: All 13 tables conform strictly to Contract v1.0.0.")
        print("  - Schema & headers match exactly")
        print("  - Enum constraints respected")
        print("  - Foreign keys verified")
        print("  - Funnel consistency invariant satisfied")
        print("  - requested_qty >= fulfilled_qty invariant satisfied")
        print("  - Physical capacity conservation satisfied")
        print("  - Zero forbidden ground-truth words detected")
        return 0


def cmd_seal(args):
    sealed_dir = getattr(args, "sealed_dir", "sealed")
    os.makedirs(sealed_dir, exist_ok=True)
    print("=" * 70)
    print("BIOKRAFT DGP — COMMIT TO TRUTH & SEAL WORLDS")
    print("=" * 70)

    results = []
    for world_id, cfg_path, seed, mapping_note in WORLD_ASSIGNMENTS:
        if not os.path.exists(cfg_path):
            print(f"Skipping {world_id}: {cfg_path} not found.")
            continue
        cfg = WorldConfig.load_yaml(cfg_path)
        doc = generate_sealed_doc(world_id, cfg, seed, mapping_note)
        out_path, sha256_hash = write_and_hash_sealed(sealed_dir, world_id, doc)
        results.append((world_id, out_path, sha256_hash, mapping_note))
        print(f"Sealed {world_id:10s} -> {out_path}")
        print(f"  SHA-256: {sha256_hash}")

    print("=" * 70)
    print("Record these SHA-256 hashes in DGP_NOTES.md at handoff:")
    for wid, _, hsh, note in results:
        print(f"  {wid}: {hsh} ({note})")
    print("=" * 70)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Biokraft Data Generating Process (DGP) CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Generate
    gen_parser = subparsers.add_parser("generate", help="Generate a synthetic world drop")
    gen_parser.add_argument("--world", required=True, help="Path to world YAML configuration")
    gen_parser.add_argument("--seed", type=int, required=True, help="Integer random seed")
    gen_parser.add_argument("--out", required=True, help="Output directory (e.g. out/world_01)")
    gen_parser.add_argument("--extension-weeks", type=int, default=0, help="Additional weeks to simulate (for sequential drops)")
    gen_parser.set_defaults(func=cmd_generate)

    # Validate
    val_parser = subparsers.add_parser("validate", help="Validate an output drop against Data Contract v1.0.0")
    val_parser.add_argument("drop_dir", help="Path to output drop directory")
    val_parser.set_defaults(func=cmd_validate)

    # Seal
    seal_parser = subparsers.add_parser("seal", help="Seal world ground truths and output SHA-256 hashes")
    seal_parser.add_argument("--sealed-dir", default="sealed", help="Directory to save sealed truth YAMLs")
    seal_parser.set_defaults(func=cmd_seal)

    parsed = parser.parse_args()
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
