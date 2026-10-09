import re
from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt

CATEGORIES = ["Roads", "Sanitation", "Streetlights", "Water & Drainage", "Public Infrastructure", "Other"]
DEPARTMENTS = {"Roads": "Roads Department", "Sanitation": "Sanitation Department", "Streetlights": "Electrical Department", "Water & Drainage": "Water Department", "Public Infrastructure": "Public Works Department", "Other": "Municipal Services"}


def analyze(title: str, description: str, category: str | None = None) -> dict:
    """Transparent rule-based advisory fallback; no external provider required."""
    text = f"{title} {description}".lower()
    rules = [("Sanitation", ("garbage", "trash", "waste", "sewage", "dirty")),
             ("Streetlights", ("streetlight", "street light", "lamp", "dark")),
             ("Water & Drainage", ("water", "leak", "drain", "flood", "pipe")),
             ("Roads", ("pothole", "road", "pavement", "asphalt")),
             ("Public Infrastructure", ("park", "bench", "building", "footpath"))]
    selected = category if category in CATEGORIES else next((c for c, words in rules if any(w in text for w in words)), "Other")
    priority = "high" if re.search(r"(danger|urgent|blocked|injur|exposed wire|flood)", text) else "medium"
    summary = (description.strip().split("\n")[0])[:180]
    return {"category": selected, "department": DEPARTMENTS[selected], "priority": priority,
            "summary": summary, "advisory": True, "provider": "rule-based fallback"}


def _distance_km(lat1, lon1, lat2, lon2):
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))


def find_duplicates(title, description, category, latitude, longitude, candidates):
    """Rank possible related reports; never treat a match as a reason to reject."""
    text = f"{title} {description}".lower()
    matches = []
    for item in candidates:
        other = f"{item.title} {item.description}".lower()
        text_score = SequenceMatcher(None, text, other).ratio()
        category_score = 1.0 if category == item.category else 0.0
        distance = None
        location_score = 0.0
        if latitude is not None and longitude is not None and item.latitude is not None and item.longitude is not None:
            distance = _distance_km(latitude, longitude, item.latitude, item.longitude)
            location_score = max(0.0, 1 - distance / 2) if distance <= 2 else 0.0
        score = (0.65 * text_score + 0.2 * category_score + 0.15 * location_score) if distance is not None else (0.8 * text_score + 0.2 * category_score)
        if score >= 0.42:
            matches.append({"reference": item.reference, "category": item.category, "status": item.status,
                            "similarity": round(score, 2), "distance_km": round(distance, 2) if distance is not None else None,
                            "human_review_required": True})
    return sorted(matches, key=lambda x: x["similarity"], reverse=True)[:5]


def guidance(question):
    """Answer only from verified portal workflow details; avoid promises or policy claims."""
    text = question.lower()
    if any(word in text for word in ("track", "status", "reference")):
        answer = "Sign in and open My complaints. Select a report to view its reference number and status timeline."
    elif any(word in text for word in ("photo", "image", "evidence", "attach")):
        answer = "You can attach a JPEG, PNG, or WebP image up to 5 MB on the report or complaint details page."
    elif any(word in text for word in ("location", "address", "map", "gps")):
        answer = "Enter a location description. Coordinates are optional; the public issue map rounds coordinates to reduce location precision."
    elif any(word in text for word in ("submit", "report", "complaint")):
        answer = "Sign in, choose Report an issue, complete the title, description, category, and location fields, then submit."
    else:
        answer = "I can explain how to submit a report, attach an image, enter a location, or track a report. For local service rules, contact the relevant municipal office."
    return {"answer": answer, "source": "JANASEVA portal help", "advisory": False}


def resolution_support(title, description, status):
    missing = []
    if len(description.strip()) < 25:
        missing.append("A more detailed issue description may help the service team.")
    if not title.strip():
        missing.append("A clear issue title is missing.")
    return {"summary": f"{title.strip()}: {description.strip()[:220]}", "current_status": status,
            "missing_information": missing, "draft_response": "Thank you for reporting this issue. The service team has updated the report. Please review the status timeline for the latest information.",
            "advisory": True, "provider": "rule-based fallback"}
