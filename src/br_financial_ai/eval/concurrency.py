import asyncio
from collections.abc import Awaitable, Callable, Sequence


async def map_bounded[T, R](
    items: Sequence[T],
    func: Callable[[T], Awaitable[R]],
    *,
    concurrency: int,
) -> list[R]:
    if not items:
        return []

    limit = max(1, int(concurrency))
    semaphore = asyncio.Semaphore(limit)
    results: list[R | object] = [_UNSET] * len(items)

    async def run_identified(index: int, item: T) -> None:
        async with semaphore:
            try:
                results[index] = await func(item)
            except Exception as exc:
                identity = _case_identity(item, index)
                raise AssertionError(f"Eval case {identity} failed: {exc}") from exc

    async with asyncio.TaskGroup() as group:
        for index, item in enumerate(items):
            group.create_task(run_identified(index, item))

    filled: list[R] = []
    for slot in results:
        if slot is _UNSET:
            raise RuntimeError("bounded map left an empty slot")
        filled.append(slot)  # type: ignore[arg-type]
    return filled


_UNSET = object()


def _case_identity(item: object, index: int) -> str:
    if isinstance(item, dict):
        identity = item.get("id")
        if isinstance(identity, str) and identity.strip():
            return identity
    return f"#{index}"
