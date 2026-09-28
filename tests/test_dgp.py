"""Comprehensive tests for Biokraft DGP simulator and contract validation."""

import os
import shutil
import tempfile
import pytest
from dgp.config import WorldConfig
from dgp.world import WorldSimulator
from dgp.export.csv_writer import export_drop, compute_sha256
from dgp.validate.validator import ContractValidator, FORBIDDEN_WORDS


def test_determinism_same_seed():
    """Ensure identical config and seed produces byte-identical output across all tables."""
    cfg = WorldConfig.load_yaml("worlds/cfg_ordinary_growth.yaml")
    seed = 42001

    sim1 = WorldSimulator(cfg, seed)
    tables1, h_start1, h_end1, p_end1 = sim1.run_simulation()

    sim2 = WorldSimulator(cfg, seed)
    tables2, h_start2, h_end2, p_end2 = sim2.run_simulation()

    assert h_start1 == h_start2
    assert h_end1 == h_end2
    assert p_end1 == p_end2

    temp_dir1 = tempfile.mkdtemp()
    temp_dir2 = tempfile.mkdtemp()
    try:
        hashes1 = export_drop(temp_dir1, "world_01", h_start1, h_end1, p_end1, tables1, timestamp="2026-09-29T00:00:00Z")
        hashes2 = export_drop(temp_dir2, "world_01", h_start2, h_end2, p_end2, tables2, timestamp="2026-09-29T00:00:00Z")

        assert hashes1 == hashes2

        # Verify byte identity of each file
        for fname in hashes1.keys():
            path1 = os.path.join(temp_dir1, fname)
            path2 = os.path.join(temp_dir2, fname)
            with open(path1, "rb") as f1, open(path2, "rb") as f2:
                assert f1.read() == f2.read(), f"Byte mismatch in {fname}"
    finally:
        shutil.rmtree(temp_dir1)
        shutil.rmtree(temp_dir2)


def test_validation_and_invariants():
    """Run simulation and execute full validation suite."""
    cfg = WorldConfig.load_yaml("worlds/cfg_ordinary_growth.yaml")
    seed = 42001

    sim = WorldSimulator(cfg, seed)
    tables, h_start, h_end, p_end = sim.run_simulation()

    temp_dir = tempfile.mkdtemp()
    try:
        export_drop(temp_dir, "world_01", h_start, h_end, p_end, tables)

        validator = ContractValidator(temp_dir)
        success, errors, warnings = validator.validate_all()

        assert success is True, f"Validation errors: {errors}"
        assert len(errors) == 0
    finally:
        shutil.rmtree(temp_dir)


def test_no_forbidden_ground_truth_leakage():
    """Verify no forbidden ground-truth terms exist in exported CSVs."""
    cfg = WorldConfig.load_yaml("worlds/cfg_high_marketing_viral.yaml")
    seed = 42002

    sim = WorldSimulator(cfg, seed)
    tables, h_start, h_end, p_end = sim.run_simulation()

    temp_dir = tempfile.mkdtemp()
    try:
        export_drop(temp_dir, "world_02", h_start, h_end, p_end, tables)

        for root, _, files in os.walk(temp_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                    for word in FORBIDDEN_WORDS:
                        assert word not in content, f"Forbidden word '{word}' leaked in {fname}"
    finally:
        shutil.rmtree(temp_dir)
