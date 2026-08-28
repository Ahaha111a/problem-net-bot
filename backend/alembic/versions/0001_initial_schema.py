"""Initial PostgreSQL schema for Problem-Net.

This replaces the old SQLite-created schema. The production database is now
PostgreSQL (Supabase) and every future schema change must be a new Alembic
revision instead of ad-hoc CREATE/ALTER statements in application code.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


ID = sa.BigInteger


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("ai_result", sa.Text),
        sa.Column("post_text", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="waiting"),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("channel_message_id", ID),
        sa.Column("ai_moderation_result", sa.Text),
        sa.Column("category", sa.Text),
        sa.Column("scheduled_at", sa.DateTime),
        sa.Column("scheduled_by", ID),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "support_dialogs",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("first_message", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column("support_status", sa.Text, nullable=False, server_default="new"),
        sa.Column("assigned_admin_id", ID),
        sa.Column("unread_admin", sa.Integer, nullable=False, server_default="0"),
        sa.Column("personal_contact_requested", sa.Integer, nullable=False, server_default="0"),
        sa.Column("admin_control_chat_id", ID),
        sa.Column("admin_control_message_id", ID),
        sa.Column("first_response_at", sa.DateTime),
        sa.Column("resolved_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "support_messages",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("dialog_id", ID, nullable=False),
        sa.Column("sender_id", ID, nullable=False),
        sa.Column("sender_type", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["dialog_id"], ["support_dialogs.id"]),
    )

    op.create_table(
        "users",
        sa.Column("user_id", ID, primary_key=True),
        sa.Column("notification_date", sa.Text),
        sa.Column("notification_minute", sa.Integer),
        sa.Column("notification_at", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "story_reactions",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("story_id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("reaction", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("story_id", "user_id", name="uq_story_reactions_story_user"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"]),
    )

    op.create_table(
        "admin_audit_log",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("story_id", ID),
        sa.Column("dialog_id", ID),
        sa.Column("user_id", ID),
        sa.Column("details", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "admin_roles",
        sa.Column("user_id", ID, primary_key=True),
        sa.Column("role", sa.Text, nullable=False, server_default="moderator"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "story_complaints",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("story_id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="new"),
        sa.Column("priority", sa.Text, nullable=False, server_default="normal"),
        sa.Column("assigned_admin_id", ID),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("story_id", "user_id", name="uq_story_complaints_story_user"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"]),
    )

    op.create_table(
        "story_versions",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("story_id", ID, nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("text", sa.Text),
        sa.Column("post_text", sa.Text),
        sa.Column("changed_by", ID, nullable=False),
        sa.Column("change_type", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"]),
    )

    op.create_table(
        "admin_notifications",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("read_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "support_sla",
        sa.Column("dialog_id", ID, primary_key=True),
        sa.Column("priority", sa.Text, nullable=False, server_default="normal"),
        sa.Column("first_response_due_at", sa.DateTime),
        sa.Column("resolved_at", sa.DateTime),
        sa.ForeignKeyConstraint(["dialog_id"], ["support_dialogs.id"]),
    )

    op.create_table(
        "moderator_actions",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text),
        sa.Column("target_id", ID),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "repost_jobs",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("story_id", ID, nullable=False),
        sa.Column("scheduled_at", sa.Text, nullable=False),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text),
        sa.Column("updated_by", ID),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "ai_checks",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_by", ID),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "story_locks",
        sa.Column("story_id", ID, primary_key=True),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("locked_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "system_errors",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("service", sa.Text, nullable=False),
        sa.Column("level", sa.Text, nullable=False, server_default="error"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "system_health",
        sa.Column("service", sa.Text, primary_key=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("details", sa.Text),
        sa.Column("checked_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "moderator_goals",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("period", sa.Text, nullable=False),
        sa.Column("target_publish", sa.Integer, nullable=False, server_default="0"),
        sa.Column("target_moderate", sa.Integer, nullable=False, server_default="0"),
        sa.Column("target_response", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("admin_id", "period", name="uq_moderator_goals_admin_period"),
    )

    op.create_table(
        "employee_training",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("admin_id", ID, nullable=False),
        sa.Column("course", sa.Text, nullable=False),
        sa.Column("lesson", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="assigned"),
        sa.Column("score", sa.Float),
        sa.Column("due_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "ai_priority_queue",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("story_id", ID, nullable=False),
        sa.Column("priority", sa.Text, nullable=False, server_default="normal"),
        sa.Column("status", sa.Text, nullable=False, server_default="queued"),
        sa.Column("reason", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processed_at", sa.DateTime),
    )

    op.create_table(
        "report_log",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("report_type", sa.Text, nullable=False),
        sa.Column("period_key", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("report_type", "period_key", name="uq_report_log_type_period"),
    )

    # Indexes used by the bot's queues and Mini App.
    op.create_index("ix_stories_status_scheduled", "stories", ["status", "scheduled_at"])
    op.create_index("ix_stories_user_id", "stories", ["user_id"])
    op.create_index("ix_stories_created_at", "stories", ["created_at"])
    op.create_index("ix_support_dialogs_status_updated", "support_dialogs", ["status", "updated_at"])
    op.create_index("ix_support_messages_dialog_id", "support_messages", ["dialog_id", "id"])
    op.create_index("ix_story_versions_story_id", "story_versions", ["story_id", "version_no"])
    op.create_index("ix_ai_priority_queue_status_priority", "ai_priority_queue", ["status", "priority", "id"])
    op.create_index("ix_admin_audit_created_at", "admin_audit_log", ["created_at"])


def downgrade() -> None:
    for table in [
        "report_log",
        "ai_priority_queue",
        "employee_training",
        "moderator_goals",
        "system_health",
        "system_errors",
        "story_locks",
        "ai_checks",
        "app_settings",
        "repost_jobs",
        "moderator_actions",
        "support_sla",
        "admin_notifications",
        "story_versions",
        "story_complaints",
        "admin_roles",
        "admin_audit_log",
        "story_reactions",
        "users",
        "support_messages",
        "support_dialogs",
        "stories",
    ]:
        op.drop_table(table)
