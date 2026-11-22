import json
import os
import sqlite3
from datetime import date, timedelta
import streamlit as st

st.set_page_config(
    page_title="Центр подготовки к экзаменам — ОГЭ и ЕГЭ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)

# ==========================================
# БАЗА ДАННЫХ (SQLite)
# ==========================================
DB_NAME = "platform.db"


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
    c.execute(
        "SELECT username, exam_type, subject_goals, xp, streak, last_active, accent_color, custom_status, title, avatar_icon FROM users WHERE username = ?",
        (username,),
    )
    user = c.fetchone()
    if not user:
        c.execute(
            "INSERT INTO users (username, last_active) VALUES (?, ?)",
            (username, today),
        )
        conn.commit()
        c.execute(
            "SELECT username, exam_type, subject_goals, xp, streak, last_active, accent_color, custom_status, title, avatar_icon FROM users WHERE username = ?",
            (username,),
        )
        user = c.fetchone()
    else:
        last_active = user[5]
        yesterday = str(date.today() - timedelta(days=1))
        if last_active == yesterday:
            c.execute(
                "UPDATE users SET streak = streak + 1, last_active = ? WHERE username = ?",
                (today, username),
            )
        elif last_active != today:
            c.execute(
                "UPDATE users SET streak = 1, last_active = ? WHERE username = ?",
                (today, username),
            )
        conn.commit()
        c.execute(
            "SELECT username, exam_type, subject_goals, xp, streak, last_active, accent_color, custom_status, title, avatar_icon FROM users WHERE username = ?",
            (username,),
        )
        user = c.fetchone()
    conn.close()
    return user


def update_profile(username: str, exam_type: str, goals_dict: dict, accent_color: str, custom_status: str, avatar_icon: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    goals_json = json.dumps(goals_dict, ensure_ascii=False)
    c.execute(
        """
        UPDATE users
        SET exam_type=?, subject_goals=?, accent_color=?, custom_status=?, avatar_icon=?
        WHERE username=?
        """,
        (exam_type, goals_json, accent_color, custom_status, avatar_icon, username),
    )
    conn.commit()
    conn.close()


def parse_goals(goals_str: str) -> dict:
    if not goals_str:
        return {}
    try:
        data = json.loads(goals_str)
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


init_db()

# Сохранение сессии при нажатии F5 через URL-параметр
qp_user = st.query_params.get("u", "")
if "logged_in" not in st.session_state:
    if qp_user and user_exists(qp_user):
        st.session_state.logged_in = True
        st.session_state.username = qp_user
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""

if "reg_step" not in st.session_state:
    st.session_state.reg_step = 1
if "profile_open" not in st.session_state:
    st.session_state.profile_open = False
if "active_section" not in st.session_state:
    st.session_state.active_section = "Курсы подготовки"

# ==========================================
# ЭТАЛОННЫЙ ДИЗАЙН (ПЛАВНЫЙ БЕЛО-ЖЁЛТО-ЧЁРНЫЙ)
# ==========================================
css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

#MainMenu, footer, header {visibility: hidden;}

.stApp {
    background-color: #FAF9F5;
    background-image:
        linear-gradient(to bottom, rgba(250, 249, 245, 0.90) 0%, rgba(245, 240, 224, 0.86) 45%, rgba(28, 29, 34, 0.92) 85%, #111216 100%),
        linear-gradient(rgba(17, 18, 22, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(17, 18, 22, 0.04) 1px, transparent 1px);
    background-size: 100% 100%, 32px 32px, 32px 32px;
    background-attachment: fixed;
    color: #111216;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
}

h1, h2, h3, h4, p, label, .stMarkdown, .stRadio label, .stCheckbox label {
    color: #111216 !important;
}

.stTextInput input {
    background-color: #FFFFFF !important;
    color: #111216 !important;
    border: 1.5px solid #D4D4D8 !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    font-size: 15px !important;
}
.stTextInput input:focus {
    border-color: #111216 !important;
    box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.45) !important;
}

/* Вкладки на стартовом экране */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent !important;
    gap: 12px;
    border-bottom: 2px solid rgba(17, 18, 22, 0.12);
    margin-bottom: 18px;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    color: #52525B !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    padding: 8px 4px !important;
}
.stTabs [aria-selected="true"] {
    color: #111216 !important;
    border-bottom: 3px solid #FACC15 !important;
}

/* Кнопки: чёрные, при наведении — ярко-жёлтые */
div.stButton > button,
div.stFormSubmitButton > button {
    background-color: #111216 !important;
    color: #FFFFFF !important;
    border: 1.5px solid #111216 !important;
    border-radius: 10px !important;
    padding: 11px 20px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    transition: all 0.22s ease !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
}
div.stButton > button p,
div.stFormSubmitButton > button p {
    color: #FFFFFF !important;
    transition: color 0.22s ease !important;
}
div.stButton > button:hover,
div.stFormSubmitButton > button:hover {
    background-color: #FACC15 !important;
    color: #111216 !important;
    border-color: #111216 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 18px rgba(250, 204, 21, 0.45) !important;
}
div.stButton > button:hover p,
div.stFormSubmitButton > button:hover p {
    color: #111216 !important;
}

/* Верхний бейдж и заголовок */
.official-badge {
    display: inline-block;
    background-color: #111216;
    color: #FACC15 !important;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding: 6px 16px;
    border-radius: 999px;
    margin-bottom: 14px;
    text-transform: uppercase;
}
.main-heading {
    font-size: 40px;
    font-weight: 800;
    color: #111216 !important;
    margin: 0;
    letter-spacing: -0.5px;
}
.sub-heading {
    font-size: 16px;
    color: #3F3F46 !important;
    max-width: 600px;
    margin: 10px auto 24px auto;
    line-height: 1.5;
}

/* Переливающаяся шкала прогресса */
@keyframes goldShimmer {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.progress-wrapper {
    background-color: #14151A;
    border: 1px solid #27272A;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 18px;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
}
.progress-header {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    font-weight: 600;
    color: #FACC15 !important;
    margin-bottom: 8px;
}
.progress-track {
    width: 100%;
    height: 10px;
    background-color: #27272A;
    border-radius: 999px;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #EAB308, #FACC15, #FEF08A, #FACC15, #CA8A04);
    background-size: 200% 200%;
    animation: goldShimmer 3s ease infinite;
    border-radius: 999px;
    transition: width 0.4s ease;
}

/* 4 нижние информационные карточки на главной */
.info-card {
    background-color: #14151A;
    border: 1px solid #27272A;
    border-top: 4px solid #FACC15;
    border-radius: 14px;
    padding: 20px 22px;
    min-height: 128px;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
}
.info-card-title {
    color: #FFFFFF !important;
    font-size: 16px;
    font-weight: 700;
    margin: 0 0 8px 0;
}
.info-card-desc {
    color: #E4E4E7 !important;
    font-size: 13.5px;
    line-height: 1.5;
    margin: 0;
}

/* Верхняя навигационная панель после входа */
.top-decor-bar {
    background-color: #14151A;
    border: 1px solid #27272A;
    border-radius: 12px;
    padding: 11px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
}
.top-decor-left {
    color: #FACC15 !important;
    font-size: 12.5px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}
.top-decor-right {
    color: #D4D4D8 !important;
    font-size: 12.5px;
    font-weight: 500;
}

/* Карточка профиля */
.profile-card-main {
    background-color: #14151A;
    border: 1px solid #27272A;
    border-top: 4px solid #FACC15;
    border-radius: 16px;
    padding: 24px 28px;
    margin-top: 14px;
    margin-bottom: 16px;
    box-shadow: 0 14px 32px rgba(0, 0, 0, 0.25);
}
.profile-name {
    color: #FFFFFF !important;
    font-size: 26px;
    font-weight: 800;
    vertical-align: middle;
}
.profile-rank-badge {
    background-color: #FACC15;
    color: #111216 !important;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    margin-left: 10px;
    vertical-align: middle;
}
.profile-meta {
    color: #FACC15 !important;
    font-size: 14px;
    font-weight: 600;
}
.profile-sub {
    color: #D4D4D8 !important;
    font-size: 14px;
    margin-top: 8px;
}

/* 4 карточки метрик */
.metric-tile {
    background-color: #14151A;
    border: 1px solid #27272A;
    border-top: 3px solid #FACC15;
    border-radius: 14px;
    padding: 18px 20px;
    height: 112px;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
}
.metric-label {
    color: #A1A1AA !important;
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    margin-bottom: 10px;
}
.metric-val {
    color: #FFFFFF !important;
    font-size: 28px;
    font-weight: 800;
    line-height: 1.1;
}

@keyframes flamePulse {
    0% { transform: scale(1); filter: drop-shadow(0 0 6px rgba(249, 115, 22, 0.7)); }
    50% { transform: scale(1.12); filter: drop-shadow(0 0 14px rgba(250, 204, 21, 0.95)); }
    100% { transform: scale(1); filter: drop-shadow(0 0 6px rgba(249, 115, 22, 0.7)); }
}
.flame-3d {
    display: inline-block;
    font-size: 28px;
    animation: flamePulse 2s ease-in-out infinite;
    margin-right: 6px;
    vertical-align: middle;
}

/* Правое меню (popover) */
div[data-testid="stPopover"] > button {
    background-color: #FFFFFF !important;
    color: #111216 !important;
    border: 1.5px solid #D4D4D8 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}
div[data-testid="stPopover"] > button:hover {
    background-color: #FACC15 !important;
    border-color: #111216 !important;
}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# ==========================================
# ЭКРАН 1: ВХОД И ПОШАГОВАЯ РЕГИСТРАЦИЯ
# ==========================================
if not st.session_state.logged_in:
    st.markdown(
        '<div style="text-align:center; padding-top:16px;">'
        '<div class="official-badge">ГОСУДАРСТВЕННАЯ ИТОГОВАЯ АТТЕСТАЦИЯ • ОГЭ И ЕГЭ</div>'
        '<h1 class="main-heading">Центр подготовки к экзаменам</h1>'
        '<p class="sub-heading">Индивидуальный план подготовки, актуальные задания открытого банка ФИПИ и пошаговый разбор сложных тем.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1, 1.35, 1])
    with center_col:
        tab_in, tab_reg = st.tabs(["Вход в личный кабинет", "Регистрация обучающегося"])

        with tab_in:
            login_name = st.text_input("Имя пользователя", placeholder="Например: Алексей_10А", key="login_input")
            if st.button("Продолжить", use_container_width=True, key="btn_login"):
                clean_name = login_name.strip()
                if clean_name:
                    get_or_create_user(clean_name)
                    st.session_state.username = clean_name
                    st.session_state.logged_in = True
                    st.query_params["u"] = clean_name
                    st.rerun()
                else:
                    st.warning("Введите имя пользователя для входа.")

        with tab_reg:
            step = st.session_state.reg_step
            pct = step * 25
            st.markdown(
                f'<div class="progress-wrapper">'
                f'<div class="progress-header"><span>Этап настройки: Шаг {step} из 4</span><span>{pct}%</span></div>'
                f'<div class="progress-track"><div class="progress-fill" style="width:{pct}%;"></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

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
                c_b1, c_b2 = st.columns(2)
                with c_b1:
                    if st.button("Назад", use_container_width=True, key="step2_back"):
                        st.session_state.reg_step = 1
                        st.rerun()
                with c_b2:
                    if st.button("Продолжить", use_container_width=True, key="step2_next"):
                        st.session_state.tmp_reg_exam = r_exam
                        st.session_state.reg_step = 3
                        st.rerun()

            elif step == 3:
                avatars = ["🎓", "📘", "🧭", "⚡", "🏛️", "📐"]
                r_ava = st.radio("Шаг 3. Выберите значок профиля", avatars, horizontal=True, key="r_ava_in")
                c_b1, c_b2 = st.columns(2)
                with c_b1:
                    if st.button("Назад", use_container_width=True, key="step3_back"):
                        st.session_state.reg_step = 2
                        st.rerun()
                with c_b2:
                    if st.button("Продолжить", use_container_width=True, key="step3_next"):
                        st.session_state.tmp_reg_ava = r_ava
                        st.session_state.reg_step = 4
                        st.rerun()

            elif step == 4:
                r_status = st.text_input(
                    "Шаг 4. Ваша учебная цель или девиз",
                    value="Системная подготовка к экзаменам",
                    key="r_status_in",
                )
                c_b1, c_b2 = st.columns(2)
                with c_b1:
                    if st.button("Назад", use_container_width=True, key="step4_back"):
                        st.session_state.reg_step = 3
                        st.rerun()
                with c_b2:
                    if st.button("Подтвердить и создать профиль", use_container_width=True, key="step4_done"):
                        uname = st.session_state.get("tmp_reg_name", "Ученик")
                        uexam = st.session_state.get("tmp_reg_exam", "ЕГЭ")
                        uava = st.session_state.get("tmp_reg_ava", "🎓")
                        get_or_create_user(uname)
                        update_profile(uname, uexam, {}, "#FACC15", r_status.strip() or "Системная подготовка к экзаменам", uava)
                        st.session_state.username = uname
                        st.session_state.logged_in = True
                        st.session_state.reg_step = 1
                        st.query_params["u"] = uname
                        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            '<div class="info-card">'
            '<div class="info-card-title">Актуальная база ФИПИ</div>'
            '<p class="info-card-desc">Свежие задания из открытого банка ФИПИ и тренировочных сборников текущего года.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="info-card">'
            '<div class="info-card-title">План под целевой балл</div>'
            '<p class="info-card-desc">При выборе предмета задаётся нужный результат — от минимального порога до 100 баллов.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="info-card">'
            '<div class="info-card-title">Разбор каждой ошибки</div>'
            '<p class="info-card-desc">Система пошагово объясняет решение простым языком и подстраивается под ваши уточнения.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            '<div class="info-card">'
            '<div class="info-card-title">Рейтинг и регулярность</div>'
            '<p class="info-card-desc">Начисление очков опыта за верные ответы, учёт дней занятий и таблица лидеров.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    st.stop()

# ==========================================
# ЭКРАН 2: ВЕРХНЯЯ ПАНЕЛЬ + РАСКРЫВАЮЩИЙСЯ ПРОФИЛЬ
# ==========================================
username = st.session_state.username
user = get_or_create_user(username)
_, exam_type, subject_goals_str, xp, streak, _, accent_color, custom_status, title, avatar_icon = user
solved_ids = get_solved_ids(username)

# Верхняя панель: круглая аватарка слева, декоративная плашка по центру, меню (3 полоски) справа
nav_left, nav_mid, nav_right = st.columns([0.7, 8.6, 0.7])

with nav_left:
    st.markdown(
        """
        <style>
        div[data-testid="column"]:first-child div.stButton > button {
            border-radius: 50% !important;
            width: 44px !important;
            height: 44px !important;
            padding: 0 !important;
            font-size: 20px !important;
            background-color: #FFFFFF !important;
            color: #111216 !important;
            border: 1.5px solid #D4D4D8 !important;
        }
        div[data-testid="column"]:first-child div.stButton > button:hover {
            background-color: #FACC15 !important;
            border-color: #111216 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button(avatar_icon, key="toggle_profile_btn", help="Открыть / закрыть личный профиль"):
        st.session_state.profile_open = not st.session_state.profile_open
        st.rerun()

with nav_mid:
    sec_title = st.session_state.active_section.upper()
    st.markdown(
        f'<div class="top-decor-bar">'
        f'<span class="top-decor-left">ЦЕНТР ПОДГОТОВКИ К {exam_type} • {sec_title}</span>'
        f'<span class="top-decor-right">Открытый банк заданий ФИПИ • 2026–2027</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

with nav_right:
    with st.popover("☰", use_container_width=True):
        st.markdown("**Навигация по платформе**")
        for sec in [
            "Курсы подготовки",
            "Все задания банка ФИПИ",
            "Квиз",
            "Рейтинг",
        ]:
            if st.button(sec, key=f"nav_item_{sec}", use_container_width=True):
                st.session_state.active_section = sec
                st.rerun()

# Раскрывающийся профиль (только по нажатию на круглую аватарку слева)
if st.session_state.profile_open:
    st.markdown(
        f'<div class="profile-card-main">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">'
        f'<div>'
        f'<span style="font-size:26px; vertical-align:middle; margin-right:8px;">{avatar_icon}</span>'
        f'<span class="profile-name">{username}</span>'
        f'<span class="profile-rank-badge">{title}</span>'
        f'</div>'
        f'<div class="profile-meta">Форма аттестации: {exam_type}</div>'
        f'</div>'
        f'<div class="profile-sub">{custom_status}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    next_lvl = 50 if xp < 50 else (150 if xp < 150 else 300)
    rem_xp = max(0, next_lvl - xp)
    lvl_pct = min(100, int((xp / next_lvl) * 100)) if next_lvl > 0 else 100

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div class="metric-tile">'
            f'<div class="metric-label">XP</div>'
            f'<div class="metric-val">{xp} XP</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-tile">'
            f'<div class="metric-label">РЕГУЛЯРНОСТЬ</div>'
            f'<div class="metric-val"><span class="flame-3d">🔥</span>{streak} дн. подряд</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="metric-tile">'
            f'<div class="metric-label">ВЫПОЛНЕНО ЗАДАНИЙ</div>'
            f'<div class="metric-val">{len(solved_ids)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f'<div class="metric-tile">'
            f'<div class="metric-label">ДО НОВОГО УРОВНЯ ({rem_xp} XP)</div>'
            f'<div class="progress-track" style="margin-top:16px;"><div class="progress-fill" style="width:{lvl_pct}%;"></div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.write("")
    p_left, _, p_right = st.columns([2.2, 5.6, 2.2])
    with p_left:
        new_exam = st.radio(
            "Сменить экзамен:",
            ["ЕГЭ", "ОГЭ"],
            index=0 if exam_type == "ЕГЭ" else 1,
            horizontal=True,
            key="switch_exam_radio",
        )
        if new_exam != exam_type:
            update_profile(username, new_exam, parse_goals(subject_goals_str), accent_color, custom_status, avatar_icon)
            st.rerun()
    with p_right:
        st.write("")
        if st.button("Выйти из аккаунта", use_container_width=True, key="btn_logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.profile_open = False
            st.query_params.clear()
            st.rerun()

# Рабочая область ниже верхней панели оставлена чистой для пошагового добавления карточек
