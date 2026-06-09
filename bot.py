import asyncio
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "8815800506:AAFpUXbyqAj7Cm-f_chFoNLN9kq-BcZF8uE"

TABLE_NAME = "Остатки Чинор"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not GOOGLE_CREDENTIALS:
    raise ValueError("GOOGLE_CREDENTIALS не найден")

creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(TABLE_NAME).sheet1

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_data = {}

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить остаток")],
        [KeyboardButton(text="🔍 Найти по цвету"), KeyboardButton(text="📐 Найти по размеру")],
        [KeyboardButton(text="📦 Все остатки"), KeyboardButton(text="❌ Списать остаток")],
        [KeyboardButton(text="📊 Статистика")]
    ],
    resize_keyboard=True
)


def area_m2(length, width, qty):
    value = (int(length) * int(width) * int(qty)) / 1_000_000
    return round(value, 4)


def area_to_text(value):
    return str(value).replace(".", ",")


def area_to_float(value):
    if value is None or value == "":
        return 0
    return float(str(value).replace(",", "."))


def get_rows():
    headers = sheet.row_values(1)
    values = sheet.get_all_values()[1:]
    rows = []

    for row in values:
        item = {}
        for i, header in enumerate(headers):
            item[header] = row[i] if i < len(row) else ""
        rows.append(item)

    return rows


def is_active(row):
    return str(row.get("Статус", "")).strip().lower() == "есть"


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Бот остатков Чинор запущен.\n\nВыберите действие:",
        reply_markup=main_keyboard
    )


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text == "➕ Добавить остаток":
        user_data[user_id] = {"step": "color"}
        await message.answer("Введите цвет или код цвета:")
        return

    if text == "🔍 Найти по цвету":
        user_data[user_id] = {"step": "find_color"}
        await message.answer("Введите цвет или код цвета:")
        return

    if text == "📐 Найти по размеру":
        user_data[user_id] = {"step": "find_length"}
        await message.answer("Введите нужную длину в мм:")
        return

    if text == "📦 Все остатки":
        rows = get_rows()
        active = [r for r in rows if is_active(r)]

        if not active:
            await message.answer("Активных остатков нет.", reply_markup=main_keyboard)
            return

        answer = "📦 Все активные остатки:\n\n"

        for r in active[:30]:
            answer += (
                f"ID: {r['ID']}\n"
                f"{r['Цвет']}, {r['Толщина']} мм\n"
                f"{r['Длина']}×{r['Ширина']}, кол-во: {r['Кол-во']}\n"
                f"Место: {r['Место']}\n"
                f"Площадь: {r['Площадь м²']} м²\n\n"
            )

        await message.answer(answer, reply_markup=main_keyboard)
        return

    if text == "❌ Списать остаток":
        user_data[user_id] = {"step": "delete_id"}
        await message.answer("Введите ID остатка:")
        return

    if text == "📊 Статистика":
        rows = get_rows()
        active = [r for r in rows if is_active(r)]

        total_positions = len(active)
        total_qty = sum(int(r["Кол-во"]) for r in active)
        total_area = sum(area_to_float(r["Площадь м²"]) for r in active)

        await message.answer(
            f"📊 Статистика остатков:\n\n"
            f"Активных позиций: {total_positions}\n"
            f"Общее количество деталей: {total_qty}\n"
            f"Общая площадь: {area_to_text(round(total_area, 4))} м²",
            reply_markup=main_keyboard
        )
        return

    if user_id not in user_data:
        await message.answer("Выберите действие кнопкой.", reply_markup=main_keyboard)
        return

    data = user_data[user_id]

    if data["step"] == "color":
        data["color"] = text
        data["step"] = "thickness"
        await message.answer("Введите толщину, например 16 или 18:")

    elif data["step"] == "thickness":
        if not text.isdigit():
            await message.answer("Толщина должна быть числом.")
            return
        data["thickness"] = text
        data["step"] = "length"
        await message.answer("Введите длину в мм:")

    elif data["step"] == "length":
        if not text.isdigit():
            await message.answer("Длина должна быть числом.")
            return
        data["length"] = text
        data["step"] = "width"
        await message.answer("Введите ширину в мм:")

    elif data["step"] == "width":
        if not text.isdigit():
            await message.answer("Ширина должна быть числом.")
            return
        data["width"] = text
        data["step"] = "qty"
        await message.answer("Введите количество:")

    elif data["step"] == "qty":
        if not text.isdigit():
            await message.answer("Количество должно быть числом.")
            return
        data["qty"] = text
        data["step"] = "place"
        await message.answer("Введите место хранения, например A1:")

    elif data["step"] == "place":
        data["place"] = text

        new_id = len(sheet.get_all_values())
        area = area_m2(data["length"], data["width"], data["qty"])
        area_text = area_to_text(area)

        row = [
            new_id,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            data["color"],
            data["thickness"],
            data["length"],
            data["width"],
            data["qty"],
            data["place"],
            area_text,
            "Есть"
        ]

        sheet.append_row(row)

        await message.answer(
            f"✅ Остаток сохранён\n\n"
            f"ID: {new_id}\n"
            f"Цвет: {data['color']}\n"
            f"Размер: {data['length']}×{data['width']}\n"
            f"Толщина: {data['thickness']} мм\n"
            f"Кол-во: {data['qty']}\n"
            f"Место: {data['place']}\n"
            f"Площадь: {area_text} м²",
            reply_markup=main_keyboard
        )

        del user_data[user_id]

    elif data["step"] == "find_color":
        color = text.lower()
        rows = get_rows()

        results = [
            r for r in rows
            if color in str(r["Цвет"]).lower() and is_active(r)
        ]

        if not results:
            await message.answer("Ничего не найдено.", reply_markup=main_keyboard)
        else:
            answer = "🔍 Найдено:\n\n"
            for r in results[:20]:
                answer += (
                    f"ID: {r['ID']}\n"
                    f"{r['Цвет']}, {r['Толщина']} мм\n"
                    f"{r['Длина']}×{r['Ширина']}, кол-во: {r['Кол-во']}\n"
                    f"Место: {r['Место']}\n"
                    f"Площадь: {r['Площадь м²']} м²\n\n"
                )
            await message.answer(answer, reply_markup=main_keyboard)

        del user_data[user_id]

    elif data["step"] == "find_length":
        if not text.isdigit():
            await message.answer("Длина должна быть числом.")
            return
        data["need_length"] = int(text)
        data["step"] = "find_width"
        await message.answer("Введите нужную ширину в мм:")

    elif data["step"] == "find_width":
        if not text.isdigit():
            await message.answer("Ширина должна быть числом.")
            return

        need_length = data["need_length"]
        need_width = int(text)

        rows = get_rows()
        results = []

        for r in rows:
            if not is_active(r):
                continue

            length = int(r["Длина"])
            width = int(r["Ширина"])

            fits_normal = length >= need_length and width >= need_width
            fits_rotated = length >= need_width and width >= need_length

            if fits_normal or fits_rotated:
                results.append(r)

        if not results:
            await message.answer("Подходящих остатков нет.", reply_markup=main_keyboard)
        else:
            answer = f"📐 Подходит под {need_length}×{need_width}:\n\n"
            for r in results[:20]:
                answer += (
                    f"ID: {r['ID']}\n"
                    f"{r['Цвет']}, {r['Толщина']} мм\n"
                    f"{r['Длина']}×{r['Ширина']}, кол-во: {r['Кол-во']}\n"
                    f"Место: {r['Место']}\n"
                    f"Площадь: {r['Площадь м²']} м²\n\n"
                )
            await message.answer(answer, reply_markup=main_keyboard)

        del user_data[user_id]

    elif data["step"] == "delete_id":
        if not text.isdigit():
            await message.answer("ID должен быть числом.")
            return

        target_id = text
        values = sheet.get_all_values()
        found = False

        for index, row in enumerate(values[1:], start=2):
            if row[0] == target_id:
                sheet.update_cell(index, 10, "Использован")
                found = True
                break

        if found:
            await message.answer(f"❌ Остаток ID {target_id} списан.", reply_markup=main_keyboard)
        else:
            await message.answer("Такой ID не найден.", reply_markup=main_keyboard)

        del user_data[user_id]


async def main():
    print("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
