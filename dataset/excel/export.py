"""Export watched dataset to Excel."""

import os

from openpyxl import Workbook

from config import constant
from dataset.excel.rows import apply_header_column_widths, build_row
from dataset.excel.schema import SHEET_NAME, is_excel_schema_actual, move_excel_to_backup
from storage import data as storage_data


def export_dataset_to_excel(overwrite: bool = False) -> bool:
    """Выгружает датасет в Excel."""
    data = storage_data.load_dataset()
    meta = storage_data.load_meta()
    os.makedirs(constant.DIR_TXT, exist_ok=True)

    if overwrite is False and os.path.exists(constant.EDIT_EXCEL):
        try:
            if is_excel_schema_actual():
                print(f"Excel для редактирования уже существует: {constant.EDIT_EXCEL}")
                print("Открываю существующий файл без перезаписи.")
                return True
        except PermissionError:
            print(f"Не удалось прочитать Excel: {constant.EDIT_EXCEL}")
            print("Закрой файл в Excel и попробуй открыть датасет снова.")
            return False

        print("Схема тегов изменилась. Пересоздаю Excel по актуальным колонкам.")
        if move_excel_to_backup() is False:
            return False

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = SHEET_NAME
    worksheet.append(constant.CSV_FIELDS)

    for movie in data.values():
        worksheet.append(build_row(movie))

    if len(data) == 0 and len(meta) > 0:
        for movie in meta.values():
            row = []
            for feature in constant.MAIN_INFO:
                row.append(movie["main_info"][feature])
            for feature in constant.RAW_SCORES:
                row.append(movie["raw_scores"][feature])
            row.extend([""] * len(constant.TAGS_VIBE))
            row.extend([""] * len(constant.GENRE))
            worksheet.append(row)

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    apply_header_column_widths(worksheet)

    try:
        workbook.save(constant.EDIT_EXCEL)
    except PermissionError:
        print(f"Не удалось открыть Excel для записи: {constant.EDIT_EXCEL}")
        print("Закрой файл в Excel и попробуй снова.")
        return False

    print(f"Excel для редактирования сохранен: {constant.EDIT_EXCEL}")
    return True
