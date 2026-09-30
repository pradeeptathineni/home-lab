"""command line entry point"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from labctl import doctor, lima
from labctl.compose import (
    PROFILES,
    compose_command,
    profiles_arguments,
    validate_profile,
    validate_service,
)
from labctl.runner import CommandRunner


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="labctl", description="Operate the portable home lab")
    parser.add_argument(
        "--dry-run", action="store_true", help="print commands without running them"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="check dependencies and configuration")

    node = subparsers.add_parser("node", help="manage the Lima node")
    node_commands = node.add_subparsers(dest="node_command", required=True)
    node_commands.add_parser("up")
    node_commands.add_parser("down")
    node_commands.add_parser("status")
    node_commands.add_parser("shell")
    node_commands.add_parser("converge")

    deploy = subparsers.add_parser("deploy", help="start one service profile")
    deploy.add_argument("profile", choices=PROFILES)

    stop = subparsers.add_parser("stop", help="stop one service profile")
    stop.add_argument("profile", choices=PROFILES)

    subparsers.add_parser("status", help="show all service containers")

    secrets = subparsers.add_parser("secrets", help="manage private runtime values")
    secrets.add_argument("operation", choices=("init",))

    logs = subparsers.add_parser("logs", help="follow one service log")
    logs.add_argument("service")

    benchmark = subparsers.add_parser("benchmark", help="run a bounded benchmark")
    benchmark.add_argument("kind", choices=("ai", "dns", "network"))

    backup = subparsers.add_parser("backup", help="operate an explicit restic repository")
    backup.add_argument("operation", choices=("create", "check", "restore-test"))
    backup.add_argument("--allow-local-repository", action="store_true")

    subparsers.add_parser("validate", help="run repository validation")
    return parser


def _run_script(
    repo: Path, runner: CommandRunner, relative: str, extra: list[str] | None = None
) -> int:
    command = [sys.executable, str(repo / relative), *(extra or [])]
    return runner.run(command, cwd=repo, check=False).returncode


def _validate(repo: Path, runner: CommandRunner) -> int:
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "pytest"],
        [sys.executable, "-m", "yamllint", "."],
        [
            "docker",
            "compose",
            "--project-directory",
            str(repo),
            "--env-file",
            str(repo / "config" / "example.env"),
            "-f",
            str(repo / "compose.yaml"),
            *profiles_arguments(),
            "config",
            "--quiet",
        ],
    ]
    for command in commands:
        result = runner.run(command, cwd=repo, check=False)
        if result.returncode:
            return result.returncode
    ansible_root = repo / "infra" / "ansible"
    ansible_commands = [
        [
            str(Path(sys.executable).parent / "ansible-playbook"),
            "-i",
            "inventory/local.yml",
            "playbooks/converge.yml",
            "--syntax-check",
        ],
        [str(Path(sys.executable).parent / "ansible-lint"), "playbooks", "roles"],
    ]
    for command in ansible_commands:
        result = runner.run(command, cwd=ansible_root, check=False)
        if result.returncode:
            return result.returncode
    return 0


def dispatch(args: argparse.Namespace, runner: CommandRunner, repo: Path) -> int:
    if args.command == "doctor":
        return doctor.run(repo)
    if args.command == "node":
        if args.node_command == "up":
            return lima.up(repo, runner)
        if args.node_command == "down":
            return lima.down(runner)
        if args.node_command == "status":
            print(lima.node_state())
            return 0
        if args.node_command == "shell":
            return lima.shell(runner)
        return lima.converge(repo, runner)
    if args.command == "deploy":
        profile = validate_profile(args.profile)
        command = compose_command(repo, ["--profile", profile, "up", "-d", "--wait"])
        return runner.run(command).returncode
    if args.command == "stop":
        profile = validate_profile(args.profile)
        return runner.run(compose_command(repo, ["--profile", profile, "stop"])).returncode
    if args.command == "status":
        return runner.run(compose_command(repo, [*profiles_arguments(), "ps"])).returncode
    if args.command == "secrets":
        command = [
            "limactl",
            "shell",
            "--workdir",
            str(repo),
            "home-lab",
            "--",
            "python3",
            str(repo / "scripts" / "init_runtime_env.py"),
        ]
        return runner.run(command).returncode
    if args.command == "logs":
        service = validate_service(args.service)
        return runner.run(
            compose_command(repo, [*profiles_arguments(), "logs", "-f", service])
        ).returncode
    if args.command == "benchmark":
        return _run_script(repo, runner, f"benchmarks/{args.kind}/run.py")
    if args.command == "backup":
        if args.operation == "create":
            return _run_script(repo, runner, "scripts/backup.py")
        if args.operation == "check":
            return runner.run(["restic", "check"]).returncode
        extra = ["--allow-local-repository"] if args.allow_local_repository else []
        return _run_script(repo, runner, "scripts/restore_test.py", extra)
    if args.command == "validate":
        return _validate(repo, runner)
    raise ValueError(f"unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args, CommandRunner(args.dry_run), repository_root())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except (ValueError, RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
