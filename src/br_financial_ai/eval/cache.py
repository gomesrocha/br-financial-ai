from collections.abc import Awaitable, Callable


class EvalResultCache:
    """Eval-run-local cache. Not used by application persistence."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], object] = {}

    async def get_or_set[T](
        self,
        namespace: str,
        key: str,
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        identity = (namespace, key)
        if identity not in self._values:
            self._values[identity] = await factory()
        return self._values[identity]  # type: ignore[return-value]

    def __len__(self) -> int:
        return len(self._values)
