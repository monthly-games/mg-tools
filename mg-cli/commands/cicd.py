"""
CI/CD Commands for MG-CLI

Manages build, test, and deployment workflows for MG Games.
"""

import click
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

from ..services.game_scanner import GameScanner, GameInfo


class CICDService:
    """CI/CD automation service"""

    def __init__(self, scanner: GameScanner):
        self.scanner = scanner

    def run_flutter_tests(self, game_info: GameInfo) -> Tuple[bool, str]:
        """Run Flutter tests for a game"""
        game_dir = game_info.path / "game"
        if not game_dir.exists():
            return False, "Game directory not found"

        try:
            result = subprocess.run(
                ["flutter", "test"],
                cwd=str(game_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                return True, "All tests passed"
            else:
                return False, result.stderr or result.stdout
        except subprocess.TimeoutExpired:
            return False, "Tests timed out"
        except FileNotFoundError:
            return False, "Flutter not found"
        except Exception as e:
            return False, str(e)

    def run_flutter_analyze(self, game_info: GameInfo) -> Tuple[bool, str]:
        """Run Flutter analyze for a game"""
        game_dir = game_info.path / "game"
        if not game_dir.exists():
            return False, "Game directory not found"

        try:
            result = subprocess.run(
                ["flutter", "analyze"],
                cwd=str(game_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                return True, "No issues found"
            else:
                # Count issues
                lines = result.stdout.split("\n")
                issues = [l for l in lines if "error" in l.lower() or "warning" in l.lower()]
                return False, f"{len(issues)} issues found"
        except Exception as e:
            return False, str(e)

    def build_apk(
        self, game_info: GameInfo, release: bool = False
    ) -> Tuple[bool, str]:
        """Build Android APK"""
        game_dir = game_info.path / "game"
        if not game_dir.exists():
            return False, "Game directory not found"

        mode = "--release" if release else "--debug"
        try:
            result = subprocess.run(
                ["flutter", "build", "apk", mode],
                cwd=str(game_dir),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                apk_path = game_dir / "build" / "app" / "outputs" / "flutter-apk"
                return True, f"APK built: {apk_path}"
            else:
                return False, result.stderr or "Build failed"
        except Exception as e:
            return False, str(e)

    def build_ios(
        self, game_info: GameInfo, release: bool = False
    ) -> Tuple[bool, str]:
        """Build iOS"""
        game_dir = game_info.path / "game"
        if not game_dir.exists():
            return False, "Game directory not found"

        mode = "--release" if release else "--debug"
        try:
            result = subprocess.run(
                ["flutter", "build", "ios", mode, "--no-codesign"],
                cwd=str(game_dir),
                capture_output=True,
                text=True,
                timeout=900,
            )
            if result.returncode == 0:
                return True, "iOS build completed"
            else:
                return False, result.stderr or "Build failed"
        except Exception as e:
            return False, str(e)

    def get_dependencies(self, game_info: GameInfo) -> Tuple[bool, str]:
        """Get Flutter dependencies"""
        game_dir = game_info.path / "game"
        if not game_dir.exists():
            return False, "Game directory not found"

        try:
            result = subprocess.run(
                ["flutter", "pub", "get"],
                cwd=str(game_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return True, "Dependencies resolved"
            else:
                return False, result.stderr or "Failed to get dependencies"
        except Exception as e:
            return False, str(e)


# Click commands
@click.group("cicd")
def cicd():
    """CI/CD commands for building and testing"""
    pass


@cicd.command("test")
@click.option("--game", "-g", help="Specific game ID")
@click.option("--all", "all_games", is_flag=True, help="Test all games")
@click.pass_context
def run_tests(ctx, game, all_games):
    """Run Flutter tests"""
    scanner: GameScanner = ctx.obj["scanner"]
    service = CICDService(scanner)

    if game:
        game_info = scanner.get_game(game)
        if not game_info or not game_info.exists:
            click.echo(f"Game {game} not found")
            return

        click.echo(f"Testing {game_info.name}...")
        success, msg = service.run_flutter_tests(game_info)
        status = "[OK]" if success else "[FAIL]"
        click.echo(f"  {status} {msg}")
    elif all_games:
        games = scanner.filter_games()
        passed = 0
        failed = 0

        for g in games:
            click.echo(f"Testing {g.name}...", nl=False)
            success, msg = service.run_flutter_tests(g)
            if success:
                click.echo(" [OK]")
                passed += 1
            else:
                click.echo(f" [FAIL] {msg}")
                failed += 1

        click.echo(f"\nResults: {passed} passed, {failed} failed")
    else:
        click.echo("Specify --game or --all")


@cicd.command("analyze")
@click.option("--game", "-g", help="Specific game ID")
@click.option("--all", "all_games", is_flag=True, help="Analyze all games")
@click.pass_context
def run_analyze(ctx, game, all_games):
    """Run Flutter analyze"""
    scanner: GameScanner = ctx.obj["scanner"]
    service = CICDService(scanner)

    if game:
        game_info = scanner.get_game(game)
        if not game_info or not game_info.exists:
            click.echo(f"Game {game} not found")
            return

        click.echo(f"Analyzing {game_info.name}...")
        success, msg = service.run_flutter_analyze(game_info)
        status = "[OK]" if success else "[WARN]"
        click.echo(f"  {status} {msg}")
    elif all_games:
        games = scanner.filter_games()
        clean = 0
        issues = 0

        for g in games:
            click.echo(f"Analyzing {g.name}...", nl=False)
            success, msg = service.run_flutter_analyze(g)
            if success:
                click.echo(" [OK]")
                clean += 1
            else:
                click.echo(f" [WARN] {msg}")
                issues += 1

        click.echo(f"\nResults: {clean} clean, {issues} with issues")
    else:
        click.echo("Specify --game or --all")


@cicd.command("build")
@click.option("--game", "-g", required=True, help="Game ID to build")
@click.option("--platform", "-p", type=click.Choice(["android", "ios", "all"]),
              default="android", help="Target platform")
@click.option("--release", "-r", is_flag=True, help="Build release version")
@click.pass_context
def build(ctx, game, platform, release):
    """Build game for specified platform"""
    scanner: GameScanner = ctx.obj["scanner"]
    service = CICDService(scanner)

    game_info = scanner.get_game(game)
    if not game_info or not game_info.exists:
        click.echo(f"Game {game} not found")
        return

    mode = "release" if release else "debug"
    click.echo(f"Building {game_info.name} ({mode})...")

    # Get dependencies first
    click.echo("  Getting dependencies...")
    success, msg = service.get_dependencies(game_info)
    if not success:
        click.echo(f"  [FAIL] {msg}")
        return

    if platform in ["android", "all"]:
        click.echo("  Building Android APK...")
        success, msg = service.build_apk(game_info, release)
        status = "[OK]" if success else "[FAIL]"
        click.echo(f"  {status} {msg}")

    if platform in ["ios", "all"]:
        click.echo("  Building iOS...")
        success, msg = service.build_ios(game_info, release)
        status = "[OK]" if success else "[FAIL]"
        click.echo(f"  {status} {msg}")


@cicd.command("deps")
@click.option("--game", "-g", help="Specific game ID")
@click.option("--all", "all_games", is_flag=True, help="Update all games")
@click.pass_context
def get_deps(ctx, game, all_games):
    """Get/update Flutter dependencies"""
    scanner: GameScanner = ctx.obj["scanner"]
    service = CICDService(scanner)

    if game:
        game_info = scanner.get_game(game)
        if not game_info or not game_info.exists:
            click.echo(f"Game {game} not found")
            return

        click.echo(f"Getting dependencies for {game_info.name}...")
        success, msg = service.get_dependencies(game_info)
        status = "[OK]" if success else "[FAIL]"
        click.echo(f"  {status} {msg}")
    elif all_games:
        games = scanner.filter_games()

        for g in games:
            click.echo(f"Getting deps for {g.name}...", nl=False)
            success, msg = service.get_dependencies(g)
            if success:
                click.echo(" [OK]")
            else:
                click.echo(f" [FAIL]")

        click.echo("\nDone!")
    else:
        click.echo("Specify --game or --all")
