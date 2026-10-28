"""Least-privilege checks for the local Hermes profile-bound MCP launcher."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
from typing import Callable, TypedDict, cast
import unittest
from unittest.mock import patch

from project_fixtures import (
    TestProjectAccess,
    build_test_profile_mcp,
    create_consumer_repo,
    open_test_profile_mcp,
    register_test_project_access,
    write_consumer_config,
)

from mcp import Client
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
    ProjectPlugin,
    ProjectStatusChangeRequest,
    SQLiteTokenBucket,
    SuccessCriterion,
    hosted_mcp,
)
from curatormd_v2.hosted_mcp import LocalProfileMCP, build_local_profile_mcp
from curatormd_v2.service import _PreparedEvent  # pyright: ignore[reportPrivateUsage]
from curatormd_v2.mcp_server import safe_tool_handler

def hermes_meta(
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


class _InFlightSuspendContext(TypedDict):
    """Bound state for the admitted-write versus suspend race test."""

    runtime: LocalProfileMCP
    entered_effect: Event
    release_effect: Event
    status_started: Event
    plugin: ProjectPlugin
    pause_commit: Callable[
        [EventEnvelope, _PreparedEvent, str | None], EventInboxReceipt
    ]
    event: EventEnvelope
    transition_store: CuratorStore
    manager: ProjectAccessManager
    operator: AuthenticatedCaller


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


class HostedMcpFixtures:  # pylint: disable=too-few-public-methods
    """Shared disposable project setup for hosted MCP process tests."""

    def _project(self, root: Path, project_id: str = "bound-project") -> None:
        create_consumer_repo(root)
        (root / "docs" / "tasks.md").write_text("- [ ] Bounded task\n")
        (root / "persistence" / "HISTORY.md").write_text("# History\n")
        write_consumer_config(root, project_id)

    def _project_database(
        self, temporary: str, project_id: str = "bound-project"
    ) -> tuple[Path, Path]:
        root = Path(temporary) / "consumer"
        self._project(root, project_id)
        return root, Path(temporary) / "global.sqlite3"

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

        store = CuratorStore(database)
        try:
            actions = [ProjectAction.READ]
            if allow_write:
                actions.append(ProjectAction.WRITE)
            if allow_review:
                actions.append(ProjectAction.REVIEW)
            register_test_project_access(
                store,
                root,
                _local_subject(),
                TestProjectAccess(
                    actions=tuple(actions),
                    admin_subject="test-operator",
                    registration_rationale=(
                        "Approve the disposable integration-test project binding"
                    ),
                    grant_rationale=(
                        "Grant the disposable integration-test profile exact access"
                    ),
                ),
            )
        finally:
            store.close()

    def _inflight_suspend_context(
        self, temporary_root: Path
    ) -> _InFlightSuspendContext:
        root = temporary_root / "consumer"
        self._project(root)
        database = temporary_root / "global.sqlite3"
        self._provision(root, database, "gptmd-coding", allow_write=True)
        runtime = build_test_profile_mcp(
            project_root=root,
            database=database,
            allow_write=True,
        )
        entered_effect = Event()
        release_effect = Event()
        status_started = Event()
        plugin = getattr(runtime.api, "_plugins")["bound-project"]
        original_commit_event = cast(
            Callable[
                [EventEnvelope, _PreparedEvent, str | None], EventInboxReceipt
            ],
            getattr(plugin.service, "_commit_event"),
        )
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

        def pause_commit(
            envelope: EventEnvelope,
            prepared: _PreparedEvent,
            lease_owner: str | None,
        ) -> EventInboxReceipt:
            entered_effect.set()
            if not release_effect.wait(timeout=10):
                raise TimeoutError("test did not release the fenced event effect")
            return original_commit_event(envelope, prepared, lease_owner)

        return {
            "runtime": runtime,
            "entered_effect": entered_effect,
            "release_effect": release_effect,
            "status_started": status_started,
            "plugin": plugin,
            "pause_commit": pause_commit,
            "event": event,
            "transition_store": transition_store,
            "manager": manager,
            "operator": operator,
        }



class HostedMcpTests(HostedMcpFixtures, unittest.TestCase):
    """Exercise profile-bound access through the local MCP launcher."""

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
            with open_test_profile_mcp(
                root, database, allow_write=True
            ) as runtime:
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
            runtime = build_test_profile_mcp(
                project_root=root,
                database=database,
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
                            "goal_start", arguments, meta=hermes_meta("gptmd-coding")
                        )
                        self.assertFalse(first.is_error)
                        retry = await client.call_tool(
                            "goal_start", arguments, meta=hermes_meta("gptmd-coding")
                        )
                        self.assertFalse(retry.is_error)

                        changed = dict(arguments)
                        changed["problem"] = "Changed payload must conflict"
                        conflict = await client.call_tool(
                            "goal_start", changed, meta=hermes_meta("gptmd-coding")
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
                            meta=hermes_meta("another-profile"),
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
                            meta=hermes_meta("gptmd-coding"),
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
                            meta=hermes_meta("gptmd-coding"),
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
                                **hermes_meta("gptmd-coding"),
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
            context = self._inflight_suspend_context(Path(temporary))
            try:
                with ThreadPoolExecutor(max_workers=2) as workers:
                    with patch.object(
                        context["plugin"].service,
                        "_commit_event",
                        side_effect=context["pause_commit"],
                    ):
                        write_future = workers.submit(
                            context["runtime"].api.process_event_json,
                            context["runtime"].caller,
                            "bound-project",
                            context["event"].to_json(),
                        )
                        self.assertTrue(
                            context["entered_effect"].wait(timeout=5),
                            str(write_future.exception(timeout=0))
                            if write_future.done()
                            else "event worker did not reach its durable commit",
                        )

                        def suspend_after_effect_admission():
                            context["status_started"].set()
                            registration = context[
                                "transition_store"
                            ].get_project_registration(
                                "bound-project"
                            )
                            return context["manager"].set_project_status(
                                context["operator"],
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
                        self.assertTrue(context["status_started"].wait(timeout=5))
                        self.assertFalse(status_future.done())
                        context["release_effect"].set()
                        receipt = write_future.result(timeout=10)
                        transition = status_future.result(timeout=10)
                self.assertEqual(receipt.status, EventInboxStatus.PROCESSED)
                self.assertEqual(transition.receipt.action, "suspended")
                self.assertEqual(transition.receipt.revision, 2)
                self.assertEqual(transition.registration.status, "suspended")
                self.assertEqual(
                    context["runtime"].api.consumer_source_epoch(
                        context["runtime"].caller,
                        "bound-project",
                        context["event"].event_id,
                    ),
                    1,
                )
                with self.assertRaisesRegex(PermissionError, "not authorized"):
                    context["runtime"].api.consumer_source_epoch(
                        context["runtime"].caller,
                        "bound-project",
                        "unprocessed-event",
                    )
                replayed_receipt = context["runtime"].api.process_event_json(
                    context["runtime"].caller,
                    "bound-project",
                    context["event"].to_json(),
                )
                self.assertEqual(replayed_receipt, receipt)

                changed_event = EventEnvelope(
                    context["event"].event_id,
                    context["event"].project_id,
                    GoalStarted(
                        "fenced-goal",
                        "Changed event payload must not reuse the processed receipt",
                        (SuccessCriterion("recorded", "The event payload changed"),),
                    ),
                )
                with self.assertRaisesRegex(PermissionError, "not authorized"):
                    context["runtime"].api.process_event_json(
                        context["runtime"].caller,
                        "bound-project",
                        changed_event.to_json(),
                    )
            finally:
                context["release_effect"].set()
                context["runtime"].close()
                context["transition_store"].close()


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
                ), patch(
                    "curatormd_v2.hosted_mcp.set_process_privacy_limits"
                ), redirect_stderr(stderr):
                    exit_code = hosted_mcp.main(arguments)

                self.assertEqual(exit_code, 2)
                self.assertIn("startup failed", stderr.getvalue())
                self.assertNotIn("private raw payload marker", stderr.getvalue())
                self.assertNotIn("private-database.sqlite3", stderr.getvalue())
                self.assertNotIn("private SQL fragment", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_launcher_privacy_limits_apply_in_child_process(self) -> None:
        script = """
import json, os, resource
from curatormd_v2.hosted_mcp import set_process_privacy_limits
set_process_privacy_limits()
observed_umask = os.umask(0o077)
print(json.dumps({"umask": observed_umask, "core": resource.getrlimit(resource.RLIMIT_CORE)}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        )
        observed = json.loads(completed.stdout)
        self.assertEqual(observed["umask"], 0o077)
        self.assertEqual(observed["core"], [0, 0])






if __name__ == "__main__":
    unittest.main()
