"""Responses API — replace conversations/messages with stateless response chaining.

Revision ID: 20260212_000005
Revises: 20260212_000004
Create Date: 2026-02-12 00:00:05.000000

Changes:
1. Create `responses` table
2. Create `response_items` table
3. Add `latest_response_id`, `response_count` to `conversations`
4. Rename `tool_executions.message_id` → `response_item_id`, update FK
5. Add `response_id` to `usage_logs`
6. Migrate data: messages → responses + response_items
7. Drop `messages` table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260212_000005"
down_revision = "20260212_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create responses table
    op.create_table(
        "responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assistant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_response_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Config snapshot
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("tool_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("knowledge_base_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("max_tool_rounds", sa.Integer(), server_default="10", nullable=False),
        # Status
        sa.Column("status", sa.String(50), server_default="in_progress", nullable=False),
        sa.Column("status_reason", sa.String(100), nullable=True),
        # Usage
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        # Error
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Metadata
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_response_id"], ["responses.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_responses_organization_id", "responses", ["organization_id"])
    op.create_index("ix_responses_conversation_id", "responses", ["conversation_id"])
    op.create_index("ix_responses_user_id", "responses", ["user_id"])
    op.create_index("ix_responses_assistant_id", "responses", ["assistant_id"])
    op.create_index("ix_responses_previous_response_id", "responses", ["previous_response_id"])

    # 2. Create response_items table
    op.create_table(
        "response_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_order", sa.Integer(), server_default="0", nullable=False),
        # Type & direction
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        # Message fields
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(50), server_default="text", nullable=False),
        # Function call fields
        sa.Column("call_id", sa.String(100), nullable=True),
        sa.Column("function_name", sa.String(255), nullable=True),
        sa.Column("function_arguments", sa.Text(), nullable=True),
        # Function output fields
        sa.Column("function_output", sa.Text(), nullable=True),
        # RAG context fields
        sa.Column("rag_sources", postgresql.JSONB(), nullable=True),
        # Metadata
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["response_id"], ["responses.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_response_items_response_id", "response_items", ["response_id"])
    op.create_index("ix_response_items_type", "response_items", ["item_type"])

    # 3. Add columns to conversations
    op.add_column("conversations", sa.Column("latest_response_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("conversations", sa.Column("response_count", sa.Integer(), server_default="0", nullable=False))
    op.create_foreign_key(
        "fk_conversations_latest_response_id",
        "conversations",
        "responses",
        ["latest_response_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Rename tool_executions.message_id → response_item_id
    # Drop old FK constraint (name may vary, try common patterns)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'tool_executions_message_id_fkey'
                AND table_name = 'tool_executions'
            ) THEN
                ALTER TABLE tool_executions DROP CONSTRAINT tool_executions_message_id_fkey;
            END IF;
        END $$;
    """)

    # Rename column (safe if column exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tool_executions' AND column_name = 'message_id'
            ) THEN
                ALTER TABLE tool_executions RENAME COLUMN message_id TO response_item_id;
            END IF;
        END $$;
    """)

    # Add new FK to response_items
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tool_executions' AND column_name = 'response_item_id'
            ) THEN
                ALTER TABLE tool_executions
                    ADD CONSTRAINT tool_executions_response_item_id_fkey
                    FOREIGN KEY (response_item_id) REFERENCES response_items(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # 5. Add response_id to usage_logs
    op.add_column("usage_logs", sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_usage_logs_response_id",
        "usage_logs",
        "responses",
        ["response_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_usage_logs_response_id", "usage_logs", ["response_id"])

    # 6. Migrate data: messages → responses + response_items
    # We process this in raw SQL for performance
    op.execute("""
        DO $$
        DECLARE
            conv RECORD;
            msg RECORD;
            prev_response_id UUID;
            new_response_id UUID;
            seq_counter INTEGER;
            user_msg_content TEXT;
            is_first_response BOOLEAN;
        BEGIN
            -- Check if messages table exists before trying to migrate
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages') THEN
                RETURN;
            END IF;

            FOR conv IN
                SELECT DISTINCT c.id, c.organization_id, c.user_id, c.assistant_id
                FROM conversations c
                WHERE EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id)
                ORDER BY c.created_at
            LOOP
                prev_response_id := NULL;
                is_first_response := TRUE;

                -- Process messages in order, grouping user+assistant pairs
                FOR msg IN
                    SELECT * FROM messages
                    WHERE conversation_id = conv.id
                    ORDER BY created_at ASC
                LOOP
                    IF msg.role = 'user' THEN
                        -- Start a new response for this user message
                        new_response_id := gen_random_uuid();
                        seq_counter := 0;
                        user_msg_content := msg.content;

                        INSERT INTO responses (
                            id, organization_id, user_id, assistant_id,
                            conversation_id, previous_response_id,
                            model, provider, status, status_reason,
                            created_at, updated_at
                        )
                        VALUES (
                            new_response_id, conv.organization_id, conv.user_id, conv.assistant_id,
                            conv.id, prev_response_id,
                            COALESCE((msg.meta_data->>'model')::TEXT, 'unknown'),
                            COALESCE((msg.meta_data->>'provider')::TEXT, 'unknown'),
                            'completed', 'stop',
                            msg.created_at, msg.created_at
                        );

                        -- Save user message as input item
                        INSERT INTO response_items (
                            id, response_id, sequence_order,
                            item_type, direction, role, content,
                            created_at, updated_at
                        )
                        VALUES (
                            gen_random_uuid(), new_response_id, seq_counter,
                            'message', 'input', 'user', msg.content,
                            msg.created_at, msg.created_at
                        );
                        seq_counter := seq_counter + 1;

                    ELSIF msg.role = 'assistant' AND new_response_id IS NOT NULL THEN
                        -- Save assistant message as output item
                        INSERT INTO response_items (
                            id, response_id, sequence_order,
                            item_type, direction, role, content,
                            created_at, updated_at
                        )
                        VALUES (
                            gen_random_uuid(), new_response_id, seq_counter,
                            'message', 'output', 'assistant', msg.content,
                            msg.created_at, msg.created_at
                        );
                        seq_counter := seq_counter + 1;

                        -- Update response usage from message metadata
                        UPDATE responses SET
                            model = COALESCE((msg.meta_data->>'model')::TEXT, model),
                            provider = COALESCE((msg.meta_data->>'provider')::TEXT, provider),
                            input_tokens = COALESCE((msg.meta_data->>'input_tokens')::INTEGER, 0),
                            output_tokens = COALESCE((msg.meta_data->>'output_tokens')::INTEGER, 0),
                            total_tokens = COALESCE((msg.meta_data->>'input_tokens')::INTEGER, 0)
                                + COALESCE((msg.meta_data->>'output_tokens')::INTEGER, 0)
                        WHERE id = new_response_id;

                        prev_response_id := new_response_id;
                        new_response_id := NULL;
                    END IF;
                END LOOP;

                -- Update conversation with latest response
                UPDATE conversations SET
                    latest_response_id = prev_response_id,
                    response_count = (
                        SELECT COUNT(*) FROM responses WHERE conversation_id = conv.id
                    )
                WHERE id = conv.id;
            END LOOP;
        END $$;
    """)

    # 7. Drop messages table
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages') THEN
                DROP TABLE messages CASCADE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Recreate messages table
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(50), server_default="text", nullable=False),
        sa.Column("meta_data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column("tool_results", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # Drop response_id from usage_logs
    op.drop_index("ix_usage_logs_response_id", "usage_logs")
    op.drop_constraint("fk_usage_logs_response_id", "usage_logs", type_="foreignkey")
    op.drop_column("usage_logs", "response_id")

    # Rename response_item_id back to message_id on tool_executions
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'tool_executions_response_item_id_fkey'
                AND table_name = 'tool_executions'
            ) THEN
                ALTER TABLE tool_executions DROP CONSTRAINT tool_executions_response_item_id_fkey;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tool_executions' AND column_name = 'response_item_id'
            ) THEN
                ALTER TABLE tool_executions RENAME COLUMN response_item_id TO message_id;
            END IF;
        END $$;
    """)

    # Drop columns from conversations
    op.drop_constraint("fk_conversations_latest_response_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "response_count")
    op.drop_column("conversations", "latest_response_id")

    # Drop response_items and responses tables
    op.drop_table("response_items")
    op.drop_table("responses")
