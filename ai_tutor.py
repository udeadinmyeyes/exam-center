import re
import g4f


def clean_text(text: str) -> str:
    text = text.replace("$$", "").replace("$", "")
    text = text.replace("\\frac", "").replace("\\sqrt", "√")
    text = re.sub(r"[\\{}]", "", text)
    return text.strip()


def ask_tutor(question: str, user_answer: str, correct_answer: str, user_request: str = "") -> str:
    extra_instruction = (
        f"Дополнительная просьба ученика: '{user_request}'. Обязательно подстрой стиль и глубину объяснения под эту просьбу."
        if user_request.strip()
        else "Объясняй спокойно, пошагово и максимально понятно, как хороший школьный учитель."
    )

    system_prompt = (
        f"Ты опытный преподаватель по подготовке к ОГЭ и ЕГЭ. {extra_instruction} "
        "СТРОГОЕ ПРАВИЛО: пиши на русском языке простым человеческим языком. Запрещено использовать LaTeX, "
        "обратные слэши, знаки доллара и сложные технические символы. Дроби пиши через /, корни через √, степени через ^."
    )

    prompt = (
        f"Задание: {question}\n"
        f"Ответ ученика: {user_answer}\n"
        f"Правильный ответ: {correct_answer}\n"
        "Пошагово разбери решение и подскажи, где возникла ошибка (если ответ неверный)."
    )

    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        return clean_text(str(response))
    except Exception:
        return (
            f"Правильный ответ: {correct_answer}. "
            "(Не удалось получить разбор от бесплатного сервера ИИ — попробуйте нажать кнопку ещё раз)."
        )
