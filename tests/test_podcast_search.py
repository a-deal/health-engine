"""Tests for search_podcasts MCP tool."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def podcast_dir(tmp_path):
    """Create sample transcript and summary files."""
    transcripts = tmp_path / "transcripts"
    summaries = tmp_path / "summaries"
    transcripts.mkdir()
    summaries.mkdir()

    # Transcript 1: Local First FM
    (transcripts / "abc123.txt").write_text(
        "Welcome to Local First FM.\n"
        "Today we're talking about CRDTs and sync engines.\n"
        "The key insight is that conflict-free replicated data types\n"
        "allow multiple users to edit simultaneously without coordination.\n"
        "This is fundamental to offline-first architecture.\n"
        "You don't need a server to resolve conflicts.\n"
        "The data structure itself guarantees convergence.\n"
        "That's what makes local-first different from traditional client-server.\n"
    )
    (summaries / "abc123.md").write_text(
        "---\n"
        "video_id: abc123\n"
        'title: "CRDTs and Sync Engines"\n'
        'channel: "Local First FM"\n'
        'date: "2026-03-15"\n'
        "words: 500\n"
        "---\n\n"
        "TL;DR CRDTs enable offline-first sync without servers.\n"
    )

    # Transcript 2: All-In Podcast
    (transcripts / "def456.txt").write_text(
        "Let's talk about AI pricing strategy.\n"
        "The SaaS model is breaking down because AI can replace entire products.\n"
        "Anthropic just announced something that tanked legal tech stocks.\n"
        "The question is whether subscription pricing survives\n"
        "when a foundation model can do 80% of what a vertical SaaS does.\n"
        "I think usage-based pricing is the answer.\n"
        "You charge for outcomes, not seats.\n"
    )
    (summaries / "def456.md").write_text(
        "---\n"
        "video_id: def456\n"
        'title: "AI Pricing and SaaS Disruption"\n'
        'channel: "All-In Podcast"\n'
        'date: "2026-03-20"\n'
        "words: 400\n"
        "---\n\n"
        "TL;DR AI is disrupting SaaS pricing models.\n"
    )

    # Transcript 3: Invest Like The Best
    (transcripts / "ghi789.txt").write_text(
        "Today we're discussing owner-operator models.\n"
        "The best businesses are run by people who have skin in the game.\n"
        "3G Capital deploys mostly house capital.\n"
        "Their edge is patience and meritocratic talent development.\n"
        "When you align incentives through ownership, behavior changes.\n"
        "That's the coaching insight too. Ownership drives adherence.\n"
    )
    (summaries / "ghi789.md").write_text(
        "---\n"
        "video_id: ghi789\n"
        'title: "Owner-Operator Models"\n'
        'channel: "Invest Like The Best"\n'
        'date: "2026-03-25"\n'
        "words: 350\n"
        "---\n\n"
        "TL;DR Owner-operators with aligned incentives build the best businesses.\n"
    )

    return tmp_path


class TestSearchPodcasts:
    def test_finds_matching_transcripts(self, podcast_dir):
        from mcp_server.tools import _search_podcasts
        results = _search_podcasts("CRDTs", podcast_dir=str(podcast_dir))
        assert len(results) >= 1
        assert results[0]["title"] == "CRDTs and Sync Engines"
        assert results[0]["channel"] == "Local First FM"
        assert "conflict-free replicated data types" in results[0]["context"]

    def test_returns_empty_for_no_match(self, podcast_dir):
        from mcp_server.tools import _search_podcasts
        results = _search_podcasts("quantum computing", podcast_dir=str(podcast_dir))
        assert results == []

    def test_limit_caps_results(self, podcast_dir):
        from mcp_server.tools import _search_podcasts
        results = _search_podcasts("the", limit=1, podcast_dir=str(podcast_dir))
        assert len(results) == 1

    def test_case_insensitive(self, podcast_dir):
        from mcp_server.tools import _search_podcasts
        results = _search_podcasts("crdts", podcast_dir=str(podcast_dir))
        assert len(results) >= 1

    def test_includes_context_lines(self, podcast_dir):
        from mcp_server.tools import _search_podcasts
        results = _search_podcasts("pricing strategy", podcast_dir=str(podcast_dir))
        assert len(results) >= 1
        # Context should include surrounding lines
        assert "subscription pricing" in results[0]["context"]

    def test_searches_across_channels(self, podcast_dir):
        from mcp_server.tools import _search_podcasts
        results = _search_podcasts("ownership", podcast_dir=str(podcast_dir))
        assert len(results) >= 1
        assert results[0]["channel"] == "Invest Like The Best"
