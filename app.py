from typing import Optional, List
from datetime import datetime

from bson import ObjectId
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from utils.predictor import predict_intensity
from utils.recommender import generate_recommendation
from utils.exercise_recommender import recommend_exercises
from utils.exercise_loader import (
    load_exercises,
    find_exercise_by_id,
    get_exercise_id,
    get_exercise_name,
    get_body_part,
    get_target,
    get_equipment,
    get_secondary_muscles,
    get_instructions,
    unique_sorted_values,
)
from utils.history_adapter import summarize_user_history, adapt_recommendation_with_history
from utils.auth import hash_password, verify_password
from database.mongo import (
    users_collection,
    workout_logs_collection,
    saved_recommendations_collection,
    feedback_collection,
    favorites_collection,
    weekly_plans_collection,
)

app = FastAPI(title="Intelligent Trainer")
app.add_middleware(SessionMiddleware, secret_key="change_this_secret_key_for_production")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# =========================
# General helper functions
# =========================


def encode_gender(gender: str) -> int:
    return 1 if gender.lower() == "male" else 0


def encode_experience(level: str) -> int:
    mapping = {
        "beginner": 1,
        "intermediate": 2,
        "advanced": 3,
    }
    return mapping.get(level.lower(), 1)


def parse_optional_float(value: Optional[str], default: float) -> float:
    if value is None:
        return default
    value = value.strip().lower()
    if value in ["", "unknown", "none", "null", "i_dont_know"]:
        return default
    return float(value)


def stringify_mongo_doc(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


# =========================
# Authentication helpers
# =========================


def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    try:
        return users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def get_current_user_id(request: Request) -> Optional[str]:
    user = get_current_user(request)
    if not user:
        return None
    return str(user["_id"])


def is_profile_complete(user: dict) -> bool:
    return bool(user and user.get("profile_completed"))


def redirect_if_not_logged_in(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return None


def redirect_if_profile_not_completed(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if not is_profile_complete(user):
        return RedirectResponse(url="/profile/setup", status_code=303)

    return None


def get_favorite_ids(user_id: str):
    docs = favorites_collection.find({"user_id": user_id}, {"exercise_id": 1})
    return {str(item.get("exercise_id")) for item in docs}


# =========================
# Weekly plan helpers
# =========================


def build_weekly_grouped_plan(plans):
    week_days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    grouped = {day: [] for day in week_days}

    for item in plans:
        day = item.get("day_of_week", "")
        if day in grouped:
            grouped[day].append(item)

    return grouped


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "current_user": get_current_user(request),
        },
    )


# =========================
# Authentication routes
# =========================


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request,
            "error": None,
            "current_user": None,
        },
    )


@app.post("/signup", response_class=HTMLResponse)
def signup(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if get_current_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)

    cleaned_email = email.lower().strip()

    existing_user = users_collection.find_one({"email": cleaned_email})
    if existing_user:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": "An account with this email already exists.",
                "current_user": None,
            },
        )

    user_doc = {
        "full_name": full_name.strip(),
        "email": cleaned_email,
        "password_hash": hash_password(password),
        "profile_completed": False,
        "age": None,
        "gender": "",
        "height_cm": None,
        "weight_kg": None,
        "experience_level": "",
        "main_goal": "",
        "focus_area": "",
        "preferred_equipment": "",
        "workout_frequency_days_week": None,
        "created_at": datetime.utcnow(),
    }

    inserted = users_collection.insert_one(user_doc)
    request.session["user_id"] = str(inserted.inserted_id)

    return RedirectResponse(url="/profile/setup", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": None,
            "current_user": None,
        },
    )


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    if get_current_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)

    cleaned_email = email.lower().strip()
    user = users_collection.find_one({"email": cleaned_email})

    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid email or password.",
                "current_user": None,
            },
        )

    request.session["user_id"] = str(user["_id"])

    if not is_profile_complete(user):
        return RedirectResponse(url="/profile/setup", status_code=303)

    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# =========================
# Profile routes
# =========================


@app.get("/profile/setup", response_class=HTMLResponse)
def profile_setup_page(request: Request):
    auth_redirect = redirect_if_not_logged_in(request)
    if auth_redirect:
        return auth_redirect

    current_user = get_current_user(request)

    return templates.TemplateResponse(
        "profile_setup.html",
        {
            "request": request,
            "current_user": current_user,
            "is_edit": False,
        },
    )


@app.post("/profile/setup")
def profile_setup_save(
    request: Request,
    age: int = Form(...),
    gender: str = Form(...),
    height_cm: float = Form(...),
    weight_kg: float = Form(...),
    experience_level: str = Form(...),
    main_goal: str = Form(...),
    focus_area: str = Form(...),
    preferred_equipment: str = Form(...),
    workout_frequency_days_week: int = Form(...),
):
    auth_redirect = redirect_if_not_logged_in(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "age": age,
                "gender": gender,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "experience_level": experience_level,
                "main_goal": main_goal,
                "focus_area": focus_area,
                "preferred_equipment": preferred_equipment,
                "workout_frequency_days_week": workout_frequency_days_week,
                "profile_completed": True,
            }
        },
    )

    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    auth_redirect = redirect_if_not_logged_in(request)
    if auth_redirect:
        return auth_redirect

    current_user = get_current_user(request)

    return templates.TemplateResponse(
        "profile_setup.html",
        {
            "request": request,
            "current_user": current_user,
            "is_edit": True,
        },
    )


@app.post("/profile")
def profile_update(
    request: Request,
    age: int = Form(...),
    gender: str = Form(...),
    height_cm: float = Form(...),
    weight_kg: float = Form(...),
    experience_level: str = Form(...),
    main_goal: str = Form(...),
    focus_area: str = Form(...),
    preferred_equipment: str = Form(...),
    workout_frequency_days_week: int = Form(...),
):
    auth_redirect = redirect_if_not_logged_in(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "age": age,
                "gender": gender,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "experience_level": experience_level,
                "main_goal": main_goal,
                "focus_area": focus_area,
                "preferred_equipment": preferred_equipment,
                "workout_frequency_days_week": workout_frequency_days_week,
                "profile_completed": True,
            }
        },
    )

    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/form", response_class=HTMLResponse)
def form_page(request: Request):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    current_user = get_current_user(request)

    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "current_user": current_user,
        },
    )


@app.get("/about", response_class=HTMLResponse)
def about_page(request: Request):
    return templates.TemplateResponse(
        "about.html",
        {
            "request": request,
            "current_user": get_current_user(request),
        },
    )


@app.get("/library", response_class=HTMLResponse)
def library_page(
    request: Request,
    search: str = Query(default=""),
    body_part: str = Query(default=""),
    equipment: str = Query(default=""),
    target: str = Query(default=""),
    secondary_muscle: str = Query(default=""),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)
    exercises = load_exercises()

    body_parts = unique_sorted_values(get_body_part(ex) for ex in exercises)
    equipments = unique_sorted_values(get_equipment(ex) for ex in exercises)
    targets = unique_sorted_values(get_target(ex) for ex in exercises)

    all_secondary = []
    for ex in exercises:
        sec = get_secondary_muscles(ex)
        if isinstance(sec, list):
            all_secondary.extend(sec)
    secondary_muscles = unique_sorted_values(all_secondary)

    favorite_ids = get_favorite_ids(user_id)

    filtered = []
    search_lower = search.strip().lower()

    for ex in exercises:
        name = get_exercise_name(ex)
        ex_body_part = get_body_part(ex)
        ex_equipment = get_equipment(ex)
        ex_target = get_target(ex)
        ex_secondary = get_secondary_muscles(ex)
        ex_secondary_text = (
            " ".join(ex_secondary).lower()
            if isinstance(ex_secondary, list)
            else str(ex_secondary).lower()
        )

        if search_lower:
            haystack = " ".join(
                [
                    name,
                    ex_body_part,
                    ex_equipment,
                    ex_target,
                    ex_secondary_text,
                ]
            ).lower()
            if search_lower not in haystack:
                continue

        if body_part and ex_body_part.lower() != body_part.lower():
            continue

        if equipment and ex_equipment.lower() != equipment.lower():
            continue

        if target and ex_target.lower() != target.lower():
            continue

        if secondary_muscle and secondary_muscle.lower() not in ex_secondary_text:
            continue

        exercise_id = get_exercise_id(ex)

        filtered.append(
            {
                "id": exercise_id,
                "name": name,
                "body_part": ex_body_part,
                "equipment": ex_equipment,
                "target": ex_target,
                "secondary_muscles": ex_secondary,
                "instructions": get_instructions(ex)[:2],
                "image_url": ex.get("image_url", ""),
                "gif_media_url": ex.get("gif_media_url", ""),
                "is_favorite": exercise_id in favorite_ids,
            }
        )

    return templates.TemplateResponse(
        "library.html",
        {
            "request": request,
            "current_user": get_current_user(request),
            "exercises": filtered[:120],
            "search": search,
            "selected_body_part": body_part,
            "selected_equipment": equipment,
            "selected_target": target,
            "selected_secondary_muscle": secondary_muscle,
            "body_parts": body_parts,
            "equipments": equipments,
            "targets": targets,
            "secondary_muscles": secondary_muscles,
            "results_count": len(filtered),
        },
    )


@app.get("/exercise/{exercise_id}", response_class=HTMLResponse)
def exercise_detail_page(request: Request, exercise_id: str):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)
    exercise = find_exercise_by_id(exercise_id)

    if not exercise:
        return templates.TemplateResponse(
            "exercise_detail.html",
            {
                "request": request,
                "exercise": None,
                "is_favorite": False,
                "current_user": get_current_user(request),
            },
            status_code=404,
        )

    is_favorite = (
        favorites_collection.find_one(
            {
                "user_id": user_id,
                "exercise_id": exercise_id,
            }
        )
        is not None
    )

    detail = {
        "id": get_exercise_id(exercise),
        "name": get_exercise_name(exercise),
        "body_part": get_body_part(exercise),
        "equipment": get_equipment(exercise),
        "target": get_target(exercise),
        "secondary_muscles": get_secondary_muscles(exercise),
        "instructions": get_instructions(exercise),
        "image_url": exercise.get("image_url", ""),
        "gif_media_url": exercise.get("gif_media_url", ""),
    }

    return templates.TemplateResponse(
        "exercise_detail.html",
        {
            "request": request,
            "exercise": detail,
            "is_favorite": is_favorite,
            "current_user": get_current_user(request),
        },
    )


@app.post("/favorites/add")
def add_favorite(
    request: Request,
    exercise_id: str = Form(...),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)

    exists = favorites_collection.find_one(
        {
            "user_id": user_id,
            "exercise_id": exercise_id,
        }
    )

    if not exists:
        exercise = find_exercise_by_id(exercise_id)
        if exercise:
            favorites_collection.insert_one(
                {
                    "user_id": user_id,
                    "exercise_id": exercise_id,
                    "exercise_name": get_exercise_name(exercise),
                    "body_part": get_body_part(exercise),
                    "target": get_target(exercise),
                    "equipment": get_equipment(exercise),
                    "created_at": datetime.utcnow(),
                }
            )

    return RedirectResponse(url=f"/exercise/{exercise_id}", status_code=303)


@app.post("/favorites/remove")
def remove_favorite(
    request: Request,
    exercise_id: str = Form(...),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)

    favorites_collection.delete_one(
        {
            "user_id": user_id,
            "exercise_id": exercise_id,
        }
    )
    return RedirectResponse(url=f"/exercise/{exercise_id}", status_code=303)


# =========================
# Weekly plan routes
# =========================


@app.get("/weekly-plan", response_class=HTMLResponse)
def weekly_plan_page(request: Request):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)

    plans = list(
        weekly_plans_collection.find({"user_id": user_id}).sort("created_at", -1)
    )
    plans = [stringify_mongo_doc(doc) for doc in plans]
    grouped_plans = build_weekly_grouped_plan(plans)

    favorites = list(
        favorites_collection.find({"user_id": user_id}).sort("created_at", -1)
    )
    favorites = [stringify_mongo_doc(doc) for doc in favorites]

    return templates.TemplateResponse(
        "weekly_plan.html",
        {
            "request": request,
            "plans": plans,
            "grouped_plans": grouped_plans,
            "favorites": favorites,
            "current_user": get_current_user(request),
        },
    )


@app.post("/weekly-plan/add")
def add_to_weekly_plan(
    request: Request,
    exercise_id: str = Form(...),
    day_of_week: str = Form(...),
    planned_sets: Optional[str] = Form(None),
    planned_reps: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)
    exercise = find_exercise_by_id(exercise_id)

    if exercise:
        weekly_plans_collection.insert_one(
    {
        "user_id": user_id,
        "exercise_id": exercise_id,
        "exercise_name": get_exercise_name(exercise),
        "body_part": get_body_part(exercise),
        "target": get_target(exercise),
        "equipment": get_equipment(exercise),
        "day_of_week": day_of_week,
        "planned_sets": planned_sets or "",
        "planned_reps": planned_reps or "",
        "notes": notes or "",
        "status": "planned",
        "planned_workout_type": "",
        "planned_duration": "",
        "planned_intensity": "",
        "planned_exercises": [],
        "created_at": datetime.utcnow(),
    }
)

    return RedirectResponse(url="/weekly-plan", status_code=303)


@app.post("/weekly-plan/add-recommendation")
def add_recommendation_to_weekly_plan(
    request: Request,
    recommendation_id: str = Form(...),
    day_of_week: str = Form(...),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)

    recommendation = saved_recommendations_collection.find_one(
        {
            "_id": ObjectId(recommendation_id),
            "user_id": user_id,
        }
    )

    if recommendation:
        weekly_plans_collection.insert_one(
            {
                "user_id": user_id,
                "recommendation_id": str(recommendation["_id"]),
                "exercise_id": "",
                "exercise_name": recommendation.get("workout_type", "Workout Plan"),
                "body_part": recommendation.get("focus_area", ""),
                "target": recommendation.get("goal", ""),
                "equipment": recommendation.get("equipment", ""),
                "day_of_week": day_of_week,
                "planned_sets": "",
                "planned_reps": "",
                "notes": "",
                "status": "planned",
                "planned_workout_type": recommendation.get("workout_type", ""),
                "planned_duration": recommendation.get("duration", ""),
                "planned_intensity": recommendation.get("predicted_intensity", ""),
                "planned_exercises": recommendation.get("recommended_exercises", []),
                "created_at": datetime.utcnow(),
            }
        )

    return RedirectResponse(url="/weekly-plan", status_code=303)

@app.post("/weekly-plan/delete")
def delete_from_weekly_plan(
    request: Request,
    plan_id: str = Form(...),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)

    weekly_plans_collection.delete_one(
        {
            "_id": ObjectId(plan_id),
            "user_id": user_id,
        }
    )
    return RedirectResponse(url="/weekly-plan", status_code=303)


@app.get("/log", response_class=HTMLResponse)
def log_page(
    request: Request,
    weekly_plan_id: Optional[str] = None,
    recommendation_id: Optional[str] = None,
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)
    recommendation = None
    weekly_plan = None

    if weekly_plan_id:
        weekly_plan = weekly_plans_collection.find_one(
            {
                "_id": ObjectId(weekly_plan_id),
                "user_id": user_id,
            }
        )
        if weekly_plan:
            weekly_plan = stringify_mongo_doc(weekly_plan)

            rec_id = weekly_plan.get("recommendation_id")
            if rec_id:
                recommendation = saved_recommendations_collection.find_one(
                    {
                        "_id": ObjectId(rec_id),
                        "user_id": user_id,
                    }
                )
                if recommendation:
                    recommendation = stringify_mongo_doc(recommendation)

    elif recommendation_id:
        recommendation = saved_recommendations_collection.find_one(
            {
                "_id": ObjectId(recommendation_id),
                "user_id": user_id,
            }
        )
        if recommendation:
            recommendation = stringify_mongo_doc(recommendation)

    return templates.TemplateResponse(
        "log.html",
        {
            "request": request,
            "recommendation": recommendation,
            "weekly_plan": weekly_plan,
            "current_user": get_current_user(request),
        },
    )

@app.post("/log/save", response_class=HTMLResponse)
def save_log(
    request: Request,
    recommendation_id: Optional[str] = Form(None),
    weekly_plan_id: Optional[str] = Form(None),
    workout_date: str = Form(...),
    completed: str = Form(...),
    difficulty: str = Form(...),
    fatigue_after_workout: str = Form(...),
    notes: Optional[str] = Form(None),
    user_rating: Optional[int] = Form(None),
    completed_exercises: List[str] = Form([]),
    manual_completed_exercises: Optional[str] = Form(None),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)
    recommendation = None
    weekly_plan = None
    planned_workout_type = ""
    planned_duration = ""
    planned_intensity = ""
    planned_exercises = []

    if weekly_plan_id:
        weekly_plan = weekly_plans_collection.find_one(
            {
                "_id": ObjectId(weekly_plan_id),
                "user_id": user_id,
            }
        )

    if weekly_plan:
        recommendation_id = weekly_plan.get("recommendation_id")
        planned_workout_type = weekly_plan.get("planned_workout_type", "")
        planned_duration = weekly_plan.get("planned_duration", "")
        planned_intensity = weekly_plan.get("planned_intensity", "")
        planned_exercises = weekly_plan.get("planned_exercises", [])

    if recommendation_id:
        recommendation = saved_recommendations_collection.find_one(
            {
                "_id": ObjectId(recommendation_id),
                "user_id": user_id,
            }
        )

    if recommendation and not planned_workout_type:
        planned_workout_type = recommendation.get("workout_type", "")
        planned_duration = recommendation.get("duration", "")
        planned_intensity = recommendation.get("predicted_intensity", "")
        planned_exercises = recommendation.get("recommended_exercises", [])

    selected_exercises = [item.strip() for item in completed_exercises if item.strip()]

    if manual_completed_exercises:
        manual_items = [
        item.strip()
        for item in manual_completed_exercises.split("|||")
        if item.strip()
    ]
    selected_exercises.extend(manual_items)

    log_doc = {
        "user_id": user_id,
        "recommendation_id": recommendation_id,
        "weekly_plan_id": weekly_plan_id,
        "workout_date": workout_date,
        "completed": completed,
        "planned_workout_type": planned_workout_type,
        "planned_duration": planned_duration,
        "planned_intensity": planned_intensity,
        "planned_exercises": planned_exercises,
        "completed_exercises": selected_exercises,
        "difficulty": difficulty,
        "fatigue_after_workout": fatigue_after_workout,
        "notes": notes or "",
        "user_rating": user_rating,
        "created_at": datetime.utcnow(),
    }

    inserted_log = workout_logs_collection.insert_one(log_doc)

    if weekly_plan_id:
        new_status = "completed" if completed == "yes" else "partial" if completed == "partially" else "skipped"

        weekly_plans_collection.update_one(
            {
                "_id": ObjectId(weekly_plan_id),
                "user_id": user_id,
            },
            {
                "$set": {
                    "status": new_status,
                    "last_logged_at": datetime.utcnow(),
                }
            },
        )

    if user_rating is not None:
        feedback_collection.insert_one(
            {
                "user_id": user_id,
                "recommendation_id": recommendation_id,
                "weekly_plan_id": weekly_plan_id,
                "workout_log_id": str(inserted_log.inserted_id),
                "user_rating": user_rating,
                "fatigue_after_workout": fatigue_after_workout,
                "notes": notes or "",
                "created_at": datetime.utcnow(),
            }
        )

    return RedirectResponse(url="/dashboard", status_code=303)
# =========================
# Dashboard route
# =========================


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)
    current_user = get_current_user(request)

    recent_logs_cursor = workout_logs_collection.find({"user_id": user_id}).sort(
        "created_at", -1
    ).limit(10)
    recent_logs = [stringify_mongo_doc(doc) for doc in recent_logs_cursor]

    all_logs = list(
        workout_logs_collection.find({"user_id": user_id}).sort("created_at", -1)
    )

    total_logs = len(all_logs)
    completed_logs = sum(1 for item in all_logs if item.get("completed") == "yes")
    partial_logs = sum(1 for item in all_logs if item.get("completed") == "partially")
    missed_logs = sum(1 for item in all_logs if item.get("completed") == "no")

    easy_logs = sum(1 for item in all_logs if item.get("difficulty") == "easy")
    moderate_logs = sum(1 for item in all_logs if item.get("difficulty") == "moderate")
    hard_logs = sum(1 for item in all_logs if item.get("difficulty") == "hard")

    low_fatigue = sum(1 for item in all_logs if item.get("fatigue_after_workout") == "low")
    moderate_fatigue = sum(
        1 for item in all_logs if item.get("fatigue_after_workout") == "moderate"
    )
    high_fatigue = sum(1 for item in all_logs if item.get("fatigue_after_workout") == "high")

    ratings = [item.get("user_rating") for item in all_logs if isinstance(item.get("user_rating"), int)]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

    duration_values = []
    for item in all_logs:
        raw = str(item.get("planned_duration", "")).strip()
        if "-" in raw:
            try:
                left = int(raw.split("-")[0].strip())
                duration_values.append(left)
            except Exception:
                pass

    avg_duration = round(sum(duration_values) / len(duration_values), 1) if duration_values else 0

    workout_type_counts = {}
    for item in all_logs:
        workout_type = item.get("planned_workout_type", "")
        if workout_type:
            workout_type_counts[workout_type] = workout_type_counts.get(workout_type, 0) + 1

    most_common_workout_type = (
        max(workout_type_counts, key=workout_type_counts.get) if workout_type_counts else ""
    )

    intensity_counts = {
        "low": saved_recommendations_collection.count_documents(
            {"user_id": user_id, "predicted_intensity": "Low"}
        ),
        "moderate": saved_recommendations_collection.count_documents(
            {"user_id": user_id, "predicted_intensity": "Moderate"}
        ),
        "high": saved_recommendations_collection.count_documents(
            {"user_id": user_id, "predicted_intensity": "High"}
        ),
    }

    history_summary = summarize_user_history(all_logs[:5])

    favorites_count = favorites_collection.count_documents({"user_id": user_id})
    weekly_plan_count = weekly_plans_collection.count_documents({"user_id": user_id})

    planned_workouts_cursor = weekly_plans_collection.find(
        {
            "user_id": user_id,
            "status": "planned",
        }
    ).sort("created_at", -1).limit(6)

    planned_workouts = [stringify_mongo_doc(doc) for doc in planned_workouts_cursor]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "recent_logs": recent_logs,
            "total_logs": total_logs,
            "completed_logs": completed_logs,
            "partial_logs": partial_logs,
            "missed_logs": missed_logs,
            "easy_logs": easy_logs,
            "moderate_logs": moderate_logs,
            "hard_logs": hard_logs,
            "low_fatigue": low_fatigue,
            "moderate_fatigue": moderate_fatigue,
            "high_fatigue": high_fatigue,
            "avg_rating": avg_rating,
            "avg_duration": avg_duration,
            "most_common_workout_type": most_common_workout_type,
            "intensity_counts": intensity_counts,
            "history_note": history_summary["history_note"],
            "favorites_count": favorites_count,
            "weekly_plan_count": weekly_plan_count,
            "planned_workouts": planned_workouts,
        },
    )

@app.post("/predict", response_class=HTMLResponse)
def predict(
    request: Request,
    avg_bpm: str = Form(...),
    session_duration_hours: float = Form(...),
    max_bpm: Optional[str] = Form(None),
    resting_bpm: Optional[str] = Form(None),
    fat_percentage: Optional[str] = Form(None),
    water_intake_liters: Optional[str] = Form(None),
):
    auth_redirect = redirect_if_profile_not_completed(request)
    if auth_redirect:
        return auth_redirect

    user_id = get_current_user_id(request)
    current_user = get_current_user(request)

    age = int(current_user["age"])
    gender = current_user["gender"]
    weight_kg = float(current_user["weight_kg"])
    height_cm = float(current_user["height_cm"])
    experience_level = current_user["experience_level"]
    goal = current_user["main_goal"]
    focus_area = current_user["focus_area"]
    equipment = current_user["preferred_equipment"]
    workout_frequency_days_week = int(current_user["workout_frequency_days_week"])

    height_m = height_cm / 100

    max_bpm_value = parse_optional_float(max_bpm, 220 - age)
    avg_bpm_value = parse_optional_float(avg_bpm, 130.0)
    resting_bpm_value = parse_optional_float(resting_bpm, 70.0)
    fat_percentage_value = parse_optional_float(fat_percentage, 25.0)
    water_intake_value = parse_optional_float(water_intake_liters, 2.0)

    bmi = weight_kg / (height_m ** 2)
    avg_hr_reserve = avg_bpm_value - resting_bpm_value
    calories_burned_value = session_duration_hours * avg_bpm_value * 2.2

    input_data = {
        "age": age,
        "gender_encoded": encode_gender(gender),
        "weight_kg": weight_kg,
        "height_m": height_m,
        "max_bpm": max_bpm_value,
        "avg_bpm": avg_bpm_value,
        "resting_bpm": resting_bpm_value,
        "session_duration_hours": session_duration_hours,
        "calories_burned": calories_burned_value,
        "fat_percentage": fat_percentage_value,
        "water_intake_liters": water_intake_value,
        "workout_frequency_days_week": workout_frequency_days_week,
        "experience_level_encoded": encode_experience(experience_level),
        "bmi": bmi,
        "avg_hr_reserve": avg_hr_reserve,
    }

    model_intensity = predict_intensity(input_data)

    recommendation = generate_recommendation(
        model_intensity=model_intensity,
        goal=goal,
        focus_area=focus_area,
        equipment=equipment,
        experience_level=experience_level,
        bmi=bmi,
        water_intake_liters=water_intake_value,
        workout_frequency_days_week=workout_frequency_days_week,
        session_duration_hours=session_duration_hours,
        avg_bpm=avg_bpm_value,
        resting_bpm=resting_bpm_value,
        max_bpm=max_bpm_value,
    )

    recent_logs = list(
        workout_logs_collection.find({"user_id": user_id}).sort("created_at", -1).limit(5)
    )
    history_summary = summarize_user_history(recent_logs)
    recommendation = adapt_recommendation_with_history(recommendation, history_summary)

    history_adjustments = recommendation.get("history_adjustments", [])

    recommendation["explanation_blocks"] = {
        "profile_based": [
            f"Profile goal: {goal.replace('_', ' ').title()}",
            f"Experience level: {experience_level.title()}",
            f"Preferred focus area: {focus_area.replace('_', ' ').title()}",
            f"Preferred equipment: {equipment.replace('_', ' ').title()}",
            f"Target frequency: {workout_frequency_days_week} workout(s) per week",
        ],
        "current_condition": [
            f"Average BPM input: {round(avg_bpm_value, 1)}",
            f"Session duration input: {session_duration_hours} hour(s)",
            f"Water intake: {round(water_intake_value, 1)} L",
            f"Resting BPM: {round(resting_bpm_value, 1)}",
            f"Calculated BMI: {round(bmi, 1)}",
            f"Predicted model intensity: {model_intensity.title()}",
        ],
        "history_based": history_adjustments if history_adjustments else [
            "No major workout-history adjustment was applied yet."
        ],
    }

    recommended_exercises = recommend_exercises(
    focus_area=focus_area,
    equipment=equipment,
    experience_level=experience_level,
    intensity=recommendation["predicted_intensity"].lower(),
    goal=goal,
)

    recommendation["recommended_exercises"] = recommended_exercises
    recommendation["bmi"] = round(bmi, 1)
    recommendation["goal"] = goal.replace("_", " ").title()
    recommendation["focus_area"] = focus_area.replace("_", " ").title()
    recommendation["equipment"] = equipment.replace("_", " ").title()
    recommendation["experience_level"] = experience_level.title()

    recommendation["input_summary"] = {
        "age": age,
        "gender": gender.title(),
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "avg_bpm": avg_bpm_value,
        "max_bpm": max_bpm_value,
        "resting_bpm": resting_bpm_value,
        "session_duration_hours": session_duration_hours,
        "fat_percentage": fat_percentage_value,
        "water_intake_liters": water_intake_value,
        "workout_frequency_days_week": workout_frequency_days_week,
        "model_intensity": model_intensity.title(),
    }

    recommendation_doc = {
        "user_id": user_id,
        "goal": recommendation["goal"],
        "focus_area": recommendation["focus_area"],
        "equipment": recommendation["equipment"],
        "experience_level": recommendation["experience_level"],
        "predicted_intensity": recommendation["predicted_intensity"],
        "workout_type": recommendation["workout_type"],
        "duration": recommendation["duration"],
        "style": recommendation["style"],
        "recovery_advice": recommendation["recovery_advice"],
        "explanation": recommendation["explanation"],
        "history_note": recommendation.get("history_note", ""),
        "history_adjustments": recommendation.get("history_adjustments", []),
        "personal_insights": recommendation["personal_insights"],
        "recommended_exercises": recommendation["recommended_exercises"],
        "input_summary": recommendation["input_summary"],
        "created_at": datetime.utcnow(),
    }

    saved_result = saved_recommendations_collection.insert_one(recommendation_doc)
    recommendation["recommendation_id"] = str(saved_result.inserted_id)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "result": recommendation,
            "current_user": get_current_user(request),
        },
    )