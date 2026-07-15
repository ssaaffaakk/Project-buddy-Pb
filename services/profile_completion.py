"""Profile completeness — drives the "Complete your profile" progress bar.

A small, dependency-light computation used on the user's own profile page to
nudge them to fill in the fields that make matching and discovery work better.
Percent is the share of checklist items done; items carry a link to where the
user can fix each one.
"""

from models import UserAvailability


# (label, predicate, link) — order defines display order of the checklist.
def profile_completion(user):
    """Return (percent:int, items:list[dict]).

    items: [{'label': str, 'done': bool, 'link': str}, ...]
    """
    has_availability = (
        UserAvailability.query.filter_by(user_id=user.id).first() is not None
    )

    items = [
        {"label": "Profile photo",      "done": bool(user.avatar_url),                        "link": "/edit-profile"},
        {"label": "Short bio",          "done": bool(user.bio and user.bio.strip()),          "link": "/edit-profile"},
        {"label": "Department",         "done": bool(user.department),                        "link": "/edit-profile"},
        {"label": "At least one skill", "done": len(user.skills) > 0,                          "link": "/edit-profile"},
        {"label": "Interest tags",      "done": len(user.interest_tags) > 0,                   "link": "/edit-profile"},
        {"label": "Courses",            "done": len(user.courses) > 0,                         "link": "/edit-profile"},
        {"label": "Weekly availability","done": has_availability,                              "link": "/availability"},
    ]

    done = sum(1 for it in items if it["done"])
    percent = round(done / len(items) * 100)
    return percent, items
