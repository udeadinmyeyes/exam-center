import json
import os
import random
import sqlite3
from datetime import date, timedelta
import streamlit as st
from ai_tutor import ask_tutor

st.set_page_config(page_title="Центр подготовки к экзаменам — ОГЭ и ЕГЭ", layout="wide", initial_sidebar_state="collapsed")
st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)

DB_NAME = "platform.db"
COURSES_FILE = os.path.join("data", "courses.json")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, exam_type TEXT DEFAULT 'ЕГЭ', subject_goals TEXT DEFAULT '{}', xp INTEGER DEFAULT 0, streak INTEGER DEFAULT 1, last_active TEXT, accent_color TEXT DEFAULT '#FACC15', custom_status TEXT DEFAULT 'Системная подготовка к экзаменам', title TEXT DEFAULT 'Начальный уровень', avatar_icon TEXT DEFAULT '🎓')")
    c.execute("CREATE TABLE IF NOT EXISTS solved_tasks (username TEXT, task_id TEXT, PRIMARY KEY (username, task_id))")
    c.execute("CREATE TABLE IF NOT EXISTS custom_tasks (id TEXT PRIMARY KEY, exam_type TEXT, subject TEXT, num TEXT, topic TEXT, difficulty TEXT, question TEXT, answer TEXT, hint TEXT)")
    for col_def in ["subject_goals TEXT DEFAULT '{}'", "accent_color TEXT DEFAULT '#FACC15'", "custom_status TEXT DEFAULT 'Системная подготовка к экзаменам'", "title TEXT DEFAULT 'Начальный уровень'", "avatar_icon TEXT DEFAULT '🎓'"]:
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
        last_active = user
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
    c.execute("UPDATE users SET exam_type=?, subject_goals=?, accent_color=?, custom_status=?, avatar_icon=? WHERE username=?", (exam_type, json.dumps(goals_dict, ensure_ascii=False), accent_color, custom_status, avatar_icon, username))
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
        new_xp = (row if row else 0) + xp_reward
        c.execute("UPDATE users SET xp = ?, title = ? WHERE username = ?", (new_xp, calc_title(new_xp), username))
    conn.commit()
    conn.close()
    return not already


def add_new_fipi_task(exam_type: str, subject: str, num: str, topic: str, difficulty: str, question: str, answer: str, hint: str):
    task_id = f"custom_{exam_type}_{random.randint(10000, 99999)}"
    new_task = {"id": task_id, "num": num.strip() or "Задание ФИПИ", "topic": topic.strip() or "Актуальный банк", "difficulty": difficulty, "question": question.strip(), "answer": answer.strip(), "hint": hint.strip() or "Внимательно проверьте условие задания."}
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO custom_tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (task_id, exam_type, subject, new_task["num"], new_task["topic"], difficulty, new_task["question"], new_task["answer"], new_task["hint"]))
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
    c.execute("SELECT u.username, u.exam_type, u.xp, u.streak, u.title, u.avatar_icon, COUNT(s.task_id) FROM users u LEFT JOIN solved_tasks s ON u.username = s.username GROUP BY u.username ORDER BY u.xp DESC, COUNT(s.task_id) DESC LIMIT 25")
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
    return {r for r in rows}


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

css_parts = [
    "<style>",
    "@import url('https://googleapis.com');",
    "html, body, [class*='css'] { font-family: 'Inter', sans-serif; }",
    "#MainMenu, footer, header {visibility: hidden;}",
    ".stApp { background-color: #FAF9F5; background-image: linear-gradient(to bottom, rgba(250,249,245,0.92) 0%, rgba(245,240,224,0.88) 45%, rgba(28,29,34,0.94) 85%, #111216 100%), linear-gradient(rgba(17,18,22,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(17,18,22,0.04) 1px, transparent 1px); background-size: 100% 100%, 32px 32px, 32px 32px; background-attachment: fixed; color: #111216; }",
    ".block-container { padding-top: 1.4rem !important; padding-bottom: 3rem !important; }",
    "h1, h2, h3, h4, p, label, .stMarkdown, .stRadio label, .stCheckbox label { color: #111216 !important; }",
    "@keyframes fadeSlideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }",
    "@keyframes goldShimmer { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }",
    "@keyframes flamePulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.14); } }",
    ".anim-block { animation: fadeSlideUp 0.45s ease both; }",
    ".stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb='select'] > div { background-color: #FFFFFF !important; color: #111216 !important; border: 1.5px solid #D4D4D8 !important; border-radius: 8px !important; }",
    ".stTabs [data-baseweb='tab-list'] { background: transparent !important; gap: 12px; border-bottom: 2px solid rgba(17,18,22,0.12); margin-bottom: 16px; }",
    ".stTabs [data-baseweb='tab'] { background: transparent !important; color: #52525B !important; font-weight: 600 !important; }",
    ".stTabs [aria-selected='true'] { color: #111216 !important; border-bottom: 3px solid #FACC15 !important; }",
    if not st.session_state.logged_in:
    st.markdown('<div style="text-align:center; padding-top:14px;" class="anim-block"><div class="official-badge">ГОСУДАРСТВЕННАЯ ИТОГОВАЯ АТТЕСТАЦИЯ • ОГЭ И ЕГЭ</div><h1 class="main-heading">Центр подготовки к экзаменам</h1><p class="sub-heading">Индивидуальный план подготовки, актуальные задания открытого банка ФИПИ и пошаговый разбор сложных тем.</p></div>', unsafe_allow_html=True)
    _, center_col, _ = st.columns([1, 1.35, 1])
    with center_col:
        tab_in, tab_reg = st.tabs(["Вход в личный кабинет", "Регистрация обучающегося"])
        with tab_in:
            login_name = st.text_input("Имя пользователя", placeholder="Например: Алексей_10А", key="login_input")
            if st.button("Продолжить", use_container_width=True, key="btn_login"):
                if login_name.strip():
                    get_or_create_user(login_name.strip())
                    st.session_state.username = login_name.strip()
                    st.session_state.logged_in = True
                    st.query_params["u"] = login_name.strip()
                    st.rerun()
                else:
                    st.warning("Введите имя пользователя для входа.")
        with tab_reg:
            step = st.session_state.reg_step
            pct = step * 25
            st.markdown(f'<div class="dark-card"><div style="display:flex;justify-content:space-between;color:#FACC15;font-weight:700;font-size:13px;"><span>Этап настройки: Шаг {step} из 4</span><span>{pct}%</span></div><div class="progress-track"><div class="progress-fill" style="width:{pct}%;"></div></div></div>', unsafe_allow_html=True)
            if step == 1:
                r_name = st.text_input("Шаг 1. Придумайте имя пользователя", placeholder="Например: Алексей_10А", key="r_name_in")
                if st.button("Продолжить", use_container_width=True, key="step1_next"):
                    if r_name.strip():
                        st.session_state.tmp_reg_name = r_name.strip()
                        st.session_state.reg_step = 2
                        st.rerun()
                    else:
                        st.warning("Укажите имя пользователя.")
            elif step == 2:
                r_exam = st.radio("Шаг 2. Выберите форму аттестации", ["ЕГЭ", "ОГЭ"], horizontal=True, key="r_exam_in")
                c1, c2 = st.columns(2)
                if c1.button("Назад", use_container_width=True, key="s2_b"):
                    st.session_state.reg_step = 1
                    st.rerun()
                if c2.button("Продолжить", use_container_width=True, key="s2_n"):
                    st.session_state.tmp_reg_exam = r_exam
                    st.session_state.reg_step = 3
                    st.rerun()
            elif step == 3:
                r_ava = st.radio("Шаг 3. Выберите значок профиля", ["🎓", "📘", "🧭", "⚡", "🏛️", "📐"], horizontal=True, key="r_ava_in")
                c1, c2 = st.columns(2)
                if c1.button("Назад", use_container_width=True, key="s3_b"):
                    st.session_state.reg_step = 2
                    st.rerun()
                if c2.button("Продолжить", use_container_width=True, key="s3_n"):
                    st.session_state.tmp_reg_ava = r_ava
                    st.session_state.reg_step = 4
                    st.rerun()
            elif step == 4:
                r_status = st.text_input("Шаг 4. Ваша учебная цель или девиз", value="Системная подготовка к экзаменам", key="r_status_in")
                c1, c2 = st.columns(2)
                if c1.button("Назад", use_container_width=True, key="s4_b"):
                    st.session_state.reg_step = 3
                    st.rerun()
                if c2.button("Подтвердить и создать профиль", use_container_width=True, key="s4_d"):
                    uname = st.session_state.get("tmp_reg_name", "Ученик")
                    get_or_create_user(uname)
                    update_profile(uname, st.session_state.get("tmp_reg_exam", "ЕГЭ"), {}, "#FACC15", r_status.strip() or "Системная подготовка к экзаменам", st.session_state.get("tmp_reg_ava", "🎓"))
                    st.session_state.username = uname
                    st.session_state.logged_in = True
                    st.session_state.reg_step = 1
                    st.query_params["u"] = uname
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    cards_info = [
        ("Актуальная база ФИПИ", "Свежие задания из открытого банка ФИПИ и тренировочных сборников текущего года."),
        ("План под целевой балл", "При выборе предмета задаётся нужный результат — от минимального порога до 100 баллов."),
        ("Разбор каждой ошибки", "Система пошагово объясняет решение простым языком и подстраивается под ваши уточнения."),
        ("Рейтинг и регулярность", "Начисление очков опыта за верные ответы, учёт дней занятий и таблица лидеров."),
    ]
    for col, (t_head, t_desc) in zip(st.columns(4), cards_info):
        col.markdown(f'<div class="dark-card" style="min-height:125px;"><div class="card-title">{t_head}</div><p class="card-text">{t_desc}</p></div>', unsafe_allow_html=True)
    st.stop()

username = st.session_state.username
user = get_or_create_user(username)
_, exam_type, subject_goals_str, xp, streak, _, accent_color, custom_status, title, avatar_icon = user
solved_ids = get_solved_ids(username)
subject_goals = parse_goals(subject_goals_str)

nav_left, nav_mid, nav_right = st.columns([0.8, 8.4, 0.8])
with nav_left:
    st.markdown('<style>div[data-testid="column"]:first-child div.stButton>button{border-radius:50%!important;width:44px!important;height:44px!important;padding:0!important;font-size:20px!important;background:#FFF!important;color:#111216!important;border:1.5px solid #D4D4D8!important;}</style>', unsafe_allow_html=True)
    if st.button(avatar_icon, key="toggle_profile_btn"):
        st.session_state.profile_open = not st.session_state.profile_open
        st.rerun()
with nav_mid:
    st.markdown(f'<div class="top-decor-bar"><span style="color:#FACC15;font-size:12.5px;font-weight:700;">ЦЕНТР ПОДГОТОВКИ К {exam_type} • {st.session_state.active_section.upper()}</span><span style="color:#D4D4D8;font-size:12px;">Открытый банк ФИПИ • 2026–2027</span></div>', unsafe_allow_html=True)
with nav_right:
    with st.popover("☰", use_container_width=True):
        st.markdown("**Навигация**")
        for sec in ["Курсы подготовки", "Все задания банка ФИПИ", "Квиз", "Рейтинг"]:
            if st.button(sec, key=f"nav_{sec}", use_container_width=True):
                st.session_state.active_section = sec
                st.rerun()

if st.session_state.profile_open:
    st.markdown(f'<div class="dark-card" style="margin-top:14px;"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;"><div><span style="font-size:24px;margin-right:8px;">{avatar_icon}</span><span style="color:#FFF;font-size:24px;font-weight:800;">{username}</span> <span style="background:#FACC15;color:#111216;font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px;">{title}</span></div><div style="color:#FACC15;font-weight:600;">Экзамен: {exam_type}</div></div><div style="color:#D4D4D8;font-size:14px;margin-top:6px;">{custom_status}</div></div>', unsafe_allow_html=True)
    next_lvl = 50 if xp < 50 else (150 if xp < 150 else 300)
    rem_xp = max(0, next_lvl - xp)
    lvl_pct = min(100, int((xp / next_lvl) * 100))
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="dark-card"><div style="color:#A1A1AA;font-size:11px;font-weight:700;">ОПЫТ</div><div style="color:#FFF;font-size:26px;font-weight:800;">{xp} XP</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="dark-card"><div style="color:#A1A1AA;font-size:11px;font-weight:700;">РЕГУЛЯРНОСТЬ</div><div style="color:#FFF;font-size:26px;font-weight:800;"><span class="flame-3d">🔥</span>{streak} дн.</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="dark-card"><div style="color:#A1A1AA;font-size:11px;font-weight:700;">ВЫПОЛНЕНО</div><div style="color:#FFF;font-size:26px;font-weight:800;">{len(solved_ids)}</div></div>', unsafe_allow_html=True)
    m4.markdown(f'<div class="dark-card"><div style="color:#A1A1AA;font-size:11px;font-weight:700;">ДО УРОВНЯ ({rem_xp} XP)</div><div class="progress-track" style="margin-top:16px;"><div class="progress-fill" style="width:{lvl_pct}%;"></div></div></div>', unsafe_allow_html=True)
    p1, _, p2 = st.columns([2.5, 5, 2.5])
    with p1:
        new_exam = st.radio("Сменить экзамен:", ["ЕГЭ", "ОГЭ"], index=0 if exam_type == "ЕГЭ" else 1, horizontal=True)
        if new_exam != exam_type:
            update_profile(username, new_exam, subject_goals, accent_color, custom_status, avatar_icon)
            st.session_state.selected_subject = "Все предметы"
            st.rerun()
    with p2:
        st.write("")
        if st.button("Выйти из аккаунта", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.profile_open = False
            st.query_params.clear()
            st.rerun()

all_courses = load_courses_data(include_db=True)
exam_subjects = all_courses.get(exam_type, {})
active_sec = st.session_state.active_section

if active_sec == "Курсы подготовки":
    st.markdown(f'<div class="dark-card" style="margin-top:14px;"><div class="card-title" style="font-size:22px;">Курсы подготовки к {exam_type}</div><p class="card-text">Выберите предмет, задайте целевой балл и переходите к решению актуальных заданий ФИПИ.</p></div>', unsafe_allow_html=True)
    subj_list = list(exam_subjects.items())
    for idx in range(0, len(subj_list), 2):
        cols = st.columns(2)
        for col_i in range(2):
            if idx + col_i >= len(subj_list):
                break
            subj_name, subj_data = subj_list[idx + col_i]
            tasks = subj_data.get("tasks", [])
            
