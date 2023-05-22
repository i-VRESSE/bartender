import asyncio
from functools import partial, wraps
from typing import Any, Awaitable, Callable, Optional

# TODO add typing so returned function has typed args, kwargs and return


def async_wrap(func: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    """
    Wraps a synchronous function to run asynchronously.

    Example:

        >>> def sum(a, b):
        ...     return a + b
        >>> async_sum = async_wrap(sum)
        >>> result = await async_sum(1, 2)
        3

    Args:
        func: The synchronous function to wrap.

    Returns:
        An asynchronous function that wraps the synchronous function.
    """

    @wraps(func)
    async def run(  # noqa: WPS430
        *args: Any,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        executor: Any = None,
        **kwargs: Any,
    ) -> Any:
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run
