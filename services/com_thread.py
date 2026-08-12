"""COM 感知线程池

封装 ThreadPoolExecutor，确保每个工作线程自动初始化/释放 COM 环境，
pywin32 的打印 API 需要 COM 支持。
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class COMThreadPool:
    """COM 感知的线程池，自动管理 pythoncom 生命周期。"""

    def __init__(self, max_workers: int = 3) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_done: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> Future[Any]:
        """提交任务到线程池，自动处理 COM 初始化/释放。

        Args:
            fn: 要在工作线程中调用的函数。
            *args: 传递给 fn 的位置参数。
            on_done: 任务完成后的主线程回调（通过 tk.after 安全调用）。
            **kwargs: 传递给 fn 的关键字参数。

        Returns:
            Future 对象。
        """

        def _worker() -> Any:
            import pythoncom

            com_initialized = False
            try:
                pythoncom.CoInitialize()
                com_initialized = True
                return fn(*args, **kwargs)
            finally:
                if com_initialized:
                    pythoncom.CoUninitialize()

        def _on_complete(fut: Future[Any]) -> None:
            try:
                fut.result()  # 抛出线程中的异常（如有）
            except Exception:
                import traceback

                from loguru import logger

                logger.error(f"后台任务异常:\n{traceback.format_exc()}")
            finally:
                if on_done is not None:
                    on_done()

        future = self._executor.submit(_worker)
        future.add_done_callback(_on_complete)
        return future

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池。"""
        self._executor.shutdown(wait=wait)
