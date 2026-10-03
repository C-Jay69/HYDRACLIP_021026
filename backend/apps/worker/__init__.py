"""Celery worker package.

``docker-compose.yml`` referenced ``./apps/worker`` from the start, but the
directory never existed, so the worker service could not build and the
flower container monitored an empty broker.
"""
