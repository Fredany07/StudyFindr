# StudyFindr — Planning

## Overview

StudyFindr is a multi-tool AI agent for CS students prepping for technical interviews
(or exams). A student describes what they're studying, and the agent searches for a
matching resource, optionally finds a compatible study partner, optionally generates
flashcards, then builds a study plan and a shareable recap card -- adapting its
behavior at each step based on what's actually available rather than running every
tool unconditionally.

## A Complete Interaction

A student says: "I'm studying dynamic programming for interviews, I know recursion
and arrays already but DP itself is still shaky. I have two weeks. I'd like a study
partner if there's a match, and some flashcards to review."

What triggers each tool: `search_resources` always runs first, since nothing
downstream can happen without a resource. `find_study_partners` only runs because
the student explicitly asked for a partner -- if they hadn't, this tool would be
skipped entirely. `generate_flashcards` only runs because the student asked for
flashcards. `generate_study_plan` always runs (assuming a resource was found),
since it's the core deliverable. `create_recap_card` only runs if the study plan
generated successfully.

What happens when something fails: if `search_resources` finds nothing, the agent
retries with progressively loosened filters (first dropping difficulty, then
dropping resource type) before giving up and telling the student to try a broader
topic. If `find_study_partners` returns no match, that is *not* treated as an
error -- the agent notes it and continues with a solo study plan. If
`generate_study_plan` fails (e.g. the LLM call errors), the agent stops and does
not attempt to create a recap card from a plan that doesn't exist.

## Tool 1: search_resources

- **What it does:** Searches the mock resource dataset (`data/resources.json`) for
  study materials matching a topic, optionally filtered by type and difficulty.
- **Inputs:**
  - `topic` (str, required): subject to search for, e.g. `"dynamic programming"`.
    Matched case-insensitively as a substring against the resource's topic, title,
    and tags.
  - `resource_type` (str | None): one of `"article"`, `"video"`, `"practice_set"`,
    or `None` to match any type.
  - `max_difficulty` (str | None): one of `"beginner"`, `"intermediate"`,
    `"advanced"`, or `None`. Resources at or below this difficulty are included.
- **Returns:** `list[dict]` of matching resources, sorted easiest-first. Each dict
  has `id`, `title`, `type`, `topic`, `tags`, `difficulty`, `platform`,
  `duration_minutes`, `description`. Returns `[]` (not an exception) when nothing
  matches.
- **Failure mode:** Empty list is the expected "no match" outcome, not an
  exception. The agent's job is to decide what to do about an empty list (retry
  with loosened filters, then give up with a specific suggestion).

## Tool 2: find_study_partners

- **What it does:** Matches the student against a mock pool of other students
  (`data/partners.json`) studying similar topics.
- **Inputs:**
  - `topic` (str, required): subject to match on, e.g. `"graphs"`.
  - `availability` (str | None): one of `"mornings"`, `"evenings"`, `"weekends"`,
    or `None` to ignore availability.
  - `current_level` (str | None): one of `"beginner"`, `"intermediate"`,
    `"advanced"`, or `None`. Partners within one level are included.
- **Returns:** `list[dict]` of matching partners, each with `id`, `name`, `topics`,
  `level`, `availability`, `timezone`, `bio`. Returns `[]` if no partners match.
- **Failure mode:** An empty list is a normal, expected outcome (not every topic
  has a matching partner in the mock pool). The agent does not treat this as an
  error -- it notes the miss and proceeds with a solo study plan instead of
  stopping or retrying indefinitely.

## Tool 3: generate_flashcards

- **What it does:** Calls the LLM to generate question/answer flashcard pairs for
  a topic, optionally grounded in a specific resource's content.
- **Inputs:**
  - `topic` (str, required): subject for the flashcards.
  - `resource` (dict | None): a resource dict from `search_resources` to ground
    the questions in. If `None`, flashcards are generated from general knowledge.
  - `num_cards` (int): how many cards to generate (default 5).
- **Returns:** `list[dict]` of `{"question": str, "answer": str}`. Returns `[]` if
  `topic` is empty/missing, or if the LLM call fails or returns malformed JSON
  (caught and converted to an empty list rather than propagating an exception).
- **Failure mode:** The agent checks for an empty list and adds a note that
  flashcards were skipped, then continues to the study plan step without them --
  flashcards are a nice-to-have, not a blocker.

## Tool 4: generate_study_plan

- **What it does:** Calls the LLM to build a concrete, multi-paragraph study plan
  using whatever context is available: the selected resource (required), an
  optional partner match, optional flashcards, and the student's existing
  knowledge profile.
- **Inputs:**
  - `resource` (dict, required): the resource to build the plan around.
  - `partner_match` (dict | None): from `find_study_partners`, or `None` for solo.
  - `flashcards` (list[dict] | None): from `generate_flashcards`, or `None`/`[]`.
  - `existing_knowledge` (dict | None): see `data/knowledge_schema.json` --
    `known_topics`, `weak_topics`, `goal`, `days_until_goal`.
- **Returns:** `str`, a 2-3 paragraph plan. Returns an error string starting with
  `"Error:"` (not an exception) if `resource` is missing/malformed, or if the LLM
  call fails.
- **Failure mode:** The agent checks whether the returned string starts with
  `"Error:"`. If so, it stores the error and stops -- it will not attempt to
  create a recap card from a plan that doesn't exist.

## Tool 5: create_recap_card

- **What it does:** Calls the LLM to generate a short (1-3 sentence), shareable
  recap caption summarizing the study plan -- written like something a student
  would post in a study-tracking log.
- **Inputs:**
  - `study_plan` (str, required): the plan text from `generate_study_plan`. Must
    be non-empty/non-whitespace.
  - `resource` (dict, required): the resource the plan was built around.
- **Returns:** `str`, a short recap. Returns an error string starting with
  `"Error:"` if `study_plan` is empty/whitespace, `resource` is missing, or the
  LLM call fails.
- **Failure mode:** This is the last tool in the chain, so its failure just means
  the agent reports the error to the student alongside whatever else succeeded
  (the resource, partner match, flashcards, and plan are still shown).

## Planning Loop

The planning loop is implemented in `agent.py`'s `run_agent()`. Its branches, in
order:

1. **Always** call `search_resources(topic, resource_type, max_difficulty)`.
   - If `results` is empty AND `max_difficulty` was set: retry with
     `max_difficulty=None`. Add a note.
   - If still empty AND `resource_type` was set: retry with `resource_type=None`
     also. Add a note.
   - If still empty: set `session["error"]` to a specific, actionable message and
     **return immediately** -- no further tools are called.
   - Otherwise: set `session["selected_resource"] = results[0]`.

2. **Conditionally**, only if `want_partner` is `True`: call
   `find_study_partners(topic, availability, current_level)`.
   - If matches found: set `session["partner_match"] = matches[0]`. Add a note.
   - If no matches: leave `partner_match` as `None`. Add a note that the agent is
     continuing solo. **This is not an error path** -- the loop proceeds normally.
   - If `want_partner` is `False`: this tool is never called at all.

3. **Conditionally**, only if `want_flashcards` is `True`: call
   `generate_flashcards(topic, resource=selected_resource, num_cards)`.
   - If cards returned: set `session["flashcards"] = cards`.
   - If empty: leave `flashcards` as `[]`. Add a note. Proceed regardless.
   - If `want_flashcards` is `False`: this tool is never called at all.

4. **Always** (assuming step 1 found a resource): call
   `generate_study_plan(resource, partner_match, flashcards, existing_knowledge)`.
   - If the return value starts with `"Error:"`: set `session["error"]` and
     **return immediately** -- `create_recap_card` is not called.
   - Otherwise: set `session["study_plan"]`.

5. **Always** (assuming step 4 succeeded): call
   `create_recap_card(study_plan, selected_resource)`.
   - Set `session["recap_card"]`. If it starts with `"Error:"`, also set
     `session["error"]` so the UI surfaces it, but the rest of the session
     (resource, partner, flashcards, plan) is still returned intact.

The key property: the agent's behavior is genuinely conditional on what each tool
returns and what the student asked for. A query with `want_partner=False` and
`want_flashcards=False` calls only 3 of the 5 tools. A query where
`search_resources` succeeds on the first try skips both retry branches entirely.
This is verified directly in `tests/test_agent.py` (e.g.
`test_partner_not_requested_is_skipped` asserts `find_study_partners` is never
called when not requested).

## State Management

The `session` dict is created once at the top of `run_agent()` and threaded
through every step. Each tool's output is written into a specific key
(`selected_resource`, `partner_match`, `flashcards`, `study_plan`, `recap_card`)
immediately after that tool returns, and downstream tool calls read directly from
those keys -- e.g. `generate_study_plan` is called with
`resource=session["selected_resource"]`, the exact same dict object that
`search_resources` returned, not a re-entered or re-typed value. `tests/test_agent.py::test_state_flows_between_tool_calls`
asserts this with an identity check (`is`, not just `==`).

A `notes` list also accumulates human-readable strings describing every branching
decision the agent made (fallback retries, partner-not-found, flashcards skipped),
which is surfaced in the Gradio UI and used in the demo video to narrate what the
agent decided and why.

## Architecture

```mermaid
flowchart TD
    A[User query: topic, flags, knowledge profile] --> B[Planning Loop: run_agent]
    B --> C[search_resources]
    C -->|results empty, max_difficulty set| C2[Retry without difficulty filter]
    C2 -->|still empty, resource_type set| C3[Retry without type filter]
    C3 -->|still empty| ERR1[ERROR: no resources found -- return early]
    C -->|results found| D[Session: selected_resource = results[0]]
    C2 -->|results found| D
    C3 -->|results found| D

    D --> E{want_partner?}
    E -->|yes| F[find_study_partners]
    F -->|match found| G[Session: partner_match = match]
    F -->|no match| H[Note: continuing solo]
    E -->|no| H

    G --> I{want_flashcards?}
    H --> I
    I -->|yes| J[generate_flashcards]
    J -->|cards found| K[Session: flashcards = cards]
    J -->|empty| L[Note: skipping flashcards]
    I -->|no| L

    K --> M[generate_study_plan]
    L --> M
    M -->|returns Error string| ERR2[ERROR: store and return early]
    M -->|success| N[Session: study_plan = plan]

    N --> O[create_recap_card]
    O --> P[Session: recap_card = recap]
    P --> Q[Return full session]

    ERR1 -.-> Q
    ERR2 -.-> Q
```

## AI Tool Plan

- **Milestone: implementing `search_resources` and `find_study_partners`.** I'll
  give Claude the Tool 1 and Tool 2 spec blocks above (inputs, return value,
  failure mode) and ask it to implement both functions using `load_resources()`
  and `load_partners()` from `utils/data_loader.py`. Before running the generated
  code, I'll check that it filters on all listed parameters, handles `None`
  filters correctly, and returns `[]` rather than raising on no-match. Then I'll
  run it against 3 known queries (one with results, one guaranteed empty, one with
  a difficulty filter) and compare against the dataset by hand.

- **Milestone: implementing the LLM-backed tools (`generate_flashcards`,
  `generate_study_plan`, `create_recap_card`).** I'll give Claude each tool's spec
  block one at a time, plus the JSON-parsing requirement for flashcards. I'll
  check that each function catches LLM/parsing exceptions and converts them to
  the documented failure-mode return value (`[]` or an `"Error:"`-prefixed
  string) rather than letting an exception propagate. I'll verify by deliberately
  triggering each failure mode (empty topic, missing resource, empty plan) and
  confirming no traceback appears.

- **Milestone: implementing the planning loop in `agent.py`.** I'll share the full
  Mermaid diagram above plus the Planning Loop and State Management sections with
  Claude and ask it to implement `run_agent()`. Before running it, I'll check: does
  it skip `find_study_partners` entirely when `want_partner=False` (not just skip
  storing the result)? Does it return early on a `search_resources` failure
  without calling later tools? Does it pass the exact `selected_resource` object
  into later calls rather than re-deriving it? I verified all three with the
  mocked tests in `tests/test_agent.py` before considering the loop done.

## Error Handling Table

| Tool | Failure scenario | Agent's response | Fallback offered |
|---|---|---|---|
| `search_resources` | No resources match topic/filters | Retries with loosened filters first; if still empty, tells the student: "No study resources found for '{topic}'. Try a broader topic ... or check the spelling." | Loosened-filter retry, then a specific suggestion |
| `find_study_partners` | No partner matches | Adds a note: "No study partner match found -- continuing with a solo study plan." Does not block the rest of the flow. | Continues solo automatically |
| `generate_flashcards` | Empty topic, or LLM returns malformed/non-JSON output | Returns `[]`; agent adds a note and proceeds to the study plan without flashcards. | Plan generation continues without flashcards |
| `generate_study_plan` | Missing resource, or LLM call fails | Returns an `"Error:"`-prefixed string describing what went wrong; agent stops and surfaces the error, does not attempt a recap card. | None -- this is a hard stop since nothing downstream can use a failed plan |
| `create_recap_card` | Empty/whitespace plan, or missing resource, or LLM call fails | Returns an `"Error:"`-prefixed string; agent still returns the resource, partner, flashcards, and plan that succeeded earlier. | Partial results are still shown to the student |
