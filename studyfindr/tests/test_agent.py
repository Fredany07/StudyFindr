"""
Tests for StudyFindr's planning loop in agent.py.

LLM-backed tools are mocked here so the planning loop's branching logic
(fallback retries, partner/flashcard skip behavior, error propagation)
can be tested deterministically without a live GROQ_API_KEY.
"""
import sys
import os
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import run_agent


def test_no_results_stops_before_downstream_tools():
    """If search_resources finds nothing even after fallback retries,
    the agent must not call generate_study_plan or create_recap_card."""
    with patch("agent.generate_study_plan") as mock_plan, \
         patch("agent.create_recap_card") as mock_recap:
        result = run_agent(topic="underwater basket weaving")
        assert result["error"] is not None
        assert result["study_plan"] is None
        assert result["recap_card"] is None
        mock_plan.assert_not_called()
        mock_recap.assert_not_called()


def test_difficulty_fallback_retry_triggers():
    """'system design' only exists at 'advanced' difficulty -- requesting
    max_difficulty='beginner' should trigger the fallback retry note and
    still find the resource."""
    with patch("agent.generate_flashcards", return_value=[]), \
         patch("agent.generate_study_plan", return_value="Mock plan."), \
         patch("agent.create_recap_card", return_value="Mock recap."):
        result = run_agent(topic="system design", max_difficulty="beginner")
        assert any("Retrying without the difficulty filter" in n for n in result["notes"])
        assert result["selected_resource"] is not None
        assert result["selected_resource"]["title"] == "System Design Fundamentals"


def test_partner_not_requested_is_skipped():
    """If want_partner=False, find_study_partners must not be called at all --
    this is the core proof that the agent doesn't run a fixed sequence."""
    with patch("agent.find_study_partners") as mock_partners, \
         patch("agent.generate_study_plan", return_value="Mock plan."), \
         patch("agent.create_recap_card", return_value="Mock recap."):
        result = run_agent(topic="dynamic programming", want_partner=False)
        mock_partners.assert_not_called()
        assert result["partner_match"] is None


def test_partner_requested_but_no_match_continues_gracefully():
    """An empty partner match list must not be treated as an error --
    the agent should add a note and continue to the study plan step."""
    with patch("agent.find_study_partners", return_value=[]), \
         patch("agent.generate_study_plan", return_value="Mock plan.") as mock_plan, \
         patch("agent.create_recap_card", return_value="Mock recap."):
        result = run_agent(topic="dynamic programming", want_partner=True)
        assert result["partner_match"] is None
        assert result["error"] is None
        assert any("No study partner match found" in n for n in result["notes"])
        mock_plan.assert_called_once()


def test_state_flows_between_tool_calls():
    """The resource selected in step 1 must be the exact object passed into
    generate_study_plan and create_recap_card."""
    with patch("agent.generate_study_plan", return_value="Mock plan.") as mock_plan, \
         patch("agent.create_recap_card", return_value="Mock recap.") as mock_recap:
        result = run_agent(topic="dynamic programming")
        selected = result["selected_resource"]

        _, plan_kwargs = mock_plan.call_args
        assert plan_kwargs["resource"] is selected

        recap_args, _ = mock_recap.call_args
        assert recap_args[1] is selected


def test_failed_study_plan_stops_before_recap_card():
    """If generate_study_plan returns an error string, create_recap_card
    must not be called."""
    with patch("agent.generate_study_plan", return_value="Error: LLM unavailable."), \
         patch("agent.create_recap_card") as mock_recap:
        result = run_agent(topic="dynamic programming")
        assert result["error"] == "Error: LLM unavailable."
        mock_recap.assert_not_called()
