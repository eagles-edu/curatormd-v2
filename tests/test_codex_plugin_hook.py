"""Focused checks for prompt-safe Curator V2 Codex plugin guidance."""

from __future__ import annotations

import json
import runpy
from importlib import import_module
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Mapping, cast
import unittest
from unittest.mock import Mock, patch

from curatormd_v2.codex_mcp import (
    CODEX_INSTRUCTIONS,
)
from curatormd_v2.project_config import ProjectConfig


ROOT = Path(__file__).resolve().parents[1]
_CODEX_MCP = import_module("curatormd_v2.codex_mcp")
_bound_codex_instructions = getattr(_CODEX_MCP, "_bound_codex_instructions")
_codex_parent_workspace = getattr(_CODEX_MCP, "_codex_parent_workspace")
_load_evidence_verifier = getattr(_CODEX_MCP, "_load_evidence_verifier")
_workspace_root = getattr(_CODEX_MCP, "_workspace_root")
HOOKS_DIR = ROOT / "integrations" / "codex-plugin" / "hooks"
HOOK = HOOKS_DIR / "user_prompt_submit.py"
PRE_TOOL_HOOK = HOOKS_DIR / "lifecycle_pre_tool.py"
POST_TOOL_HOOK = HOOKS_DIR / "lifecycle_post_tool.py"
STOP_HOOK = HOOKS_DIR / "lifecycle_stop.py"
HOOK_INSTALLER = ROOT / "integrations" / "codex-plugin" / "bin" / "install_user_hook.py"
sys.path.insert(0, str(HOOKS_DIR))
_HOOK_MODULE = runpy.run_path(str(HOOK))
_HOOK_INSTALLER_MODULE = runpy.run_path(str(HOOK_INSTALLER))
_MCP_INSTALLER_MODULE = runpy.run_path(
    str(ROOT / "integrations" / "codex-plugin" / "bin" / "install_user_mcp.py")
)
_CONTEXT = _HOOK_MODULE["_context"]
_TASK_SCOPE_CUE = _HOOK_MODULE["_task_scope_cue"]
_TASK_SCOPE_GOAL_ID = _HOOK_MODULE["_task_scope_goal_id"]
_PROTECT_PROMPT_PROCESS = _HOOK_MODULE["_protect_prompt_process"]


class CodexPluginHookTests(unittest.TestCase):
    """Keep the injected instructions bounded and free of prompt contents."""

    def test_context_fits_limit_and_contains_task_and_human_review_rules(self) -> None:
        """Keep automatic task tracking and the human decision boundary in context."""

        context = _CONTEXT("p" * 128, "codex-turn-" + "a" * 32)
        hook_config = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
        limit = hook_config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["additionalContextLimit"]
        self.assertLessEqual(len(context), limit)
        for phrase in (
            "`goal_start.event_id`=",
            "Track nontrivial project work before edits",
            "“Finish the plugin” means work",
            "reuse one clear same-task goal",
            "Repository or topic similarity alone is not a plan match",
            "Plans=parent+child",
            "top-level one-off",
            "Never attach one-off facts to another task",
            "same-task active: read status and record intent, no start/activate",
            '`initial_status="active"`',
            "save intent",
            "Plans=parent+child",
            "follow each item/one-off",
            "`Problem: <problem>. Success: <observable checks>.`",
            "Retry/resume reuse same goal and wording",
            "separated records for one task stay under the same goal ID across pauses/threads; child IDs link to parent",
            "cues are hints",
            "advance only if continuing",
            "At task end, save the observed result",
            "without waiting for separate proof",
            "Propose potentially useful facts for owner review",
            "do not approve or codify on the owner's behalf",
            "Never retain prompts",
            "Claim writes only after success",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, context)
        for cue in (
            "hold",
            "resume",
            "next plan item",
            "end current task or item",
            "begin task",
        ):
            with self.subTest(cue=cue):
                context = _CONTEXT("p" * 128, "codex-turn-" + "a" * 32, cue)
                self.assertLessEqual(len(context), limit)
                self.assertIn("Propose potentially useful facts for owner review", context)
                if cue == "resume":
                    self.assertIn(
                        "`Resuming problem/task: <saved problem/title> [plan item X]. Open checks: <saved checks>.`",
                        context,
                    )
        endpoint_context = _CONTEXT("alpha", "codex-turn-test", "end current task or item")
        self.assertIn("create its pending SDE proposal", endpoint_context)

    def test_explicit_task_scope_prefixes_select_top_level_or_child_lifecycle(self) -> None:
        """Keep owner prefixes visible and distinguish their goal relationships."""

        self.assertEqual(_TASK_SCOPE_CUE("ootask: update the README"), "ootask")
        self.assertEqual(
            _TASK_SCOPE_CUE("ootask add hook activation instructions to the README"),
            "ootask",
        )
        self.assertEqual(_TASK_SCOPE_CUE("  AOTASK parent-alpha: add the toolbox task"), "aotask")
        self.assertEqual(_TASK_SCOPE_CUE("  AATASK: unrelated aside"), "aatask")
        aside = _CONTEXT("project", "codex-turn-aside", scope_cue="aatask")
        self.assertIn("Do not create or update a Curator project goal", aside)
        self.assertNotIn("Track nontrivial project work before edits", aside)
        self.assertIsNone(_TASK_SCOPE_GOAL_ID("ootask: update the README"))
        self.assertEqual(
            _TASK_SCOPE_GOAL_ID("  AOTASK parent-alpha: add the toolbox task"),
            "parent-alpha",
        )
        self.assertIsNone(_TASK_SCOPE_CUE("please update the README"))
        standalone = _CONTEXT("project", "codex-turn-standalone", scope_cue="ootask")
        self.assertIn("distinct one-off", standalone)
        self.assertIn("own criteria, facts, checks, and lifecycle", standalone)
        self.assertIn("defer that exact item", standalone)
        self.assertIn("reactivate the previously paused item", standalone)
        self.assertIn("Never attach one-off facts", standalone)
        addon = _CONTEXT("project", "codex-turn-addon", scope_cue="aotask")
        self.assertIn("same implicit goal ID", addon)
        self.assertNotIn("must name the goal ID", addon)
        self.assertIn("Do not create another goal", addon)
        targeted_addon = _CONTEXT(
            "project", "codex-turn-addon", scope_cue="aotask",
            scope_goal_id="parent-alpha",
        )
        self.assertIn("goal_id=parent-alpha", targeted_addon)
        self.assertIn("keep its same ID", targeted_addon)

    def test_plugin_bundles_the_mcp_server_whose_tools_have_approval_rules(self) -> None:
        """Bind approval policy to the actual plugin server name."""

        plugin = json.loads(
            (ROOT / "integrations" / "codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        openai_extension = plugin["extensions"]["com.openai"]
        prompt = openai_extension["interface"]["defaultPrompt"]
        self.assertTrue(any("read the goal back after writes" in item for item in prompt))
        hooks_path = openai_extension["hooks"]
        self.assertEqual(hooks_path, "./hooks/hooks.json")
        hooks = json.loads(
            (ROOT / "integrations" / "codex-plugin" / hooks_path.removeprefix("./"))
            .read_text(encoding="utf-8")
        )["hooks"]
        self.assertEqual(
            set(hooks), {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
        )
        server_config = json.loads(
            (ROOT / "integrations" / "codex-plugin" / "mcp.json").read_text(
                encoding="utf-8"
            )
        )
        configured_servers = plugin.get("mcpServers", server_config["mcpServers"])
        self.assertIn("codex-intake", configured_servers)
        server = configured_servers["codex-intake"]
        self.assertEqual(server["type"], "stdio")
        self.assertIn("--allow-write", server["args"])
        database_arg = server["args"][
            server["args"].index("--database-bindings") + 1
        ]
        self.assertEqual(
            database_arg, "~/.config/curatormd-v2/database-bindings.json"
        )
        self.assertNotIn("--project-root", server["args"])
        self.assertNotIn("--evidence-config", server["args"])
        self.assertNotIn("cwd", server)

        launcher = ROOT / "integrations" / "codex-plugin" / "bin" / "launch-curator-mcp.py"
        launcher_namespace = runpy.run_path(
            str(launcher), run_name="curator_v2_codex_launcher_test"
        )
        with patch.dict(os.environ, {"PATH": ""}, clear=True):
            self.assertEqual(
                launcher_namespace["_v2_mcp_path"](),
                ROOT / ".venv" / "bin" / "curatormd-v2-codex-mcp",
            )

    def test_cached_launcher_finds_installed_executable(self) -> None:
        """A copied plugin cache must not treat its parent as the checkout."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            cached = root / "cache" / "market" / "plugin" / "version" / "bin"
            cached.mkdir(parents=True)
            launcher = cached / "launch-curator-mcp.py"
            launcher.write_text(
                (ROOT / "integrations" / "codex-plugin" / "bin" / launcher.name)
                .read_text(encoding="utf-8"), encoding="utf-8"
            )
            installed = root / "bin" / "curatormd-v2-codex-mcp"
            installed.parent.mkdir()
            installed.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            installed.chmod(0o700)
            namespace = runpy.run_path(str(launcher), run_name="cached_launcher_test")
            with patch.dict(os.environ, {"PATH": str(installed.parent)}, clear=True):
                self.assertEqual(namespace["_v2_mcp_path"](), installed)
            with patch.dict(os.environ, {"CURATOR_V2_CODEX_MCP": "relative"}, clear=True):
                self.assertIsNone(namespace["_v2_mcp_path"]())

    def test_plugin_bundles_prompt_and_lifecycle_hooks(self) -> None:
        """Install intake and endpoint checks with the plugin, not separately."""

        hooks = json.loads(
            (ROOT / "integrations" / "codex-plugin" / "hooks" / "hooks.json")
            .read_text(encoding="utf-8")
        )["hooks"]
        self.assertEqual(
            set(hooks), {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
        )
        prompt_handler = hooks["UserPromptSubmit"][0]["hooks"][0]
        self.assertIn("${PLUGIN_ROOT}/hooks/user_prompt_submit.py", prompt_handler["command"])
        self.assertEqual(prompt_handler["additionalContextLimit"], 4096)
        pre_handler = hooks["PreToolUse"][0]
        self.assertEqual(
            pre_handler["matcher"],
            "^(?:Bash|apply_patch|Edit|Write|mcp__codex[-_]intake__(?:goal_start|goal_activate|goal_finish|goal_defer|fact_record|sde_assess|sde_record_user_report))$",
        )
        self.assertIn("lifecycle_pre_tool.py", pre_handler["hooks"][0]["command"])
        self.assertIn("lifecycle_post_tool.py", hooks["PostToolUse"][0]["hooks"][0]["command"])
        self.assertIn(
            "fact_record|sde_assess|sde_record_user_report",
            hooks["PostToolUse"][0]["matcher"],
        )
        self.assertIn("sde_review_detail", hooks["PostToolUse"][0]["matcher"])
        self.assertIn("goal_report", hooks["PostToolUse"][0]["matcher"])
        self.assertIn("lifecycle_stop.py", hooks["Stop"][0]["hooks"][0]["command"])

    def test_codex_mcp_loads_only_host_evidence_config_outside_project(self) -> None:
        """Bind receipt verification to the owner file and active project ID."""

        with TemporaryDirectory() as directory:
            project_root = Path(directory) / "project"
            project_root.mkdir()
            host_config = Path(directory) / "host-evidence.json"
            host_config.write_text("{}", encoding="utf-8")
            with (
                patch("curatormd_v2.codex_mcp.validate_host_evidence_config_path") as validate,
                patch("curatormd_v2.codex_mcp.load_local_evidence_verifier") as load,
            ):
                validate.return_value = host_config
                load.return_value = object()
                verifier = _load_evidence_verifier(host_config, project_root, "alpha")

        self.assertIsNotNone(verifier)
        validate.assert_called_once_with(host_config, project_root)
        load.assert_called_once_with(host_config, project_id="alpha")

    def test_codex_mcp_selects_evidence_for_the_active_project(self) -> None:
        """Discover only the active project's owner-managed evidence file."""

        with TemporaryDirectory() as directory:
            home = Path(directory)
            project_root = home / "project"
            project_root.mkdir()
            evidence_dir = home / ".config" / "curatormd-v2"
            evidence_dir.mkdir(parents=True)
            selected = evidence_dir / "alpha-evidence.json"
            selected.write_text("{}", encoding="utf-8")
            with (
                patch("curatormd_v2.codex_mcp.Path.home", return_value=home),
                patch("curatormd_v2.codex_mcp.validate_host_evidence_config_path") as validate,
                patch("curatormd_v2.codex_mcp.load_local_evidence_verifier") as load,
            ):
                validate.return_value = selected
                load.return_value = object()
                self.assertIsNotNone(_load_evidence_verifier(None, project_root, "alpha"))
                self.assertIsNone(_load_evidence_verifier(None, project_root, "other"))
        validate.assert_called_once_with(selected, project_root)
        load.assert_called_once_with(selected, project_id="alpha")

    def test_hook_does_not_echo_or_retain_submitted_prompt(self) -> None:
        """The hook uses workspace binding, never the submitted prompt body."""

        prompt = "private prompt sentinel"
        turn_id = "private-turn-sentinel"
        with TemporaryDirectory() as directory:
            Path(directory, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps({"cwd": directory, "prompt": prompt, "turn_id": turn_id}),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(prompt, result.stdout)
        self.assertNotIn(turn_id, result.stdout)
        response = json.loads(result.stdout)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Curator V2;", context)
        self.assertIn("Track nontrivial project work before edits", context)
        self.assertIn(
            _HOOK_MODULE["_source_event_id"](turn_id),
            context,
        )

    def test_hook_classifies_lifecycle_wording_without_echoing_prompt(self) -> None:
        """Give Codex a focused cue while keeping prompt text out of its reply."""

        classify = _HOOK_MODULE["_transition_cue"]
        cases = {
            "Please put this task on hold": "hold",
            "Pause here": "hold",
            "I'm holding this until tomorrow": "hold",
            "Park this issue for now": "hold",
            "Leave this open for now": "hold",
            "Put this on the back burner": "hold",
            "Let's leave this for later": "hold",
            "Suspend work on this for now": "hold",
            "Come back to this next time": "hold",
            "Leave this here for now": "hold",
            "Skip this task until later": "hold",
            "Let's table this item for now": "hold",
            "Put this on ice until tomorrow": "hold",
            "Let's continue the current task": "resume",
            "Back to this plan item": "resume",
            "Carry on with this task": "resume",
            "Let's get back to this task": "resume",
            "We're back": "resume",
            "Pick this up again": "resume",
            "Move to the next item": "next plan item",
            "Move on to the next item": "next plan item",
            "Move on after this": "next plan item",
            "Take the following step": "next plan item",
            "On to the next item": "next plan item",
            "Next up, the next task": "next plan item",
            "Check it off and move on": "next plan item",
            "Let's close things to move ahead": "next plan item",
            "Clear the next 10 unfinished items": "next plan item",
            "Move on": "next plan item",
            "Finish this task": "begin task",
            "Finish the plugin today": "begin task",
            "Complete this task by fixing the intake flow": "begin task",
            "The plugin should learn phrases like 'put this on hold' and 'check this item off'": "ordinary work or progress",
            "When Codex says 'done with this item', it should prepare an SDE": "ordinary work or progress",
            "Done.": "end current task or item",
            "I finished the one-off task": "end current task or item",
            "Mark this item complete": "end current task or item",
            "Check it off": "end current task or item",
            "It's completed": "end current task or item",
            "Done with this": "end current task or item",
            "We're all done": "end current task or item",
            "Call this complete": "end current task or item",
            "Wrap up this item": "end current task or item",
            "Work item closed out": "end current task or item",
            "We've wrapped up this item": "end current task or item",
            "Implement the retry logic": "begin task",
            "Tackle the queue bug": "begin task",
            "Let's fix the task intake": "begin task",
            "Please begin the task intake repair": "begin task",
            "The repair has begun": "begin task",
            "Let's address the task intake": "begin task",
            "Work through the retry logic": "begin task",
            "Can you get this working": "begin task",
            "Don't pause this task": "ordinary work or progress",
            "We can't close this task yet": "ordinary work or progress",
            "Do not check it off yet": "ordinary work or progress",
            "This task hasn't begun yet": "ordinary work or progress",
            "Don't mark this item complete": "ordinary work or progress",
            "Is this task complete?": "ordinary work or progress",
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(classify(prompt), expected)

        prompt = "Please pause this private task canary"
        with TemporaryDirectory() as directory:
            Path(directory, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps({"cwd": directory, "prompt": prompt}),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
            )

        response = json.loads(result.stdout)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("TURN=HOLD", context)
        self.assertIn("goal_defer", context)
        self.assertNotIn(prompt, context)
        self.assertNotIn("private task canary", context)

    def test_existing_goal_can_bootstrap_a_fresh_turn(self) -> None:
        """Permit the MCP reads and intent write needed to unlock local work."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            (workspace / ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            env = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {"cwd": str(workspace), "session_id": "session", "turn_id": "turn"}

            def invoke(script: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)], input=json.dumps(base | event),
                    capture_output=True, check=False, text=True, timeout=3, env=env,
                )

            for tool in ("goal_list_page", "goal_status", "fact_record"):
                result = invoke(PRE_TOOL_HOOK, {"tool_name": f"mcp__codex-intake__{tool}"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
            blocked = invoke(PRE_TOOL_HOOK, {"tool_name": "Bash"})
            reason = json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn("disable the Curator PreToolUse hook", reason)
            self.assertIn("do not call goal_start or goal_activate", reason)

            status = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "existing-goal"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"goal":{"goal_id":"existing-goal","status":"active"}}',
                }]},
            })
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertTrue(invoke(PRE_TOOL_HOOK, {"tool_name": "Bash"}).stdout)
            recorded = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "existing-goal", "kind": "intent"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"event_id":"intent","status":"processed"}',
                }]},
            })
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            self.assertEqual(invoke(PRE_TOOL_HOOK, {"tool_name": "Bash"}).stdout, "")

    def test_fact_record_is_blocked_after_goal_completion_readback(self) -> None:
        """Avoid failed fact events when the agent continues after finishing a goal."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            (workspace / ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            env = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "completed-goal-session",
                "turn_id": "completed-goal-turn",
            }

            def invoke(script: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps(base | event),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=env,
                )

            finish = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_finish",
                "tool_input": {"goal_id": "goal-completed"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"finish-event","status":"processed"}',
                }]},
            })
            self.assertEqual(finish.returncode, 0, finish.stderr)
            status = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-completed"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "goal": {"goal_id": "goal-completed", "status": "complete"},
                    }),
                }]},
            })
            self.assertEqual(status.returncode, 0, status.stderr)

            blocked = invoke(PRE_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "goal-completed", "kind": "research"},
            })
            self.assertEqual(blocked.returncode, 0, blocked.stderr)
            response = json.loads(blocked.stdout)
            self.assertEqual(
                response["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertIn(
                "Do not append facts to a terminal goal",
                response["hookSpecificOutput"]["permissionDecisionReason"],
            )

            base["turn_id"] = "completed-goal-next-turn"
            readback = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-completed"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "goal": {"goal_id": "goal-completed", "status": "complete"},
                    }),
                }]},
            })
            self.assertEqual(readback.returncode, 0, readback.stderr)
            next_turn_blocked = invoke(PRE_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "goal-completed", "kind": "intent"},
            })
            self.assertEqual(next_turn_blocked.returncode, 0, next_turn_blocked.stderr)
            next_turn_response = json.loads(next_turn_blocked.stdout)
            self.assertEqual(
                next_turn_response["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )
            self.assertIn(
                "confirm this exact goal is active",
                next_turn_response["hookSpecificOutput"]["permissionDecisionReason"],
            )

    def test_verification_fact_requires_matching_configured_capture(self) -> None:
        """Block hand-built evidence references before they become failed events."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            (workspace / ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            env = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "verification-session",
                "turn_id": "verification-turn",
            }

            def invoke(script: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps(base | event),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=env,
                )

            status = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-evidence"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "goal": {"goal_id": "goal-evidence", "status": "active"},
                    }),
                }]},
            })
            self.assertEqual(status.returncode, 0, status.stderr)

            evidence = {
                "evidence_kind": "repository_test",
                "locator": "test-run:alpha",
                "sha256": "a" * 64,
                "outcome": "passed",
                "occurrence_id": "occurrence-alpha",
            }
            fact_input = {
                "goal_id": "goal-evidence",
                "kind": "verification",
                "criterion_id": "criterion-alpha",
                "evidence": [evidence],
            }
            blocked = invoke(PRE_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": fact_input,
            })
            self.assertEqual(blocked.returncode, 0, blocked.stderr)
            self.assertIn(
                "must use a passing reference returned by",
                json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecisionReason"],
            )

            captured = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__evidence_capture",
                "tool_input": {
                    "goal_id": "goal-evidence",
                    "criterion_id": "criterion-alpha",
                    "evidence_kind": evidence["evidence_kind"],
                    "locator": evidence["locator"],
                },
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": json.dumps(evidence),
                }]},
            })
            self.assertEqual(captured.returncode, 0, captured.stderr)
            self.assertEqual(invoke(PRE_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": fact_input,
            }).stdout, "")

            altered = fact_input | {"evidence": [evidence | {"sha256": "b" * 64}]}
            altered_result = invoke(PRE_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": altered,
            })
            self.assertIn(
                "must use a passing reference returned by",
                json.loads(altered_result.stdout)["hookSpecificOutput"]["permissionDecisionReason"],
            )

            state_text = next((state_root / "task-state").glob("turn-*.json")).read_text(
                encoding="utf-8"
            )
            self.assertNotIn(evidence["locator"], state_text)
            self.assertNotIn(evidence["sha256"], state_text)

    def test_open_goal_can_retry_finish_after_checkpoint_fact(self) -> None:
        """Keep a still-open task eligible for its next finish attempt."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            (workspace / ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            env = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "open-goal-session",
                "turn_id": "open-goal-turn",
            }

            def invoke(script: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps(base | event),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=env,
                )

            status = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-open"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "goal": {"goal_id": "goal-open", "status": "open"},
                        "facts": [{"bullet": "x" * (17 * 1024)}],
                    }),
                }]},
            })
            self.assertEqual(status.returncode, 0, status.stderr)
            fact = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "goal-open", "kind": "change"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"status":"processed"}',
                }]},
            })
            self.assertEqual(fact.returncode, 0, fact.stderr)

            finish = invoke(PRE_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_finish",
                "tool_input": {"goal_id": "goal-open"},
            })

            self.assertEqual(finish.stdout, "")

    def test_local_work_waits_for_a_server_confirmed_active_goal(self) -> None:
        """Block shell/edit tools until this turn has an active Curator goal."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            Path(workspace, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            environment = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "session-canary",
                "turn_id": "turn-one",
            }

            def invoke(script: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps(event),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )

            blocked = invoke(PRE_TOOL_HOOK, {**base, "tool_name": "Bash"})
            self.assertEqual(blocked.returncode, 0, blocked.stderr)
            self.assertEqual(
                json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

            finish_without_fact = invoke(PRE_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__goal_finish",
                "tool_input": {"goal_id": "goal-alpha"},
            })
            self.assertEqual(
                json.loads(finish_without_fact.stdout)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )

            started = invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex_intake__goal_start",
                "tool_input": {
                    "goal_id": "goal-alpha",
                    "initial_status": "active",
                    "problem": "private prompt body canary",
                    "success_criteria": ["private criteria canary"],
                },
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"event-alpha","status":"processed",'
                    '"debug":"private tool response canary"}',
                }]},
            })
            self.assertEqual(started.returncode, 0, started.stderr)

            still_blocked = invoke(PRE_TOOL_HOOK, {**base, "tool_name": "apply_patch"})
            self.assertEqual(
                json.loads(still_blocked.stdout)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )

            recorded = invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {
                    "goal_id": "goal-alpha",
                    "fact_id": "fact-alpha",
                    "bullet": "private fact body canary",
                },
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"event_id":"event-fact","status":"processed"}',
                }]},
            })
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            allowed = invoke(PRE_TOOL_HOOK, {**base, "tool_name": "apply_patch"})
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(allowed.stdout, "")

            summary = invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {
                    "goal_id": "goal-alpha",
                    "kind": "change",
                    "bullet": "Task summary: implementation completed from fact-alpha",
                },
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"event_id":"summary-alpha","status":"processed"}',
                }]},
            })
            self.assertEqual(summary.returncode, 0, summary.stderr)
            summary_readback = invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__goal_report",
                "tool_input": {"goal_id": "goal-alpha", "fact_limit": 16},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": "# Goal `goal-alpha`\nTask summary: implementation completed from fact-alpha",
                }]},
            })
            self.assertEqual(summary_readback.returncode, 0, summary_readback.stderr)

            new_turn = invoke(PRE_TOOL_HOOK, {
                **base, "turn_id": "turn-two", "tool_name": "Bash",
            })
            self.assertEqual(
                json.loads(new_turn.stdout)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

            finished = invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex_intake__goal_finish",
                "tool_input": {"goal_id": "goal-alpha"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"event_id":"event-finish","status":"processed"}',
                }]},
            })
            self.assertEqual(finished.returncode, 0, finished.stderr)
            while_finishing = invoke(PRE_TOOL_HOOK, {**base, "tool_name": "Bash"})
            self.assertIn(
                "goal status readback",
                json.loads(while_finishing.stdout)["hookSpecificOutput"][
                    "permissionDecisionReason"
                ],
            )
            finish_request_state = json.loads(
                next((state_root / "task-state").glob("turn-*.json")).read_text()
            )
            self.assertEqual(finish_request_state["active_goal_ids"], ["goal-alpha"])
            self.assertEqual(
                finish_request_state["finish_requested_goal_ids"], ["goal-alpha"]
            )

            status = invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex_intake__goal_status",
                "tool_input": {"goal_id": "goal-alpha"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"goal-alpha","status":"complete"}}',
                }]},
            })
            self.assertEqual(status.returncode, 0, status.stderr)
            finish_allowed = invoke(PRE_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__goal_finish",
                "tool_input": {"goal_id": "goal-alpha"},
            })
            self.assertEqual(
                json.loads(finish_allowed.stdout)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )
            pending_state = json.loads(
                next((state_root / "task-state").glob("turn-*.json")).read_text()
            )
            self.assertEqual(pending_state["summary_ready_goal_ids"], [])
            self.assertNotIn("pending_sde_goal_ids", pending_state)
            self.assertNotIn("private fact body canary", json.dumps(pending_state))
            after_finish = invoke(PRE_TOOL_HOOK, {**base, "tool_name": "Bash"})
            self.assertEqual(
                json.loads(after_finish.stdout)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )
            state_files = list((state_root / "task-state").glob("turn-*.json"))
            self.assertEqual(len(state_files), 1)
            self.assertEqual(json.loads(state_files[0].read_text()), {
                "project_id": "alpha",
                "active_goal_ids": [],
                "completed_goal_ids": ["goal-alpha"],
                "captured_evidence_fingerprints": [],
                "fact_recorded_goal_ids": [],
                "finish_requested_goal_ids": [],
                "defer_requested_goal_ids": [],
                "report_pending_goal_ids": [],
                "summary_fact_goal_ids": [],
                "summary_invalidated_goal_ids": [],
                "summary_ready_goal_ids": [],
                "prompt_cues": [],
                "task_scope_cues": [],
                "task_scope_target_goal_ids": [],
                "scope_valid_goal_ids": [],
                "ootask_paused_goal_ids": [],
                "ootask_goal_ids": [],
                "ootask_sde_candidate_pairs": [],
                "ootask_sde_reviewed_candidate_pairs": [],
                "sde_proposal_goal_ids": [],
                "sde_candidate_pairs": [],
                "sde_reviewed_candidate_pairs": [],
                "stop_prompted_stages": [],
            })
            serialized_state = state_files[0].read_text()
            for private_value in (
                "private prompt body canary",
                "private criteria canary",
                "private tool response canary",
                "private fact body canary",
                "private proposal text",
            ):
                self.assertNotIn(private_value, serialized_state)

    def test_explicit_scope_prefixes_guard_goal_start_and_addon_lifecycle(self) -> None:
        """Keep one-offs distinct and route add-ons to an existing goal ID."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            Path(workspace, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            environment = os.environ | {"PLUGIN_DATA": str(state_root)}
            base: dict[str, object] = {
                "cwd": str(workspace), "session_id": "scope-session",
            }

            def invoke(
                script: Path, event: Mapping[str, object]
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps(dict(event)), capture_output=True, check=False,
                    text=True, timeout=3, env=environment,
                )

            aside_turn = base | {"turn_id": "aside-turn"}
            aside = invoke(HOOK, aside_turn | {"prompt": "aatask: check unrelated weather"})
            self.assertIn("SCOPE=AATASK", aside.stdout)
            work = invoke(PRE_TOOL_HOOK, aside_turn | {"tool_name": "Bash"})
            self.assertEqual(work.stdout, "")
            empty_tool_input: dict[str, object] = {}
            for tool in ("goal_start", "fact_record", "sde_assess"):
                denied = invoke(PRE_TOOL_HOOK, aside_turn | {
                    "tool_name": f"mcp__codex-intake__{tool}", "tool_input": empty_tool_input,
                })
                self.assertEqual(json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            stopped = invoke(STOP_HOOK, aside_turn | {"last_assistant_message": "The aside is done."})
            self.assertEqual(stopped.stdout, "")

            oneoff_turn = base | {"turn_id": "ootask-turn"}
            prompt = invoke(HOOK, oneoff_turn | {
                "prompt": "ootask add the repository README hook activation instructions",
            })
            self.assertEqual(prompt.returncode, 0, prompt.stderr)
            oneoff_state = next(
                state_text
                for path in (state_root / "task-state").glob("turn-*.json")
                if '"task_scope_cues":["ootask"]'
                in (state_text := path.read_text(encoding="utf-8"))
            )
            self.assertNotIn(
                "ootask add the repository README hook activation instructions",
                oneoff_state,
            )
            oneoff_start = invoke(PRE_TOOL_HOOK, oneoff_turn | {
                "tool_name": "mcp__codex-intake__goal_start",
                "tool_input": {"goal_id": "oneoff-alpha", "initial_status": "active", "parent_goal_id": "parent-alpha"},
            })
            self.assertEqual(oneoff_start.stdout, "")
            wrong_parent_status = invoke(POST_TOOL_HOOK, oneoff_turn | {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "parent-alpha"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"parent-alpha","status":"active",'
                    '"parent_goal_id":null}}',
                }]},
            })
            self.assertEqual(wrong_parent_status.returncode, 0, wrong_parent_status.stderr)
            parent_fact = invoke(POST_TOOL_HOOK, oneoff_turn | {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "parent-alpha", "kind": "intent"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"status":"processed"}',
                }]},
            })
            self.assertEqual(parent_fact.returncode, 0, parent_fact.stderr)
            self.assertNotEqual(
                invoke(PRE_TOOL_HOOK, oneoff_turn | {"tool_name": "Bash"}).stdout,
                "",
            )
            oneoff_started = invoke(POST_TOOL_HOOK, oneoff_turn | {
                "tool_name": "mcp__codex-intake__goal_start",
                "tool_input": {
                    "goal_id": "oneoff-alpha", "initial_status": "active",
                    "parent_goal_id": "parent-alpha",
                },
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"status":"processed"}',
                }]},
            })
            self.assertEqual(oneoff_started.returncode, 0, oneoff_started.stderr)
            oneoff_status = invoke(POST_TOOL_HOOK, oneoff_turn | {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "oneoff-alpha"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"oneoff-alpha","status":"active",'
                    '"parent_goal_id":"parent-alpha"}}',
                }]},
            })
            self.assertEqual(oneoff_status.returncode, 0, oneoff_status.stderr)
            registry_state_path = next((state_root / "task-state").glob("ootasks-*.json"))
            registry_state = registry_state_path.read_text(encoding="utf-8")
            self.assertIn('"ootask_goal_ids":["oneoff-alpha"]', registry_state)
            self.assertNotIn("parent-alpha", registry_state)
            oneoff_fact = invoke(POST_TOOL_HOOK, oneoff_turn | {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "oneoff-alpha", "kind": "intent"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"status":"processed"}',
                }]},
            })
            self.assertEqual(oneoff_fact.returncode, 0, oneoff_fact.stderr)
            self.assertEqual(
                invoke(PRE_TOOL_HOOK, oneoff_turn | {"tool_name": "Bash"}).stdout,
                "",
            )
            resumed_oneoff_turn = {
                "cwd": str(workspace), "session_id": "new-session",
                "turn_id": "resume-ootask-turn",
            }
            resumed_prompt = invoke(HOOK, resumed_oneoff_turn | {
                "prompt": "ootask: continue the repository README task",
            })
            self.assertEqual(resumed_prompt.returncode, 0, resumed_prompt.stderr)
            resumed_status = invoke(POST_TOOL_HOOK, resumed_oneoff_turn | {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "oneoff-alpha"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"oneoff-alpha","status":"active",'
                    '"parent_goal_id":"parent-alpha"}}',
                }]},
            })
            self.assertEqual(resumed_status.returncode, 0, resumed_status.stderr)
            resumed_intent = invoke(POST_TOOL_HOOK, resumed_oneoff_turn | {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "oneoff-alpha", "kind": "intent"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"status":"processed"}',
                }]},
            })
            self.assertEqual(resumed_intent.returncode, 0, resumed_intent.stderr)
            self.assertEqual(
                invoke(PRE_TOOL_HOOK, resumed_oneoff_turn | {"tool_name": "Bash"}).stdout,
                "",
            )

            addon_turn = base | {"turn_id": "aotask-turn"}
            addon_prompt = invoke(HOOK, addon_turn | {
                "prompt": "aotask parent-alpha: add a bounded toolbox task",
            })
            self.assertEqual(addon_prompt.returncode, 0, addon_prompt.stderr)
            scope_state = next(
                state_text
                for scope_path in (state_root / "task-state").glob("turn-*.json")
                if '"task_scope_target_goal_ids":["parent-alpha"]'
                in (state_text := scope_path.read_text(encoding="utf-8"))
            )
            self.assertIn('"task_scope_target_goal_ids":["parent-alpha"]', scope_state)
            self.assertNotIn("aotask parent-alpha: add a bounded toolbox task", scope_state)
            addon_wrong = invoke(PRE_TOOL_HOOK, addon_turn | {
                "tool_name": "mcp__codex-intake__goal_start",
                "tool_input": {"initial_status": "active", "parent_goal_id": "parent-alpha"},
            })
            self.assertEqual(
                json.loads(addon_wrong.stdout)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )
            mismatched_activation = invoke(PRE_TOOL_HOOK, addon_turn | {
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "addon-alpha"},
            })
            self.assertEqual(
                json.loads(mismatched_activation.stdout)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )
            wrong_addon_status = invoke(POST_TOOL_HOOK, addon_turn | {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "addon-alpha"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"addon-alpha","status":"active",'
                    '"parent_goal_id":"parent-alpha"}}',
                }]},
            })
            self.assertEqual(wrong_addon_status.returncode, 0, wrong_addon_status.stderr)
            self.assertNotEqual(
                invoke(PRE_TOOL_HOOK, addon_turn | {"tool_name": "Bash"}).stdout,
                "",
            )
            wrong_fact = invoke(POST_TOOL_HOOK, addon_turn | {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "addon-alpha", "kind": "intent"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"status":"processed"}',
                }]},
            })
            self.assertEqual(wrong_fact.returncode, 0, wrong_fact.stderr)
            self.assertNotEqual(
                invoke(PRE_TOOL_HOOK, addon_turn | {"tool_name": "Bash"}).stdout,
                "",
            )
            mismatched_finish = invoke(PRE_TOOL_HOOK, addon_turn | {
                "tool_name": "mcp__codex-intake__goal_finish",
                "tool_input": {"goal_id": "addon-alpha"},
            })
            self.assertEqual(
                json.loads(mismatched_finish.stdout)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )
            addon_status = invoke(POST_TOOL_HOOK, addon_turn | {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "parent-alpha"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"parent-alpha","status":"active",'
                    '"parent_goal_id":null}}',
                }]},
            })
            self.assertEqual(addon_status.returncode, 0, addon_status.stderr)
            recorded = invoke(POST_TOOL_HOOK, addon_turn | {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "parent-alpha", "kind": "intent"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"status":"processed"}',
                }]},
            })
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            self.assertEqual(
                invoke(PRE_TOOL_HOOK, addon_turn | {"tool_name": "Bash"}).stdout,
                "",
            )

    def test_stop_hook_completes_lifecycle_cues_before_ending_turn(self) -> None:
        """Require the matching lifecycle write after Codex states a transition."""

        with TemporaryDirectory() as directory:
            Path(directory, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            environment = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": directory,
                "session_id": "session-lifecycle",
                "turn_id": "turn-lifecycle",
            }

            def invoke(message: str, *, active: bool = False) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(STOP_HOOK)],
                    input=json.dumps({
                        **base,
                        "last_assistant_message": message,
                        "stop_hook_active": active,
                    }),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )

            next_item = invoke("I am moving to the next item.")
            self.assertEqual(next_item.returncode, 0, next_item.stderr)
            response = json.loads(next_item.stdout)
            self.assertEqual(response["decision"], "block")
            self.assertIn("finish it only if its checks pass", response["reason"])
            self.assertIn("create a pending SDE proposal", response["reason"])
            self.assertTrue((state_root / "task-state").is_dir())

            negated = invoke("I will not mark this item complete yet.")
            self.assertEqual(negated.stdout, "")
            already_continuing = invoke("I am moving to the next item.", active=True)
            self.assertEqual(already_continuing.stdout, "")

    def test_stop_hook_does_not_require_report_readback_after_fact_write(self) -> None:
        """A successful fact write does not require a redundant report read."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            Path(workspace, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            environment = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "session-report",
                "turn_id": "turn-report",
            }

            def invoke(script: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps({**base, **event}),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )

            fact = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "goal-report", "fact_id": "fact-report"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": '{"event_id":"event-report","status":"processed"}',
                }]},
            })
            self.assertEqual(fact.returncode, 0, fact.stderr)
            pending = invoke(STOP_HOOK, {})
            self.assertEqual(pending.stdout, "")

            unrelated = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_report",
                "tool_input": {"goal_id": "another-goal"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": "# Goal " + chr(96) + "another-goal" + chr(96),
                }]},
            })
            self.assertEqual(unrelated.returncode, 0, unrelated.stderr)
            still_pending = json.loads(
                next((state_root / "task-state").glob("turn-*.json")).read_text()
            )
            self.assertEqual(still_pending["report_pending_goal_ids"], ["goal-report"])

            report = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_report",
                "tool_input": {"goal_id": "goal-report", "fact_limit": 16},
                "tool_response": {"isError": False, "content": [{
                    "type": "text", "text": "# Goal " + chr(96) + "goal-report" + chr(96) + "\n- Fact fact-report",
                }]},
            })
            self.assertEqual(report.returncode, 0, report.stderr)
            cleared = json.loads(
                next((state_root / "task-state").glob("turn-*.json")).read_text()
            )
            self.assertEqual(cleared["report_pending_goal_ids"], [])
            after_readback = invoke(STOP_HOOK, {})
            self.assertEqual(after_readback.stdout, "")

    def test_stop_hook_uses_user_transition_when_codex_omits_it(self) -> None:
        """Keep ordinary user lifecycle wording active through the turn endpoint."""

        cases = (
            ("Please begin this task", "begin task", "create or activate"),
            ("Put this task on hold", "hold", "save a checkpoint and defer"),
            ("Continue this task", "resume", "activate the matching task"),
            ("Check this item off and move to the next item", "next plan item", "verify and record"),
            ("Done with this task", "end current task or item", "verify and record"),
        )
        for index, (prompt, cue, expected_action) in enumerate(cases):
            with self.subTest(cue=cue), TemporaryDirectory() as directory:
                workspace = Path(directory) / "workspace"
                workspace.mkdir()
                Path(workspace, ".curatormd-v2.toml").write_text(
                    'project_id = "alpha"\n', encoding="utf-8"
                )
                state_root = Path(directory) / "plugin-data"
                state_root.mkdir(mode=0o700)
                environment = os.environ | {"PLUGIN_DATA": str(state_root)}
                base = {
                    "cwd": str(workspace),
                    "session_id": f"session-user-cue-{index}",
                    "turn_id": f"turn-user-cue-{index}",
                }
                submitted = subprocess.run(
                    [sys.executable, str(HOOK)],
                    input=json.dumps({**base, "prompt": prompt}),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )
                self.assertEqual(submitted.returncode, 0, submitted.stderr)
                self.assertNotIn(prompt, submitted.stdout)
                state_file = next((state_root / "task-state").glob("turn-*.json"))
                state_text = state_file.read_text(encoding="utf-8")
                state = json.loads(state_text)
                self.assertEqual(state["prompt_cues"], [cue])
                self.assertNotIn(prompt, state_text)

                stopped = subprocess.run(
                    [sys.executable, str(STOP_HOOK)],
                    input=json.dumps({
                        **base,
                        "last_assistant_message": "I have noted the request.",
                        "stop_hook_active": False,
                    }),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )
                self.assertEqual(stopped.returncode, 0, stopped.stderr)
                response = json.loads(stopped.stdout)
                self.assertEqual(response["decision"], "block")
                self.assertIn(expected_action, response["reason"])

    def test_stop_hook_requires_pending_sde_proposal_after_goal_finish(self) -> None:
        """Require the completed goal's supported facts to reach owner review."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            Path(workspace, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            environment = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "session-sde",
                "turn_id": "turn-sde",
            }
            for tool_name, tool_input, result_text in (
                (
                    "mcp__codex-intake__goal_start",
                    {"goal_id": "goal-sde", "initial_status": "active"},
                    '{"event_id":"start-sde","status":"processed"}',
                ),
                (
                    "mcp__codex-intake__fact_record",
                    {
                        "goal_id": "goal-sde",
                        "kind": "change",
                        "bullet": "Task summary: completed from saved facts",
                    },
                    '{"event_id":"summary-sde","status":"processed"}',
                ),
                (
                    "mcp__codex-intake__goal_report",
                    {"goal_id": "goal-sde"},
                    "# Goal `goal-sde`\nTask summary: completed from saved facts",
                ),
            ):
                recorded = subprocess.run(
                    [sys.executable, str(POST_TOOL_HOOK)],
                    input=json.dumps({
                        **base,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_response": {"isError": False, "content": [{
                            "type": "text", "text": result_text,
                        }]},
                    }),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
            finished = subprocess.run(
                [sys.executable, str(POST_TOOL_HOOK)],
                input=json.dumps({
                    **base,
                    "tool_name": "mcp__codex-intake__goal_finish",
                    "tool_input": {"goal_id": "goal-sde"},
                    "tool_response": {"isError": False, "content": [{
                        "type": "text",
                        "text": '{"event_id":"finish-sde","status":"processed"}',
                    }]},
                }),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
                env=environment,
            )
            self.assertEqual(finished.returncode, 0, finished.stderr)
            awaiting_status = subprocess.run(
                [sys.executable, str(STOP_HOOK)],
                input=json.dumps({
                    **base,
                    "last_assistant_message": "The task is finished.",
                }),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
                env=environment,
            )
            self.assertEqual(awaiting_status.returncode, 0, awaiting_status.stderr)
            self.assertIn(
                "accepted a finish request but its result is unconfirmed",
                json.loads(awaiting_status.stdout)["reason"],
            )
            status = subprocess.run(
                [sys.executable, str(POST_TOOL_HOOK)],
                input=json.dumps({
                    **base,
                    "tool_name": "mcp__codex-intake__goal_status",
                    "tool_input": {"goal_id": "goal-sde"},
                    "tool_response": {"isError": False, "content": [{
                        "type": "text",
                        "text": '{"goal":{"goal_id":"goal-sde","status":"complete"}}',
                    }]},
                }),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
                env=environment,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            scope_state = json.loads(
                next((state_root / "task-state").glob("turn-*.json")).read_text()
            )
            self.assertEqual(scope_state["completed_goal_ids"], ["goal-sde"])
            result = subprocess.run(
                [sys.executable, str(STOP_HOOK)],
                input=json.dumps({
                    **base,
                    "last_assistant_message": "The task is finished.",
                }),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("pending `sde_assess` proposal", json.loads(result.stdout)["reason"])
            proposal = subprocess.run(
                [sys.executable, str(POST_TOOL_HOOK)],
                input=json.dumps({
                    **base,
                    "tool_name": "mcp__codex-intake__sde_assess",
                    "tool_input": {"goal_id": "goal-sde", "fact_ids": ["summary-sde"]},
                    "tool_response": {"isError": False, "content": [{
                        "type": "text",
                        "text": '{"goal_id":"goal-sde","candidate_id":"candidate-sde",'
                        '"status":"pending_review"}',
                    }]},
                }),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
                env=environment,
            )
            self.assertEqual(proposal.returncode, 0, proposal.stderr)
            proposal_state = json.loads(
                next((state_root / "task-state").glob("turn-*.json")).read_text()
            )
            self.assertEqual(proposal_state["sde_candidate_pairs"], ["goal-sde|candidate-sde"])
            awaiting_detail = subprocess.run(
                [sys.executable, str(STOP_HOOK)],
                input=json.dumps({**base, "last_assistant_message": "The task is finished."}),
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
                env=environment,
            )
            self.assertEqual(awaiting_detail.returncode, 0, awaiting_detail.stderr)
            self.assertIn("sde_review_detail", json.loads(awaiting_detail.stdout)["reason"])

    def test_normal_request_requires_pending_sde_proposal_at_completion(self) -> None:
        """Carry a completed normal task into its own pending owner-review proposal."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            Path(workspace, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            environment = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "session-full-lifecycle",
                "turn_id": "turn-lifecycle-complete",
            }

            def invoke(script: Path, event: Mapping[str, object]) -> dict[str, object]:
                result = subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps({**base, **event}),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout) if result.stdout else {}

            prompt = "ootask: implement a small task and verify its success."
            submitted = invoke(HOOK, {"prompt": prompt})
            hook_output = cast(dict[str, object], submitted["hookSpecificOutput"])
            context = cast(str, hook_output["additionalContext"])
            self.assertIn("TURN=BEGIN", context)
            self.assertIn("Track nontrivial project work before edits", context)
            self.assertIn("follow each item/one-off", context)
            self.assertIn("defer that exact item", context)

            invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__goal_defer",
                "tool_input": {"goal_id": "paused-plan-item"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"defer-paused-child","status":"processed"}',
                }]},
            })
            invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "paused-plan-item"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"paused-plan-item","status":"deferred"}}',
                }]},
            })

            for tool_name, tool_input, result_text in (
                (
                    "mcp__codex-intake__goal_start",
                    {"goal_id": "goal-lifecycle", "initial_status": "active"},
                    '{"event_id":"start-lifecycle","status":"processed"}',
                ),
                (
                    "mcp__codex-intake__fact_record",
                    {"goal_id": "goal-lifecycle", "bullet": "private fact canary"},
                    '{"event_id":"fact-lifecycle","status":"processed"}',
                ),
            ):
                invoke(POST_TOOL_HOOK, {
                    **base,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_response": {"isError": False, "content": [{
                        "type": "text", "text": result_text,
                    }]},
                })

            invoke(POST_TOOL_HOOK, {
                **base,
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"goal-lifecycle","status":"active",'
                    '"parent_goal_id":"plan-alpha"}}',
                }]},
            })

            allowed = invoke(PRE_TOOL_HOOK, {"tool_name": "Bash"})
            self.assertEqual(allowed, {})
            hold_turn = {"turn_id": "turn-lifecycle-hold"}
            invoke(POST_TOOL_HOOK, {
                **hold_turn,
                "tool_name": "mcp__codex-intake__goal_defer",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"defer-lifecycle","status":"processed"}',
                }]},
            })
            hold_prompt = invoke(STOP_HOOK, {
                **hold_turn,
                "last_assistant_message": "Pausing task tracking.",
            })
            self.assertIn("goal_status", cast(str, hold_prompt["reason"]))
            invoke(POST_TOOL_HOOK, {
                **hold_turn,
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"goal-lifecycle","status":"deferred"}}',
                }]},
            })

            resume_turn = {"turn_id": "turn-lifecycle-resume"}
            resumed = invoke(HOOK, {
                **resume_turn,
                "prompt": "Let's resume this task.",
            })
            resume_context = cast(
                str,
                cast(dict[str, object], resumed["hookSpecificOutput"])[
                    "additionalContext"
                ],
            )
            self.assertIn("TURN=RESUME", resume_context)
            invoke(POST_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"goal-lifecycle","status":"deferred"}}',
                }]},
            })
            invoke(POST_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"activate-lifecycle","status":"processed"}',
                }]},
            })
            invoke(POST_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "goal-lifecycle", "bullet": "resumed"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"resume-fact-lifecycle","status":"processed"}',
                }]},
            })
            allowed_after_resume = invoke(PRE_TOOL_HOOK, {
                **resume_turn, "tool_name": "Bash",
            })
            self.assertEqual(allowed_after_resume, {})
            completion_turn = {"turn_id": "turn-lifecycle-complete"}
            invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"goal-lifecycle","status":"active"}}',
                }]},
            })
            invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {
                    "goal_id": "goal-lifecycle",
                    "kind": "change",
                    "bullet": "Task summary: completed from fact-lifecycle",
                },
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"summary-lifecycle","status":"processed"}',
                }]},
            })
            invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_report",
                "tool_input": {"goal_id": "goal-lifecycle", "fact_limit": 16},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": "# Goal `goal-lifecycle`\nTask summary: completed from fact-lifecycle",
                }]},
            })
            finish_gate = invoke(PRE_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_finish",
                "tool_input": {"goal_id": "goal-lifecycle"},
            })
            self.assertEqual(finish_gate, {})
            invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_finish",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"finish-lifecycle","status":"processed"}',
                }]},
            })

            stop_event = {"last_assistant_message": "The task is complete."}
            status_prompt = invoke(STOP_HOOK, {**completion_turn, **stop_event})
            self.assertIn("decision", status_prompt)
            self.assertIn("goal_status", cast(str, status_prompt["reason"]))
            invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"goal-lifecycle","status":"complete"}}',
                }]},
            })
            activation_before_proposal = invoke(PRE_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "paused-plan-item"},
            })
            before_proposal_output = cast(
                dict[str, object], activation_before_proposal["hookSpecificOutput"]
            )
            self.assertEqual(
                before_proposal_output["permissionDecision"],
                "deny",
            )
            self.assertIn(
                "pending SDE proposal",
                cast(str, before_proposal_output["permissionDecisionReason"]),
            )
            proposal_prompt = invoke(STOP_HOOK, {**completion_turn, **stop_event})
            self.assertIn("pending `sde_assess` proposal", cast(str, proposal_prompt["reason"]))
            proposal = invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__sde_assess",
                "tool_input": {"goal_id": "goal-lifecycle", "fact_ids": ["fact-lifecycle"]},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal_id":"goal-lifecycle","candidate_id":"candidate-lifecycle",'
                    '"status":"pending_review"}',
                }]},
            })
            self.assertEqual(proposal, {})
            activation_before_detail_confirmation = invoke(PRE_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "paused-plan-item"},
            })
            before_detail_output = cast(
                dict[str, object],
                activation_before_detail_confirmation["hookSpecificOutput"],
            )
            self.assertEqual(
                before_detail_output["permissionDecision"],
                "deny",
            )
            self.assertIn(
                "attached to its goal",
                cast(str, before_detail_output["permissionDecisionReason"]),
            )
            wrong_candidate_detail = invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__sde_review_detail",
                "tool_input": {"candidate_id": "other-candidate"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": "{\"candidate\":{\"candidate_id\":\"other-candidate\","
                    "\"goal_id\":\"goal-lifecycle\",\"status\":\"pending_review\"}}",
                }]},
            })
            self.assertEqual(wrong_candidate_detail, {})
            early_resume_turn = {"turn_id": "turn-lifecycle-early-continue"}
            invoke(HOOK, {
                **early_resume_turn,
                "prompt": "Continue the previously paused plan item.",
            })
            before_pending_sde_readback = invoke(PRE_TOOL_HOOK, {
                **early_resume_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "paused-plan-item"},
            })
            early_resume_reason = cast(
                str,
                cast(dict[str, object], before_pending_sde_readback[
                    "hookSpecificOutput"
                ])["permissionDecisionReason"],
            )
            self.assertIn("read back that exact pending candidate", early_resume_reason)
            still_gated = invoke(PRE_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "paused-plan-item"},
            })
            still_gated_output = cast(
                dict[str, object], still_gated["hookSpecificOutput"]
            )
            self.assertEqual(still_gated_output["permissionDecision"], "deny")
            proposal_detail = invoke(POST_TOOL_HOOK, {
                **completion_turn,
                "tool_name": "mcp__codex-intake__sde_review_detail",
                "tool_input": {"candidate_id": "candidate-lifecycle"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": "{\"candidate\":{\"candidate_id\":\"candidate-lifecycle\","
                    "\"goal_id\":\"goal-lifecycle\",\"status\":\"pending_review\"}}",
                }]},
            })
            self.assertEqual(proposal_detail, {})
            resume_turn = {"turn_id": "turn-lifecycle-continue"}
            no_continue_prompt = invoke(PRE_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "paused-plan-item"},
            })
            no_continue_output = cast(
                dict[str, object], no_continue_prompt["hookSpecificOutput"]
            )
            self.assertEqual(no_continue_output["permissionDecision"], "deny")
            self.assertIn(
                "Wait for the user to say continue",
                cast(str, no_continue_output["permissionDecisionReason"]),
            )
            continued = invoke(HOOK, {
                **resume_turn,
                "prompt": "Continue the previously paused plan item.",
            })
            continued_context = cast(
                str,
                cast(dict[str, object], continued["hookSpecificOutput"])[
                    "additionalContext"
                ],
            )
            self.assertIn("TURN=RESUME", continued_context)
            wrong_child = invoke(PRE_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "later-plan-child"},
            })
            wrong_child_output = cast(
                dict[str, object], wrong_child["hookSpecificOutput"]
            )
            self.assertEqual(wrong_child_output["permissionDecision"], "deny")
            self.assertIn(
                "exact item",
                cast(str, wrong_child_output["permissionDecisionReason"]),
            )
            resume_paused_item = invoke(PRE_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "paused-plan-item"},
            })
            self.assertEqual(resume_paused_item, {})
            invoke(POST_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__goal_activate",
                "tool_input": {"goal_id": "paused-plan-item"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"resume-paused-child","status":"processed"}',
                }]},
            })
            invoke(POST_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "paused-plan-item"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"goal":{"goal_id":"paused-plan-item","status":"active"}}',
                }]},
            })
            invoke(POST_TOOL_HOOK, {
                **resume_turn,
                "tool_name": "mcp__codex-intake__fact_record",
                "tool_input": {"goal_id": "paused-plan-item", "kind": "intent"},
                "tool_response": {"isError": False, "content": [{
                    "type": "text",
                    "text": '{"event_id":"paused-child-resume-intent","status":"processed"}',
                }]},
            })
            self.assertEqual(invoke(PRE_TOOL_HOOK, {
                **resume_turn, "tool_name": "Bash",
            }), {})
            task_state = next(
                json.loads(state_text)
                for path in (state_root / "task-state").glob("turn-*.json")
                if '"completed_goal_ids":["goal-lifecycle"]'
                in (state_text := path.read_text(encoding="utf-8"))
            )
            self.assertEqual(task_state["completed_goal_ids"], ["goal-lifecycle"])
            self.assertEqual(task_state["sde_proposal_goal_ids"], ["goal-lifecycle"])
            self.assertEqual(task_state["ootask_paused_goal_ids"], [])
            state_files = list((state_root / "task-state").glob("turn-*.json"))
            self.assertEqual(len(state_files), 5)
            handoff_files = list((state_root / "task-state").glob("handoff-*.json"))
            self.assertEqual(len(handoff_files), 1)
            handoff_state = json.loads(handoff_files[0].read_text(encoding="utf-8"))
            self.assertEqual(handoff_state["ootask_paused_goal_ids"], [])
            self.assertEqual(handoff_state["ootask_goal_ids"], [])
            registry_files = list((state_root / "task-state").glob("ootasks-*.json"))
            self.assertEqual(len(registry_files), 1)
            registry_state = json.loads(registry_files[0].read_text(encoding="utf-8"))
            self.assertEqual(registry_state["ootask_goal_ids"], [])
            states = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in state_files
            ]
            self.assertTrue(all("pending_sde_goal_ids" not in state for state in states))
            for path in state_files:
                self.assertNotIn("private fact canary", path.read_text(encoding="utf-8"))

    def test_hold_requires_status_confirmation_and_keeps_task_checkpoint(self) -> None:
        """A successful defer is a pause, not task completion or SDE assessment."""

        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            Path(workspace, ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            state_root = Path(directory) / "plugin-data"
            state_root.mkdir(mode=0o700)
            environment = os.environ | {"PLUGIN_DATA": str(state_root)}
            base = {
                "cwd": str(workspace),
                "session_id": "session-hold",
                "turn_id": "turn-hold",
            }

            def invoke(script: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps({**base, **event}),
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=3,
                    env=environment,
                )

            for tool_name, tool_input, response in (
                (
                    "mcp__codex-intake__goal_start",
                    {"goal_id": "goal-hold", "initial_status": "active"},
                    '{"event_id":"start-hold","status":"processed"}',
                ),
                (
                    "mcp__codex-intake__fact_record",
                    {"goal_id": "goal-hold", "bullet": "checkpoint"},
                    '{"event_id":"fact-hold","status":"processed"}',
                ),
            ):
                recorded = invoke(POST_TOOL_HOOK, {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_response": {"isError": False, "content": [{"type": "text", "text": response}]},
                })
                self.assertEqual(recorded.returncode, 0, recorded.stderr)

            deferred = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_defer",
                "tool_input": {"goal_id": "goal-hold"},
                "tool_response": {"isError": False, "content": [{"type": "text", "text": '{"event_id":"defer-hold","status":"processed"}'}]},
            })
            self.assertEqual(deferred.returncode, 0, deferred.stderr)
            while_unconfirmed = invoke(PRE_TOOL_HOOK, {"tool_name": "Bash"})
            self.assertIn(
                "goal status readback",
                json.loads(while_unconfirmed.stdout)["hookSpecificOutput"][
                    "permissionDecisionReason"
                ],
            )

            status = invoke(POST_TOOL_HOOK, {
                "tool_name": "mcp__codex-intake__goal_status",
                "tool_input": {"goal_id": "goal-hold"},
                "tool_response": {"isError": False, "content": [{"type": "text", "text": '{"goal":{"goal_id":"goal-hold","status":"deferred"}}'}]},
            })
            self.assertEqual(status.returncode, 0, status.stderr)
            state = json.loads(next((state_root / "task-state").glob("turn-*.json")).read_text())
            self.assertEqual(state["active_goal_ids"], [])
            self.assertEqual(state["defer_requested_goal_ids"], [])
            self.assertNotIn("pending_sde_goal_ids", state)

    def test_prompt_turn_event_id_is_stable_and_does_not_expose_turn_id(self) -> None:
        """Use the same content-free event ID when one Codex turn is retried."""

        source_event_id = _HOOK_MODULE["_source_event_id"]
        turn_id = "same-turn"
        first = source_event_id(turn_id)
        self.assertEqual(first, source_event_id(turn_id))
        self.assertNotEqual(first, source_event_id("different-turn"))
        self.assertRegex(first, r"^codex-turn-[a-f0-9]{32}$")
        self.assertNotIn(turn_id, first)

    def test_plugin_mcp_config_discovers_the_active_project(self) -> None:
        """Resolve each workspace to its exact owner-configured database."""

        transport = _MCP_INSTALLER_MODULE["_expected_transport"](
            Path("/tmp/curator-v2-test.sqlite3")
        )
        args = transport["args"]
        self.assertNotIn("--project-root", args)
        database_index = args.index("--database")
        self.assertTrue(Path(args[database_index + 1]).is_absolute())
        self.assertIn("--allow-write", args)
        self.assertIsNone(transport["cwd"])

    def test_user_mcp_detection_does_not_confuse_plugin_registration(self) -> None:
        """Check the owner config before adding an override with the same name."""

        has_user_server = _MCP_INSTALLER_MODULE["_has_user_server"]
        with TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            with patch.dict(os.environ, {"CODEX_HOME": directory}):
                self.assertFalse(has_user_server())
                config.write_text('[mcp_servers.other]\ncommand = "other"\n', encoding="utf-8")
                self.assertFalse(has_user_server())
                config.write_text('[mcp_servers.codex-intake]\ncommand = "other"\n', encoding="utf-8")
                self.assertTrue(has_user_server())

    def test_user_mcp_installer_preserves_conflicting_registration(self) -> None:
        """Never replace another owner-configured server with the same name."""

        install = _MCP_INSTALLER_MODULE["install_user_mcp"]
        with (
            patch.dict(install.__globals__, {
                "_has_user_server": lambda: True,
                "_get_server": lambda: {"enabled": True, "transport": {"command": "other"}},
            }),
            patch("subprocess.run") as run,
        ):
            with self.assertRaises(ValueError):
                install(Path("/tmp/curator-v2-test.sqlite3"))
            run.assert_not_called()

    def test_codex_mcp_instructions_include_server_verified_project_fingerprints(self) -> None:
        """Make the enforced project and config binding available for audit receipts."""

        parent = ROOT / ".curatormd-v2"
        staging_root = parent / "side-buffer"
        created_parent = not parent.exists()
        created_staging_root = not staging_root.exists()
        staging_root.mkdir(parents=True, exist_ok=True)
        try:
            config = ProjectConfig.load(ROOT)
            instructions = _bound_codex_instructions(config)
        finally:
            if created_staging_root:
                staging_root.rmdir()
            if created_parent:
                parent.rmdir()
        self.assertIn(f"project_id={config.project_id}", instructions)
        self.assertIn(f"repository_fingerprint={config.repository_fingerprint}", instructions)
        self.assertIn(f"config_sha256={config.config_sha256}", instructions)
        self.assertIn("server-enforced", instructions)
        self.assertIn("do not require a host receipt for ordinary local checks", instructions)
        self.assertNotIn("use a host-configured repository_test receipt", instructions)
        self.assertIn("never require it for completion or", instructions)

    def test_intake_skill_tracks_normal_lifecycle_and_leaves_sde_decisions_to_user(self) -> None:
        """Ensure ordinary item language controls work and SDE decisions stay human."""

        skill = " ".join((ROOT / "integrations" / "codex-plugin" / "skills" / "curator-intake" / "SKILL.md").read_text(encoding="utf-8").split())
        for phrase in (
            "Use `limit=10` and reduce each result to its `goal_id`, status, "
            "saved problem, success checks, and parent ID before comparing candidates",
            "never create from a truncated or partially reviewed list",
            "“moving to the next item”, “check this off”, “mark this complete”",
            "call `goal_finish` when the task is done, then activate the next planned child",
            "one practical success check",
            "without waiting for another instruction or automated evidence",
            "“pause”, “hold”, “put it aside”, “not now”",
            "then calls `goal_defer`",
            "“resume”, “continue”, “back to this”",
            "planned, deferred, or its blocker is resolved",
            "already active, continue without another transition",
            "call `goal_finish`",
            "Apply the same lifecycle to each plan child and each one-off task",
            "whether it is inside or outside a plan",
            "state the same compact kickoff in this exact form",
            "`Problem: <what is wrong or needs doing>. Success: <observable checks that show it is done>.`",
            "On a retry or resume, reuse the same goal and wording",
            "never call `goal_start` just because the turn or thread changed",
            "`Resuming problem/task: <saved problem or title>. Open checks: <checks still open>.`",
            "never invent a plan number",
            "the existing `goal_id` is the continuity key",
            "The prompt-turn event ID is only for retrying one `goal_start` event",
            "never reuse it for a later operation or use it as the task ID",
            "Give every later `fact_record`, lifecycle transition, and SDE operation its own fresh event ID",
            "its saved `parent_goal_id` groups it under the plan",
            "`ootask:` to require a distinct one-off goal",
            "`aotask:` (add-on to current item) to add a sub-item",
            "Build the completed task's proposal summary from its supported facts",
            "never submit child fact IDs as a parent's SDE facts",
            "Do not create or read back a separate `Task summary:` fact",
            "After the owner approves an SDE, transfer only the approved facts",
            "A task endpoint or pending proposal alone does not authorize cleanup",
            "The SDE decision is the single owner approval",
            "do not ask for a separate deletion approval",
            "Task evidence and lifecycle tracking are part of each tracked task",
            "do not ask the user to enable capture",
            "Propose potentially useful facts for owner review, including during active work",
            "After `goal_finish` succeeds",
            "For a child one-off, assess its",
            "read `goal_status` and pass its current lifecycle revision",
            "The user decides what is memorialized, its importance, and whether it is approved",
            "it never approves or codifies knowledge",
            "“Beginning task tracking.”",
            "“Pausing task tracking.”",
            "“Resuming task tracking.”",
            "After `goal_finish` is confirmed: prepare a pending proposal",
            "Curator task tracking is the default workflow",
            "If Codex reports that the Curator MCP transport is closed",
            "reload the VS Code window (Codex host) or start a fresh Codex session",
            "Do not re-enroll the project or recreate its grants.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

    def test_plugin_starter_prompts_fit_manifest_limits(self) -> None:
        """Keep optional starter prompts short; detailed behavior lives in the skill and hook."""

        manifest = json.loads(
            (ROOT / "integrations" / "codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        default_prompts = manifest["extensions"]["com.openai"]["interface"]["defaultPrompt"]
        self.assertLessEqual(len(default_prompts), 3)
        self.assertTrue(default_prompts)
        for prompt in default_prompts:
            with self.subTest(prompt=prompt):
                self.assertLessEqual(len(prompt), 128)
        joined_prompts = " ".join(default_prompts)
        for phrase in ("`Problem: ... Success: ...`", "Curator goal", "compact evidence facts", "After a goal completes", "pending SDE proposal", "before edits"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, joined_prompts)

    def test_user_hook_installer_preserves_existing_handlers_and_is_idempotent(self) -> None:
        """Register only one V2 handler without replacing existing hooks."""

        with TemporaryDirectory() as directory:
            codex_home = Path(directory) / ".codex"
            codex_home.mkdir(mode=0o700)
            config_path = codex_home / "hooks.json"
            config_path.write_text(
                json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "keep-me"}]}]}}),
                encoding="utf-8",
            )
            config_path.chmod(0o600)

            install = _HOOK_INSTALLER_MODULE["install_user_hook"]
            self.assertTrue(install(codex_home))
            self.assertFalse(install(codex_home))
            saved = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "keep-me")
        prompt_hooks = saved["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(prompt_hooks), 1)
        handler = prompt_hooks[0]["hooks"][0]
        self.assertIn("integrations/codex-plugin/hooks/user_prompt_submit.py", handler["command"])
        self.assertEqual(handler["additionalContextLimit"], 4096)

    def test_prompt_process_sets_core_and_file_privacy_limits(self) -> None:
        """Protect the hook before it receives the raw prompt event."""

        prctl = Mock(return_value=0)
        libc = SimpleNamespace(prctl=prctl)
        with (
            patch("resource.setrlimit") as setrlimit,
            patch("ctypes.CDLL", return_value=libc),
            patch("os.umask") as umask,
            patch("sys.platform", "linux"),
        ):
            self.assertTrue(_PROTECT_PROMPT_PROCESS())
        setrlimit.assert_called_once_with(4, (0, 0))
        prctl.assert_called_once_with(4, 0, 0, 0, 0)
        umask.assert_called_once_with(0o077)

    def test_hook_does_not_read_prompt_if_process_protection_fails(self) -> None:
        """Fail closed before reading stdin when local limits are unavailable."""

        stdin = SimpleNamespace(buffer=Mock())
        with (
            patch.object(sys, "stdin", stdin),
            patch("resource.setrlimit", side_effect=OSError),
        ):
            self.assertEqual(_HOOK_MODULE["main"](), 0)
        stdin.buffer.read.assert_not_called()

    def test_mcp_guidance_matches_task_lifecycle_and_human_sde_decisions(self) -> None:
        """Keep the connected MCP rules consistent with normal task language."""

        instructions = " ".join(CODEX_INSTRUCTIONS.split())
        for phrase in (
            '"Next item", "check it off", "mark complete", or your own narration that you are moving on records',
            '"Pause", "hold", or "put it aside"',
            "calls `goal_defer`",
            '"Resume" or "continue"',
            "prepares a pending SDE proposal from that completed goal's supported facts",
            'A request to "finish the plugin" or "complete this task" asks for work',
            "Curator tracking is the default for every nontrivial task",
            "do not ask the user to opt in or start a separate capture mode",
            '"Beginning task tracking"',
            '"Pausing task tracking"',
            "prepare a pending SDE proposal from supported facts belonging to that goal",
            "`ootask:` explicitly means a distinct one-off",
            "`aotask:` means add a sub-item under, or correct/change, the current goal or plan item",
            "Use one practical success check per task",
            "never require it for completion or a proposal",
            "create a pending proposal using only supported facts from that goal",
            "the user decides what is memorialized, its importance",
            "Never approve/reject or codify on the user's behalf",
            "Before `goal_finish`, `goal_defer`, or `goal_activate`, read `goal_status`",
            "test/lint result or owner confirmation",
            "1-16 facts per page",
            "`goal_list_page` result in pages of 10",
            "follow every `next_offset`",
            "hook-provided `codex-turn-*` prompt-turn event ID exactly",
            "Give every later `fact_record`, lifecycle transition, and SDE operation its own fresh event ID",
            "never reuse it for a later operation or as the task ID",
            "State them to the user as `Problem: <problem>. Success: <observable checks>.`",
            "For a plan, state this for the parent and again for each child",
            "For a one-off, state it once whether it is inside or outside a plan",
            "On retries and resumes reuse the same goal and wording",
            "never call `goal_start` just because a turn or thread changed",
            "`Resuming problem/task: <saved problem or title>. Open checks: <checks still open>.`",
            "A `goal_id` groups the task's facts across turns, pauses, threads, and intervening unrelated work",
            "exact `fact_compaction_propose` and owner-approved `fact_compaction_approve`",
            "Never save the raw prompt or chat transcript",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, instructions)

    def test_mcp_finds_session_workspace_when_started_from_plugin_directory(self) -> None:
        """Resolve project config when Codex launches MCP from the plugin cache."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = root / "plugin-cache"
            project_dir = root / "workspace"
            plugin_dir.mkdir()
            project_dir.mkdir()
            (project_dir / ".curatormd-v2.toml").write_text(
                'project_id = "alpha"\n', encoding="utf-8"
            )
            with (
                patch("pathlib.Path.cwd", return_value=plugin_dir),
                patch.dict("os.environ", {"PWD": str(project_dir)}),
            ):
                self.assertEqual(_workspace_root(None), project_dir)

    def test_mcp_prefers_codex_parent_workspace_over_plugin_and_stale_pwd(self) -> None:
        """Bind to Codex's workspace when the plugin process cwd is its cache."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            plugin_dir = root / "plugin-cache"
            project_dir = root / "workspace"
            stale_dir = root / "previous-workspace"
            for candidate in (plugin_dir, project_dir, stale_dir):
                candidate.mkdir()
            (project_dir / ".curatormd-v2.toml").write_text(
                'project_id = "active"\n', encoding="utf-8"
            )
            (stale_dir / ".curatormd-v2.toml").write_text(
                'project_id = "stale"\n', encoding="utf-8"
            )
            with (
                patch("curatormd_v2.codex_mcp._codex_parent_workspace", return_value=project_dir),
                patch("pathlib.Path.cwd", return_value=plugin_dir),
                patch.dict("os.environ", {"PWD": str(stale_dir)}),
            ):
                self.assertEqual(_workspace_root(None), project_dir)

    def test_codex_parent_workspace_requires_codex_parent_process(self) -> None:
        """Do not treat an unrelated parent process directory as workspace context."""

        with (
            patch("sys.platform", "linux"),
            patch("os.getppid", return_value=1234),
            patch("pathlib.Path.read_text", return_value="python\n"),
        ):
            self.assertIsNone(_codex_parent_workspace())


if __name__ == "__main__":
    unittest.main()
