from models import Badge
from extensions import db
from services.mock_data import seed_mock_data
 # This service initializes the database with default data and performs necessary migrations.
#thıs servıce controls setup of database before the app starts. It ensures that the database schema is up to date and that essential data, such as badges, is seeded. This allows the application to function correctly with the expected data structure and content from the outset.
DEFAULT_BADGES = [
    ("first step", "Completed your first project", "projects_completed:1"),
    ("veteran", "Completed 5 projects", "projects_completed:5"),
    ("expert", "Received 10 endorsements", "endorsements_received:10"),
]


def initialize_bootstrap_data():
    migrate_user_avatar_column()
    seed_badges()
    seed_mock_data()


def migrate_user_avatar_column():
    """Add newer columns without failing on databases that already have them."""
    try:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def seed_badges():
    existing_badges = {badge.name for badge in Badge.query.all()}

    for name, description, condition in DEFAULT_BADGES:
        if name not in existing_badges:
            db.session.add(Badge(name=name, description=description, condition=condition))

    db.session.commit()
