import json
from pathlib import Path


DATA_PATH = Path("data/exercises.json")
STATIC_MEDIA_PREFIX = "/static/exercise_media/"


def build_media_url(relative_path: str) -> str:
    if not relative_path:
        return ""

    relative_path = str(relative_path).strip().replace("\\", "/")

    if relative_path.startswith("http://") or relative_path.startswith("https://"):
        return relative_path

    return f"{STATIC_MEDIA_PREFIX}{relative_path}"


def normalize_exercise_record(exercise: dict) -> dict:
    exercise = dict(exercise)

    exercise["image_url"] = build_media_url(exercise.get("image", ""))
    exercise["gif_media_url"] = build_media_url(exercise.get("gif_url", ""))

    return exercise


def load_exercises():
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Exercise dataset not found: {DATA_PATH}. "
            "Make sure exercises.json is inside the data folder."
        )

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        if "exercises" in data and isinstance(data["exercises"], list):
            return [normalize_exercise_record(item) for item in data["exercises"]]
        if "data" in data and isinstance(data["data"], list):
            return [normalize_exercise_record(item) for item in data["data"]]

    if isinstance(data, list):
        return [normalize_exercise_record(item) for item in data]

    raise ValueError("Unsupported exercises.json structure.")


def get_exercise_id(exercise: dict) -> str:
    return str(exercise.get("id", "")).strip()


def get_exercise_name(exercise: dict) -> str:
    return exercise.get("name") or "Unknown Exercise"


def get_body_part(exercise: dict) -> str:
    return (
        exercise.get("bodyPart")
        or exercise.get("body_part")
        or exercise.get("category")
        or ""
    )


def get_target(exercise: dict) -> str:
    return exercise.get("target") or ""


def get_equipment(exercise: dict) -> str:
    return exercise.get("equipment") or ""


def get_secondary_muscles(exercise: dict):
    return exercise.get("secondaryMuscles") or exercise.get("secondary_muscles") or []


def get_instructions(exercise: dict):
    steps = exercise.get("instruction_steps", {})
    if isinstance(steps, dict):
        en_steps = steps.get("en", [])
        if isinstance(en_steps, list) and en_steps:
            return en_steps

    instructions = exercise.get("instructions", {})
    if isinstance(instructions, dict):
        en_text = instructions.get("en", "")
        if en_text:
            return [en_text]

    raw = exercise.get("instructions") or []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return [raw]

    return []


def find_exercise_by_id(exercise_id: str):
    exercises = load_exercises()
    for exercise in exercises:
        if get_exercise_id(exercise) == str(exercise_id):
            return exercise
    return None


def unique_sorted_values(items):
    values = []
    seen = set()

    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            values.append(value)

    return sorted(values, key=lambda x: x.lower())