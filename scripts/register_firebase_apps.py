"""
Register all MG Games apps in Firebase project mg-games-dev
"""
import subprocess
import time
import os

# 존재하는 게임 목록 (0035, 0039-0047 제외)
ALL_GAMES = [f"{i:04d}" for i in range(1, 53) if i != 35 and not (39 <= i <= 47)]

# 이미 등록된 게임 (0001-0015)
REGISTERED_GAMES = set(f"{i:04d}" for i in range(1, 16))

# 아직 등록 안 된 게임만 처리
GAMES = [g for g in ALL_GAMES if g not in REGISTERED_GAMES]

PROJECT_ID = "mg-games-dev"

# Windows firebase.cmd 경로
FIREBASE_CMD = os.path.join(os.environ.get("APPDATA", ""), "npm", "firebase.cmd")

def register_app(game_id: str, platform: str) -> bool:
    """Register an app in Firebase"""
    package = f"com.monthlygames.game{game_id}"

    if platform == "ANDROID":
        cmd = [FIREBASE_CMD, "apps:create", "ANDROID", "--package-name", package, "--project", PROJECT_ID]
    else:
        cmd = [FIREBASE_CMD, "apps:create", "IOS", "--bundle-id", package, "--project", PROJECT_ID]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"  [OK] {platform}: {package}")
            return True
        elif "already exists" in result.stderr.lower():
            print(f"  [SKIP] {platform}: already exists")
            return True
        else:
            print(f"  [FAIL] {platform}: {result.stderr.strip()[:100]}")
            return False
    except Exception as e:
        print(f"  [ERROR] {platform}: {e}")
        return False

def main():
    print(f"Registering {len(GAMES)} games in {PROJECT_ID}")
    print("=" * 50)

    for i, game_id in enumerate(GAMES):
        print(f"\n[{i+1}/{len(GAMES)}] MG-{game_id}")
        register_app(game_id, "ANDROID")
        register_app(game_id, "IOS")

        # Rate limiting every 10 games
        if (i + 1) % 10 == 0 and i < len(GAMES) - 1:
            print("\n  Waiting 5 seconds...")
            time.sleep(5)

    print("\n" + "=" * 50)
    print("Done!")

if __name__ == "__main__":
    main()
