"""
Tests for StudyFindr's tools. The LLM-backed tools (generate_flashcards,
generate_study_plan, create_recap_card) are tested for their input-validation
and failure-mode behavior without requiring a live Groq API key, by checking
behavior on invalid input. Their happy paths are exercised in
tests/test_agent.py via mocking, and manually via agent.py's __main__ block
when a real GROQ_API_KEY is present.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import search_resources, find_study_partners, generate_flashcards, generate_study_plan, create_recap_card


# --- search_resources ---

def test_search_returns_results():
    results = search_resources("dynamic programming")
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_resources("underwater basket weaving")
    assert results == []


def test_search_difficulty_filter():
    results = search_resources("dynamic programming", max_difficulty="beginner")
    assert all(r["difficulty"] == "beginner" for r in results)


def test_search_type_filter():
    results = search_resources("graphs", resource_type="article")
    assert all(r["type"] == "article" for r in results)


def test_search_invalid_topic_does_not_crash():
    assert search_resources(None) == []
    assert search_resources("") == []


# --- find_study_partners ---

def test_partners_returns_results():
    results = find_study_partners("dynamic programming")
    assert isinstance(results, list)
    assert len(results) > 0


def test_partners_empty_results():
    results = find_study_partners("underwater basket weaving")
    assert results == []


def test_partners_availability_filter():
    results = find_study_partners("dynamic programming", availability="weekends")
    assert all("weekends" in p["availability"] for p in results)


def test_partners_invalid_topic_does_not_crash():
    assert find_study_partners(None) == []
    assert find_study_partners("") == []


# --- generate_flashcards (failure modes only, no live API call) ---

def test_flashcards_empty_topic_returns_empty_list():
    assert generate_flashcards("") == []
    assert generate_flashcards(None) == []


# --- generate_study_plan (failure modes only, no live API call) ---

def test_study_plan_missing_resource_returns_error_string():
    result = generate_study_plan(resource=None)
    assert isinstance(result, str)
    assert result.startswith("Error:")


def test_study_plan_invalid_resource_type_returns_error_string():
    result = generate_study_plan(resource="not a dict")
    assert isinstance(result, str)
    assert result.startswith("Error:")


# --- create_recap_card (failure modes only, no live API call) ---

def test_recap_card_empty_plan_returns_error_string():
    sample_resource = search_resources("dynamic programming")[0]
    result = create_recap_card("", sample_resource)
    assert isinstance(result, str)
    assert result.startswith("Error:")


def test_recap_card_missing_resource_returns_error_string():
    result = create_recap_card("Some valid plan text.", None)
    assert isinstance(result, str)
    assert result.startswith("Error:")


def test_recap_card_whitespace_only_plan_returns_error_string():
    sample_resource = search_resources("dynamic programming")[0]
    result = create_recap_card("   ", sample_resource)
    assert isinstance(result, str)
    assert result.startswith("Error:")
