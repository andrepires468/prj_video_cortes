from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Double,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.schemas import JobStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


_JOB_STATUS = Enum(
    JobStatus,
    native_enum=False,
    values_callable=lambda items: [item.value for item in items],
    length=16,
)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    downloads: Mapped[list[Download]] = relationship(back_populates="usuario")
    cortes: Mapped[list[Corte]] = relationship(back_populates="usuario")


class Download(Base):
    __tablename__ = "downloads"
    __table_args__ = (
        Index("ix_downloads_usuario_criado", "usuario_id", "criado_em"),
        Index("ix_downloads_status", "status"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    url_origem: Mapped[str] = mapped_column(String(2048), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumb_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        _JOB_STATUS,
        nullable=False,
        default=JobStatus.queued,
    )
    progress: Mapped[float] = mapped_column(
        Numeric(5, 1, asdecimal=False),
        nullable=False,
        default=0.0,
    )
    mensagem: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duracao_seg: Mapped[float | None] = mapped_column(Double, nullable=True)
    largura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    altura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    usuario: Mapped[Usuario] = relationship(back_populates="downloads")
    cortes: Mapped[list[Corte]] = relationship(
        back_populates="download",
        cascade="all, delete-orphan",
    )


class Corte(Base):
    __tablename__ = "cortes"
    __table_args__ = (
        Index("ix_cortes_download_id", "download_id"),
        Index("ix_cortes_usuario_criado", "usuario_id", "criado_em"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    download_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("downloads.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    corte_origem_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("cortes.id", ondelete="SET NULL"),
        nullable=True,
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumb_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inicio_seg: Mapped[float] = mapped_column(Double, nullable=False)
    fim_seg: Mapped[float] = mapped_column(Double, nullable=False)
    velocidade: Mapped[float] = mapped_column(
        Numeric(4, 2, asdecimal=False),
        nullable=False,
        default=1.0,
    )
    status: Mapped[JobStatus] = mapped_column(
        _JOB_STATUS,
        nullable=False,
        default=JobStatus.queued,
    )
    progress: Mapped[float] = mapped_column(
        Numeric(5, 1, asdecimal=False),
        nullable=False,
        default=0.0,
    )
    mensagem: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    download: Mapped[Download] = relationship(back_populates="cortes")
    usuario: Mapped[Usuario] = relationship(back_populates="cortes")
    corte_origem: Mapped[Corte | None] = relationship(
        remote_side="Corte.id",
        foreign_keys=[corte_origem_id],
    )
