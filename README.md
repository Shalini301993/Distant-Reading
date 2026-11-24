# Distant Reading: conspiracy theories on Hacker News

Pipeline: `pipeline/scrape.py` (HN Algolia API → pseudonymised stories/comments) → `pipeline/analyze.py`
(TF-IDF + NMF topics, VADER sentiment) → `dashboard/` (static D3 site).

## Publish with GitHub Actions
1. Merge this branch into the default branch (Pages deploys only from it by default).
2. **Settings → Pages → Source: GitHub Actions.**
3. Optional secret `PSEUDONYM_SALT` (Settings → Secrets and variables → Actions). Generate one with
   `python3 -c "import secrets;print(secrets.token_hex(32))"`. Without it each run uses a random salt:
   pseudonyms are still non-reversible but differ between runs. No other secrets are needed (HN's API is public).
4. **Actions → Collect HN data and publish dashboard → Run workflow.** A failed run can be retried with *Re-run all jobs*.

Run locally: `pip install -r requirements.txt && cd pipeline && python scrape.py && python analyze.py`, then serve `dashboard/`.

Privacy: usernames are replaced by salted-HMAC pseudonyms in memory; raw handles are never written. Only `dashboard/*` is published.
