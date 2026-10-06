# Design Note: Index Data Pipeline on AWS

## Product Summary

Every day, a price file arrives; the platform validates it, computes an equal-weighted index over a fixed list of stocks, stores a versioned result, and exposes it through an API and CLI.

## Architecture Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Data Source  │────>│ S3 Landing   │────>│ Lambda Validator │────>│ S3 Validated │
│ (CSV files)  │     │   Bucket     │     │                 │     │   Prefix     │
└─────────────┘     └──────────────┘     └────────┬────────┘     └──────┬───────┘
                                                  │ (fail)              │ (pass)
                                          ┌───────▼────────┐    ┌──────▼───────┐
                                          │ S3 Rejected    │    │  Glue Job    │
                                          │   Prefix       │    │ (Transform)  │
                                          └────────────────┘    └──────┬───────┘
                                                                       │
                                          ┌────────────────┐    ┌──────▼───────┐
                                          │   FastAPI &    │<───│ RDS Postgres │
                                          │     CLI        │    │  (Versioned) │
                                          └────────────────┘    └──────────────┘
                                                                       ▲
                                          ┌────────────────┐           │
                                          │  CloudWatch    │───────────┘
                                          │ Alarms/Logs    │
                                          └────────────────┘

                                          ┌────────────────┐    ┌──────────────┐
                                          │   Terraform    │    │GitHub Actions│
                                          │ (IaC for all)  │    │   (CI/CD)    │
                                          └────────────────┘    └──────────────┘
```

## Stock Universe

30 Indian large-cap stocks (Nifty 30 subset). The constituent list is versioned with effective date ranges.

## Index Methodology (Sample - Not Official)

- **Type:** Equal-weighted price return index
- **Base Value:** 100 on the base date (2024-01-01)
- **Daily Calculation:** `Index(t) = Index(t-1) × (1 + average_daily_return(t))`
- **Daily Return per Stock:** `Return(t) = (Close(t) / Close(t-1)) - 1`
- **Missing Prices:** Carry forward the previous day's close once. If still missing, flag the stock and exclude from that day's calculation.
- **Constituent Changes:** Versioned constituent list with effective date ranges. Changes take effect on the specified date.

> **Disclaimer:** This is a sample methodology for demonstration purposes only. It is not an official index methodology.

## Input File Contract

- **File Name Pattern:** `prices_YYYY-MM-DD.csv`
- **Columns (required):** date, symbol, open, high, low, close, volume
- **Column Types:**
  - date: ISO 8601 date string (YYYY-MM-DD)
  - symbol: string, uppercase
  - open, high, low, close: float, > 0
  - volume: integer, >= 0
- **Optional Columns:** Any additional columns are tolerated but not required.
- **Constraints:**
  - high >= low
  - close within [low, high]
  - No duplicate symbols for the same date
  - date in each row matches the file date

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Compute | Lambda + Glue | Lambda for fast event-driven validation; Glue Python Shell for cost-effective transformation at this data volume |
| Database | RDS PostgreSQL | Free-tier friendly, full SQL support, same engine as Aurora for future migration |
| Networking | No NAT Gateway | Avoid hourly NAT charges; use VPC endpoints and S3 gateway endpoints |
| Orchestration | Lambda-triggered Glue | Simpler than Step Functions; adequate for a linear pipeline |
| Schema Migrations | Alembic | Industry standard, version-controlled migrations with rollback support |
| IaC | Terraform | Declarative, multi-cloud capable, strong AWS provider |
| CI/CD | GitHub Actions | Free for public repos, native GitHub integration |

## Cost Controls

- RDS: db.t3.micro (free-tier eligible), stop when idle
- Glue: Python Shell jobs (0.0625 DPU minimum vs 2 DPU for Spark)
- Lambda: 256MB memory, 60s timeout
- S3: Lifecycle rules to expire test data after 30 days
- No NAT Gateways
- Budget alerts at $5, $10, $20 thresholds
