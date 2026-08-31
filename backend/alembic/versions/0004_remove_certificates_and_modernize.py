"""Remove LMS certificates and harden AI/LMS production behavior."""
from alembic import op
import sqlalchemy as sa

revision = "0004_remove_certificates_and_modernize"
down_revision = "0003_founder_ai_lms_ops"
branch_labels = None
depends_on = None

def upgrade():
    op.execute(sa.text("DROP TABLE IF EXISTS lms_certificates"))
    # Clean any duplicate assignments created by the old schema before adding the unique key.
    op.execute(sa.text("""
        DELETE FROM lms_assignments a
        USING lms_assignments b
        WHERE a.id > b.id AND a.admin_id = b.admin_id AND a.course_id = b.course_id
    """))
    # Prevent duplicate course assignments so automatic permission gating is idempotent.
    op.create_unique_constraint("uq_lms_assignment_admin_course", "lms_assignments", ["admin_id", "course_id"])
    op.execute(sa.text("UPDATE ai_model_configs SET enabled=false WHERE model IN ('llama-3.1-8b-instant','llama-3.3-70b-versatile')"))
    op.execute(sa.text("UPDATE app_settings SET value='openai/gpt-oss-120b' WHERE key='ai_model' AND value IN ('llama-3.3-70b-versatile','llama-3.1-8b-instant')"))
    op.execute(sa.text("UPDATE app_settings SET value='openai/gpt-oss-20b' WHERE key='ai_fallback_model' AND value IN ('llama-3.1-8b-instant','llama-3.3-70b-versatile')"))
    op.execute(sa.text("INSERT INTO app_settings(key,value) VALUES('ai_safety_model','openai/gpt-oss-safeguard-20b') ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value"))
    op.execute(sa.text("""
        INSERT INTO ai_model_configs(model,enabled,priority,max_tokens,temperature) VALUES
        ('openai/gpt-oss-120b',true,10,2200,0.2),
        ('openai/gpt-oss-20b',true,20,1800,0.2),
        ('qwen/qwen3.6-27b',true,30,1800,0.2),
        ('openai/gpt-oss-safeguard-20b',true,5,1200,0.0)
        ON CONFLICT(model) DO NOTHING
    """))

def downgrade():
    op.drop_constraint("uq_lms_assignment_admin_course", "lms_assignments", type_="unique")
