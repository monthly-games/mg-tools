"""
Commit Firebase configuration files for all games
"""
import subprocess
import os

REPOS_DIR = r"d:\mg-games\repos"
GAMES = ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0012", "0013", "0014", "0015"]

COMMIT_MESSAGE = """Add Firebase configuration files

- firebase_options.dart: Flutter Firebase options
- google-services.json: Android Firebase config
- GoogleService-Info.plist: iOS Firebase config

Project: mg-games-dev

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"""

def commit_game(game_id: str) -> bool:
    game_dir = os.path.join(REPOS_DIR, f"mg-game-{game_id}")

    if not os.path.exists(game_dir):
        print(f"  [SKIP] Directory not found")
        return False

    try:
        # Add Firebase files
        files_to_add = [
            "game/lib/firebase_options.dart",
            "game/android/app/google-services.json",
            "game/ios/Runner/GoogleService-Info.plist"
        ]

        for f in files_to_add:
            full_path = os.path.join(game_dir, f)
            if os.path.exists(full_path):
                subprocess.run(["git", "add", f], cwd=game_dir, capture_output=True)

        # Check if there are changes to commit
        status = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=game_dir, capture_output=True, text=True
        )

        if not status.stdout.strip():
            print(f"  [SKIP] No changes to commit")
            return True

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", COMMIT_MESSAGE],
            cwd=game_dir, capture_output=True, text=True, encoding='utf-8', errors='replace'
        )

        if result.returncode == 0:
            print(f"  [OK] Committed")
            return True
        else:
            print(f"  [FAIL] {result.stderr[:50]}")
            return False

    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def main():
    print(f"Committing Firebase config for {len(GAMES)} games")
    print("=" * 50)

    success = 0
    for i, game_id in enumerate(GAMES):
        print(f"\n[{i+1}/{len(GAMES)}] MG-{game_id}")
        if commit_game(game_id):
            success += 1

    print("\n" + "=" * 50)
    print(f"Done! Success: {success}/{len(GAMES)}")

if __name__ == "__main__":
    main()
