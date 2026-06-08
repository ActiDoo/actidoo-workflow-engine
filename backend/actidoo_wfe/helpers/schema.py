# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

PaginatedDataItemType = TypeVar("PaginatedDataItemType")


class PaginatedDataSchema(BaseModel, Generic[PaginatedDataItemType]):
    """A generic Pydantic API Scheme for paginated results"""

    ITEMS: List[PaginatedDataItemType]
    COUNT: int
    # Keyset cursor for the next page; null when none / in offset mode.
    NEXT_CURSOR: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
