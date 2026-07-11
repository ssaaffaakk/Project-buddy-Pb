"""
Marshmallow schemas for the JSON API (/api/v1).

Request schemas validate and deserialize input (bad input → 422 with per-field
errors); response schemas define the exact JSON shape and feed the OpenAPI spec
that renders at /api/docs.
"""

from marshmallow import Schema, fields, validate


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenRequestSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class TokenResponseSchema(Schema):
    access_token = fields.Str()
    token_type = fields.Str()
    expires_in = fields.Int(metadata={"description": "Seconds until expiry"})


# ── Shared ────────────────────────────────────────────────────────────────────

class UserPublicSchema(Schema):
    id = fields.Int()
    first_name = fields.Str()
    last_name = fields.Str()
    department = fields.Str(allow_none=True)
    avatar_url = fields.Str(allow_none=True)


class PaginationArgsSchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=50))


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectListArgsSchema(PaginationArgsSchema):
    q = fields.Str(load_default=None, metadata={"description": "Search in title/description"})
    tag = fields.Str(load_default=None, metadata={"description": "Filter by topic tag"})
    status = fields.Str(
        load_default="open",
        validate=validate.OneOf(["open", "closed", "completed"]),
    )


class ProjectSchema(Schema):
    id = fields.Int()
    title = fields.Str()
    description = fields.Str()
    course = fields.Str(allow_none=True)
    status = fields.Str()
    team_size = fields.Int()
    member_count = fields.Function(lambda p: p.current_member_count())
    spots_left = fields.Function(
        lambda p: max(0, p.team_size - p.current_member_count())
    )
    deadline = fields.DateTime(allow_none=True)
    created_at = fields.DateTime()
    owner = fields.Nested(UserPublicSchema)
    tags = fields.Function(lambda p: [t.tag for t in p.topic_tags])
    required_skills = fields.Function(lambda p: [s.skill for s in p.required_skills])


class ProjectDetailSchema(ProjectSchema):
    vote_score = fields.Int()


class ProjectPageSchema(Schema):
    items = fields.List(fields.Nested(ProjectSchema))
    page = fields.Int()
    per_page = fields.Int()
    total = fields.Int()
    pages = fields.Int()


class ApplyArgsSchema(Schema):
    message = fields.Str(load_default=None, validate=validate.Length(max=2000))


# ── Recommendations ───────────────────────────────────────────────────────────

class RecommendationSchema(Schema):
    project = fields.Nested(ProjectSchema)
    fit_percent = fields.Float()


class RecommendationsResponseSchema(Schema):
    items = fields.List(fields.Nested(RecommendationSchema))
    variant = fields.Str(allow_none=True,
                         metadata={"description": "A/B arm that ranked these ('ml'/'rules')"})


# ── Me ────────────────────────────────────────────────────────────────────────

class MeSchema(Schema):
    id = fields.Int()
    first_name = fields.Str()
    last_name = fields.Str()
    email = fields.Email()
    role = fields.Str()
    department = fields.Str(allow_none=True)
    bio = fields.Str(allow_none=True)
    avatar_url = fields.Str(allow_none=True)
    interests = fields.Function(lambda u: [i.tag for i in u.interest_tags])
    skills = fields.Function(lambda u: [s.skill for s in u.skills])


# ── Study groups ──────────────────────────────────────────────────────────────

class StudyGroupSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    topic = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    is_private = fields.Bool()
    member_count = fields.Function(lambda g: g.member_count())
    created_at = fields.DateTime()


class StudyGroupPageSchema(Schema):
    items = fields.List(fields.Nested(StudyGroupSchema))
    page = fields.Int()
    per_page = fields.Int()
    total = fields.Int()
    pages = fields.Int()


# ── Generic ───────────────────────────────────────────────────────────────────

class MessageSchema(Schema):
    message = fields.Str()
