"""Test fixtures for a deployment that installs this composite.

``BLOCK_ENFORCEMENT`` defaults to ``required``, which means every test in
every suite that touches a classified contact needs a REGISTERED
``profiles.relationships`` provider or it raises
:class:`~stapel_classified.blocks.BlockCheckUnavailable`. That is the default
doing its job — but it makes "set up a working block store" a thing every
consumer has to figure out, and 0.3.1's own publish job proves how that ends:
21 tests red, and the tempting fix is to weaken the default.

So the harness ships with the module. Two backends, one API:

* **stapel-profiles is installed and mounted** — a block is a real
  ``UserRelationship`` row, read back by profiles' own provider. Nothing is
  faked, which is the only way a test can prove the seam.
* **it is not** — an explicit in-memory provider is registered under this
  deployment's ``BLOCK_FUNCTION`` name, with the same request/response shape.
  A stated double, chosen by the absence of the real thing, rather than a
  silent one that shadows it.

Use it from pytest — there is nothing to wire, the ``pytest11`` entry point
loads it for anyone who has this package installed::

    def test_a_blocked_buyer_cannot_write(block_provider, buyer, seller):
        block_provider.block(seller, buyer)
        ...

**Do not also name it in ``pytest_plugins``.** pytest registers an
entry-point plugin under its entry-point name; a ``pytest_plugins`` entry
registers the same module under its module name, and the second registration
raises ``ValueError: Plugin already registered under a different name``.
(0.3.2 shipped that line, passed on a machine whose editable install predated
the entry point, and died on the runner. 0.3.3 is the fix, and
``test_the_shipped_pytest_plugin_is_registered_exactly_once`` is the gate.)

Outside pytest, :func:`memory_block_provider` is a context manager with the
same API.
"""
from __future__ import annotations

from contextlib import contextmanager
from importlib.util import find_spec

__all__ = [
    "BlockStore",
    "block",
    "block_provider",
    "blocks_down",
    "memory_block_provider",
    "no_block_provider",
    "profiles_is_mounted",
]


def profiles_is_mounted() -> bool:
    """Is stapel-profiles installed AND in this project's INSTALLED_APPS?

    Both halves matter: installed-but-unmounted registers no provider, and
    that is the state a suite must not silently mistake for a working one.
    """
    if find_spec("stapel_profiles") is None:
        return False
    from django.apps import apps

    return apps.is_installed("stapel_profiles")


class BlockStore:
    """What a test does to blocks, whichever backend is behind it.

    ``block`` / ``unblock`` take users or ids, in the direction a person acts:
    ``block(blocker, blocked)``. Reads are symmetric — that is the fleet rule
    (profiles stores an intent, answers an effect), so ``is_blocked`` does not
    take a direction seriously and neither should any caller.
    """

    def __init__(self, backend: str):
        #: ``"profiles"`` or ``"memory"`` — say which one a failing test ran
        #: against, because the two prove different things.
        self.backend = backend

    @staticmethod
    def _id(user) -> str:
        return str(getattr(user, "pk", user))

    def block(self, blocker, blocked):  # pragma: no cover - overridden
        raise NotImplementedError

    def unblock(self, blocker, blocked):  # pragma: no cover - overridden
        raise NotImplementedError

    def set_unavailable(self, down: bool = True):  # pragma: no cover
        """Make the REGISTERED provider fail — the 503 case.

        Deliberately not the same thing as unregistering it: an unregistered
        provider is a deployment without a block store, and a failing one is
        an outage. The module answers them differently on purpose.
        """
        raise NotImplementedError

    def is_blocked(self, a, b) -> bool:
        from . import blocks

        return blocks.is_blocked(self._id(a), self._id(b))


class _ProfilesBlockStore(BlockStore):
    """Real ``UserRelationship`` rows, read by profiles' real provider."""

    def __init__(self):
        super().__init__("profiles")
        self._saved = None

    def block(self, blocker, blocked):
        from stapel_profiles.models import UserRelationship
        from stapel_profiles.relationships import BLOCKED

        return UserRelationship.objects.create(
            follower_id=self._id(blocker),
            following_id=self._id(blocked),
            status=BLOCKED,
        )

    def unblock(self, blocker, blocked):
        from stapel_profiles.models import UserRelationship

        UserRelationship.objects.filter(
            follower_id=self._id(blocker), following_id=self._id(blocked)
        ).delete()

    def set_unavailable(self, down: bool = True):
        from stapel_profiles import relationships

        if down:
            if self._saved is None:
                self._saved = relationships.blocked_pairs

            def _down(pairs):
                raise RuntimeError("profiles is down (test harness)")

            relationships.blocked_pairs = _down
        elif self._saved is not None:
            relationships.blocked_pairs = self._saved
            self._saved = None

    def restore(self):
        self.set_unavailable(False)


class _MemoryBlockStore(BlockStore):
    """An in-memory provider under this deployment's ``BLOCK_FUNCTION`` name."""

    def __init__(self):
        super().__init__("memory")
        self.pairs: set = set()
        self.down = False

    def block(self, blocker, blocked):
        self.pairs.add(frozenset((self._id(blocker), self._id(blocked))))

    def unblock(self, blocker, blocked):
        self.pairs.discard(frozenset((self._id(blocker), self._id(blocked))))

    def set_unavailable(self, down: bool = True):
        self.down = down

    def answer(self, payload: dict) -> dict:
        if self.down:
            raise RuntimeError("block provider is down (test harness)")
        asked = payload.get("pairs") or []
        return {
            "blocked": [
                [a, b]
                for a, b in asked
                if frozenset((str(a), str(b))) in self.pairs
            ]
        }


@contextmanager
def memory_block_provider():
    """Register an in-memory block provider for the duration of the block.

    For a suite (or a script) with no stapel-profiles in it. Yields a
    :class:`BlockStore`; unregisters on exit, restoring whatever was there.
    """
    from stapel_core.comm.registry import function_registry

    from .conf import classified_settings

    name = classified_settings.BLOCK_FUNCTION
    store = _MemoryBlockStore()
    previous = function_registry._providers.get(name)
    previous_schema = function_registry._schemas.get(name)
    function_registry._providers[name] = store.answer
    function_registry._schemas[name] = None
    try:
        yield store
    finally:
        function_registry._providers.pop(name, None)
        function_registry._schemas.pop(name, None)
        if previous is not None:
            function_registry._providers[name] = previous
            function_registry._schemas[name] = previous_schema


# ── pytest fixtures ──────────────────────────────────────────────────

try:  # pragma: no cover - pytest is a test-time dependency, not a runtime one
    import pytest
except ImportError:  # pragma: no cover
    pytest = None


if pytest is not None:

    @pytest.fixture
    def block_provider(db):
        """A working block store, whichever backend this project can have.

        Real profiles where profiles is mounted; an explicit in-memory
        provider otherwise. Either way ``BLOCK_ENFORCEMENT="required"`` is
        satisfied and the composite's contact path runs as it does in
        production.
        """
        if profiles_is_mounted():
            store = _ProfilesBlockStore()
            try:
                yield store
            finally:
                store.restore()
        else:
            with memory_block_provider() as store:
                yield store

    @pytest.fixture
    def block(block_provider):
        """``block(blocker, blocked)`` — the shorthand most tests want."""
        return block_provider.block

    @pytest.fixture
    def blocks_down(block_provider):
        """The provider is REGISTERED and FAILING — the 503 case.

        Not the same as :func:`no_block_provider`: an outage is not a
        deployment without a block store, and this module answers them
        differently (503 vs the declared posture).
        """
        block_provider.set_unavailable(True)
        yield block_provider
        block_provider.set_unavailable(False)

    @pytest.fixture
    def no_block_provider():
        """A deployment with NO block store: unregister the provider.

        The posture ``BLOCK_ENFORCEMENT="auto"`` exists for, and the state
        ``"required"`` refuses to boot in. Constructing it explicitly is the
        point — with a provider mounted it is no longer something a test gets
        by doing nothing.
        """
        from stapel_core.comm.registry import function_registry

        from .conf import classified_settings

        name = classified_settings.BLOCK_FUNCTION
        provider = function_registry._providers.pop(name, None)
        schema = function_registry._schemas.pop(name, None)
        try:
            yield name
        finally:
            if provider is not None:
                function_registry._providers[name] = provider
                function_registry._schemas[name] = schema
