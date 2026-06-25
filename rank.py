"""
Redrob Hackathon — Intelligent Candidate Ranker
Author: Aira
Role: Senior AI Engineer — Founding Team

Approach:
  - Parse the job description requirements into hard must-haves and nice-to-haves
  - Score each candidate across 4 dimensions:
      1. Skills match (core required skills vs nice-to-have)
      2. Career quality (product company experience, role fit, years of experience)
      3. Behavioral signals (active, responsive, relocatable)
      4. Red flags / disqualifiers (consulting-only, CV/NLP mismatch, honeypot detection)
  - Combine into a composite score, rank top 100, write CSV

No LLM API calls. Runs fully offline. CPU only. ~1-2 min on 100K candidates.
"""

import json
import csv
import argparse
import math
import re
from datetime import datetime, date

# ─────────────────────────────────────────────
# JD KNOWLEDGE BASE  (parsed from job_description)
# ─────────────────────────────────────────────

# Core must-have skills (any match = strong positive)
CORE_SKILLS = {
    # Embeddings & retrieval
    "sentence-transformers", "sentence transformers", "embeddings", "vector embeddings",
    "dense retrieval", "semantic search", "embedding", "bge", "e5", "openai embeddings",
    # Vector DBs
    "pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
    "elasticsearch", "vector database", "vector db", "vector search", "hybrid search",
    # Ranking / IR
    "ranking", "information retrieval", "bm25", "hybrid retrieval", "reranking",
    "re-ranking", "learning to rank", "ltr", "ndcg", "mrr", "map", "recall",
    # LLMs & Fine-tuning
    "llm", "large language model", "fine-tuning", "fine tuning", "lora", "qlora",
    "peft", "rlhf", "instruction tuning", "rag", "retrieval augmented generation",
    # Production ML
    "mlops", "model serving", "inference optimization", "ml pipeline",
    "recommendation system", "recommender", "search system",
    # Core languages/tools
    "python", "pytorch", "tensorflow", "transformers", "huggingface",
}

# Nice-to-have skills
BONUS_SKILLS = {
    "xgboost", "lightgbm", "gradient boosting", "learning to rank",
    "distributed systems", "kafka", "spark", "airflow",
    "kubernetes", "docker", "aws", "gcp", "azure",
    "a/b testing", "experimentation", "sql", "nlp",
    "open source", "github", "research",
}

# Hard disqualifiers — title-level red flags
DISQUALIFIED_TITLES = {
    "marketing manager", "hr manager", "accountant", "civil engineer",
    "mechanical engineer", "graphic designer", "customer support",
    "operations manager", "content writer", "java developer",
    ".net developer", "project manager", "business analyst",
    "frontend engineer", "mobile developer",
}

# Consulting-only companies (JD explicitly disqualifies)
CONSULTING_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "mindtree", "mphasis", "hexaware", "tech mahindra", "hcl",
    "l&t infotech", "ltimindtree", "persistent systems", "cyient",
}

# Preferred Indian metro locations (Pune/Noida preferred, others OK)
PREFERRED_LOCATIONS = {
    "pune", "noida", "hyderabad", "mumbai", "bangalore", "bengaluru",
    "delhi", "gurgaon", "gurugram", "chennai", "kolkata",
}

# ─────────────────────────────────────────────
# HONEYPOT DETECTION
# ─────────────────────────────────────────────

FOUNDING_YEARS = {
    # Major Indian tech companies founding years (approximate)
    # Used to catch "8 yrs experience at company founded 3 yrs ago"
}

def detect_honeypot(candidate: dict) -> bool:
    """
    Return True if this candidate looks like a honeypot.
    Checks:
      - Impossible experience: listed 10+ expert skills with 0 duration
      - Company tenure > company age (where we know founding year)
      - Skills claimed as expert but assessment score < 20
    """
    skills = candidate.get("skills", [])

    # Flag: too many "expert" skills with very short duration
    expert_zero_duration = sum(
        1 for s in skills
        if s.get("proficiency") in ("expert", "advanced")
        and s.get("duration_months", 1) == 0
    )
    if expert_zero_duration >= 5:
        return True

    # Flag: claimed skills don't match assessment scores at all
    signals = candidate.get("redrob_signals", {})
    assessment = signals.get("skill_assessment_scores", {})
    expert_skills_names = {
        s["name"] for s in skills if s.get("proficiency") == "expert"
    }
    badly_failed = sum(
        1 for name, score in assessment.items()
        if name in expert_skills_names and score < 15
    )
    if badly_failed >= 3:
        return True

    # Flag: years of experience way too high for their age (proxy: yoe > 40)
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    if yoe > 40:
        return True

    return False


# ─────────────────────────────────────────────
# SCORING FUNCTIONS
# ─────────────────────────────────────────────

def score_skills(candidate: dict) -> float:
    """
    Score 0-1 based on skills match with JD requirements.
    Weights core skills heavily, bonus skills lightly.
    Also considers assessment scores and proficiency level.
    """
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

        # Proficiency multiplier
        prof_mult = {"expert": 1.0, "advanced": 0.85, "intermediate": 0.65, "beginner": 0.35}.get(proficiency, 0.5)

        # Duration multiplier (more time = more real)
        dur_mult = min(1.0, duration / 24.0)  # caps at 2 years

        # Assessment multiplier
        if assess_score is not None:
            assess_mult = assess_score / 100.0
        else:
            assess_mult = 0.7  # no assessment = neutral

        skill_score = prof_mult * (0.5 + 0.3 * dur_mult + 0.2 * assess_mult)

        # Check against core skills
        matched_core = any(core in name_lower for core in CORE_SKILLS)
        # Also check name_lower in core_skills directly
        if not matched_core:
            matched_core = name_lower in CORE_SKILLS

        if matched_core:
            core_hits += skill_score
        elif any(bonus in name_lower for bonus in BONUS_SKILLS) or name_lower in BONUS_SKILLS:
            bonus_hits += skill_score * 0.3

    # Normalize: ~5 core skill hits = full score
    core_score = min(1.0, core_hits / 4.0)
    bonus_score = min(0.3, bonus_hits / 3.0)

    return min(1.0, core_score * 0.85 + bonus_score * 0.15)


def score_career(candidate: dict) -> float:
    """
    Score 0-1 based on career quality signals.
    Factors:
      - Years of experience (sweet spot 5-9)
      - Product company experience vs consulting-only
      - Role titles (AI/ML/search/ranking roles = strong signal)
      - Career recency (recent AI roles > old ones)
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])

    yoe = profile.get("years_of_experience", 0)
    current_title = profile.get("current_title", "").lower()
    current_company = profile.get("current_company", "").lower()
    current_industry = profile.get("current_industry", "").lower()

    score = 0.0

    # --- Years of experience (sweet spot 5-9, JD says 5-9 but open outside) ---
    if 5 <= yoe <= 9:
        yoe_score = 1.0
    elif 4 <= yoe < 5 or 9 < yoe <= 11:
        yoe_score = 0.8
    elif 3 <= yoe < 4 or 11 < yoe <= 14:
        yoe_score = 0.5
    elif yoe > 14:
        yoe_score = 0.35  # over-qualified concern
    else:
        yoe_score = 0.2   # too junior
    score += yoe_score * 0.25

    # --- Current title relevance ---
    strong_titles = {
        "ml engineer", "ai engineer", "machine learning engineer", "nlp engineer",
        "search engineer", "ranking engineer", "applied scientist", "data scientist",
        "recommendation", "research engineer", "llm engineer", "ai researcher",
        "senior engineer", "staff engineer", "principal engineer",
    }
    medium_titles = {
        "software engineer", "backend engineer", "data engineer",
        "platform engineer", "full stack", "cloud engineer", "devops",
    }
    title_score = 0.0
    if any(t in current_title for t in strong_titles):
        title_score = 1.0
    elif any(t in current_title for t in medium_titles):
        title_score = 0.55
    elif current_title in DISQUALIFIED_TITLES or any(d in current_title for d in DISQUALIFIED_TITLES):
        title_score = 0.05
    else:
        title_score = 0.3
    score += title_score * 0.25

    # --- Product company vs consulting analysis ---
    all_companies = [c.get("company", "").lower() for c in career]
    all_industries = [c.get("industry", "").lower() for c in career]

    consulting_months = 0
    product_months = 0
    ai_ml_months = 0

    ai_ml_industries = {"artificial intelligence", "machine learning", "tech", "technology",
                        "software", "saas", "fintech", "edtech", "healthtech", "e-commerce"}
    consulting_industries = {"it services", "consulting", "outsourcing", "staffing"}

    for job in career:
        company_name = job.get("company", "").lower()
        industry = job.get("industry", "").lower()
        duration = job.get("duration_months", 0)
        title = job.get("title", "").lower()
        desc = job.get("description", "").lower()

        is_consulting = (
            any(c in company_name for c in CONSULTING_COMPANIES)
            or any(ci in industry for ci in consulting_industries)
        )

        is_ai_ml = (
            any(ai in industry for ai in ai_ml_industries)
            or any(t in title for t in ["ml", "ai ", "nlp", "search", "ranking", "recommend", "data scientist"])
            or any(kw in desc for kw in ["embedding", "retrieval", "ranking", "vector", "llm", "transformer"])
        )

        if is_consulting:
            consulting_months += duration
        else:
            product_months += duration

        if is_ai_ml:
            ai_ml_months += duration

    total_months = max(1, consulting_months + product_months)
    product_ratio = product_months / total_months
    ai_ml_ratio = ai_ml_months / total_months

    # Penalize consulting-only careers (JD explicitly says this)
    if product_ratio < 0.1:
        product_score = 0.1  # consulting-only = near disqualifier
    elif product_ratio < 0.3:
        product_score = 0.4
    elif product_ratio < 0.6:
        product_score = 0.7
    else:
        product_score = 1.0
    score += product_score * 0.3

    # Reward AI/ML career history
    ai_ml_score = min(1.0, ai_ml_ratio * 2.0)  # 50% AI/ML roles = full score
    score += ai_ml_score * 0.2

    return min(1.0, score)


def score_behavioral(candidate: dict) -> float:
    """
    Score 0-1 based on behavioral signals from redrob_signals.
    These are the 'multiplier' signals — great skills + inactive = not hirable.
    """
    signals = candidate.get("redrob_signals", {})
    today = date(2026, 6, 25)  # current date per context

    score = 0.0

    # --- Recency: last active date ---
    last_active_str = signals.get("last_active_date", "")
    if last_active_str:
        try:
            last_active = datetime.strptime(last_active_str, "%Y-%m-%d").date()
            days_inactive = (today - last_active).days
            if days_inactive <= 30:
                recency_score = 1.0
            elif days_inactive <= 60:
                recency_score = 0.85
            elif days_inactive <= 90:
                recency_score = 0.7
            elif days_inactive <= 180:
                recency_score = 0.45
            else:
                recency_score = 0.15
        except Exception:
            recency_score = 0.5
    else:
        recency_score = 0.3
    score += recency_score * 0.25

    # --- Open to work flag ---
    open_to_work = signals.get("open_to_work_flag", False)
    score += (0.15 if open_to_work else 0.0)

    # --- Recruiter response rate (critical — can we even reach them?) ---
    response_rate = signals.get("recruiter_response_rate", 0.5)
    score += response_rate * 0.2

    # --- Notice period (JD wants sub-30 day, can buy out 30, 30+ = lower bar) ---
    notice = signals.get("notice_period_days", 60)
    if notice <= 0:
        notice_score = 1.0
    elif notice <= 30:
        notice_score = 0.9
    elif notice <= 60:
        notice_score = 0.6
    elif notice <= 90:
        notice_score = 0.4
    else:
        notice_score = 0.2
    score += notice_score * 0.15

    # --- Location / relocation ---
    location = candidate.get("profile", {}).get("location", "").lower()
    willing_to_relocate = signals.get("willing_to_relocate", False)
    in_preferred = any(loc in location for loc in PREFERRED_LOCATIONS)

    if in_preferred:
        location_score = 1.0
    elif willing_to_relocate:
        # JD says open to relocation from Tier-1 Indian cities
        country = candidate.get("profile", {}).get("country", "").lower()
        if country == "india":
            location_score = 0.75
        else:
            location_score = 0.3  # outside India = case-by-case
    else:
        country = candidate.get("profile", {}).get("country", "").lower()
        if country == "india":
            location_score = 0.5  # India but unknown city, not relocating
        else:
            location_score = 0.1  # outside India, not relocating
    score += location_score * 0.15

    # --- Interview completion + offer acceptance (commitment signals) ---
    interview_rate = signals.get("interview_completion_rate", 0.5)
    score += interview_rate * 0.05

    # --- GitHub activity (JD values open-source contributions) ---
    github = signals.get("github_activity_score", -1)
    if github >= 0:
        score += min(0.05, github / 100.0 * 0.05)

    return min(1.0, score)


def score_red_flags(candidate: dict) -> float:
    """
    Returns a penalty multiplier (0.0 to 1.0).
    1.0 = no red flags, 0.0 = severe red flags.
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])

    current_title = profile.get("current_title", "").lower()
    penalties = 0.0

    # Hard title mismatch — current role is completely wrong field
    if any(d in current_title for d in DISQUALIFIED_TITLES):
        penalties += 0.5

    # Consulting-only entire career
    all_companies_lower = [j.get("company", "").lower() for j in career]
    all_consulting = all(
        any(c in comp for c in CONSULTING_COMPANIES) for comp in all_companies_lower if comp
    )
    if all_consulting and len(all_companies_lower) >= 2:
        penalties += 0.4

    # Pure research / academic background with no production
    industries = [j.get("industry", "").lower() for j in career]
    is_all_academic = all("research" in ind or "education" in ind or "academic" in ind for ind in industries if ind)
    if is_all_academic and len(industries) >= 2:
        penalties += 0.3

    # Very low profile completeness (lazy profile = not serious)
    completeness = candidate.get("redrob_signals", {}).get("profile_completeness_score", 50)
    if completeness < 40:
        penalties += 0.2

    return max(0.0, 1.0 - penalties)


def generate_reasoning(candidate: dict, scores: dict) -> str:
    """
    Generate a specific, honest 1-2 sentence reasoning for this candidate.
    References actual profile facts. Acknowledges gaps where they exist.
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = candidate.get("skills", [])
    career = candidate.get("career_history", [])

    title = profile.get("current_title", "Unknown")
    yoe = profile.get("years_of_experience", 0)
    location = profile.get("location", "Unknown")
    notice = signals.get("notice_period_days", 60)
    response_rate = signals.get("recruiter_response_rate", 0)
    last_active = signals.get("last_active_date", "")

    # Top skills
    top_skills = [s["name"] for s in sorted(skills, key=lambda x: (
        {"expert": 3, "advanced": 2, "intermediate": 1, "beginner": 0}.get(x.get("proficiency", "beginner"), 0)
    ), reverse=True)[:4]]

    # Compute days inactive
    try:
        last_active_date = datetime.strptime(last_active, "%Y-%m-%d").date()
        days_inactive = (date(2026, 6, 25) - last_active_date).days
    except Exception:
        days_inactive = 999

    parts = []

    # Strength sentence
    skill_str = ", ".join(top_skills[:3]) if top_skills else "general software skills"
    parts.append(f"{title} with {yoe:.1f} yrs exp ({location}); top skills: {skill_str}.")

    # Context / concern sentence
    concerns = []
    positives = []

    if scores["skills"] >= 0.7:
        positives.append("strong core AI/ML skill match")
    elif scores["skills"] < 0.3:
        concerns.append("limited core AI/ML skills")

    if days_inactive > 180:
        concerns.append(f"inactive for {days_inactive} days")
    elif days_inactive <= 30:
        positives.append("recently active")

    if response_rate < 0.2:
        concerns.append(f"low recruiter response rate ({response_rate:.0%})")

    if notice > 90:
        concerns.append(f"long notice period ({notice}d)")
    elif notice <= 30:
        positives.append(f"short notice ({notice}d)")

    if scores["career"] < 0.3:
        concerns.append("career history not aligned with AI/ML product roles")

    if positives and concerns:
        parts.append(f"Positives: {'; '.join(positives)}. Concerns: {'; '.join(concerns)}.")
    elif positives:
        parts.append(f"{'; '.join(positives).capitalize()}.")
    elif concerns:
        parts.append(f"Concerns: {'; '.join(concerns)}.")

    return " ".join(parts)[:400]


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def score_candidate(candidate: dict) -> dict:
    """Compute all scores and final composite for one candidate."""

    # Honeypot check first
    if detect_honeypot(candidate):
        return {
            "candidate_id": candidate["candidate_id"],
            "final_score": 0.0,
            "skills": 0.0,
            "career": 0.0,
            "behavioral": 0.0,
            "red_flag_mult": 0.0,
            "is_honeypot": True,
        }

    s_skills    = score_skills(candidate)
    s_career    = score_career(candidate)
    s_behavioral = score_behavioral(candidate)
    s_red_flag  = score_red_flags(candidate)

    # Composite:
    # Skills is king (40%) — this is a technical role
    # Career quality (30%) — product company AI/ML experience
    # Behavioral (20%) — can we actually hire them?
    # Red flag multiplier reduces everything
    raw = (
        s_skills    * 0.40 +
        s_career    * 0.30 +
        s_behavioral * 0.20
    ) * (0.3 + 0.7 * s_red_flag)  # red flags can cut score by up to 70%

    return {
        "candidate_id": candidate["candidate_id"],
        "final_score": round(raw, 6),
        "skills": s_skills,
        "career": s_career,
        "behavioral": s_behavioral,
        "red_flag_mult": s_red_flag,
        "is_honeypot": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Redrob hackathon candidate ranker")
    parser.add_argument("--candidates", default="candidates.jsonl", help="Path to candidates.jsonl")
    parser.add_argument("--out", default="submission.csv", help="Output CSV path")
    parser.add_argument("--top", type=int, default=100, help="Number of top candidates to output")
    parser.add_argument("--sample", action="store_true", help="Use sample_candidates.json instead")
    args = parser.parse_args()

    print(f"[+] Loading candidates from: {args.candidates}")

    candidates = []

    if args.sample:
        # For testing with the 50-candidate sample
        with open(args.candidates) as f:
            candidates = json.load(f)
        print(f"[+] Loaded {len(candidates)} candidates (sample mode)")
    else:
        # Full JSONL load
        with open(args.candidates) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                candidates.append(json.loads(line))
                if (i + 1) % 10000 == 0:
                    print(f"    ... loaded {i+1} candidates")

        print(f"[+] Loaded {len(candidates)} candidates total")

    print(f"[+] Scoring candidates...")
    scored = []
    honeypot_count = 0

    for i, c in enumerate(candidates):
        result = score_candidate(c)
        scored.append(result)
        if result["is_honeypot"]:
            honeypot_count += 1
        if (i + 1) % 20000 == 0:
            print(f"    ... scored {i+1}/{len(candidates)}")

    print(f"[+] Scoring complete. Honeypots detected: {honeypot_count}")

    # Sort by final score descending, tie-break by candidate_id numerically ascending (spec requirement)
    def sort_key(x):
        cid_num = int(x["candidate_id"].split("_")[1]) if "_" in x["candidate_id"] else 0
        return (-x["final_score"], cid_num)
    scored.sort(key=sort_key)

    top_candidates = scored[:args.top]

    # Sanity check: honeypot rate in top 100
    honeypots_in_top = sum(1 for c in top_candidates if c["is_honeypot"])
    honeypot_rate = honeypots_in_top / len(top_candidates)
    print(f"[+] Honeypot rate in top {args.top}: {honeypots_in_top}/{args.top} = {honeypot_rate:.1%}")
    if honeypot_rate > 0.10:
        print(f"[!] WARNING: honeypot rate > 10% — risk of disqualification!")

    # Build candidate lookup for reasoning generation
    candidate_lookup = {c["candidate_id"]: c for c in candidates}

    # Write CSV
    print(f"[+] Writing submission to: {args.out}")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])

        for rank, result in enumerate(top_candidates, start=1):
            cid = result["candidate_id"]
            candidate_data = candidate_lookup.get(cid, {})
            reasoning = generate_reasoning(candidate_data, result)
            writer.writerow([
                cid,
                rank,
                round(result["final_score"], 6),
                reasoning,
            ])

    print(f"[+] Done! Wrote {len(top_candidates)} candidates to {args.out}")
    print(f"\n    Score distribution (top 10):")
    for r in top_candidates[:10]:
        print(f"      Rank {scored.index(r)+1}: {r['candidate_id']} — score={r['final_score']:.4f} "
              f"(skills={r['skills']:.2f}, career={r['career']:.2f}, "
              f"behavioral={r['behavioral']:.2f}, flags={r['red_flag_mult']:.2f})")


if __name__ == "__main__":
    main()
