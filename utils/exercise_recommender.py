from utils.exercise_loader import load_exercises


def normalize_text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(x).strip().lower() for x in value)
    return str(value).strip().lower()


def map_focus_area_to_keywords(focus_area: str):
    mapping = {
        "upper_body": [
            "upper arms", "upper arm", "biceps", "triceps",
            "chest", "back", "lats", "shoulders", "delts", "forearms"
        ],
        "lower_body": [
            "upper legs", "upper leg", "lower legs", "lower leg",
            "glutes", "hamstrings", "quadriceps", "quads", "calves"
        ],
        "core": [
            "waist", "abs", "abdominals", "core", "obliques", "lower back"
        ],
        "full_body": []
    }
    return mapping.get(focus_area, [])


def equipment_matches(exercise_equipment: str, selected_equipment: str) -> bool:
    eq = normalize_text(exercise_equipment)

    if selected_equipment == "gym":
        return True

    if selected_equipment == "home":
        blocked = [
            "barbell", "smith", "cable", "machine",
            "leverage machine", "trap bar", "sled", "elliptical"
        ]
        return not any(word in eq for word in blocked)

    if selected_equipment == "no_equipment":
        allowed = ["body weight", "bodyweight", "none"]
        return any(word in eq for word in allowed) or eq == ""

    return True


def extract_name(ex):
    return ex.get("name") or "Unknown Exercise"


def extract_body_part(ex):
    return (
        ex.get("bodyPart")
        or ex.get("body_part")
        or ex.get("category")
        or ""
    )


def extract_target(ex):
    return ex.get("target") or ""


def extract_secondary(ex):
    return ex.get("secondaryMuscles") or ex.get("secondary_muscles") or ex.get("secondary_muscles") or []


def extract_equipment(ex):
    return ex.get("equipment") or ""


def extract_instructions(ex):
    steps = ex.get("instruction_steps", {})
    if isinstance(steps, dict):
        en_steps = steps.get("en", [])
        if isinstance(en_steps, list) and en_steps:
            return en_steps

    instructions = ex.get("instructions", {})
    if isinstance(instructions, dict):
        en_text = instructions.get("en", "")
        if en_text:
            return [en_text]

    raw = ex.get("instructions") or []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return [raw]

    return []


def exercise_score(ex, focus_area, equipment, experience_level, intensity, goal):
    score = 0

    body_part = normalize_text(extract_body_part(ex))
    target = normalize_text(extract_target(ex))
    secondary = normalize_text(extract_secondary(ex))
    exercise_equipment = extract_equipment(ex)
    name = normalize_text(extract_name(ex))

    keywords = map_focus_area_to_keywords(focus_area)

    if focus_area == "full_body":
        score += 2
    else:
        if any(k in body_part for k in keywords):
            score += 5
        if any(k in target for k in keywords):
            score += 5
        if any(k in secondary for k in keywords):
            score += 2

    if equipment_matches(exercise_equipment, equipment):
        score += 4
    else:
        score -= 100

    if goal == "muscle_gain":
        if any(word in name for word in ["press", "curl", "row", "deadlift", "squat", "pulldown", "extension"]):
            score += 2

    if goal == "weight_loss":
        if any(word in name for word in ["burpee", "jump", "climber", "step", "cardio"]):
            score += 2

    if goal == "endurance":
        if any(word in name for word in ["cardio", "jump", "march", "step"]):
            score += 2

    if goal == "general_fitness":
        score += 1

    if experience_level == "beginner":
        if any(word in name for word in ["machine", "basic", "wall", "assisted"]):
            score += 2
        if any(word in name for word in ["explosive", "archer", "advanced"]):
            score -= 2

    if experience_level == "advanced":
        if any(word in name for word in ["barbell", "deadlift", "explosive", "archer", "weighted"]):
            score += 2

    if intensity == "low":
        if any(word in name for word in ["stretch", "mobility", "walk", "bird dog", "dead bug", "plank"]):
            score += 2
        if any(word in name for word in ["burpee", "jump", "explosive"]):
            score -= 2

    if intensity == "high":
        if any(word in name for word in ["burpee", "jump", "deadlift", "squat", "press", "climber"]):
            score += 2

    return score


def choose_count_by_intensity(intensity: str):
    if intensity == "low":
        return 3
    if intensity == "moderate":
        return 4
    return 5


def recommend_exercises(
    focus_area: str,
    equipment: str,
    experience_level: str,
    intensity: str,
    goal: str
):
    exercises = load_exercises()

    scored = []
    for ex in exercises:
        score = exercise_score(
            ex=ex,
            focus_area=focus_area,
            equipment=equipment,
            experience_level=experience_level,
            intensity=intensity,
            goal=goal
        )
        if score > -50:
            scored.append((score, ex))

    scored.sort(key=lambda x: x[0], reverse=True)

    top_n = choose_count_by_intensity(intensity)
    selected = []
    seen_names = set()

    for _, ex in scored:
        name = extract_name(ex)
        if name.lower() in seen_names:
            continue

        selected.append({
            "id": ex.get("id", ""),
            "name": name,
            "body_part": extract_body_part(ex),
            "target": extract_target(ex),
            "equipment": extract_equipment(ex),
            "secondary_muscles": extract_secondary(ex),
            "instructions": extract_instructions(ex)[:3],
            "image_url": ex.get("image_url", ""),
            "gif_media_url": ex.get("gif_media_url", ""),
        })
        seen_names.add(name.lower())

        if len(selected) >= top_n:
            break

    return selected