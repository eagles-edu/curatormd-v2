"""Least-privilege checks for the local Hermes profile-bound MCP launcher."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Event
from typing import Callable, cast
import unittest
from unittest.mock import patch

from project_fixtures import create_consumer_repo, write_consumer_config

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import RequestParamsMeta, TextContent

from curatormd_v2 import (
    AuthenticatedCaller,
    CuratorStore,
    ConsumerDrainAuthorizationRequest,
    ConsumerBindingTransitionRequest,
    EventEnvelope,
    EventInboxReceipt,
    EventInboxStatus,
    GoalStarted,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectConfig,
    ProjectRegistrationRequest,
    ProjectPlugin,
    ProjectStatusChangeRequest,
    SQLiteTokenBucket,
    SuccessCriterion,
    hosted_mcp,
)
from curatormd_v2.hosted_mcp import build_local_profile_mcp
from curatormd_v2.service import _PreparedEvent  # pyright: ignore[reportPrivateUsage]
from curatormd_v2.mcp_server import safe_tool_handler

def _hermes_meta(
    profile_id: str, session_id: str = "test-session"
) -> RequestParamsMeta:
    """Build synthetic Hermes context metadata for boundary tests."""

    return {
        "hermes/profile_id": profile_id,
        "hermes/session_id": session_id,
    }


def _local_subject() -> str:
    """Match the authenticated account used by the local MCP child process."""

    return f"local-uid:{os.geteuid()}"


# ProjectAdminAuthorizer fixture intentionally implements one protocol method.
class _TestProjectAdmin:  # pylint: disable=too-few-public-methods
    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Allow administration only to the explicitly named test operator."""

        return (
            (
                caller.subject_id == "test-operator"
                or (
                    caller.subject_id.startswith("local-uid:")
                    and action is ProjectAdministrationAction.DRAIN
                )
            )
            and bool(project_id)
            and action
            in {
                ProjectAdministrationAction.REGISTER,
                ProjectAdministrationAction.UPDATE,
                ProjectAdministrationAction.SUSPEND,
                ProjectAdministrationAction.REACTIVATE,
                ProjectAdministrationAction.VIEW,
                ProjectAdministrationAction.GRANT,
                ProjectAdministrationAction.REVOKE,
                ProjectAdministrationAction.DEREGISTER,
                ProjectAdministrationAction.DEREGISTER_FINALIZE,
                ProjectAdministrationAction.DRAIN,
                ProjectAdministrationAction.DISPOSE_EVENT,
                ProjectAdministrationAction.RETIRE,
            }
        )


class HostedMcpTests(unittest.TestCase):
    """Keep each local MCP process pinned to one project and principal."""

    def _project(self, root: Path, project_id: str = "bound-project") -> None:
        create_consumer_repo(root)
        (root / "docs" / "tasks.md").write_text("- [ ] Bounded task\n")
        (root / "persistence" / "HISTORY.md").write_text("# History\n")
        write_consumer_config(root, project_id)

    def _provision(
        self,
        root: Path,
        database: Path,
        _profile_id: str,
        *,
        allow_write: bool = False,
        allow_review: bool = False,
    ) -> None:
        """Seed durable access using the host-only project administration API."""

        config = ProjectConfig.load(root)
        store = CuratorStore(database)
        try:
            manager = ProjectAccessManager(store, _TestProjectAdmin())
            operator = AuthenticatedCaller("test-operator")
            manager.register_project(
                operator,
                ProjectRegistrationRequest.from_project_config(
                    config,
                    "Approve the disposable integration-test project binding",
                ),
            )
            for action in (
                ProjectAction.READ,
                ProjectAction.WRITE,
                ProjectAction.REVIEW,
            ):
                if action is ProjectAction.WRITE and not allow_write:
                    continue
                if action is ProjectAction.REVIEW and not allow_review:
                    continue
                manager.grant(
                    operator,
                    config.project_id,
                    _local_subject(),
                    action,
                    "Grant the disposable integration-test profile exact access",
                )
        finally:
            store.close()

    def test_profile_binding_defaults_to_read_only_and_denies_review_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding")
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
            )
            try:
                self.assertEqual(runtime.caller.subject_id, _local_subject())
                self.assertEqual(runtime.caller.profile_id, "gptmd-coding")
                self.assertIsInstance(runtime.api.limiter, SQLiteTokenBucket)
                authorizer = runtime.api.authorizer
                self.assertTrue(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.READ
                    )
                )
                for action in (
                    ProjectAction.WRITE,
                    ProjectAction.REVIEW,
                    ProjectAction.PURGE_RETRY,
                    ProjectAction.RETENTION_HOLD_RELEASE,
                    ProjectAction.EVENT_RETRY,
                ):
                    with self.subTest(action=action):
                        self.assertFalse(
                            authorizer.authorize(
                                runtime.caller, "bound-project", action
                            )
                        )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "another-project", ProjectAction.READ
                    )
                )
            finally:
                runtime.close()

    def test_write_grant_is_exact_to_local_account_project_and_not_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding", allow_write=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
                allow_write=True,
            )
            try:
                authorizer = runtime.api.authorizer
                self.assertTrue(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.WRITE
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        type(runtime.caller)("local-uid:999"),
                        "bound-project",
                        ProjectAction.WRITE,
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "another-project", ProjectAction.WRITE
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.REVIEW
                    )
                )
            finally:
                runtime.close()

    def test_review_grant_is_exact_and_requires_launcher_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(
                root,
                database,
                "reviewer-profile",
                allow_review=True,
            )
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
                allow_review=True,
            )
            try:
                authorizer = runtime.api.authorizer
                self.assertTrue(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.REVIEW
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        AuthenticatedCaller("local-uid:999"),
                        "bound-project",
                        ProjectAction.REVIEW,
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "another-project", ProjectAction.REVIEW
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.WRITE
                    )
                )
            finally:
                runtime.close()

            read_only_runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
            )
            try:
                self.assertFalse(
                    read_only_runtime.api.authorizer.authorize(
                        read_only_runtime.caller,
                        "bound-project",
                        ProjectAction.REVIEW,
                    )
                )
            finally:
                read_only_runtime.close()

            store = CuratorStore(database)
            try:
                manager = ProjectAccessManager(store, _TestProjectAdmin())
                manager.revoke(
                    AuthenticatedCaller("test-operator"),
                    "bound-project",
                    _local_subject(),
                    ProjectAction.REVIEW,
                    "Revoke review access before testing launcher opt-in",
                )
            finally:
                store.close()
            with self.assertRaisesRegex(
                ValueError, "requested project review grant is not active"
            ):
                build_local_profile_mcp(
                    project_root=root,
                    database=database,
                    profile_id="read-only-profile",
                    allow_review=True,
                )

    def test_typed_mcp_event_retry_ignores_regenerated_occurrence_time(self) -> None:
        """A new MCP invocation can safely replay a processed event identity."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding", allow_write=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
                allow_write=True,
            )
            try:
                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        arguments = {
                            "event_id": "mcp-replay-event",
                            "goal_id": "mcp-replay-goal",
                            "problem": "Verify typed event retry behavior",
                            "success_criteria": [
                                {"criterion_id": "verified", "description": "Retry is idempotent"}
                            ],
                        }
                        first = await client.call_tool(
                            "goal_start", arguments, meta=_hermes_meta("gptmd-coding")
                        )
                        self.assertFalse(first.is_error)
                        retry = await client.call_tool(
                            "goal_start", arguments, meta=_hermes_meta("gptmd-coding")
                        )
                        self.assertFalse(retry.is_error)

                        changed = dict(arguments)
                        changed["problem"] = "Changed payload must conflict"
                        conflict = await client.call_tool(
                            "goal_start", changed, meta=_hermes_meta("gptmd-coding")
                        )
                        self.assertTrue(conflict.is_error)
                        conflict_content = conflict.content[0]
                        assert isinstance(conflict_content, TextContent)
                        self.assertEqual(json.loads(conflict_content.text)["code"], "conflict")

                asyncio.run(exercise())
            finally:
                runtime.close()

    def test_profile_processes_only_inventoried_event_during_approved_drain(self) -> None:
        """Exercise the exact old-event exception through the bound API facade."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "drain-profile", allow_write=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="drain-profile",
                allow_write=True,
            )
            try:
                config = ProjectConfig.load(root)
                event = EventEnvelope(
                    "drain-event-1",
                    config.project_id,
                    GoalStarted(
                        goal_id="drain-goal",
                        problem="Complete the queued task",
                        success_criteria=(SuccessCriterion("done", "Task is done"),),
                    ),
                    source_id="hermes-profile-drain-profile-generation-1",
                    source_sequence=1,
                )
                runtime.store.ingest_event(event)
                admin = AuthenticatedCaller("test-operator")
                policy = _TestProjectAdmin()
                manager = ProjectAccessManager(runtime.store, policy)
                manager.transition_consumer_binding(
                    admin,
                    ConsumerBindingTransitionRequest(
                        config.project_id,
                        "deregistration_pending",
                        "Stop new work before reviewing queued events",
                        1,
                        "drain-api-transition-1",
                    ),
                )
                inventory_count, inventory_digest = runtime.store.consumer_drain_inventory(
                    config.project_id
                )
                self.assertEqual(inventory_count, 1)
                local_operator = AuthenticatedCaller(_local_subject())
                manager.authorize_consumer_drain(
                    local_operator,
                    ConsumerDrainAuthorizationRequest(
                        project_id=config.project_id,
                        transition_id="drain-api-transition-1",
                        expected_revision=2,
                        expected_inventory_sha256=inventory_digest,
                        lifetime_seconds=60,
                        consumer_profile="drain-profile",
                    ),
                )
                self.assertEqual(
                    runtime.api.consumer_source_epoch(
                        runtime.caller, config.project_id, event.event_id
                    ),
                    1,
                )
                receipt = runtime.api.process_event_json(
                    runtime.caller, config.project_id, event.to_json()
                )
                self.assertEqual(receipt.status.value, "processed")
                new_event = EventEnvelope(
                    "new-event-during-drain",
                    config.project_id,
                    event.payload,
                    source_id=event.source_id,
                    source_sequence=2,
                )
                with self.assertRaises(PermissionError):
                    runtime.api.process_event_json(
                        runtime.caller, config.project_id, new_event.to_json()
                    )
            finally:
                runtime.close()

    def test_every_local_profile_tool_call_requires_matching_hermes_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding")
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
            )
            try:
                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        missing = await client.call_tool("project_activity_status", {})
                        self.assertTrue(missing.is_error)
                        missing_content = missing.content[0]
                        assert isinstance(missing_content, TextContent)
                        self.assertEqual(
                            json.loads(missing_content.text)["code"], "unauthenticated"
                        )

                        mismatch = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta=_hermes_meta("another-profile"),
                        )
                        self.assertTrue(mismatch.is_error)

                        no_session = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta={"hermes/profile_id": "gptmd-coding"},
                        )
                        self.assertTrue(no_session.is_error)

                        valid = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta=_hermes_meta("gptmd-coding"),
                        )
                        self.assertFalse(valid.is_error)

                asyncio.run(exercise())
            finally:
                runtime.close()

    def test_strict_profile_denies_a_missing_authenticated_person_subject(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding")
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
                require_authenticated_subject=True,
            )
            try:
                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        result = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta=_hermes_meta("gptmd-coding"),
                        )
                        self.assertTrue(result.is_error)
                        content = result.content[0]
                        assert isinstance(content, TextContent)
                        self.assertEqual(
                            json.loads(content.text)["code"], "unauthenticated"
                        )
                        ungranted_subject = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta={
                                **_hermes_meta("gptmd-coding"),
                                "hermes/authenticated_subject": (
                                    'auth:v1:["oidc","https://issuer.example","user-42"]'
                                ),
                            },
                        )
                        self.assertTrue(ungranted_subject.is_error)
                        denied_content = ungranted_subject.content[0]
                        assert isinstance(denied_content, TextContent)
                        self.assertEqual(
                            json.loads(denied_content.text)["code"], "forbidden"
                        )

                asyncio.run(exercise())
            finally:
                runtime.close()

    def test_launcher_requires_registered_fingerprint_and_live_grants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            with self.assertRaisesRegex(ValueError, "registration fingerprint"):
                build_local_profile_mcp(
                    project_root=root,
                    database=database,
                    profile_id="gptmd-coding",
                )

            self._provision(root, database, "gptmd-coding")
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
            )
            try:
                self.assertTrue(
                    runtime.api.authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.READ
                    )
                )
                external_store = CuratorStore(database)
                try:
                    manager = ProjectAccessManager(
                        external_store, _TestProjectAdmin()
                    )
                    config = ProjectConfig.load(root)
                    plugin = ProjectPlugin.bind(config, external_store)
                    manager.set_project_status(
                        AuthenticatedCaller("test-operator"),
                        ProjectStatusChangeRequest(
                            project_id="bound-project",
                            status="suspended",
                            rationale="Suspend the disposable test project",
                            expected_revision=1,
                            transition_id="hosted-test-suspend-1",
                        ),
                    )
                    review_packet = manager.project_reactivation_review_packet(
                        AuthenticatedCaller("test-operator"),
                        "bound-project",
                        plugin.review_staging_inventory(),
                    )
                    self.assertTrue(review_packet.complete)
                    self.assertIsNotNone(review_packet.packet_sha256)
                    manager.set_project_status(
                        AuthenticatedCaller("test-operator"),
                        ProjectStatusChangeRequest(
                            project_id="bound-project",
                            status="active",
                            rationale="Reactivate after the disposable suspension",
                            expected_revision=2,
                            transition_id="hosted-test-reactivate-1",
                            review_packet_sha256=review_packet.packet_sha256,
                            suspension_transition_id=(
                                review_packet.suspension_transition_id
                            ),
                            staging_inventory_sha256=(
                                review_packet.staging_inventory_sha256
                            ),
                            staging_inventory_count=(
                                review_packet.staging_inventory_count
                            ),
                            staging_inventory_bytes=(
                                review_packet.staging_inventory_bytes
                            ),
                            staging_inventory_observed_at=(
                                review_packet.staging_inventory_observed_at
                            ),
                        ),
                    )
                finally:
                    external_store.close()
                self.assertFalse(
                    runtime.api.authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.READ
                    )
                )
            finally:
                runtime.close()

            refreshed_runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
            )
            try:
                self.assertTrue(
                    refreshed_runtime.api.authorizer.authorize(
                        refreshed_runtime.caller,
                        "bound-project",
                        ProjectAction.READ,
                    )
                )
            finally:
                refreshed_runtime.close()

            changed = (root / ".curatormd-v2.toml").read_text()
            (root / ".curatormd-v2.toml").write_text(
                changed.replace('project_id = "bound-project"', 'project_id = "changed-project"')
            )
            (root / ".curatormd-v2.toml").chmod(0o600)
            with self.assertRaisesRegex(ValueError, "registration fingerprint"):
                build_local_profile_mcp(
                    project_root=root,
                    database=database,
                    profile_id="gptmd-coding",
                )

    def test_inflight_write_finishes_before_project_suspend_cutover(self) -> None:
        """Serialize an already admitted durable write before a status change."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding", allow_write=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
                allow_write=True,
            )
            entered_effect = Event()
            release_effect = Event()
            status_started = Event()
            plugin = getattr(runtime.api, "_plugins")["bound-project"]
            # Pause at the exact transaction boundary to prove suspension waits.
            original_commit_event = cast(
                Callable[
                    [EventEnvelope, _PreparedEvent, str | None], EventInboxReceipt
                ],
                getattr(plugin.service, "_commit_event"),
            )

            def pause_inside_fenced_event_commit(
                event: EventEnvelope,
                prepared: _PreparedEvent,
                lease_owner: str | None,
            ):
                entered_effect.set()
                if not release_effect.wait(timeout=10):
                    raise TimeoutError("test did not release the fenced event effect")
                return original_commit_event(event, prepared, lease_owner)

            event = EventEnvelope(
                "fenced-event-1",
                "bound-project",
                GoalStarted(
                    "fenced-goal",
                    "Ensure the event commits before project suspension",
                    (SuccessCriterion("recorded", "The event is durably recorded"),),
                ),
            )
            transition_store = CuratorStore(database)
            manager = ProjectAccessManager(transition_store, _TestProjectAdmin())
            operator = AuthenticatedCaller("test-operator")
            try:
                with ThreadPoolExecutor(max_workers=2) as workers:
                    with patch.object(
                        plugin.service,
                        "_commit_event",
                        side_effect=pause_inside_fenced_event_commit,
                    ):
                        write_future = workers.submit(
                            runtime.api.process_event_json,
                            runtime.caller,
                            "bound-project",
                            event.to_json(),
                        )
                        self.assertTrue(
                            entered_effect.wait(timeout=5),
                            str(write_future.exception(timeout=0))
                            if write_future.done()
                            else "event worker did not reach its durable commit",
                        )

                        def suspend_after_effect_admission():
                            status_started.set()
                            registration = transition_store.get_project_registration(
                                "bound-project"
                            )
                            return manager.set_project_status(
                                operator,
                                ProjectStatusChangeRequest(
                                    project_id="bound-project",
                                    status="suspended",
                                    rationale=(
                                        "Suspend after the already admitted event"
                                    ),
                                    expected_revision=registration.revision,
                                    transition_id="suspend-after-event-1",
                                ),
                            )

                        status_future = workers.submit(suspend_after_effect_admission)
                        self.assertTrue(status_started.wait(timeout=5))
                        self.assertFalse(status_future.done())
                        release_effect.set()
                        receipt = write_future.result(timeout=10)
                        transition = status_future.result(timeout=10)
                self.assertEqual(receipt.status, EventInboxStatus.PROCESSED)
                self.assertEqual(transition.receipt.action, "suspended")
                self.assertEqual(transition.receipt.revision, 2)
                self.assertEqual(transition.registration.status, "suspended")
                self.assertEqual(
                    runtime.api.consumer_source_epoch(
                        runtime.caller, "bound-project", event.event_id
                    ),
                    1,
                )
                with self.assertRaisesRegex(PermissionError, "not authorized"):
                    runtime.api.consumer_source_epoch(
                        runtime.caller, "bound-project", "unprocessed-event"
                    )
                replayed_receipt = runtime.api.process_event_json(
                    runtime.caller, "bound-project", event.to_json()
                )
                self.assertEqual(replayed_receipt, receipt)

                changed_event = EventEnvelope(
                    event.event_id,
                    event.project_id,
                    GoalStarted(
                        "fenced-goal",
                        "Changed event payload must not reuse the processed receipt",
                        (SuccessCriterion("recorded", "The event payload changed"),),
                    ),
                )
                with self.assertRaisesRegex(PermissionError, "not authorized"):
                    runtime.api.process_event_json(
                        runtime.caller, "bound-project", changed_event.to_json()
                    )
            finally:
                release_effect.set()
                runtime.close()
                transition_store.close()


    def test_database_path_must_be_absolute_and_profile_id_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            with self.assertRaisesRegex(ValueError, "absolute path"):
                build_local_profile_mcp(
                    project_root=root,
                    database="relative.sqlite3",
                    profile_id="gptmd-coding",
                )
            with self.assertRaisesRegex(ValueError, "profile_id"):
                build_local_profile_mcp(
                    project_root=root,
                    database=Path(temporary) / "global.sqlite3",
                    profile_id="bad profile",
                )

    def test_tool_failure_uses_public_error_without_exception_details(self) -> None:
        def fail_with_sensitive_detail() -> None:
            raise RuntimeError("private database path and SQL fragment")

        with self.assertLogs("curatormd_v2.mcp_server", level="WARNING") as logs:
            result = safe_tool_handler(fail_with_sensitive_detail)()
        self.assertTrue(result.is_error)
        content = result.content[0]
        assert isinstance(content, TextContent)
        public_error = json.loads(content.text)
        self.assertEqual(public_error["code"], "internal_error")
        self.assertNotIn("private database path", content.text)
        self.assertNotIn("Traceback", content.text)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("code=internal_error", logs.output[0])
        self.assertIn("exception_type=RuntimeError", logs.output[0])
        self.assertNotIn("private database path", logs.output[0])
        self.assertNotIn("SQL fragment", logs.output[0])

    def test_launcher_startup_failure_does_not_echo_exception_detail(self) -> None:
        """Do not copy arbitrary startup exception text into process logs."""

        stderr = StringIO()
        arguments = [
            "--project-root",
            "/tmp/private-project",
            "--database",
            "/tmp/private-database.sqlite3",
            "--profile-id",
            "trusted-profile",
        ]
        for startup_exception in (
            ValueError("private raw payload marker"),
            OSError("private-database.sqlite3 could not be opened"),
            RuntimeError("private SQL fragment"),
        ):
            with self.subTest(exception=type(startup_exception).__name__):
                stderr = StringIO()
                with patch(
                    "curatormd_v2.hosted_mcp.build_local_profile_mcp",
                    side_effect=startup_exception,
                ), redirect_stderr(stderr):
                    exit_code = hosted_mcp.main(arguments)

                self.assertEqual(exit_code, 2)
                self.assertIn("startup failed", stderr.getvalue())
                self.assertNotIn("private raw payload marker", stderr.getvalue())
                self.assertNotIn("private-database.sqlite3", stderr.getvalue())
                self.assertNotIn("private SQL fragment", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_stdio_process_pins_real_config_and_rejects_ungranted_goal_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding")
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "curatormd_v2.hosted_mcp",
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "--profile-id",
                    "gptmd-coding",
                ],
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
                },
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=False) as client:
                    denied = await client.call_tool(
                        "goal_start",
                        {
                            "event_id": "denied-event",
                            "goal_id": "denied-goal",
                            "problem": "A write must require the explicit write grant",
                            "success_criteria": [
                                {
                                    "criterion_id": "denied",
                                    "description": "The write is rejected",
                                }
                            ],
                        },
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertTrue(denied.is_error)
                    denied_content = denied.content[0]
                    assert isinstance(denied_content, TextContent)
                    public_error = json.loads(denied_content.text)
                    self.assertEqual(public_error["schema_version"], 1)
                    self.assertEqual(public_error["code"], "forbidden")
                    self.assertEqual(
                        public_error["message"],
                        "The caller is not allowed to perform this operation.",
                    )
                    self.assertNotIn("Traceback", denied_content.text)
                    self.assertNotIn("project is not authorized", denied_content.text)
                    missing_context = await client.call_tool(
                        "event_queue_status", {}
                    )
                    self.assertTrue(missing_context.is_error)
                    queue = await client.call_tool(
                        "event_queue_status",
                        {},
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(queue.is_error)
                    content = queue.content[0]
                    assert isinstance(content, TextContent)
                    self.assertEqual(json.loads(content.text)["received_count"], 0)

            asyncio.run(exercise())

    def test_installed_launcher_writes_and_reads_a_project_bound_goal(self) -> None:
        """Exercise the packaged command, not only its Python module entrypoint."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(
                root,
                database,
                "gptmd-coding",
                allow_write=True,
                allow_review=True,
            )
            launcher = Path(sys.executable).with_name("curatormd-v2-mcp")
            self.assertTrue(launcher.is_file(), f"missing installed launcher: {launcher}")
            parameters = StdioServerParameters(
                command=str(launcher),
                args=[
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "--profile-id",
                    "gptmd-coding",
                    "--allow-write",
                    "--allow-review",
                ],
                env={
                    "PATH": os.environ.get("PATH", ""),
                },
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=True) as client:
                    tools = await client.list_tools()
                    self.assertIn(
                        "project_artifact_inventory_discover",
                        {tool.name for tool in tools.tools},
                    )
                    goal_start = next(
                        tool for tool in tools.tools if tool.name == "goal_start"
                    )
                    self.assertNotIn("project_id", goal_start.input_schema["properties"])
                    self.assertNotIn("caller", goal_start.input_schema["properties"])
                    started = await client.call_tool(
                        "goal_start",
                        {
                            "event_id": "launcher-event-1",
                            "goal_id": "launcher-goal-1",
                            "problem": "Verify the installed Curator V2 MCP launcher",
                            "success_criteria": [
                                {
                                    "criterion_id": "stdio-roundtrip",
                                    "description": "Create and read a scoped goal over MCP stdio",
                                }
                            ],
                        },
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(started.is_error)
                    status = await client.call_tool(
                        "goal_status",
                        {"goal_id": "launcher-goal-1"},
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(status.is_error)
                    content = status.content[0]
                    assert isinstance(content, TextContent)
                    value = json.loads(content.text)
                    goal = value["goal"]
                    self.assertEqual(goal["project_id"], "bound-project")
                    self.assertEqual(goal["status"], "planned")
                    self.assertEqual(
                        goal["problem"],
                        "Verify the installed Curator V2 MCP launcher",
                    )
                    self.assertEqual(
                        goal["success_criteria"][0]["criterion_id"],
                        "stdio-roundtrip",
                    )
                    inventory_result = await client.call_tool(
                        "project_artifact_inventory_discover",
                        {},
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(inventory_result.is_error)
                    inventory_content = inventory_result.content[0]
                    assert isinstance(inventory_content, TextContent)
                    inventory = json.loads(inventory_content.text)
                    self.assertTrue(inventory["usage"]["inventory_complete"])
                    self.assertIsNone(inventory["scope_goal_id"])

            asyncio.run(exercise())

    def test_installed_launcher_exposes_sde_proposal_context(self) -> None:
        """The installed MCP schema carries compact proposal context fields."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding", allow_write=True)
            launcher = Path(sys.executable).with_name("curatormd-v2-mcp")
            self.assertTrue(launcher.is_file(), f"missing installed launcher: {launcher}")
            parameters = StdioServerParameters(
                command=str(launcher),
                args=[
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "--profile-id",
                    "gptmd-coding",
                    "--allow-write",
                ],
                env={"PATH": os.environ.get("PATH", "")},
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=True) as client:
                    tools = await client.list_tools()
                    assessment = next(
                        tool for tool in tools.tools if tool.name == "sde_assess"
                    )
                    schema = assessment.input_schema
                    properties = schema["properties"]
                    self.assertIn("impact", properties)
                    self.assertIn("retrieval_value", properties)
                    self.assertNotIn("project_id", properties)
                    required = set(schema.get("required", []))
                    self.assertTrue(
                        {"impact", "retrieval_value"}.isdisjoint(required),
                        "routine progress must remain valid without SDE context",
                    )

            asyncio.run(exercise())

    def test_two_stdio_projects_sharing_database_remain_isolated(self) -> None:
        """Separate consumer launchers cannot list or read each other's goals."""

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project_a = base / "consumer-a"
            project_b = base / "consumer-b"
            self._project(project_a, "project-a")
            self._project(project_b, "project-b")
            database = base / "global.sqlite3"
            self._provision(
                project_a, database, "profile-a", allow_write=True
            )
            self._provision(
                project_b, database, "profile-b", allow_write=True
            )
            launcher = Path(sys.executable).with_name("curatormd-v2-mcp")
            self.assertTrue(launcher.is_file(), f"missing installed launcher: {launcher}")

            def parameters(root: Path, profile_id: str) -> StdioServerParameters:
                return StdioServerParameters(
                    command=str(launcher),
                    args=[
                        "--project-root",
                        str(root),
                        "--database",
                        str(database),
                        "--profile-id",
                        profile_id,
                        "--allow-write",
                    ],
                    env={"PATH": os.environ.get("PATH", "")},
                    cwd=Path(__file__).parents[1],
                )

            async def exercise() -> None:
                async with Client(
                    parameters(project_a, "profile-a"), raise_exceptions=True
                ) as client_a:
                    started_a = await client_a.call_tool(
                        "goal_start",
                        {
                            "event_id": "project-a-event",
                            "goal_id": "project-a-goal",
                            "problem": "A scoped goal for consumer A",
                            "success_criteria": [
                                {
                                    "criterion_id": "a-only",
                                    "description": "Remain visible only in project A",
                                }
                            ],
                        },
                        meta=_hermes_meta("profile-a"),
                    )
                    self.assertFalse(started_a.is_error)

                    async with Client(
                        parameters(project_b, "profile-b"), raise_exceptions=True
                    ) as client_b:
                        page_b = await client_b.call_tool(
                            "goal_list_page",
                            {"offset": 0, "limit": 10},
                            meta=_hermes_meta("profile-b"),
                        )
                        self.assertFalse(page_b.is_error)
                        page_b_content = page_b.content[0]
                        assert isinstance(page_b_content, TextContent)
                        page_b_value = json.loads(page_b_content.text)
                        self.assertEqual(page_b_value["project_id"], "project-b")
                        self.assertEqual(page_b_value["total"], 0)
                        self.assertEqual(page_b_value["goals"], [])

                        foreign_status = await client_b.call_tool(
                            "goal_status",
                            {"goal_id": "project-a-goal"},
                            meta=_hermes_meta("profile-b"),
                        )
                        self.assertTrue(foreign_status.is_error)

                        started_b = await client_b.call_tool(
                            "goal_start",
                            {
                                "event_id": "project-b-event",
                                "goal_id": "project-b-goal",
                                "problem": "A scoped goal for consumer B",
                                "success_criteria": [
                                    {
                                        "criterion_id": "b-only",
                                        "description": "Remain visible only in project B",
                                    }
                                ],
                            },
                            meta=_hermes_meta("profile-b"),
                        )
                        self.assertFalse(started_b.is_error)

                    page_a = await client_a.call_tool(
                        "goal_list_page",
                        {"offset": 0, "limit": 10},
                        meta=_hermes_meta("profile-a"),
                    )
                    self.assertFalse(page_a.is_error)
                    page_a_content = page_a.content[0]
                    assert isinstance(page_a_content, TextContent)
                    page_a_value = json.loads(page_a_content.text)
                    self.assertEqual(page_a_value["project_id"], "project-a")
                    self.assertEqual(page_a_value["total"], 1)
                    self.assertEqual(
                        [goal["goal_id"] for goal in page_a_value["goals"]],
                        ["project-a-goal"],
                    )
                    foreign_status = await client_a.call_tool(
                        "goal_status",
                        {"goal_id": "project-b-goal"},
                        meta=_hermes_meta("profile-a"),
                    )
                    self.assertTrue(foreign_status.is_error)

            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
