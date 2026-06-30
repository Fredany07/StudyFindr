# StudyFindr

A multi-tool AI agent that helps CS students find study resources, optionally
match with a study partner, generate flashcards, and turn all of that into a
concrete study plan and a shareable recap -- branching its behavior based on
what each tool actually returns, not running a fixed sequence every time.

## Quick start

```bash
git clone <your-fork-url>
cd studyfindr
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
source .venv/Scripts/activate      # Windows (Git Bash)

pip install -r requirements.txt

cp .env.example .env
# then edit .env and add your free Groq API key from console.groq.com

python app.py
# open the URL printed in the terminal (usually http://localhost:7860)
```

Run the tests:

```bash
pytest tests/ -v
```

Run the agent directly from the terminal (no UI) to see a full happy-path and a
no-results path printed to the console:

```bash
python agent.py
```

## Tool inventory

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `search_resources(topic: str, resource_type: str \| None, max_difficulty: str \| None)` | topic, optional type filter (`article`/`video`/`practice_set`), optional max difficulty (`beginner`/`intermediate`/`advanced`) | `list[dict]` of matching resources, sorted easiest-first; `[]` if none match | Finds study materials for a topic from the mock dataset |
| `find_study_partners(topic: str, availability: str \| None, current_level: str \| None)` | topic, optional availability (`mornings`/`evenings`/`weekends`), optional level | `list[dict]` of matching partners; `[]` if none match | Matches the student with other students studying similar topics |
| `generate_flashcards(topic: str, resource: dict \| None, num_cards: int)` | topic, optional resource to ground questions in, number of cards | `list[dict]` of `{"question", "answer"}` pairs; `[]` on empty topic or LLM failure | Generates review flashcards via the LLM |
| `generate_study_plan(resource: dict, partner_match: dict \| None, flashcards: list \| None, existing_knowledge: dict \| None)` | the selected resource (required), optional partner/flashcards/knowledge context | `str` plan, or an `"Error:"`-prefixed string | Builds a concrete plan using whatever context is available |
| `create_recap_card(study_plan: str, resource: dict)` | the generated plan, the resource it was based on | `str` short shareable caption, or an `"Error:"`-prefixed string | Produces a shareable summary of the study session |

## How the planning loop works

The loop lives in `agent.py`'s `run_agent()`. It is not a fixed sequence -- its
behavior changes based on the student's flags and what each tool returns:

1. `search_resources` always runs first. If it returns nothing, the loop retries
   with the difficulty filter dropped, then with the type filter also dropped,
   before giving up and returning a specific error message. No further tools run
   if this step ultimately fails.
2. `find_study_partners` only runs if the student set `want_partner=True`. If it's
   not requested, the function is never called at all (not just ignored --
   verified directly in `tests/test_agent.py::test_partner_not_requested_is_skipped`).
   An empty partner match is treated as a normal outcome, not an error: the loop
   logs a note and proceeds solo.
3. `generate_flashcards` only runs if `want_flashcards=True`. An empty/failed
   result is logged and the loop proceeds without flashcards.
4. `generate_study_plan` always runs (assuming step 1 succeeded), using whatever
   combination of resource/partner/flashcards/knowledge is available. If it
   returns an `"Error:"` string, the loop stops here.
5. `create_recap_card` only runs if step 4 succeeded.

This means a query with no flags set calls exactly 2 tools (`search_resources` and
`generate_study_plan`, plus `create_recap_card` if that succeeds), while a fully
loaded query calls all 5. The branch is driven by real conditionals on tool
output, not a flat call-everything pipeline.

## State management

A single `session` dict is created at the start of `run_agent()` and passed
through the whole call. Each tool's result is written into a specific key
(`selected_resource`, `partner_match`, `flashcards`, `study_plan`, `recap_card`,
`error`, `notes`) the moment that tool returns, and every later tool call reads
directly from those keys -- e.g. `generate_study_plan(resource=session["selected_resource"], ...)`
passes the literal object `search_resources` returned, with no re-entry or
re-derivation. This is checked with an identity assertion in
`tests/test_agent.py::test_state_flows_between_tool_calls`.

## Error handling

| Tool | What triggers failure | Agent's response |
|---|---|---|
| `search_resources` | No matches for topic/filters | Retries with progressively loosened filters, then returns a specific "try a broader topic" message and stops the whole loop |
| `find_study_partners` | No matching partner | Logs a note and continues with a solo plan -- not treated as an error |
| `generate_flashcards` | Empty topic, or malformed LLM/JSON output | Returns `[]`; loop logs a note and proceeds without flashcards |
| `generate_study_plan` | Missing resource, or LLM failure | Returns an `"Error:"` string; loop stops and does not attempt a recap card |
| `create_recap_card` | Empty plan, missing resource, or LLM failure | Returns an `"Error:"` string; loop still returns everything else that succeeded |

**Concrete example from testing:** searching `"system design"` with
`max_difficulty="beginner"` returns `[]` from the dataset (the only system design
resource is `advanced`). Rather than stopping there, the agent retries with
`max_difficulty=None`, finds "System Design Fundamentals," and logs the note
`"No resources found at or below 'beginner' difficulty. Retrying without the
difficulty filter."` -- this exact case is asserted in
`tests/test_agent.py::test_difficulty_fallback_retry_triggers`.

## Spec reflection

One way the spec helped: writing out the exact branching logic for each tool in
`planning.md` *before* touching `agent.py` made it obvious that "partner not
found" and "no resources found" needed fundamentally different treatment (one is
a soft note, one is a hard stop) -- that distinction would have been easy to
blur if I'd started coding first.

One way implementation diverged from the spec: the original plan had the
fallback retry for `search_resources` only loosen the difficulty filter. While
testing, I found `resource_type` + a narrow topic could also produce zero
results (e.g. `"graphs"` + `resource_type="video"` legitimately has no match in
the dataset), so I added a second retry stage that also drops the type filter
before giving up, rather than surfacing a false "nothing exists for this topic"
error when a video on the topic simply doesn't exist.

## AI usage

1. **Implementing `search_resources` and `find_study_partners`:** I gave Claude
   the Tool 1/Tool 2 spec blocks from `planning.md` and asked it to implement
   them using `load_resources()`/`load_partners()`. I reviewed the generated
   filtering logic and changed the difficulty comparison from an exact-match
   check to a "rank-based, at-or-below" check, since the spec called for
   "resources at or below this difficulty," not just exact matches.

2. **Implementing the planning loop in `agent.py`:** I gave Claude the Mermaid
   diagram and the Planning Loop + State Management sections from `planning.md`.
   The first generated version called `find_study_partners` unconditionally and
   only skipped *storing* the result when `want_partner=False` -- I caught this
   against my own spec (which required the tool call itself to be skipped) and
   had it rewritten to wrap the call in the `if want_partner:` check, which is
   what `test_partner_not_requested_is_skipped` now verifies.

## Demo video

See `demo.mp4` (or the link in the submission) for a 3-5 minute walkthrough
showing: a complete query using all 5 tools end-to-end, narration of which tool
runs at each step and why, the `selected_resource` object visibly flowing into
`generate_study_plan` and `create_recap_card`, and the triggered
`max_difficulty="beginner"` fallback for `"system design"` as the error-handling
example.
