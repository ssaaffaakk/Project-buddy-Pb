"""
Applicant → project fit scoring (explainable).

When a project owner reviews applications, this puts a fit % and the reasons
behind it next to each applicant, so accept/reject is an informed decision
rather than a guess. Same vocabulary as the recommender: required-skill
overlap, interest-topic overlap with the project's tags, and course match.

Pure/deterministic and read-only — safe to call per application in a request.
"""

from services.recommendation_service import expand_user_interests, normalize_tag

_W_SKILL = 30       # per required skill the applicant has (strongest signal)
_W_TOPIC = 10       # per matching interest topic
_W_COURSE = 20      # applicant took the project's course


def score_applicant(applicant, project):
    """Return {'percent': int, 'reasons': [str], 'shared_skills': [str]}.

    percent is capped at 99 and floored at a small base so an applicant who
    bothered to apply never shows a demotivating 0.
    """
    req_skills = {normalize_tag(s.skill) for s in project.required_skills if s.skill}
    proj_tags = {normalize_tag(t.tag) for t in project.topic_tags if t.tag}
    proj_course = normalize_tag(project.course) if project.course else None

    app_skills = {normalize_tag(s.skill) for s in applicant.skills if s.skill}
    app_courses = {normalize_tag(c.course) for c in applicant.courses if c.course}
    app_topics = {normalize_tag(t)
                  for t in expand_user_interests([i.tag for i in applicant.interest_tags])}

    shared_skills = req_skills & app_skills
    shared_topics = proj_tags & app_topics
    course_match = bool(proj_course and proj_course in app_courses)

    # Denominator: the strongest possible fit for THIS project, so the percent
    # is "how much of what this project wants does the applicant have".
    max_score = (_W_SKILL * max(1, len(req_skills))
                 + _W_TOPIC * max(1, len(proj_tags))
                 + _W_COURSE)
    raw = (_W_SKILL * len(shared_skills)
           + _W_TOPIC * len(shared_topics)
           + (_W_COURSE if course_match else 0))
    percent = max(8, min(99, round(raw / max_score * 100))) if max_score else 8

    reasons = []
    if shared_skills:
        reasons.append(f"has {len(shared_skills)} required skill"
                       f"{'s' if len(shared_skills) != 1 else ''}")
    if course_match:
        reasons.append("took this course")
    if shared_topics:
        reasons.append(f"{len(shared_topics)} matching interest"
                       f"{'s' if len(shared_topics) != 1 else ''}")
    if not reasons:
        reasons.append("no overlapping skills or interests")

    return {
        "percent": percent,
        "reasons": reasons,
        "shared_skills": sorted(shared_skills),
    }
