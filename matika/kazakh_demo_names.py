"""Kazakh-style demo identities: latin.first.last@gmail.com + Cyrillic full names."""

from __future__ import annotations

import itertools
import random

# Latin local part for @gmail.com; Cyrillic display names (Kazakh-style).
# 40×40 = 1600 unique (first, last) pairs — enough for large demo seeds.
LATIN_FIRST = [
    # Women
    "aigerim",
    "ainur",
    "amina",
    "aruzhan",
    "asel",
    "assem",
    "dinara",
    "madina",
    "saltanat",
    "zhanar",
    "almira",
    "gulmira",
    "kamila",
    "liana",
    "sabina",
    "aida",
    "dilnaz",
    "gulnar",
    "zhuldyz",
    "kamilya",
    # Men
    "erlan",
    "nurlan",
    "daulet",
    "erbol",
    "yerlan",
    "dimash",
    "almaz",
    "bauyrzhan",
    "timur",
    "ruslan",
    "azamat",
    "sanzhar",
    "adilbek",
    "mukhammed",
    "rakhat",
    "zhanbolat",
    "dauren",
    "yeldos",
    "aisultan",
    "temirlan",
]
CYR_FIRST = [
    "Әйгерім",
    "Айнұр",
    "Амина",
    "Арұжан",
    "Асел",
    "Ассем",
    "Динара",
    "Мадина",
    "Салтанат",
    "Жанар",
    "Алмира",
    "Гүлмира",
    "Камила",
    "Лиана",
    "Сабина",
    "Айда",
    "Дильназ",
    "Гүлнар",
    "Жұлдыз",
    "Кәмиля",
    "Ерлан",
    "Нұрлан",
    "Дәулет",
    "Ербол",
    "Йерлан",
    "Димаш",
    "Алмаз",
    "Бауыржан",
    "Тимур",
    "Руслан",
    "Азамат",
    "Санжар",
    "Әділбек",
    "Мұхаммед",
    "Рахат",
    "Жанболат",
    "Даурен",
    "Елдос",
    "Айсұлтан",
    "Темірлан",
]

LATIN_LAST = [
    "nurtas",
    "tileikhan",
    "omarov",
    "suleimen",
    "bekmurat",
    "kasym",
    "mukhamed",
    "nurzhan",
    "rakhim",
    "serik",
    "tulegen",
    "zhaksylyk",
    "abai",
    "ospan",
    "sattor",
    "nurtasov",
    "alimov",
    "ibraev",
    "kazhigaliev",
    "suleimenov",
    "beisenov",
    "khassanov",
    "nursultanov",
    "smagulov",
    "tokayev",
    "zhumatay",
    "akhmetov",
    "karimov",
    "saparov",
    "yesimov",
    "musayev",
    "dzhaksylykov",
    "nurpeisov",
    "bisenbayev",
    "shaimerdenov",
    "kaliyev",
    "omirtayev",
    "rakhmetov",
    "umarov",
    "kassymov",
]
CYR_LAST = [
    "Нұртас",
    "Тілехан",
    "Омаров",
    "Сүлеймен",
    "Бекмұрат",
    "Қасым",
    "Мұхамед",
    "Нұржан",
    "Рахим",
    "Серік",
    "Түлеген",
    "Жақсылық",
    "Абай",
    "Оспан",
    "Саттор",
    "Нұртасов",
    "Алімов",
    "Ибраев",
    "Қажығалиев",
    "Сүлейменов",
    "Бейсенов",
    "Хасанов",
    "Нұрсұлтанов",
    "Смағұлов",
    "Тоқаев",
    "Жұматай",
    "Ахметов",
    "Каримов",
    "Сапаров",
    "Есімов",
    "Мұсаев",
    "Жақсылықов",
    "Нұрпейісов",
    "Бисенбаев",
    "Шаймерденов",
    "Қалиев",
    "Омиртаев",
    "Рахметов",
    "Умаров",
    "Қасымов",
]

MAX_PAIR_POOL = len(LATIN_FIRST) * len(LATIN_LAST)

ADMIN_EMAIL = "batima.tileikhan@gmail.com"
ADMIN_FULL_NAME = "Батима Тилейхан"


def email_from_pair(fi: int, li: int) -> str:
    return f"{LATIN_FIRST[fi]}.{LATIN_LAST[li]}@gmail.com"


def full_name_from_pair(fi: int, li: int) -> str:
    return f"{CYR_FIRST[fi]} {CYR_LAST[li]}"


def build_teacher_and_student_pairs(
    rng: random.Random,
    *,
    n_teachers: int = 8,
    n_students: int = 240,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]]:
    """Disjoint (first_idx, last_idx) pairs for teachers and students; remainder for overflow users."""
    pair_pool = list(itertools.product(range(len(LATIN_FIRST)), range(len(LATIN_LAST))))
    rng.shuffle(pair_pool)
    need = n_teachers + n_students
    if need > len(pair_pool):
        raise ValueError(
            f"Need {need} unique name pairs but only {len(pair_pool)} exist (max {MAX_PAIR_POOL})."
        )
    return (
        pair_pool[:n_teachers],
        pair_pool[n_teachers : n_teachers + n_students],
        pair_pool[n_teachers + n_students :],
    )
