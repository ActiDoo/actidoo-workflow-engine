# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import dataclasses
import datetime
import logging
import uuid
from collections.abc import Iterable
from enum import Enum
from typing import Annotated, Any, List, Optional

import pydantic.v1
from dateutil import parser
from fastapi import Query
from sqlalchemy import ScalarResult, Select, and_, func, or_, select
from sqlalchemy.orm import Session

from actidoo_wfe.database import eilike, search_uuid_by_prefix

log = logging.getLogger(__name__)

_member_seperator: str = "___"


def encode_cursor(id_: uuid.UUID) -> str:
    """Encode a keyset cursor token from a row id."""
    return id_.hex


def decode_cursor(token: Optional[str]) -> Optional[uuid.UUID]:
    """Parse a cursor token into a row id; None for a missing/malformed token."""
    if not token:
        return None
    try:
        return uuid.UUID(hex=token)
    except (ValueError, TypeError):
        return None


def build_field_name(*parts):
    return _member_seperator.join(parts)


def get_db_field(field_name, query: Select, field_to_dbfield_map: dict):
    return field_to_dbfield_map.get(field_name) or getattr(
        query.exported_columns,
        field_name,
    )


class SortingDirectionEnum(str, Enum):
    asc = "asc"
    desc = "desc"


@dataclasses.dataclass
class FilterField:
    name: str

    def add_GET_parameters(self, schema_query_params):
        raise NotImplementedError()

    def add_database_query_parameters(
        self,
        query: Select,
        request_params: "BffTableQuerySchemaBase",
        field_to_dbfield_map: dict,
    ):
        raise NotImplementedError()

    def get_database_global_search_query_clause(
        self,
        query: Select,
        search: str,
        field_to_dbfield_map: dict,
    ):
        raise NotImplementedError()


@dataclasses.dataclass
class IntegerSearchFilterField(FilterField):
    def add_GET_parameters(self, schema_query_params):
        schema_query_params["f_" + self.name + "_geq"] = (Optional[int], None)
        schema_query_params["f_" + self.name + "_leq"] = (Optional[int], None)
        schema_query_params["f_" + self.name + "_eq"] = (Optional[int], None)

    def add_database_query_parameters(
        self,
        query: Select,
        request_params: "BffTableQuerySchemaBase",
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        from_filter = getattr(request_params, "f_" + self.name + "_geq", None)
        to_filter = getattr(request_params, "f_" + self.name + "_leq", None)
        eq_filter = getattr(request_params, "f_" + self.name + "_eq", None)

        if from_filter:
            query = query.where(dbfield >= from_filter)

        if to_filter:
            query = query.where(dbfield <= to_filter)

        if eq_filter:
            query = query.where(dbfield == eq_filter)

        return query

    def get_database_global_search_query_clause(
        self,
        query: Select,
        search: str,
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        clause = False

        if search:
            try:
                searchint = int(search)
            except Exception:
                log.debug(f"Global search {search} could not be parsed as int")
            else:
                clause = and_(dbfield == searchint)

        return clause


@dataclasses.dataclass
class UUidSearchFilterField(FilterField):
    def add_GET_parameters(self, schema_query_params):
        schema_query_params["f_" + self.name] = (Optional[str], None)

    def add_database_query_parameters(
        self,
        query: Select,
        request_params: "BffTableQuerySchemaBase",
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        search_prefix = getattr(request_params, "f_" + self.name, None)

        if search_prefix is not None:
            query = query.where(search_uuid_by_prefix(dbfield, search_prefix))

        return query

    def get_database_global_search_query_clause(
        self,
        query: Select,
        search: str,
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        clause = False

        if search:
            clause = and_(search_uuid_by_prefix(dbfield, search))

        return clause


@dataclasses.dataclass
class TextSearchFilterField(FilterField):
    def add_GET_parameters(self, schema_query_params):
        schema_query_params["f_" + self.name] = (Optional[str], None)

    def add_database_query_parameters(
        self,
        query: Select,
        request_params: "BffTableQuerySchemaBase",
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        if getattr(request_params, "f_" + self.name, None) is not None:
            query = query.where(
                eilike(dbfield, getattr(request_params, "f_" + self.name)),
            )

        return query

    def get_database_global_search_query_clause(
        self,
        query: Select,
        search: str,
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        clause = False

        if search:
            clause = and_(eilike(dbfield, search))

        return clause


@dataclasses.dataclass
class DatetimeSearchFilterField(FilterField):
    def add_GET_parameters(self, schema_query_params):
        schema_query_params["f_" + self.name + "_eq"] = (Optional[str], None)

    def add_database_query_parameters(
        self,
        query: Select,
        request_params: "BffTableQuerySchemaBase",
        field_to_dbfield_map: dict,
    ):
        eq_filter = getattr(request_params, "f_" + self.name + "_eq", None)

        if eq_filter:
            search_clause = self.get_database_global_search_query_clause(
                query=query,
                search=eq_filter,
                field_to_dbfield_map=field_to_dbfield_map,
            )
            if search_clause is not None:
                query = query.filter(search_clause)

        return query

    def get_database_global_search_query_clause(
        self,
        query: Select,
        search: str,
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        clause = False

        if search:
            try:
                if len(search) <= 10:  # datum
                    dtstart = parser.parse(search)
                    dtend = dtstart + datetime.timedelta(days=1)
                else:  # datetime
                    dtstart = parser.parse(search).replace(microsecond=0)
                    dtend = dtstart + datetime.timedelta(seconds=1)

                clause = and_(dbfield >= dtstart, dbfield < dtend)
            except parser.ParserError:
                log.debug(f"Global search {search} could not be parsed as date")
            except Exception:
                log.exception(
                    f"Global search {search} raised an unexpected error during date parsing",
                )

        return clause


@dataclasses.dataclass
class BooleanFilterField(FilterField):
    default: Optional[bool] = None

    def add_GET_parameters(self, schema_query_params):
        schema_query_params["f_" + self.name] = (Optional[bool], self.default)

    def add_database_query_parameters(
        self,
        query: Select,
        request_params: "BffTableQuerySchemaBase",
        field_to_dbfield_map: dict,
    ):
        dbfield = get_db_field(
            field_name=self.name,
            field_to_dbfield_map=field_to_dbfield_map,
            query=query,
        )

        req_value = getattr(request_params, "f_" + self.name, None)

        if req_value is not None:
            query = query.where(dbfield == getattr(request_params, "f_" + self.name))

        return query

    def get_database_global_search_query_clause(
        self,
        query: Select,
        search: str,
        field_to_dbfield_map: dict,
    ):
        return False


class BffTableQuerySchemaBase(pydantic.v1.BaseModel):
    def get_offset(self):
        return get_min_max(
            getattr(self, "offset", None),
            maxv=9999999,
            default=0,
            minv=0,
        )

    def get_limit(self):
        return get_min_max(getattr(self, "limit", None), maxv=200, default=100, minv=1)

    def get_cursor(self) -> Optional[uuid.UUID]:
        return decode_cursor(getattr(self, "cursor", None))

    def get_filter_fields(self) -> List[FilterField]:
        raise NotImplementedError()


@dataclasses.dataclass
class PaginatedData:
    items: list
    count: int


@dataclasses.dataclass
class CursorPaginatedData(PaginatedData):
    next_cursor: Optional[str] = None


class BFFTable:
    """
    A class to encapsulate the functionality for querying a database table through a Backend-For-Frontend (BFF) pattern.

    This class manages the preparation and execution of SQLAlchemy queries based on incoming request parameters, including
    sorting, filtering, and pagination. It relies on specific filter fields to apply constraints to the queries and can
    apply global search functionality.

    Attributes:
        db (Session): The database session used to execute queries.
        request_params (BffTableQuerySchemaBase): The parameters from the request that influence the query.
        query (Select): The SQLAlchemy Select query object that will be modified and executed.
        field_to_dbfield_map (dict): A mapping between field names and their corresponding database fields.
        filter_fields (List[FilterField]): A list of filter fields used for adding query constraints.
        default_order_by (List): The default order by clauses to apply to the query.

    Methods:
        get_paginated_data: Executes the query with pagination and returns a PaginatedData object containing the results
                            and total count.
    """

    def __init__(
        self,
        db: Session,
        request_params: BffTableQuerySchemaBase,
        query: Select,
        field_to_dbfield_map: dict,
        default_order_by,
    ):
        self.db = db
        self.request_params = request_params
        self.query = query
        self.field_to_dbfield_map = field_to_dbfield_map
        self.filter_fields = request_params.get_filter_fields()
        self.default_order_by = [default_order_by] if not isinstance(default_order_by, Iterable) else default_order_by

        self._prepare_query()

    def _get_query_field(self, param_name):
        if param_name in self.field_to_dbfield_map:
            return self.field_to_dbfield_map.get(param_name)
        else:
            return get_db_field(
                field_name=param_name,
                field_to_dbfield_map=self.field_to_dbfield_map,
                query=self.query,
            )

    def _order_by_clauses(self):
        order_by_clauses = []

        sorts = getattr(self.request_params, "sort", [])
        sorts = sorts or []

        default_order_list = [x for x in self.default_order_by]

        for sort in sorts:
            fieldname, direction = sort.split(".")

            for default_order in default_order_list:
                if fieldname == default_order.element.name:
                    default_order_list.remove(default_order)

            if direction == "asc":
                order_by_clauses.append(self._get_query_field(fieldname).asc())
            elif direction == "desc":
                order_by_clauses.append(self._get_query_field(fieldname).desc())

        for default_order in default_order_list:
            order_by_clauses.append(default_order)

        return order_by_clauses

    def _prepare_query(self):
        for field in self.filter_fields:
            self.query = field.add_database_query_parameters(
                query=self.query,
                request_params=self.request_params,
                field_to_dbfield_map=self.field_to_dbfield_map,
            )

        if getattr(self.request_params, "search", None):
            search = getattr(self.request_params, "search")
            clauses = []
            for field in self.filter_fields:
                clause = field.get_database_global_search_query_clause(
                    query=self.query,
                    search=search,
                    field_to_dbfield_map=self.field_to_dbfield_map,
                )
                clauses.append(clause)
            self.query = self.query.where(or_(*clauses))

        self.query = self.query.order_by(*self._order_by_clauses())

    def _paginate(self, query: Select) -> Select:
        # Must not mutate self.query: _get_count reuses it without pagination.
        query = query.limit(self.request_params.get_limit())
        query = query.offset(self.request_params.get_offset())
        return query

    def _make_result(self, items: list, count: int) -> PaginatedData:
        return PaginatedData(items=items, count=count)

    def _get_scalars(self) -> ScalarResult:
        return self.db.execute(self._paginate(self.query)).scalars()

    def _get_count(self):
        """Retrieve the total count of records matching the current query without limit, offset, or order by clauses.

        This method constructs a count query based on the current query configuration, removing any existing
        limits, offsets, or orderings to ensure an accurate total count of records. By wrapping the query as a
        subquery, DISTINCT clauses are properly respected in the count.

        Returns:
            int: The total count of records as an integer.
        """
        count_query = self.query
        count_query = count_query.limit(None)
        count_query = count_query.offset(None)
        count_query = count_query.order_by(None)

        # Wrap as subquery to correctly handle DISTINCT in the original query,
        # then count the rows of the subquery.
        subquery = count_query.subquery()
        count_query = select(func.count()).select_from(subquery)

        return self.db.execute(count_query).scalar()

    def get_paginated_data(self) -> PaginatedData:
        """
        Retrieve a paginated set of data from the database with the current query.

        This method executes the current SQLAlchemy query with limit and offset
        parameters applied, fetching a list of scalar results. It also calculates
        the total count of available records that match the current query without
        pagination restrictions. The results are returned as a PaginatedData
        object, which includes the list of items and the total count.

        Returns:
            PaginatedData: An object containing a list of items and the total
            count of matching records.
        """
        items = list(self._get_scalars().all())
        return self._make_result(items, self._get_count() or 0)


class CursorBFFTable(BFFTable):
    """Keyset (cursor) pagination variant of :class:`BFFTable`.

    Slices by a stable cursor on ``(cursor_sort, cursor_id)`` ordered DESC.
    Filtering, search and counting are inherited unchanged.
    """

    def __init__(
        self,
        db: Session,
        request_params: BffTableQuerySchemaBase,
        query: Select,
        field_to_dbfield_map: dict,
        cursor_sort,
        cursor_id,
    ):
        # Must be set before super().__init__() runs _prepare_query().
        self.cursor_sort = cursor_sort
        self.cursor_id = cursor_id
        super().__init__(
            db=db,
            request_params=request_params,
            query=query,
            field_to_dbfield_map=field_to_dbfield_map,
            default_order_by=[],
        )

    def _order_by_clauses(self):
        return [self.cursor_sort.desc(), self.cursor_id.desc()]

    def _resolve_cursor_position(self):
        # Token carries only the id; look up its sort value. None if no cursor
        # or the row is gone (then paging restarts from the beginning).
        cursor_id_value = self.request_params.get_cursor()
        if cursor_id_value is None:
            return None
        sort_value = self.db.execute(
            select(self.cursor_sort).where(self.cursor_id == cursor_id_value),
        ).scalar_one_or_none()
        if sort_value is None:
            return None
        return (sort_value, cursor_id_value)

    def _paginate(self, query: Select) -> Select:
        position = self._resolve_cursor_position()
        if position is not None:
            sort_value, id_value = position
            query = query.where(
                or_(
                    self.cursor_sort < sort_value,
                    and_(self.cursor_sort == sort_value, self.cursor_id < id_value),
                ),
            )
        return query.limit(self.request_params.get_limit())

    def _make_result(self, items: list, count: int) -> CursorPaginatedData:
        return CursorPaginatedData(items=items, count=count, next_cursor=self._next_cursor(items))

    def _next_cursor(self, items: list) -> Optional[str]:
        # No token on a non-full page: nothing left to fetch.
        if not items or len(items) < self.request_params.get_limit():
            return None
        return encode_cursor(getattr(items[-1], self.cursor_id.key))


def get_bff_table_query_schema(
    schema_name: str,
    sorting_fields: List[str],
    filter_fields: List[FilterField],
    add_global_search_filter: bool,
):
    query_params_definition: dict[str, Any] = {
        "limit": (Optional[int], None),
        "offset": (Optional[int], None),
        # Keyset cursor; only used by cursor-paginated endpoints.
        "cursor": (Optional[str], None),
    }

    sorting_enum_values = dict()

    for field in sorting_fields:
        sorting_enum_values[field + ".asc"] = field + ".asc"
        sorting_enum_values[field + ".desc"] = field + ".desc"

    MySortingEnum = Enum(schema_name + "SortingEnum", sorting_enum_values, type=str)

    # query_params_definition["sort"] = (Optional[List[MySortingEnum]], Query(default_factory=lambda: []))
    # for now this is still pydantic v1
    query_params_definition["sort"] = (
        Annotated[Optional[List[MySortingEnum]], Query()],
        [],
    )

    for field in filter_fields:
        field.add_GET_parameters(schema_query_params=query_params_definition)

    if add_global_search_filter:
        query_params_definition["search"] = (Optional[str], None)

    class MyBffTableQuerySchemaBase(BffTableQuerySchemaBase):
        def get_filter_fields(self):
            return filter_fields

    model = pydantic.v1.create_model(
        schema_name,
        __base__=MyBffTableQuerySchemaBase,
        **query_params_definition,
    )

    # model = create_model()
    return model


def get_min_max(val, maxv=100, minv=1, default=100):
    try:
        x = int(val)
        x = max(x, minv)
        x = min(x, maxv)
    except Exception:
        x = default
    return x
