#!/usr/bin/env python3
"""
RAG Retriever for behavior-psychology skill.
Handles embedding generation, case storage, similarity search, and user profiles.
"""

import json
import math
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# ── Paths ─────────────────────────────────────────────────────────
SKILL_DIR = Path(__file__).parent.parent
KB_DIR = SKILL_DIR / "knowledge_base"
CASES_PATH = KB_DIR / "cases.json"
PROFILES_PATH = KB_DIR / "user_profiles.json"

# ── Embedding (OpenAI API) ───────────────────────────────────────

def get_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    key = cfg.get("openai", {}).get("apiKey", "")
            except Exception:
                pass
    return key


def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """Generate embedding vector via OpenAI API."""
    import urllib.request
    import urllib.error

    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found in env or config")

    url = "https://api.openai.com/v1/embeddings"
    data = json.dumps({"model": model, "input": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["data"][0]["embedding"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Embedding API error: {e.code} {body}")


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Case Management ──────────────────────────────────────────────

def load_cases() -> Dict[str, Any]:
    if not CASES_PATH.exists():
        return {"version": "1.0", "cases": []}
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cases(data: Dict[str, Any]) -> None:
    with open(CASES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_case(user_description: str, behavior_tags: List[str],
             mechanisms: List[Dict], alternatives: List[str],
             outcome: str = "", notes: str = "") -> str:
    """Add a new case with embedding. Returns case ID."""
    import datetime
    data = load_cases()
    case_id = f"case_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Generate embedding
    try:
        embedding = get_embedding(user_description)
    except RuntimeError as e:
        print(
            f"[降级] embedding 生成失败（{e}）"
            f"→ 将存储空向量（该案例无法参与语义检索，仅能被关键词匹配召回）"
            f"→ 建议：检查 OPENAI_API_KEY 与网络连接后重新添加案例",
            file=sys.stderr,
        )
        embedding = []

    case = {
        "id": case_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "user_description": user_description,
        "behavior_tags": behavior_tags,
        "mechanisms": mechanisms,
        "alternatives": alternatives,
        "embedding": embedding,
        "outcome": outcome,
        "notes": notes,
    }
    data.setdefault("cases", []).append(case)
    save_cases(data)
    return case_id


def search_similar_cases(query_text: str, top_k: int = 3,
                         tag_filter: Optional[List[str]] = None) -> List[Tuple[Dict, float]]:
    """Search cases by semantic similarity. Returns [(case, score), ...]."""
    data = load_cases()
    cases = data.get("cases", [])
    if not cases:
        return []

    # Generate query embedding
    try:
        query_emb = get_embedding(query_text)
    except RuntimeError as e:
        print(
            f"[降级] embedding 生成失败（{e}）"
            f"→ 将回退到仅标签匹配（检索召回率与排序精度会降低）"
            f"→ 建议：检查 OPENAI_API_KEY 与网络连接后重新搜索",
            file=sys.stderr,
        )
        query_emb = []

    results = []
    for case in cases:
        # Tag-based pre-filter
        if tag_filter:
            case_tags = set(case.get("behavior_tags", []))
            if not any(t in case_tags for t in tag_filter):
                continue

        # Semantic similarity
        case_emb = case.get("embedding", [])
        if query_emb and case_emb:
            score = cosine_similarity(query_emb, case_emb)
        else:
            score = 0.0

        # Tag overlap boost
        if tag_filter:
            case_tags = set(case.get("behavior_tags", []))
            overlap = len(case_tags.intersection(set(tag_filter)))
            score += overlap * 0.15  # boost per matching tag

        results.append((case, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


# ── User Profiles ──────────────────────────────────────────────────

def load_profiles() -> Dict[str, Any]:
    if not PROFILES_PATH.exists():
        return {"version": "1.0", "profiles": {}}
    with open(PROFILES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profiles(data: Dict[str, Any]) -> None:
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_or_create_profile(person_key: str, relationship: str = "unknown") -> Dict[str, Any]:
    """Get or create a person profile."""
    data = load_profiles()
    profiles = data.setdefault("profiles", {})
    if person_key not in profiles:
        import datetime
        profiles[person_key] = {
            "relationship": relationship,
            "first_analyzed": datetime.datetime.now().isoformat(),
            "last_analyzed": datetime.datetime.now().isoformat(),
            "analysis_count": 0,
            "recurring_tags": [],
            "recurring_mechanisms": [],
            "user_notes": "",
            "confidence_trend": [],
        }
    return profiles[person_key]


def update_profile(person_key: str, behavior_tags: List[str],
                   mechanisms: List[Dict], confidence: float) -> None:
    """Update a person profile with new analysis data."""
    import datetime
    data = load_profiles()
    profiles = data.setdefault("profiles", {})

    if person_key not in profiles:
        return

    profile = profiles[person_key]
    profile["last_analyzed"] = datetime.datetime.now().isoformat()
    profile["analysis_count"] = profile.get("analysis_count", 0) + 1

    # Update recurring tags
    existing_tags = set(profile.get("recurring_tags", []))
    for tag in behavior_tags:
        existing_tags.add(tag)
    profile["recurring_tags"] = list(existing_tags)

    # Update recurring mechanisms
    existing_mechs = set(profile.get("recurring_mechanisms", []))
    for m in mechanisms:
        existing_mechs.add(m.get("name", ""))
    profile["recurring_mechanisms"] = list(existing_mechs)

    # Confidence trend
    trend = profile.get("confidence_trend", [])
    trend.append({"timestamp": datetime.datetime.now().isoformat(), "confidence": confidence})
    if len(trend) > 20:
        trend = trend[-20:]
    profile["confidence_trend"] = trend

    save_profiles(data)


def get_profile_summary(person_key: str) -> Optional[str]:
    """Generate a text summary of a person's profile for RAG injection."""
    data = load_profiles()
    profiles = data.get("profiles", {})
    if person_key not in profiles:
        return None

    p = profiles[person_key]
    lines = [
        f"[历史画像] 该人物已被分析 {p.get('analysis_count', 0)} 次。",
        f"关系类型: {p.get('relationship', 'unknown')}",
        f"高频行为标签: {', '.join(p.get('recurring_tags', []))}",
        f"高频心理机制: {', '.join(p.get('recurring_mechanisms', []))}",
    ]
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG Retriever for behavior-psychology")
    sub = parser.add_subparsers(dest="command")

    # add-case
    p_add = sub.add_parser("add-case", help="Add a new case with embedding")
    p_add.add_argument("description", help="User's behavior description")
    p_add.add_argument("--tags", nargs="+", default=[], help="Behavior tags")
    p_add.add_argument("--mechanisms", default="", help="JSON array of mechanisms")
    p_add.add_argument("--alternatives", nargs="+", default=[], help="Alternative explanations")
    p_add.add_argument("--outcome", default="", help="User's observed outcome")

    # search
    p_search = sub.add_parser("search", help="Search similar cases")
    p_search.add_argument("query", help="Query text")
    p_search.add_argument("--top-k", type=int, default=3, help="Number of results")
    p_search.add_argument("--tags", nargs="+", default=[], help="Filter by tags")

    # profile
    sub.add_parser("list-profiles", help="List all person profiles")

    p_update = sub.add_parser("update-profile", help="Update a person profile")
    p_update.add_argument("person_key", help="Person identifier")
    p_update.add_argument("--tags", nargs="+", default=[])
    p_update.add_argument("--mechanisms", default="")
    p_update.add_argument("--confidence", type=float, default=0.5)

    p_summary = sub.add_parser("profile-summary", help="Get profile summary text")
    p_summary.add_argument("person_key", help="Person identifier")

    args = parser.parse_args()

    if args.command == "add-case":
        mechs = json.loads(args.mechanisms) if args.mechanisms else []
        case_id = add_case(args.description, args.tags, mechs, args.alternatives, args.outcome)
        print(f"Added case: {case_id}")

    elif args.command == "search":
        results = search_similar_cases(args.query, args.top_k, args.tags or None)
        for case, score in results:
            print(f"\n[Score: {score:.3f}] {case['id']}")
            print(f"  Desc: {case['user_description'][:80]}")
            print(f"  Tags: {', '.join(case.get('behavior_tags', []))}")
            print(f"  Mechanisms: {', '.join(m['name'] for m in case.get('mechanisms', []))}")

    elif args.command == "list-profiles":
        data = load_profiles()
        for key, p in data.get("profiles", {}).items():
            print(f"{key}: {p.get('relationship', '?')} | analyzed {p.get('analysis_count', 0)} times | tags: {', '.join(p.get('recurring_tags', []))}")

    elif args.command == "update-profile":
        mechs = json.loads(args.mechanisms) if args.mechanisms else []
        update_profile(args.person_key, args.tags, mechs, args.confidence)
        print(f"Updated profile: {args.person_key}")

    elif args.command == "profile-summary":
        summary = get_profile_summary(args.person_key)
        print(summary or f"No profile found for {args.person_key}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
