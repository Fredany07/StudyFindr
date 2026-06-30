"""
StudyFindr tools.

Each tool has a clearly defined interface: explicit input parameters and
a predictable return shape, even on failure. Tools that call the LLM use
Groq's llama-3.3-70b-versatile model.
"""
import os
import random
from groq import Groq
from dotenv import load_dotenv
from utils.data_loader import load_resources, load_partners

load_dotenv()

_client = None


def _get_client():
    """Lazily creates the Groq client so tests can import this module
    without requiring a valid API key to be present."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


def _call_llm(prompt, temperature=0.9, max_tokens=300):
    """Shared helper for calling the Groq LLM. Returns the text response,
    or raises an exception that calling tools are expected to catch."""
    response = _get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Tool 1: search_resources
# ---------------------------------------------------------------------------
def search_resources(topic, resource_type=None, max_difficulty=None):
    """Searches the mock resource dataset for study materials matching a topic.

    Args:
        topic (str): the subject to search for, e.g. "dynamic programming".
            Matched against the resource's topic, title, and tags
            (case-insensitive substring match).
        resource_type (str | None): one of "article", "video", "practice_set",
            or None to match any type.
        max_difficulty (str | None): one of "beginner", "intermediate",
            "advanced", or None to match any difficulty. Resources at or
            below this difficulty level are included (beginner < intermediate
            < advanced).

    Returns:
        list[dict]: matching resources, sorted by difficulty (easiest first).
            Each dict has keys: id, title, type, topic, tags, difficulty,
            platform, duration_minutes, description.
            Returns [] if no resources match. Never raises an exception
            for "no results" -- only for malformed input.
    """
    if not topic or not isinstance(topic, str):
        return []

    difficulty_rank = {"beginner": 0, "intermediate": 1, "advanced": 2}
    topic_lower = topic.lower()
    max_rank = difficulty_rank.get(max_difficulty) if max_difficulty else None

    resources = load_resources()
    matches = []
    for r in resources:
        topic_match = (
            topic_lower in r["topic"].lower()
            or topic_lower in r["title"].lower()
            or any(topic_lower in tag.lower() for tag in r["tags"])
        )
        if not topic_match:
            continue
        if resource_type and r["type"] != resource_type:
            continue
        if max_rank is not None and difficulty_rank.get(r["difficulty"], 99) > max_rank:
            continue
        matches.append(r)

    matches.sort(key=lambda r: difficulty_rank.get(r["difficulty"], 99))
    return matches


# ---------------------------------------------------------------------------
# Tool 2: find_study_partners
# ---------------------------------------------------------------------------
def find_study_partners(topic, availability=None, current_level=None):
    """Matches the user against a mock pool of other students studying
    similar topics.

    Args:
        topic (str): the subject to find partners for, e.g. "graphs".
            Matched against each partner's topics list (case-insensitive
            substring match).
        availability (str | None): one of "mornings", "evenings", "weekends",
            or None to ignore availability when matching.
        current_level (str | None): one of "beginner", "intermediate",
            "advanced", or None to ignore level when matching. Partners
            within one level of the given level are included.

    Returns:
        list[dict]: matching partners, each with keys: id, name, topics,
            level, availability, timezone, bio. Returns [] if no partners
            match -- this is a normal, expected outcome, not an error.
    """
    if not topic or not isinstance(topic, str):
        return []

    level_rank = {"beginner": 0, "intermediate": 1, "advanced": 2}
    topic_lower = topic.lower()
    target_rank = level_rank.get(current_level) if current_level else None

    partners = load_partners()
    matches = []
    for p in partners:
        topic_match = any(topic_lower in t.lower() for t in p["topics"])
        if not topic_match:
            continue
        if availability and availability not in p["availability"]:
            continue
        if target_rank is not None:
            partner_rank = level_rank.get(p["level"], 99)
            if abs(partner_rank - target_rank) > 1:
                continue
        matches.append(p)

    return matches


# ---------------------------------------------------------------------------
# Tool 3: generate_flashcards
# ---------------------------------------------------------------------------
def generate_flashcards(topic, resource=None, num_cards=5):
    """Generates flashcard-style question/answer pairs for a topic, optionally
    grounded in a specific resource.

    Args:
        topic (str): the subject to generate flashcards for. Required --
            this tool cannot run without a topic.
        resource (dict | None): a resource dict (as returned by
            search_resources) to ground the flashcards in. If None,
            flashcards are generated from general knowledge of the topic.
        num_cards (int): how many flashcards to generate. Defaults to 5.

    Returns:
        list[dict]: each dict has keys "question" (str) and "answer" (str).
            Returns [] if topic is empty/missing. Returns [] (not an
            exception) if the LLM call fails, so the caller can detect
            and handle the failure.
    """
    if not topic or not isinstance(topic, str):
        return []

    context = ""
    if resource:
        context = f' Base the questions specifically on this resource: "{resource["title"]}" -- {resource["description"]}'

    prompt = (
        f"Generate exactly {num_cards} flashcard question-and-answer pairs "
        f"for a computer science student studying '{topic}'.{context} "
        f"Questions should test understanding of core concepts, not just trivia. "
        f"Respond ONLY with a JSON array, no preamble, no markdown fences. "
        f'Format: [{{"question": "...", "answer": "..."}}, ...]'
    )

    try:
        raw = _call_llm(prompt, temperature=0.7, max_tokens=800)
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        import json
        cards = json.loads(cleaned)
        if not isinstance(cards, list):
            return []
        valid_cards = [
            c for c in cards
            if isinstance(c, dict) and "question" in c and "answer" in c
        ]
        return valid_cards[:num_cards]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Tool 4: generate_study_plan
# ---------------------------------------------------------------------------
def generate_study_plan(resource, partner_match=None, flashcards=None, existing_knowledge=None):
    """Builds a concrete study plan using whatever context is available.

    Args:
        resource (dict): the primary resource to build the plan around, as
            returned by search_resources. Required -- without a resource
            there is nothing to plan around.
        partner_match (dict | None): a partner dict from find_study_partners,
            or None if studying solo. The plan's tone/structure adapts
            based on whether this is present.
        flashcards (list[dict] | None): flashcards from generate_flashcards,
            or None/[] if none were generated.
        existing_knowledge (dict | None): a knowledge profile dict (see
            data/knowledge_schema.json) describing what the student already
            knows. If None, an empty profile is assumed.

    Returns:
        str: a multi-paragraph study plan as plain text. Returns a
            descriptive error string (not an exception) if resource is
            missing or malformed.
    """
    if not resource or not isinstance(resource, dict):
        return "Error: no resource was provided to build a study plan around."

    knowledge = existing_knowledge or {}
    known = knowledge.get("known_topics", [])
    weak = knowledge.get("weak_topics", [])
    goal = knowledge.get("goal", "general study")
    days = knowledge.get("days_until_goal", 0)

    partner_clause = ""
    if partner_match:
        partner_clause = (
            f" The student will be studying with a partner named {partner_match['name']} "
            f"({partner_match['level']} level, available {', '.join(partner_match['availability'])}). "
            f"Suggest how to split or collaborate on the work."
        )
    else:
        partner_clause = " The student is studying solo."

    flashcard_clause = ""
    if flashcards:
        flashcard_clause = f" {len(flashcards)} flashcards have already been generated and should be incorporated as a review step."

    timeline_clause = f" The student has {days} days until their goal: {goal}." if days else f" The student's goal is: {goal}."

    prompt = (
        f"Create a short, concrete study plan for a student using this resource: "
        f'"{resource["title"]}" ({resource["type"]}, {resource["difficulty"]} difficulty) -- '
        f'{resource["description"]} '
        f"The student already knows: {', '.join(known) if known else 'nothing listed'}. "
        f"They struggle with: {', '.join(weak) if weak else 'nothing listed'}."
        f"{timeline_clause}{partner_clause}{flashcard_clause} "
        f"Write 2-3 short paragraphs giving a concrete, actionable plan -- "
        f"not generic advice. Reference the specific resource and topic."
    )

    try:
        return _call_llm(prompt, temperature=0.7, max_tokens=400)
    except Exception as e:
        return f"Error: could not generate a study plan right now ({str(e)}). Try again in a moment."


# ---------------------------------------------------------------------------
# Tool 5: create_recap_card
# ---------------------------------------------------------------------------
def create_recap_card(study_plan, resource):
    """Generates a short, shareable recap of a study plan -- the kind of
    thing someone would post in a study-tracking log or "study vlog" caption.

    Args:
        study_plan (str): the plan text from generate_study_plan. Must be
            non-empty.
        resource (dict): the resource the plan was built around, as
            returned by search_resources.

    Returns:
        str: a short (1-3 sentence) shareable recap, different each time
            for different inputs. Returns a descriptive error string
            (not an exception) if study_plan is empty or resource is missing.
    """
    if not study_plan or not isinstance(study_plan, str) or not study_plan.strip():
        return "Error: can't create a recap card without a completed study plan."
    if not resource or not isinstance(resource, dict):
        return "Error: can't create a recap card without knowing which resource the plan was based on."

    prompt = (
        f"Write a short, casual 1-3 sentence recap caption a student might post "
        f'in a study-tracking app or "study vlog" after working through this plan:\n\n'
        f"{study_plan}\n\n"
        f'The resource used was "{resource["title"]}" ({resource["topic"]}). '
        f"Make it sound genuine and specific, not like a product description. "
        f"Light emoji use is fine but don't overdo it. Output only the caption text."
    )

    try:
        return _call_llm(prompt, temperature=1.0, max_tokens=120)
    except Exception as e:
        return f"Error: could not generate a recap card right now ({str(e)}). Try again in a moment."
