"""
Redrob AI Challenge — Sandbox Demo
Streamlit app: upload up to 100 candidates, get ranked output instantly.
Hosted on Streamlit Cloud — this is the sandbox link for submission.
"""

import streamlit as st
import json
import csv
import io
from datetime import datetime, date

# ── paste your full scoring logic here (copied from rank.py) ──────────────────

CORE_SKILLS = {
    "sentence-transformers", "sentence transformers", "embeddings", "vector embeddings",
    "dense retrieval", "semantic search", "embedding", "bge", "e5", "openai embeddings",
    "pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
    "elasticsearch", "vector database", "vector db", "vector search", "hybrid search",
    "ranking", "information retrieval", "bm25", "hybrid retrieval", "reranking",
    "re-ranking", "learning to rank", "ltr", "ndcg", "mrr", "map", "recall",
    "llm", "large language model", "fine-tuning", "fine tuning", "lora", "qlora",
    "peft", "rlhf", "instruction tuning", "rag", "retrieval augmented generation",
    "mlops", "model serving", "inference optimization", "ml pipeline",
    "recommendation system", "recommender", "search system",
    "python", "pytorch", "tensorflow", "transformers", "huggingface",
}

BONUS_SKILLS = {
    "xgboost", "lightgbm", "gradient boosting", "learning to rank",
    "distributed systems", "kafka", "spark", "airflow",
    "kubernetes", "docker", "aws", "gcp", "azure",
    "a/b testing", "experimentation", "sql", "nlp",
    "open source", "github", "research",
}

DISQUALIFIED_TITLES = {
    "marketing manager", "hr manager", "accountant", "civil engineer",
    "mechanical engineer", "graphic designer", "customer support",
    "operations manager", "content writer", "java developer",
    ".net developer", "project manager", "business analyst",
    "frontend engineer", "mobile developer",
}

CONSULTING_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "mindtree", "mphasis", "hexaware", "tech mahindra", "hcl",
    "l&t infotech", "ltimindtree", "persistent systems", "cyient",
}

PREFERRED_LOCATIONS = {
    "pune", "noida", "hyderabad", "mumbai", "bangalore", "bengaluru",
    "delhi", "gurgaon", "gurugram", "chennai", "kolkata",
}


def detect_honeypot(candidate):
    skills = candidate.get("skills", [])
    expert_zero = sum(1 for s in skills if s.get("proficiency") in ("expert", "advanced") and s.get("duration_months", 1) == 0)
    if expert_zero >= 5:
        return True
    signals = candidate.get("redrob_signals", {})
    assessment = signals.get("skill_assessment_scores", {})
    expert_names = {s["name"] for s in skills if s.get("proficiency") == "expert"}
    badly_failed = sum(1 for name, score in assessment.items() if name in expert_names and score < 15)
    if badly_failed >= 3:
        return True
    if candidate.get("profile", {}).get("years_of_experience", 0) > 40:
        return True
    return False


def score_skills(candidate):
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    assessment = signals.get("skill_assessment_scores", {})
    core_hits = 0.0
    bonus_hits = 0.0
    for skill in skills:
        name_lower = skill["name"].lower()
        proficiency = skill.get("proficiency", "beginner")
        duration = skill.get("duration_months", 0)
        assess_score = assessment.get(skill["name"], None)
        prof_mult = {"expert": 1.0, "advanced": 0.85, "intermediate": 0.65, "beginner": 0.35}.get(proficiency, 0.5)
        dur_mult = min(1.0, duration / 24.0)
        assess_mult = assess_score / 100.0 if assess_score is not None else 0.7
        skill_score = prof_mult * (0.5 + 0.3 * dur_mult + 0.2 * assess_mult)
        matched_core = any(core in name_lower for core in CORE_SKILLS) or name_lower in CORE_SKILLS
        if matched_core:
            core_hits += skill_score
        elif any(bonus in name_lower for bonus in BONUS_SKILLS) or name_lower in BONUS_SKILLS:
            bonus_hits += skill_score * 0.3
    return min(1.0, min(1.0, core_hits / 4.0) * 0.85 + min(0.3, bonus_hits / 3.0) * 0.15)


def score_career(candidate):
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    yoe = profile.get("years_of_experience", 0)
    current_title = profile.get("current_title", "").lower()
    score = 0.0
    if 5 <= yoe <= 9: yoe_score = 1.0
    elif 4 <= yoe < 5 or 9 < yoe <= 11: yoe_score = 0.8
    elif 3 <= yoe < 4 or 11 < yoe <= 14: yoe_score = 0.5
    elif yoe > 14: yoe_score = 0.35
    else: yoe_score = 0.2
    score += yoe_score * 0.25
    strong_titles = {"ml engineer","ai engineer","machine learning engineer","nlp engineer","search engineer","ranking engineer","applied scientist","data scientist","recommendation","research engineer","llm engineer","ai researcher","senior engineer","staff engineer","principal engineer"}
    medium_titles = {"software engineer","backend engineer","data engineer","platform engineer","full stack","cloud engineer","devops"}
    if any(t in current_title for t in strong_titles): title_score = 1.0
    elif any(t in current_title for t in medium_titles): title_score = 0.55
    elif any(d in current_title for d in DISQUALIFIED_TITLES): title_score = 0.05
    else: title_score = 0.3
    score += title_score * 0.25
    consulting_months = product_months = ai_ml_months = 0
    ai_ml_industries = {"artificial intelligence","machine learning","tech","technology","software","saas","fintech","edtech","healthtech","e-commerce"}
    consulting_industries = {"it services","consulting","outsourcing","staffing"}
    for job in career:
        company_name = job.get("company","").lower()
        industry = job.get("industry","").lower()
        duration = job.get("duration_months", 0)
        title = job.get("title","").lower()
        desc = job.get("description","").lower()
        is_consulting = any(c in company_name for c in CONSULTING_COMPANIES) or any(ci in industry for ci in consulting_industries)
        is_ai_ml = any(ai in industry for ai in ai_ml_industries) or any(t in title for t in ["ml","ai ","nlp","search","ranking","recommend","data scientist"]) or any(kw in desc for kw in ["embedding","retrieval","ranking","vector","llm","transformer"])
        if is_consulting: consulting_months += duration
        else: product_months += duration
        if is_ai_ml: ai_ml_months += duration
    total_months = max(1, consulting_months + product_months)
    product_ratio = product_months / total_months
    ai_ml_ratio = ai_ml_months / total_months
    if product_ratio < 0.1: product_score = 0.1
    elif product_ratio < 0.3: product_score = 0.4
    elif product_ratio < 0.6: product_score = 0.7
    else: product_score = 1.0
    score += product_score * 0.3
    score += min(1.0, ai_ml_ratio * 2.0) * 0.2
    return min(1.0, score)


def score_behavioral(candidate):
    signals = candidate.get("redrob_signals", {})
    today = date(2026, 6, 25)
    score = 0.0
    last_active_str = signals.get("last_active_date", "")
    try:
        days_inactive = (today - datetime.strptime(last_active_str, "%Y-%m-%d").date()).days
        if days_inactive <= 30: recency_score = 1.0
        elif days_inactive <= 60: recency_score = 0.85
        elif days_inactive <= 90: recency_score = 0.7
        elif days_inactive <= 180: recency_score = 0.45
        else: recency_score = 0.15
    except: recency_score = 0.5
    score += recency_score * 0.25
    score += 0.15 if signals.get("open_to_work_flag", False) else 0.0
    score += signals.get("recruiter_response_rate", 0.5) * 0.2
    notice = signals.get("notice_period_days", 60)
    if notice <= 0: notice_score = 1.0
    elif notice <= 30: notice_score = 0.9
    elif notice <= 60: notice_score = 0.6
    elif notice <= 90: notice_score = 0.4
    else: notice_score = 0.2
    score += notice_score * 0.15
    location = candidate.get("profile", {}).get("location", "").lower()
    willing = signals.get("willing_to_relocate", False)
    country = candidate.get("profile", {}).get("country", "").lower()
    if any(loc in location for loc in PREFERRED_LOCATIONS): location_score = 1.0
    elif willing and country == "india": location_score = 0.75
    elif willing: location_score = 0.3
    elif country == "india": location_score = 0.5
    else: location_score = 0.1
    score += location_score * 0.15
    score += signals.get("interview_completion_rate", 0.5) * 0.05
    github = signals.get("github_activity_score", -1)
    if github >= 0: score += min(0.05, github / 100.0 * 0.05)
    return min(1.0, score)


def score_red_flags(candidate):
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    current_title = profile.get("current_title", "").lower()
    penalties = 0.0
    if any(d in current_title for d in DISQUALIFIED_TITLES): penalties += 0.5
    all_companies = [j.get("company","").lower() for j in career]
    if all(any(c in comp for c in CONSULTING_COMPANIES) for comp in all_companies if comp) and len(all_companies) >= 2:
        penalties += 0.4
    completeness = candidate.get("redrob_signals", {}).get("profile_completeness_score", 50)
    if completeness < 40: penalties += 0.2
    return max(0.0, 1.0 - penalties)


def score_candidate(candidate):
    if detect_honeypot(candidate):
        return {"candidate_id": candidate["candidate_id"], "final_score": 0.0, "skills": 0.0, "career": 0.0, "behavioral": 0.0, "red_flag_mult": 0.0, "is_honeypot": True}
    s_skills = score_skills(candidate)
    s_career = score_career(candidate)
    s_behavioral = score_behavioral(candidate)
    s_red_flag = score_red_flags(candidate)
    raw = (s_skills * 0.40 + s_career * 0.30 + s_behavioral * 0.20) * (0.3 + 0.7 * s_red_flag)
    return {"candidate_id": candidate["candidate_id"], "final_score": round(raw, 6), "skills": s_skills, "career": s_career, "behavioral": s_behavioral, "red_flag_mult": s_red_flag, "is_honeypot": False}


def generate_reasoning(candidate, scores):
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = candidate.get("skills", [])
    title = profile.get("current_title", "Unknown")
    yoe = profile.get("years_of_experience", 0)
    location = profile.get("location", "Unknown")
    notice = signals.get("notice_period_days", 60)
    response_rate = signals.get("recruiter_response_rate", 0)
    last_active = signals.get("last_active_date", "")
    top_skills = [s["name"] for s in sorted(skills, key=lambda x: {"expert":3,"advanced":2,"intermediate":1,"beginner":0}.get(x.get("proficiency","beginner"),0), reverse=True)[:3]]
    try:
        days_inactive = (date(2026, 6, 25) - datetime.strptime(last_active, "%Y-%m-%d").date()).days
    except: days_inactive = 999
    skill_str = ", ".join(top_skills) if top_skills else "general software skills"
    parts = [f"{title} with {yoe:.1f} yrs exp ({location}); top skills: {skill_str}."]
    concerns, positives = [], []
    if scores["skills"] >= 0.7: positives.append("strong core AI/ML skill match")
    elif scores["skills"] < 0.3: concerns.append("limited core AI/ML skills")
    if days_inactive > 180: concerns.append(f"inactive for {days_inactive} days")
    elif days_inactive <= 30: positives.append("recently active")
    if response_rate < 0.2: concerns.append(f"low recruiter response rate ({response_rate:.0%})")
    if notice > 90: concerns.append(f"long notice period ({notice}d)")
    elif notice <= 30: positives.append(f"short notice ({notice}d)")
    if scores["career"] < 0.3: concerns.append("career not aligned with AI/ML product roles")
    if positives and concerns: parts.append(f"Positives: {'; '.join(positives)}. Concerns: {'; '.join(concerns)}.")
    elif positives: parts.append(f"{'; '.join(positives).capitalize()}.")
    elif concerns: parts.append(f"Concerns: {'; '.join(concerns)}.")
    return " ".join(parts)[:400]


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Redrob AI Ranker", page_icon="🎯", layout="wide")

st.title("🎯 Redrob AI — Candidate Ranker")
st.caption("India Runs Data & AI Challenge — Sandbox Demo | Upload up to 100 candidates and get ranked results instantly.")

st.info("📌 **This sandbox accepts a small candidate sample (≤100 candidates) for demo purposes.** The full 100K ranking runs via the CLI in ~35 seconds.")

st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Upload Candidates")
    uploaded_file = st.file_uploader(
        "Upload your candidates JSON file",
        type=["json", "jsonl"],
        help="Upload sample_candidates.json (JSON array) or a small .jsonl file with up to 100 candidates"
    )

    top_n = st.slider("How many top candidates to show?", min_value=5, max_value=50, value=20)

with col2:
    st.subheader("How it scores")
    st.markdown("""
| Dimension | Weight |
|---|---|
| 🧠 Skills match | 40% |
| 💼 Career quality | 30% |
| 📊 Behavioral signals | 20% |
| 🚩 Red flag penalty | multiplier |
""")

st.markdown("---")

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")

        # Try JSON array first, then JSONL
        candidates = []
        try:
            candidates = json.loads(content)
            if isinstance(candidates, dict):
                candidates = [candidates]
        except json.JSONDecodeError:
            for line in content.strip().split("\n"):
                line = line.strip()
                if line:
                    candidates.append(json.loads(line))

        if len(candidates) > 100:
            st.warning(f"⚠️ You uploaded {len(candidates)} candidates. Sandbox is limited to 100 — using first 100.")
            candidates = candidates[:100]

        st.success(f"✅ Loaded {len(candidates)} candidates. Scoring now...")

        # Score all candidates
        scored = []
        honeypot_count = 0
        progress = st.progress(0)

        for i, c in enumerate(candidates):
            result = score_candidate(c)
            scored.append((c, result))
            if result["is_honeypot"]:
                honeypot_count += 1
            progress.progress((i + 1) / len(candidates))

        progress.empty()

        # Sort
        scored.sort(key=lambda x: (-x[1]["final_score"], int(x[0]["candidate_id"].split("_")[1]) if "_" in x[0]["candidate_id"] else 0))

        top = scored[:top_n]

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Candidates scored", len(candidates))
        m2.metric("Showing top", top_n)
        m3.metric("Honeypots detected", honeypot_count)
        m4.metric("Top score", f"{top[0][1]['final_score']:.3f}" if top else "—")

        st.markdown("---")
        st.subheader(f"🏆 Top {top_n} Candidates")

        # Build results table
        rows = []
        for rank, (candidate, result) in enumerate(top, start=1):
            p = candidate.get("profile", {})
            reasoning = generate_reasoning(candidate, result)
            rows.append({
                "Rank": rank,
                "Candidate ID": result["candidate_id"],
                "Title": p.get("current_title", ""),
                "YOE": p.get("years_of_experience", 0),
                "Location": p.get("location", ""),
                "Score": round(result["final_score"], 4),
                "Skills": round(result["skills"], 2),
                "Career": round(result["career"], 2),
                "Behavioral": round(result["behavioral"], 2),
                "Honeypot": "⚠️" if result["is_honeypot"] else "✅",
                "Reasoning": reasoning,
            })

        import pandas as pd
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Download button for CSV
        st.markdown("---")
        st.subheader("📥 Download Ranked Output")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (candidate, result) in enumerate(top, start=1):
            reasoning = generate_reasoning(candidate, result)
            writer.writerow([result["candidate_id"], rank, round(result["final_score"], 6), reasoning])

        st.download_button(
            label="⬇️ Download CSV",
            data=output.getvalue(),
            file_name="ranked_output.csv",
            mime="text/csv"
        )

        # Expandable details for top 5
        st.markdown("---")
        st.subheader("🔍 Top 5 Candidate Breakdown")
        for rank, (candidate, result) in enumerate(top[:5], start=1):
            p = candidate.get("profile", {})
            signals = candidate.get("redrob_signals", {})
            skills = candidate.get("skills", [])
            with st.expander(f"#{rank} — {p.get('current_title','')} | {result['candidate_id']} | Score: {result['final_score']:.4f}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Location:** {p.get('location','')} ({p.get('country','')})")
                    st.markdown(f"**Experience:** {p.get('years_of_experience','')} years")
                    st.markdown(f"**Current company:** {p.get('current_company','')}")
                    st.markdown(f"**Open to work:** {'Yes ✅' if signals.get('open_to_work_flag') else 'No'}")
                    st.markdown(f"**Notice period:** {signals.get('notice_period_days','')} days")
                    st.markdown(f"**Response rate:** {signals.get('recruiter_response_rate', 0):.0%}")
                with c2:
                    st.markdown("**Score breakdown:**")
                    st.progress(result["skills"], text=f"Skills: {result['skills']:.2f}")
                    st.progress(result["career"], text=f"Career: {result['career']:.2f}")
                    st.progress(result["behavioral"], text=f"Behavioral: {result['behavioral']:.2f}")
                    st.markdown(f"**Red flag multiplier:** {result['red_flag_mult']:.2f}")
                top_skills = [s["name"] for s in sorted(skills, key=lambda x: {"expert":3,"advanced":2,"intermediate":1,"beginner":0}.get(x.get("proficiency","beginner"),0), reverse=True)[:6]]
                st.markdown(f"**Top skills:** {', '.join(top_skills)}")
                st.markdown(f"**Reasoning:** {generate_reasoning(candidate, result)}")

    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.exception(e)

else:
    st.markdown("""
    ### 👆 Upload a candidate file to get started

    **Expected format:** `sample_candidates.json` from the challenge bundle (JSON array of candidate objects)

    Each candidate object should have:
    - `candidate_id` — e.g. `CAND_0000001`
    - `profile` — title, location, years of experience
    - `skills` — list of skills with proficiency and duration
    - `career_history` — list of past roles
    - `redrob_signals` — behavioral signals

    ---
    **CLI usage (for full 100K dataset):**
    ```bash
    python rank.py --candidates candidates.jsonl --out submission.csv
    ```
    """)

st.markdown("---")
st.caption("Built for the Redrob India Runs Data & AI Challenge · rank.py · No external API calls · CPU only")
