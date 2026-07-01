# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

PaginatedDataItemType = TypeVar("PaginatedDataItemType")


class PaginatedDataSchema(BaseModel, Generic[PaginatedDataItemType]):
    """A generic Pydantic API Scheme for offset-paginated results"""

    ITEMS: List[PaginatedDataItemType]
    COUNT: int

    model_config = ConfigDict(from_attributes=True)


class CursorPaginatedDataSchema(BaseModel, Generic[PaginatedDataItemType]):
    """A generic Pydantic API Scheme for keyset/cursor-paginated results.

    Deliberately separate from :class:`PaginatedDataSchema`: a cursor page has a
    next-page token but no total count — an endless list has no use for one, and
    computing it would run the full visibility query on every scroll fetch.
    """

    ITEMS: List[PaginatedDataItemType]
    # Keyset cursor for the next page; null when this is the last page.
    NEXT_CURSOR: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
