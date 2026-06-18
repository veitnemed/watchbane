"""Содержит интерактивные действия меню настройки тегов."""

from data_work import storage
from data_work import tags_work


def show_tags() -> None:
    """Показывает список тегов."""
    tags = tags_work.load_tags()
    print('\nТеги вайба:\n')
    if len(tags) == 0:
        print('Сейчас вайб-тегов нет.')
        return
    for idx, (feature, settings) in enumerate(tags.items(), start=1):
        print(f'{idx}) {feature} | {settings["label"]}')


def request_new_tag() -> None:
    """Запрашивает данные нового тега и добавляет его в проект."""
    tags = tags_work.load_tags()

    feature = input('Название поля на английском, например imdb_drama >> ').strip()
    if tags_work.is_correct_tag_name(feature) is False:
        print('Ошибка! Название должно начинаться с английской буквы и содержать только английские буквы, цифры и _.')
        return

    if feature in tags:
        print('Ошибка! Такой тег уже существует.')
        return

    settings = {}
    settings["label"] = input('Название для интерфейса >> ').strip()
    settings["title"] = input('Короткий заголовок >> ').strip()
    settings["question"] = input('Описание-вопрос >> ').strip()
    settings["scale"] = [
        input('Описание значения 0 >> ').strip(),
        input('Описание значения 1 >> ').strip()
    ]
    settings["translation"] = input('Перевод на английский >> ').strip()

    if any(value == "" for value in [
        settings["label"],
        settings["title"],
        settings["question"],
        settings["scale"][0],
        settings["scale"][1],
        settings["translation"]
    ]):
        print('Ошибка! Все поля должны быть заполнены.')
        return

    storage.create_backup()
    tags_work.backup_tag_files()
    tags_work.add_tag_to_data(feature)
    tags[feature] = settings
    tags_work.save_tags(tags)
    tags_work.move_edit_files_to_backup()
    print(f'Тег добавлен: {feature}')
    print('Схема изменилась. Запусти программу снова.')
    raise SystemExit


def request_delete_all_tags() -> None:
    """Запрашивает подтверждение и удаляет все вайб-теги."""
    answer = input("\nУдалить все теги? Введите yes >> ").strip().lower()
    if answer != "yes":
        print('Удаление отменено.')
        return

    storage.create_backup()
    tags_work.backup_tag_files()
    tags_work.delete_all_tags()
    tags_work.move_edit_files_to_backup()
    print("Все вайб-теги удалены.")
    print('Схема изменилась. Запусти программу снова.')
    raise SystemExit


def request_delete_tag() -> None:
    """Запрашивает номер тега и удаляет выбранный тег."""
    tags = tags_work.load_tags()
    show_tags()
    if len(tags) == 0:
        return

    idx_answer = input('\nВведи порядковый номер тега >> ').strip()
    if idx_answer.isdigit() is False:
        print('Ошибка! Нужно ввести номер тега.')
        return

    idx_del = int(idx_answer) - 1
    if idx_del < 0 or idx_del >= len(tags):
        print('Ошибка! Такой тег не найден.')
        return

    feature = list(tags.keys())[idx_del]
    answer = input(f'Удалить тег {feature}? Введи yes >> ').strip().lower()
    if answer != "yes":
        print('Удаление отменено.')
        return

    storage.create_backup()
    tags_work.backup_tag_files()
    tags_work.delete_tag_from_data(feature)
    tags.pop(feature)
    tags_work.save_tags(tags)
    tags_work.move_edit_files_to_backup()
    print(f'Тег удален: {feature}')
    print('Схема изменилась. Запусти программу снова.')
    raise SystemExit
