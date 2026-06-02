"""Tests for scripts/lib/asset_registry.py — SQLite-based Spine asset deployment tracker."""

import pytest

from scripts.lib.asset_registry import AssetRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def registry(tmp_path):
    """Given a fresh registry backed by a temp database."""
    db_path = tmp_path / "test_assets.db"
    reg = AssetRegistry(str(db_path))
    yield reg
    reg.close()


@pytest.fixture
def populated(registry):
    """Given a registry with pre-registered assets across two games."""
    registry.register_asset("mg-game-0001", "skeleton", "hero/hero.skel", "4.1", "sha256:aaa")
    registry.register_asset("mg-game-0001", "atlas", "hero/hero.atlas", "4.1", "sha256:bbb")
    registry.register_asset("mg-game-0002", "skeleton", "villain/villain.skel", "4.1", "sha256:ccc")
    return registry


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------
class TestInit:
    def test_creates_db_on_disk(self, tmp_path):
        """Given a non-existent nested path — When creating registry — Then DB file exists."""
        db_path = tmp_path / "sub" / "registry.db"
        reg = AssetRegistry(str(db_path))
        assert db_path.exists()
        reg.close()

    def test_in_memory_db(self):
        """Given ':memory:' path — When registering — Then succeeds without file."""
        reg = AssetRegistry(":memory:")
        aid = reg.register_asset("g1", "skeleton", "a.skel", "4.0", "abc")
        assert isinstance(aid, int)
        reg.close()

    def test_idempotent_schema(self, tmp_path):
        """Given an already-initialised DB — When opening again — Then data preserved."""
        db_path = tmp_path / "twice.db"
        first = AssetRegistry(str(db_path))
        first.register_asset("g1", "skeleton", "a.skel", "4.0", "abc")
        first.close()
        second = AssetRegistry(str(db_path))
        assets = second.get_assets_for_game("g1")
        assert len(assets) == 1
        second.close()


# ---------------------------------------------------------------------------
# register_asset
# ---------------------------------------------------------------------------
class TestRegisterAsset:
    def test_returns_int_id(self, registry):
        """Given valid params — When registering — Then returns positive int id."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "hash1")
        assert isinstance(aid, int)
        assert aid > 0

    def test_stores_all_fields(self, registry):
        """Given all params — When registering then querying — Then all fields match."""
        registry.register_asset("g1", "atlas", "hero.atlas", "4.1", "sha256:abc")
        assets = registry.get_assets_for_game("g1")
        assert len(assets) == 1
        a = assets[0]
        assert a["game_id"] == "g1"
        assert a["asset_type"] == "atlas"
        assert a["file_path"] == "hero.atlas"
        assert a["spine_version"] == "4.1"
        assert a["checksum"] == "sha256:abc"

    def test_multiple_assets_same_game(self, registry):
        """Given two registrations for same game — When querying — Then both returned."""
        registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.register_asset("g1", "atlas", "a.atlas", "4.1", "h2")
        assert len(registry.get_assets_for_game("g1")) == 2

    def test_duplicate_updates_checksum(self, registry):
        """Given same (game_id, file_path) — When re-registering — Then updates in place."""
        id1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "old")
        id2 = registry.register_asset("g1", "skeleton", "a.skel", "4.2", "new")
        assert id1 == id2
        assets = registry.get_assets_for_game("g1")
        assert len(assets) == 1
        assert assets[0]["checksum"] == "new"
        assert assets[0]["spine_version"] == "4.2"

    def test_different_games_independent(self, populated):
        """Given assets in separate games — When querying each — Then isolated."""
        assert len(populated.get_assets_for_game("mg-game-0001")) == 2
        assert len(populated.get_assets_for_game("mg-game-0002")) == 1

    def test_created_at_populated(self, registry):
        """Given registration — When querying — Then created_at is non-empty ISO string."""
        registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        asset = registry.get_assets_for_game("g1")[0]
        assert "created_at" in asset
        assert len(asset["created_at"]) > 0


# ---------------------------------------------------------------------------
# get_assets_for_game
# ---------------------------------------------------------------------------
class TestGetAssetsForGame:
    def test_returns_matching(self, populated):
        """Given assets for mg-game-0001 — When querying — Then correct types returned."""
        assets = populated.get_assets_for_game("mg-game-0001")
        types = {a["asset_type"] for a in assets}
        assert types == {"skeleton", "atlas"}

    def test_empty_for_unknown(self, populated):
        """Given unknown game_id — When querying — Then empty list."""
        assert populated.get_assets_for_game("mg-game-9999") == []

    def test_no_cross_contamination(self, populated):
        """Given two games — When querying one — Then only its assets appear."""
        assets = populated.get_assets_for_game("mg-game-0002")
        assert len(assets) == 1
        assert assets[0]["file_path"] == "villain/villain.skel"

    def test_result_is_list_of_dicts(self, populated):
        """Given populated DB — When querying — Then result is List[dict]."""
        assets = populated.get_assets_for_game("mg-game-0001")
        assert isinstance(assets, list)
        for a in assets:
            assert isinstance(a, dict)


# ---------------------------------------------------------------------------
# mark_deployed
# ---------------------------------------------------------------------------
class TestMarkDeployed:
    def test_creates_deployment_record(self, registry):
        """Given a registered asset — When marking deployed — Then deployment counted."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.mark_deployed(aid, "g1")
        status = registry.get_deployment_status("g1")
        assert status["deployed"] == 1

    def test_nonexistent_asset_raises(self, registry):
        """Given no asset with id 9999 — When marking deployed — Then ValueError."""
        with pytest.raises(ValueError):
            registry.mark_deployed(9999, "g1")

    def test_deploy_to_multiple_games(self, registry):
        """Given asset deployed to two games — When checking status — Then counted."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.mark_deployed(aid, "g1")
        registry.mark_deployed(aid, "g2")
        status = registry.get_deployment_status("g1")
        assert status["deployed"] >= 1

    def test_deploy_same_game_twice(self, registry):
        """Given duplicate deploy calls — When checking status — Then asset still counted once."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.mark_deployed(aid, "g1")
        registry.mark_deployed(aid, "g1")
        status = registry.get_deployment_status("g1")
        assert status["deployed"] == 1


# ---------------------------------------------------------------------------
# get_deployment_status
# ---------------------------------------------------------------------------
class TestGetDeploymentStatus:
    def test_no_assets_returns_zeroes(self, registry):
        """Given unknown game — When getting status — Then all-zero dict."""
        status = registry.get_deployment_status("mg-game-9999")
        assert status["total"] == 0
        assert status["deployed"] == 0
        assert status["pending"] == 0

    def test_all_deployed(self, registry):
        """Given all assets deployed — When getting status — Then pending == 0."""
        a1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        a2 = registry.register_asset("g1", "atlas", "a.atlas", "4.1", "h2")
        registry.mark_deployed(a1, "g1")
        registry.mark_deployed(a2, "g1")
        status = registry.get_deployment_status("g1")
        assert status["total"] == 2
        assert status["deployed"] == 2
        assert status["pending"] == 0

    def test_partial_deployed(self, registry):
        """Given 1 of 2 deployed — When getting status — Then pending == 1."""
        a1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.register_asset("g1", "atlas", "a.atlas", "4.1", "h2")
        registry.mark_deployed(a1, "g1")
        status = registry.get_deployment_status("g1")
        assert status["total"] == 2
        assert status["deployed"] == 1
        assert status["pending"] == 1

    def test_deployment_rate(self, registry):
        """Given 1 of 2 deployed — When getting rate — Then 0.5."""
        a1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.register_asset("g1", "atlas", "a.atlas", "4.1", "h2")
        registry.mark_deployed(a1, "g1")
        status = registry.get_deployment_status("g1")
        assert status["deployment_rate"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# list_undeployed
# ---------------------------------------------------------------------------
class TestListUndeployed:
    def test_empty_db(self, registry):
        """Given empty DB — When listing undeployed — Then empty list."""
        assert registry.list_undeployed() == []

    def test_all_undeployed(self, registry):
        """Given assets with no deployments — When listing — Then all returned."""
        registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.register_asset("g2", "skeleton", "b.skel", "4.1", "h2")
        undeployed = registry.list_undeployed()
        assert len(undeployed) == 2

    def test_mix_deployed_undeployed(self, registry):
        """Given one deployed, one not — When listing — Then only undeployed returned."""
        a1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.register_asset("g1", "atlas", "a.atlas", "4.1", "h2")
        registry.mark_deployed(a1, "g1")
        undeployed = registry.list_undeployed()
        assert len(undeployed) == 1
        assert undeployed[0]["file_path"] == "a.atlas"

    def test_deployed_not_included(self, registry):
        """Given all deployed — When listing — Then empty."""
        a1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.mark_deployed(a1, "g1")
        assert registry.list_undeployed() == []


# ---------------------------------------------------------------------------
# update_quality_gate
# ---------------------------------------------------------------------------
class TestUpdateQualityGate:
    def test_stores_pass_level(self, registry):
        """Given asset — When updating quality to pass/0.95 — Then reflected in query."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.update_quality_gate(aid, "pass", 0.95)
        asset = registry.get_assets_for_game("g1")[0]
        assert asset["quality_level"] == "pass"
        assert asset["quality_score"] == pytest.approx(0.95)

    def test_stores_warn_level(self, registry):
        """Given asset — When updating quality to warn — Then level is 'warn'."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.update_quality_gate(aid, "warn", 0.6)
        assert registry.get_assets_for_game("g1")[0]["quality_level"] == "warn"

    def test_stores_fail_level(self, registry):
        """Given asset — When updating quality to fail — Then level is 'fail'."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.update_quality_gate(aid, "fail", 0.2)
        assert registry.get_assets_for_game("g1")[0]["quality_level"] == "fail"

    def test_invalid_level_raises(self, registry):
        """Given invalid level string — When updating — Then ValueError."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        with pytest.raises(ValueError):
            registry.update_quality_gate(aid, "invalid", 0.5)

    def test_score_above_one_raises(self, registry):
        """Given score > 1.0 — When updating — Then ValueError."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        with pytest.raises(ValueError):
            registry.update_quality_gate(aid, "pass", 1.5)

    def test_negative_score_raises(self, registry):
        """Given score < 0.0 — When updating — Then ValueError."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        with pytest.raises(ValueError):
            registry.update_quality_gate(aid, "pass", -0.1)

    def test_nonexistent_asset_raises(self, registry):
        """Given missing asset id — When updating quality — Then ValueError."""
        with pytest.raises(ValueError):
            registry.update_quality_gate(9999, "pass", 0.9)

    def test_overwrites_previous(self, registry):
        """Given quality already set — When updating again — Then latest wins."""
        aid = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.update_quality_gate(aid, "fail", 0.2)
        registry.update_quality_gate(aid, "pass", 0.95)
        asset = registry.get_assets_for_game("g1")[0]
        assert asset["quality_level"] == "pass"
        assert asset["quality_score"] == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------
class TestGetStats:
    def test_empty_db(self, registry):
        """Given empty DB — When getting stats — Then zeroes."""
        stats = registry.get_stats()
        assert stats["total_assets"] == 0
        assert stats["deployment_rate"] == 0.0

    def test_total_assets(self, populated):
        """Given 3 assets — When getting stats — Then total_assets == 3."""
        stats = populated.get_stats()
        assert stats["total_assets"] == 3

    def test_deployment_rate(self, registry):
        """Given 1 of 2 deployed — When getting stats — Then rate == 0.5."""
        a1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.register_asset("g1", "atlas", "a.atlas", "4.1", "h2")
        registry.mark_deployed(a1, "g1")
        stats = registry.get_stats()
        assert stats["deployment_rate"] == pytest.approx(0.5)

    def test_game_summary(self, populated):
        """Given assets in two games — When getting stats — Then by_game has both."""
        stats = populated.get_stats()
        assert "by_game" in stats
        assert "mg-game-0001" in stats["by_game"]
        assert stats["by_game"]["mg-game-0001"]["total"] == 2
        assert "mg-game-0002" in stats["by_game"]
        assert stats["by_game"]["mg-game-0002"]["total"] == 1

    def test_game_summary_deployed_count(self, registry):
        """Given partial deployment — When getting stats — Then by_game reflects it."""
        a1 = registry.register_asset("g1", "skeleton", "a.skel", "4.1", "h1")
        registry.register_asset("g1", "atlas", "a.atlas", "4.1", "h2")
        registry.mark_deployed(a1, "g1")
        stats = registry.get_stats()
        assert stats["by_game"]["g1"]["deployed"] == 1
        assert stats["by_game"]["g1"]["total"] == 2
