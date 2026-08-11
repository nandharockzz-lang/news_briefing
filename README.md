# Morning Brief — Codespaces Phase 1A

This repository is prepared for the approved Phase 1A Tamil Nadu vertical slice.

## Run

Open a GitHub Codespace, then in the terminal:

```bash
python -m src.run_check
```

The command checks the candidate endpoints from an internet-enabled runtime and writes:
`data/connectivity-check.json`

## Important

Some entries are currently RSS-page candidates rather than confirmed machine-readable feed URLs. The connectivity check is intentionally allowed to fail for those; we will use the results to validate the correct endpoint rather than guessing or scraping.

No AI, X, Reddit, clustering, impact scoring, personalization, or UI is included.
