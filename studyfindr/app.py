"""
StudyFindr Streamlit app. Run with: streamlit run app.py
Opens a local web UI for entering a study request and seeing each tool's
output as the agent works through the planning loop.
"""
import streamlit as st
from agent import run_agent

st.set_page_config(page_title="StudyFindr", page_icon="📚", layout="wide")


def format_resource(resource):
    if not resource:
        st.info("No resource selected.")
        return
    st.markdown(f"**{resource['title']}** ({resource['type']}, {resource['difficulty']})")
    st.caption(f"Platform: {resource['platform']} • {resource['duration_minutes']} min")
    st.write(resource['description'])


def format_partner(partner):
    if not partner:
        st.info("No study partner matched -- continuing solo.")
        return
    st.markdown(f"**{partner['name']}** ({partner['level']})")
    st.caption(f"Available: {', '.join(partner['availability'])} • {partner['timezone']}")
    st.write(partner['bio'])


def format_flashcards(cards):
    if not cards:
        st.info("No flashcards generated.")
        return
    for i, c in enumerate(cards, 1):
        with st.expander(f"Q{i}: {c['question']}"):
            st.write(c['answer'])


st.title("📚 StudyFindr")
st.write(
    "Tell the agent what you're studying. It searches for a resource, "
    "optionally finds a study partner and generates flashcards, then "
    "builds a study plan and a shareable recap -- branching its behavior "
    "based on what each tool returns."
)

with st.sidebar:
    st.header("Study request")

    topic = st.text_input("Topic", placeholder="e.g. dynamic programming")
    resource_type = st.selectbox("Resource type", ["any", "article", "video", "practice_set"])
    max_difficulty = st.selectbox("Max difficulty", ["any", "beginner", "intermediate", "advanced"])

    st.subheader("Study partner")
    want_partner = st.checkbox("Try to find a study partner", value=False)
    partner_availability = st.selectbox("Your availability", ["any", "mornings", "evenings", "weekends"])
    partner_level = st.selectbox("Your level", ["any", "beginner", "intermediate", "advanced"])

    st.subheader("Flashcards")
    want_flashcards = st.checkbox("Generate flashcards", value=False)
    num_flashcards = st.slider("Number of flashcards", 1, 10, 5)

    st.subheader("What you already know")
    known_topics = st.text_input("Known topics (comma-separated)", placeholder="recursion, arrays")
    weak_topics = st.text_input("Weak topics (comma-separated)", placeholder="dynamic programming")
    goal = st.text_input("Goal", placeholder="coding interview prep")
    days_until_goal = st.number_input("Days until goal", min_value=0, value=14)

    submit = st.button("Find my study plan", type="primary", use_container_width=True)

if submit:
    if not topic.strip():
        st.error("Please enter a topic before submitting.")
        st.stop()

    resource_type_val = None if resource_type == "any" else resource_type
    max_difficulty_val = None if max_difficulty == "any" else max_difficulty
    partner_availability_val = None if partner_availability == "any" else partner_availability
    partner_level_val = None if partner_level == "any" else partner_level

    existing_knowledge = {
        "known_topics": [t.strip() for t in known_topics.split(",") if t.strip()],
        "weak_topics": [t.strip() for t in weak_topics.split(",") if t.strip()],
        "goal": goal,
        "days_until_goal": int(days_until_goal),
    }

    with st.spinner("Running the agent..."):
        session = run_agent(
            topic=topic,
            resource_type=resource_type_val,
            max_difficulty=max_difficulty_val,
            want_partner=want_partner,
            partner_availability=partner_availability_val,
            partner_level=partner_level_val,
            want_flashcards=want_flashcards,
            num_flashcards=int(num_flashcards),
            existing_knowledge=existing_knowledge,
        )

    if session["error"]:
        st.error(session["error"])

    if session["notes"]:
        with st.expander("Agent notes (fallbacks / branching decisions)", expanded=False):
            for n in session["notes"]:
                st.write(f"- {n}")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Resource found")
        format_resource(session["selected_resource"])

        st.subheader("Study partner")
        format_partner(session["partner_match"])

        st.subheader("Flashcards")
        format_flashcards(session["flashcards"])

    with col2:
        st.subheader("Study plan")
        if session["study_plan"]:
            st.write(session["study_plan"])
        else:
            st.info("No study plan generated.")

        st.subheader("Recap card")
        if session["recap_card"]:
            st.success(session["recap_card"])
        else:
            st.info("No recap card generated.")
else:
    st.caption("Fill in the sidebar and click **Find my study plan** to run the agent.")
