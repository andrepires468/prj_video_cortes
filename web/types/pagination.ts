export interface PaginationMeta {
  page: number
  per_page: number
  total: number
  pages: number
  has_next: boolean
  has_prev: boolean
}

export interface Paginated<T> {
  items: T[]
  pagination: PaginationMeta
}

export const DEFAULT_PER_PAGE = 20
