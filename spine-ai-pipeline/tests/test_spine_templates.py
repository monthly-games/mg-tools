"""Tests for scripts/lib/spine_templates.py — get_template and template structures."""

import pytest
from lib.spine_templates import get_template


class TestGetTemplate:
    def test_humanoid_returns_dict(self):
        t = get_template("humanoid")
        assert isinstance(t, dict)

    def test_chibi_returns_dict(self):
        t = get_template("chibi")
        assert isinstance(t, dict)

    def test_monster_returns_dict(self):
        t = get_template("monster")
        assert isinstance(t, dict)

    def test_unknown_template_returns_humanoid_default(self):
        """Unknown key falls back to humanoid template."""
        t = get_template("alien")
        humanoid = get_template("humanoid")
        assert t == humanoid


class TestHumanoidTemplate:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.template = get_template("humanoid")

    def test_has_bones_key(self):
        assert "bones" in self.template

    def test_has_ik_key(self):
        assert "ik" in self.template

    def test_root_bone_exists(self):
        names = {b["name"] for b in self.template["bones"]}
        assert "root" in names

    def test_body_bone_exists(self):
        names = {b["name"] for b in self.template["bones"]}
        assert "body" in names

    def test_bone_count_at_least_8(self):
        assert len(self.template["bones"]) >= 8

    def test_all_bones_have_name(self):
        for bone in self.template["bones"]:
            assert "name" in bone

    def test_non_root_bones_have_parent(self):
        for bone in self.template["bones"]:
            if bone["name"] != "root":
                assert "parent" in bone

    def test_ik_constraints_reference_existing_bones(self):
        names = {b["name"] for b in self.template["bones"]}
        for ik in self.template["ik"]:
            for bone_name in ik["bones"]:
                assert bone_name in names

    def test_symmetric_arms(self):
        names = {b["name"] for b in self.template["bones"]}
        assert "arm_L" in names
        assert "arm_R" in names

    def test_symmetric_legs(self):
        names = {b["name"] for b in self.template["bones"]}
        # legs via thigh_L/thigh_R in humanoid
        assert "thigh_L" in names or "leg_L" in names


class TestChibiTemplate:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.template = get_template("chibi")

    def test_head_length_larger_than_humanoid(self):
        chibi_head = next(b for b in self.template["bones"] if b["name"] == "head")
        humanoid_head = next(b for b in get_template("humanoid")["bones"] if b["name"] == "head")
        assert chibi_head.get("length", 0) > humanoid_head.get("length", 0)

    def test_has_ik_constraints(self):
        assert len(self.template["ik"]) >= 2


class TestMonsterTemplate:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.template = get_template("monster")

    def test_fewer_bones_than_humanoid(self):
        humanoid = get_template("humanoid")
        assert len(self.template["bones"]) < len(humanoid["bones"])

    def test_empty_ik(self):
        assert self.template["ik"] == []

    def test_has_body_and_head(self):
        names = {b["name"] for b in self.template["bones"]}
        assert "body" in names
        assert "head" in names


class TestAllTemplates:
    @pytest.mark.parametrize("name", ["humanoid", "chibi", "monster"])
    def test_parseable_bones_list(self, name):
        t = get_template(name)
        assert isinstance(t["bones"], list)
        assert len(t["bones"]) > 0

    @pytest.mark.parametrize("name", ["humanoid", "chibi", "monster"])
    def test_ik_is_list(self, name):
        t = get_template(name)
        assert isinstance(t["ik"], list)
