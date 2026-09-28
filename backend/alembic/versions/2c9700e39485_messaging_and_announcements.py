"""messaging and announcements

Revision ID: 2c9700e39485
Revises: 6c1d2a9e5b70
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '2c9700e39485'
down_revision = '6c1d2a9e5b70'
branch_labels = None
depends_on = None

TENANT_SCOPED_NEW_TABLES = ["message_threads", "thread_participants", "messages", "announcements"]


def _tenant_id():
    return sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade() -> None:
    op.execute("CREATE TYPE thread_kind AS ENUM ('conversation', 'convocation')")
    op.create_table(
        "message_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), _tenant_id(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("kind", postgresql.ENUM("conversation", "convocation", name="thread_kind", create_type=False), nullable=False),
        sa.Column("meeting_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meeting_place", sa.String(length=200), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False, index=True),
        *_stamps(),
    )
    op.create_table(
        "thread_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), _tenant_id(),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
        sa.UniqueConstraint("thread_id", "user_id", name="uq_thread_participant"),
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), _tenant_id(),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        *_stamps(),
    )
    op.create_index("ix_messages_thread_created", "messages", ["thread_id", "created_at"])
    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), _tenant_id(),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        *_stamps(),
    )
    for table in TENANT_SCOPED_NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
            f"WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )


def downgrade() -> None:
    for table in reversed(TENANT_SCOPED_NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
    op.drop_table("announcements")
    op.drop_index("ix_messages_thread_created", table_name="messages")
    op.drop_table("messages")
    op.drop_table("thread_participants")
    op.drop_table("message_threads")
    op.execute("DROP TYPE thread_kind")
