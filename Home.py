import streamlit as st

st.set_page_config(
    page_title="French Practice Hub",
    page_icon="🇫🇷",
    layout="wide",
)


def render_home() -> None:
    st.markdown(
        """
        <style>
        .home-shell {
            max-width: 1100px;
        }

        .home-shell p,
        .home-shell li {
            font-size: 1.05rem;
            line-height: 1.7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="home-shell">', unsafe_allow_html=True)
    st.title("🇫🇷 French Practice Hub")
    st.write("Choose how you want to practise French from the sidebar.")

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    readme_lines = readme.splitlines()
    if readme_lines and readme_lines[0].lstrip().startswith("# "):
        readme = "\n".join(readme_lines[1:]).lstrip()

    st.markdown(readme, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


navigation = st.navigation(
    [
        st.Page(render_home, title="Home", icon="🏠", default=True),
        st.Page("pages/01_Conjugations.py", title="Conjugations", icon="📘"),
        st.Page("pages/02_Voice_Realtime.py", title="Speak In French", icon="🎙️"),
        st.Page("pages/04_Vocabulary_Review.py", title="Vocabulary Inbox", icon="🗂️"),
        st.Page("pages/05_Vocabulary_Practice.py", title="Vocabulary Practice", icon="📝"),
    ],
    position="sidebar",
)

navigation.run()
