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

### [2026-09-30 05:35 UTC+05:30] Named World Archetypes & Explicit Strategic Focus

The six worlds have been mapped into explicit, distinct business archetypes with tailored underlying dynamics:

#### Archetype & Blind Mapping Table

| Public ID | Archetype / Thematic Focus | Internal Config File | Seed | Key Strategic Focus / Phenomenon | Sealed YAML SHA-256 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`world_01`** | **High Volatility & High Risk** | `cfg_world_01_high_volatility_risk.yaml` | 42001 | Extreme macroeconomic and seasonal volatility. Navratri/Shravan fasting dips (-40%), high consumer price sensitivity, low repeat retention (26%), high churn, reactive marketing budget whipsaws, and heatwave cold-chain crisis. | `2e05da46025787e21b7b10a75b2a93306c4ff869b5ed59647d0906a98e301e15` |
| **`world_02`** | **Prime Standing & Operational Scale** | `cfg_world_02_prime_standing.yaml` | 42002 | Market leader with high customer retention (45% repeat, 20% subscribers), premium brand equity (NPS 8.9 baseline), predictable yields (2.5% failure), disciplined marketing, and reliable co-manufacturing reserves. | `5023559da92bae5017c5f9c719aa9f41ef66c112839e617d52f05db6aa9b9188` |
| **`world_03`** | **Viral Hypergrowth & Demand Surges** | `cfg_world_03_viral_hypergrowth.yaml` | 42003 | Aggressive digital ad efficiency (high CAC yield) and explosive crowdsourced word-of-mouth. Viral spikes at Week 40 & Week 92 cause sudden 2x+ demand surges that overwhelm bioreactor ceilings and trigger order waitlists. | `16825e8f1ddd52c7b2005d42a9f7946c4e6d2e9ff755cee73bc5fff883e69da1` |
| **`world_04`** | **Production Bottlenecks & Operational Distress** | `cfg_world_04_production_bottleneck.yaml` | 42004 | Chronic manufacturing fragility with high base batch failure rates (7% fail, 12% partial). Protracted monsoon media contamination crisis (Weeks 62-72) forces emergency reliance on expensive co-manufacturers, causing widespread order stockouts. | `2eb88e671c42a766b71634e7ca742729a0e14186ccc240dbf8ac7ad2a5d9990c` |
| **`world_05`** | **Structural Break & Strategic Transformation** | `cfg_world_05_structural_break.yaml` | 42005 | Significant structural break midway through history (Week 78). Six new Tier-1/Tier-2 cold-chain regional routes open simultaneously with the commercial launch of the Mycelium product line (`SKU-MYC-500G`) moving from pilot to production. | `ca38efaf23c8aaf44cf08f57727fae66d21522804a1ed0e580c0e6b4ac6dfced` |
| **`world_06`** | **B2B Key Account Concentration & Channel Squeeze** | `cfg_world_06_b2b_concentration.yaml` | 42006 | Extreme B2B wholesale concentration (>65% volume in a dominant 38-outlet QSR chain). Severe shortfall penalties (INR 250/kg) force ops to prioritize B2B and starve D2C e-commerce when output tightens. Major caterer churn at Week 75 creates inventory overhang and spoilage. | `71e2eaa1c60acc3deb0c179abdf9707c9e2e95ebe09cb68b76dd480881d50f83` |

#### Sequential Extension Drops
- **`world_01_drop2`**: Extends World 01 (High Volatility & High Risk) by 13 additional weeks (history: `2022-01-03` to `2025-03-30`, plan through `2025-06-29`).
- **`world_02_drop2`**: Extends World 02 (Prime Standing & Operational Scale) by 13 additional weeks (history: `2022-01-03` to `2025-03-30`, plan through `2025-06-29`).

---

### [2026-09-30 05:40 UTC+05:30] Full Validation Verification

- [x] **Contract Validation**: All drops (`out/world_01` through `out/world_06`, plus `world_01_drop2` and `world_02_drop2`) passed `dgp validate` with zero errors.
- [x] **Funnel Invariants**: Verified for all records (`bounces <= unique_visitors`, `leads <= unique_visitors - bounces`, `qualified_leads <= leads`, `conversions <= leads`).
- [x] **Order Constraints**: Strictly satisfied `requested_qty_kg >= fulfilled_qty_kg >= 0.0`.
- [x] **Physical Capacity Conservation**: Total fulfilled kg bounded by actual realized production.
- [x] **Zero Ground-Truth Leakage**: Clean text scan across all drops confirms zero occurrence of unblinded or forbidden terms (`true_`, `regime`, `viral`, `elasticity`, `shock`, `unobserved`, `ground_truth`).
- [x] **Deterministic Lineage**: Tested with pytest — identical seed produces byte-identical CSV tables.
