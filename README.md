# Verity
Verity - Pharma Quality Investigator, an AI-assisted pharmaceutical quality investigation, root cause analysis, and CAPA management.

## RCA draft workflow

RCA jobs use a specific approved extraction review and preserve its
effective facts, evidence provenance, unresolved findings, and input
fingerprint.

LangGraph validates the input, generates draft content through Groq,
and validates the output references. A separate worker manages leases,
retries, and transactional result persistence.

From the backend directory, process one eligible job:

```powershell
python -m verity.rcaWorker --once
```

Process a specific job:

```powershell
python -m verity.rcaWorker --once --job-id <job-uuid>
```

Run continuously:

```powershell
python -m verity.rcaWorker
```

The worker reads ../.env by default. Use --env-file to override it.

RCA endpoints are available in Swagger under "RCA Jobs".

Generated hypotheses remain unverified. Structural validation and valid
fact references do not establish causal correctness. Human review is
required before accepting conclusions or approving CAPA.
