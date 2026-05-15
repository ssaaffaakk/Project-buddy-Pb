from datetime import datetime
from models import Project
from extensions import db


def flag_overdue_projects():
    """
    Find all projects where deadline has passed and status is still open/closed.
    Sets status = 'completed' and records completed_at. Run periodically.
    """
    for project in Project.query.filter(
        Project.deadline.isnot(None),
        Project.deadline < datetime.utcnow(),
        Project.status.in_(["open", "closed"])
    ).all():
        project.status = "completed"
        if not project.completed_at:
            project.completed_at = datetime.utcnow()
        db.session.add(project)
    db.session.commit()
    


if __name__ == "__main__":
    # Run manually: python services/deadline_checker.py
    from app import create_app
    app = create_app()
    with app.app_context():
        flag_overdue_projects()
        print("Deadline check complete.")