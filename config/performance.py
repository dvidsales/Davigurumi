"""Opt-in aggregate timings. Never record SQL, parameters, URLs or identities."""

from contextvars import ContextVar
from functools import wraps
from time import perf_counter
import logging
from django.conf import settings
from django.db import connection

_metrics = ContextVar("request_performance", default=None)
logger = logging.getLogger("davigurumi.performance")


def timed_operation(kind):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            metrics = _metrics.get()
            if metrics is None:
                return function(*args, **kwargs)
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                metrics[kind + "_count"] += 1
                metrics[kind + "_ms"] += (perf_counter() - start) * 1000

        return measured

    return decorate


class PerformanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.PERFORMANCE_LOGGING:
            return self.get_response(request)
        metrics = {
            key: 0
            for key in (
                "db_count",
                "db_ms",
                "remote_count",
                "remote_ms",
                "ledger_count",
                "ledger_ms",
            )
        }
        token = _metrics.set(metrics)
        start = perf_counter()

        def execute(execute, sql, params, many, context):
            begun = perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                metrics["db_count"] += 1
                metrics["db_ms"] += (perf_counter() - begun) * 1000

        try:
            with connection.execute_wrapper(execute):
                response = self.get_response(request)
            route = (
                request.resolver_match.view_name
                if request.resolver_match
                else "unresolved"
            )
            logger.info(
                "request route=%s status=%s total_ms=%.2f db_count=%s db_ms=%.2f remote_count=%s remote_ms=%.2f ledger_count=%s ledger_ms=%.2f",
                route,
                response.status_code,
                (perf_counter() - start) * 1000,
                metrics["db_count"],
                metrics["db_ms"],
                metrics["remote_count"],
                metrics["remote_ms"],
                metrics["ledger_count"],
                metrics["ledger_ms"],
            )
            return response
        finally:
            _metrics.reset(token)
