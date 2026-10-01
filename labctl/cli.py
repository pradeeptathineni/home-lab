"""command line entry point"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from labctl import ai, doctor, lima, sandbox
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

    ai_parser = subparsers.add_parser("ai", help="manage local AI evidence")
    ai_commands = ai_parser.add_subparsers(dest="ai_command", required=True)
    ai_commands.add_parser("inspect")
    ai_commands.add_parser("models")
    ai_fetch = ai_commands.add_parser("fetch")
    ai_fetch.add_argument("model")
    ai_serve = ai_commands.add_parser("serve")
    ai_serve.add_argument("model")
    ai_commands.add_parser("stop")
    ai_route = ai_commands.add_parser("route")
    ai_route.add_argument("operation", choices=("start", "status", "stop"))
    ai_webui = ai_commands.add_parser("webui")
    ai_webui.add_argument("operation", choices=("configure",))
    ai_benchmark = ai_commands.add_parser("benchmark")
    ai_benchmark.add_argument("model")
    ai_eval = ai_commands.add_parser("eval")
    ai_eval.add_argument("model")
    ai_commands.add_parser("compare")
    ai_retrieval = ai_commands.add_parser("retrieval")
    ai_retrieval.add_argument("model")

    sandbox_parser = subparsers.add_parser("sandbox", help="manage the disposable experiment VM")
    sandbox_commands = sandbox_parser.add_subparsers(dest="sandbox_command", required=True)
    sandbox_commands.add_parser("create")
    sandbox_commands.add_parser("start")
    sandbox_commands.add_parser("status")
    sandbox_commands.add_parser("shell")
    sandbox_commands.add_parser("verify")
    sandbox_commands.add_parser("stop")
    sandbox_destroy = sandbox_commands.add_parser("destroy")
    sandbox_destroy.add_argument("--yes", action="store_true")
    sandbox_experiment = sandbox_commands.add_parser("experiment")
    sandbox_experiment.add_argument("experiment", choices=("network-fault",))

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
    if args.command == "ai":
        if args.ai_command == "inspect":
            return ai.inspect(repo)
        if args.ai_command == "models":
            return ai.list_models(repo)
        if args.ai_command == "fetch":
            return ai.fetch(repo, runner, args.model)
        if args.ai_command == "serve":
            return ai.serve(repo, runner, args.model)
        if args.ai_command == "stop":
            return ai.stop(repo, runner)
        if args.ai_command == "route":
            if args.operation == "start":
                return ai.route_start(repo, runner)
            if args.operation == "status":
                return ai.route_status(repo)
            return ai.route_stop(repo, runner)
        if args.ai_command == "webui":
            return ai.configure_open_webui(repo, runner)
        if args.ai_command == "compare":
            return _run_script(repo, runner, "benchmarks/ai/compare.py")
        relative = {
            "benchmark": "benchmarks/ai/run.py",
            "eval": "benchmarks/ai/eval.py",
            "retrieval": "benchmarks/retrieval/run.py",
        }[args.ai_command]
        return _run_script(repo, runner, relative, ["--model", args.model])
    if args.command == "sandbox":
        if args.sandbox_command == "create":
            return sandbox.create(repo, runner)
        if args.sandbox_command == "start":
            return sandbox.start(runner)
        if args.sandbox_command == "status":
            print(sandbox.state())
            return 0
        if args.sandbox_command == "shell":
            return sandbox.shell(runner)
        if args.sandbox_command == "verify":
            return sandbox.verify(repo)
        if args.sandbox_command == "stop":
            return sandbox.stop(runner)
        if args.sandbox_command == "destroy":
            return sandbox.destroy(runner, args.yes)
        return sandbox.network_fault_experiment(repo)
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
