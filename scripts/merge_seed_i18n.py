"""Merge seed DB string translations into locale/*/LC_MESSAGES/django.po and compile .mo via polib."""
from __future__ import annotations

import sys
from pathlib import Path

import polib

BASE = Path(__file__).resolve().parent.parent

# Russian / Kazakh for English strings in university.translation_catalog (and seed_demo DB).
RU: dict[str, str] = {
    "Engineering": "Инженерия",
    "Economics": "Экономика",
    "Natural Sciences": "Естественные науки",
    "Social Sciences": "Общественные науки",
    "Humanities": "Гуманитарные науки",
    "Software Engineering": "Программная инженерия",
    "Data Science": "Наука о данных",
    "Computer Science": "Компьютерные науки",
    "Cybersecurity": "Кибербезопасность",
    "Information Systems": "Информационные системы",
    "Finance": "Финансы",
    "Business Analytics": "Бизнес-аналитика",
    "Management": "Менеджмент",
    "Physics": "Физика",
    "Chemistry": "Химия",
    "Biology": "Биология",
    "Law": "Право",
    "Psychology": "Психология",
    "Sociology": "Социология",
    "Philology": "Филология",
    "Algorithms": "Алгоритмы",
    "Databases": "Базы данных",
    "Web Development": "Веб-разработка",
    "Software Architecture": "Архитектура ПО",
    "Linear Algebra": "Линейная алгебра",
    "Probability": "Теория вероятностей",
    "Machine Learning": "Машинное обучение",
    "Data Engineering": "Инженерия данных",
    "Programming": "Программирование",
    "Computer Networks": "Компьютерные сети",
    "Operating Systems": "Операционные системы",
    "Discrete Mathematics": "Дискретная математика",
    "Network Security": "Сетевая безопасность",
    "Cryptography": "Криптография",
    "Secure Software Development": "Безопасная разработка ПО",
    "Digital Forensics": "Цифровая криминалистика",
    "Systems Analysis": "Системный анализ",
    "ERP Systems": "Системы ERP",
    "IT Governance": "ИТ-управление",
    "Business Process Modeling": "Моделирование бизнес-процессов",
    "Microeconomics": "Микроэкономика",
    "Accounting": "Бухгалтерский учёт",
    "Corporate Finance": "Корпоративные финансы",
    "Statistics": "Статистика",
    "Business Intelligence": "Бизнес-аналитика BI",
    "SQL Analytics": "SQL-аналитика",
    "Forecasting": "Прогнозирование",
    "Optimization": "Оптимизация",
    "Strategic Management": "Стратегический менеджмент",
    "Organizational Behavior": "Организационное поведение",
    "Human Resource Management": "Управление персоналом",
    "Operations Management": "Операционный менеджмент",
    "Mechanics": "Механика",
    "Thermodynamics": "Термодинамика",
    "Electrodynamics": "Электродинамика",
    "Quantum Physics": "Квантовая физика",
    "General Chemistry": "Общая химия",
    "Organic Chemistry": "Органическая химия",
    "Physical Chemistry": "Физическая химия",
    "Analytical Chemistry": "Аналитическая химия",
    "Cell Biology": "Клеточная биология",
    "Genetics": "Генетика",
    "Ecology": "Экология",
    "Microbiology": "Микробиология",
    "Constitutional Law": "Конституционное право",
    "Civil Law": "Гражданское право",
    "Criminal Law": "Уголовное право",
    "International Law": "Международное право",
    "General Psychology": "Общая психология",
    "Social Psychology": "Социальная психология",
    "Cognitive Science": "Когнитивистика",
    "Research Methods": "Методы исследования",
    "Social Theory": "Социальная теория",
    "Urban Sociology": "Городская социология",
    "Social Policy": "Социальная политика",
    "Survey Methods": "Методы опросов",
    "Comparative Literature": "Сравнительное литературоведение",
    "Stylistics": "Стилистика",
    "Linguistics": "Лингвистика",
    "Translation Studies": "Переводоведение",
    "World History": "Всемирная история",
    "Historiography": "Историография",
    "Kazakhstan History": "История Казахстана",
    "Archival Studies": "Архивоведение",
    "Lecture": "Лекционная",
    "Practice": "Практическая",
    "Laboratory": "Лаборатория",
    "Lab": "Лабораторный корпус",
    "Senior Lecturer": "Старший преподаватель",
    "Associate Professor": "Доцент",
    "Professor": "Профессор",
    "Assistant Professor": "Ассистент профессора",
    "Docent": "Доцент",
    "Lecturer": "Преподаватель",
}

KK: dict[str, str] = {
    "Engineering": "Инженерия",
    "Economics": "Экономика",
    "Natural Sciences": "Табиғи ғылымдар",
    "Social Sciences": "Қоғамдық ғылымдар",
    "Humanities": "Гуманитарлық ғылымдар",
    "Software Engineering": "Бағдарламалық инженерия",
    "Data Science": "Деректер ғылымы",
    "Computer Science": "Компьютерлік ғылым",
    "Cybersecurity": "Киберқауіпсіздік",
    "Information Systems": "Ақпараттық жүйелер",
    "Finance": "Қаржы",
    "Business Analytics": "Бизнес-аналитика",
    "Management": "Менеджмент",
    "Physics": "Физика",
    "Chemistry": "Химия",
    "Biology": "Биология",
    "Law": "Құқық",
    "Psychology": "Психология",
    "Sociology": "Социология",
    "Philology": "Филология",
    "Algorithms": "Алгоритмдер",
    "Databases": "Дерекқорлар",
    "Web Development": "Веб-әзірлеу",
    "Software Architecture": "Бағдарламалық архитектура",
    "Linear Algebra": "Сызықтық алгебра",
    "Probability": "Ықтималдық теориясы",
    "Machine Learning": "Машиналық оқыту",
    "Data Engineering": "Деректер инженериясы",
    "Programming": "Бағдарламалау",
    "Computer Networks": "Компьютерлік желілер",
    "Operating Systems": "Операциялық жүйелер",
    "Discrete Mathematics": "Дискретті математика",
    "Network Security": "Желілік қауіпсіздік",
    "Cryptography": "Криптография",
    "Secure Software Development": "Қауіпсіз бағдарламалау",
    "Digital Forensics": "Цифрлық криминалистика",
    "Systems Analysis": "Жүйелік талдау",
    "ERP Systems": "ERP жүйелері",
    "IT Governance": "АТ басқаруы",
    "Business Process Modeling": "Бизнес-процестерді модельдеу",
    "Microeconomics": "Микроэкономика",
    "Accounting": "Бухгалтерлік есеп",
    "Corporate Finance": "Корпоративтік қаржы",
    "Statistics": "Статистика",
    "Business Intelligence": "Бизнес-аналитика BI",
    "SQL Analytics": "SQL-аналитика",
    "Forecasting": "Болжамдау",
    "Optimization": "Оңтайландыру",
    "Strategic Management": "Стратегиялық менеджмент",
    "Organizational Behavior": "Ұйымдық мінез-құлық",
    "Human Resource Management": "Кадрларды басқару",
    "Operations Management": "Операциялық менеджмент",
    "Mechanics": "Механика",
    "Thermodynamics": "Термодинамика",
    "Electrodynamics": "Электродинамика",
    "Quantum Physics": "Кванттық физика",
    "General Chemistry": "Жалпы химия",
    "Organic Chemistry": "Органикалық химия",
    "Physical Chemistry": "Физикалық химия",
    "Analytical Chemistry": "Аналитикалық химия",
    "Cell Biology": "Клеткалық биология",
    "Genetics": "Генетика",
    "Ecology": "Экология",
    "Microbiology": "Микробиология",
    "Constitutional Law": "Конституциялық құқық",
    "Civil Law": "Азаматтық құқық",
    "Criminal Law": "Қылмыстық құқық",
    "International Law": "Халықаралық құқық",
    "General Psychology": "Жалпы психология",
    "Social Psychology": "Әлеуметтік психология",
    "Cognitive Science": "Когнитивистика",
    "Research Methods": "Зерттеу әдістері",
    "Social Theory": "Әлеуметтік теория",
    "Urban Sociology": "Қалалық социология",
    "Social Policy": "Әлеуметтік саясат",
    "Survey Methods": "Сауалнама әдістері",
    "Comparative Literature": "Салыстырмалы әдебиеттану",
    "Stylistics": "Стилистика",
    "Linguistics": "Тіл білімі",
    "Translation Studies": "Аудару ілімі",
    "World History": "Дүние жүзі тарихы",
    "Historiography": "Тарихнама",
    "Kazakhstan History": "Қазақстан тарихы",
    "Archival Studies": "Мұрағаттану",
    "Lecture": "Дәріс",
    "Practice": "Практика",
    "Laboratory": "Зертхана",
    "Lab": "Зертхана корпусы",
    "Senior Lecturer": "Аға оқытушы",
    "Associate Professor": "Доцент",
    "Professor": "Профессор",
    "Assistant Professor": "Ассистент профессор",
    "Docent": "Доцент",
    "Lecturer": "Оқытушы",
}


def merge_lang(code: str, translations: dict[str, str]) -> None:
    po_path = BASE / "locale" / code / "LC_MESSAGES" / "django.po"
    mo_path = BASE / "locale" / code / "LC_MESSAGES" / "django.mo"
    po = polib.pofile(str(po_path))
    existing: dict[str, polib.POEntry] = {e.msgid: e for e in po}
    added = 0
    for msgid, msgstr in translations.items():
        if msgid in existing:
            ent = existing[msgid]
            if not (ent.msgstr or "").strip():
                ent.msgstr = msgstr
                added += 1
        else:
            po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
            added += 1
    po.save(str(po_path))
    po.save_as_mofile(str(mo_path))
    print(f"{code}: merged/updated {added} entries -> {mo_path}")


def main() -> int:
    merge_lang("ru", RU)
    merge_lang("kk", KK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
