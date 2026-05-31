from sqlalchemy import (
    Integer,
    String,
    Numeric,
    DateTime,
    Text,
    ForeignKey,
    Index,
    BigInteger,
    JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional

from app.core.database import Base


class AddressCluster(Base):
    __tablename__ = "address_clusters"

    cluster_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True
    )

    heuristic: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    confidence: Mapped[float] = mapped_column(
        Numeric(5, 4),
        nullable=False
    )

    size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    total_value: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0
    )

    addresses: Mapped[List["Address"]] = relationship(
        "Address",
        back_populates="cluster",
        foreign_keys="Address.cluster_id"
    )

    members: Mapped[List["ClusterMember"]] = relationship(
        "ClusterMember",
        back_populates="cluster",
        cascade="all, delete-orphan"
    )


class ClusterMember(Base):
    __tablename__ = "cluster_members"

    cluster_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("address_clusters.cluster_id", ondelete="CASCADE"),
        primary_key=True
    )

    address: Mapped[str] = mapped_column(
        String,
        ForeignKey("addresses.address", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )

    joined_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default="NOW()",
        nullable=False
    )

    cluster: Mapped["AddressCluster"] = relationship(
        "AddressCluster",
        back_populates="members"
    )

    address_obj: Mapped["Address"] = relationship(
        "Address",
        back_populates="cluster_memberships"
    )


class SuspiciousPattern(Base):
    __tablename__ = "suspicious_patterns"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    pattern_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )

    confidence: Mapped[float] = mapped_column(
        Numeric(5, 4),
        nullable=False
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    evidence: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True
    )

    address: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("addresses.address", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    txid: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("transactions.txid", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    detected_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default="NOW()",
        nullable=False,
        index=True
    )

    address_obj: Mapped[Optional["Address"]] = relationship(
        "Address",
        back_populates="suspicious_patterns"
    )

    transaction: Mapped[Optional["Transaction"]] = relationship(
        "Transaction",
        back_populates="suspicious_patterns"
    )

    __table_args__ = (
        Index("idx_patterns_detected", "detected_at"),
    )
