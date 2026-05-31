from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    BigInteger,
    JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional

from app.core.database import Base


class Block(Base):
    __tablename__ = "blocks"

    block_height: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    block_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    block_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True
    )

    tx_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    total_btc: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0
    )

    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="block",
        cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    txid: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        index=True
    )

    block_height: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("blocks.block_height", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    block_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    total_input: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0
    )

    total_output: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0
    )

    fee: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0
    )

    input_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    output_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    is_coinbase: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    block: Mapped["Block"] = relationship(
        "Block",
        back_populates="transactions"
    )

    inputs: Mapped[List["TxInput"]] = relationship(
        "TxInput",
        back_populates="transaction",
        cascade="all, delete-orphan",
        foreign_keys="TxInput.txid"
    )

    outputs: Mapped[List["TxOutput"]] = relationship(
        "TxOutput",
        back_populates="transaction",
        cascade="all, delete-orphan"
    )

    graph_edges: Mapped[List["GraphEdge"]] = relationship(
        "GraphEdge",
        back_populates="transaction",
        cascade="all, delete-orphan"
    )

    suspicious_patterns: Mapped[List["SuspiciousPattern"]] = relationship(
        "SuspiciousPattern",
        back_populates="transaction"
    )


class TxInput(Base):
    __tablename__ = "tx_inputs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    txid: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("transactions.txid", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    vout: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    prev_txid: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True
    )

    prev_vout: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    address: Mapped[str] = mapped_column(
        String,
        ForeignKey("addresses.address", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    value: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="inputs",
        foreign_keys=[txid]
    )

    address_obj: Mapped["Address"] = relationship(
        "Address",
        back_populates="inputs"
    )

    __table_args__ = (
        Index("idx_tx_inputs_prev", "prev_txid", "prev_vout"),
    )


class TxOutput(Base):
    __tablename__ = "tx_outputs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    txid: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("transactions.txid", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    vout: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    address: Mapped[str] = mapped_column(
        String,
        ForeignKey("addresses.address", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    value: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False
    )

    script_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    is_spent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="outputs"
    )

    address_obj: Mapped["Address"] = relationship(
        "Address",
        back_populates="outputs"
    )

    __table_args__ = (
        Index("idx_tx_outputs_unspent", "address", "is_spent", postgresql_where=("is_spent = false")),
    )


class Address(Base):
    __tablename__ = "addresses"

    address: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True
    )

    first_seen: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    last_seen: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    total_received: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0
    )

    total_sent: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0
    )

    balance: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        default=0,
        index=True
    )

    tx_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    cluster_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("address_clusters.cluster_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    suspicious_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        index=True
    )

    risk_factors: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )

    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )

    inputs: Mapped[List["TxInput"]] = relationship(
        "TxInput",
        back_populates="address_obj",
        foreign_keys="TxInput.address"
    )

    outputs: Mapped[List["TxOutput"]] = relationship(
        "TxOutput",
        back_populates="address_obj",
        foreign_keys="TxOutput.address"
    )

    cluster: Mapped[Optional["AddressCluster"]] = relationship(
        "AddressCluster",
        back_populates="addresses"
    )

    cluster_memberships: Mapped[List["ClusterMember"]] = relationship(
        "ClusterMember",
        back_populates="address_obj",
        cascade="all, delete-orphan"
    )

    suspicious_patterns: Mapped[List["SuspiciousPattern"]] = relationship(
        "SuspiciousPattern",
        back_populates="address_obj"
    )

    outgoing_edges: Mapped[List["GraphEdge"]] = relationship(
        "GraphEdge",
        back_populates="from_address_obj",
        foreign_keys="GraphEdge.from_address"
    )

    incoming_edges: Mapped[List["GraphEdge"]] = relationship(
        "GraphEdge",
        back_populates="to_address_obj",
        foreign_keys="GraphEdge.to_address"
    )

    __table_args__ = (
        Index("idx_addresses_risk", "suspicious_score"),
        Index("idx_addresses_balance", "balance"),
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    from_address: Mapped[str] = mapped_column(
        String,
        ForeignKey("addresses.address", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    to_address: Mapped[str] = mapped_column(
        String,
        ForeignKey("addresses.address", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    txid: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("transactions.txid", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    value: Mapped[float] = mapped_column(
        Numeric(28, 8),
        nullable=False,
        index=True
    )

    block_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    from_address_obj: Mapped["Address"] = relationship(
        "Address",
        back_populates="outgoing_edges",
        foreign_keys=[from_address]
    )

    to_address_obj: Mapped["Address"] = relationship(
        "Address",
        back_populates="incoming_edges",
        foreign_keys=[to_address]
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="graph_edges"
    )

    __table_args__ = (
        Index("idx_edges_value", "value"),
    )
