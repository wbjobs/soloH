from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    Enum,
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape

from app.db.base import Base


class CropType(str, PyEnum):
    WHEAT = "wheat"
    POTATO = "potato"
    CORN = "corn"
    RICE = "rice"


class AlertType(str, PyEnum):
    RISK = "risk"
    WARNING = "warning"


class NotificationChannel(str, PyEnum):
    EMAIL = "email"
    WEBHOOK = "webhook"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    configs = relationship("UserConfig", back_populates="user")
    alerts = relationship("Alert", back_populates="user")


class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crop_type = Column(Enum(CropType), nullable=False)
    variety_name = Column(String, nullable=False)
    resistance_level = Column(Integer, CheckConstraint("resistance_level >= 1", name="ck_user_configs_resistance_level_min"), nullable=False)
    risk_threshold = Column(Float, CheckConstraint("risk_threshold BETWEEN 0 AND 100", name="ck_user_configs_risk_threshold"), nullable=False)
    notification_email = Column(String)
    webhook_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="configs")

    __table_args__ = (
        Index("ix_user_configs_user_id_crop_type", "user_id", "crop_type", unique=True),
    )


class WeatherStation(Base):
    __tablename__ = "weather_stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    elevation = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    weather_data = relationship("WeatherData", back_populates="station")

    __table_args__ = (
        Index("ix_weather_stations_location", "location", postgresql_using="gist"),
    )

    @property
    def latitude(self):
        if self.location:
            return to_shape(self.location).y
        return None

    @property
    def longitude(self):
        if self.location:
            return to_shape(self.location).x
        return None


class WeatherData(Base):
    __tablename__ = "weather_data"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("weather_stations.id"), nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    temperature = Column(Float)
    relative_humidity = Column(Float, CheckConstraint("relative_humidity BETWEEN 0 AND 100", name="ck_weather_data_relative_humidity"))
    rainfall = Column(Float)
    leaf_wetness_duration = Column(Float)
    wind_speed = Column(Float)
    solar_radiation = Column(Float)

    station = relationship("WeatherStation", back_populates="weather_data")

    __table_args__ = (
        Index("ix_weather_data_station_timestamp", "station_id", "timestamp", unique=True),
    )


class SporeSensor(Base):
    __tablename__ = "spore_sensors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    crop_type = Column(Enum(CropType), nullable=False)
    spore_type = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    spore_data = relationship("SporeData", back_populates="sensor")

    __table_args__ = (
        Index("ix_spore_sensors_location", "location", postgresql_using="gist"),
    )

    @property
    def latitude(self):
        if self.location:
            return to_shape(self.location).y
        return None

    @property
    def longitude(self):
        if self.location:
            return to_shape(self.location).x
        return None


class SporeData(Base):
    __tablename__ = "spore_data"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("spore_sensors.id"), nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    concentration = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sensor = relationship("SporeSensor", back_populates="spore_data")

    __table_args__ = (
        Index("ix_spore_data_sensor_timestamp", "sensor_id", "timestamp", unique=True),
    )


class GridCell(Base):
    __tablename__ = "grid_cells"

    id = Column(Integer, primary_key=True, index=True)
    grid_x = Column(Integer, nullable=False)
    grid_y = Column(Integer, nullable=False)
    centroid = Column(Geometry("POINT", srid=4326), nullable=False)
    bounds = Column(Geometry("POLYGON", srid=4326), nullable=False)
    resolution_km = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    risk_grids = relationship("RiskGrid", back_populates="grid_cell")
    forecast_data = relationship("ForecastData", back_populates="grid_cell")
    alerts = relationship("Alert", back_populates="grid_cell")

    __table_args__ = (
        UniqueConstraint("grid_x", "grid_y", name="uq_grid_cells_x_y"),
        Index("ix_grid_cells_centroid", "centroid", postgresql_using="gist"),
        Index("ix_grid_cells_bounds", "bounds", postgresql_using="gist"),
    )

    @property
    def lat(self):
        if self.centroid:
            return to_shape(self.centroid).y
        return None

    @property
    def lon(self):
        if self.centroid:
            return to_shape(self.centroid).x
        return None


class RiskGrid(Base):
    __tablename__ = "risk_grids"

    id = Column(Integer, primary_key=True, index=True)
    grid_id = Column(Integer, ForeignKey("grid_cells.id"), nullable=False)
    forecast_date = Column(DateTime, index=True, nullable=False)
    crop_type = Column(Enum(CropType), index=True, nullable=False)
    risk_index = Column(Float, CheckConstraint("risk_index BETWEEN 0 AND 100", name="ck_risk_grids_risk_index"), nullable=False)
    infection_probability = Column(Float)
    model_version = Column(String)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    grid_cell = relationship("GridCell", back_populates="risk_grids")

    __table_args__ = (
        UniqueConstraint(
            "grid_id", "forecast_date", "crop_type",
            name="uq_risk_grids_grid_date_crop"
        ),
    )


class ForecastData(Base):
    __tablename__ = "forecast_data"

    id = Column(Integer, primary_key=True, index=True)
    grid_id = Column(Integer, ForeignKey("grid_cells.id"), nullable=False)
    forecast_date = Column(DateTime, index=True, nullable=False)
    lead_time_hours = Column(Integer, nullable=False)
    temperature = Column(Float)
    humidity = Column(Float)
    rainfall = Column(Float)
    wind_speed = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    grid_cell = relationship("GridCell", back_populates="forecast_data")

    __table_args__ = (
        UniqueConstraint(
            "grid_id", "forecast_date", "lead_time_hours",
            name="uq_forecast_data_grid_date_lead"
        ),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    grid_id = Column(Integer, ForeignKey("grid_cells.id"), nullable=False)
    alert_type = Column(Enum(AlertType), nullable=False)
    severity = Column(String, nullable=False)
    threshold_exceeded = Column(Float)
    message = Column(String, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    notified_at = Column(DateTime)
    is_read = Column(Boolean, default=False)

    user = relationship("User", back_populates="alerts")
    grid_cell = relationship("GridCell", back_populates="alerts")
    notification_logs = relationship("NotificationLog", back_populates="alert")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    recipient = Column(String, nullable=False)
    status = Column(String, nullable=False)
    error_message = Column(String)
    sent_at = Column(DateTime, default=datetime.utcnow)

    alert = relationship("Alert", back_populates="notification_logs")


class RiskAttribution(Base):
    __tablename__ = "risk_attributions"

    id = Column(Integer, primary_key=True, index=True)
    grid_id = Column(Integer, ForeignKey("grid_cells.id"), nullable=False)
    forecast_date = Column(DateTime, index=True, nullable=False)
    crop_type = Column(Enum(CropType), index=True, nullable=False)
    risk_index = Column(Float, nullable=False)
    base_value = Column(Float, nullable=False)

    shap_temperature = Column(Float, nullable=False)
    shap_humidity = Column(Float, nullable=False)
    shap_leaf_wetness = Column(Float, nullable=False)
    shap_spore_concentration = Column(Float, nullable=False)
    shap_resistance = Column(Float, nullable=False)

    dominant_factor = Column(String, nullable=False)
    dominant_factor_contribution = Column(Float, nullable=False)

    method = Column(String, default="shap")
    model_version = Column(String)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    grid_cell = relationship("GridCell")

    __table_args__ = (
        UniqueConstraint(
            "grid_id", "forecast_date", "crop_type",
            name="uq_risk_attributions_grid_date_crop"
        ),
    )


class DroneFlight(Base):
    __tablename__ = "drone_flights"

    id = Column(Integer, primary_key=True, index=True)
    flight_code = Column(String, unique=True, index=True, nullable=False)
    drone_id = Column(String, nullable=False)
    pilot_name = Column(String)
    crop_type = Column(Enum(CropType), nullable=False)
    flight_date = Column(DateTime, index=True, nullable=False)
    area_covered_ha = Column(Float)
    altitude_m = Column(Float)
    overlap = Column(Float)
    resolution_cm_px = Column(Float)
    bands = Column(String)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    images = relationship("DroneImage", back_populates="flight")
    detections = relationship("DroneDiseaseDetection", back_populates="flight")


class DroneImage(Base):
    __tablename__ = "drone_images"

    id = Column(Integer, primary_key=True, index=True)
    flight_id = Column(Integer, ForeignKey("drone_flights.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    image_type = Column(String, nullable=False)
    center_location = Column(Geometry("POINT", srid=4326))
    corners = Column(Geometry("POLYGON", srid=4326))
    capture_time = Column(DateTime)
    band_count = Column(Integer)
    bands_metadata = Column(String)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    flight = relationship("DroneFlight", back_populates="images")

    __table_args__ = (
        Index("ix_drone_images_center", "center_location", postgresql_using="gist"),
    )


class DroneDiseaseDetection(Base):
    __tablename__ = "drone_disease_detections"

    id = Column(Integer, primary_key=True, index=True)
    flight_id = Column(Integer, ForeignKey("drone_flights.id"), nullable=False)
    image_id = Column(Integer, ForeignKey("drone_images.id"))
    grid_id = Column(Integer, ForeignKey("grid_cells.id"))
    crop_type = Column(Enum(CropType), nullable=False)
    disease_name = Column(String, nullable=False)
    detection_confidence = Column(Float, CheckConstraint("detection_confidence BETWEEN 0 AND 1", name="ck_drone_detections_confidence"))
    severity = Column(Float, CheckConstraint("severity BETWEEN 0 AND 100", name="ck_drone_detections_severity"))
    area_affected_m2 = Column(Float)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    polygon = Column(Geometry("POLYGON", srid=4326))
    ndvi_value = Column(Float)
    ndre_value = Column(Float)
    gndvi_value = Column(Float)
    pri_value = Column(Float)
    fused_risk_boost = Column(Float, default=1.0)
    model_used = Column(String)
    detection_time = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)
    notes = Column(String)

    flight = relationship("DroneFlight", back_populates="detections")
    image = relationship("DroneImage")
    grid_cell = relationship("GridCell")

    __table_args__ = (
        Index("ix_drone_detections_location", "location", postgresql_using="gist"),
        Index("ix_drone_detections_grid", "grid_id"),
    )


class PesticideProduct(Base):
    __tablename__ = "pesticide_products"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, nullable=False)
    registration_number = Column(String, unique=True, nullable=False)
    active_ingredient = Column(String, nullable=False)
    formulation = Column(String)
    concentration = Column(String)
    target_crops = Column(String)
    target_diseases = Column(String)
    recommended_dosage = Column(String)
    dosage_ha = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    pre_harvest_interval_days = Column(Integer)
    safety_interval_days = Column(Integer)
    rainfastness_hours = Column(Integer)
    price_per_unit = Column(Float)
    efficacy_rating = Column(Float, CheckConstraint("efficacy_rating BETWEEN 0 AND 100", name="ck_pesticide_products_efficacy_rating"))
    resistance_risk = Column(String)
    restricted_use = Column(Boolean, default=False)
    notes = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SprayRecommendation(Base):
    __tablename__ = "spray_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    grid_id = Column(Integer, ForeignKey("grid_cells.id"), nullable=False)
    forecast_date = Column(DateTime, index=True, nullable=False)
    crop_type = Column(Enum(CropType), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))

    risk_index = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    drone_detected_severity = Column(Float)
    economic_threshold = Column(Float, nullable=False)
    spray_needed = Column(Boolean, nullable=False)
    urgency = Column(String, nullable=False)

    recommended_product_id = Column(Integer, ForeignKey("pesticide_products.id"))
    alternative_product_id = Column(Integer, ForeignKey("pesticide_products.id"))
    application_rate = Column(Float)
    application_rate_unit = Column(String)
    total_area_ha = Column(Float)
    total_product_needed = Column(Float)
    estimated_cost = Column(Float)

    application_timing = Column(String)
    application_method = Column(String)
    pre_harvest_interval = Column(Integer)
    reentry_interval = Column(Integer)
    weather_conditions = Column(String)

    expected_efficacy = Column(Float)
    resistance_management = Column(String)
    environmental_impact = Column(String)
    safety_precautions = Column(String)

    generated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    is_applied = Column(Boolean, default=False)
    applied_at = Column(DateTime)
    notes = Column(String)

    grid_cell = relationship("GridCell")
    user = relationship("User")
    recommended_product = relationship("PesticideProduct", foreign_keys=[recommended_product_id])
    alternative_product = relationship("PesticideProduct", foreign_keys=[alternative_product_id])

    __table_args__ = (
        UniqueConstraint(
            "grid_id", "forecast_date", "crop_type",
            name="uq_spray_recs_grid_date_crop"
        ),
    )
