import json
import os
import random
import sqlite3
from datetime import date, timedelta
import streamlit as st
from ai_tutor import ask_tutor

st.set_page_config(
    page_title="Центр подготовки к экзаменам — ОГЭ и ЕГЭ",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)

DB_NAME = "platform.db"
COURSES_FILE = os.path.join("data", "courses.json")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            exam_type TEXT DEFAULT 'ЕГЭ',
            subject_goals TEXT DEFAULT '{}',
            xp INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 1,
            last_active TEXT,
            accent_color TEXT DEFAULT '#FACC15',
            custom_status TEXT DEFAULT 'Системная подготовка к экзаменам',
            title TEXT DEFAULT 'Начальный уровень',
            avatar_icon TEXT DEFAULT '🎓'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS solved_tasks (
            username TEXT,
            task_id TEXT,
            PRIMARY KEY (username, task_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_tasks (
            id TEXT PRIMARY KEY,
            exam_type TEXT,
            subject TEXT,
            num TEXT,
            topic TEXT,
            difficulty TEXT,
            question TEXT,
            answer TEXT,
            hint TEXT
        )
    """)
    for col_def in [
        "subject_goals TEXT DEFAULT '{}'",
        "accent_color TEXT DEFAULT '#FACC15'",
        "custom_status TEXT DEFAULT 'Системная подготовка к экзаменам'",
        "title TEXT DEFAULT 'Начальный уровень'",
        "avatar_icon TEXT DEFAULT '🎓'",
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def calc_title(xp: int) -> str:
    if xp >= 300:
        return "Мастер ФИПИ"
    if xp >= 150:
        return "Продвинутый уровень"
    if xp >= 50:
        return "Уверенный старт"
    return "Начальный уровень"


def user_exists(username: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    res = c.fetchone() is not None
    conn.close()
    return res


def get_or_create_user(username: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = str(date.today())
    c.execute("SELECT username, exam_type, subject_goals, xp, streak, last_active, accent_color, custom_status, title, avatar_icon FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (username, last_active) VALUES (?, ?)", (username, today))
        conn.commit()
    else:
        last_active = user[5]
        yesterday = str(date.today() - timedelta(days=1))
        if last_active == yesterday:
            c.execute("UPDATE users SET streak = streak + 1, last_active = ? WHERE username = ?", (today, username))
        elif last_active != today:
            c.execute("UPDATE users SET streak = 1, last_active = ? WHERE username = ?", (today, username))
        conn.commit()
    c.execute("SELECT username, exam_type, subject_goals, xp, streak, last_active, accent_color, custom_status, title, avatar_icon FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user


def update_profile(username: str, exam_type: str, goals_dict: dict, accent_color: str, custom_status: str, avatar_icon: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET exam_type=?, subject_goals=?, accent_color=?, custom_status=?, avatar_icon=? WHERE username=?",
        (exam_type, json.dumps(goals_dict, ensure_ascii=False), accent_color, custom_status, avatar_icon, username),
    )
    conn.commit()
    conn.close()


def mark_task_solved(username: str, task_id: str, xp_reward: int = 15) -> bool:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM solved_tasks WHERE username = ? AND task_id = ?", (username, task_id))
    already = c.fetchone() is not None
    if not already:
        c.execute("INSERT INTO solved_tasks (username, task_id) VALUES (?, ?)", (username, task_id))
        c.execute("SELECT xp FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        new_xp = (row[0] if row else 0) + xp_reward
        c.execute("UPDATE users SET xp = ?, title = ? WHERE username = ?", (new_xp, calc_title(new_xp), username))
    conn.commit()
    conn.close()
    return not already


def add_new_fipi_task(exam_type: str, subject: str, num: str, topic: str, difficulty: str, question: str, answer: str, hint: str):
    task_id = f"custom_{exam_type}_{random.randint(10000, 99999)}"
    new_task = {
        "id": task_id,
        "num": num.strip() or "Задание ФИПИ",
        "topic": topic.strip() or "Актуальный банк",
        "difficulty": difficulty,
        "question": question.strip(),
        "answer": answer.strip(),
        "hint": hint.strip() or "Внимательно проверьте условие задания.",
    }
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO custom_tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, exam_type, subject, new_task["num"], new_task["topic"], difficulty, new_task["question"], new_task["answer"], new_task["hint"]),
    )
    conn.commit()
    conn.close()
    try:
        data = load_courses_data(include_db=False)
        if exam_type in data and subject in data[exam_type]:
            data[exam_type][subject]["tasks"].append(new_task)
            with open(COURSES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_leaderboard():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT u.username, u.exam_type, u.xp, u.streak, u.title, u.avatar_icon, COUNT(s.task_id) as solved_cnt
        FROM users u LEFT JOIN solved_tasks s ON u.username = s.username
        GROUP BY u.username ORDER BY u.xp DESC, solved_cnt DESC, u.streak DESC LIMIT 25
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def parse_goals(goals_str: str) -> dict:
    try:
        data = json.loads(goals_str or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_solved_ids(username: str) -> set:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT task_id FROM solved_tasks WHERE username = ?", (username,))
    rows = c.fetchall()
    conn.close()
    return {r[0] for r in rows}


def load_courses_data(include_db: bool = True) -> dict:
    data = {"ЕГЭ": {}, "ОГЭ": {}}
    if os.path.exists(COURSES_FILE):
        try:
            with open(COURSES_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception:
            pass
    if include_db:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id, exam_type, subject, num, topic, difficulty, question, answer, hint FROM custom_tasks")
        rows = c.fetchall()
        conn.close()
        for tid, ex_t, subj, num, topic, diff, quest, ans, hint in rows:
            if ex_t in data and subj in data[ex_t]:
                if tid not in {t["id"] for t in data[ex_t][subj]["tasks"]}:
                    data[ex_t][subj]["tasks"].append({"id": tid, "num": num, "topic": topic, "difficulty": diff, "question": quest, "answer": ans, "hint": hint})
    return data


def normalize_ans(val: str) -> str:
    return val.strip().lower().replace(",", ".").replace("ё", "е")


init_db()

qp_user = st.query_params.get("u", "")
if "logged_in" not in st.session_state:
    if qp_user and user_exists(qp_user):
        st.session_state.logged_in = True
        st.session_state.username = qp_user
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""

st.session_state.setdefault("reg_step", 1)
st.session_state.setdefault("profile_open", False)
st.session_state.setdefault("active_section", "Курсы подготовки")
st.session_state.setdefault("selected_subject", "Все предметы")

st.markdown("""
<style>
@import url('https://googleapis.com');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header {visibility: hidden;}
.stApp {
    background-color: #FAF9F5;
    background-image:
        linear-gradient(to bottom, rgba(250,249,245,0.92) 0%, rgba(245,240,224,0.88) 45%, rgba(28,29,34,0.94) 85%, #111216 100%),
        linear-gradient(rgba(17,18,22,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(17,18,22,0.04) 1px, transparent 1px);
    background-size: 100% 100%, 32px 32px, 32px 32px;
    background-attachment: fixed;
    color: #111216;
}
.block-container { padding-top: 1.4rem !important; padding-bottom: 3rem !important; }
h1, h2, h3, h4, p, label, .stMarkdown, .stRadio label, .stCheckbox label { color: #111216 !important; }
@keyframes fadeSlideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes goldShimmer { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
@keyframes flamePulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.14); } }
.anim-block { animation: fadeSlideUp 0.45s ease both; }
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
    
