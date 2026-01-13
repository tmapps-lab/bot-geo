import asyncio
import os
import json
from datetime import datetime
import re
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
    BotCommand,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
from docxtpl import DocxTemplate  # используем docxtpl
from docx2pdf import convert

# ---------- НАСТРОЙКИ ШАБЛОНА ---------- #

TEMPLATE_FILE = "dog_fl.docx"  # имя файла-шаблона .docx
AKT_TEMPLATE_FILE = "akt_fl.docx"
CONFIG_PATH = Path("bot_config.json")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: dict) -> None:
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")


# ---------- ЗАГРУЗКА ТОКЕНА ---------- #

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в .env файле")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
CONFIG = load_config()

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---------- #


def is_valid_date(date_str: str) -> bool:
    """Проверяем, что дата в формате ДД.ММ.ГГГГ и существует."""
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
        return True
    except ValueError:
        return False


def normalize_text(text: str) -> str:
    return text.strip().lower()


def normalize_phone(phone: str) -> str | None:
    """
    Приводит телефон к виду +7XXXXXXXXXX.
    Возвращает None, если номер некорректный.
    """
    cleaned = re.sub(r"[^\d+]", "", phone)

    if cleaned.count("+") > 1 or (cleaned.count("+") == 1 and not cleaned.startswith("+")):
        return None

    if cleaned.startswith("+7") and len(cleaned) == 12 and cleaned[2:].isdigit():
        return cleaned

    if cleaned.startswith("8") and len(cleaned) == 11 and cleaned[1:].isdigit():
        return "+7" + cleaned[1:]

    if cleaned.startswith("7") and len(cleaned) == 11 and cleaned[1:].isdigit():
        return "+" + cleaned

    if cleaned.isdigit() and len(cleaned) == 10:
        return "+7" + cleaned

    return None


async def send_report(text: str):
    report_chat_id = CONFIG.get("report_chat_id")
    report_thread_id = CONFIG.get("report_thread_id")

    if not report_chat_id or report_thread_id is None:
        return

    try:
        await bot.send_message(
            chat_id=report_chat_id,
            text=text,
            message_thread_id=report_thread_id,
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"Ошибка отправки отчёта: {e}")


async def send_file_to_archive(file_path: str, caption: str, message: Message):
    files_chat_id = CONFIG.get("files_chat_id")
    files_thread_id = CONFIG.get("files_thread_id")

    if not files_chat_id or files_thread_id is None:
        return

    try:
        await bot.send_document(
            chat_id=files_chat_id,
            document=FSInputFile(file_path),
            caption=caption,
            message_thread_id=files_thread_id,
        )
    except Exception as e:
        print(f"Ошибка отправки файла в архив: {e}")


async def send_stats_event(data: dict, message: Message):
    stats_chat_id = CONFIG.get("stats_chat_id")
    stats_thread_id = CONFIG.get("stats_thread_id")

    if not stats_chat_id or stats_thread_id is None:
        return

    user = message.from_user
    if user is None:
        return

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Неизвестный пользователь"
    username = f"@{user.username}" if user.username else "нет username"
    doc_type = data.get("doc_type", "contract")
    doc_label = "Договор" if doc_type == "contract" else "Акт"
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    text = (
        f"📊 Новый документ: <b>{doc_label}</b>\n"
        f"🕒 {now_str}\n"
        f"👤 {full_name} ({username})\n"
        f"🆔 <code>{user.id}</code>"
    )

    try:
        await bot.send_message(
            chat_id=stats_chat_id,
            text=text,
            message_thread_id=stats_thread_id,
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"Ошибка отправки статистики: {e}")


@dp.message(Command("set_report_topic"))
async def set_report_topic(message: Message):
    global CONFIG
    CONFIG["report_chat_id"] = message.chat.id
    CONFIG["report_thread_id"] = message.message_thread_id
    save_config(CONFIG)
    await message.answer(
        "✅ Эта тема назначена как тема для *отчётов*.\n"
        "Сюда будут приходить уведомления о запуске бота и создании документов.",
        parse_mode="Markdown",
    )


@dp.message(Command("set_files_topic"))
async def set_files_topic(message: Message):
    global CONFIG
    CONFIG["files_chat_id"] = message.chat.id
    CONFIG["files_thread_id"] = message.message_thread_id
    save_config(CONFIG)
    await message.answer(
        "✅ Эта тема назначена как тема для *файлов*.\n"
        "Сюда будут дублироваться созданные договоры и акты.",
        parse_mode="Markdown",
    )


@dp.message(Command("set_stats_topic"))
async def set_stats_topic(message: Message):
    global CONFIG
    CONFIG["stats_chat_id"] = message.chat.id
    CONFIG["stats_thread_id"] = message.message_thread_id
    save_config(CONFIG)
    await message.answer(
        "✅ Эта тема назначена как тема для *статистики*.\n"
        "Сюда будут приходить сообщения о создании документов.",
        parse_mode="Markdown",
    )


@dp.message(Command("contact"))
async def cmd_contact(message: Message):
    text = (
        "Хочешь такого же бота под свой бизнес? 🚀\n\n"
        "Напиши автору:\n"
        "👉 @stanillarim"
    )
    await message.answer(text)


@dp.message(lambda m: m.text == "💬 Хочу такого же бота")
async def handle_want_bot(message: Message):
    await cmd_contact(message)


def extract_digits_to_int(value: str | None, *, allow_empty: bool = False) -> int:
    """
    Преобразует строку с суммой в целое число.
    Удаляет все символы кроме цифр. Если цифр нет:
    - возвращает 0, если allow_empty=True;
    - выбрасывает ValueError, если allow_empty=False.
    """
    if value is None:
        value = ""
    digits_only = re.sub(r"[^\d]", "", value)

    if digits_only:
        return int(digits_only)

    if allow_empty:
        return 0

    raise ValueError("empty amount")


def generate_contract_doc(data: dict) -> str:
    """
    Создаёт договор на основе шаблона TEMPLATE_FILE и данных из FSM.
    Использует docxtpl (форматирование сохраняется полностью).
    Возвращает путь к созданному .docx файлу.
    """
    template_path = Path(TEMPLATE_FILE)
    if not template_path.exists():
        raise FileNotFoundError(f"Не найден файл шаблона: {TEMPLATE_FILE}")

    output_dir = Path("generated")
    output_dir.mkdir(exist_ok=True)

    client_name = data.get("client_name") or "Клиент"
    safe_name = re.sub(r"[^a-zA-Zа-яА-Я0-9_]+", "_", client_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name_docx = f"dogovor_{safe_name}_{timestamp}.docx"
    file_name_pdf = f"dogovor_{safe_name}_{timestamp}.pdf"
    docx_path = output_dir / file_name_docx
    pdf_path = output_dir / file_name_pdf

    date_end_value = data.get("end_date") or ""
    if date_end_value == "не указана":
        date_end_value = ""

    context = {
        "CLIENT_NAME": data.get("client_name", ""),
        "CLIENT_MOBILE": data.get("phone", ""),
        "ADDRESS_DOG": data.get("address", ""),
        "DATE_DOG": data.get("contract_date", ""),
        "DATE_BEGIN": data.get("start_date", ""),
        "DATE_END": date_end_value,
        "TOTAL_SUM": data.get("total_sum", ""),

        # ПАСПОРТ
        "PASSPORT_SERIES": data.get("passport_series", ""),
        "PASSPORT_NUMBER": data.get("passport_number", ""),
        "PASSPORT_BASE": data.get("passport_base", ""),

        # ОПЛАТЫ (пока не собираем, оставим пустыми — заполним на следующем шаге)
        "PRE_PAY": data.get("pre_pay", ""),
        "FIRST_PAY": data.get("first_pay", ""),
        "SECOND_PAY": data.get("second_pay", ""),
    }

    doc = DocxTemplate(str(template_path))
    doc.render(context)
    doc.save(str(docx_path))

    try:
        convert(str(docx_path), str(pdf_path))
        return str(pdf_path)
    except Exception:
        return str(docx_path)


def generate_act_doc(data: dict) -> str:
    """
    Создаёт акт приёмки по шаблону AKT_TEMPLATE_FILE и данным из FSM.
    Возвращает путь к .docx файлу.
    """
    template_path = Path(AKT_TEMPLATE_FILE)
    if not template_path.exists():
        raise FileNotFoundError(f"Не найден файл шаблона акта: {AKT_TEMPLATE_FILE}")

    output_dir = Path("generated")
    output_dir.mkdir(exist_ok=True)

    client_name = data.get("client_name") or "Клиент"
    safe_name = re.sub(r"[^a-zA-Zа-яА-Я0-9_]+", "_", client_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name_docx = f"akt_{safe_name}_{timestamp}.docx"
    file_name_pdf = f"akt_{safe_name}_{timestamp}.pdf"
    docx_path = output_dir / file_name_docx
    pdf_path = output_dir / file_name_pdf

    context = {
        "DATE_DOG": data.get("contract_date", ""),
        "ADDRESS_DOG": data.get("address", ""),
        "CLIENT_NAME": data.get("client_name", ""),
        "PASSPORT_SERIES": data.get("passport_series", ""),
        "PASSPORT_NUMBER": data.get("passport_number", ""),
        "PASSPORT_BASE": data.get("passport_base", ""),
        "CLIENT_MOBILE": data.get("phone", ""),
    }

    doc = DocxTemplate(str(template_path))
    doc.render(context)
    doc.save(str(docx_path))

    try:
        convert(str(docx_path), str(pdf_path))
        return str(pdf_path)
    except Exception:
        return str(docx_path)


async def recalc_payments(state: FSMContext):
    data = await state.get_data()
    total = extract_digits_to_int(data.get("total_sum"))
    pre = extract_digits_to_int(data.get("pre_pay"), allow_empty=True)
    first_pay_value = data.get("first_pay")
    second_pay_value = data.get("second_pay")

    if second_pay_value:
        if not first_pay_value:
            raise ValueError("Сначала укажи сумму после 1 этапа.")
        first = extract_digits_to_int(first_pay_value, allow_empty=True)
        rest = total - pre - first
        if rest < 0:
            raise ValueError(
                "Новая сумма договора меньше уже указанных оплат. Измени суммы оплат."
            )
        await state.update_data(second_pay=str(rest))
    else:
        rest = total - pre
        if rest < 0:
            raise ValueError(
                "Предоплата больше общей суммы договора. Измени данные."
            )
        await state.update_data(first_pay=str(rest), second_pay="")


# ---------- СОСТОЯНИЯ FSM ---------- #


class ContractForm(StatesGroup):
    waiting_for_client_name = State()
    waiting_for_address = State()
    waiting_for_phone = State()
    waiting_for_contract_date = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_total_sum = State()
    waiting_for_passport_series = State()
    waiting_for_passport_number = State()
    waiting_for_passport_base = State()
    waiting_for_pre_pay = State()
    waiting_for_stage_choice = State()
    waiting_for_first_pay = State()
    waiting_for_summary_confirm = State()
    waiting_for_edit_choice = State()
    waiting_after_file = State()


# ---------- КЛАВИАТУРЫ ---------- #

ACT_BUTTON_TEXT = "📄 Создать акт приёмки"
BACK_TO_START_BUTTON = "Вернуться в начало"
EDIT_PREVIOUS_BUTTON = "Изменить предыдущее значение"
EDIT_FIO_BUTTON = "Изменить ФИО"
SKIP_BUTTON_TEXT = "Пропустить"
CALL_BUTTON_TEXT = "по звонку"
CURRENT_DATE_BUTTON = "Текущая"

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Создать договор")],
        [KeyboardButton(text=ACT_BUTTON_TEXT)],
        [KeyboardButton(text="💬 Хочу такого же бота")],
    ],
    resize_keyboard=True,
)

fio_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=EDIT_FIO_BUTTON)],
        [KeyboardButton(text=ACT_BUTTON_TEXT)],
        [KeyboardButton(text=SKIP_BUTTON_TEXT)],
    ],
    resize_keyboard=True,
)

fio_act_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=EDIT_FIO_BUTTON)],
        [KeyboardButton(text=SKIP_BUTTON_TEXT)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)

nav_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=EDIT_PREVIOUS_BUTTON)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)

start_date_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=CALL_BUTTON_TEXT)],
        [KeyboardButton(text=EDIT_PREVIOUS_BUTTON)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)

end_date_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=SKIP_BUTTON_TEXT)],
        [KeyboardButton(text=EDIT_PREVIOUS_BUTTON)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)

pre_pay_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=SKIP_BUTTON_TEXT)],
        [KeyboardButton(text=EDIT_PREVIOUS_BUTTON)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)

stage_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="1"), KeyboardButton(text="2")],
        [KeyboardButton(text=EDIT_PREVIOUS_BUTTON)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)

contract_date_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=CURRENT_DATE_BUTTON)],
        [KeyboardButton(text=EDIT_PREVIOUS_BUTTON)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)

summary_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Все верно")],
        [KeyboardButton(text="Изменить данные")],
    ],
    resize_keyboard=True,
)

edit_choice_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="ФИО"), KeyboardButton(text="Паспорт")],
        [KeyboardButton(text="Адрес"), KeyboardButton(text="Телефон")],
        [KeyboardButton(text="Даты"), KeyboardButton(text="Сумма"), KeyboardButton(text="Оплаты")],
        [KeyboardButton(text="Начать заново")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

after_file_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Создать новый документ")],
        [KeyboardButton(text="Изменить данные этого документа")],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="contact", description="Хочу такого же бота"),
    ]
    await bot.set_my_commands(commands)

# ---------- ОБРАБОТЧИКИ ---------- #


@dp.message(lambda m: m.text == ACT_BUTTON_TEXT)
async def handle_create_act(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(doc_type="act")
    user = message.from_user
    if user is not None:
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Неизвестный пользователь"
        username = f"@{user.username}" if user.username else "нет username"
        report_text = (
            "📄 Создание акта приёмки\n"
            f"👤 {full_name}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📛 Username: {username}\n"
        )
        await send_report(report_text)
    await message.answer(
        "Создаём акт приёмки.\n\n"
        "Сначала введи ФИО заказчика полностью.",
        reply_markup=nav_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_client_name)


@dp.message(lambda m: m.text == BACK_TO_START_BUTTON)
async def handle_back_to_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Ок, возвращаемся в начало.\n"
        "Выбери, что хочешь сделать:",
        reply_markup=main_keyboard,
    )


@dp.message(lambda m: m.text == EDIT_FIO_BUTTON)
async def handle_edit_fio(message: Message, state: FSMContext):
    await state.set_state(ContractForm.waiting_for_client_name)
    await message.answer(
        "Введи ФИО заказчика заново:",
        reply_markup=nav_keyboard,
    )


@dp.message(lambda m: m.text == EDIT_PREVIOUS_BUTTON)
async def handle_edit_previous(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if not current_state:
        await message.answer(
            "Сейчас нечего редактировать. Нажми «📝 Создать договор», чтобы начать заново.",
            reply_markup=main_keyboard,
        )
        return

    data = await state.get_data()

    if current_state == ContractForm.waiting_for_passport_series.state:
        await state.set_state(ContractForm.waiting_for_client_name)
        await message.answer("Введи ФИО заказчика заново:", reply_markup=nav_keyboard)
        return

    if current_state == ContractForm.waiting_for_passport_number.state:
        await state.set_state(ContractForm.waiting_for_passport_series)
        await message.answer("Введи серию паспорта (4 цифры) заново:", reply_markup=nav_keyboard)
        return

    if current_state == ContractForm.waiting_for_passport_base.state:
        await state.set_state(ContractForm.waiting_for_passport_number)
        await message.answer("Введи номер паспорта (6 цифр) заново:", reply_markup=nav_keyboard)
        return

    if current_state == ContractForm.waiting_for_address.state:
        if any(
            data.get(key)
            for key in ("passport_series", "passport_number", "passport_base")
        ):
            await state.set_state(ContractForm.waiting_for_passport_base)
            await message.answer(
                "Введи, кем и когда выдан паспорт, заново:",
                reply_markup=nav_keyboard,
            )
        else:
            await state.set_state(ContractForm.waiting_for_passport_series)
            await message.answer(
                "Введи серию паспорта (4 цифры) или напиши «пропустить».",
                reply_markup=nav_keyboard,
            )
        return

    if current_state == ContractForm.waiting_for_phone.state:
        await state.set_state(ContractForm.waiting_for_address)
        await message.answer("Введи адрес объекта заново:", reply_markup=nav_keyboard)
        return

    if current_state == ContractForm.waiting_for_contract_date.state:
        await state.set_state(ContractForm.waiting_for_phone)
        await message.answer("Введи номер телефона заказчика заново:", reply_markup=nav_keyboard)
        return

    if current_state == ContractForm.waiting_for_start_date.state:
        await state.set_state(ContractForm.waiting_for_contract_date)
        await message.answer(
            "Введи дату договора заново (ДД.ММ.ГГГГ):",
            reply_markup=nav_keyboard,
        )
        return

    if current_state == ContractForm.waiting_for_end_date.state:
        await state.set_state(ContractForm.waiting_for_start_date)
        await message.answer(
            "Введи дату начала работ заново или используй кнопку «по звонку»:",
            reply_markup=start_date_keyboard,
        )
        return

    if current_state == ContractForm.waiting_for_total_sum.state:
        await state.set_state(ContractForm.waiting_for_end_date)
        await message.answer(
            "Введи дату окончания работ заново или нажми «Пропустить»:",
            reply_markup=end_date_keyboard,
        )
        return

    if current_state == ContractForm.waiting_for_pre_pay.state:
        await state.set_state(ContractForm.waiting_for_total_sum)
        await message.answer("Введи общую сумму договора заново:", reply_markup=nav_keyboard)
        return

    if current_state == ContractForm.waiting_for_stage_choice.state:
        await state.set_state(ContractForm.waiting_for_pre_pay)
        await message.answer("Введи сумму предоплаты заново:", reply_markup=nav_keyboard)
        return

    if current_state == ContractForm.waiting_for_first_pay.state:
        await state.set_state(ContractForm.waiting_for_stage_choice)
        await message.answer(
            "Сколько этапов будет в монтаже? Выбери 1 или 2:",
            reply_markup=stage_keyboard,
        )
        return

    if current_state == ContractForm.waiting_for_client_name.state:
        await message.answer(
            "Мы уже на шаге ввода ФИО. Введи ФИО заказчика:",
            reply_markup=nav_keyboard,
        )
        return

    await message.answer(
        "Сейчас нельзя изменить предыдущее значение на этом шаге.",
        reply_markup=nav_keyboard,
    )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    if user is not None:
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Неизвестный пользователь"
        username = f"@{user.username}" if user.username else "нет username"
        report_text = (
            "🚀 Запуск бота\n"
            f"👤 {full_name}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📛 Username: {username}\n"
        )
        await send_report(report_text)

    await message.answer(
        "Привет! Я бот для создания договоров на натяжные потолки.\n"
        "Выбери, что хочешь сделать: создать договор или акт приёмки.",
        reply_markup=main_keyboard,
    )


@dp.message(lambda msg: msg.text == "📝 Создать договор")
async def cmd_create_contract(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(doc_type="contract")
    user = message.from_user
    if user is not None:
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Неизвестный пользователь"
        username = f"@{user.username}" if user.username else "нет username"
        report_text = (
            "📝 Создание договора\n"
            f"👤 {full_name}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📛 Username: {username}\n"
        )
        await send_report(report_text)
    await message.answer(
        "Окей, давай создадим договор.\n\n"
        "Напиши, пожалуйста, ФИО заказчика полностью.",
        reply_markup=nav_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_client_name)


@dp.message(ContractForm.waiting_for_client_name)
async def process_client_name(message: Message, state: FSMContext):
    client_name = message.text.strip()
    await state.update_data(client_name=client_name)

    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "fio":
        await finish_inline_edit(message, state)
        return

    doc_type = data.get("doc_type", "contract")
    keyboard = fio_keyboard if doc_type != "act" else fio_act_keyboard
    doc_label = "договора" if doc_type != "act" else "акта"

    await message.answer(
        f"Отлично! Записал ФИО:\n<b>{client_name}</b>\n\n"
        f"Теперь можно заполнить паспортные данные для {doc_label} или пропустить этот шаг.\n"
        "Если хочешь указать паспорт, введи серию паспорта (4 цифры).\n"
        "Если не хочешь указывать паспорт, напиши «пропустить».\n"
        "Если нужно изменить ФИО — нажми кнопку ниже.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await state.set_state(ContractForm.waiting_for_passport_series)


@dp.message(ContractForm.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    await state.update_data(address=address)

    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "address":
        await finish_inline_edit(message, state)
        return

    await message.answer(
        "Хорошо! Теперь укажи <b>контактный телефон заказчика</b>.\n\n"
        "Примеры:\n"
        "+79991234567\n"
        "89991234567\n"
        "9991234567",
        parse_mode="HTML",
        reply_markup=nav_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_phone)


@dp.message(ContractForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    raw_phone = message.text.strip()
    phone = normalize_phone(raw_phone)

    if phone is None:
        await message.answer(
            "Похоже, номер телефона указан в неверном формате ❌\n\n"
            "Пожалуйста, введи корректный номер.\n"
            "Примеры:\n"
            "+79991234567\n"
            "89991234567\n"
            "9991234567",
            parse_mode="HTML",
            reply_markup=nav_keyboard,
        )
        return

    await state.update_data(phone=phone)

    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "phone":
        await finish_inline_edit(message, state)
        return

    doc_type = data.get("doc_type", "contract")
    date_label = "дату акта" if doc_type == "act" else "дату договора"

    await message.answer(
        "Телефон записал ✅\n\n"
        f"Теперь укажи <b>{date_label}</b> в формате ДД.ММ.ГГГГ.\n"
        "Например: 03.12.2025",
        parse_mode="HTML",
        reply_markup=contract_date_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_contract_date)


@dp.message(ContractForm.waiting_for_contract_date)
async def process_contract_date(message: Message, state: FSMContext):
    text = message.text.strip()
    text_norm = normalize_text(text)
    data = await state.get_data()
    doc_type = data.get("doc_type", "contract")
    date_word = "договора" if doc_type != "act" else "акта"

    if text_norm in {normalize_text(CURRENT_DATE_BUTTON), "сегодня"}:
        contract_date = datetime.now().strftime("%d.%m.%Y")
    else:
        if not is_valid_date(text):
            await message.answer(
                "Похоже, дата указана в неверном формате.\n"
                f"Пожалуйста, введи дату {date_word} в формате <b>ДД.ММ.ГГГГ</b>.\n"
                "Например: 03.12.2025",
                parse_mode="HTML",
                reply_markup=contract_date_keyboard,
            )
            return
        contract_date = text

    await state.update_data(contract_date=contract_date)

    # если редактируем даты — сразу возвращаемся к сводке
    if data.get("edit_mode") and data.get("edit_field") == "dates":
        await finish_inline_edit(message, state)
        return

    if doc_type == "act":
        await send_summary_and_ask_confirm(message, state)
        return

    await message.answer(
        "Записал дату договора ✅\n\n"
        "Теперь укажи <b>предварительную дату начала работ</b> "
        "в формате ДД.ММ.ГГГГ.\n"
        "Если точной даты нет — напиши <b>«по звонку»</b>.",
        parse_mode="HTML",
        reply_markup=start_date_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_start_date)


@dp.message(ContractForm.waiting_for_start_date)
async def process_start_date(message: Message, state: FSMContext):
    text = message.text.strip()
    text_norm = normalize_text(text)

    if text_norm in {"по звонку", "нет", "не знаю", "неизвестно", "пока нет"}:
        start_date_value = "по звонку"
    else:
        if not is_valid_date(text):
            await message.answer(
                "Похоже, дата начала работ указана неверно.\n"
                "Введи дату в формате <b>ДД.ММ.ГГГГ</b>\n"
                "или напиши <b>«по звонку»</b>, если дата ещё не определена.",
                parse_mode="HTML",
                reply_markup=start_date_keyboard,
            )
            return
        start_date_value = text

    await state.update_data(start_date=start_date_value)

    await message.answer(
        "Дата начала работ записана ✅\n\n"
        "Теперь укажи <b>предварительную дату окончания работ</b> "
        "в формате ДД.ММ.ГГГГ.\n"
        "Если точной даты нет — напиши <b>«нет»</b> или <b>«пропустить»</b>.",
        parse_mode="HTML",
        reply_markup=end_date_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_end_date)


@dp.message(ContractForm.waiting_for_end_date)
async def process_end_date(message: Message, state: FSMContext):
    text = message.text.strip()
    text_norm = normalize_text(text)

    if text_norm in {"нет", "не знаю", "неизвестно", "пока нет", "пропустить"}:
        end_date_value = "не указана"
    else:
        if not is_valid_date(text):
            await message.answer(
                "Похоже, дата окончания работ указана неверно.\n"
                "Введи дату в формате <b>ДД.ММ.ГГГГ</b>\n"
                "или напиши <b>«нет»</b> / <b>«пропустить»</b>, "
                "если дата ещё не определена.",
                parse_mode="HTML",
                reply_markup=end_date_keyboard,
            )
            return
        end_date_value = text

    await state.update_data(end_date=end_date_value)

    await message.answer(
        "Отлично, даты записал ✅\n\n"
        "Теперь укажи, пожалуйста, <b>общую сумму договора</b> цифрами.\n"
        "Например: 55000",
        parse_mode="HTML",
        reply_markup=nav_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_total_sum)


@dp.message(ContractForm.waiting_for_total_sum)
async def process_total_sum(message: Message, state: FSMContext):
    total_sum = message.text.strip()
    await state.update_data(total_sum=total_sum)

    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "sum":
        # пересчёт оплат сохраняем существующие значения stage_count
        try:
            await recalc_payments(state)
        except ValueError as err:
            await message.answer(str(err), reply_markup=nav_keyboard)
            return
        await finish_inline_edit(message, state)
        return

    await message.answer(
        "Записал общую сумму договора ✅\n\n"
        "Теперь укажи сумму предоплаты цифрами.\n"
        "Если предоплаты нет — напиши «нет» или «пропустить».",
        parse_mode="HTML",
        reply_markup=pre_pay_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_pre_pay)


@dp.message(ContractForm.waiting_for_passport_series)
async def process_passport_series(message: Message, state: FSMContext):
    raw_text = message.text.strip()
    normalized = normalize_text(raw_text)

    if normalized == "пропустить":
        await state.update_data(
            passport_series="",
            passport_number="",
            passport_base="",
        )
        data = await state.get_data()
        if data.get("edit_mode") and data.get("edit_field") == "passport":
            await finish_inline_edit(message, state)
        else:
            await message.answer(
                "Хорошо, пропускаем паспортные данные.\n"
                "Теперь напиши <b>адрес объекта</b>.",
                parse_mode="HTML",
                reply_markup=nav_keyboard,
            )
            await state.set_state(ContractForm.waiting_for_address)
        return

    series = raw_text.replace(" ", "")

    if not (series.isdigit() and len(series) == 4):
        await message.answer(
            "Серия паспорта должна состоять из <b>4 цифр</b>.\n"
            "Например: <code>1234</code>\n\n"
            "Попробуй ещё раз:",
            parse_mode="HTML",
            reply_markup=nav_keyboard,
        )
        return

    await state.update_data(passport_series=series)
    await message.answer(
        "Серию паспорта записал ✅\n\n"
        "Теперь введи <b>номер паспорта</b> (6 цифр).\n"
        "Например: <code>567890</code>",
        parse_mode="HTML",
        reply_markup=nav_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_passport_number)


@dp.message(ContractForm.waiting_for_passport_number)
async def process_passport_number(message: Message, state: FSMContext):
    number = message.text.strip().replace(" ", "")

    if not (number.isdigit() and len(number) == 6):
        await message.answer(
            "Номер паспорта должен состоять из <b>6 цифр</b>.\n"
            "Например: <code>567890</code>\n\n"
            "Попробуй ещё раз:",
            parse_mode="HTML",
            reply_markup=nav_keyboard,
        )
        return

    await state.update_data(passport_number=number)

    await message.answer(
        "Номер паспорта записал ✅\n\n"
        "Теперь напиши, <b>кем и когда выдан паспорт</b>.\n"
        "Например:\n"
        "<code>УФМС России по РБ, 01.01.2015</code>",
        parse_mode="HTML",
        reply_markup=nav_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_passport_base)


@dp.message(ContractForm.waiting_for_passport_base)
async def process_passport_base(message: Message, state: FSMContext):
    passport_base = message.text.strip()
    await state.update_data(passport_base=passport_base)

    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "passport":
        await finish_inline_edit(message, state)
        return

    await message.answer(
        "Паспортные данные записаны ✅\n\n"
        "Теперь напиши <b>адрес объекта</b>.",
        parse_mode="HTML",
        reply_markup=nav_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_address)


@dp.message(ContractForm.waiting_for_pre_pay)
async def process_pre_pay(message: Message, state: FSMContext):
    raw_value = message.text.strip()
    normalized_value = normalize_text(raw_value)

    if normalized_value in {"нет", "пропустить", "0"}:
        pre_pay_value = ""
    else:
        cleaned_value = raw_value.replace(" ", "").replace(",", "")
        if not cleaned_value.isdigit():
            await message.answer(
                "Сумму нужно вводить только цифрами. Например: 15000",
                reply_markup=pre_pay_keyboard,
            )
            return
        pre_pay_value = cleaned_value

    await state.update_data(pre_pay=pre_pay_value)

    await message.answer(
        "Предоплату записал ✅\n"
        "Теперь укажи, в сколько этапов будет монтаж: <b>1</b> или <b>2</b>?",
        parse_mode="HTML",
        reply_markup=stage_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_stage_choice)


@dp.message(ContractForm.waiting_for_stage_choice)
async def process_stage_choice(message: Message, state: FSMContext):
    choice = message.text.strip().lower()

    if choice in {"1", "один"}:
        data = await state.get_data()
        try:
            total = extract_digits_to_int(data.get("total_sum"))
        except ValueError:
            await message.answer(
                "Не удалось распознать общую сумму договора.\n"
                "Пожалуйста, введи её ещё раз цифрами.",
                reply_markup=nav_keyboard,
            )
            await state.set_state(ContractForm.waiting_for_total_sum)
            return

        try:
            pre = extract_digits_to_int(data.get("pre_pay"), allow_empty=True)
        except ValueError:
            pre = 0

        rest = total - pre
        if rest < 0:
            await message.answer(
                "Похоже, предоплата больше общей суммы. Проверь данные и введи предоплату ещё раз.",
                reply_markup=nav_keyboard,
            )
            await state.set_state(ContractForm.waiting_for_pre_pay)
            return

        await state.update_data(first_pay=str(rest), second_pay="")
        if data.get("edit_mode") and data.get("edit_field") == "payments":
            await finish_inline_edit(message, state)
        else:
            await send_summary_and_ask_confirm(message, state)
        return

    if choice in {"2", "два"}:
        await message.answer(
            "Хорошо, монтаж в 2 этапа.\n"
            "Укажи сумму оплаты после 1 этапа работ цифрами. Например: 30000.",
            reply_markup=nav_keyboard,
        )
        await state.set_state(ContractForm.waiting_for_first_pay)
        return

    await message.answer(
        "Пожалуйста, введи только <b>1</b> или <b>2</b> — количество этапов монтажа.",
        parse_mode="HTML",
        reply_markup=stage_keyboard,
    )


@dp.message(ContractForm.waiting_for_first_pay)
async def process_first_pay(message: Message, state: FSMContext):
    raw_value = message.text.strip()
    cleaned_value = raw_value.replace(" ", "").replace(",", "")

    if not cleaned_value.isdigit():
        await message.answer(
            "Сумму нужно вводить только цифрами. Например: 30000",
            reply_markup=nav_keyboard,
        )
        return

    await state.update_data(first_pay=cleaned_value)

    data = await state.get_data()

    try:
        total = extract_digits_to_int(data.get("total_sum"))
    except ValueError:
        await message.answer(
            "Не удалось распознать общую сумму договора.\n"
            "Пожалуйста, введи её ещё раз цифрами.",
            reply_markup=nav_keyboard,
        )
        await state.set_state(ContractForm.waiting_for_total_sum)
        return

    try:
        pre = extract_digits_to_int(data.get("pre_pay"), allow_empty=True)
    except ValueError:
        pre = 0

    first = extract_digits_to_int(cleaned_value, allow_empty=True)
    rest = total - pre - first

    if rest < 0:
        await message.answer(
            "Сумма предоплаты и оплаты после 1 этапа больше общей суммы договора.\n"
            "Проверь данные и введи сумму после 1 этапа ещё раз.",
            reply_markup=nav_keyboard,
        )
        return

    await state.update_data(second_pay=str(rest))
    if data.get("edit_mode") and data.get("edit_field") == "payments":
        await finish_inline_edit(message, state)
    else:
        await send_summary_and_ask_confirm(message, state)

async def send_summary_and_ask_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    doc_type = data.get("doc_type", "contract")
    date_label = "Дата акта" if doc_type == "act" else "Дата договора"

    summary_text = (
        "Супер! Я собрал данные для документа:\n\n"
        f"👤 ФИО заказчика: <b>{data.get('client_name')}</b>\n"
        f"🏠 Адрес объекта: <b>{data.get('address')}</b>\n"
        f"📞 Телефон: <b>{data.get('phone')}</b>\n"
        f"📅 {date_label}: <b>{data.get('contract_date')}</b>\n"
    )

    if doc_type != "act":
        summary_text += (
            f"📅 Дата начала работ: <b>{data.get('start_date')}</b>\n"
            f"📅 Дата окончания работ: <b>{data.get('end_date')}</b>\n"
            f"💰 Общая сумма: <b>{data.get('total_sum')} ₽</b>\n\n"
        )
    else:
        summary_text += "\n"

    summary_text += (
        "🪪 Паспорт:\n"
        f"Серия: <b>{data.get('passport_series') or '—'}</b>\n"
        f"Номер: <b>{data.get('passport_number') or '—'}</b>\n"
        f"Выдан: <b>{data.get('passport_base') or '—'}</b>\n\n"
    )

    if doc_type != "act":
        summary_text += (
            "💵 Оплаты:\n"
            f"Предоплата: <b>{data.get('pre_pay') or '—'} ₽</b>\n"
            f"После 1 этапа: <b>{data.get('first_pay') or '—'} ₽</b>\n"
            f"После 2 этапа: <b>{data.get('second_pay') or '—'} ₽</b>\n\n"
        )

    summary_text += "Проверь данные и подтверди👇"

    await message.answer(
        summary_text,
        parse_mode="HTML",
        reply_markup=summary_keyboard,
    )
    await state.set_state(ContractForm.waiting_for_summary_confirm)


async def finish_inline_edit(message: Message, state: FSMContext):
    await state.update_data(edit_mode=False, edit_field=None)
    await send_summary_and_ask_confirm(message, state)


@dp.message(ContractForm.waiting_for_summary_confirm)
async def process_summary_confirm(message: Message, state: FSMContext):
    choice = normalize_text(message.text)

    if choice in {"все верно", "всё верно"}:
        data = await state.get_data()
        doc_type = data.get("doc_type", "contract")
        try:
            if doc_type == "act":
                file_path = generate_act_doc(data)
                caption = "Готовый акт сдачи-приёмки выполненных работ."
            else:
                file_path = generate_contract_doc(data)
                caption = "Готовый договор на установку натяжных потолков."
        except Exception as e:
            await message.answer(
                "Произошла ошибка при генерации документа 😔\n"
                f"Текст ошибки: <code>{e}</code>\n"
                "Попробуй ещё раз или измени данные.",
                parse_mode="HTML",
                reply_markup=summary_keyboard,
            )
            return

        doc_file = FSInputFile(file_path)

        await message.answer_document(
            doc_file,
            caption=caption,
            reply_markup=main_keyboard,
        )

        await send_file_to_archive(file_path, caption, message)
        await send_stats_event(data, message)

        await message.answer(
            "Файл документа отправлен ✅\n\n"
            "Ты можешь:\n"
            "• создать новый документ;\n"
            "• изменить данные этого документа и получить обновлённый файл;\n"
            "• вернуться в начало.",
            reply_markup=after_file_keyboard,
        )
        await state.set_state(ContractForm.waiting_after_file)
        return

    if choice == "изменить данные":
        await state.update_data(edit_mode=False, edit_field=None)
        await message.answer(
            "Выбери, что нужно изменить:",
            reply_markup=edit_choice_keyboard,
        )
        await state.set_state(ContractForm.waiting_for_edit_choice)
        return

    await message.answer(
        "Используй кнопки «Все верно» или «Изменить данные».",
        reply_markup=summary_keyboard,
    )


@dp.message(ContractForm.waiting_for_edit_choice)
async def process_edit_choice(message: Message, state: FSMContext):
    choice = normalize_text(message.text)
    data = await state.get_data()

    if choice in {"начать заново", "начать сначала"}:
        await state.clear()
        await message.answer(
            "Начнём сначала. Выбери действие:",
            reply_markup=main_keyboard,
        )
        return

    if choice == "фио":
        current = data.get("client_name") or "не указано"
        await state.update_data(edit_mode=True, edit_field="fio")
        await state.set_state(ContractForm.waiting_for_client_name)
        await message.answer(
            f"Текущее ФИО: <b>{current}</b>\nВведи новое ФИО:",
            parse_mode="HTML",
            reply_markup=nav_keyboard,
        )
        return

    if choice == "паспорт":
        await state.update_data(edit_mode=True, edit_field="passport")
        await state.set_state(ContractForm.waiting_for_passport_series)
        await message.answer(
            "Введи серию паспорта (4 цифры) или напиши «пропустить»:",
            reply_markup=nav_keyboard,
        )
        return

    if choice == "адрес":
        current = data.get("address") or "не указан"
        await state.update_data(edit_mode=True, edit_field="address")
        await state.set_state(ContractForm.waiting_for_address)
        await message.answer(
            f"Текущий адрес: <b>{current}</b>\nВведи новый адрес:",
            parse_mode="HTML",
            reply_markup=nav_keyboard,
        )
        return

    if choice == "телефон":
        current = data.get("phone") or "не указан"
        await state.update_data(edit_mode=True, edit_field="phone")
        await state.set_state(ContractForm.waiting_for_phone)
        await message.answer(
            f"Текущий телефон: <b>{current}</b>\nВведи новый номер:",
            parse_mode="HTML",
            reply_markup=nav_keyboard,
        )
        return

    if choice == "даты":
        current = data.get("contract_date") or "не указана"
        await state.update_data(edit_mode=True, edit_field="dates")
        await state.set_state(ContractForm.waiting_for_contract_date)
        await message.answer(
            f"Текущая дата договора: <b>{current}</b>\nВведи новую дату или нажми «{CURRENT_DATE_BUTTON}»:",
            parse_mode="HTML",
            reply_markup=contract_date_keyboard,
        )
        return

    if choice == "сумма":
        current = data.get("total_sum") or "не указана"
        await state.update_data(edit_mode=True, edit_field="sum")
        await state.set_state(ContractForm.waiting_for_total_sum)
        await message.answer(
            f"Текущая общая сумма: <b>{current}</b>\nВведи новую сумму:",
            parse_mode="HTML",
            reply_markup=nav_keyboard,
        )
        return

    if choice == "оплаты":
        await state.update_data(edit_mode=True, edit_field="payments")
        await state.set_state(ContractForm.waiting_for_pre_pay)
        await message.answer(
            "Введи сумму предоплаты заново (можно написать «нет» или «пропустить»):",
            reply_markup=pre_pay_keyboard,
        )
        return

    if choice == "отмена":
        await send_summary_and_ask_confirm(message, state)
        return

    if message.text == BACK_TO_START_BUTTON:
        await handle_back_to_start(message, state)
        return

    await message.answer(
        "Пожалуйста, выбери вариант из списка выше.",
        reply_markup=edit_choice_keyboard,
    )


@dp.message(ContractForm.waiting_after_file)
async def process_after_file(message: Message, state: FSMContext):
    choice = normalize_text(message.text)

    if choice in {"создать новый документ"}:
        await state.clear()
        await message.answer(
            "Что создаём?",
            reply_markup=main_keyboard,
        )
        return

    if choice in {"изменить данные этого документа", "изменить данные"}:
        await message.answer(
            "Выбери, что нужно изменить:",
            reply_markup=edit_choice_keyboard,
        )
        await state.set_state(ContractForm.waiting_for_edit_choice)
        return

    if message.text == BACK_TO_START_BUTTON:
        await handle_back_to_start(message, state)
        return

    await message.answer(
        "Используй кнопки ниже, чтобы выбрать действие.",
        reply_markup=after_file_keyboard,
    )


async def main():
    await set_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
fio_act_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=EDIT_FIO_BUTTON)],
        [KeyboardButton(text=SKIP_BUTTON_TEXT)],
        [KeyboardButton(text=BACK_TO_START_BUTTON)],
    ],
    resize_keyboard=True,
)
