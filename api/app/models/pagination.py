from __future__ import annotations

from typing import Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Contrato padrão de listas paginadas (`items` + `pagination`)."""

    items: list[T]
    pagination: PaginationMeta


def normalize_pagination(
    page: int,
    per_page: int,
    total: int,
) -> tuple[int, int, int]:
    per_page = min(max(int(per_page or DEFAULT_PER_PAGE), 1), MAX_PER_PAGE)
    total = max(int(total), 0)
    pages = max((total + per_page - 1) // per_page, 1) if total else 1
    page = min(max(int(page or DEFAULT_PAGE), 1), pages)
    return page, per_page, pages


def build_pagination(total: int, page: int = DEFAULT_PAGE, per_page: int = DEFAULT_PER_PAGE) -> PaginationMeta:
    page, per_page, pages = normalize_pagination(page, per_page, total)
    return PaginationMeta(
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )


def pagination_for_items(items: Sequence[object], page: int = DEFAULT_PAGE, per_page: int | None = None) -> PaginationMeta:
    total = len(items)
    return build_pagination(total, page, per_page if per_page is not None else max(total, 1))


def paginate_query(query, page: int = DEFAULT_PAGE, per_page: int = DEFAULT_PER_PAGE):
    """Aplica COUNT + OFFSET/LIMIT em uma query SQLAlchemy e devolve (linhas, meta)."""
    total = int(query.order_by(None).count())
    page, per_page, _pages = normalize_pagination(page, per_page, total)
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return rows, build_pagination(total, page, per_page)


def PageQuery(default: int = DEFAULT_PAGE):
    return Query(default, ge=1, description="Página (1-based)")


def PerPageQuery(default: int = DEFAULT_PER_PAGE):
    return Query(default, ge=1, le=MAX_PER_PAGE, description="Itens por página")


class PaginationParams(BaseModel):
    page: int = Field(DEFAULT_PAGE, ge=1)
    per_page: int = Field(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE)
