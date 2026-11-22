import json
import os
import random
import sqlite3
from datetime import date, timedelta
import streamlit as st
from ai_tutor import ask_tutor
from bank_data import BANK_DATA

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
    data = json.loads(json.dumps(BANK_DATA))
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
    "div.stButton > button, div.stFormSubmitButton > button { background-color: #111216 !important; color: #FFFFFF !important; border: 1.5px solid #111216 !important; border-radius: 10px !important; padding: 10px 18px !important; font-weight: 600 !important; transition: all 0.2s ease !important; }",
    "div.stButton > button p, div.stFormSubmitButton > button p { color: #FFFFFF !important; }",
    "div.stButton > button:hover, div.stFormSubmitButton > button:hover { background-color: #FACC15 !important; color: #111216 !important; transform: translateY(-1px) !important; }",
    "div.stButton > button:hover p, div.stFormSubmitButton > button:hover p { color: #111216 !important; }",
    "div[data-testid='stPopover'] > button { background: #FFFFFF !important; color: #111216 !important; border: 1.5px solid #D4D4D8 !important; border-radius: 10px !important; font-weight: 700 !important; }",
    "div[data-testid='stPopover'] > button:hover { background: #FACC15 !important; border-color: #111216 !important; }",
    ".official-badge { display: inline-block; background: #111216; color: #FACC15 !important; font-size: 11px; font-weight: 700; padding: 6px 16px; border-radius: 999px; margin-bottom: 12px; }",
    ".main-heading { font-size: 38px; font-weight: 800; color: #111216 !important; margin: 0; }",
    ".sub-heading { font-size: 15.5px; color: #3F3F46 !important; max-width: 600px; margin: 10px auto 22px auto; }",
    ".dark-card { background-color: #14151A; border: 1px solid #27272A; border-top: 4px solid #FACC15; border-radius: 14px; padding: 18px 22px; margin-bottom: 12px; box-shadow: 0 10px 24px rgba(0,0,0,0.24); animation: fadeSlideUp 0.45s ease both; transition: transform 0.22s ease, border-color 0.22s ease; }",
    ".dark-card:hover { transform: translateY(-2px); border-color: #FACC15; }",
    ".card-solved { border-top: 4px solid #22C55E !important; }",
    ".card-title { color: #FFFFFF !important; font-size: 17px; font-weight: 700; margin: 0 0 6px 0; }",
    ".card-text { color: #E4E4E7 !important; font-size: 14px; line-height: 1.5; margin: 0; }",
    ".gold-pill { background: #27272A; color: #FACC15 !important; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 999px; display: inline-block; }",
    ".green-pill { background: rgba(34,197,94,0.18); color: #4ADE80 !important; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 999px; display: inline-block; }",
    ".progress-track { width: 100%; height: 10px; background: #27272A; border-radius: 999px; overflow: hidden; margin-top: 8px; }",
    ".progress-fill { height: 100%; background: linear-gradient(90deg, #EAB308, #FACC15, #FEF08A, #FACC15); background-size: 200% 200%; animation: goldShimmer 3s ease infinite; border-radius: 999px; }",
    ".top-decor-bar { background: #14151A; border: 1px solid #27272A; border-radius: 12px; padding: 11px 18px; display: flex; justify-content: space-between; align-items: center; }",
    ".flame-3d { display: inline-block; font-size: 26px; animation: flamePulse 2s infinite; margin-right: 6px; }",
    ".ai-box { background: #1C1D24; border-left: 4px solid #FACC15; border-radius: 10px; padding: 14px 18px; margin-top: 8px; color: #F4F4F5 !important; font-size: 14px; line-height: 1.55; }",
    "</style>"
]
st.markdown("".join(css_parts), unsafe_allow_html=True)
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
exam_key = exam_type if exam_type in all_courses and all_courses[exam_type] else "ЕГЭ"
exam_subjects = all_courses.get(exam_key, BANK_DATA["ЕГЭ"])
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
            tot_t, sol_t = len(tasks), sum(1 for t in tasks if t["id"] in solved_ids)
            pct_t = int((sol_t / tot_t) * 100) if tot_t else 0
            max_sc, min_sc = subj_data.get("max_score", 100), subj_data.get("min_score", 0)
            cur_goal = max(min_sc, min(max_sc, int(subject_goals.get(subj_name, max_sc))))
            with cols[col_i]:
                st.markdown(f'<div class="dark-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;"><span class="card-title" style="margin:0;">{subj_data.get("icon","📘")} {subj_name}</span><span class="gold-pill">Цель: {cur_goal}/{max_sc}</span></div><p class="card-text" style="min-height:42px;margin-bottom:10px;">{subj_data.get("desc","")}</p><div style="display:flex;justify-content:space-between;color:#A1A1AA;font-size:12px;"><span>Решено: {sol_t} из {tot_t}</span><span>{pct_t}%</span></div><div class="progress-track"><div class="progress-fill" style="width:{pct_t}%;"></div></div></div>', unsafe_allow_html=True)
                b1, b2 = st.columns([1.2, 1])
                if b1.button("Решать задания →", key=f"go_{exam_type}_{subj_name}", use_container_width=True):
                    st.session_state.selected_subject = subj_name
                    st.session_state.active_section = "Все задания банка ФИПИ"
                    st.rerun()
                with b2.popover("🎯 Цель", use_container_width=True):
                    ng = st.slider("Целевой балл", min_sc, max_sc, cur_goal, key=f"sl_{exam_type}_{subj_name}")
                    if st.button("Сохранить", key=f"sv_{exam_type}_{subj_name}", use_container_width=True):
                        ug = dict(subject_goals)
                        ug[subj_name] = ng
                        update_profile(username, exam_type, ug, accent_color, custom_status, avatar_icon)
                        st.rerun()
                st.write("")
                elif active_sec == "Все задания банка ФИПИ":
    st.markdown(f'<div class="dark-card" style="margin-top:14px;"><div class="card-title" style="font-size:22px;">Открытый банк заданий ФИПИ • {exam_type}</div><p class="card-text">Решайте реальные задания, получайте +15 XP за верный ответ и пополняйте базу новыми задачами.</p></div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2.2, 1.5, 1.8])
    opts = ["Все предметы"] + list(exam_subjects.keys())
    def_i = opts.index(st.session_state.selected_subject) if st.session_state.selected_subject in opts else 0
    chosen_subj = f1.selectbox("Предмет:", opts, index=def_i)
    st.session_state.selected_subject = chosen_subj
    chosen_status = f2.selectbox("Статус:", ["Все задания", "Нерешённые", "Выполненные"])
    with f3:
        st.write("")
        with st.popover("➕ Пополнить базу", use_container_width=True):
            if exam_subjects:
                a_subj = st.selectbox("Предмет:", list(exam_subjects.keys()), key="a_s")
                a_num = st.text_input("Номер КИМ:", placeholder="Задание 12", key="a_n")
                a_top = st.text_input("Тема:", placeholder="Производная", key="a_t")
                a_dif = st.selectbox("Сложность:", ["Базовый", "Повышенный", "Высокий"], key="a_d")
                a_q = st.text_area("Условие задания ФИПИ:", key="a_q")
                a_a = st.text_input("Правильный ответ:", key="a_a")
                a_h = st.text_input("Подсказка:", key="a_h")
                if st.button("Сохранить в базу", use_container_width=True, key="a_btn"):
                    if a_q.strip() and a_a.strip():
                        add_new_fipi_task(exam_type, a_subj, a_num, a_top, a_dif, a_q, a_a, a_h)
                        st.success("Задание сохранено!")
                        st.rerun()

    filtered = [(sn, sd.get("icon", "📘"), t) for sn, sd in exam_subjects.items() if chosen_subj in ("Все предметы", sn) for t in sd.get("tasks", []) if not ((chosen_status == "Нерешённые" and t["id"] in solved_ids) or (chosen_status == "Выполненные" and t["id"] not in solved_ids))]
    if not filtered:
        st.info("По выбранным фильтрам заданий пока нет.")
    for s_name, s_icon, task in filtered:
        tid = task["id"]
        done = tid in solved_ids
        badge = '<span class="green-pill">✓ Выполнено (+15 XP)</span>' if done else f'<span class="gold-pill">{task.get("difficulty","Базовый")}</span>'
        st.markdown(f'<div class="dark-card {"card-solved" if done else ""}"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:10px;"><span class="gold-pill">{s_icon} {s_name} • {task.get("num","")} • {task.get("topic","")}</span>{badge}</div><p class="card-text" style="font-size:15.5px;color:#FFF!important;">{task["question"]}</p></div>', unsafe_allow_html=True)
        c_in, c_ok, c_ht = st.columns([3.5, 1.3, 1.2])
        u_ans = c_in.text_input("Ответ", key=f"in_{tid}", label_visibility="collapsed", placeholder="Введите ответ...")
        if c_ok.button("Проверить", key=f"ok_{tid}", use_container_width=True):
            if normalize_ans(u_ans) == normalize_ans(str(task["answer"])):
                added = mark_task_solved(username, tid, 15)
                st.session_state[f"msg_{tid}"] = ("ok", f"Верно! Ответ: {task['answer']}. {'+15 XP!' if added else ''}")
                if added:
                    st.rerun()
            else:
                st.session_state[f"msg_{tid}"] = ("err", f"Неверно («{u_ans}»). Попробуйте ещё или откройте ИИ-разбор.")
        if c_ht.button("Подсказка", key=f"ht_{tid}", use_container_width=True):
            st.session_state[f"sh_{tid}"] = not st.session_state.get(f"sh_{tid}", False)
        if st.session_state.get(f"sh_{tid}"):
            st.markdown(f'<div class="ai-box"><strong style="color:#FACC15;">💡 Подсказка:</strong> {task.get("hint","")}</div>', unsafe_allow_html=True)
        if f"msg_{tid}" in st.session_state:
            k, m = st.session_state[f"msg_{tid}"]
            (st.success if k == "ok" else st.error)(m)
        with st.expander("🤖 Пошаговый разбор от ИИ-преподавателя"):
            req = st.text_input("Уточнение (необязательно):", placeholder="Объясни максимально просто", key=f"rq_{tid}")
            if st.button("Разобрать решение", key=f"tb_{tid}"):
                with st.spinner("Готовим объяснение..."):
                    st.session_state[f"ta_{tid}"] = ask_tutor(task["question"], u_ans.strip() or "Нет ответа", str(task["answer"]), req)
            if f"ta_{tid}" in st.session_state:
                st.markdown(f'<div class="ai-box">{st.session_state[f"ta_{tid}"].replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        st.write("")
        elif active_sec == "Квиз":
    st.markdown(f'<div class="dark-card" style="margin-top:14px;"><div class="card-title" style="font-size:22px;">Экспресс-квиз • {exam_type}</div><p class="card-text">Мини-тест из 5 реальных заданий для быстрой проверки знаний.</p></div>', unsafe_allow_html=True)
    q1, q2 = st.columns([2.5, 1.5])
    q_subj = q1.selectbox("Тема квиза:", ["Все предметы (Микс)"] + list(exam_subjects.keys()))
    start_q = q2.button("🚀 Новый квиз", use_container_width=True)
    if start_q or "quiz_q" not in st.session_state or st.session_state.get("quiz_m") != exam_type:
        pool = [(sn, sd.get("icon", "📘"), t) for sn, sd in exam_subjects.items() if q_subj in ("Все предметы (Микс)", sn) for t in sd.get("tasks", [])]
        random.shuffle(pool)
        st.session_state.quiz_q = pool[:5]
        st.session_state.quiz_m = exam_type
        st.session_state.quiz_done = False
        if start_q:
            st.rerun()
    ql = st.session_state.get("quiz_q", [])
    if ql:
        with st.form("q_form"):
            ans_map = {}
            for i, (sn, sic, qt) in enumerate(ql, 1):
                st.markdown(f'<div class="dark-card"><span class="gold-pill">Вопрос {i}/{len(ql)} • {sic} {sn}</span><p class="card-text" style="color:#FFF!important;margin-top:8px;">{qt["question"]}</p></div>', unsafe_allow_html=True)
                ans_map[qt["id"]] = st.text_input(f"Ответ {i}:", key=f"qi_{i}_{qt['id']}")
            if st.form_submit_button("Проверить квиз", use_container_width=True):
                ok_c, earned, det = 0, 0, []
                for sn, sic, qt in ql:
                    uv = ans_map.get(qt["id"], "")
                    ok = normalize_ans(uv) == normalize_ans(str(qt["answer"]))
                    if ok:
                        ok_c += 1
                        if mark_task_solved(username, qt["id"], 15):
                            earned += 15
                    det.append((sn, qt, uv, ok))
                st.session_state.quiz_done = True
                st.session_state.quiz_res = (ok_c, len(ql), earned, det)
        if st.session_state.get("quiz_done") and "quiz_res" in st.session_state:
            oc, tc, er, dt = st.session_state.quiz_res
            pct = int((oc / tc) * 100)
            st.markdown(f'<div class="dark-card"><div style="display:flex;justify-content:space-between;color:#FACC15;font-weight:700;"><span>Результат: {oc} из {tc} ({pct}%)</span><span>+{er} XP</span></div><div class="progress-track"><div class="progress-fill" style="width:{pct}%;"></div></div></div>', unsafe_allow_html=True)
            for sn, qt, uv, ok in dt:
                (st.success if ok else st.error)(f"{'✓' if ok else '✕'} [{sn}] Ваш ответ: {uv or '—'} | Верный: {qt['answer']}")

elif active_sec == "Рейтинг":
    st.markdown('<div class="dark-card" style="margin-top:14px;"><div class="card-title" style="font-size:22px;">Рейтинг обучающихся платформы</div><p class="card-text">Решайте задания, копите опыт и поднимайтесь в таблице лидеров.</p></div>', unsafe_allow_html=True)
    for idx, (ln, le, lx, ls, lt, la, lsol) in enumerate(get_leaderboard(), 1):
        med = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"#{idx}"))
        brd = "border:2px solid #FACC15;" if ln == username else ""
        st.markdown(f'<div class="dark-card" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;{brd}"><div><strong style="color:#FACC15;font-size:18px;margin-right:10px;">{med}</strong><span style="font-size:20px;margin-right:6px;">{la}</span><strong style="color:#FFF;font-size:16px;">{ln}</strong> <span class="gold-pill">{lt} • {le}</span></div><div style="color:#FACC15;font-weight:700;">✅ {lsol} &nbsp;|&nbsp; 🔥 {ls} дн. &nbsp;|&nbsp; ⚡ {lx} XP</div></div>', unsafe_allow_html=True)
        
