"""initialize

Revision ID: cac2000912a5
Revises:
Create Date: 2020-04-07 21:53:03.499040

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy_utils import EncryptedType

import constants

# revision identifiers, used by Alembic.
revision = 'cac2000912a5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('people',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('identity', sa.String(length=64), nullable=False),
    sa.Column('referrer_id', sa.String(length=16), nullable=True),
    sa.Column('privacy', sa.String(length=8), server_default='public', nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled', 'suspended'), nullable=False),
    sa.ForeignKeyConstraint(['referrer_id'], ['people.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('identity')
    )
    op.create_table('time_zone_name',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('status', sa.Enum('active', 'disabled'), server_default='active', nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('categories',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled'), server_default='active', nullable=False),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('name', 'uid', name='uniq_category_owner')
    )
    op.create_table('contacts',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('label', sa.Enum('home', 'mobile', 'other', 'work'), server_default='home', nullable=False),
    sa.Column('type', sa.Enum('email', 'linkedin', 'location', 'messenger', 'slack', 'sms', 'voice', 'whatsapp'), server_default='email', nullable=False),
    sa.Column('carrier', sa.String(length=16), nullable=True),
    sa.Column('info', sa.String(length=255), nullable=True),
    sa.Column('muted', sa.BOOLEAN(), server_default=sa.text('0'), nullable=False),
    sa.Column('rank', sa.INTEGER(), server_default='1', nullable=False),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('privacy', sa.String(length=8), server_default='member', nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'unconfirmed', 'disabled'), server_default='unconfirmed', nullable=False),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('info', 'type', name='uniq_info_type')
    )
    with op.batch_alter_table('contacts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contacts_uid'), ['uid'], unique=False)

    op.create_table('grants',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=24), nullable=False),
    sa.Column('value', sa.String(length=64), nullable=False),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('expires', sa.TIMESTAMP(), nullable=True),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled'), server_default='active', nullable=False),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('name', 'uid', name='uniq_grant_user')
    )
    op.create_table(
    'locations',
    sa.Column('id', sa.String(length=16), primary_key=True, unique=True),
    sa.Column('name', sa.String(length=255)),
    sa.Column('address', sa.String(length=255)),
    sa.Column('city', sa.String(length=64), nullable=False),
    sa.Column('state', sa.String(length=16)),
    sa.Column('postalcode', sa.String(length=12)),
    sa.Column('country', sa.String(length=2), nullable=False,
              server_default=constants.DEFAULT_COUNTRY),
    # Unsupported by MariaDB, alas
    # sa.Column('geo', Geometry(geometry_type='POINT', management=True)),
    sa.Column('geolat', sa.INTEGER()),
    sa.Column('geolong', sa.INTEGER()),
    sa.Column('neighborhood', sa.String(length=32)),
    sa.Column('privacy', sa.String(length=8),
              nullable=False, server_default=u"public"),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('category_id', sa.String(length=16), nullable=False),
    sa.Column('created', sa.TIMESTAMP(), nullable=False,
              server_default=sa.func.now()),
    sa.Column('modified', sa.TIMESTAMP()),
    sa.Column('status', sa.Enum('active', u'disabled'), nullable=False),
    sa.ForeignKeyConstraint(['uid'], [u'people.id']),
    sa.ForeignKeyConstraint(['category_id'], [u'categories.id']),
    )

    op.create_table('messages',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('content', sa.TEXT(), nullable=False),
    sa.Column('subject', sa.String(length=128), nullable=True),
    sa.Column('sender_id', sa.String(length=16), nullable=False),
    sa.Column('recipient_id', sa.String(length=16), nullable=True),
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
    sa.UniqueConstraint('id')
    )
    op.create_table('profileitems',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('item', sa.Enum('birthday', 'employer', 'gender', 'hometown', 'jobtitle', 'lang', 'location', 'partner', 'album', 'reminders', 'tz'), nullable=False),
    sa.Column('value', sa.String(length=32), nullable=True),
    sa.Column('tz_id', sa.INTEGER(), nullable=True),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled'), nullable=False),
    sa.ForeignKeyConstraint(['tz_id'], ['time_zone_name.id'], ),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('uid', 'item', name='uniq_itemuid')
    )
    op.create_table('directmessages',
    sa.Column('message_id', sa.String(length=16), nullable=False),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('message_id'),
    sa.UniqueConstraint('message_id', 'uid', name='uniq_directmessage')
    )
    with op.batch_alter_table('directmessages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_directmessages_uid'), ['uid'], unique=False)

    op.create_table('lists',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('description', sa.TEXT(), nullable=True),
    sa.Column('privacy', sa.String(length=8), server_default='secret', nullable=False),
    sa.Column('category_id', sa.String(length=16), nullable=False),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled'), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('name', 'uid', name='uniq_list_owner')
    )
    op.create_table('listmembers',
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('list_id', sa.String(length=16), nullable=False),
    sa.Column('authorization', sa.String(length=8), server_default='member', nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['list_id'], ['lists.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('uid'),
    sa.UniqueConstraint('list_id', 'uid', name='uniq_listmember')
    )
    with op.batch_alter_table('listmembers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_listmembers_list_id'), ['list_id'], unique=False)

    op.create_table('listmessages',
    sa.Column('message_id', sa.String(length=16), nullable=False),
    sa.Column('list_id', sa.String(length=16), nullable=False),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['list_id'], ['lists.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('message_id'),
    sa.UniqueConstraint('list_id', 'message_id', name='uniq_listmessage')
    )
    with op.batch_alter_table('listmessages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_listmessages_list_id'), ['list_id'], unique=False)

    op.create_table('settings',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('privacy', sa.String(length=8), server_default='public', nullable=False),
    sa.Column('smtp_port', sa.INTEGER(), server_default='25', nullable=False),
    sa.Column('smtp_smarthost', sa.String(length=255), nullable=True),
    sa.Column('country', sa.String(length=2), server_default='US', nullable=False),
    sa.Column('lang', sa.String(length=6), server_default='en_US', nullable=False),
    sa.Column('tz_id', sa.INTEGER(), server_default='598', nullable=False),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.Column('window_title', sa.String(length=127), server_default='Conclave Event Management', nullable=True),
    sa.Column('default_cat_id', sa.String(length=16), nullable=False),
    sa.Column('administrator_id', sa.String(length=16), nullable=False),
    sa.Column('default_hostlist_id', sa.String(length=16), nullable=True),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.ForeignKeyConstraint(['administrator_id'], ['people.id'], ),
    sa.ForeignKeyConstraint(['default_cat_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['default_hostlist_id'], ['lists.id'], ),
    sa.ForeignKeyConstraint(['tz_id'], ['time_zone_name.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_table('accounts',
    sa.Column('id', sa.String(length=16), nullable=False, primary_key=True, unique=True),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('uid', sa.String(length=16), nullable=False),
    sa.Column('password', EncryptedType(sa.String(length=77)),
              nullable=False),
    sa.Column('password_must_change', sa.BOOLEAN(), server_default=sa.text('0'), nullable=False),
    sa.Column('totp_secret', EncryptedType(sa.String(length=32)), nullable=True),
    sa.Column('is_admin', sa.BOOLEAN(), server_default=sa.text('0'), nullable=False),
    sa.Column('settings_id', sa.String(length=16), nullable=False),
    sa.Column('last_login', sa.TIMESTAMP(), nullable=True),
    sa.Column('invalid_attempts', sa.INTEGER(), server_default='0', nullable=False),
    sa.Column('last_invalid_attempt', sa.TIMESTAMP(), nullable=True),
    sa.Column('created', sa.TIMESTAMP(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('modified', sa.TIMESTAMP(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled'), nullable=False),
    sa.ForeignKeyConstraint(['settings_id'], ['settings.id'], ),
    sa.ForeignKeyConstraint(['uid'], ['people.id'], ondelete='CASCADE'),
    sa.UniqueConstraint('id', 'uid', name='uniq_account_user'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('uid')
    )
    # ### end Alembic commands ###
