# Healthcare Data Governance

## Sensitive Data Handling

This POC uses **100% synthetic data**. No real patient, physician, or clinical data is included.

In a production implementation, the following governance controls would apply:

### PHI Protection

| Data Type | Classification | Handling |
|-----------|---------------|---------|
| Patient Name | PHI | Never stored; aggregated at source |
| Patient DOB | PHI | Never stored |
| Patient Diagnosis | PHI | Never stored |
| MRN / Patient ID | PHI | Never stored |
| HCP Name | PII-like | Stored; masked in non-production |
| NPI | Public identifier | Stored unmasked |
| HCP address | PII | Stored; masked in analytics layer |

### Synthetic POC Limitations

1. All patient support data is synthetic and de-identified by design — no real patient records exist
2. HCP names are randomly generated; NPIs are fictional 10-digit numbers
3. Interaction and prescription data is statistically plausible but not real
4. This POC **must not** be connected to any real CRM, EHR, or prescription data system

## Access Control Assumptions

In production:
- **Role-Based Access Control (RBAC)** governs who can read each Gold table
- **Row-Level Security** on territory data limits reps to their own territory
- **Column masking** applies to HCP contact details in shared analytics environments
- **Audit logging** captures every read of gold_hcp_360

## Data Masking Approach

| Field | Masking Rule | Applied At |
|-------|-------------|-----------|
| rep_id | Hash with salt | Silver and above |
| Patient age band | Retained (aggregate only) | Silver |
| HCP NPI | Retained unmasked | All layers |
| HCP address | Partial mask (City + State only) | Gold analytics |

## Auditability

Every model score can be traced:
1. `gold_hcp_targeting_score.hcp_id` → `gold_hcp_360.hcp_id`
2. `gold_hcp_360.hcp_id` → `silver_hcp_standardized.hcp_id`
3. `silver_hcp_standardized.hcp_id` → `bronze_hcp_master.hcp_id`
4. `bronze_hcp_master._batch_id` → ingestion log (date, source file, record count)

The complete provenance of any AI score is auditable from prediction to raw source file.

## Compliance Considerations

| Regulation | Relevance | How This POC Addresses It |
|-----------|-----------|--------------------------|
| **HIPAA** | Patient data protection | No PHI stored; aggregation enforced |
| **GDPR** | HCP personal data (EU only) | HCP data treated as personal data; masked in POC |
| **FDA 21 CFR Part 11** | Audit trails for clinical data | All batch IDs and load timestamps retained |
| **Sunshine Act** | HCP interaction transparency | Interaction data traceable to source |

## Limitations of This POC

This is a portfolio POC demonstrating data strategy patterns. It does not implement:
- Real identity verification services
- Production-grade RBAC (relies on DuckDB local access)
- Real-time PHI detection or scanning
- Certified de-identification algorithms
- HIPAA Business Associate Agreements (BAA)

A production deployment would require engagement with a certified healthcare data governance framework.
