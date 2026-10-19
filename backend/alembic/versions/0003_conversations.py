"""Persist user-owned AI conversations and idempotent turns.

Revision ID: 0003
Revises: 00df5fcbfbce
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "00df5fcbfbce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("active_request_id", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("usage", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("finish_reason", sa.String(40), nullable=True),
        sa.UniqueConstraint("user_id", "request_id", "role"),
        sa.UniqueConstraint("conversation_id", "ordinal"),
        sa.CheckConstraint("role IN ('user','assistant')", name="conversation_message_role"),
        sa.CheckConstraint(
            "status IN ('pending','streaming','completed','cancelled','error')",
            name="conversation_message_status",
        ),
        sa.CheckConstraint("length(content) <= 32768", name="conversation_message_length"),
    )
    op.create_index("ix_conversation_messages_user_id", "conversation_messages", ["user_id"])
    op.create_index(
        "ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_user_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
