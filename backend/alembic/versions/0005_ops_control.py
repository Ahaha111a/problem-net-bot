"""Operational control plane: workload, prompts, incidents, policies and shadow runs."""
from alembic import op
import sqlalchemy as sa

revision = "0005_ops_control"
down_revision = "0004_remove_certificates_and_modernize"
branch_labels = None
depends_on = None
ID = sa.BigInteger


def upgrade():
    op.create_table(
        "moderator_workload",
        sa.Column("admin_id", ID, primary_key=True),
        sa.Column("active_tasks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_tasks", sa.Integer, nullable=False, server_default="10"),
        sa.Column("weight", sa.Float, nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_assigned_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", ID),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )
    op.create_table(
        "policy_rules",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("config_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by", ID),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "incidents",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("service", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False, server_default="medium"),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("details", sa.Text),
        sa.Column("deployment_id", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column("resolution_note", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("resolved_at", sa.DateTime),
    )
    op.create_table(
        "rollback_actions",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("incident_id", ID),
        sa.Column("service", sa.Text, nullable=False),
        sa.Column("target_deployment_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("details", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "ai_shadow_runs",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("story_id", ID),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("result", sa.Text),
        sa.Column("latency_ms", sa.Integer, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_workload_tasks", "moderator_workload", ["active_tasks", "enabled"])
    op.create_index("ix_prompt_active", "prompt_versions", ["name", "active"])
    op.create_index("ix_incident_status_created", "incidents", ["status", "created_at"])
    op.create_index("ix_shadow_created", "ai_shadow_runs", ["created_at"])
    # IMPORTANT: do not embed JSON literals directly into sa.text().
    # SQLAlchemy interprets tokens such as :15 / :false inside text() as
    # bind parameters. Pass the complete JSON string as a named parameter.
    stmt = sa.text("""
        INSERT INTO policy_rules(key, title, config_json, enabled)
        VALUES (:key, :title, :config_json, :enabled)
        ON CONFLICT(key) DO NOTHING
    """)
    bind = op.get_bind()
    defaults = [
        (
            "ai_shadow_mode",
            "AI Shadow Mode",
            '{"enabled":false,"model":""}',
            False,
        ),
        (
            "auto_rollback",
            "Automatic rollback",
            '{"enabled":false,"severity":"critical"}',
            False,
        ),
        (
            "safety_policy",
            "Safety policy",
            '{"manual_review_risk":0.75,"reject_risk":0.95,"require_second_opinion":true}',
            True,
        ),
        (
            "sla_policy",
            "SLA policy",
            '{"critical_minutes":15,"high_minutes":30,"normal_minutes":120,"low_minutes":480}',
            True,
        ),
    ]
    for key, title, config_json, enabled in defaults:
        bind.execute(
            stmt,
            {
                "key": key,
                "title": title,
                "config_json": config_json,
                "enabled": enabled,
            },
        )


def downgrade():
    for name in ["ai_shadow_runs", "rollback_actions", "incidents", "policy_rules", "prompt_versions", "moderator_workload"]:
        op.drop_table(name)
