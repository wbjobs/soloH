"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


crop_type_enum = postgresql.ENUM('WHEAT', 'POTATO', 'CORN', 'RICE', name='croptype')
alert_type_enum = postgresql.ENUM('RISK', 'WARNING', name='alerttype')
notification_channel_enum = postgresql.ENUM('EMAIL', 'WEBHOOK', name='notificationchannel')


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')

    crop_type_enum.create(op.get_bind(), checkfirst=True)
    alert_type_enum.create(op.get_bind(), checkfirst=True)
    notification_channel_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    op.create_table(
        'user_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('crop_type', crop_type_enum, nullable=False),
        sa.Column('variety_name', sa.String(), nullable=False),
        sa.Column('resistance_level', sa.Integer(), nullable=False),
        sa.Column('risk_threshold', sa.Float(), nullable=False),
        sa.Column('notification_email', sa.String(), nullable=True),
        sa.Column('webhook_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('resistance_level BETWEEN 1 AND 5', name=op.f('ck_user_configs_resistance_level')),
        sa.CheckConstraint('risk_threshold BETWEEN 0 AND 100', name=op.f('ck_user_configs_risk_threshold')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_configs_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_configs'))
    )
    op.create_index(op.f('ix_user_configs_id'), 'user_configs', ['id'], unique=False)
    op.create_index('ix_user_configs_user_id_crop_type', 'user_configs', ['user_id', 'crop_type'], unique=True)

    op.create_table(
        'weather_stations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('location', Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False),
        sa.Column('elevation', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_weather_stations'))
    )
    op.create_index(op.f('ix_weather_stations_code'), 'weather_stations', ['code'], unique=True)
    op.create_index(op.f('ix_weather_stations_id'), 'weather_stations', ['id'], unique=False)
    op.create_index('ix_weather_stations_location', 'weather_stations', ['location'], postgresql_using='gist')

    op.create_table(
        'weather_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('relative_humidity', sa.Float(), nullable=True),
        sa.Column('rainfall', sa.Float(), nullable=True),
        sa.Column('leaf_wetness_duration', sa.Float(), nullable=True),
        sa.Column('wind_speed', sa.Float(), nullable=True),
        sa.Column('solar_radiation', sa.Float(), nullable=True),
        sa.CheckConstraint('relative_humidity BETWEEN 0 AND 100', name=op.f('ck_weather_data_relative_humidity')),
        sa.ForeignKeyConstraint(['station_id'], ['weather_stations.id'], name=op.f('fk_weather_data_station_id_weather_stations')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_weather_data'))
    )
    op.create_index(op.f('ix_weather_data_id'), 'weather_data', ['id'], unique=False)
    op.create_index(op.f('ix_weather_data_timestamp'), 'weather_data', ['timestamp'], unique=False)
    op.create_index('ix_weather_data_station_timestamp', 'weather_data', ['station_id', 'timestamp'], unique=True)

    op.create_table(
        'spore_sensors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('location', Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False),
        sa.Column('crop_type', crop_type_enum, nullable=False),
        sa.Column('spore_type', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_spore_sensors'))
    )
    op.create_index(op.f('ix_spore_sensors_code'), 'spore_sensors', ['code'], unique=True)
    op.create_index(op.f('ix_spore_sensors_id'), 'spore_sensors', ['id'], unique=False)
    op.create_index('ix_spore_sensors_location', 'spore_sensors', ['location'], postgresql_using='gist')

    op.create_table(
        'spore_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sensor_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('concentration', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sensor_id'], ['spore_sensors.id'], name=op.f('fk_spore_data_sensor_id_spore_sensors')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_spore_data'))
    )
    op.create_index(op.f('ix_spore_data_id'), 'spore_data', ['id'], unique=False)
    op.create_index(op.f('ix_spore_data_timestamp'), 'spore_data', ['timestamp'], unique=False)
    op.create_index('ix_spore_data_sensor_timestamp', 'spore_data', ['sensor_id', 'timestamp'], unique=True)

    op.create_table(
        'grid_cells',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grid_x', sa.Integer(), nullable=False),
        sa.Column('grid_y', sa.Integer(), nullable=False),
        sa.Column('centroid', Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False),
        sa.Column('bounds', Geometry(geometry_type='POLYGON', srid=4326, spatial_index=False), nullable=False),
        sa.Column('resolution_km', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('grid_x', 'grid_y', name='uq_grid_cells_x_y'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grid_cells'))
    )
    op.create_index(op.f('ix_grid_cells_id'), 'grid_cells', ['id'], unique=False)
    op.create_index('ix_grid_cells_centroid', 'grid_cells', ['centroid'], postgresql_using='gist')
    op.create_index('ix_grid_cells_bounds', 'grid_cells', ['bounds'], postgresql_using='gist')

    op.create_table(
        'risk_grids',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grid_id', sa.Integer(), nullable=False),
        sa.Column('forecast_date', sa.DateTime(), nullable=False),
        sa.Column('crop_type', crop_type_enum, nullable=False),
        sa.Column('risk_index', sa.Float(), nullable=False),
        sa.Column('infection_probability', sa.Float(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('risk_index BETWEEN 0 AND 100', name=op.f('ck_risk_grids_risk_index')),
        sa.ForeignKeyConstraint(['grid_id'], ['grid_cells.id'], name=op.f('fk_risk_grids_grid_id_grid_cells')),
        sa.UniqueConstraint('grid_id', 'forecast_date', 'crop_type', name='uq_risk_grids_grid_date_crop'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_risk_grids'))
    )
    op.create_index(op.f('ix_risk_grids_crop_type'), 'risk_grids', ['crop_type'], unique=False)
    op.create_index(op.f('ix_risk_grids_forecast_date'), 'risk_grids', ['forecast_date'], unique=False)
    op.create_index(op.f('ix_risk_grids_id'), 'risk_grids', ['id'], unique=False)

    op.create_table(
        'forecast_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grid_id', sa.Integer(), nullable=False),
        sa.Column('forecast_date', sa.DateTime(), nullable=False),
        sa.Column('lead_time_hours', sa.Integer(), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('humidity', sa.Float(), nullable=True),
        sa.Column('rainfall', sa.Float(), nullable=True),
        sa.Column('wind_speed', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['grid_id'], ['grid_cells.id'], name=op.f('fk_forecast_data_grid_id_grid_cells')),
        sa.UniqueConstraint('grid_id', 'forecast_date', 'lead_time_hours', name='uq_forecast_data_grid_date_lead'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_forecast_data'))
    )
    op.create_index(op.f('ix_forecast_data_forecast_date'), 'forecast_data', ['forecast_date'], unique=False)
    op.create_index(op.f('ix_forecast_data_id'), 'forecast_data', ['id'], unique=False)

    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('grid_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', alert_type_enum, nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('threshold_exceeded', sa.Float(), nullable=True),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('triggered_at', sa.DateTime(), nullable=True),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['grid_id'], ['grid_cells.id'], name=op.f('fk_alerts_grid_id_grid_cells')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_alerts_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_alerts'))
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)

    op.create_table(
        'notification_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('channel', notification_channel_enum, nullable=False),
        sa.Column('recipient', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], name=op.f('fk_notification_logs_alert_id_alerts')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_logs'))
    )
    op.create_index(op.f('ix_notification_logs_id'), 'notification_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notification_logs_id'), table_name='notification_logs')
    op.drop_table('notification_logs')

    op.drop_index(op.f('ix_alerts_id'), table_name='alerts')
    op.drop_table('alerts')

    op.drop_index(op.f('ix_forecast_data_id'), table_name='forecast_data')
    op.drop_index(op.f('ix_forecast_data_forecast_date'), table_name='forecast_data')
    op.drop_table('forecast_data')

    op.drop_index(op.f('ix_risk_grids_id'), table_name='risk_grids')
    op.drop_index(op.f('ix_risk_grids_forecast_date'), table_name='risk_grids')
    op.drop_index(op.f('ix_risk_grids_crop_type'), table_name='risk_grids')
    op.drop_table('risk_grids')

    op.drop_index('ix_grid_cells_bounds', table_name='grid_cells', postgresql_using='gist')
    op.drop_index('ix_grid_cells_centroid', table_name='grid_cells', postgresql_using='gist')
    op.drop_index(op.f('ix_grid_cells_id'), table_name='grid_cells')
    op.drop_table('grid_cells')

    op.drop_index('ix_spore_data_sensor_timestamp', table_name='spore_data')
    op.drop_index(op.f('ix_spore_data_timestamp'), table_name='spore_data')
    op.drop_index(op.f('ix_spore_data_id'), table_name='spore_data')
    op.drop_table('spore_data')

    op.drop_index('ix_spore_sensors_location', table_name='spore_sensors', postgresql_using='gist')
    op.drop_index(op.f('ix_spore_sensors_id'), table_name='spore_sensors')
    op.drop_index(op.f('ix_spore_sensors_code'), table_name='spore_sensors')
    op.drop_table('spore_sensors')

    op.drop_index('ix_weather_data_station_timestamp', table_name='weather_data')
    op.drop_index(op.f('ix_weather_data_timestamp'), table_name='weather_data')
    op.drop_index(op.f('ix_weather_data_id'), table_name='weather_data')
    op.drop_table('weather_data')

    op.drop_index('ix_weather_stations_location', table_name='weather_stations', postgresql_using='gist')
    op.drop_index(op.f('ix_weather_stations_id'), table_name='weather_stations')
    op.drop_index(op.f('ix_weather_stations_code'), table_name='weather_stations')
    op.drop_table('weather_stations')

    op.drop_index('ix_user_configs_user_id_crop_type', table_name='user_configs')
    op.drop_index(op.f('ix_user_configs_id'), table_name='user_configs')
    op.drop_table('user_configs')

    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    notification_channel_enum.drop(op.get_bind(), checkfirst=True)
    alert_type_enum.drop(op.get_bind(), checkfirst=True)
    crop_type_enum.drop(op.get_bind(), checkfirst=True)
