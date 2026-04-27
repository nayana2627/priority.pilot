"""
PriorityPilot - AI-Powered Product Prioritization Agent
========================================================
Specialization: Transforms raw product ideas into ranked, reasoned priority lists
using multi-dimensional scoring — the way an experienced APO would think.

Powered by: Groq API (free tier — fastest LLM inference available)
Model     : llama-3.3-70b-versatile
Author    : [Your Name]
Version   : 3.0.0
"""

import os
import json
import time
import argparse
import urllib.request
import urllib.error
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

# ── Prompts ─────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are PriorityPilot, an elite AI Product Owner agent.

Your ONLY job is to take a list of product ideas or features and return a deeply reasoned priority ranking.

You think in 5 dimensions:
1. STRATEGIC FIT (0-10): How well does this align with the company's stated vision and current priorities?
2. USER IMPACT (0-10): How many users does this affect, and how deeply does it change their experience?
3. EFFORT ESTIMATE (0-10): Lower score = higher effort. A score of 10 means it ships in a day.
4. REVENUE / GROWTH LEVERAGE (0-10): Does this unlock new revenue, retention, or growth loops?
5. TIME SENSITIVITY (0-10): Is there a cost to delaying this? Competition, market window, user trust?

Your PRIORITY SCORE formula:
Priority = (Strategic Fit x 2) + (User Impact x 2) + Effort + (Revenue x 1.5) + Time Sensitivity
Max possible = 75

For each item you MUST provide:
- Dimension scores (all 5)
- Final priority score (out of 75)
- 2-sentence sharp reasoning
- One "risk if deprioritized" statement

Output STRICT JSON only.
Do NOT wrap in markdown.
Do NOT include ```json or ``` anywhere.
Do NOT include explanations before or after.
ONLY return a valid JSON object starting with { and ending with }.

JSON structure:
{
  "ranked_priorities": [
    {
      "rank": 1,
      "feature": "Feature name",
      "scores": {
        "strategic_fit": 9,
        "user_impact": 8,
        "effort": 7,
        "revenue_leverage": 9,
        "time_sensitivity": 8
      },
      "priority_score": 68.5,
      "reasoning": "Two sharp sentences explaining why this ranks here.",
      "risk_if_deprioritized": "One sentence on what happens if this is delayed."
    }
  ],
  "agent_summary": "2-3 sentences on the overall prioritization logic and what the team should focus on this sprint.",
  "top_priority_action": "One crisp sentence — the single most important thing to do next."
}"""

BASELINE_SYSTEM = """You are a helpful product manager assistant.
Given a list of product features or ideas, rank them by priority and briefly explain why."""


# ── Core API Call ────────────────────────────────────────────────────────────────
def call_groq(system: str, user_message: str) -> tuple:
    """Call Groq API and return (response_text, elapsed_seconds)."""
    if not GROQ_API_KEY:
        raise ValueError(
            "\n ERROR: GROQ_API_KEY not found!\n"
            "  1. Get your FREE key at: https://console.groq.com\n"
            "  2. Add to your .env file: GROQ_API_KEY=gsk_your_key_here\n"
        )

    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_message}
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }).encode("utf-8")

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST"
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Groq API error {e.code}:\n{body}")

    elapsed = round(time.time() - start, 2)
    text = data["choices"][0]["message"]["content"].strip()
    return text, elapsed


def clean_json(raw: str) -> str:
    """Extract valid JSON from model output."""
    raw = raw.strip()

    # Remove markdown fences if present
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                return part

    # Extract JSON substring
    start = raw.find("{")
    end = raw.rfind("}") + 1

    if start != -1 and end > start:
        return raw[start:end]

    raise ValueError("No valid JSON found in model output")

# ── Agent Functions ──────────────────────────────────────────────────────────────
def run_prioritypilot(features: list, context: str = "", verbose: bool = True) -> dict:
    """Run PriorityPilot agent. Returns structured priority ranking."""
    feature_list  = "\n".join(f"- {f}" for f in features)
    context_block = f"\nCompany context: {context}" if context else ""

    user_message = f"""Please prioritize the following product features/ideas:{context_block}

{feature_list}

Return your full priority analysis as JSON."""

    if verbose:
        print("\n Analyzing " + str(len(features)) + " features...")
        print("   Model: " + MODEL + " via Groq (free tier)\n")

    raw, elapsed = call_groq(SYSTEM_PROMPT, user_message)
    cleaned = clean_json(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("\n❌ JSON parse failed")
        print("Error:", e)
        print("\n--- RAW OUTPUT ---\n", raw[:800])

    # Try one more aggressive cleanup
        try:
            cleaned = raw[raw.index("{"): raw.rindex("}")+1]
            result = json.loads(cleaned)
        except:
            raise RuntimeError("Model did not return valid JSON")

    result["_meta"] = {
        "model": MODEL,
        "provider": "Groq (free tier)",
        "response_time_seconds": elapsed,
        "features_analyzed": len(features)
    }
    return result


def run_baseline(features: list, context: str = "") -> dict:
    """Run same model with NO specialized prompt — for benchmark comparison."""
    feature_list  = "\n".join(f"- {f}" for f in features)
    context_block = f"\nContext: {context}" if context else ""

    user_message = f"""Please prioritize these product features:{context_block}

{feature_list}"""

    print("   Running baseline (no agent system prompt)...")
    raw, elapsed = call_groq(BASELINE_SYSTEM, user_message)

    return {
        "raw_response": raw,
        "_meta": {
            "model": MODEL + " (no system prompt)",
            "provider": "Groq (free tier)",
            "response_time_seconds": elapsed,
        }
    }


# ── Scoring ──────────────────────────────────────────────────────────────────────
def calculate_performance_score(result: dict) -> dict:
    """
    PriorityPilot Performance Scoring System — scale 1 to 10,000.

    Dimensions:
    - Structured Output Quality  (0-2500)
    - Reasoning Depth            (0-2500)
    - Dimensional Coverage       (0-2000)
    - Actionability              (0-2000)
    - Speed Efficiency           (0-1000)
    """
    score     = 0
    breakdown = {}

    # 1. Structured Output Quality (2500 pts)
    has_ranked  = "ranked_priorities" in result and len(result["ranked_priorities"]) > 0
    has_summary = "agent_summary" in result
    has_action  = "top_priority_action" in result
    struct_score = (833 if has_ranked else 0) + (833 if has_summary else 0) + (834 if has_action else 0)
    score += struct_score
    breakdown["structured_output_quality"] = {"score": struct_score, "max": 2500}

    # 2. Reasoning Depth (2500 pts)
    items = result.get("ranked_priorities", [])
    reasoning_pts = 0
    for item in items:
        if bool(item.get("reasoning", "").strip()):
            reasoning_pts += 150
        if bool(item.get("risk_if_deprioritized", "").strip()):
            reasoning_pts += 100
    reasoning_score = min(reasoning_pts, 2500)
    score += reasoning_score
    breakdown["reasoning_depth"] = {"score": reasoning_score, "max": 2500}

    # 3. Dimensional Coverage (2000 pts)
    required_dims = {"strategic_fit", "user_impact", "effort", "revenue_leverage", "time_sensitivity"}
    dim_hits  = sum(1 for item in items if set(item.get("scores", {}).keys()) >= required_dims)
    dim_score = min(int((dim_hits / max(len(items), 1)) * 2000), 2000)
    score += dim_score
    breakdown["dimensional_coverage"] = {"score": dim_score, "max": 2000}

    # 4. Actionability (2000 pts)
    action       = result.get("top_priority_action", "")
    action_score = 2000 if len(action) > 20 else (1000 if len(action) > 5 else 0)
    score += action_score
    breakdown["actionability"] = {"score": action_score, "max": 2000}

    # 5. Speed Efficiency (1000 pts)
    elapsed = result.get("_meta", {}).get("response_time_seconds", 99)
    if elapsed < 5:
        speed_score = 1000
    elif elapsed < 10:
        speed_score = 700
    elif elapsed < 20:
        speed_score = 400
    else:
        speed_score = 100
    score += speed_score
    breakdown["speed_efficiency"] = {"score": speed_score, "max": 1000, "response_time_seconds": elapsed}

    return {
        "total_score": score,
        "max_possible": 10000,
        "percentage": round((score / 10000) * 100, 1),
        "breakdown": breakdown,
        "grade": "S" if score >= 9000 else "A" if score >= 7500 else "B" if score >= 6000 else "C"
    }


# ── Display ──────────────────────────────────────────────────────────────────────
def print_results(result: dict, perf: dict, baseline: dict):
    """Pretty-print the full comparison report."""

    print("\n" + "=" * 60)
    print("  PRIORITYPILOT RESULTS")
    print("=" * 60)

    for item in result.get("ranked_priorities", []):
        print(f"\n#{item['rank']} -- {item['feature']}")
        print(f"   Priority Score : {item['priority_score']}/75")
        s = item.get("scores", {})
        print(f"   Strategic Fit  : {s.get('strategic_fit')}/10  |  "
              f"User Impact : {s.get('user_impact')}/10  |  "
              f"Effort : {s.get('effort')}/10")
        print(f"   Revenue        : {s.get('revenue_leverage')}/10  |  "
              f"Time Sensitivity : {s.get('time_sensitivity')}/10")
        print(f"   Reasoning : {item.get('reasoning')}")
        print(f"   Risk      : {item.get('risk_if_deprioritized')}")

    print(f"\nSUMMARY    : {result.get('agent_summary')}")
    print(f"TOP ACTION : {result.get('top_priority_action')}")

    print("\n" + "=" * 60)
    print("  PERFORMANCE SCORE")
    print("=" * 60)
    print(f"  Total Score : {perf['total_score']} / 10,000")
    print(f"  Grade       : {perf['grade']}")
    print(f"  Percentage  : {perf['percentage']}%")
    for k, v in perf["breakdown"].items():
        label  = k.replace("_", " ").title()
        filled = int((v["score"] / v["max"]) * 20) if v["max"] else 0
        bar    = "=" * filled + "-" * (20 - filled)
        print(f"  {label:35s} [{bar}]  {v['score']}/{v['max']}")

    print("\n" + "=" * 60)
    print("  BASELINE COMPARISON (same model, no agent)")
    print("=" * 60)
    baseline_text = baseline.get("raw_response", "N/A")
    print(baseline_text[:700] + ("..." if len(baseline_text) > 700 else ""))
    print(f"\n  PriorityPilot response time : {result['_meta']['response_time_seconds']}s")
    print(f"  Baseline response time      : {baseline['_meta']['response_time_seconds']}s")
    print()
    print("  PriorityPilot vs Baseline:")
    print("  [+] Structured JSON output       vs  unstructured prose")
    print("  [+] 5-dimensional scoring         vs  vague gut-feel ranking")
    print("  [+] Risk analysis per feature     vs  no risk analysis")
    print("  [+] Actionable next step          vs  general advice only")
    print("  [+] Machine-readable & pipeable   vs  human-read only")


# ── Demo Data ────────────────────────────────────────────────────────────────────
DEMO_FEATURES = [
    "Binance portfolio tracker with P&L analysis",
    "AI-powered trade journaling with pattern recognition",
    "Multi-exchange aggregator dashboard",
    "Telegram bot for price alerts",
    "Social trading feed — follow top traders",
]
DEMO_CONTEXT = "Crypto trading productivity app, early-stage startup, 500 beta users"


# ── Entry Point ──────────────────────────────────────────────────────────────────
def interactive_mode():
    print("\n" + "=" * 60)
    print("  PRIORITYPILOT — Interactive Mode")
    print("  Type 'demo' at context prompt to use demo data")
    print("=" * 60)

    print("\nEnter your product/company context:")
    context = input("  > ").strip()

    if context.lower() == "demo":
        context  = DEMO_CONTEXT
        features = DEMO_FEATURES
    else:
        print("\nEnter features one per line (blank line when done):")
        features = []
        while True:
            line = input("  > ").strip()
            if not line:
                break
            features.append(line)

    if not features:
        print("No features entered. Exiting.")
        return

    result   = run_prioritypilot(features, context)
    baseline = run_baseline(features, context)
    perf     = calculate_performance_score(result)
    print_results(result, perf, baseline)

    output = {"prioritypilot_result": result, "performance_score": perf, "baseline_comparison": baseline}
    with open("prioritypilot_output.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nFull results saved to prioritypilot_output.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PriorityPilot — AI Product Prioritization Agent")
    parser.add_argument("--demo",     action="store_true", help="Run with built-in demo data")
    parser.add_argument("--features", nargs="+",           help="Features to prioritize")
    parser.add_argument("--context",  default="",          help="Company/product context")
    args = parser.parse_args()

    if args.demo:
        print("\n PriorityPilot Agent Running...")
        result   = run_prioritypilot(DEMO_FEATURES, DEMO_CONTEXT)
        baseline = run_baseline(DEMO_FEATURES, DEMO_CONTEXT)
        perf     = calculate_performance_score(result)
        print_results(result, perf, baseline)
        with open("prioritypilot_output.json", "w") as f:
            json.dump({"prioritypilot_result": result,
                       "performance_score": perf,
                       "baseline_comparison": baseline}, f, indent=2)
        print("\nSaved to prioritypilot_output.json")

    elif args.features:
        result   = run_prioritypilot(args.features, args.context)
        baseline = run_baseline(args.features, args.context)
        perf     = calculate_performance_score(result)
        print_results(result, perf, baseline)

    else:
        interactive_mode()