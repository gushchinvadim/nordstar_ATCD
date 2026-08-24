# ATCD — Aviation Training Center Documentation System

Система управления документооборотом авиационного учебного центра (АУЦ) авиакомпании «НордСтар».

## 📋 О проекте

ATCD автоматизирует полный жизненный цикл обучения авиационного персонала:
- Создание групп и набор слушателей
- Формирование расписания и журнала оценок
- Генерация приказов, сертификатов, заданий на тренировку
- Подготовка отчётов для государственных органов (РАУЦ, ФИС ФРДО)
- Индивидуальные учебные планы (ИУП)
- Архивация групп с возможностью восстановления

## 🏗 Архитектура

**Стек:**
- Backend: Django 5.x + Python 3.14
- Database: PostgreSQL
- PDF-генерация: WeasyPrint
- Excel-отчёты: openpyxl
- Frontend: Django Templates + HTMX (в разработке React)

**Приложения Django:**

```text
backend_ATCD/
├── core/           # Базовые утилиты, импорт из Excel
── people/         # Студенты, персонал (Staff)
├── training/       # Программы, модули, этапы, разделы
├── execution/      # Группы, зачисления, оценки, сертификаты, ИУП
├── references/     # Справочники (ВС, аудитории, лицензии, локации)
├── reporting/      # Отчёты РАУЦ и ФРДО
└── docs/           # Views и шаблоны для документов
```

## 🚀 Установка и запуск

### Требования
- Python 3.14
- PostgreSQL 14+
- WeasyPrint (системная библиотека)

### Локальная разработка

```bash
# Клонирование репозитория
git clone <repo-url>
cd nordstar_ATCD/backend_ATCD

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env (DATABASE_URL, SECRET_KEY, EMAIL_HOST и т.д.)

# Применение миграций
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Запуск сервера разработки
python manage.py runserver
```

Админка: http://localhost:8000/admin/

## 📥 Импорт данных

Система поддерживает массовый импорт из Excel-файлов:

```bash
# Импорт программы обучения
python manage.py import_training_program programs.xlsx

# Импорт персонала
python manage.py import_staff staff.xlsx

# Импорт слушателей
python manage.py import_students students.xlsx
```

**Формат файлов:** смотрите примеры в папке `docs/import_templates/`

## 📄 Генерация документов

### Основные документы группы
- Приказ о зачислении
- Расписание занятий
- Журнал подготовки (посещаемость + тематический план)
- Приказ об окончании (ОК) / об отчислении (ОТ)
- Задания на тренировку АСП (Суша/Вода)
- Сертификаты/удостоверения

### Отчёты для госорганов
- **РАУЦ** — Excel и XML форматы
- **ФИС ФРДО** — Excel формат

Документы генерируются через **Центр документов** группы (кнопка в админке).

## 🎓 Индивидуальные учебные планы (ИУП)

Если студент пропустил занятия, методист может назначить ИУП:
1. В журнале оценок нажать кнопку «📋 ИУП» рядом со студентом
2. Указать новые даты, инструкторов, аудитории
3. Система сгенерирует отдельное расписание и тематический план

ИУП сохраняются в БД и могут быть перегенерированы после архивации группы.

##  Архивация групп

Для освобождения места на диске:
1. В админке выбрать завершённые группы
2. Действие: « Архивировать группу и удалить медиа-файлы»
3. Папка группы удаляется, данные в БД сохраняются

**Восстановление:** действие «♻️ Восстановить группу из архива» + перегенерация документов.

## 🗄 Структура базы данных

### Ключевые модели

**training/**
- `Course` — программа обучения (с настройками ФРДО, типом сертификата)
- `Module` — модуль программы
- `Stage` — этап модуля
- `Section` — раздел/тема
- `Subsection` — подраздел

**execution/**
- `Group` — группа обучения
- `Enrollment` — зачисление студента в группу
- `Assessment` — оценка по разделу
- `Certificate` — выданный сертификат
- `ScheduleItem` — занятие в расписании
- `IndividualStudyPlan` — индивидуальный учебный план

**people/**
- `Student` — слушатель
- `Staff` — преподаватель/методист

**references/**
- `AircraftType` — тип ВС
- `Classroom` — аудитория/тренажёр
- `License` — лицензия АУЦ
- `Location` — место проведения

## 🔧 Management Commands

```bash
# Импорт данных
python manage.py import_students <file.xlsx>
python manage.py import_staff <file.xlsx>
python manage.py import_training_program <file.xlsx>
```

## 🚀 Деплой

### Автоматический деплой через `deploy.sh`

```bash
#!/bin/bash
cd /var/www/nordstar_ATCD/nordstar_ATCD/backend_ATCD
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart atcdocs
```

### Ручной деплой

```bash
# 1. Обновление кода
git pull origin main

# 2. Установка зависимостей
pip install -r requirements.txt

# 3. Применение миграций
python manage.py migrate

# 4. Сборка статики
python manage.py collectstatic --noinput

# 5. Перезапуск Gunicorn
sudo systemctl restart atcdocs
```

##  Структура медиа-файлов

```text
media/
└── documents/
    └── {YEAR}/
        └── groups/
            └── {MODULE_CODE}/
                └── {GROUP_NUMBER}/
                    ├── orders/          # Приказы
                    ├── schedules/       # Расписания
                    ├── journal/         # Журналы
                    ├── training_tasks/  # Задания АСП
                    ├── certificates/    # Сертификаты
                    ├── iup/             # Индивидуальные планы
                    └── reports/         # Отчёты РАУЦ/ФРДО
```

## 🔐 Безопасность

- Все views защищены `@staff_member_required`
- CSRF-токены для POST-запросов
- Секреты хранятся в `.env` (не коммитятся)
- Пути к файлам валидируются (защита от path traversal)

## 🧪 Тестирование

```bash
# Запуск всех тестов
python manage.py test

# Тесты конкретного приложения
python manage.py test execution

# С покрытием
coverage run manage.py test
coverage report
```

## 📝 Логирование

Логи сохраняются в `/var/log/atcd/`:
- `django.log` — общие логи приложения
- `errors.log` — только ошибки
- `access.log` — HTTP-запросы

## 🤝 Вклад в проект

1. Создайте feature-ветку: `git checkout -b feature/my-feature`
2. Внесите изменения
3. Закоммитьте миграции: `git add */migrations/0*.py`
4. Отправьте PR

---

**Версия:** 1.0.0  
**Последнее обновление:** Август 2026  
**Проект:** АУЦ НордСтар | Система ATCD