"""
Helper functions for loading mock data used by StudyFindr's tools.
Tools should use these rather than re-implementing file loading.
"""
import json
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_resources():
    """Loads the full list of study resources from data/resources.json.

    Returns:
        list[dict]: each dict has keys: id, title, type, topic, tags,
            difficulty, platform, duration_minutes, description.
    """
    path = os.path.join(_DATA_DIR, "resources.json")
    with open(path, "r") as f:
        return json.load(f)


def load_partners():
    """Loads the full list of mock study partners from data/partners.json.

    Returns:
        list[dict]: each dict has keys: id, name, topics, level,
            availability, timezone, bio.
    """
    path = os.path.join(_DATA_DIR, "partners.json")
    with open(path, "r") as f:
        return json.load(f)


def get_example_knowledge():
    """Returns an example filled-in knowledge profile for testing.

    Returns:
        dict: known_topics (list[str]), weak_topics (list[str]),
            goal (str), days_until_goal (int).
    """
    return {
        "known_topics": ["recursion", "arrays", "hash tables"],
        "weak_topics": ["dynamic programming"],
        "goal": "coding interview prep",
        "days_until_goal": 14,
    }


def get_empty_knowledge():
    """Returns an empty knowledge profile, for testing the no-context path.

    Returns:
        dict: same shape as get_example_knowledge(), but with empty/zero values.
    """
    return {
        "known_topics": [],
        "weak_topics": [],
        "goal": "",
        "days_until_goal": 0,
    }
