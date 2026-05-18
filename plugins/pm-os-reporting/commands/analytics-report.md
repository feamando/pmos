---
description: Google Analytics funnel reports, traffic analysis, and conversion reporting
---

# /analytics-report -- Analytics Reporting (GA4 + Databricks)

Parse the arguments to determine which report type and parameters to use:

| Report Type | Description |
|-------------|-------------|
| `--funnel-analysis` | Acquisition funnel breakdown with step-by-step drop-offs |
| *(more to come)* | Traffic, retention, channel, experiment reports |

## Arguments
$ARGUMENTS

## Parameters

| Parameter | Required | Format | Description |
|-----------|----------|--------|-------------|
| `--funnel-analysis` | Yes (report type) | flag | Generate acquisition funnel report |
| `--brand` | Yes | String | Brand name: `The Pets Table`, `Good Chop`, `HelloFresh`, `Factor`, `Green Chef`, `YouFoodz`, `Chefs Plate`, `EveryPlate` |
| `--market` | No | Comma-separated | Market codes: `US`, `DE`, `UK`, `CA`, `AU`, `NL`, `BE`, `FR`, `IT`, `AT`, `CH`, `SE`, `DK`, `NO`, `NZ`, `ES`, `IE`, `LU`. Defaults to primary market for brand. |
| `--timeframe` | Yes | `YYYYMMDD-YYYYMMDD` | Date range for the report |
| `--xbrand-compliant` | No | flag | Exclude active subscribers from funnel (prospect-only). Matches xbrand SQL logic: removes post-activation sessions, uses engaged users only. |
| `--single-session` | No | flag | Only count users who completed their funnel journey in a single session (first visit). Excludes multi-session prospects who returned. Combines with `--xbrand-compliant`. GA4 filter: `newVsReturning = "new"`. |
| `--orthogonal` | No | flag | Pull data from both GA4 and Databricks, present side-by-side comparison with delta analysis. Produces a unified report with both sources. |

## Data Sources

| Source | Tool | What It Provides |
|--------|------|-----------------|
| **GA4** | `mcp__analytics-mcp__run_report` | User-level funnel (totalUsers), event-based signals, real-time |
| **Databricks** | `mcp__databricks__execute_sql` or direct SQL API | Session-level funnel, net conversions (2WK/5WK), empty conversion rates, backend activation |

When `--orthogonal` is set, query BOTH sources and produce a combined report. Otherwise default to GA4 only.

**Databricks table:** `public_glue.private_growth_intermediate_layer_live.funnel_prospects_session_level_xbrand_enriched_ow`
- Partition key: `fk_date` (integer YYYYMMDD)
- Brand filter: `brand` column (values: `HelloFresh`, `GoodChop`, `Factor75`, `GreenChef`, `EveryPlate`, `ChefsPlate`, `YouFoodz`, `The Pets Table`)
- Warehouse ID: read from `.mcp.json` env `DATABRICKS_SQL_WAREHOUSE_HTTP_PATH` (extract ID after `/warehouses/`)

**Brand name mapping (display name to Databricks value):**

| Brand (input) | Databricks `brand` value |
|---------------|--------------------------|
| The Pets Table | The Pets Table |
| Good Chop | GoodChop |
| HelloFresh | HelloFresh |
| Factor | Factor75 |
| Green Chef | GreenChef |
| EveryPlate | EveryPlate |
| Chefs Plate | ChefsPlate |
| YouFoodz | YouFoodz |

## Report Storage

All reports are stored at a canonical path:

```
user/products/<product-kebab>/analytics/report/<report-type>/<brand>-<creation-date>-<report-type>-<report-name>.md
```

**Path components:**

| Component | Format | Example |
|-----------|--------|---------|
| `<product-kebab>` | kebab-case product folder | `the-pets-table`, `good-chop` |
| `<report-type>` | kebab-case report type | `funnel-analysis`, `traffic`, `retention` |
| `<brand>` | kebab-case brand | `the-pets-table`, `good-chop` |
| `<creation-date>` | `YYYY-MM-DD` (today's date) | `2026-05-07` |
| `<report-name>` | descriptive slug from timeframe/context | `dec-2025-prospects`, `q1-2026-all-traffic` |

**Examples:**
```
user/products/the-pets-table/analytics/report/funnel-analysis/the-pets-table-2026-05-07-funnel-analysis-dec-2025-prospects.md
user/products/good-chop/analytics/report/funnel-analysis/good-chop-2026-05-07-funnel-analysis-apr-2026-xbrand.md
user/products/the-pets-table/analytics/report/funnel-analysis/the-pets-table-2026-05-07-funnel-analysis-dec-2025-orthogonal.md
```

Create intermediate directories if they don't exist.

## No Arguments -- Show Help

If no arguments provided, display:

```
Analytics Report -- GA4 + Databricks Analytics Reporting

  /analytics-report --funnel-analysis --brand "The Pets Table" --timeframe 20251201-20251231
  /analytics-report --funnel-analysis --brand "Good Chop" --market US --timeframe 20260401-20260430
  /analytics-report --funnel-analysis --brand "Factor" --market US,CA --timeframe 20260101-20260131 --xbrand-compliant
  /analytics-report --funnel-analysis --brand "The Pets Table" --timeframe 20251201-20251231 --xbrand-compliant --single-session
  /analytics-report --funnel-analysis --brand "The Pets Table" --timeframe 20251201-20251231 --orthogonal

Report Types:
  --funnel-analysis    Acquisition funnel with step-by-step drop-offs and CVR

Data Sources:
  GA4                  Google Analytics 4 (user-level, event-based)
  Databricks           Backend session-level funnel with net conversions

Options:
  --brand              Brand name (required)
  --market             Market code(s), comma-separated (default: brand primary market)
  --timeframe          Date range as YYYYMMDD-YYYYMMDD (required)
  --xbrand-compliant   Exclude active subscribers (prospect sessions only)
  --single-session     Only count first-visit users (no multi-session prospects)
  --orthogonal         Pull from both GA4 and Databricks, produce side-by-side comparison

Storage:
  Reports saved to: user/products/<product>/analytics/report/<type>/<brand>-<date>-<type>-<name>.md

Usage: /analytics-report --funnel-analysis --brand <brand> --timeframe <range> [--market <codes>] [--xbrand-compliant] [--single-session] [--orthogonal]
```

---

## Brand to GA4 Property Mapping

| Brand | Market | Property ID | Display Name |
|-------|--------|-------------|--------------|
| The Pets Table | US | 351791540 | [Website] The Pets Table US |
| Good Chop | US | 311882232 | [Website] Good Chop US |
| Good Chop | US (Shopify) | 526248433 | [Website] Good Chop - Shopify |
| HelloFresh | US | 312063326 | [Website] HelloFresh US |
| HelloFresh | DE | 311925039 | [Website] HelloFresh DE |
| HelloFresh | UK | 312027295 | [Website] HelloFresh UK |
| HelloFresh | CA | 311886066 | [Website] HelloFresh CA |
| HelloFresh | AU | 311922893 | [Website] HelloFresh AU |
| HelloFresh | NL | 311899083 | [Website] HelloFresh NL |
| HelloFresh | BE | 311919877 | [Website] HelloFresh BE |
| HelloFresh | AT | 311719107 | [Website] HelloFresh AT |
| HelloFresh | CH | 311948752 | [Website] HelloFresh CH |
| HelloFresh | FR | 311924732 | [Website] HelloFresh FR |
| HelloFresh | IT | 311910280 | [Website] HelloFresh IT |
| HelloFresh | SE | 312090460 | [Website] HelloFresh SE |
| HelloFresh | DK | 311881635 | [Website] HelloFresh DK |
| HelloFresh | NO | 311946824 | [Website] HelloFresh NO |
| HelloFresh | NZ | 312021247 | [Website] HelloFresh NZ |
| HelloFresh | ES | 327358851 | [Website] HelloFresh ES |
| HelloFresh | IE | 327729395 | [Website] HelloFresh IE |
| HelloFresh | LU | 311888003 | [Website] HelloFresh LU |
| Factor | US | 311927763 | [Website] Factor US |
| Factor | CA | 311880190 | [Website] Factor CA |
| Factor | NL | 360688536 | [Website] Factor NL |
| Factor | BE | 360691936 | [Website] Factor BE |
| Factor | SE | 429374439 | [Website] Factor SE |
| Factor | DK | 429389480 | [Website] Factor DK |
| Factor | DE | 454987567 | [Website] Factor DE |
| Factor | US (Shopify/VMS) | 514837615 | [Website] Factor Form - Shopify |
| Green Chef | US | 311932300 | [Website] Green Chef US |
| Green Chef | UK | 311905264 | [Website] Green Chef UK |
| Green Chef | NL | 311943661 | [Website] Green Chef NL |
| EveryPlate | US | 311932106 | [Website] EveryPlate US |
| EveryPlate | AU | 311734672 | [Website] EveryPlate AU |
| YouFoodz | AU | 317507525 | [Website] Youfoodz AU |
| Chefs Plate | CA | 311719310 | [Website] Chefs Plate CA |

**Default markets:** The Pets Table = US, Good Chop = US, Factor = US, Green Chef = US, YouFoodz = AU, Chefs Plate = CA, HelloFresh = US.

---

## funnel-analysis

Generate an acquisition funnel report with per-step drop-off analysis.

### Step 1: Resolve Parameters

1. Parse `--brand` to identify the brand
2. Parse `--market` (or use default) to resolve GA4 property ID from the mapping above
3. Parse `--timeframe` as `YYYYMMDD-YYYYMMDD`, convert to `YYYY-MM-DD` format for GA4 API
4. Check `--xbrand-compliant` flag

### Step 2: Determine Funnel Steps

The funnel steps vary by brand. Detect available events by querying for the brand's quiz/signup events.

**Standard HF-platform funnel (The Pets Table, HelloFresh, Factor, Green Chef, EveryPlate, Chefs Plate):**

All steps are event-based (no page-view signals) for consistency and to ensure only users who took action are counted.

| # | Step Name | GA4 Signal | Type |
|---|-----------|-----------|------|
| 01 | all_traffic | Total `totalUsers` for property | Metric |
| 02-09 | quiz_steps | `Signup_FunnelQuizPageLoad` event, dimension `customEvent:event_action` = `<StepName> \| Loaded` | Event + dimension |
| 10 | visited_plans | `SelectPlan_PlanSelection` event (user selected a plan) | Event |
| 11 | visited_select_meals | `SelectMeals_Submit` event (user submitted meal selection) | Event |
| 12 | registration_step | `Signup_LeadGenSuccess` event | Event |
| 13 | checkout_address | `add_shipping_info` event | Event |
| 14 | checkout_payment | `add_payment_info` event | Event |
| 15 | conversion | `purchase` event | Event |

**Why event-based:** Page-view signals (`/plans-selection`, `/select-meals`) include passive visitors (direct URL traffic, back-navigation, page browsers who take no action). Event-based signals only count users who actively engaged with the step, producing a monotonically decreasing funnel.

**Good Chop (Shopify) funnel:** TBD (different event structure, detect on first run).

### Step 3: Query GA4

For each funnel step, query the GA4 Analytics MCP using `mcp__analytics-mcp__run_report`:

```
property_id: <resolved property ID>
date_ranges: [{"start_date": "<start>", "end_date": "<end>"}]
metrics: ["totalUsers"]
```

**IMPORTANT: Use `totalUsers` (unique users), NOT `sessions` or `engagedSessions`.**

GA4 "engaged sessions" applies a 10-second/2-pageview threshold that is stricter than Databricks' prospect filter, artificially shrinking the denominator and inflating CVR (~4.4% vs real ~3.2%). User-based counting (`totalUsers`) produces results within 0.2pp of Tableau/Databricks (3.18% vs 3.37%) and is the correct GA4 methodology for funnel CVR.

**If `--xbrand-compliant`:** Add dimension filter to exclude active subscribers:
```json
{"not_expression": {"filter": {"field_name": "customUser:hasActiveSubscription", "string_filter": {"value": "true", "match_type": "EXACT"}}}}
```

Note: `hasInactiveSubscription` exclusion has no measurable impact (tested May 2026) and can be omitted.

**If `--single-session`:** Add additional dimension filter:
```json
{"filter": {"field_name": "newVsReturning", "string_filter": {"value": "new", "match_type": "EXACT"}}}
```

**If both `--xbrand-compliant` AND `--single-session`:** Combine in an `and_group`:
```json
{"and_group": {"expressions": [
  {"not_expression": {"filter": {"field_name": "customUser:hasActiveSubscription", "string_filter": {"value": "true", "match_type": "EXACT"}}}},
  {"filter": {"field_name": "newVsReturning", "string_filter": {"value": "new", "match_type": "EXACT"}}}
]}}
```

**Multi-pet exclusion:** Not needed in GA4. Multi-pet users are 75% active subscribers (already excluded by xbrand filter). The remaining ~250 prospect users who touch multi-pet pages have negligible impact (<0.1pp on CVR).

Query in batches:
1. Total traffic (no dimension filter beyond xbrand/single-session)
2. Quiz steps (`Signup_FunnelQuizPageLoad` with `event_action` dimension)
3. Mid-funnel events (`SelectPlan_PlanSelection`, `SelectMeals_Submit`)
4. Checkout events (`Signup_LeadGenSuccess`, `add_shipping_info`, `add_payment_info`, `purchase`)

### Step 4: Calculate Funnel Metrics

For each step:
- `% of All Traffic` = step_users / all_traffic_users * 100
- `Step Drop-off` = (current_step - previous_step) / previous_step * 100

Summary metrics:
- Overall CVR = conversion / all_traffic * 100
- Quiz CVR = conversion / quiz_start * 100
- Quiz Engagement Rate = quiz_start / all_traffic * 100
- Quiz Completion Rate = last_quiz_step / quiz_start * 100
- Payment → Conversion Rate = conversion / checkout_payment * 100

### Step 5: Query Databricks (if `--orthogonal`)

If `--orthogonal` is set, also query Databricks for session-level funnel data.

**Key filters:**
- `asset = 'Website'` for web-only (matches Tableau "Asset: Website" filter)
- `iso_week` format is `W49`, `W50`, etc. (no year prefix). When filtering by HF week, use `iso_week IN ('W49', 'W50', ...)` combined with `fk_date` range to scope to the correct year.
- The aggregated table has NO visitor/session IDs and NO page_path. It's pre-aggregated by dimension combos.

```sql
SELECT
  SUM(visits_can_activate) as prospect_sessions,
  SUM(entered_funnel) as entered_funnel,
  SUM(plps) as plps,
  SUM(plans) as plans,
  SUM(pre_registration) as pre_registration,
  SUM(registration) as registration,
  SUM(checkout_address) as checkout_address,
  SUM(c_checkout_address) as c_checkout_address,
  SUM(checkout_payment) as checkout_payment,
  SUM(c_checkout_payment) as c_checkout_payment,
  SUM(checkout_submit_payment) as checkout_submit_payment,
  SUM(activations) as activations,
  SUM(net_conversion_2WK) as net_conv_2wk,
  SUM(net_conversion_5WK) as net_conv_5wk,
  SUM(empty_conversion_2WK) as empty_conv_2wk,
  SUM(empty_conversion_5WK) as empty_conv_5wk,
  SUM(my_deliveries) as my_deliveries
FROM public_glue.private_growth_intermediate_layer_live.funnel_prospects_session_level_xbrand_enriched_ow
WHERE brand = '<databricks_brand_value>'
  AND fk_date >= <start_YYYYMMDD>
  AND fk_date <= <end_YYYYMMDD>
  AND asset = 'Website'
```

**Databricks SQL API (primary method, since MCP server has known issues):**

```bash
curl -s -X POST "https://hf-query-engine.cloud.databricks.com/api/2.0/sql/statements/" \
  -H "Authorization: Bearer <DATABRICKS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"statement": "<sql>", "warehouse_id": "96c9036f3d79463f", "wait_timeout": "50s"}'
```

If `wait_timeout` returns PENDING/RUNNING, poll with GET:
```bash
curl -s -X GET "https://hf-query-engine.cloud.databricks.com/api/2.0/sql/statements/<statement_id>" \
  -H "Authorization: Bearer <DATABRICKS_TOKEN>"
```

Read connection details from `/pm-os/.mcp.json` > `mcpServers.databricks.env`:
- `DATABRICKS_HOST`: `https://hf-query-engine.cloud.databricks.com/`
- `DATABRICKS_TOKEN`: from env config
- `DATABRICKS_SQL_WAREHOUSE_HTTP_PATH`: `/sql/1.0/warehouses/96c9036f3d79463f`

**Session-level table (for deeper investigation):**
If you need visitor-level or page-path-level data, use:
`public_glue.private_growth_intermediate_layer_live.funnel_activation_prospects_session_level_enriched_ow`
This has `visitor_id`, `session_id`, `page_path`, `landingpage`, and all funnel step flags.

### Step 6: Generate Report

**Storage path (mandatory):**
```
user/products/<product-kebab>/analytics/report/<report-type>/<brand>-<creation-date>-<report-type>-<report-name>.md
```

Create directories with `mkdir -p` if needed.

**Report name construction:**
- Timeframe as short slug: `20251201-20251231` becomes `dec-2025`
- Append filter context: `prospects` (if xbrand), `new-users` (if single-session), `orthogonal` (if both sources)
- Examples: `dec-2025-prospects`, `q1-2026-all-traffic`, `dec-2025-orthogonal`

**Source attribution (REQUIRED in every report):**

Every report MUST include a `**Source:**` line in the header listing all data sources used:
- GA4-only: `**Source:** Google Analytics 4 (property: <id>, <display name>)`
- Databricks-only: `**Source:** Databricks (table: public_glue.private_growth_intermediate_layer_live.funnel_prospects_session_level_xbrand_enriched_ow)`
- Orthogonal: `**Sources:** Google Analytics 4 (property: <id>) + Databricks (xbrand session funnel)`

**Report structure (GA4 only):**

```markdown
# <Brand> Acquisition Funnel — <Period Description>

**Date of Analysis:** <today>
**Period:** <start> to <end>
**Source:** Google Analytics 4 (property: <id>, <display name>)
**Filter:** <describe filters applied>
**Metric:** Total Users (unique)

---

## Funnel Overview

| # | Step | Users | % of All Traffic | Step Drop-off |
|---|------|-------------|-----------------|---------------|
<rows>

**Overall CVR (All Traffic to Purchase): X.X%**
**Quiz CVR (Quiz Start to Purchase): X.X%**

---

## Visual Funnel

<ASCII bar chart, proportional to all_traffic base>

---

## Drop-off Analysis

### Major Drop-off Points

| Transition | Users Lost | Drop % | Hypothesis |
<rows for drops > 10%>

---

## Summary Metrics

| Metric | Value |
|--------|-------|
<summary rows>
```

**Report structure (--orthogonal, both sources):**

```markdown
# <Brand> Acquisition Funnel — <Period Description> (Orthogonal)

**Date of Analysis:** <today>
**Period:** <start> to <end>
**Sources:** Google Analytics 4 (property: <id>) + Databricks (xbrand session funnel)
**Filter:** <describe filters applied>

---

## Funnel Overview — GA4 (Users)

| # | Step | Users | % of All Traffic | Step Drop-off |
|---|------|-------------|-----------------|---------------|
<GA4 rows>

---

## Funnel Overview — Databricks (Sessions)

| # | Step | Sessions | % of Prospect Traffic | Step Drop-off |
|---|------|---------|----------------------|---------------|
<Databricks rows>

---

## Source Comparison

| Step | GA4 (Users) | Databricks (Sessions) | Delta | Notes |
|------|------------|----------------------|-------|-------|
<comparison rows>

---

## Key Differences Between Sources

| Factor | Impact | Explanation |
|--------|--------|-------------|
| Session vs. User counting | <> | <> |
| Prospect definition precision | <> | <> |
| Conversion definition | <> | <> |
| Net conversion visibility | <> | <> |

---

## Databricks-Only Insights

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Net Conversion (2WK) | <> | Activations minus early cancels |
| Net Conversion (5WK) | <> | True acquired customers |
| Empty Conversion Rate (2WK) | <> | Early churn signal |
| Empty Conversion Rate (5WK) | <> | Extended churn signal |
| My Deliveries | <> | Post-activation engagement |

---

## Visual Funnel

<ASCII bar chart for both sources>

---

## Drop-off Analysis

<Major drop-off analysis from both sources>

---

## Summary Metrics

| Metric | GA4 | Databricks | Delta |
|--------|-----|-----------|-------|
<summary comparison rows>

---

## Recommendations

<numbered recommendations based on findings from both sources>
```

### CVR Reconciliation Guidance (for --orthogonal reports)

When comparing GA4 and Databricks CVRs, expect these patterns:

| GA4 Methodology | Typical Result | Relationship to Tableau |
|---|---|---|
| `totalUsers` (prospect, xbrand-compliant) | ~3.2% | Within 0.2pp of Tableau (correct) |
| `sessions` (all prospect sessions) | ~2.6% | Below Tableau (over-counted denominator) |
| `engagedSessions` | ~4.3% | Above Tableau (over-filtered denominator, DO NOT USE) |

**Always present GA4 CVR as user-based (`totalUsers` / purchase `totalUsers`).** This is the apples-to-apples comparison with Tableau/Databricks.

**Why Tableau denominator (149K) sits between GA4 all sessions (200K) and engaged sessions (122K):**
Databricks' `visits_can_activate` applies a session_duration > 0 filter (excludes pure bounces) but is less strict than GA4's 10-second engagement threshold. There is no exact GA4 equivalent.

**Conversion gap (~250 conversions):** Databricks excludes multi-pet + gift-card/seasonal conversions via upstream SQL. Multi-pet is negligible in GA4 (75% already excluded by prospect filter). Gift-card/seasonal exclusions account for most of the gap but cannot be replicated in GA4 without BigQuery.

### Step 7: Report Output

Display:
- File path where report was saved
- Overall CVR headline (from both sources if orthogonal)
- Top 3 drop-off points
- Confirm xbrand filter status
- Confirm data sources used

---

## Execute

1. If no arguments: show help text
2. If `--funnel-analysis`: validate required params (`--brand`, `--timeframe`), then:
   a. Resolve GA4 property from brand/market mapping
   b. Query GA4 for funnel steps (Steps 2-4)
   c. If `--orthogonal`: also query Databricks (Step 5), resolve brand name mapping
   d. Calculate metrics (Step 4)
   e. Generate report at canonical storage path (Step 6)
   f. Display summary (Step 7)
3. Report errors clearly if brand/market combination not found in property mapping
4. If Databricks MCP unavailable and `--orthogonal` requested: fall back to curl-based SQL API, warn user if that also fails
