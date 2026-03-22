"""Tests for get_skill_ladder tool."""

from mcp_server.tools import _get_skill_ladder


ALL_GOALS = [
    "sleep-better", "less-stress", "lose-weight", "build-strength",
    "more-energy", "sharper-focus", "better-mood", "eat-healthier",
]


def test_all_goals_load():
    """Every goal ID returns a valid ladder."""
    for goal_id in ALL_GOALS:
        result = _get_skill_ladder(goal_id)
        assert "error" not in result, f"{goal_id} failed: {result}"
        assert result["goal_id"] == goal_id
        assert result["total_levels"] >= 4
        assert len(result["levels"]) == result["total_levels"]


def test_level_structure():
    """Each level has required fields."""
    result = _get_skill_ladder("sleep-better")
    for level in result["levels"]:
        assert "level" in level
        assert "habit" in level
        assert "why" in level
        assert "diagnostic" in level
        assert isinstance(level["level"], int)
        assert level["diagnostic"].endswith("?") or level["diagnostic"].endswith('"')


def test_levels_are_ordered():
    """Levels are numbered sequentially starting at 1."""
    result = _get_skill_ladder("lose-weight")
    for i, level in enumerate(result["levels"]):
        assert level["level"] == i + 1


def test_invalid_goal():
    """Unknown goal returns error with available goals list."""
    result = _get_skill_ladder("fake-goal")
    assert "error" in result
    assert "available_goals" in result
    assert set(result["available_goals"]) == set(ALL_GOALS)


def test_instructions_included():
    """Response includes coaching instructions."""
    result = _get_skill_ladder("sleep-better")
    assert "instructions" in result
    assert "Arrival Principle" in result["instructions"]


def test_name_and_outcome():
    """Each goal has a human-readable name and outcome."""
    for goal_id in ALL_GOALS:
        result = _get_skill_ladder(goal_id)
        assert result["name"], f"{goal_id} missing name"
        assert result["outcome"], f"{goal_id} missing outcome"
