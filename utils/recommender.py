def categorize_bmi(bmi: float) -> str:
    if bmi < 18.5:
        return "underweight"
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    return "obese"


def hydration_status(water_intake_liters: float) -> str:
    if water_intake_liters < 1.5:
        return "low"
    if water_intake_liters < 2.5:
        return "moderate"
    return "good"


def frequency_status(workout_frequency_days_week: int) -> str:
    if workout_frequency_days_week <= 2:
        return "low"
    if workout_frequency_days_week <= 4:
        return "moderate"
    return "high"


def intensity_to_score(model_intensity: str) -> int:
    mapping = {"low": 0, "moderate": 1, "high": 2}
    return mapping.get(model_intensity.lower(), 1)


def score_to_intensity(score: int) -> str:
    if score <= 0:
        return "low"
    if score == 1:
        return "moderate"
    return "high"


def clamp_to_one_step(base_score: int, adjusted_score: int) -> int:
    if adjusted_score > base_score + 1:
        return base_score + 1
    if adjusted_score < base_score - 1:
        return base_score - 1
    return adjusted_score


def choose_duration(intensity: str, experience_level: str, frequency: str) -> str:
    if intensity == "low":
        if experience_level == "beginner":
            return "20-25 min"
        if experience_level == "advanced":
            return "25-35 min"
        return "20-30 min"

    if intensity == "moderate":
        if frequency == "high":
            return "30-40 min"
        if experience_level == "advanced":
            return "40-50 min"
        return "30-45 min"

    if frequency == "high":
        return "40-50 min"
    if experience_level == "beginner":
        return "35-45 min"
    return "45-60 min"


def choose_workout_type(goal: str, intensity: str) -> str:
    goal_map = {
        "weight_loss": {
            "low": "Light cardio and mobility session",
            "moderate": "Cardio and bodyweight circuit",
            "high": "HIIT or intense cardio session"
        },
        "muscle_gain": {
            "low": "Light strength activation session",
            "moderate": "Moderate resistance training",
            "high": "Intense strength training"
        },
        "endurance": {
            "low": "Light aerobic recovery",
            "moderate": "Steady-state cardio session",
            "high": "Interval endurance training"
        },
        "general_fitness": {
            "low": "Mobility and stretching session",
            "moderate": "Mixed full-body workout",
            "high": "Functional full-body training"
        }
    }
    return goal_map[goal][intensity]


def choose_training_style(intensity: str) -> str:
    styles = {
        "low": "Light recovery-oriented training",
        "moderate": "Balanced moderate-intensity training",
        "high": "Demanding high-intensity training"
    }
    return styles[intensity]


def build_personal_insights(
    hydration: str,
    frequency: str,
    bmi_group: str,
    experience_level: str,
    session_duration_hours: float,
    hr_ratio: float
):
    insights = []

    if hydration == "low":
        insights.append("Your estimated daily water intake is low, so recovery and hydration should be prioritized.")
    elif hydration == "moderate":
        insights.append("Your hydration looks acceptable, but slightly increasing water intake may improve recovery.")

    if frequency == "high":
        insights.append("You already train frequently, so the plan should avoid unnecessary overload.")
    elif frequency == "low":
        insights.append("Your weekly training frequency is relatively low, so consistency is more important than volume.")

    if bmi_group in ["overweight", "obese"]:
        insights.append("A gradual workload increase is more suitable than sudden intensity spikes.")

    if experience_level == "beginner":
        insights.append("Because you are a beginner, the workout focuses on manageable exercises and clear structure.")
    elif experience_level == "advanced":
        insights.append("Your advanced level allows slightly more demanding exercise selection.")

    if session_duration_hours <= 0.4:
        insights.append("Your typical training duration is short, so the session is designed to stay practical and achievable.")
    elif session_duration_hours >= 1.1:
        insights.append("Your usual training duration suggests you can handle more volume in a single session.")

    if hr_ratio <= 0.35:
        insights.append("Your heart-rate response suggests a lighter training recommendation is more appropriate today.")
    elif hr_ratio >= 0.7:
        insights.append("Your heart-rate response suggests readiness for a stronger workload.")

    return insights[:5]


def build_recovery_advice(intensity: str, hydration: str, frequency: str) -> str:
    parts = []

    if intensity == "low":
        parts.append("Prioritize recovery, mobility, and controlled pacing.")
    elif intensity == "moderate":
        parts.append("Maintain a stable training pace and monitor your energy level.")
    else:
        parts.append("Include a cool-down and proper post-workout recovery.")

    if hydration == "low":
        parts.append("Increase water intake before and after exercise.")
    elif hydration == "moderate":
        parts.append("Maintain adequate hydration during the day.")
    else:
        parts.append("Your hydration pattern appears supportive of recovery.")

    if frequency == "high":
        parts.append("Since you train often, avoid excessive overload.")
    elif frequency == "low":
        parts.append("Focus on consistency and progressive adaptation.")

    return " ".join(parts)


def build_explanation(model_intensity: str, final_intensity: str, factors, goal: str) -> str:
    parts = [
        f"The machine learning model estimated {model_intensity} physiological intensity.",
        f"The final recommendation remained within one adaptive step and resulted in {final_intensity} intensity.",
        f"The final workout type was aligned with the goal of {goal.replace('_', ' ')}."
    ]

    if factors:
        parts.append("Main adjustment factors: " + "; ".join(factors) + ".")

    return " ".join(parts)


def generate_recommendation(
    model_intensity: str,
    goal: str,
    focus_area: str,
    equipment: str,
    experience_level: str,
    bmi: float,
    water_intake_liters: float,
    workout_frequency_days_week: int,
    session_duration_hours: float,
    avg_bpm: float,
    resting_bpm: float,
    max_bpm: float
):
    base_score = intensity_to_score(model_intensity)
    adjusted_score = base_score
    factors = []

    bmi_group = categorize_bmi(bmi)
    hydration = hydration_status(water_intake_liters)
    frequency = frequency_status(workout_frequency_days_week)

    hr_range = max(max_bpm - resting_bpm, 1.0)
    hr_ratio = (avg_bpm - resting_bpm) / hr_range

    if experience_level == "beginner":
        adjusted_score -= 1
        factors.append("beginner level reduced exercise complexity")
    elif experience_level == "advanced":
        adjusted_score += 1
        factors.append("advanced level supports a more demanding session")

    if hydration == "low":
        adjusted_score -= 1
        factors.append("low hydration reduced the final workload")

    if frequency == "high":
        adjusted_score -= 1
        factors.append("high weekly frequency reduced the session load")
    elif frequency == "low":
        factors.append("low weekly frequency supported manageable progression")

    if goal == "weight_loss" and bmi_group in ["overweight", "obese"]:
        adjusted_score -= 1
        factors.append("weight-loss profile emphasized safer progression")

    if session_duration_hours >= 1.1:
        adjusted_score += 1
        factors.append("longer usual sessions support more training volume")
    elif session_duration_hours <= 0.4:
        adjusted_score -= 1
        factors.append("very short usual sessions reduced the recommended load")

    if hr_ratio >= 0.7:
        adjusted_score += 1
        factors.append("higher heart-rate response suggested stronger exercise readiness")
    elif hr_ratio <= 0.35:
        adjusted_score -= 1
        factors.append("lower heart-rate response suggested a lighter training recommendation")

    adjusted_score = clamp_to_one_step(base_score, adjusted_score)
    adjusted_score = max(0, min(2, adjusted_score))

    final_intensity = score_to_intensity(adjusted_score)
    workout_type = choose_workout_type(goal, final_intensity)
    training_style = choose_training_style(final_intensity)
    duration = choose_duration(final_intensity, experience_level, frequency)
    recovery_advice = build_recovery_advice(final_intensity, hydration, frequency)
    explanation = build_explanation(
        model_intensity=model_intensity,
        final_intensity=final_intensity,
        factors=factors,
        goal=goal
    )

    personal_insights = build_personal_insights(
        hydration=hydration,
        frequency=frequency,
        bmi_group=bmi_group,
        experience_level=experience_level,
        session_duration_hours=session_duration_hours,
        hr_ratio=hr_ratio
    )

    return {
        "predicted_intensity": final_intensity.title(),
        "workout_type": workout_type,
        "duration": duration,
        "style": training_style,
        "recovery_advice": recovery_advice,
        "explanation": explanation,
        "personal_insights": personal_insights
    }