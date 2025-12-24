"""
MG-CLI: Main CLI entry point

Usage:
    mg-cli status                     # Show overall status
    mg-cli status --game 0001         # Show single game status
    mg-cli firebase init --game 0001  # Initialize Firebase for a game
    mg-cli firebase init --all        # Initialize Firebase for all games
    mg-cli ads setup --game 0001      # Setup AdMob for a game
    mg-cli config set-env dev         # Set environment
    mg-cli cicd test --game 0001      # Run tests
    mg-cli analytics setup --game 0001 # Setup analytics
    mg-cli marketing plan --game 0001 # Create marketing plan
    mg-cli infra terraform --game 0001 # Generate Terraform config
"""

import click
from pathlib import Path
from typing import Optional

from .config import get_config, init_config
from .services.game_scanner import GameScanner
from .services.firebase_service import FirebaseService
from .services.ads_service import AdsService
from .commands.cicd import cicd
from .commands.analytics import analytics, marketing
from .commands.infra import infra


# CLI group
@click.group()
@click.option("--config", "-c", type=click.Path(exists=False), help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--dry-run", is_flag=True, help="Dry run mode (no changes)")
@click.pass_context
def cli(ctx, config, verbose, dry_run):
    """MG-CLI: Manage MG Games projects"""
    ctx.ensure_object(dict)

    # Initialize config
    if config:
        cfg = init_config(Path(config))
    else:
        cfg = get_config()

    if dry_run:
        cfg._config["batch"]["dry_run"] = True

    ctx.obj["config"] = cfg
    ctx.obj["verbose"] = verbose
    ctx.obj["scanner"] = GameScanner()


# ============================================
# Status Commands
# ============================================

@cli.command("status")
@click.option("--game", "-g", help="Specific game ID (e.g., 0001)")
@click.option("--type", "game_type", type=click.Choice(["original", "jrpg_level_a", "casual"]),
              help="Filter by game type")
@click.option("--firebase", "show_firebase", is_flag=True, help="Show Firebase status only")
@click.option("--ads", "show_ads", is_flag=True, help="Show Ads status only")
@click.pass_context
def status(ctx, game, game_type, show_firebase, show_ads):
    """Show status of games"""
    scanner: GameScanner = ctx.obj["scanner"]
    verbose = ctx.obj["verbose"]

    if game:
        # Single game status
        game_info = scanner.get_game(game)
        if not game_info:
            click.echo(f"Game {game} not found")
            return

        _print_game_status(game_info, verbose)
    else:
        # Summary status
        summary = scanner.get_summary()
        _print_summary(summary)

        if verbose or game_type:
            games = scanner.filter_games(game_type=game_type)
            click.echo(f"\n{'='*60}")
            click.echo(f"Games ({len(games)}):")
            click.echo(f"{'='*60}")

            for g in games:
                fb_status = "O" if g.firebase_ready else "X"
                ads_status = "O" if g.ads_ready else "X"
                click.echo(f"  {g.name}: Firebase[{fb_status}] Ads[{ads_status}] - {g.game_type}")


def _print_game_status(game_info, verbose: bool = False):
    """Print status for a single game"""
    click.echo(f"\n{'='*60}")
    click.echo(f"Game: {game_info.name}")
    click.echo(f"{'='*60}")

    if not game_info.exists:
        click.echo("  Status: NOT FOUND")
        return

    click.echo(f"  Path: {game_info.path}")
    click.echo(f"  Type: {game_info.game_type}")
    click.echo(f"  Submodule: {game_info.submodule_type.value}")
    click.echo(f"  Documents: {game_info.document_count}")

    click.echo("\n  Firebase:")
    click.echo(f"    firebase.json:       {'[O]' if game_info.has_firebase_json else '[X]'}")
    click.echo(f"    firebase_options:    {'[O]' if game_info.has_firebase_options else '[X]'}")
    click.echo(f"    google-services:     {'[O]' if game_info.has_google_services else '[X]'}")
    click.echo(f"    GoogleService-Info:  {'[O]' if game_info.has_google_service_info else '[X]'}")
    click.echo(f"    Dependencies:        {'Enabled' if game_info.firebase_deps_enabled else 'Disabled'}")
    click.echo(f"    Ready:               {'[O] YES' if game_info.firebase_ready else '[X] NO'}")

    click.echo("\n  Ads:")
    click.echo(f"    Android Manifest:    {'[O]' if game_info.has_admob_android else '[X]'}")
    click.echo(f"    iOS Info.plist:      {'[O]' if game_info.has_admob_ios else '[X]'}")
    click.echo(f"    Dependencies:        {'Enabled' if game_info.ads_deps_enabled else 'Disabled'}")
    click.echo(f"    Ready:               {'[O] YES' if game_info.ads_ready else '[X] NO'}")


def _print_summary(summary: dict):
    """Print summary statistics"""
    click.echo(f"\n{'='*60}")
    click.echo("MG Games Status Summary")
    click.echo(f"{'='*60}")

    click.echo(f"\n  Total Registered: {summary['total_registered']}")
    click.echo(f"  Existing:         {summary['existing']}")
    click.echo(f"  Missing:          {summary['missing']}")

    click.echo(f"\n  Firebase Ready:   {summary['firebase_ready']}/{summary['existing']}")
    click.echo(f"  Ads Ready:        {summary['ads_ready']}/{summary['existing']}")

    click.echo("\n  By Type:")
    for t, count in summary.get("by_type", {}).items():
        click.echo(f"    {t}: {count}")

    click.echo("\n  By Submodule:")
    for s, count in summary.get("by_submodule", {}).items():
        click.echo(f"    {s}: {count}")


# ============================================
# Firebase Commands
# ============================================

@cli.group("firebase")
def firebase():
    """Firebase configuration commands"""
    pass


@firebase.command("init")
@click.option("--game", "-g", help="Specific game ID (e.g., 0001)")
@click.option("--all", "all_games", is_flag=True, help="Process all games")
@click.option("--force", "-f", is_flag=True, help="Force overwrite existing config")
@click.pass_context
def firebase_init(ctx, game, all_games, force):
    """Initialize Firebase for game(s)"""
    scanner: GameScanner = ctx.obj["scanner"]
    config = ctx.obj["config"]
    dry_run = config.is_dry_run

    if not game and not all_games:
        click.echo("Error: Specify --game or --all")
        return

    if all_games:
        games = scanner.filter_games(firebase_ready=False)
        click.echo(f"Processing {len(games)} games without Firebase...")

        for g in games:
            _firebase_init_game(g, config, dry_run, force)
    else:
        game_info = scanner.get_game(game)
        if not game_info or not game_info.exists:
            click.echo(f"Game {game} not found")
            return

        _firebase_init_game(game_info, config, dry_run, force)


def _firebase_init_game(game_info, config, dry_run: bool, force: bool):
    """Initialize Firebase for a single game"""
    if game_info.firebase_ready and not force:
        click.echo(f"  [SKIP] {game_info.name}: Firebase already configured")
        return

    if dry_run:
        click.echo(f"  [DRY-RUN] {game_info.name}: Would initialize Firebase")
        return

    service = FirebaseService(config)
    success, message = service.init_firebase(game_info, force)

    if success:
        click.echo(f"  [OK] {game_info.name}: {message}")
    else:
        click.echo(f"  [FAIL] {game_info.name}: {message}")


@firebase.command("status")
@click.option("--game", "-g", help="Specific game ID")
@click.pass_context
def firebase_status(ctx, game):
    """Show Firebase configuration status"""
    scanner: GameScanner = ctx.obj["scanner"]

    if game:
        game_info = scanner.get_game(game)
        if not game_info:
            click.echo(f"Game {game} not found")
            return
        _print_game_status(game_info)
    else:
        # Summary
        games = scanner.scan_all()
        existing = [g for g in games if g.exists]
        ready = [g for g in existing if g.firebase_ready]
        not_ready = [g for g in existing if not g.firebase_ready]

        click.echo(f"\nFirebase Status: {len(ready)}/{len(existing)} ready")
        click.echo(f"\nNot configured ({len(not_ready)}):")
        for g in not_ready[:10]:
            click.echo(f"  - {g.name}")
        if len(not_ready) > 10:
            click.echo(f"  ... and {len(not_ready) - 10} more")


@firebase.command("create")
@click.option("--game", "-g", help="Specific game ID (e.g., 0001)")
@click.option("--all", "all_games", is_flag=True, help="Create for all games")
@click.option("--batch-size", default=5, help="Batch size for rate limiting")
@click.pass_context
def firebase_create(ctx, game, all_games, batch_size):
    """Create Firebase project(s) via Firebase CLI"""
    scanner: GameScanner = ctx.obj["scanner"]
    config = ctx.obj["config"]
    dry_run = config.is_dry_run

    service = FirebaseService(config)

    # Check CLI availability
    available, msg = service.check_cli_available()
    if not available:
        click.echo(f"[ERROR] {msg}")
        return
    click.echo(f"[OK] {msg}")

    if not game and not all_games:
        click.echo("Error: Specify --game or --all")
        return

    if game:
        game_info = scanner.get_game(game)
        if not game_info or not game_info.exists:
            click.echo(f"Game {game} not found")
            return

        click.echo(f"\nCreating Firebase project for {game_info.name}...")
        success, msg = service.create_and_configure(game_info, dry_run)
        status = "[OK]" if success else "[FAIL]"
        click.echo(f"  {status} {msg}")
    else:
        games = scanner.filter_games()
        click.echo(f"\nCreating Firebase projects for {len(games)} games (batch size: {batch_size})...")

        import time
        for i, g in enumerate(games):
            click.echo(f"\n[{i+1}/{len(games)}] {g.name}")
            success, msg = service.create_and_configure(g, dry_run)
            status = "[OK]" if success else "[FAIL]"
            click.echo(f"  {status} {msg}")

            # Rate limiting between batches
            if (i + 1) % batch_size == 0 and i < len(games) - 1:
                click.echo(f"\n  Waiting 30 seconds for rate limit...")
                if not dry_run:
                    time.sleep(30)

        click.echo("\nDone!")


@firebase.command("configure")
@click.option("--game", "-g", required=True, help="Game ID to configure")
@click.pass_context
def firebase_configure(ctx, game):
    """Run FlutterFire configure for a game"""
    scanner: GameScanner = ctx.obj["scanner"]
    config = ctx.obj["config"]
    dry_run = config.is_dry_run

    service = FirebaseService(config)

    # Check FlutterFire CLI
    available, msg = service.check_flutterfire_available()
    if not available:
        click.echo(f"[ERROR] {msg}")
        return
    click.echo(f"[OK] {msg}")

    game_info = scanner.get_game(game)
    if not game_info or not game_info.exists:
        click.echo(f"Game {game} not found")
        return

    click.echo(f"\nRunning FlutterFire configure for {game_info.name}...")
    success, msg = service.run_flutterfire_configure(game_info, dry_run)

    if success:
        click.echo(f"  [OK] {msg}")
    else:
        click.echo(f"  [FAIL] {msg}")


@firebase.command("list")
@click.pass_context
def firebase_list(ctx):
    """List existing Firebase projects"""
    config = ctx.obj["config"]
    service = FirebaseService(config)

    available, msg = service.check_cli_available()
    if not available:
        click.echo(f"[ERROR] {msg}")
        return

    click.echo("Fetching Firebase projects...")
    success, projects = service.list_projects()

    if success:
        mg_projects = [p for p in projects if p.startswith("mg-game-")]
        other_projects = [p for p in projects if not p.startswith("mg-game-")]

        click.echo(f"\nMG Game Projects ({len(mg_projects)}):")
        for p in sorted(mg_projects):
            click.echo(f"  - {p}")

        if other_projects:
            click.echo(f"\nOther Projects ({len(other_projects)}):")
            for p in sorted(other_projects)[:5]:
                click.echo(f"  - {p}")
            if len(other_projects) > 5:
                click.echo(f"  ... and {len(other_projects) - 5} more")
    else:
        click.echo(f"[FAIL] {projects}")


# ============================================
# Ads Commands
# ============================================

@cli.group("ads")
def ads():
    """Ads SDK configuration commands"""
    pass


@ads.command("setup")
@click.option("--game", "-g", help="Specific game ID (e.g., 0001)")
@click.option("--all", "all_games", is_flag=True, help="Process all games")
@click.option("--sdk", type=click.Choice(["admob", "unity", "max"]), default="admob",
              help="Ads SDK to use")
@click.option("--force", "-f", is_flag=True, help="Force overwrite existing config")
@click.pass_context
def ads_setup(ctx, game, all_games, sdk, force):
    """Setup Ads SDK for game(s)"""
    scanner: GameScanner = ctx.obj["scanner"]
    config = ctx.obj["config"]
    dry_run = config.is_dry_run

    if not game and not all_games:
        click.echo("Error: Specify --game or --all")
        return

    if sdk != "admob":
        click.echo(f"SDK '{sdk}' not yet supported. Only 'admob' is currently available.")
        return

    if all_games:
        games = scanner.filter_games(ads_ready=False)
        click.echo(f"Processing {len(games)} games without Ads SDK...")

        for g in games:
            _ads_setup_game(g, config, dry_run, force)
    else:
        game_info = scanner.get_game(game)
        if not game_info or not game_info.exists:
            click.echo(f"Game {game} not found")
            return

        _ads_setup_game(game_info, config, dry_run, force)


def _ads_setup_game(game_info, config, dry_run: bool, force: bool):
    """Setup Ads for a single game"""
    if game_info.ads_ready and not force:
        click.echo(f"  [SKIP] {game_info.name}: Ads already configured")
        return

    if dry_run:
        click.echo(f"  [DRY-RUN] {game_info.name}: Would setup AdMob")
        return

    service = AdsService(config)
    success, message = service.setup_ads(game_info, force)

    if success:
        click.echo(f"  [OK] {game_info.name}: {message}")
    else:
        click.echo(f"  [FAIL] {game_info.name}: {message}")


@ads.command("test-mode")
@click.option("--game", "-g", help="Specific game ID")
@click.option("--enable/--disable", default=True, help="Enable or disable test mode")
@click.pass_context
def ads_test_mode(ctx, game, enable):
    """Toggle test mode for ads"""
    config = ctx.obj["config"]

    if game:
        click.echo(f"Test mode {'enabled' if enable else 'disabled'} for {game}")
    else:
        config._config["ads"]["test_mode"] = enable
        config.save_config()
        click.echo(f"Global test mode {'enabled' if enable else 'disabled'}")


# ============================================
# Config Commands
# ============================================

@cli.group("config")
def config_group():
    """Configuration management commands"""
    pass


@config_group.command("show")
@click.pass_context
def config_show(ctx):
    """Show current configuration"""
    config = ctx.obj["config"]

    click.echo("\nCurrent Configuration:")
    click.echo(f"  Environment: {config.environment}")
    click.echo(f"  Test Mode: {config.is_test_mode}")
    click.echo(f"  Dry Run: {config.is_dry_run}")

    click.echo("\n  Firebase:")
    for k, v in config.firebase_config.items():
        click.echo(f"    {k}: {v}")

    click.echo("\n  Ads:")
    for k, v in config.ads_config.items():
        click.echo(f"    {k}: {v}")


@config_group.command("set-env")
@click.argument("env", type=click.Choice(["dev", "staging", "prod"]))
@click.pass_context
def config_set_env(ctx, env):
    """Set environment (dev/staging/prod)"""
    config = ctx.obj["config"]
    config.environment = env
    config.save_config()
    click.echo(f"Environment set to: {env}")


@config_group.command("init")
@click.pass_context
def config_init(ctx):
    """Initialize default configuration file"""
    config = ctx.obj["config"]
    config.save_config()
    click.echo(f"Configuration saved to: {config.config_path / 'mg_cli_config.yaml'}")


# ============================================
# Batch Commands
# ============================================

@cli.group("batch")
def batch():
    """Batch processing commands"""
    pass


@batch.command("scan")
@click.pass_context
def batch_scan(ctx):
    """Scan all games and report status"""
    scanner: GameScanner = ctx.obj["scanner"]

    click.echo("Scanning all games...")
    games = scanner.scan_all(force_refresh=True)

    existing = [g for g in games if g.exists]
    click.echo(f"\nFound {len(existing)} games")

    # Firebase status
    fb_ready = len([g for g in existing if g.firebase_ready])
    fb_missing = len(existing) - fb_ready

    # Ads status
    ads_ready = len([g for g in existing if g.ads_ready])
    ads_missing = len(existing) - ads_ready

    click.echo(f"\nFirebase: {fb_ready} ready, {fb_missing} need setup")
    click.echo(f"Ads:      {ads_ready} ready, {ads_missing} need setup")


@batch.command("setup-all")
@click.option("--firebase", "setup_firebase", is_flag=True, help="Setup Firebase")
@click.option("--ads", "setup_ads", is_flag=True, help="Setup Ads")
@click.confirmation_option(prompt="This will modify all games. Continue?")
@click.pass_context
def batch_setup_all(ctx, setup_firebase, setup_ads):
    """Setup Firebase and/or Ads for all games"""
    scanner: GameScanner = ctx.obj["scanner"]
    config = ctx.obj["config"]
    dry_run = config.is_dry_run

    if not setup_firebase and not setup_ads:
        click.echo("Specify --firebase and/or --ads")
        return

    games = scanner.scan_all()
    existing = [g for g in games if g.exists]

    click.echo(f"Processing {len(existing)} games...")

    for game in existing:
        if setup_firebase and not game.firebase_ready:
            _firebase_init_game(game, config, dry_run, force=False)

        if setup_ads and not game.ads_ready:
            _ads_setup_game(game, config, dry_run, force=False)

    click.echo("\nDone!")


# ============================================
# Register Additional Command Groups
# ============================================

cli.add_command(cicd)
cli.add_command(analytics)
cli.add_command(marketing)
cli.add_command(infra)


# Entry point
if __name__ == "__main__":
    cli()
