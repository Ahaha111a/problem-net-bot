"""Founder cabinet, LMS expansion, AI safety and deployment telemetry."""
from alembic import op
import sqlalchemy as sa

revision = "0003_founder_ai_lms_ops"
down_revision = "0002_staff_lms_kpi_ai_ops"
branch_labels = None
depends_on = None

ID = sa.BigInteger


def upgrade():
    op.create_table(
        "lms_practical_tasks",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("course_id", ID, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text),
        sa.Column("max_score", sa.Integer, nullable=False, server_default="100"),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["course_id"], ["lms_courses.id"]),
    )
    op.create_table(
        "lms_exams",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("course_id", ID, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("pass_score", sa.Integer, nullable=False, server_default="70"),
        sa.Column("attempt_limit", sa.Integer, nullable=False, server_default="3"),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["course_id"], ["lms_courses.id"]),
    )
    op.create_table(
        "lms_exam_attempts",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("exam_id", ID, nullable=False),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("answers", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["exam_id"], ["lms_exams.id"]),
    )
    op.create_table(
        "ai_safety_events",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("story_id", ID),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("risk_score", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("flags", sa.Text),
        sa.Column("details", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"]),
    )
    op.create_table(
        "ai_model_health",
        sa.Column("model", sa.Text, primary_key=True),
        sa.Column("status", sa.Text, nullable=False, server_default="unknown"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("details", sa.Text),
        sa.Column("checked_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "founder_notes",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_safety_story_created", "ai_safety_events", ["story_id", "created_at"])
    op.create_index("ix_exam_attempt_admin", "lms_exam_attempts", ["admin_id", "created_at"])

    op.execute(sa.text("""
        INSERT INTO ai_model_configs(model,enabled,priority,max_tokens,temperature)
        VALUES
          ('llama-3.3-70b-versatile', true, 10, 1800, 0.2),
          ('llama-3.1-8b-instant', true, 20, 1600, 0.2)
        ON CONFLICT(model) DO NOTHING
    """))


def downgrade():
    for name in [
        "founder_notes",
        "ai_model_health",
        "ai_safety_events",
        "lms_exam_attempts",
        "lms_exams",
        "lms_practical_tasks",
    ]:
        op.drop_table(name)
