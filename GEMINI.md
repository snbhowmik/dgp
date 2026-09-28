# GEMINI.md — Biokraft Data Generating Process (DGP)

> Place this file at the root of the **`biokraft-dgp`** repository. Gemini CLI loads `GEMINI.md` automatically as project context.
> This repository must stay **separate** from `biokraft-dce` (the planning app). Never copy files between them except the CSV drops described in §8.

---

## 1. Your role

You are building a **synthetic world simulator** for a food manufacturer. It produces realistic historical business data: orders, production batches, co-manufacturing, B2B accounts, marketing performance, customers, and satisfaction.

A different team, using a different AI, is building a planning app that will **forecast demand and recommend capacity allocation** from your data. They will never see your code, equations, parameters, or world descriptions. They receive only CSV files matching the data contract in §7.

**The one rule:** you design the hidden "truth" of each world yourself. Nobody on the app side has told you, or will tell you, what functional forms, parameter values, or effect sizes to use. Choose what you believe is realistic for this business. Do not try to make the data easy or hard for any particular forecasting method. You have not been told which methods the app uses, and you should not ask.

---

## 2. The business you are simulating

**Biokraft Foods Private Limited** is an Indian alternative-protein company.

- **Commercial product today:** cultivated chicken (perishable).
- **R&D pipeline:** seaweed-based, microbial-protein (fermentation), and mycelium-based products. These may move from R&D → pilot → production over time.
- **Channels:**
  - **D2C e-commerce**, selling to individual consumers across regions with cold-chain delivery.
  - **B2B wholesale**, selling to restaurants, QSR chains, hotels, caterers, and distributors, usually with committed monthly volumes, contract prices, and shortfall penalties.
- **Production:**
  - **In-house bioreactor batches**, where yield varies and batches can fail.
  - **Co-manufacturing partners**, which have activation lead times, minimum commitments, maximum volumes, and a cost premium.
- **The central tension:** total output has a **hard ceiling**. When demand exceeds it, orders are waitlisted, partially filled, or cancelled. When output exceeds demand, perishable product goes to waste.
- **Marketing:** spend by region and campaign type (PPC, native, social, influencer, email, trade) drives visitors, leads, and customers through a funnel, with delays.

The company's people behave like real people. The marketing team reacts to what it sees. Sales chases big accounts. Ops plans batches ahead. Nobody has perfect information.

---

## 3. Isolation rules

1. Do not read, fetch, or search for anything from the `biokraft-dce` repository.
2. Do not include any **ground-truth labels** in the output CSVs. For example, no "true demand" column, no "viral event" flag, no true elasticity or adstock values, no "regime" field, and no causal-attribution columns. The app must infer all of these, as it would with real company data.
3. `manifest.json` in each drop must **not** describe the world's character. It carries only the contract version, date range, and generation timestamp (§8).
4. World descriptions and parameters live only in `sealed/` (§6.3) and are released only when the app team formally requests unblinding after freezing its results.
5. If a contract field seems wrong or missing, record it in `DGP_NOTES.md` as a contract issue. Do not change the contract unilaterally; the contract is shared and versioned.

---

## 4. What to build

### 4.1 Repository layout (suggested)
```
biokraft-dgp/
├── GEMINI.md               # this file
├── DGP_NOTES.md            # your decision + generation log (append-only)
├── pyproject.toml
├── dgp/
│   ├── world.py            # world config → full simulation
│   ├── agents/             # consumers, B2B accounts, marketing team, ops/production
│   ├── funnel/             # spend → visitors → leads → customers → repeat
│   ├── production/         # batches, yield, failures, co-man
│   ├── fulfillment/        # allocation under capacity, waitlist, stockouts, waste
│   ├── export/             # contract-conformant CSV writers
│   └── validate/           # contract + sanity checks
├── worlds/                 # world configs (PRIVATE — never shipped)
├── sealed/                 # sealed world descriptions + hashes (PRIVATE)
├── out/<world_id>/         # generated drops (the only thing shipped)
└── tests/
```

### 4.2 Interface
```bash
dgp generate --world worlds/<name>.yaml --seed <int> --out out/world_01
dgp validate out/world_01
dgp seal     # writes sealed/world_01.yaml + prints its SHA-256
```
Same config + same seed must give byte-identical output.

### 4.3 Simulation approach
Prefer an **agent-based or process-based simulation** over directly drawing numbers for each output column. Simulate customers moving through the funnel, accounts placing orders, batches being run, and a fulfillment step that allocates limited output. Then **derive** the CSVs from what happened. This produces the internal consistency that real data has: orders that reference real customers, fulfilled quantities that respect capacity, NPS that responds to service quality, and so on.

---

## 5. Mechanisms each world must contain

You choose every functional form and parameter. The list below says **which phenomena must exist**, not how they behave numerically.

### 5.1 Marketing funnel
The world should represent these concepts, with the business meanings they have in performance marketing:

- **Spend** by region, campaign type, and date, including **pay-per-click** and **native advertising**.
- **Unique visitors**, **bounce rate**, the effect of **call-to-action** quality and **conversion rate optimization** (visible only as differences in conversion across campaigns and over time), **cost per lead**, **qualified leads** (shaped by **buyer persona** fit), and **conversion rate**.
- **Lifecycle stages** (awareness → evaluation → purchase), which take time. Spend and orders are not simultaneous.
- **Customer acquisition cost**, **churn rate**, repeat purchasing, **lifetime value**, and **LTV:CAC**. These should emerge from the simulation, not be set as outputs.
- **Monthly recurring revenue**, from B2B contracts and any D2C subscribers.
- **Net promoter score**, which responds to the customer's actual experience.
- **Word of mouth** and **crowdsourced content**, meaning organic demand not bought with spend.
- **Viral content**: rare, spend-independent demand surges.
- **Closed-loop marketing** as company behavior: the simulated marketing team adjusts spend based on what it observes.
- **Customer relationship management**, reflected in `customers.csv` and `b2b_accounts.csv`.
- **Return on investment**, which is not an output column but should be *computable* from the data.
- **Product matrix**: which SKUs can be sold in which channel and region, and when.

### 5.2 Realism requirements
- **Censoring:** when output runs short, some demand is waitlisted, partially filled, or lost. Record these honestly in order statuses so that `requested_qty_kg` ≥ `fulfilled_qty_kg`.
- **Perishability:** product has a shelf life, so surplus cannot be stored indefinitely.
- **Production uncertainty:** batch yield varies, and some batches fail or partially fail.
- **Co-manufacturing:** partners have lead times and minimums. The simulated company uses them at some points in history, with imperfect delivery.
- **B2B behavior:** accounts don't always order exactly their commitment. Accounts onboard, churn, pause, and renew. Some pipeline accounts exist at the end of history.
- **Regional heterogeneity:** regions differ in size, responsiveness, cost to reach, and cold-chain availability.
- **Realistic marketing decisions:** the simulated marketing team sets spend partly *in response to* what it sees in demand, as real teams do. Spend is not randomly assigned.
- **Ad-platform attribution:** `attributed_revenue_inr` should behave like real platform-reported attribution, not like the true causal effect of spend.
- **Plans vs. reality:** `capacity_plan.csv` and `marketing_plan.csv` are what the company *planned*. Actual batches and actual spend can deviate from plan.
- **Calendar:** Indian seasonality and festivals may matter if you judge they would for this product.
- **Product pipeline:** at least one R&D/pilot product line exists in `skus.csv`. In some worlds, a pilot launch happens during history in a limited region.
- **Mild real-world messiness** that still conforms to the schema: zero-spend weeks, sparse NPS responses, late deliveries, and similar.

---

## 6. Worlds

### 6.1 How many and how they differ
Produce **six worlds**. They should differ from one another in **meaningful underlying dynamics**, not just random seeds. You decide which dimensions to vary and how strongly. Plausible dimensions include demand seasonality, sensitivity to marketing, production reliability, B2B concentration, organic growth, and shock frequency, but you are free to choose others. At least one world should be close to "ordinary". At least one should contain a structural change partway through history.

### 6.2 Size bounds
These are operational limits for the app, not hints about dynamics:
- History length: **130–260 weeks** per world. The app holds out the final 13 weeks for evaluation.
- Forward plans: `capacity_plan.csv` and `marketing_plan.csv` extend **13 weeks beyond** the last history date.
- **5–20 regions**, **5–50 B2B accounts** (all statuses combined), and **1–6 SKUs**.

### 6.3 Blind naming and sealing
- Ship worlds as `world_01` … `world_06`, assigned to your configs in **random order**, and record the mapping only in `sealed/`.
- For each world, `sealed/world_xx.yaml` contains a plain-language description of the world, every parameter and functional form used, and notable events with dates (shocks, launches, structural breaks).
- Run `dgp seal` and record each sealed file's **SHA-256** in `DGP_NOTES.md` **at handoff**. This commits you to the truth before the app team evaluates, so nobody can later change it.

### 6.4 Sequential drops (closed-loop demo)
For **one** of the six worlds, also produce a second drop, `world_0X_drop2`. It continues the same simulation for 13 more weeks, with the same hidden truth and the same seed lineage, conforming to the same contract.

---

## 7. Data contract v1.0.0 (must match exactly)

**Conventions:** ISO dates `YYYY-MM-DD`. Weeks start **Monday**. Currency INR. Quantities in **kg**. CSV with a header row, UTF-8, comma separator. Empty cell = null. Booleans `true`/`false`. Column names and enum values exactly as written. Pipe-separated lists where noted.

### 7.1 `regions.csv`
| column | type | notes |
|---|---|---|
| region_id | str | PK |
| region_name | str | |
| tier | str | e.g. metro / tier1 / tier2 |
| cold_chain_available | bool | |

### 7.2 `skus.csv`
| column | type | notes |
|---|---|---|
| sku_id | str | PK |
| product_line | str | `cultivated_chicken` / `mycelium` / `seaweed` / `microbial` |
| pack_size_kg | float | |
| status | enum | `rnd` / `pilot` / `production` / `retired` |
| expected_launch_date | date? | |
| shelf_life_days | int | |
| unit_cost_inr_per_kg | float | |
| list_price_d2c_inr_per_kg | float | |

### 7.3 `product_matrix.csv`
| column | type | notes |
|---|---|---|
| sku_id | str | FK skus |
| channel | enum | `D2C` / `B2B` |
| region_id | str | FK regions |
| eligible_from | date | |
| eligible_to | date? | |

### 7.4 `orders.csv`
| column | type | notes |
|---|---|---|
| order_id | str | PK |
| order_date | date | when requested |
| channel | enum | `D2C` / `B2B` |
| region_id | str | FK |
| sku_id | str | FK |
| customer_id | str? | D2C only, FK customers |
| account_id | str? | B2B only, FK b2b_accounts |
| requested_qty_kg | float | ≥ fulfilled |
| fulfilled_qty_kg | float | |
| unit_price_inr | float | |
| status | enum | `fulfilled` / `partial` / `waitlisted` / `cancelled_stockout` / `cancelled_other` |
| promised_date | date | |
| delivered_date | date? | null if not delivered |

### 7.5 `capacity_batches.csv`
| column | type | notes |
|---|---|---|
| batch_id | str | PK |
| start_date | date | |
| end_date | date | |
| facility_id | str | |
| product_line | str | |
| planned_yield_kg | float | |
| actual_yield_kg | float | 0 if failed |
| outcome | enum | `success` / `partial` / `failed` |

### 7.6 `capacity_plan.csv`
| column | type | notes |
|---|---|---|
| week_start | date | history + 13 weeks ahead |
| facility_id | str | |
| product_line | str | |
| planned_batches | int | |
| planned_yield_per_batch_kg | float | |

### 7.7 `coman_contracts.csv`
| column | type |
|---|---|
| coman_id | str (PK) |
| product_line | str |
| available_from | date |
| lead_time_weeks | int |
| min_commit_kg_per_week | float |
| max_kg_per_week | float |
| unit_cost_inr_per_kg | float |
| min_active_weeks | int |

### 7.8 `coman_activity.csv`
| column | type |
|---|---|
| coman_id | str (FK) |
| week_start | date |
| requested_kg | float |
| delivered_kg | float |

### 7.9 `b2b_accounts.csv`
| column | type | notes |
|---|---|---|
| account_id | str | PK |
| account_type | enum | `restaurant` / `qsr_chain` / `hotel` / `caterer` / `distributor` / `other` |
| region_id | str | primary region |
| regions_served | str | pipe-separated region_ids |
| outlets_count | int | |
| status | enum | `active` / `pipeline` / `churned` / `paused` (as of history end) |
| onboarded_date | date? | |
| contract_start | date? | |
| contract_end | date? | |
| committed_kg_per_month | float? | |
| contract_price_inr_per_kg | float? | |
| shortfall_penalty_inr_per_kg | float? | |
| requested_start_date | date? | pipeline only |
| requested_kg_per_month | float? | pipeline only |

### 7.10 `marketing_daily.csv`
| column | type |
|---|---|
| date | date |
| region_id | str |
| channel | enum `D2C` / `B2B` |
| campaign_type | enum `ppc` / `native` / `social` / `influencer` / `email` / `trade` |
| campaign_id | str |
| spend_inr | float |
| impressions | int |
| clicks | int |
| unique_visitors | int |
| bounces | int |
| leads | int |
| qualified_leads | int |
| conversions | int |
| attributed_revenue_inr | float |

Funnel counts must be internally consistent: bounces ≤ unique_visitors, leads ≤ unique_visitors − bounces, qualified_leads ≤ leads, conversions ≤ leads.

### 7.11 `marketing_plan.csv`
| column | type |
|---|---|
| week_start | date |
| region_id | str |
| channel | enum |
| campaign_type | enum |
| planned_spend_inr | float |

### 7.12 `customers.csv`
| column | type | notes |
|---|---|---|
| customer_id | str | PK |
| region_id | str | |
| acquired_date | date | |
| acquisition_campaign_type | enum? | null = organic / word of mouth |
| persona_segment | str | |
| churned_date | date? | per a company churn rule you define (e.g. inactivity) |
| is_subscriber | bool | |

### 7.13 `nps_responses.csv`
| column | type |
|---|---|
| response_date | date |
| channel | enum |
| region_id | str |
| customer_or_account_id | str |
| score | int 0–10 |

---

## 8. Drop format and handoff

Each drop is a folder:
```
out/world_01/
├── manifest.json
├── regions.csv  skus.csv  product_matrix.csv  orders.csv
├── capacity_batches.csv  capacity_plan.csv
├── coman_contracts.csv  coman_activity.csv
├── b2b_accounts.csv  marketing_daily.csv  marketing_plan.csv
├── customers.csv  nps_responses.csv
```

`manifest.json` contains **only** these fields:
```json
{
  "world_id": "world_01",
  "contract_version": "1.0.0",
  "history_start": "YYYY-MM-DD",
  "history_end": "YYYY-MM-DD",
  "plan_end": "YYYY-MM-DD",
  "generated_at": "ISO-8601 timestamp",
  "files": {"orders.csv": "<sha256>", "...": "..."}
}
```

**Handoff checklist:**
- [ ] `dgp validate` passes for every drop: schema, enums, FKs, funnel consistency, `requested ≥ fulfilled`, fulfilled totals per week ≤ realized output (in-house + co-man + allowed carryover).
- [ ] No ground-truth or regime information in any shipped file (grep the drop for words like `true_`, `viral`, `regime`, `elasticity`, `shock`).
- [ ] Sealed-file SHA-256 values recorded in `DGP_NOTES.md`.
- [ ] Only `out/` folders are copied to the app side, into `biokraft-dce/data/incoming/`.

---

## 9. Unblinding protocol

The app team requests unblinding only after it has frozen its evaluation report and recorded that report's hash. On request:
1. Release `sealed/world_xx.yaml` files.
2. The receiving side verifies each file against the SHA-256 recorded at handoff.
3. Log the release in `DGP_NOTES.md`.

---

## 10. Optional later phase: interactive replay

If requested later, expose the simulator as an environment API: `reset(world, seed)` → history, and `step(decisions)` → next week's CSV rows. Here `decisions` are the app's allocation, spend, and onboarding choices, and the world reacts to them (for example, stockouts affect NPS and future demand). The API returns only contract-shaped data, never internal state. Do not build this until asked.

---

## 11. Logging (`DGP_NOTES.md`)

Keep an append-only log with:
- design decisions (functional forms and agent behaviors chosen, and why you consider them realistic);
- one private entry per world config, with its random `world_xx` assignment;
- validation results per drop;
- contract issues found;
- sealed-file hashes at handoff;
- unblinding releases.

`DGP_NOTES.md` is **private** to this repository until unblinding.
