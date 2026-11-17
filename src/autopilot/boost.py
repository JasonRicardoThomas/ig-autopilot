"""$100 paid-boost plan for the best organic Reel (boosting itself is done in the Instagram app)."""
import json

from .util import POSTS, read_json


def best_reel(insights_path=None):
    """Pick the published Reel with the best engagement; insights come from a JSON file you paste in the review page, or fall back to the newest."""
    posts = [read_json(p) for p in sorted(POSTS.glob("*.json"))]
    reels = [p for p in posts if p["kind"] == "reel" and p["status"] == "published"]
    if not reels:
        return None
    ins = read_json(insights_path, {}) if insights_path else {}
    return max(reels, key=lambda p: (ins.get(p["id"], {}).get("saves", 0) * 3 + ins.get(p["id"], {}).get("shares", 0) * 2
                                      + ins.get(p["id"], {}).get("likes", 0), p["scheduled_for"]))


def plan(total=100, days=10):
    per_day = round(total / days, 2)
    return {
        "budget_usd": total, "days": days, "per_day_usd": per_day, "goal": "Profile visits",
        "audience": {"locations": ["Mexico City", "Madrid", "Seville"], "ages": "25-45",
                     "interests": ["Business English", "Language learning", "Professional development", "Writing"]},
        "steps": ["Wait 5 to 7 days after a Reel posts and read its saves and shares.",
                  "Boost the Reel with the most saves + shares, not the most likes.",
                  f"In the Instagram app: open the Reel, tap Boost, goal Profile visits, audience as above, ${per_day}/day for {days} days.",
                  "Do not boost a Reel with a stock-photo-only look or approximate event dates.",
                  "After 10 days, note cost per profile visit; repeat only if it is under about $0.50."],
    }


if __name__ == "__main__":
    print(json.dumps(plan(), indent=2))
