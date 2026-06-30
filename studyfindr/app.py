"""
StudyFindr Gradio app. Run with: python app.py
Opens a local web UI for entering a study request and seeing each tool's
output as the agent works through the planning loop.
"""
import gradio as gr
from agent import run_agent


def format_resource(resource):
    if not resource:
        return "_No resource selected._"
    return (
        f"**{resource['title']}** ({resource['type']}, {resource['difficulty']})\n\n"
        f"Platform: {resource['platform']} • {resource['duration_minutes']} min\n\n"
        f"{resource['description']}"
    )


def format_partner(partner):
    if not partner:
        return "_No study partner matched -- continuing solo._"
    return (
        f"**{partner['name']}** ({partner['level']})\n\n"
        f"Available: {', '.join(partner['availability'])} • {partner['timezone']}\n\n"
        f"{partner['bio']}"
    )


def format_flashcards(cards):
    if not cards:
        return "_No flashcards generated._"
    lines = []
    for i, c in enumerate(cards, 1):
        lines.append(f"**Q{i}:** {c['question']}\n\n**A{i}:** {c['answer']}")
    return "\n\n---\n\n".join(lines)


def handle_query(
    topic,
    resource_type,
    max_difficulty,
    want_partner,
    partner_availability,
    partner_level,
    want_flashcards,
    num_flashcards,
    known_topics,
    weak_topics,
    goal,
    days_until_goal,
):
    """Maps form inputs to run_agent() args, then maps the session dict
    to the output panels."""
    resource_type = resource_type if resource_type != "any" else None
    max_difficulty = max_difficulty if max_difficulty != "any" else None
    partner_availability = partner_availability if partner_availability != "any" else None
    partner_level = partner_level if partner_level != "any" else None

    existing_knowledge = {
        "known_topics": [t.strip() for t in known_topics.split(",") if t.strip()],
        "weak_topics": [t.strip() for t in weak_topics.split(",") if t.strip()],
        "goal": goal,
        "days_until_goal": int(days_until_goal) if days_until_goal else 0,
    }

    session = run_agent(
        topic=topic,
        resource_type=resource_type,
        max_difficulty=max_difficulty,
        want_partner=want_partner,
        partner_availability=partner_availability,
        partner_level=partner_level,
        want_flashcards=want_flashcards,
        num_flashcards=int(num_flashcards),
        existing_knowledge=existing_knowledge,
    )

    notes_text = "\n".join(f"- {n}" for n in session["notes"]) if session["notes"] else "_No fallback branches were triggered._"
    error_text = session["error"] if session["error"] else "_No errors._"

    return (
        format_resource(session["selected_resource"]),
        format_partner(session["partner_match"]),
        format_flashcards(session["flashcards"]),
        session["study_plan"] or "_No study plan generated._",
        session["recap_card"] or "_No recap card generated._",
        notes_text,
        error_text,
    )


with gr.Blocks(title="StudyFindr") as demo:
    gr.Markdown("# 📚 StudyFindr")
    gr.Markdown(
        "Tell the agent what you're studying. It searches for a resource, "
        "optionally finds a study partner and generates flashcards, then "
        "builds a study plan and a shareable recap -- branching its behavior "
        "based on what each tool returns."
    )

    with gr.Row():
        with gr.Column(scale=1):
            topic = gr.Textbox(label="Topic", placeholder="e.g. dynamic programming")
            resource_type = gr.Dropdown(
                ["any", "article", "video", "practice_set"], value="any", label="Resource type"
            )
            max_difficulty = gr.Dropdown(
                ["any", "beginner", "intermediate", "advanced"], value="any", label="Max difficulty"
            )

            gr.Markdown("**Study partner**")
            want_partner = gr.Checkbox(label="Try to find a study partner", value=False)
            partner_availability = gr.Dropdown(
                ["any", "mornings", "evenings", "weekends"], value="any", label="Your availability"
            )
            partner_level = gr.Dropdown(
                ["any", "beginner", "intermediate", "advanced"], value="any", label="Your level"
            )

            gr.Markdown("**Flashcards**")
            want_flashcards = gr.Checkbox(label="Generate flashcards", value=False)
            num_flashcards = gr.Slider(1, 10, value=5, step=1, label="Number of flashcards")

            gr.Markdown("**What you already know**")
            known_topics = gr.Textbox(label="Known topics (comma-separated)", placeholder="recursion, arrays")
            weak_topics = gr.Textbox(label="Weak topics (comma-separated)", placeholder="dynamic programming")
            goal = gr.Textbox(label="Goal", placeholder="coding interview prep")
            days_until_goal = gr.Number(label="Days until goal", value=14)

            submit = gr.Button("Find my study plan", variant="primary")

        with gr.Column(scale=1):
            resource_out = gr.Markdown(label="Resource found")
            partner_out = gr.Markdown(label="Study partner")
            flashcards_out = gr.Markdown(label="Flashcards")
            plan_out = gr.Markdown(label="Study plan")
            recap_out = gr.Markdown(label="Recap card")
            notes_out = gr.Markdown(label="Agent notes (fallbacks/branching)")
            error_out = gr.Markdown(label="Errors")

    submit.click(
        fn=handle_query,
        inputs=[
            topic, resource_type, max_difficulty,
            want_partner, partner_availability, partner_level,
            want_flashcards, num_flashcards,
            known_topics, weak_topics, goal, days_until_goal,
        ],
        outputs=[resource_out, partner_out, flashcards_out, plan_out, recap_out, notes_out, error_out],
    )

if __name__ == "__main__":
    demo.launch()
