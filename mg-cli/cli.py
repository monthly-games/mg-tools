"""Main CLI entry point for mg-cli."""

import click
from pathlib import Path

if __package__:
    from .config import CLIConfig
    from .services.game_scanner import GameScanner
    from .services.firebase_service import FirebaseService
    from .services.ads_service import AdsService
    from .commands.batch import BatchService
else:
    from mg_cli.config import CLIConfig
    from mg_cli.services.game_scanner import GameScanner
    from mg_cli.services.firebase_service import FirebaseService
    from mg_cli.services.ads_service import AdsService
    from mg_cli.commands.batch import BatchService


# Load configuration
config = CLIConfig.load()


@click.group()
@click.version_option(version="0.1.0", prog_name="mg-cli")
def main():
    """MG-CLI: Firebase and Ads SDK management for Monthly Games."""
    pass


# ============================================================================
# Firebase Commands
# ============================================================================

@main.group()
def firebase():
    """Firebase configuration commands."""
    pass


@firebase.command('init')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0001)')
@click.option('--all', 'all_games', is_flag=True, help='Apply to all games')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def firebase_init(game, all_games, dry_run):
    """Initialize Firebase configuration for games."""
    scanner = GameScanner(config.repos_path)
    service = FirebaseService(config)

    if all_games:
        game_ids = config.get_game_ids()
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    for gid in game_ids:
        game_info = scanner.scan_game(gid)
        if not game_info.exists:
            click.echo(f"[SKIP] MG-{gid:04d}: Repository not found")
            continue

        click.echo(f"\n[MG-{gid:04d}] Initializing Firebase...")

        # Generate firebase_options.dart
        success, msg = service.generate_firebase_options(game_info, dry_run=dry_run)
        click.echo(f"  - {msg}")

        # Enable dependencies
        success, msg = service.enable_pubspec_deps(game_info, dry_run=dry_run)
        click.echo(f"  - {msg}")


@firebase.command('create')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0001)')
@click.option('--all', 'all_games', is_flag=True, help='Create for all games')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def firebase_create(game, all_games, dry_run):
    """Create Firebase projects via Firebase CLI."""
    service = FirebaseService(config)

    # Check CLI
    installed, version = service.check_cli_installed()
    if not installed:
        click.echo(f"Error: Firebase CLI not installed. Run: npm install -g firebase-tools")
        return
    click.echo(f"Firebase CLI: {version}")

    if all_games:
        game_ids = config.get_game_ids()
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    for gid in game_ids:
        game_id_str = f"{gid:04d}"
        click.echo(f"\n[MG-{game_id_str}] Creating Firebase project...")

        success, msg = service.create_project(game_id_str, dry_run=dry_run)
        click.echo(f"  - {msg}")

        if success and not dry_run:
            success, msg = service.register_apps(game_id_str, dry_run=dry_run)
            click.echo(f"  - {msg}")


@firebase.command('configure')
@click.option('--game', '-g', type=str, required=True, help='Game ID (e.g., 0001)')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def firebase_configure(game, dry_run):
    """Run FlutterFire configure for a game."""
    scanner = GameScanner(config.repos_path)
    service = FirebaseService(config)

    # Check FlutterFire CLI
    installed, version = service.check_flutterfire_installed()
    if not installed:
        click.echo("Error: FlutterFire CLI not installed. Run: dart pub global activate flutterfire_cli")
        return
    click.echo(f"FlutterFire CLI: {version}")

    game_info = scanner.scan_game(int(game))
    if not game_info.exists:
        click.echo(f"Error: Game MG-{game} not found")
        return

    success, msg = service.run_flutterfire_configure(game_info, dry_run=dry_run)
    click.echo(msg)


@firebase.command('status')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0001)')
@click.option('--all', 'all_games', is_flag=True, help='Show all games')
def firebase_status(game, all_games):
    """Show Firebase configuration status."""
    scanner = GameScanner(config.repos_path)
    service = FirebaseService(config)

    if all_games:
        game_ids = config.get_game_ids()
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    click.echo("\nFirebase Configuration Status")
    click.echo("=" * 60)
    click.echo(f"{'Game':<10} {'Options':<10} {'Android':<10} {'iOS':<10} {'Deps':<10}")
    click.echo("-" * 60)

    for gid in game_ids:
        game_info = scanner.scan_game(gid)
        if not game_info.exists:
            continue

        status = service.get_status(game_info)
        click.echo(
            f"MG-{gid:04d}  "
            f"{'[OK]' if status['firebase_options'] else '[--]':<10}"
            f"{'[OK]' if status['google_services_json'] else '[--]':<10}"
            f"{'[OK]' if status['google_service_info_plist'] else '[--]':<10}"
            f"{'[OK]' if status['deps_enabled'] else '[--]':<10}"
        )


@firebase.command('list')
def firebase_list():
    """List Firebase projects from console."""
    service = FirebaseService(config)

    installed, _ = service.check_cli_installed()
    if not installed:
        click.echo("Error: Firebase CLI not installed")
        return

    success, projects = service.list_projects()
    if success:
        click.echo(f"\nFound {len(projects)} projects:")
        for proj in projects:
            if proj.startswith('mg-game-'):
                click.echo(f"  - {proj}")
    else:
        click.echo("Failed to list projects. Make sure you're logged in: firebase login")


# ============================================================================
# Ads Commands
# ============================================================================

@main.group()
def ads():
    """Ads SDK configuration commands."""
    pass


@ads.command('setup')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0001)')
@click.option('--all', 'all_games', is_flag=True, help='Apply to all games')
@click.option('--sdk', type=click.Choice(['admob']), default='admob', help='Ads SDK to use')
@click.option('--test-mode/--prod-mode', default=True, help='Use test or production IDs')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def ads_setup(game, all_games, sdk, test_mode, dry_run):
    """Setup Ads SDK for games."""
    scanner = GameScanner(config.repos_path)
    service = AdsService(config)

    if all_games:
        game_ids = config.get_game_ids()
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    mode_str = "TEST" if test_mode else "PRODUCTION"
    click.echo(f"\nAds SDK Setup ({sdk.upper()}, {mode_str} mode)")
    click.echo("=" * 60)

    for gid in game_ids:
        game_info = scanner.scan_game(gid)
        if not game_info.exists:
            click.echo(f"[SKIP] MG-{gid:04d}: Repository not found")
            continue

        click.echo(f"\n[MG-{gid:04d}] Setting up {sdk}...")
        success, msg = service.setup_game(game_info, test_mode=test_mode, dry_run=dry_run)
        for line in msg.split('\n'):
            click.echo(f"  - {line}")


@ads.command('status')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0001)')
@click.option('--all', 'all_games', is_flag=True, help='Show all games')
def ads_status(game, all_games):
    """Show Ads SDK configuration status."""
    scanner = GameScanner(config.repos_path)
    service = AdsService(config)

    if all_games:
        game_ids = config.get_game_ids()
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    click.echo("\nAds SDK Configuration Status")
    click.echo("=" * 60)
    click.echo(f"{'Game':<10} {'Configured':<12} {'Android ID':<30}")
    click.echo("-" * 60)

    for gid in game_ids:
        game_info = scanner.scan_game(gid)
        if not game_info.exists:
            continue

        status = service.get_status(game_info)
        android_id = status['android_app_id'] or '-'
        if len(android_id) > 28:
            android_id = android_id[:25] + '...'

        click.echo(
            f"MG-{gid:04d}  "
            f"{'[OK]' if status['has_config'] else '[--]':<12}"
            f"{android_id:<30}"
        )


@ads.command('test-mode')
@click.option('--game', '-g', type=str, required=True, help='Game ID')
@click.option('--enable/--disable', default=True, help='Enable or disable test mode')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def ads_test_mode(game, enable, dry_run):
    """Enable or disable test mode for a game."""
    scanner = GameScanner(config.repos_path)
    service = AdsService(config)

    game_info = scanner.scan_game(int(game))
    if not game_info.exists:
        click.echo(f"Error: Game MG-{game} not found")
        return

    # Re-run setup with appropriate mode
    success, msg = service.setup_game(game_info, test_mode=enable, dry_run=dry_run)
    action = "Enabled" if enable else "Disabled"
    click.echo(f"{action} test mode for MG-{game}")
    for line in msg.split('\n'):
        click.echo(f"  - {line}")


# ============================================================================
# Scan Commands
# ============================================================================

@main.command('scan')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0001)')
@click.option('--all', 'all_games', is_flag=True, help='Scan all games')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def scan(game, all_games, as_json):
    """Scan game repositories for configuration status."""
    import json as json_module

    scanner = GameScanner(config.repos_path)

    if all_games:
        game_ids = config.get_game_ids()
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    games = scanner.scan_all(game_ids)

    if as_json:
        output = [g.to_dict() for g in games if g.exists]
        click.echo(json_module.dumps(output, indent=2, ensure_ascii=False))
    else:
        summary = scanner.get_summary(games)
        click.echo("\nGame Repository Scan Summary")
        click.echo("=" * 40)
        click.echo(f"Total configured:     {summary['total_configured']}")
        click.echo(f"Existing:             {summary['existing']}")
        click.echo(f"Missing:              {summary['missing']}")
        click.echo(f"\nFirebase:")
        click.echo(f"  With options.dart:  {summary['firebase']['with_options']}")
        click.echo(f"  With google-services: {summary['firebase']['with_google_services']}")
        click.echo(f"  Deps enabled:       {summary['firebase']['deps_enabled']}")
        click.echo(f"\nAds:")
        click.echo(f"  With AdMob config:  {summary['ads']['with_admob']}")


# ============================================================================
# Config Commands
# ============================================================================

@main.group()
def config_cmd():
    """Configuration management commands."""
    pass


@config_cmd.command('show')
def config_show():
    """Show current configuration."""
    click.echo("\nMG-CLI Configuration")
    click.echo("=" * 40)
    click.echo(f"Repos path:     {config.repos_path}")
    click.echo(f"Config path:    {config.config_path}")
    click.echo(f"Environment:    {config.env}")
    click.echo(f"\nFirebase:")
    click.echo(f"  Project pattern: {config.firebase.project_id_pattern}")
    click.echo(f"  Dev project:     {config.firebase.dev_project}")
    click.echo(f"\nAds:")
    click.echo(f"  Android test ID: {config.ads.android_app_id_test}")
    click.echo(f"  iOS test ID:     {config.ads.ios_app_id_test}")


@config_cmd.command('set-env')
@click.argument('env', type=click.Choice(['dev', 'staging', 'prod']))
def config_set_env(env):
    """Set the environment (dev/staging/prod)."""
    config.env = env
    config.save()
    click.echo(f"Environment set to: {env}")


# Alias for config command (avoid conflict with config module)
main.add_command(config_cmd, name='config')


# ============================================================================
# Batch Commands
# ============================================================================

@main.group()
def batch():
    """Batch operations across multiple games."""
    pass


@batch.command('update-submodules')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0025)')
@click.option('--all', 'all_games', is_flag=True, help='Update all games')
@click.option('--submodule', '-s', default='libs/mg_common_game', help='Submodule path')
@click.option('--start', type=int, default=1, help='Start game ID (default: 1)')
@click.option('--end', type=int, default=52, help='End game ID (default: 52)')
def batch_update_submodules(game, all_games, submodule, start, end):
    """Update submodules in game repositories."""
    batch_svc = BatchService(config.repos_path)

    if all_games:
        game_ids = list(range(start, end + 1))
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    click.echo(f"\nUpdating submodule: {submodule}")
    click.echo("=" * 60)

    success_count = 0
    for gid in game_ids:
        success, msg = batch_svc.update_submodule(gid, submodule)
        status = "[OK]" if success else "[--]"
        click.echo(f"MG-{gid:04d}: {status} {msg}")
        if success:
            success_count += 1

    click.echo(f"\nUpdated: {success_count}/{len(game_ids)}")


@batch.command('fix-adapters')
@click.option('--game', '-g', type=str, help='Game ID (e.g., 0001)')
@click.option('--all', 'all_games', is_flag=True, help='Fix all games')
@click.option('--type', 'adapter_type', type=click.Choice(['gacha', 'battlepass', 'both']),
              default='both', help='Adapter type to fix')
@click.option('--start', type=int, default=1, help='Start game ID')
@click.option('--end', type=int, default=52, help='End game ID')
def batch_fix_adapters(game, all_games, adapter_type, start, end):
    """Fix gacha/battlepass adapters for new mg-common-game API."""
    batch_svc = BatchService(config.repos_path)

    if all_games:
        game_ids = list(range(start, end + 1))
    elif game:
        game_ids = [int(game)]
    else:
        click.echo("Error: Specify --game or --all")
        return

    click.echo(f"\nFixing adapters: {adapter_type}")
    click.echo("=" * 60)

    gacha_fixed = 0
    bp_fixed = 0

    for gid in game_ids:
        results = []

        if adapter_type in ('gacha', 'both'):
            success, msg = batch_svc.fix_gacha_adapter(gid)
            if success:
                gacha_fixed += 1
            results.append(f"gacha: {msg}")

        if adapter_type in ('battlepass', 'both'):
            success, msg = batch_svc.fix_battlepass_adapter(gid)
            if success:
                bp_fixed += 1
            results.append(f"battlepass: {msg}")

        click.echo(f"MG-{gid:04d}: {', '.join(results)}")

    click.echo(f"\nGacha fixed: {gacha_fixed}, BattlePass fixed: {bp_fixed}")


if __name__ == '__main__':
    main()
