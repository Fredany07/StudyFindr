"""
StudyFindr agent: the planning loop that orchestrates the 5 tools.

The agent does NOT call all tools unconditionally in a fixed sequence.
It branches based on what each tool returns and what the user asked for,
and stores state in a session dict that flows between tool calls.
"""
from tools import (
    search_resources,
    find_study_partners,
    generate_flashcards,
    generate_study_plan,
    create_recap_card,
)


def run_agent(
    topic,
    resource_type=None,
    max_difficulty=None,
    want_partner=False,
    partner_availability=None,
    partner_level=None,
    want_flashcards=False,
    num_flashcards=5,
    existing_knowledge=None,
):
    """Runs the full StudyFindr planning loop for a single query.

    Args:
        topic (str): the study topic, e.g. "dynamic programming". Required.
        resource_type (str | None): filter for search_resources.
        max_difficulty (str | None): filter for search_resources.
        want_partner (bool): whether to attempt to find a study partner.
        partner_availability (str | None): availability filter for partner search.
        partner_level (str | None): level filter for partner search.
        want_flashcards (bool): whether to generate flashcards.
        num_flashcards (int): how many flashcards to request.
        existing_knowledge (dict | None): the student's knowledge profile.

    Returns:
        dict: the session state with keys:
            topic, resources, selected_resource, partner_match,
            flashcards, study_plan, recap_card, error, notes (list[str]
            of human-readable notes about fallback/branching decisions
            the agent made, useful for demoing the planning loop).
    """
    session = {
        "topic": topic,
        "resources": [],
        "selected_resource": None,
        "partner_match": None,
        "flashcards": [],
        "study_plan": None,
        "recap_card": None,
        "error": None,
        "notes": [],
    }

    # Step 1: search for resources. This is the one tool call that is
    # never skipped -- everything downstream depends on having a resource.
    results = search_resources(topic, resource_type=resource_type, max_difficulty=max_difficulty)

    if not results and max_difficulty is not None:
        # Fallback: retry with the difficulty filter loosened before giving up.
        session["notes"].append(
            f"No resources found at or below '{max_difficulty}' difficulty. Retrying without the difficulty filter."
        )
        results = search_resources(topic, resource_type=resource_type, max_difficulty=None)

    if not results and resource_type is not None:
        session["notes"].append(
            f"Still no matches for type '{resource_type}'. Retrying without the type filter."
        )
        results = search_resources(topic, resource_type=None, max_difficulty=None)

    session["resources"] = results

    if not results:
        session["error"] = (
            f"No study resources found for '{topic}'. Try a broader topic "
            f"(e.g. 'graphs' instead of 'Dijkstra's shortest path edge cases'), "
            f"or check the spelling."
        )
        return session  # Stop here -- nothing downstream can run without a resource.

    session["selected_resource"] = results[0]

    # Step 2: optionally find a study partner. This branch only runs if
    # the user asked for one -- it is not part of the fixed sequence.
    if want_partner:
        partner_matches = find_study_partners(
            topic, availability=partner_availability, current_level=partner_level
        )
        if partner_matches:
            session["partner_match"] = partner_matches[0]
            session["notes"].append(f"Matched with study partner: {partner_matches[0]['name']}.")
        else:
            session["notes"].append(
                "No study partner match found -- continuing with a solo study plan."
            )
            # No error here: an empty partner match is a normal outcome,
            # not a failure. The agent adapts and continues.

    # Step 3: optionally generate flashcards, grounded in the selected resource.
    if want_flashcards:
        cards = generate_flashcards(topic, resource=session["selected_resource"], num_cards=num_flashcards)
        if cards:
            session["flashcards"] = cards
        else:
            session["notes"].append(
                "Flashcard generation returned no usable cards -- continuing without them."
            )

    # Step 4: generate the study plan using whatever context exists so far.
    plan = generate_study_plan(
        resource=session["selected_resource"],
        partner_match=session["partner_match"],
        flashcards=session["flashcards"],
        existing_knowledge=existing_knowledge,
    )
    session["study_plan"] = plan

    if plan.startswith("Error:"):
        session["error"] = plan
        return session  # Stop here -- can't make a recap card from a failed plan.

    # Step 5: generate the shareable recap card.
    recap = create_recap_card(plan, session["selected_resource"])
    session["recap_card"] = recap
    if recap.startswith("Error:"):
        session["error"] = recap

    return session


if __name__ == "__main__":
    # Quick manual smoke test: a happy path and a guaranteed-empty path.
    print("=== Happy path ===")
    result = run_agent(
        topic="dynamic programming",
        max_difficulty="intermediate",
        want_partner=True,
        partner_availability="evenings",
        want_flashcards=True,
        existing_knowledge={
            "known_topics": ["recursion", "arrays"],
            "weak_topics": ["dynamic programming"],
            "goal": "coding interview prep",
            "days_until_goal": 14,
        },
    )
    for k, v in result.items():
        print(f"--- {k} ---")
        print(v)
        print()

    print("\n=== No-results path ===")
    result2 = run_agent(topic="underwater basket weaving")
    print("error:", result2["error"])
    print("study_plan:", result2["study_plan"])
