"""Grounded replies, agent runs and standard LangGraph PostgreSQL checkpoints.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("citations", "tool_trace"):
        op.add_column("conversation_messages", sa.Column(name, postgresql.JSONB(), nullable=True))
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "purchase_order_id", sa.Uuid(), sa.ForeignKey("purchase_orders.id"), nullable=True
        ),
        sa.Column("proposal", postgresql.JSONB(), nullable=True),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("user_id", "request_id"),
        sa.CheckConstraint(
            "status IN ('running','awaiting_approval','approved','rejected','error')",
            name="agent_run_status",
        ),
    )
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    # Standard langgraph-checkpoint-postgres 3.2 schema. Runtime does not run DDL.
    op.execute("CREATE TABLE checkpoint_migrations (v INTEGER PRIMARY KEY)")
    op.execute(
        "CREATE TABLE checkpoints (thread_id TEXT NOT NULL, "
        "checkpoint_ns TEXT NOT NULL DEFAULT '', checkpoint_id TEXT NOT NULL, "
        "parent_checkpoint_id TEXT, type TEXT, checkpoint JSONB NOT NULL, "
        "metadata JSONB NOT NULL DEFAULT '{}', PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id))"
    )
    op.execute(
        "CREATE TABLE checkpoint_blobs (thread_id TEXT NOT NULL, "
        "checkpoint_ns TEXT NOT NULL DEFAULT '', "
        "channel TEXT NOT NULL, version TEXT NOT NULL, type TEXT NOT NULL, blob BYTEA, "
        "PRIMARY KEY(thread_id,checkpoint_ns,channel,version))"
    )
    op.execute(
        "CREATE TABLE checkpoint_writes (thread_id TEXT NOT NULL, "
        "checkpoint_ns TEXT NOT NULL DEFAULT '', checkpoint_id TEXT NOT NULL, "
        "task_id TEXT NOT NULL, idx INTEGER NOT NULL, channel TEXT NOT NULL, "
        "type TEXT, blob BYTEA NOT NULL, task_path TEXT NOT NULL DEFAULT '', "
        "PRIMARY KEY(thread_id,checkpoint_ns,checkpoint_id,task_id,idx))"
    )
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        op.create_index(f"{table}_thread_id_idx", table, ["thread_id"])
    op.execute("INSERT INTO checkpoint_migrations(v) SELECT generate_series(0,9)")


def downgrade():
    for table in (
        "checkpoint_writes",
        "checkpoint_blobs",
        "checkpoints",
        "checkpoint_migrations",
        "agent_runs",
    ):
        op.drop_table(table)
    for name in ("tool_trace", "citations"):
        op.drop_column("conversation_messages", name)
