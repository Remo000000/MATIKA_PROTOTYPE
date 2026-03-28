from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from university.models import Department, Discipline, Faculty, Group, Room, StudentProfile, TeacherProfile


class Command(BaseCommand):
    help = "Convert old English demo values to Cyrillic."

    @transaction.atomic
    def handle(self, *args, **options):
        updated = 0

        faculty_map = {
            "Engineering": "Инженерия",
            "Economics": "Экономика",
            "Natural Sciences": "Естественные науки",
            "Social Sciences": "Общественные науки",
            "Humanities": "Гуманитарные науки",
            "Default": "По умолчанию",
        }
        dept_map = {
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
        discipline_map = {
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
            "Cell Biology": "Клеточная биология",
            "Genetics": "Генетика",
            "Ecology": "Экология",
            "Microbiology": "Микробиология",
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
        room_type_map = {
            "Lecture": "Лекционная",
            "Practice": "Практическая",
            "Laboratory": "Лаборатория",
        }
        building_map = {"Lab": "Лабораторный корпус"}

        for obj in Faculty.objects.all():
            new_name = faculty_map.get(obj.name)
            if new_name and new_name != obj.name:
                obj.name = new_name
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Department.objects.select_related("faculty"):
            new_name = dept_map.get(obj.name)
            if new_name and new_name != obj.name:
                obj.name = new_name
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Discipline.objects.all():
            new_name = discipline_map.get(obj.name)
            if new_name and new_name != obj.name:
                obj.name = new_name
                obj.save(update_fields=["name"])
                updated += 1

        for obj in Room.objects.all():
            changed = False
            if obj.building in building_map:
                obj.building = building_map[obj.building]
                changed = True
            if obj.room_type in room_type_map:
                obj.room_type = room_type_map[obj.room_type]
                changed = True
            if obj.equipment:
                eq = (
                    obj.equipment.replace("projector", "проектор")
                    .replace("speakers", "колонки")
                    .replace("whiteboard", "маркерная доска")
                    .replace("internet", "интернет")
                    .replace("pc", "компьютеры")
                )
                if eq != obj.equipment:
                    obj.equipment = eq
                    changed = True
            if changed:
                obj.save(update_fields=["building", "room_type", "equipment"])
                updated += 1

        for obj in TeacherProfile.objects.select_related("user"):
            changed = False
            if obj.academic_title == "Senior Lecturer":
                obj.academic_title = "Старший преподаватель"
                changed = True
            elif obj.academic_title == "Associate Professor":
                obj.academic_title = "Доцент"
                changed = True
            if obj.profession in dept_map:
                obj.profession = dept_map[obj.profession]
                changed = True
            if obj.bio.startswith("Specialist in "):
                raw = obj.bio.replace("Specialist in ", "").rstrip(".")
                obj.bio = f"Специалист по направлению: {dept_map.get(raw, raw)}."
                changed = True
            if changed:
                obj.save(update_fields=["academic_title", "profession", "bio"])
                updated += 1

        for obj in User.objects.filter(full_name__in=["Admin MATIKA", "Admin"]):
            obj.full_name = "Администратор МАТИКА"
            obj.save(update_fields=["full_name"])
            updated += 1

        # Optional group code conversion for seeded demo groups.
        prefix_map = {"SE-": "ПИ-", "DS-": "НД-", "FI-": "ФН-", "BA-": "БА-", "CS-": "КН-"}
        for obj in Group.objects.all():
            new_name = obj.name
            for old_prefix, new_prefix in prefix_map.items():
                if obj.name.startswith(old_prefix):
                    new_name = obj.name.replace(old_prefix, new_prefix, 1)
                    break
            if new_name != obj.name and not Group.objects.filter(name=new_name).exists():
                obj.name = new_name
                obj.save(update_fields=["name"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Updated entries: {updated}"))
