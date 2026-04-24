def intensity_to_score(intensity: str) -> int:
    mapping = {
        "low": 0,
        "moderate": 1,
        "high": 2,
        "Low": 0,
        "Moderate": 1,
        "High": 2,
    }
    return mapping.get(str(intensity).strip(), 1)


def score_to_intensity(score: int) -> str:
    if score <= 0:
        return "Low"
    if score == 1:
        return "Moderate"
    return "High"


def summarize_user_history(recent_logs):
    if not recent_logs:
        return {
            "has_history": False,
            "completed_yes": 0,
            "completed_partial": 0,
            "completed_no": 0,
            "hard_count": 0,
            "easy_count": 0,
            "high_fatigue_count": 0,
            "low_fatigue_count": 0,
            "avg_rating": None,
            "history_note": "No previous workout history is available yet.",
        }

    completed_yes = 0
    completed_partial = 0
    completed_no = 0
    hard_count = 0
    easy_count = 0
    high_fatigue_count = 0
    low_fatigue_count = 0
    ratings = []

    for log in recent_logs:
        completed = str(log.get("completed", "")).lower()
        difficulty = str(log.get("difficulty", "")).lower()
        fatigue = str(log.get("fatigue_after_workout", "")).lower()

        if completed == "yes":
            completed_yes += 1
        elif completed == "partially":
            completed_partial += 1
        elif completed == "no":
            completed_no += 1

        if difficulty == "hard":
            hard_count += 1
        elif difficulty == "easy":
            easy_count += 1

        if fatigue == "high":
            high_fatigue_count += 1
        elif fatigue == "low":
            low_fatigue_count += 1

        feedback_rating = log.get("user_rating")
        if isinstance(feedback_rating, int):
            ratings.append(feedback_rating)

    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    history_note = (
        f"Based on {len(recent_logs)} recent workout logs, the system detected "
        f"{completed_yes} completed sessions, {completed_partial} partially completed sessions, "
        f"and {completed_no} missed sessions."
    )

    return {
        "has_history": True,
        "completed_yes": completed_yes,
        "completed_partial": completed_partial,
        "completed_no": completed_no,
        "hard_count": hard_count,
        "easy_count": easy_count,
        "high_fatigue_count": high_fatigue_count,
        "low_fatigue_count": low_fatigue_count,
        "avg_rating": avg_rating,
        "history_note": history_note,
    }


def adapt_recommendation_with_history(recommendation: dict, history_summary: dict):
    updated = dict(recommendation)

    updated["history_note"] = history_summary["history_note"]
    updated["history_adjustments"] = []

    if not history_summary["has_history"]:
        updated["history_adjustments"].append(
            "No previous workout logs were available, so the recommendation is based only on current profile and physiological data."
        )
        return updated

    current_score = intensity_to_score(updated["predicted_intensity"])
    adjusted_score = current_score

    # Too much fatigue / hard recent sessions -> reduce by 1 if possible
    if history_summary["high_fatigue_count"] >= 2 or history_summary["hard_count"] >= 2:
        adjusted_score -= 1
        updated["history_adjustments"].append(
            "Recent logs showed repeated hard sessions or high fatigue, so the plan was slightly reduced."
        )

    # Strong consistency + low fatigue -> increase by 1 if possible
    if (
        history_summary["completed_yes"] >= 2
        and history_summary["low_fatigue_count"] >= 1
        and history_summary["hard_count"] == 0
    ):
        adjusted_score += 1
        updated["history_adjustments"].append(
            "Recent logs showed good completion and manageable fatigue, so the system allowed a slightly stronger progression."
        )

    # Missed or partial sessions -> make plan more realistic
    if history_summary["completed_no"] >= 1 or history_summary["completed_partial"] >= 2:
        adjusted_score -= 1
        updated["history_adjustments"].append(
            "Because some recent sessions were missed or only partially completed, the next plan was adjusted to be more achievable."
        )

    adjusted_score = max(0, min(2, adjusted_score))

    old_intensity = updated["predicted_intensity"]
    new_intensity = score_to_intensity(adjusted_score)

    if new_intensity != old_intensity:
        updated["predicted_intensity"] = new_intensity

        if new_intensity == "Low":
            updated["duration"] = "20-30 min"
        elif new_intensity == "Moderate":
            updated["duration"] = "30-45 min"
        else:
            updated["duration"] = "45-60 min"

    # Extra history-based note for recovery
    if history_summary["high_fatigue_count"] >= 2:
        updated["recovery_advice"] += " Recent logs also suggest that extra recovery, hydration, and sleep should be prioritized."

    if history_summary["avg_rating"] is not None:
        updated["history_adjustments"].append(
            f"Average user rating from recent logs: {history_summary['avg_rating']} / 5."
        )

    return updated