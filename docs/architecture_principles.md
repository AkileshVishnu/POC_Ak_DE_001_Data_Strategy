# Data Architecture Principles for AI-Ready Systems

## The Medallion Architecture — Foundation and Extensions

The Medallion Architecture (Bronze → Silver → Gold) provides an excellent structural foundation for AI-ready data systems. However, it is a pattern, not a complete strategy. The key is to understand what extensions are needed for AI use cases.

### Bronze Layer — Raw Preservation
**Purpose**: Capture source data exactly as received. Never transform, filter, or enrich.

**Why it matters for AI**:
- Provides a reliable replay capability when a downstream transformation bug corrupts data
- Creates an auditable record of what the system received vs what it produced
- Enables schema evolution tracking — critical for detecting breaking upstream changes

**AI-specific requirements**:
- Capture ingestion timestamp separately from event timestamp
- Record source system, batch ID, and file/API version
- Store raw schema as metadata alongside data

### Silver Layer — Standardization and Validation
**Purpose**: Apply business rules, standardize schemas, validate quality, resolve entities.

**Why it matters for AI**:
- This is where training data quality is established
- Deduplication and entity resolution at this layer prevent biased model training
- Quality validation rules define what the model will and will not see

**AI-specific requirements**:
- Validate completeness, validity, and consistency
- Track quality metrics per record for model training exclusion
- Maintain SCD (Slowly Changing Dimension) history for temporal features

### Gold Layer — Business Data Products
**Purpose**: Create business-ready, semantically rich data products that serve as the AI consumption layer.

**Why it matters for AI**:
- Features derived from well-defined data products are explainable
- Governed data products have SLAs that AI systems can depend on
- Gold layer semantics define what the model will learn

**AI-specific requirements**:
- Define and document every field with business semantics
- Compute and store validated KPIs
- Build entity-level 360 views that aggregate all signals

### Feature / Semantic Layer
**Purpose**: Compute ML-ready features with point-in-time correctness and quality scores.

**This layer is often missing from traditional data warehouses and is the most critical for AI.**

**Requirements**:
- Point-in-time correct aggregations (no data leakage)
- Feature quality scores alongside feature values
- Rolling window aggregations with gap handling
- Feature freshness timestamps

---

## Key Architectural Decisions

### Decision 1: Batch vs Streaming

| Factor | Choose Batch | Choose Streaming |
|--------|-------------|-----------------|
| Latency requirement | Hours to days acceptable | Minutes to seconds required |
| Data volume | Very large, arrival in bursts | Continuous, high-frequency |
| Processing complexity | Complex joins, aggregations | Simpler, stateless operations |
| Cost | Lower infrastructure cost | Higher infrastructure cost |
| AI use case | Batch scoring, recommendations | Real-time fraud, personalization |

**Default recommendation**: Start with batch. Add streaming only when latency requirements demand it.

### Decision 2: Star Schema vs Data Vault vs Flat Tables

| Architecture | Pros | Cons | Best For |
|-------------|------|------|---------|
| **Star Schema** | Simple queries, fast aggregations | Rigid, hard to extend, no history | Stable reporting use cases |
| **Data Vault** | Audit history, flexible, source-agnostic | Complex, harder to query | Auditability-heavy environments |
| **Wide Flat Tables** | Simple for ML consumption | Denormalized, expensive to maintain | Feature stores, ML training sets |
| **Hybrid (our approach)** | Normalized Silver, flat Gold | Requires more pipeline work | AI-ready systems |

### Decision 3: Compute-on-Read vs Compute-on-Write

**Compute-on-Write (Materialized)**:
- Precompute and store features in Gold/Feature layer
- Best for: Features used by many models, expensive aggregations, features with quality SLAs
- Risk: Features can go stale if pipeline fails

**Compute-on-Read (Query-time)**:
- Compute features at inference time from raw data
- Best for: Low-latency requirements, simple features, personalized features
- Risk: Expensive, harder to guarantee consistency between training and serving

**Recommendation for AI systems**: Use compute-on-write for training features with strict lineage requirements. Use compute-on-read for simple real-time features only.

---

## Architecture Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Source → Model Pipeline

```
❌ Source System → SQL query → ML Model
```

This bypasses all quality controls, lineage tracking, and governance. When the source changes, the model silently fails. There is no audit trail.

### Anti-Pattern 2: No Temporal Isolation

```
❌ Train: SELECT features FROM gold WHERE entity_id = ? 
   -- Uses current state of data, not state at training time
```

This guarantees data leakage. Any feature that reflects information available after the event will make the model unrealistically accurate in training and degrade catastrophically in production.

### Anti-Pattern 3: Schema-Less Bronze Layer

```
❌ Store all raw data as JSON blobs with no schema validation
```

While JSON storage is flexible, a completely schema-less Bronze layer makes schema evolution invisible, breaks lineage tracking, and makes downstream transformation logic brittle.

### Anti-Pattern 4: Shared Feature Computation

```
❌ Training pipeline and inference pipeline compute features independently 
   using different logic or different data snapshots
```

Training-serving skew is the most common cause of model performance degradation. Feature computation logic must be exactly the same at training and serving time.

---

## Technology Selection Rationale

### DuckDB — The Local OLAP Engine

DuckDB is chosen for this POC because:
- **Runs in-process**: No server required, making the POC immediately runnable
- **SQL-native**: Standard SQL, compatible with dbt, familiar to data engineers
- **Columnar storage**: Efficient for analytical workloads (aggregations, joins)
- **Parquet integration**: Native read/write of Parquet files

In production, DuckDB can be replaced by Snowflake, BigQuery, Databricks, or Redshift — the SQL logic is portable.

### dbt Core — The Transformation Standard

dbt is chosen because:
- **SQL-first**: Transformations are readable, reviewable, and version-controlled
- **Built-in lineage**: dbt automatically tracks column and table lineage
- **Testing framework**: Built-in schema and data tests
- **Documentation**: Auto-generates data catalog from model metadata

### Great Expectations — Data Quality Contracts

Great Expectations is chosen because:
- **Expectation-based**: Define what data SHOULD look like, not just what it does look like
- **Reusable**: Expectation suites can be shared across environments
- **Reporting**: Generates human-readable data quality reports
- **Integrates with dbt**: Can run expectations on dbt models

---

## Governance Architecture

### The Three Layers of Governance

**Layer 1: Technical Governance**
- Schema validation at ingestion (Bronze)
- Data quality rules at standardization (Silver)
- KPI validation at product layer (Gold)
- Feature quality checks at ML layer

**Layer 2: Semantic Governance**
- Field definitions in dbt model documentation
- Business rules documented in data strategy docs
- KPI definitions with calculation logic
- Feature derivation logic in model cards

**Layer 3: Operational Governance**
- Data ownership assignments
- Access control definitions
- Retention policies
- Incident response procedures

### The Data Contract Pattern

Every interface between layers should be defined as an explicit contract:

```yaml
# Example Data Contract
name: silver_hcp_standardized
version: "2.1"
owner: "data-engineering@company.com"
sla:
  freshness_hours: 24
  completeness_pct: 98
  quality_score_min: 0.95
schema:
  hcp_id:
    type: VARCHAR
    nullable: false
    description: "Standardized HCP identifier from MDM"
  npi:
    type: VARCHAR
    nullable: false
    pattern: "^[0-9]{10}$"
```

This contract pattern is implemented across all three POC projects.
