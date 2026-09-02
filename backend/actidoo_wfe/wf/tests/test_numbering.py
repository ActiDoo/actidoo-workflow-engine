# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Number range allocation (ADR 012).

The unit under test is ``service_task_helper.allocate_number``. It only needs three things
from a task helper - a session, the instance id and the task occurrence id - so
the tests drive it with a stub instead of running a workflow. The workflow-level
wiring (``sth.next_number``, the ``DATA_MODELS`` gate, the admin retry) is covered
by ``testdata/processes/TestFlowNumberRange``.
"""

import threading
import uuid

import pytest

from actidoo_wfe.database import SessionMaker, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.exceptions import NumberAllocationFailedError
from actidoo_wfe.wf.models import NumberRangeMixin, extension_model_base
from actidoo_wfe.wf.service_task_helper import allocate_number

setup_db(settings=settings)

_Base = extension_model_base("nrt")


class PlainNumber(_Base, NumberRangeMixin):
    """Everything on defaults: one global sequence starting at 1."""

    _ext_table = "plain"
    __abstract__ = False


class BandedNumber(_Base, NumberRangeMixin):
    """A start value and a reserved band - pure arithmetic in ``next_value``."""

    _ext_table = "banded"
    __abstract__ = False

    @classmethod
    def next_value(cls, previous):
        candidate = 1000 if previous is None else previous + 1
        return 1010 if 1005 <= candidate < 1010 else candidate


class ScopedNumber(_Base, NumberRangeMixin):
    """One independent sequence per site, taken from task data."""

    _ext_table = "scoped"
    __abstract__ = False

    @classmethod
    def number_scope(cls, sth):
        return sth.task_data["site"]

    @classmethod
    def format_number(cls, value, scope_key):
        return f"{scope_key}-{value:04d}"


class BlockNumber(_Base, NumberRangeMixin):
    """Letter blocks: the sequence stays a dense int, the rendering does not."""

    _ext_table = "block"
    __abstract__ = False

    @classmethod
    def format_number(cls, value, scope_key):
        block, index = divmod(value - 1, 3)
        return f"{chr(ord('A') + block)}{index + 1:02d}"


class GapFillNumber(_Base, NumberRangeMixin):
    """A reference that is not the highest value — proves the hook's freedom.

    Deliberately *not* a documented recipe: reusing a released number contradicts
    the rule that rows of a range are never deleted. What it pins down is that
    ``reference_value`` may run its own query and return whatever it likes, and
    that the allocation loop works with a reference the engine did not compute.
    """

    _ext_table = "gapfill"
    __abstract__ = False

    @classmethod
    def reference_value(cls, db, scope_key):
        from sqlalchemy import select

        # The session's view only - that is the whole contract; the engine adds
        # what others committed, on a retry.
        used = set(db.scalars(select(cls.value).where(cls.scope_key == scope_key)).all())
        candidate = 1
        while candidate in used:
            candidate += 1
        return candidate

    @classmethod
    def next_value(cls, previous):
        return previous


class ScatteredNumber(_Base, NumberRangeMixin):
    """A scattered scheme: no reference read at all, candidates come from a pool.

    Stands in for a deliberately non-sequential range (so the count of issued
    numbers cannot be inferred). ``_candidates`` is set per test to make the
    collisions deterministic instead of relying on chance.
    """

    _ext_table = "scattered"
    __abstract__ = False
    _number_max_attempts = 20
    _candidates = iter(())

    @classmethod
    def reference_value(cls, db, scope_key):
        return None

    @classmethod
    def next_value(cls, previous):
        return next(cls._candidates)


class CrowdedNumber(_Base, NumberRangeMixin):
    """Same defaults, room for more collisions - used by the multi-thread tests."""

    _ext_table = "crowded"
    __abstract__ = False
    _number_max_attempts = 20


class StuckNumber(_Base, NumberRangeMixin):
    """Always proposes the same value - the attempt budget has to stop it."""

    _ext_table = "stuck"
    __abstract__ = False
    _number_max_attempts = 3

    @classmethod
    def reference_value(cls, db, scope_key):
        return None

    @classmethod
    def next_value(cls, previous):
        return 99


ALL_MODELS = [
    PlainNumber,
    CrowdedNumber,
    BandedNumber,
    ScopedNumber,
    BlockNumber,
    GapFillNumber,
    ScatteredNumber,
    StuckNumber,
]


class StubHelper:
    """The three attributes ``allocate`` reads off a ServiceTaskHelper."""

    def __init__(self, db, *, task_uuid=None, instance_id=None, task_data=None):
        self.db = db
        self.task_uuid = task_uuid or uuid.uuid4()
        self.workflow_instance_id = instance_id or uuid.uuid4()
        self.task_data = task_data or {}


def _create_tables():
    engine = SessionMaker.kw["bind"]
    for model in ALL_MODELS:
        model.__table__.create(bind=engine, checkfirst=True)


def _allocate(db, model, *, task_uuid=None, instance_id=None, task_data=None, key=""):
    return allocate_number(
        model,
        sth=StubHelper(db, task_uuid=task_uuid, instance_id=instance_id, task_data=task_data),
        alloc_key=key,
    )


class TestTheFourHooks:
    def test_defaults_produce_a_dense_sequence_from_one(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                assert [_allocate(db, PlainNumber) for _ in range(3)] == ["1", "2", "3"]

    def test_next_value_carries_start_value_and_reserved_band(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                issued = [int(_allocate(db, BandedNumber)) for _ in range(7)]
            # 1005..1009 is reserved and skipped in one step.
            assert issued == [1000, 1001, 1002, 1003, 1004, 1010, 1011]

    def test_number_scope_keeps_sequences_independent(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                berlin = [_allocate(db, ScopedNumber, task_data={"site": "BER"}) for _ in range(2)]
                hamburg = [_allocate(db, ScopedNumber, task_data={"site": "HAM"}) for _ in range(2)]
                back = _allocate(db, ScopedNumber, task_data={"site": "BER"})
            assert berlin == ["BER-0001", "BER-0002"]
            # A fresh scope starts over rather than continuing the other one.
            assert hamburg == ["HAM-0001", "HAM-0002"]
            assert back == "BER-0003"

    def test_format_number_renders_blocks_over_a_dense_sequence(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                issued = [_allocate(db, BlockNumber) for _ in range(4)]
                values = [
                    row.value
                    for row in db.query(BlockNumber).order_by(BlockNumber.value).all()
                ]
            assert issued == ["A01", "A02", "A03", "B01"]
            # The ordering key stays dense even though the rendering rolls over.
            assert values == [1, 2, 3, 4]

    def test_reference_value_may_return_something_other_than_the_maximum(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                first_three = [_allocate(db, GapFillNumber) for _ in range(3)]
                assert first_three == ["1", "2", "3"]
                db.query(GapFillNumber).filter(GapFillNumber.value == 2).delete()
                db.flush()
                assert _allocate(db, GapFillNumber) == "2"


class TestTheGuarantee:
    def test_a_taken_value_is_skipped_instead_of_colliding(self, db_engine_ctx):
        """The retry loop, without threads: seed the row the scheme will propose."""
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                _allocate(db, PlainNumber)  # -> 1
                # Somebody else already holds 2, which is exactly what the default
                # next_value will propose next. The insert is refused and retried.
                db.add(
                    PlainNumber(
                        workflow_instance_id=uuid.uuid4(),
                        workflow_instance_task_id=uuid.uuid4(),
                        alloc_key="seed",
                        value=2,
                        formatted="2",
                        scope_key="",
                    ),
                )
                db.flush()
                assert _allocate(db, PlainNumber) == "3"

    def test_a_scheme_that_ignores_the_reference_still_terminates(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                ScatteredNumber._candidates = iter([7])
                assert _allocate(db, ScatteredNumber) == "7"
                # Two collisions on the taken value, then a free one.
                ScatteredNumber._candidates = iter([7, 7, 42])
                assert _allocate(db, ScatteredNumber) == "42"

    def test_exhausted_attempt_budget_raises_instead_of_looping(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                assert _allocate(db, StuckNumber) == "99"
                with pytest.raises(NumberAllocationFailedError) as excinfo:
                    _allocate(db, StuckNumber)
            assert "no free value after 3 attempts" in str(excinfo.value)

    def test_the_session_survives_a_collision(self, db_engine_ctx):
        """A refused insert must not poison the enclosing transaction."""
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                _allocate(db, PlainNumber)
                db.add(
                    PlainNumber(
                        workflow_instance_id=uuid.uuid4(),
                        workflow_instance_task_id=uuid.uuid4(),
                        alloc_key="seed",
                        value=2,
                        formatted="2",
                        scope_key="",
                    ),
                )
                db.flush()
                _allocate(db, PlainNumber)
                # Still usable after the savepoint rollback inside allocate().
                db.add(
                    PlainNumber(
                        workflow_instance_id=uuid.uuid4(),
                        workflow_instance_task_id=uuid.uuid4(),
                        alloc_key="after",
                        value=500,
                        formatted="500",
                        scope_key="",
                    ),
                )
                db.flush()
            with SessionMaker() as db:
                assert db.query(PlainNumber).count() == 4


class TestIdempotency:
    def test_the_same_task_occurrence_gets_the_same_number_back(self, db_engine_ctx):
        """What makes the admin retry of an erroneous task safe."""
        with db_engine_ctx():
            _create_tables()
            task_id = uuid.uuid4()
            with SessionMaker() as db, db.begin():
                first = _allocate(db, PlainNumber, task_uuid=task_id)
                again = _allocate(db, PlainNumber, task_uuid=task_id)
                assert first == again
                assert db.query(PlainNumber).count() == 1

    def test_separate_draws_in_one_task_get_separate_numbers(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            task_id = uuid.uuid4()
            with SessionMaker() as db, db.begin():
                first = _allocate(db, PlainNumber, task_uuid=task_id, key="#0")
                second = _allocate(db, PlainNumber, task_uuid=task_id, key="#1")
                assert first != second
                # ...and a replay of that same sequence returns both unchanged.
                assert _allocate(db, PlainNumber, task_uuid=task_id, key="#0") == first
                assert _allocate(db, PlainNumber, task_uuid=task_id, key="#1") == second
                assert db.query(PlainNumber).count() == 2

    def test_separate_task_occurrences_get_separate_numbers(self, db_engine_ctx):
        """Multi-instance children and loop passes are separate occurrences."""
        with db_engine_ctx():
            _create_tables()
            instance_id = uuid.uuid4()
            with SessionMaker() as db, db.begin():
                issued = [
                    _allocate(db, PlainNumber, task_uuid=uuid.uuid4(), instance_id=instance_id)
                    for _ in range(3)
                ]
            # One instance, three task occurrences - three numbers, not one.
            assert issued == ["1", "2", "3"]


class TestLockWaitTimeout:
    def test_the_session_value_is_restored_afterwards(self, db_engine_ctx):
        """A value left behind would outlive the request on the pooled connection."""
        from sqlalchemy import text

        from actidoo_wfe.database import session_lock_wait_timeout

        with db_engine_ctx(), SessionMaker() as db, db.begin():
            before = db.execute(text("SELECT @@SESSION.innodb_lock_wait_timeout")).scalar()
            with session_lock_wait_timeout(db, 17):
                assert db.execute(text("SELECT @@SESSION.innodb_lock_wait_timeout")).scalar() == 17
            assert db.execute(text("SELECT @@SESSION.innodb_lock_wait_timeout")).scalar() == before

    def test_none_leaves_the_session_untouched(self, db_engine_ctx):
        from sqlalchemy import text

        from actidoo_wfe.database import session_lock_wait_timeout

        with db_engine_ctx(), SessionMaker() as db, db.begin():
            before = db.execute(text("SELECT @@SESSION.innodb_lock_wait_timeout")).scalar()
            with session_lock_wait_timeout(db, None):
                assert db.execute(text("SELECT @@SESSION.innodb_lock_wait_timeout")).scalar() == before


class TestConcurrency:
    def test_two_concurrent_allocations_both_get_a_number(self, db_engine_ctx):
        """Neither a duplicate nor a starved retry.

        This races the *empty* scope, where ``reference_value`` returns ``None`` and
        both threads propose the same first number. The duplicate half is what the
        unique index guards; that both threads finish at all is what the two-source
        reference read is for.

        Verified by mutation - each of these turns this test red:

        * dropping the engine's fresh read on retry (``_committed_maximum``): the
          loser recomputes the same rejected candidate from its fixed snapshot and
          burns its whole budget;
        * making the reference a ``with_for_update`` read instead: on the empty
          scope it takes a gap lock instead of a row lock and the inserts deadlock;
        * taking the fresh read on the *first* attempt as well: not red here, but
          it nests a pool checkout on every allocation - the point of deferring it.
        """
        with db_engine_ctx():
            _create_tables()
            results: dict[int, str] = {}
            failures: dict[int, Exception] = {}
            both_started = threading.Barrier(2, timeout=30)

            def allocate_one(index: int) -> None:
                try:
                    with SessionMaker() as db, db.begin():
                        # Force both transactions to have an open snapshot before
                        # either allocates, which is the situation that starves a
                        # non-locking read.
                        db.query(PlainNumber).count()
                        both_started.wait()
                        results[index] = _allocate(db, PlainNumber)
                except Exception as error:
                    failures[index] = error

            threads = [threading.Thread(target=allocate_one, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)

            assert not failures, f"an allocation failed: {failures}"
            assert sorted(results.values()) == ["1", "2"]
            with SessionMaker() as db:
                assert db.query(PlainNumber).count() == 2

    def test_five_concurrent_allocations_on_a_populated_scope(self, db_engine_ctx):
        """The other path: a reference that exists, and more contenders than two.

        Every retry has to pick up what the previous winner committed, or two of
        these five collide on the same value and one of them ends up empty-handed.

        This is also the test that pins the primary key. With a surrogate UUID key
        instead of ``(scope_key, value)`` this went red roughly one run in two: a
        duplicate on a secondary unique index makes InnoDB gap-lock the conflicting
        row in the clustered index, random key positions make those gaps land
        crosswise, and the retries deadlock. Two threads were not enough to show it.
        """
        with db_engine_ctx():
            _create_tables()
            with SessionMaker() as db, db.begin():
                _allocate(db, CrowdedNumber)  # the scope is not empty this time

            results: dict[int, str] = {}
            failures: dict[int, Exception] = {}
            all_started = threading.Barrier(5, timeout=30)

            def allocate_one(index: int) -> None:
                try:
                    with SessionMaker() as db, db.begin():
                        db.query(CrowdedNumber).count()  # fix the snapshot first
                        all_started.wait()
                        results[index] = _allocate(db, CrowdedNumber)
                except Exception as error:
                    failures[index] = error

            threads = [threading.Thread(target=allocate_one, args=(i,)) for i in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=120)

            assert not failures, f"an allocation failed: {failures}"
            assert sorted(int(number) for number in results.values()) == [2, 3, 4, 5, 6]
            with SessionMaker() as db:
                assert db.query(CrowdedNumber).count() == 6

    def test_concurrent_scopes_do_not_interfere(self, db_engine_ctx):
        """Different scopes share a table but not a sequence, under load too."""
        with db_engine_ctx():
            _create_tables()
            results: dict[int, tuple[str, str]] = {}
            failures: dict[int, Exception] = {}
            all_started = threading.Barrier(4, timeout=30)

            def allocate_one(index: int) -> None:
                site = "BER" if index % 2 == 0 else "HAM"
                try:
                    with SessionMaker() as db, db.begin():
                        db.query(ScopedNumber).count()
                        all_started.wait()
                        results[index] = (site, _allocate(db, ScopedNumber, task_data={"site": site}))
                except Exception as error:
                    failures[index] = error

            threads = [threading.Thread(target=allocate_one, args=(i,)) for i in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=120)

            assert not failures, f"an allocation failed: {failures}"
            issued = sorted(results.values())
            # Each site ran its own sequence from 1, regardless of the other.
            assert issued == [
                ("BER", "BER-0001"),
                ("BER", "BER-0002"),
                ("HAM", "HAM-0001"),
                ("HAM", "HAM-0002"),
            ]
