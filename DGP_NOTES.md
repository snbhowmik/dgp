# Biokraft DGP — Decision & Generation Log (Private)

> **CONFIDENTIAL**: This file is append-only and private to the DGP simulator team.
> Contains ground-truth mappings, world generation seeds, architectural rationale, and validation hashes.

---

## Log Entries

### [2026-09-29 04:30 UTC+05:30] Simulator Initialization & Architectural Decisions

#### 1. Core Simulation Architecture: Process- & Agent-Based Modeling
Rather than sampling independent random variables directly for table columns, the DGP implements a dynamic, coupled, agent- and process-based simulation:
- **Time Representation**: Discrete daily steps aggregated into standard Monday-starting ISO weeks (`YYYY-MM-DD`).
- **Calendar & Indian Market Context**: Indian national holidays, regional festival spikes (e.g., Diwali, Dussehra, Durga Puja, Eid, New Year) and fasting/vegetarian observance periods (e.g., Navratri, Shravan) where non-vegetarian protein consumption dips and alternative-protein demand fluctuates based on positioning.
- **Funnel & Marketing**:
  - Closed-loop marketing decision agent that reviews trailing performance (CPA, qualified leads, ROAS, stockout feedback) and adjusts weekly plans and daily budgets across regions and campaign types (PPC, native, social, influencer, email, trade).
  - Ad-platform reporting model: platforms attribute revenue via standard attribution models (e.g. 7-day click / 1-day view attribution with typical platform inflation/overlap), distinctly separated from true incremental causal lift.
  - Funnel conservation: Strict invariant enforcement (`bounces <= unique_visitors`, `leads <= unique_visitors - bounces`, `qualified_leads <= leads`, `conversions <= leads`).
  - Organic dynamics: Word-of-mouth (WOM) driven by active happy customers, crowdsourced virality bursts (rare exogenous or endogenous spikes), and decay.
- **Customers & Personas**:
  - D2C consumer agents with explicit personas (e.g. *Fitness/Biohacker*, *Ethical Vegan/Flexitarian*, *Eco-conscious Gourmet*, *Curious Early Adopter*), regional affinity, sensitivity to delivery delays and stockouts.
  - Subscription vs one-off purchase behaviors.
  - Dynamic churn rule: Consumers who do not place a repeat order within $N$ expected reorder cycles ($90$–$120$ days) are marked churned.
  - Experience-driven NPS: NPS survey responses generated post-fulfillment reflecting actual order experience (stockout, partial fulfillment, delivery delay, cold-chain integrity).
- **B2B Wholesale Accounts**:
  - Realistic accounts across restaurant, QSR chain, hotel, caterer, and distributor archetypes with multi-region distribution networks (`regions_served` pipe-separated).
  - Monthly commitment contracts with minimums, contract pricing, and shortfall penalties.
  - Order variability around monthly commitment, onboarding lag, contract renewals, pauses, and pipeline states at history end.
- **Production & Bioreactors**:
  - In-house facility bioreactors running discrete fermentation/culture batches over multi-day batch cycles.
  - Yield modeled via stochastic distribution (e.g. Beta/Weibull-scaled planned yield) with realistic contamination/mechanical failure probabilities (success, partial, failed).
  - Co-manufacturing (co-man) contracts with activation lead times, weekly minimum commitments, maximum capacity ceilings, and premium unit costs.
- **Fulfillment & Perishable Inventory**:
  - Strict FEFO/FIFO inventory tracking of production lots with realistic shelf lives (e.g., 14–28 days for chilled cultivated meat).
  - Hard capacity ceiling: when aggregate daily/weekly demand exceeds available inventory, an allocation policy resolves priority: committed B2B accounts (subject to shortfall penalties) vs D2C orders.
  - Censoring: unfulfilled demand is waitlisted, partially filled, or marked `cancelled_stockout`. The fundamental invariant `requested_qty_kg >= fulfilled_qty_kg` is strictly preserved.
  - Spoilage: inventory exceeding shelf life without fulfillment is recorded as waste/spoilage.
  - Internal physical consistency: fulfilled totals per week are bounded by available physical inventory (in-house yield + co-man delivery + viable carryover - waste).

#### 2. Determinism & Sealing Protocol
- Every simulation run is strictly deterministic given `(world_config, seed)`.
- Command line interface: `dgp generate`, `dgp validate`, `dgp seal`.
- Output CSVs conform 100% to Data Contract v1.0.0 with zero ground-truth leakage.

---

### [2026-09-29 05:25 UTC+05:30] World Configuration Rationale & Blind Assignments

The six worlds have been mapped blindly via random permutation (`seed=20260929`). The mapping is recorded privately here and in `sealed/`.

#### Blind Mapping Table

| Public ID | Internal Config | Random Seed | Description / Underlying Dynamics | Sealed SHA-256 Hash |
| :--- | :--- | :--- | :--- | :--- |
| `world_01` | `cfg_ordinary_growth.yaml` | 42001 | Baseline ordinary growth (14% annual), balanced D2C/B2B, standard Indian festival cycles, low batch failures. | `ee5fac8bdf0c907632070657ac728d349855de5bc4cb153521aeda9bc644550d` |
| `world_02` | `cfg_high_marketing_viral.yaml` | 42002 | Explosive organic virality and digital responsiveness. Surges at Week 40 & Week 92 trigger severe demand spikes and temporary order waitlists. | `d82d7579ee35270788c292daec8d8a8da5367e6c2ac493459b2bc13c6116f7a0` |
| `world_03` | `cfg_volatile_macro.yaml` | 42003 | High macroeconomic and seasonal volatility. Deep fasting drops during Navratri/Shravan, sharp winter wedding peaks, high D2C churn. | `be2e885d769718e305fce4ffcf13513b7e63b1b2366a092c64e8cb3092a663a1` |
| `world_04` | `cfg_production_bottleneck.yaml` | 42004 | Severe bioreactor yield volatility. Extended monsoon media contamination crisis (Weeks 62-72) forces emergency co-man activation at high cost. | `df7edcac553e37d187db6c56077b17d8f81c8641c261f5f5caecf86372dda521` |
| `world_05` | `cfg_structural_break.yaml` | 42005 | Structural break at Week 78: 6 new Tier-1/Tier-2 cold chains opened + Mycelium (SKU-MYC-500G) commercial launch from R&D/pilot to production. | `054a36db33c32202d6150d53c4413235c4f3cb94a9673732d79602734f7427b8` |
| `world_06` | `cfg_b2b_concentration.yaml` | 42006 | Extreme B2B wholesale concentration (>65% volume in large QSR chains). Severe shortfall penalties force D2C rationing and cause D2C customer churn. | `b467711b89e5b5438d10d9a4d8ebaeda83caeb5dd20e34ecb00d12161996b372` |

#### Sequential Extension Drop
- `world_01_drop2`: Continuous continuation of `world_01` for an additional 13 weeks (total history 169 weeks: `2022-01-03` to `2025-03-30`), with forward plans extending through `2025-06-29`. Maintains exact seed lineage and contract consistency.

---

### [2026-09-29 05:26 UTC+05:30] Validation & Handoff Checklist Verification

- [x] **Schema & Headers**: All 13 CSV tables strictly match the column names, ordering, and data types of Contract v1.0.0.
- [x] **FK Constraints**: All foreign keys between regions, SKUs, product matrix, customers, B2B accounts, orders, and co-man contracts verified.
- [x] **Funnel Invariants**: Verified for all records in `marketing_daily.csv`:
  - `bounces <= unique_visitors`
  - `leads <= unique_visitors - bounces`
  - `qualified_leads <= leads`
  - `conversions <= leads`
- [x] **Order Fulfillment Invariants**: Verified `requested_qty_kg >= fulfilled_qty_kg >= 0.0`. Statuses match fulfilled amounts. Delivered date set iff fulfilled > 0.
- [x] **Physical Capacity Conservation**: Total fulfilled kg over history strictly bounded by total realized output (in-house actual batch yield + co-man delivered).
- [x] **Zero Ground-Truth Leakage**: Grep scan across all files in all drops confirms zero occurrence of forbidden terms (`true_`, `regime`, `viral`, `elasticity`, `shock`, `unobserved`, `ground_truth`).
- [x] **Deterministic Sealing**: SHA-256 hashes generated via `dgp seal` committed to this document prior to handoff.
- [x] **Sequential Drop Verification**: `world_01_drop2` verified against `world_01` — static reference tables (`regions.csv`, `skus.csv`, `product_matrix.csv`, `coman_contracts.csv`) produce identical SHA-256 hashes across both drops.
