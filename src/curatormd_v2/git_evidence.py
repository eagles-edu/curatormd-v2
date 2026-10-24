"""Local Git commit-range evidence with bounded, content-free attestations.

This resolver proves the bytes of a configured repository's immutable commit
diff. Its local checkout and runner identity are host assertions, not a
deployment identity or a signed repository-provider receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess  # nosec B404
import tempfile
from threading import Event, Timer

from .evidence import (
    EvidenceSourceReceipt,
    EvidenceVerificationContext,
    EvidenceSourceResolver,
)
from .models import EvidenceRef

MAX_GIT_DIFF_BYTES = 32 * 1024 * 1024
MAX_TEST_OUTPUT_BYTES = 4 * 1024 * 1024
GIT_COMMAND_TIMEOUT_SECONDS = 30
TEST_RUN_TIMEOUT_SECONDS = 300
_COMMIT_RANGE_RE = re.compile(
    r"^git-diff:([0-9a-f]{40}|[0-9a-f]{64})\.\.([0-9a-f]{40}|[0-9a-f]{64})$"
)
_TEST_LOCATOR_RE = re.compile(
    r"^git-test:([A-Za-z0-9][A-Za-z0-9._:-]{0,127}):([0-9a-f]{40}|[0-9a-f]{64})$"
)
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SUBJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class _GitRuntime:
    """Resolved host executable and isolated environment for Git operations."""

    executable: str
    environment: dict[str, str]


@dataclass(frozen=True, slots=True)
class LocalGitTestRunnerConfig:
    """Host-owned identity, command, and bounds for one local test runner."""

    project_id: str
    runner_id: str
    source_subject: str
    command: tuple[str, ...]
    max_output_bytes: int = MAX_TEST_OUTPUT_BYTES
    timeout_seconds: int = TEST_RUN_TIMEOUT_SECONDS


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    """Stop a runner and its children so inherited pipes cannot evade bounds."""

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        try:
            process.kill()
        except OSError:
            pass


class GitCommitDiffResolver(EvidenceSourceResolver):
    """Resolve only full commit-ID diff references inside one configured repo."""

    # pylint: disable=too-few-public-methods  # One bounded resolve operation is the adapter contract.

    def __init__(
        self,
        repository_root: str | Path,
        *,
        project_id: str,
        source_subject: str,
        max_diff_bytes: int = MAX_GIT_DIFF_BYTES,
        timeout_seconds: int = GIT_COMMAND_TIMEOUT_SECONDS,
    ) -> None:
        if not _PROJECT_ID_RE.fullmatch(project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        if not _SUBJECT_RE.fullmatch(source_subject):
            raise ValueError("source_subject must be a bounded opaque identifier")
        if not 1 <= max_diff_bytes <= MAX_GIT_DIFF_BYTES:
            raise ValueError("max_diff_bytes exceeds the local diff ceiling")
        if not 1 <= timeout_seconds <= GIT_COMMAND_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds exceeds the Git command ceiling")
        try:
            root = Path(repository_root).resolve(strict=True)
        except OSError:
            raise ValueError("repository root is unavailable") from None
        if not root.is_dir():
            raise ValueError("repository root is not a directory")

        self.repository_root = root
        self.project_id = project_id
        self.source_subject = source_subject
        self.scope_id = f"git-repository:{project_id}"
        self.max_diff_bytes = max_diff_bytes
        self.timeout_seconds = timeout_seconds
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "LC_ALL": "C",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
        }
        git_executable = shutil.which("git", path=environment["PATH"])
        if git_executable is None:
            raise ValueError("local Git executable is unavailable")
        self._runtime = _GitRuntime(git_executable, environment)
        self._verify_repository_root()

    def resolve(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceSourceReceipt | None:
        """Hash one bounded commit diff and return path-free local provenance."""

        if (
            context.project_id != self.project_id
            or evidence.evidence_kind != "repository_diff"
        ):
            return None
        match = _COMMIT_RANGE_RE.fullmatch(evidence.locator)
        if match is None:
            return None
        base_revision, head_revision = match.groups()
        if base_revision == head_revision:
            return None
        if not self._commit_exists(base_revision) or not self._commit_exists(
            head_revision
        ):
            return None

        digest = self._hash_diff(base_revision, head_revision)
        # The host verification context owns the clock for its entire resolver
        # call; using it avoids claiming a later observation than the verifier's
        # trusted `now` value on this immutable source.
        now = context.now_utc
        return EvidenceSourceReceipt(
            evidence_kind="repository_diff",
            locator=evidence.locator,
            evidence_sha256=digest,
            project_id=self.project_id,
            goal_id=context.goal_id,
            criterion_id=context.criterion_id,
            scope_id=self.scope_id,
            source_revision=f"git:{base_revision}..{head_revision}",
            authenticated_subject=self.source_subject,
            observed_at=now.isoformat(timespec="microseconds"),
            valid_until=datetime.max.replace(tzinfo=UTC).isoformat(),
            revocation_checked_at=now.isoformat(timespec="microseconds"),
            revoked=False,
        )

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        try:
            # The executable is resolved from the host PATH; arguments are
            # fixed options or validated full commit IDs.
            return subprocess.run(
                [
                    self._runtime.executable,
                    "-C",
                    str(self.repository_root),
                    *arguments,
                ],  # nosec B603
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=self._runtime.environment,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("local Git evidence source is unavailable") from None

    def _verify_repository_root(self) -> None:
        result = self._git("rev-parse", "--show-toplevel")
        if result.returncode != 0:
            raise ValueError("configured path is not a Git repository")
        try:
            reported_root = Path(os.fsdecode(result.stdout.rstrip(b"\n"))).resolve(
                strict=True
            )
        except OSError:
            raise ValueError("Git repository root is unavailable") from None
        if reported_root != self.repository_root:
            raise ValueError("configured path is not the Git worktree root")

    def _commit_exists(self, revision: str) -> bool:
        result = self._git("cat-file", "-e", f"{revision}^{{commit}}")
        return result.returncode == 0

    def _hash_diff(self, base_revision: str, head_revision: str) -> str:
        command = [
            self._runtime.executable,
            "-C",
            str(self.repository_root),
            "diff",
            "--binary",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--diff-algorithm=myers",
            "--unified=0",
            base_revision,
            head_revision,
            "--",
        ]
        try:
            # The only dynamic command values are the validated full commit IDs.
            # A context manager would wait without the bounded timeout/kill path below.
            process = subprocess.Popen(  # nosec B603  # pylint: disable=consider-using-with
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=self._runtime.environment,
            )
        except OSError:
            raise RuntimeError("local Git evidence source is unavailable") from None

        if process.stdout is None:
            process.kill()
            process.wait()
            raise RuntimeError("local Git evidence stream is unavailable")
        expired = Event()

        def terminate() -> None:
            expired.set()
            try:
                process.kill()
            except OSError:
                pass

        timeout = Timer(self.timeout_seconds, terminate)
        digest = hashlib.sha256()
        total_bytes = 0
        too_large = False
        timeout.start()
        try:
            while chunk := process.stdout.read(64 * 1024):
                total_bytes += len(chunk)
                if total_bytes > self.max_diff_bytes:
                    too_large = True
                    process.kill()
                    break
                digest.update(chunk)
        finally:
            timeout.cancel()
            process.stdout.close()
        try:
            return_code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError("local Git evidence source did not stop") from None
        if expired.is_set():
            raise RuntimeError("local Git evidence source timed out") from None
        if too_large:
            raise RuntimeError("repository diff exceeds the local byte ceiling") from None
        if return_code != 0:
            raise RuntimeError("local Git evidence source failed") from None
        return digest.hexdigest()


class LocalGitTestRunnerResolver(EvidenceSourceResolver):
    """Run a host-allowlisted test command against an isolated commit checkout.

    The runner command and subject are local host assertions. The resolver
    proves which configured command ran against which commit and hashes its
    bounded combined output; it does not authenticate a CI service or human.
    """

    # pylint: disable=too-few-public-methods  # One bounded resolve operation is the adapter contract.

    def __init__(
        self,
        repository_root: str | Path,
        *,
        config: LocalGitTestRunnerConfig,
    ) -> None:
        if not _PROJECT_ID_RE.fullmatch(config.project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        if not _SUBJECT_RE.fullmatch(config.runner_id):
            raise ValueError("runner_id must be a bounded opaque identifier")
        if not _SUBJECT_RE.fullmatch(config.source_subject):
            raise ValueError("source_subject must be a bounded opaque identifier")
        if not config.command or len(config.command) > 64:
            raise ValueError("test command must contain 1-64 arguments")
        if any(not item or len(item) > 1024 or "\x00" in item for item in config.command):
            raise ValueError("test command arguments must be nonempty and bounded")
        if sum(len(item.encode("utf-8")) for item in config.command) > 8192:
            raise ValueError("test command exceeds the local argument ceiling")
        if not 1 <= config.max_output_bytes <= MAX_TEST_OUTPUT_BYTES:
            raise ValueError("max_output_bytes exceeds the local output ceiling")
        if not 1 <= config.timeout_seconds <= TEST_RUN_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds exceeds the test-run ceiling")
        try:
            root = Path(repository_root).resolve(strict=True)
        except OSError:
            raise ValueError("repository root is unavailable") from None
        if not root.is_dir():
            raise ValueError("repository root is not a directory")

        self.repository_root = root
        path = os.environ.get("PATH", "")
        git_executable = shutil.which("git", path=path)
        command_executable = shutil.which(config.command[0], path=path)
        if git_executable is None or command_executable is None:
            raise ValueError("configured Git or test executable is unavailable")
        self.config = replace(
            config,
            command=(command_executable, *config.command[1:]),
        )
        environment = {
            "PATH": path,
            "LC_ALL": "C",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        self._runtime = _GitRuntime(git_executable, environment)
        self._verify_repository_root()

    @property
    def scope_id(self) -> str:
        """Return this runner's stable evidence scope."""

        return f"git-test-runner:{self.config.runner_id}"

    def resolve(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceSourceReceipt | None:
        """Run the configured command for one exact commit and emit its digest."""

        if (
            context.project_id != self.config.project_id
            or evidence.evidence_kind != "repository_test"
        ):
            return None
        match = _TEST_LOCATOR_RE.fullmatch(evidence.locator)
        if match is None:
            return None
        runner_id, revision = match.groups()
        if runner_id != self.config.runner_id or not self._commit_exists(revision):
            return None

        digest = self._run_commit(revision)
        if digest is None:
            return None
        now = context.now_utc
        return EvidenceSourceReceipt(
            evidence_kind="repository_test",
            locator=evidence.locator,
            evidence_sha256=digest,
            project_id=self.config.project_id,
            goal_id=context.goal_id,
            criterion_id=context.criterion_id,
            scope_id=self.scope_id,
            source_revision=f"git-test:{runner_id}:{revision}",
            authenticated_subject=self.config.source_subject,
            observed_at=now.isoformat(timespec="microseconds"),
            valid_until=datetime.max.replace(tzinfo=UTC).isoformat(),
            revocation_checked_at=now.isoformat(timespec="microseconds"),
            revoked=False,
        )

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                [
                    self._runtime.executable,
                    "-C",
                    str(self.repository_root),
                    *arguments,
                ],  # nosec B603
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=self._runtime.environment,
                check=False,
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("local Git test source is unavailable") from None

    def _verify_repository_root(self) -> None:
        result = self._git("rev-parse", "--show-toplevel")
        if result.returncode != 0:
            raise ValueError("configured path is not a Git repository")
        try:
            reported = Path(os.fsdecode(result.stdout.rstrip(b"\n"))).resolve(strict=True)
        except OSError:
            raise ValueError("Git repository root is unavailable") from None
        if reported != self.repository_root:
            raise ValueError("configured path is not the Git worktree root")

    def _commit_exists(self, revision: str) -> bool:
        return self._git("cat-file", "-e", f"{revision}^{{commit}}").returncode == 0

    def _run_commit(self, revision: str) -> str | None:
        with tempfile.TemporaryDirectory(prefix="curator-v2-test-") as temporary:
            clone = Path(temporary) / "checkout"
            cloned = subprocess.run(
                [self._runtime.executable, "clone", "--quiet", "--no-hardlinks",
                 "--no-checkout", "--", str(self.repository_root), str(clone)],  # nosec B603
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self._runtime.environment,
                check=False,
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            )
            if cloned.returncode != 0:
                raise RuntimeError("local Git test checkout is unavailable") from None
            checked_out = subprocess.run(
                [self._runtime.executable, "-C", str(clone), "checkout", "--quiet",
                 "--detach", revision],  # nosec B603
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self._runtime.environment,
                check=False,
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            )
            if checked_out.returncode != 0:
                raise RuntimeError("local Git test revision is unavailable") from None
            return self._execute(clone, revision)

    def _execute(self, cwd: Path, revision: str) -> str | None:
        environment = {
            **self._runtime.environment,
            "HOME": str(cwd),
            "TMPDIR": str(cwd),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        try:
            # Keep timeout-triggered process-group termination and bounded wait.
            process = subprocess.Popen(  # nosec B603  # pylint: disable=consider-using-with
                list(self.config.command),
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=environment,
                start_new_session=True,
            )
        except OSError:
            raise RuntimeError("configured local test runner is unavailable") from None
        if process.stdout is None:
            process.kill()
            process.wait()
            raise RuntimeError("configured local test output is unavailable")

        expired = Event()

        def terminate() -> None:
            expired.set()
            _kill_process_group(process)

        timer = Timer(self.config.timeout_seconds, terminate)
        digest = hashlib.sha256()
        digest.update(b"curator-v2-local-git-test-v1\0")
        digest.update(self.config.runner_id.encode("ascii"))
        digest.update(b"\0")
        digest.update(revision.encode("ascii"))
        digest.update(b"\0")
        digest.update("\0".join(self.config.command).encode("utf-8"))
        total = 0
        too_large = False
        timer.start()
        try:
            while chunk := process.stdout.read(64 * 1024):
                total += len(chunk)
                if total > self.config.max_output_bytes:
                    too_large = True
                    _kill_process_group(process)
                    break
                digest.update(chunk)
        finally:
            timer.cancel()
            process.stdout.close()
        try:
            return_code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            process.wait()
            raise RuntimeError("configured local test runner did not stop") from None
        if expired.is_set():
            raise RuntimeError("configured local test runner timed out") from None
        if too_large:
            raise RuntimeError("local test output exceeds the byte ceiling") from None
        digest.update(b"\0exit=")
        digest.update(str(return_code).encode("ascii"))
        return digest.hexdigest() if return_code == 0 else None
