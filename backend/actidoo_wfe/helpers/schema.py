# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from typing import Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict

PaginatedDataItemType = TypeVar("PaginatedDataItemType")


class PaginatedDataSchema(BaseModel, Generic[PaginatedDataItemType]):
    """A generic Pydantic API Scheme for paginated results"""

    ITEMS: List[PaginatedDataItemType]
    COUNT: int

    model_config = ConfigDict(from_attributes=True)
