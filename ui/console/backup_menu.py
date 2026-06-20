"""Показывает backup-файлы датасета и восстанавливает выбранный backup."""

from storage import files as storage_files


def open_backup_menu() -> None:
    """Открывает меню выбора backup-файла для восстановления датасета."""
    backups = storage_files.get_latest_backups(10)
    if len(backups) == 0:
        print("Backup-файлы не найдены.")
        return

    print("\nБЭКАП ДАТАСЕТА\n")
    for idx, file_path in enumerate(backups, start=1):
        print(f"{idx}) {storage_files.get_backup_label(file_path)}")
    print("0) Назад")

    answer = input("\nВыбери backup для загрузки >> ").strip()
    if answer == "0":
        return
    if answer.isdigit() is False:
        print("Ошибка! Нужно ввести номер backup.")
        return

    idx = int(answer) - 1
    if idx < 0 or idx >= len(backups):
        print("Ошибка! Такой backup не найден.")
        return

    file_path = backups[idx]
    confirm = input(f"Загрузить backup {file_path.name}? Введи yes >> ").strip().lower()
    if confirm != "yes":
        print("Загрузка backup отменена.")
        return

    try:
        records_count = storage_files.restore_backup(file_path)
    except ValueError as error:
        print(f"Ошибка backup: {error}")
        return

    print(f"Backup загружен: {file_path.name}")
    print(f"Записей в датасете: {records_count}")
