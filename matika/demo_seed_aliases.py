"""
Map localized demo DB strings (Russian/Kazakh typos) back to English gettext msgids.

Seed data and ``localize_demo_data`` store human-readable names; ``trans_seed`` and
``localize_demo_data`` (kk) rely on these aliases so :func:`django.utils.translation.gettext`
can resolve ``locale/kk/LC_MESSAGES/django.po``.
"""

from __future__ import annotations

# Russian output of the original ``localize_demo_data`` (English → Russian).
_FACULTY_RU = {
    "Engineering": "Инженерия",
    "Economics": "Экономика",
    "Natural Sciences": "Естественные науки",
    "Social Sciences": "Общественные науки",
    "Humanities": "Гуманитарные науки",
    "Default": "По умолчанию",
}
_DEPT_RU = {
    "Computer Science": "Компьютерные науки",
    "Software Engineering": "Программная инженерия",
    "Data Science": "Наука о данных",
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
    "History": "История",
    "General": "Общая кафедра",
}
_DISCIPLINE_RU = {
    "Algorithms": "Алгоритмы",
    "Databases": "Базы данных",
    "Web Development": "Веб-разработка",
    "Software Architecture": "Архитектура ПО",
    "Linear Algebra": "Линейная алгебра",
    "Probability": "Теория вероятностей",
    "Machine Learning": "Машинное обучение",
    "Data Engineering": "Инженерия данных",
    "Microeconomics": "Микроэкономика",
    "Accounting": "Бухгалтерский учет",
    "Corporate Finance": "Корпоративные финансы",
    "Statistics": "Статистика",
    "Business Intelligence": "Бизнес-аналитика BI",
    "SQL Analytics": "SQL-аналитика",
    "Forecasting": "Прогнозирование",
    "Optimization": "Оптимизация",
    "Network Security": "Сетевая безопасность",
    "Cryptography": "Криптография",
    "Secure Software Development": "Безопасная разработка ПО",
    "Digital Forensics": "Цифровая криминалистика",
    "Systems Analysis": "Системный анализ",
    "ERP Systems": "Системы ERP",
    "IT Governance": "ИТ-управление",
    "Business Process Modeling": "Моделирование бизнес-процессов",
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
    "Programming": "Программирование",
    "Computer Networks": "Компьютерные сети",
    "Operating Systems": "Операционные системы",
    "Discrete Mathematics": "Дискретная математика",
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
    "Research Methods": "Методы исследований",
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
}
_ROOM_TYPE_RU = {
    "Lecture": "Лекционная",
    "Practice": "Практическая",
    "Laboratory": "Лаборатория",
}
_BUILDING_RU = {"Lab": "Лабораторный корпус"}

# Kazakh msgstr values from ``locale/kk/LC_MESSAGES/django.po`` (discipline & dept/faculty keys).
# Used when DB already stores Kazakh after ``localize_demo_data`` with kk.
_KK_TO_EN: dict[str, str] = {
    # Typos / stray spaces seen in exports
    "Веб- әзірлеу": "Web Development",
    "Веб-әзірлеу": "Web Development",
    # Faculties
    "Инженерия": "Engineering",
    "Экономика": "Economics",
    "Табиғи ғылымдар": "Natural Sciences",
    "Қоғамдық ғылымдар": "Social Sciences",
    "Гуманитарлық ғылымдар": "Humanities",
    # Departments
    "Компьютерлік ғылым": "Computer Science",
    "Бағдарламалық инженерия": "Software Engineering",
    "Деректер ғылымы": "Data Science",
    "Киберқауіпсіздік": "Cybersecurity",
    "Ақпараттық жүйелер": "Information Systems",
    "Қаржы": "Finance",
    "Бизнес-аналитика": "Business Analytics",
    "Менеджмент": "Management",
    "Физика": "Physics",
    "Химия": "Chemistry",
    "Биология": "Biology",
    "Құқық": "Law",
    "Психология": "Psychology",
    "Социология": "Sociology",
    "Филология": "Philology",
    "Тарих": "History",
    # Disciplines (kk.po)
    "Алгоритмдер": "Algorithms",
    "Дерекқорлар": "Databases",
    "Бағдарламалық архитектура": "Software Architecture",
    "Сызықтық алгебра": "Linear Algebra",
    "Ықтималдық теориясы": "Probability",
    "Машиналық оқыту": "Machine Learning",
    "Деректер инженериясы": "Data Engineering",
    "Микроэкономика": "Microeconomics",
    "Бухгалтерлік есеп": "Accounting",
    "Корпоративтік қаржы": "Corporate Finance",
    "Статистика": "Statistics",
    "Бизнес-аналитика BI": "Business Intelligence",
    "SQL-аналитика": "SQL Analytics",
    "Болжамдау": "Forecasting",
    "Оңтайландыру": "Optimization",
    "Желілік қауіпсіздік": "Network Security",
    "Криптография": "Cryptography",
    "Қауіпсіз бағдарламалау": "Secure Software Development",
    "Цифрлық криминалистика": "Digital Forensics",
    "Жүйелік талдау": "Systems Analysis",
    "ERP жүйелері": "ERP Systems",
    "АТ басқаруы": "IT Governance",
    "Бизнес-процестерді модельдеу": "Business Process Modeling",
    "Стратегиялық менеджмент": "Strategic Management",
    "Ұйымдық мінез-құлық": "Organizational Behavior",
    "Кадрларды басқару": "Human Resource Management",
    "Операциялық менеджмент": "Operations Management",
    "Механика": "Mechanics",
    "Термодинамика": "Thermodynamics",
    "Электродинамика": "Electrodynamics",
    "Кванттық физика": "Quantum Physics",
    "Жалпы химия": "General Chemistry",
    "Органикалық химия": "Organic Chemistry",
    "Физикалық химия": "Physical Chemistry",
    "Аналитикалық химия": "Analytical Chemistry",
    "Бағдарламалау": "Programming",
    "Компьютерлік желілер": "Computer Networks",
    "Операциялық жүйелер": "Operating Systems",
    "Дискретті математика": "Discrete Mathematics",
    "Клеткалық биология": "Cell Biology",
    "Генетика": "Genetics",
    "Экология": "Ecology",
    "Микробиология": "Microbiology",
    "Конституциялық құқық": "Constitutional Law",
    "Азаматтық құқық": "Civil Law",
    "Қылмыстық құқық": "Criminal Law",
    "Халықаралық құқық": "International Law",
    "Жалпы психология": "General Psychology",
    "Әлеуметтік психология": "Social Psychology",
    "Когнитивистика": "Cognitive Science",
    "Зерттеу әдістері": "Research Methods",
    "Әлеуметтік теория": "Social Theory",
    "Қалалық социология": "Urban Sociology",
    "Әлеуметтік саясат": "Social Policy",
    "Сауалнама әдістері": "Survey Methods",
    "Салыстырмалы әдебиеттану": "Comparative Literature",
    "Стилистика": "Stylistics",
    "Тіл білімі": "Linguistics",
    "Аудару ілімі": "Translation Studies",
    "Дүние жүзі тарихы": "World History",
    "Тарихнама": "Historiography",
    "Қазақстан тарихы": "Kazakhstan History",
    "Мұрағаттану": "Archival Studies",
    "Дәріс": "Lecture",
    "Практика": "Practice",
    "Зертхана": "Laboratory",
    "Зертхана корпусы": "Lab",
}


def _invert(m: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for en, loc in m.items():
        out[loc] = en
    return out


_ALIASES_TO_ENGLISH: dict[str, str] = {}
_ALIASES_TO_ENGLISH.update(_invert(_FACULTY_RU))
_ALIASES_TO_ENGLISH.update(_invert(_DEPT_RU))
_ALIASES_TO_ENGLISH.update(_invert(_DISCIPLINE_RU))
_ALIASES_TO_ENGLISH.update(_invert(_ROOM_TYPE_RU))
_ALIASES_TO_ENGLISH.update(_invert(_BUILDING_RU))
_ALIASES_TO_ENGLISH.update(_KK_TO_EN)

# Title rewrites from localize_demo_data (Russian only — unique strings).
_ALIASES_TO_ENGLISH["Старший преподаватель"] = "Senior Lecturer"
# «Доцент» in seed usually came from Associate Professor rule; Docent stayed Latin in DB.
_ALIASES_TO_ENGLISH["Доцент"] = "Associate Professor"


def to_english_seed(value: str | None) -> str | None:
    """Resolve localized discipline/faculty/department/etc. to the English msgid string."""
    if value is None or value == "":
        return value
    s = str(value).strip()
    return _ALIASES_TO_ENGLISH.get(s, s)


def normalize_demo_equipment(value: str | None) -> str | None:
    """Map mixed RU/EN equipment labels to English tokens (comma-separated)."""
    if not value:
        return value
    parts = [p.strip() for p in str(value).split(",")]
    ru_word = {
        "проектор": "projector",
        "колонки": "speakers",
        "маркерная доска": "whiteboard",
        "интернет": "internet",
        "компьютеры": "pc",
    }
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        out.append(ru_word.get(p.lower(), p))
    return ", ".join(out)


def kazakh_equipment_line(english_csv: str) -> str:
    """English comma-separated equipment tokens → Kazakh labels for demo rooms."""
    m = {
        "projector": "проектор",
        "speakers": "динамиктер",
        "whiteboard": "ақ тақта",
        "internet": "интернет",
        "pc": "компьютерлер",
    }
    parts = [p.strip() for p in english_csv.split(",") if p.strip()]
    return ", ".join(m.get(p, p) for p in parts)
