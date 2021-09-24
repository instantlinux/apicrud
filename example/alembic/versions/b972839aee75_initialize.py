# -*- coding: utf-8 -*-

"""initialize

Revision ID: b972839aee75
Revises:
Create Date: 2020-04-07 21:53:03.499040

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b972839aee75'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('messages',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('content', sa.TEXT(), nullable=False),
    sa.Column('subject', sa.String(length=128), nullable=True),
    sa.Column('sender_id', sa.String(length=16), nullable=False),
    sa.Column('recipient_id', sa.String(length=16), nullable=True),
    sa.Column('list_id', sa.String(length=16), nullable=True),
    sa.Column('privacy', sa.String(length=8), server_default='secret', nullable=False),
    sa.Column('published', sa.BOOLEAN(), nullable=True),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('viewed', sa.TIMESTAMP(), nullable=True),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled'), server_default='active', nullable=False),
    sa.ForeignKeyConstraint(['recipient_id'], ['people.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['people.id'], ),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    )

    op.create_table('directmessages',
    sa.Column('message_id', sa.String(length=16), primary_key=True, nullable=False),
    sa.Column('uid', sa.String(length=16), primary_key=True, nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ondelete='CASCADE'),
    )
    with op.batch_alter_table('directmessages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_directmessages_uid'), ['uid'], unique=False)
        batch_op.create_unique_constraint('uniq_directmessage', ['message_id', 'uid'])

    op.create_table('listmessages',
    sa.Column('message_id', sa.String(length=16), primary_key=True, nullable=False),
    sa.Column('list_id', sa.String(length=16), primary_key=True, nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['list_id'], ['lists.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    )
    with op.batch_alter_table('listmessages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_listmessages_list_id'), ['list_id'], unique=False)
        batch_op.create_unique_constraint('uniq_listmessage', ['list_id', 'message_id'])

    # TODO Move to media
    # op.create_table('messagefiles',
    # sa.Column('file_id', sa.String(length=16), primary_key=True, nullable=False),
    # sa.Column('message_id', sa.String(length=16), primary_key=True, nullable=False),
    # sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    # sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
    # sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    # )
    # with op.batch_alter_table('messagefiles', schema=None) as batch_op:
    #     batch_op.create_index(batch_op.f('ix_messagefiles_message_id'), ['message_id'], unique=False)

    # ### end Alembic commands ###
