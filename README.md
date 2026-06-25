# Redrob AI Challenge — Intelligent Candidate Ranker

**Challenge:** India Runs Data & AI Challenge — Senior AI Engineer Ranking  
**Approach:** Multi-signal scoring system using skills match, career quality, and behavioral signals  
**Runtime:** ~35 seconds for 100,000 candidates on CPU · No GPU · No external API calls

---

## Files in this repo

| File | What it does |
|---|---|
| `rank.py` | Main ranking script — run this to produce your submission CSV |
| `app.py` | Streamlit sandbox demo — upload candidates and get ranked output in browser |
| `requirements.txt` | Python dependencies |
| `submission_metadata.yaml` | Submission metadata (team info, sandbox link, etc.) |
| `README.md` | This file |

---

## How to run

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Run the ranker (produces submission CSV)

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

### Step 3 — Validate before submitting

```bash
python validate_submission.py your_team_id.csv
```

---

## Quick test on sample data (50 candidates)

```bash
python rank.py --candidates ./sample_candidates.json --out test_output.csv --sample
```

---

## Run the sandbox demo locally

```bash
streamlit run app.py
```

Then open `http://localhost:8501` and upload `sample_candidates.json`.

---

## Arguments for rank.py

| Argument | Default | Description |
|---|---|---|
| `--candidates` | `candidates.jsonl` | Path to the candidate pool |
| `--out` | `submission.csv` | Output CSV path |
| `--top` | `100` | Number of top candidates to output |
| `--sample` | off | Use JSON array format (sample_candidates.json) |

---

## How the scoring works

Each candidate is scored across 4 dimensions:

### 1. Skills match (40%)
Matched against a curated list of core JD requirements — FAISS, Pinecone, vector DBs, embeddings, LLMs, Python, PyTorch etc. Each skill is weighted by:
- Proficiency level (expert / advanced / intermediate / beginner)
- Duration of use in months
- Redrob assessment score (where available)

### 2. Career quality (30%)
- **Product company bonus** — consulting-only careers (TCS, Infosys, Wipro etc.) are penalised as the JD explicitly states
- **AI/ML role history** — career descriptions scanned for embedding, retrieval, ranking and LLM keywords
- **Experience band** — 5–9 years is the sweet spot per JD; outside this range scores slightly lower

### 3. Behavioral signals (20%)
A perfect-on-paper candidate who hasn't logged in for 6 months is not actually hirable. This dimension checks:
- Days since last active on platform
- Open to work flag
- Recruiter response rate
- Notice period (sub-30 days preferred)
- Location / willingness to relocate to Pune or Noida

### 4. Red flag multiplier
Reduces the total score when a candidate has:
- A completely wrong-field current title (marketing manager, civil engineer etc.)
- Entire career at consulting firms only
- Very low profile completeness score

### Honeypot detection
The dataset contains ~80 fake candidates with impossible profiles. We detect them via:
- 5+ "expert" skills with 0 months of usage
- Expert-claimed skills with assessment scores below 15
- Implausibly high years of experience

**Honeypot rate in top 100: 0%**

---

## Compute constraints — well within limits

| Constraint | Limit | Actual |
|---|---|---|
| Runtime | ≤ 5 minutes | ~35 seconds ✅ |
| Memory | ≤ 16 GB | ~1.2 GB ✅ |
| Compute | CPU only | CPU only ✅ |
| Network | No external calls | Zero API calls ✅ |

---

## Output format

```
candidate_id,rank,score,reasoning
CAND_0002025,1,0.81743,"Senior AI Engineer with 5.9 yrs exp (Trivandrum, Kerala); top skills: FAISS, TensorFlow, scikit-learn. Strong core AI/ML skill match; recently active; short notice (30d)."
CAND_0064326,2,0.81324,"Search Engineer with 7.6 yrs exp (Gurgaon, Haryana); top skills: PyTorch, Deep Learning, Weaviate. Strong core AI/ML skill match."
...
```

---

## Environment tested on

- Python 3.10+
- No GPU required
- 16 GB RAM machine
- Ubuntu / macOS both work
