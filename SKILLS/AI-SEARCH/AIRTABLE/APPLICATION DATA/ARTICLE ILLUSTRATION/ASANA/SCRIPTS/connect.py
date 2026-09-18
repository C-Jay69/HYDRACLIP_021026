#!/usr/bin/env python3
"""Managed Asana entrypoint."""

import os
import sys
from datetime import date

from connect_contract import boolean, command, fields, reject, text, text_list
from connect_transport import (
    ConnectFailure,
    execute,
    managed_credentials,
    mark_untrusted,
    read_command,
    write_result,
)


CONNECTION_ENV = "MEDO_CONNECT_ASANA"
ROUTES = {
    "list_workspaces": "https://app-ehuhb6glsutd-api-connect-asana-list-workspaces.gateway.appmedo.com/",
    "list_projects": "https://app-ehuhb6glsutd-api-connect-asana-list-projects.gateway.appmedo.com/",
    "search_tasks": "https://app-ehuhb6glsutd-api-connect-asana-search-tasks.gateway.appmedo.com/",
    "create_task": "https://app-ehuhb6glsutd-api-connect-asana-create-task.gateway.appmedo.com/",
    "update_task": "https://app-ehuhb6glsutd-api-connect-asana-update-task.gateway.appmedo.com/",
}


def _ids(arguments, name):
    values = text_list(arguments, name, maximum=20, item_max_length=256)
    if values is not None and not values:
        reject("ID lists cannot be empty")
    return values


def _due_on(arguments):
    value = text(arguments, "dueOn", max_length=10)
    if value is None:
        return
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        reject("dueOn must be a real YYYY-MM-DD date")
    if parsed.isoformat() != value:
        reject("dueOn must be a real YYYY-MM-DD date")


def validate(action, arguments):
    """Validate the public arguments for one fixed action."""
    if action == "list_workspaces":
        fields(arguments, ("offset",))
        text(arguments, "offset", max_length=2_048)
    elif action == "list_projects":
        fields(arguments, ("workspaceId", "offset"), ("workspaceId",))
        text(arguments, "workspaceId", required=True, max_length=256)
        text(arguments, "offset", max_length=2_048)
    elif action == "search_tasks":
        fields(
            arguments,
            ("workspaceId", "query", "projectIds", "assigneeIds"),
            ("workspaceId",),
        )
        text(arguments, "workspaceId", required=True, max_length=256)
        text(arguments, "query", max_length=2_048)
        _ids(arguments, "projectIds")
        _ids(arguments, "assigneeIds")
        if not {"query", "projectIds", "assigneeIds"}.intersection(arguments):
            reject("At least one task search filter is required")
    elif action == "create_task":
        fields(
            arguments,
            ("name", "notes", "dueOn", "assigneeId", "workspaceId", "projectIds"),
            ("name",),
        )
        text(arguments, "name", required=True, max_length=1_024)
        text(arguments, "notes", max_length=8_192)
        text(arguments, "assigneeId", max_length=256)
        workspace = text(arguments, "workspaceId", max_length=256)
        projects = _ids(arguments, "projectIds")
        _due_on(arguments)
        if workspace is None and projects is None:
            reject("A workspace or project is required")
    elif action == "update_task":
        mutable = ("name", "notes", "dueOn", "assigneeId", "completed")
        fields(arguments, ("taskId", *mutable), ("taskId",))
        text(arguments, "taskId", required=True, max_length=256)
        text(arguments, "name", max_length=1_024)
        text(arguments, "notes", max_length=8_192)
        text(arguments, "assigneeId", max_length=256)
        boolean(arguments, "completed")
        _due_on(arguments)
        if not set(mutable).intersection(arguments):
            reject("At least one task change is required")


def handle(value, environ=os.environ, sender=execute):
    """Validate and execute one managed Connect command."""
    action, arguments = command(value, ROUTES)
    validate(action, arguments)
    gateway_jwt, connection = managed_credentials(environ, CONNECTION_ENV)
    return mark_untrusted(sender(ROUTES[action], gateway_jwt, connection, arguments))


def main():
    """Run the stdin-to-stdout command entrypoint."""
    try:
        result = handle(read_command(sys.stdin.buffer))
        exit_code = 0
    except ConnectFailure as failure:
        result = failure.as_result()
        exit_code = 1
    except Exception:
        result = ConnectFailure("RESULT_UNKNOWN", "The provider result is unknown").as_result()
        exit_code = 1
    write_result(sys.stdout, result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
