"""
Configure FlutterFire for all registered MG Games (0001-0015)
"""
import subprocess
import os
import time

# 등록된 게임 목록 (Firebase에 앱이 등록된 게임)
GAMES = [f"{i:04d}" for i in range(1, 16)]

REPOS_DIR = r"d:\mg-games\repos"
FLUTTERFIRE_CMD = r"C:\Users\USER-5\AppData\Local\Pub\Cache\bin\flutterfire.bat"

def configure_game(game_id: str) -> bool:
    """Run flutterfire configure for a game"""
    game_dir = os.path.join(REPOS_DIR, f"mg-game-{game_id}", "game")

    if not os.path.exists(game_dir):
        print(f"  [SKIP] Game directory not found")
        return False

    package = f"com.monthlygames.game{game_id}"

    cmd = [
        FLUTTERFIRE_CMD, "configure",
        "--project", "mg-games-dev",
        "--platforms", "android,ios",
        "--android-package-name", package,
        "--ios-bundle-id", package,
        "--yes"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=game_dir,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )

        if "generated successfully" in result.stdout:
            print(f"  [OK] firebase_options.dart generated")
            return True
        elif "Error" in result.stderr:
            print(f"  [FAIL] {result.stderr[:100]}")
            return False
        else:
            print(f"  [OK] Configured")
            return True

    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT]")
        return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def main():
    print(f"Configuring FlutterFire for {len(GAMES)} games")
    print("=" * 50)

    success = 0
    failed = 0

    for i, game_id in enumerate(GAMES):
        print(f"\n[{i+1}/{len(GAMES)}] MG-{game_id}")

        if configure_game(game_id):
            success += 1
        else:
            failed += 1

        # Rate limiting
        if (i + 1) % 5 == 0 and i < len(GAMES) - 1:
            print("\n  Waiting 3 seconds...")
            time.sleep(3)

    print("\n" + "=" * 50)
    print(f"Done! Success: {success}, Failed: {failed}")

if __name__ == "__main__":
    main()
