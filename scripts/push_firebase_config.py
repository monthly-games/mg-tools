"""
Push Firebase configuration commits for all games
"""
import subprocess
import os

REPOS_DIR = r"d:\mg-games\repos"
GAMES = ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0012", "0013", "0014", "0015"]

def push_game(game_id: str) -> bool:
    game_dir = os.path.join(REPOS_DIR, f"mg-game-{game_id}")

    if not os.path.exists(game_dir):
        return False

    try:
        result = subprocess.run(
            ["git", "push"],
            cwd=game_dir, capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace'
        )

        if result.returncode == 0:
            print(f"  [OK] Pushed")
            return True
        elif "up-to-date" in result.stderr:
            print(f"  [OK] Already up-to-date")
            return True
        else:
            print(f"  [FAIL] {result.stderr[:80]}")
            return False

    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def main():
    print(f"Pushing Firebase config for {len(GAMES)} games")
    print("=" * 50)

    success = 0
    for i, game_id in enumerate(GAMES):
        print(f"[{i+1}/{len(GAMES)}] MG-{game_id}")
        if push_game(game_id):
            success += 1

    print("\n" + "=" * 50)
    print(f"Done! Success: {success}/{len(GAMES)}")

if __name__ == "__main__":
    main()
