"""schema inicial: usuarios, downloads, cortes

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_KW = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", mysql.CHAR(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("criado_em", mysql.DATETIME(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.Column("atualizado_em", mysql.DATETIME(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
        **_TABLE_KW,
    )

    op.create_table(
        "downloads",
        sa.Column("id", mysql.CHAR(length=36), nullable=False),
        sa.Column("usuario_id", mysql.CHAR(length=36), nullable=False),
        sa.Column("url_origem", sa.String(length=2048), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("thumb_key", sa.String(length=512), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("progress", sa.Numeric(precision=5, scale=1), server_default="0.0", nullable=False),
        sa.Column("mensagem", sa.String(length=255), nullable=True),
        sa.Column("tamanho_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duracao_seg", sa.Double(), nullable=True),
        sa.Column("largura", sa.Integer(), nullable=True),
        sa.Column("altura", sa.Integer(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("criado_em", mysql.DATETIME(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.Column("atualizado_em", mysql.DATETIME(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], name="fk_downloads_usuario_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        **_TABLE_KW,
    )
    op.create_index("ix_downloads_usuario_criado", "downloads", ["usuario_id", "criado_em"])
    op.create_index("ix_downloads_status", "downloads", ["status"])

    op.create_table(
        "cortes",
        sa.Column("id", mysql.CHAR(length=36), nullable=False),
        sa.Column("download_id", mysql.CHAR(length=36), nullable=False),
        sa.Column("usuario_id", mysql.CHAR(length=36), nullable=False),
        sa.Column("corte_origem_id", mysql.CHAR(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("thumb_key", sa.String(length=512), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("inicio_seg", sa.Double(), nullable=False),
        sa.Column("fim_seg", sa.Double(), nullable=False),
        sa.Column("velocidade", sa.Numeric(precision=4, scale=2), server_default="1.00", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("progress", sa.Numeric(precision=5, scale=1), server_default="0.0", nullable=False),
        sa.Column("mensagem", sa.String(length=255), nullable=True),
        sa.Column("tamanho_bytes", sa.BigInteger(), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("criado_em", mysql.DATETIME(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.Column("atualizado_em", mysql.DATETIME(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False),
        sa.ForeignKeyConstraint(["download_id"], ["downloads.id"], name="fk_cortes_download_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], name="fk_cortes_usuario_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["corte_origem_id"], ["cortes.id"], name="fk_cortes_corte_origem_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        **_TABLE_KW,
    )
    op.create_index("ix_cortes_download_id", "cortes", ["download_id"])
    op.create_index("ix_cortes_usuario_criado", "cortes", ["usuario_id", "criado_em"])


def downgrade() -> None:
    op.drop_index("ix_cortes_usuario_criado", table_name="cortes")
    op.drop_index("ix_cortes_download_id", table_name="cortes")
    op.drop_table("cortes")
    op.drop_index("ix_downloads_status", table_name="downloads")
    op.drop_index("ix_downloads_usuario_criado", table_name="downloads")
    op.drop_table("downloads")
    op.drop_table("usuarios")
