
from __future__ import annotations

from datetime import datetime
import logging
import html
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup

try:
    from .config import load_admin_user_ids, load_config, save_config
    from .documents.render import render_act, render_contract, render_supplement
    from .reporting import send_doc_start_report, send_file_report, send_start_report
    from .states import ContractStates, SupplementStates
except ImportError:  # pragma: no cover - allow running as script
    from config import load_admin_user_ids, load_config, save_config
    from documents.render import render_act, render_contract, render_supplement
    from reporting import send_doc_start_report, send_file_report, send_start_report
    from states import ContractStates, SupplementStates

router = Router()
logger = logging.getLogger(__name__)

MAIN_MENU_CONTRACT = "📝 Договор"
MAIN_MENU_ACT = "📄 Акт"
MAIN_MENU_SUPPLEMENT = "➕ Доп. соглашение"
MAIN_MENU_BUTTON = "🏠 Главное меню"

CONFIRM_BUTTON = "✅ Сформировать"
EDIT_BUTTON = "✏️ Изменить данные"
RESTART_BUTTON = "Начать заново"
BACK_BUTTON = "Изменить предыдущее значение"
EDIT_BACK_BUTTON = "Назад к проверке"

SKIP_BUTTON = "Пропустить"
TODAY_BUTTON = "Текущая дата"
CALL_BUTTON = "По звонку"

STAGE_ONE_BUTTON = "1"
STAGE_TWO_BUTTON = "2"

EDIT_FIO = "ФИО"
EDIT_ADDRESS = "Адрес объекта"
EDIT_PHONE = "Телефон"
EDIT_CONTRACT_DATE = "Дата договора"
EDIT_ACT_DATE = "Дата акта"
EDIT_START_DATE = "Дата начала"
EDIT_END_DATE = "Дата окончания"
EDIT_TOTAL_SUM = "Сумма договора"
EDIT_PASSPORT_SERIES = "Паспорт серия"
EDIT_PASSPORT_NUMBER = "Паспорт номер"
EDIT_PASSPORT_BASE = "Паспорт выдан"
EDIT_PREPAY = "Предоплата"
EDIT_FIRST_PAY = "Платеж 1"
EDIT_SECOND_PAY = "Платеж 2"
EDIT_CONTRACT_NUMBER = "Номер договора"
EDIT_SUPPLEMENT_DATE = "Дата доп. соглашения"
EDIT_SUPPLEMENT_TEXT = "Текст доп. соглашения"

DOC_TYPE_LABELS = {
    "contract": "Договор",
    "act": "Акт",
    "supplement": "Доп. соглашение",
}


def build_keyboard(
    rows: list[list[str]],
    *,
    include_back: bool = True,
    include_restart: bool = True,
    include_menu: bool = True,
) -> ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]] = []
    for row in rows:
        keyboard.append([KeyboardButton(text=text) for text in row])
    if include_back:
        keyboard.append([KeyboardButton(text=BACK_BUTTON)])
    if include_restart:
        keyboard.append([KeyboardButton(text=RESTART_BUTTON)])
    if include_menu:
        keyboard.append([KeyboardButton(text=MAIN_MENU_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def input_keyboard(*, include_back: bool = True) -> ReplyKeyboardMarkup:
    return build_keyboard([], include_back=include_back)


def date_keyboard(*, include_back: bool = True) -> ReplyKeyboardMarkup:
    return build_keyboard([[TODAY_BUTTON]], include_back=include_back)


def start_date_keyboard(*, include_back: bool = True) -> ReplyKeyboardMarkup:
    return build_keyboard([[CALL_BUTTON]], include_back=include_back)


def skip_keyboard(*, include_back: bool = True) -> ReplyKeyboardMarkup:
    return build_keyboard([[SKIP_BUTTON]], include_back=include_back)


def stage_keyboard(*, include_back: bool = True) -> ReplyKeyboardMarkup:
    return build_keyboard([[STAGE_ONE_BUTTON, STAGE_TWO_BUTTON]], include_back=include_back)


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=MAIN_MENU_CONTRACT)],
        [KeyboardButton(text=MAIN_MENU_ACT)],
        [KeyboardButton(text=MAIN_MENU_SUPPLEMENT)],
    ],
    resize_keyboard=True,
)

confirm_keyboard = build_keyboard(
    [[CONFIRM_BUTTON], [EDIT_BUTTON]],
    include_back=True,
    include_restart=True,
    include_menu=True,
)

def normalize_phone(phone: str) -> str | None:
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


def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
        return True
    except ValueError:
        return False


def extract_digits(value: str) -> str | None:
    digits = re.sub(r"[^\d]", "", value)
    return digits or None


def extract_digits_to_int(value: str | None, allow_empty: bool = False) -> int:
    if value is None:
        value = ""
    digits_only = re.sub(r"[^\d]", "", value)
    if digits_only:
        return int(digits_only)
    if allow_empty:
        return 0
    raise ValueError("empty amount")


def normalize_skip(value: str) -> str:
    return value.strip().lower()


def escape_html(value: str | None) -> str:
    return html.escape(value or "")


def get_state_sequence(doc_type: str) -> list[str]:
    if doc_type == "supplement":
        return [
            SupplementStates.waiting_for_contract_number.state,
            SupplementStates.waiting_for_supplement_date.state,
            SupplementStates.waiting_for_text.state,
            SupplementStates.waiting_for_summary_confirm.state,
        ]
    if doc_type == "act":
        return [
            ContractStates.waiting_for_client_name.state,
            ContractStates.waiting_for_address.state,
            ContractStates.waiting_for_phone.state,
            ContractStates.waiting_for_contract_date.state,
            ContractStates.waiting_for_passport_series.state,
            ContractStates.waiting_for_passport_number.state,
            ContractStates.waiting_for_passport_base.state,
            ContractStates.waiting_for_summary_confirm.state,
        ]
    return [
        ContractStates.waiting_for_client_name.state,
        ContractStates.waiting_for_address.state,
        ContractStates.waiting_for_phone.state,
        ContractStates.waiting_for_contract_date.state,
        ContractStates.waiting_for_start_date.state,
        ContractStates.waiting_for_end_date.state,
        ContractStates.waiting_for_total_sum.state,
        ContractStates.waiting_for_passport_series.state,
        ContractStates.waiting_for_passport_number.state,
        ContractStates.waiting_for_passport_base.state,
        ContractStates.waiting_for_pre_pay.state,
        ContractStates.waiting_for_stage_choice.state,
        ContractStates.waiting_for_first_pay.state,
        ContractStates.waiting_for_second_pay.state,
        ContractStates.waiting_for_summary_confirm.state,
    ]


def state_from_value(state_value: str):
    mapping = {
        ContractStates.waiting_for_client_name.state: ContractStates.waiting_for_client_name,
        ContractStates.waiting_for_address.state: ContractStates.waiting_for_address,
        ContractStates.waiting_for_phone.state: ContractStates.waiting_for_phone,
        ContractStates.waiting_for_contract_date.state: ContractStates.waiting_for_contract_date,
        ContractStates.waiting_for_start_date.state: ContractStates.waiting_for_start_date,
        ContractStates.waiting_for_end_date.state: ContractStates.waiting_for_end_date,
        ContractStates.waiting_for_total_sum.state: ContractStates.waiting_for_total_sum,
        ContractStates.waiting_for_passport_series.state: ContractStates.waiting_for_passport_series,
        ContractStates.waiting_for_passport_number.state: ContractStates.waiting_for_passport_number,
        ContractStates.waiting_for_passport_base.state: ContractStates.waiting_for_passport_base,
        ContractStates.waiting_for_pre_pay.state: ContractStates.waiting_for_pre_pay,
        ContractStates.waiting_for_stage_choice.state: ContractStates.waiting_for_stage_choice,
        ContractStates.waiting_for_first_pay.state: ContractStates.waiting_for_first_pay,
        ContractStates.waiting_for_second_pay.state: ContractStates.waiting_for_second_pay,
        ContractStates.waiting_for_summary_confirm.state: ContractStates.waiting_for_summary_confirm,
        ContractStates.waiting_for_edit_choice.state: ContractStates.waiting_for_edit_choice,
        SupplementStates.waiting_for_contract_number.state: SupplementStates.waiting_for_contract_number,
        SupplementStates.waiting_for_supplement_date.state: SupplementStates.waiting_for_supplement_date,
        SupplementStates.waiting_for_text.state: SupplementStates.waiting_for_text,
        SupplementStates.waiting_for_summary_confirm.state: SupplementStates.waiting_for_summary_confirm,
        SupplementStates.waiting_for_edit_choice.state: SupplementStates.waiting_for_edit_choice,
    }
    return mapping.get(state_value)


def build_file_caption(data: dict, user) -> str:
    doc_type = data.get("doc_type", "contract")
    doc_label = DOC_TYPE_LABELS.get(doc_type, "Документ")
    address = data.get("address") or "нет данных"
    phone = data.get("phone") or "нет данных"

    client_name = data.get("client_name")
    if not client_name:
        client_name = "нет данных"

    username = f"@{user.username}" if getattr(user, "username", None) else "нет username"

    return (
        f"📄 {doc_label}\n"
        f"Адрес: {address}\n"
        f"Телефон: {phone}\n"
        f"Клиент: {client_name}\n"
        f"Сделал {doc_label.lower()}: {username}\n"
        f"UserID: {user.id}"
    )


async def is_authorized_admin(message: Message) -> bool:
    user = message.from_user
    if user is None:
        return False

    allowed_ids = load_admin_user_ids()
    if allowed_ids and user.id in allowed_ids:
        return True

    try:
        member = await message.bot.get_chat_member(message.chat.id, user.id)
    except Exception:  # noqa: BLE001 - external API
        logger.exception("Failed to fetch chat member for admin check.")
        return False

    return member.status in {"administrator", "creator"}


async def ensure_topic_command(message: Message) -> bool:
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("Команда доступна только в группе/супергруппе.")
        return False
    if not message.message_thread_id:
        await message.answer("Команду нужно отправить внутри темы (форум).")
        return False
    if not await is_authorized_admin(message):
        await message.answer("Недостаточно прав для настройки.")
        return False
    return True


async def prompt_for_state(message: Message, state_value: str, data: dict) -> None:
    if state_value == ContractStates.waiting_for_client_name.state:
        await message.answer("Введите ФИО заказчика:", reply_markup=input_keyboard(include_back=False))
        return
    if state_value == ContractStates.waiting_for_address.state:
        await message.answer("Введите адрес объекта:", reply_markup=input_keyboard())
        return
    if state_value == ContractStates.waiting_for_phone.state:
        await message.answer("Введите телефон заказчика:", reply_markup=input_keyboard())
        return
    if state_value == ContractStates.waiting_for_contract_date.state:
        await message.answer(
            "Введите дату договора/акта в формате ДД.ММ.ГГГГ (или нажмите «Текущая дата»):",
            reply_markup=date_keyboard(),
        )
        return
    if state_value == ContractStates.waiting_for_start_date.state:
        await message.answer("Введите дату начала работ (или нажмите «По звонку»):", reply_markup=start_date_keyboard())
        return
    if state_value == ContractStates.waiting_for_end_date.state:
        await message.answer("Введите дату окончания работ (или «Пропустить»):", reply_markup=skip_keyboard())
        return
    if state_value == ContractStates.waiting_for_total_sum.state:
        await message.answer("Введите общую сумму договора (только цифры):", reply_markup=input_keyboard())
        return
    if state_value == ContractStates.waiting_for_passport_series.state:
        await message.answer("Введите серию паспорта (4 цифры) или «Пропустить»:", reply_markup=skip_keyboard())
        return
    if state_value == ContractStates.waiting_for_passport_number.state:
        await message.answer("Введите номер паспорта (6 цифр) или «Пропустить»:", reply_markup=skip_keyboard())
        return
    if state_value == ContractStates.waiting_for_passport_base.state:
        await message.answer("Введите кем и когда выдан паспорт (или «Пропустить»):", reply_markup=skip_keyboard())
        return
    if state_value == ContractStates.waiting_for_pre_pay.state:
        await message.answer("Введите сумму предоплаты (или «Пропустить»):", reply_markup=skip_keyboard())
        return
    if state_value == ContractStates.waiting_for_stage_choice.state:
        await message.answer("Сколько этапов оплаты? Введите 1 или 2:", reply_markup=stage_keyboard())
        return
    if state_value == ContractStates.waiting_for_first_pay.state:
        await message.answer("Введите сумму первого платежа:", reply_markup=input_keyboard())
        return
    if state_value == ContractStates.waiting_for_second_pay.state:
        await message.answer("Введите сумму второго платежа:", reply_markup=input_keyboard())
        return
    if state_value == SupplementStates.waiting_for_contract_number.state:
        await message.answer("Введите номер договора:", reply_markup=input_keyboard(include_back=False))
        return
    if state_value == SupplementStates.waiting_for_supplement_date.state:
        await message.answer(
            "Введите дату доп. соглашения в формате ДД.ММ.ГГГГ (или нажмите «Текущая дата»):",
            reply_markup=date_keyboard(),
        )
        return
    if state_value == SupplementStates.waiting_for_text.state:
        await message.answer(
            "Введите текст доп. соглашения. Можно несколькими сообщениями. Для завершения отправьте /done.",
            reply_markup=input_keyboard(),
        )
        return
    await message.answer("Выберите документ:", reply_markup=main_keyboard)


async def handle_back(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if not current_state:
        await message.answer("Выберите документ:", reply_markup=main_keyboard)
        return
    data = await state.get_data()
    doc_type = data.get("doc_type", "contract")
    sequence = get_state_sequence(doc_type)
    if current_state not in sequence:
        await prompt_for_state(message, current_state, data)
        return
    index = sequence.index(current_state)
    if index == 0:
        await message.answer("Предыдущее значение отсутствует.", reply_markup=main_keyboard)
        return
    prev_state_value = sequence[index - 1]
    prev_state = state_from_value(prev_state_value)
    if prev_state is None:
        await message.answer("Предыдущее значение отсутствует.", reply_markup=main_keyboard)
        return
    await state.set_state(prev_state)
    await prompt_for_state(message, prev_state_value, data)


def edit_keyboard_for(doc_type: str) -> ReplyKeyboardMarkup:
    if doc_type == "supplement":
        rows = [
            [EDIT_CONTRACT_NUMBER, EDIT_SUPPLEMENT_DATE],
            [EDIT_SUPPLEMENT_TEXT],
            [EDIT_BACK_BUTTON],
        ]
        return build_keyboard(rows, include_back=False, include_restart=True, include_menu=True)
    if doc_type == "act":
        rows = [
            [EDIT_FIO, EDIT_ADDRESS],
            [EDIT_PHONE, EDIT_ACT_DATE],
            [EDIT_PASSPORT_SERIES, EDIT_PASSPORT_NUMBER],
            [EDIT_PASSPORT_BASE],
            [EDIT_BACK_BUTTON],
        ]
        return build_keyboard(rows, include_back=False, include_restart=True, include_menu=True)
    rows = [
        [EDIT_FIO, EDIT_ADDRESS],
        [EDIT_PHONE, EDIT_CONTRACT_DATE],
        [EDIT_START_DATE, EDIT_END_DATE],
        [EDIT_TOTAL_SUM],
        [EDIT_PASSPORT_SERIES, EDIT_PASSPORT_NUMBER],
        [EDIT_PASSPORT_BASE],
        [EDIT_PREPAY, EDIT_FIRST_PAY, EDIT_SECOND_PAY],
        [EDIT_BACK_BUTTON],
    ]
    return build_keyboard(rows, include_back=False, include_restart=True, include_menu=True)


async def show_edit_menu(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    doc_type = data.get("doc_type", "contract")
    await message.answer("Что хотите изменить?", reply_markup=edit_keyboard_for(doc_type))
    if doc_type == "supplement":
        await state.set_state(SupplementStates.waiting_for_edit_choice)
    else:
        await state.set_state(ContractStates.waiting_for_edit_choice)


async def finalize_edit(message: Message, state: FSMContext) -> None:
    await state.update_data(edit_mode=False, edit_field=None)
    await send_summary(message, state)

@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Привет! Выберите документ:", reply_markup=main_keyboard)
    if message.chat.type == "private" and message.from_user:
        await send_start_report(message.bot, message.from_user)


@router.message(Command("set_topic_starts"))
async def handle_set_topic_starts(message: Message) -> None:
    if not await ensure_topic_command(message):
        return

    config = load_config()
    config["report_chat_id"] = message.chat.id
    config["starts_thread_id"] = message.message_thread_id
    save_config(config)

    await message.bot.send_message(
        chat_id=message.chat.id,
        message_thread_id=message.message_thread_id,
        text="✅ Подтверждено. Эта тема назначена для отчётов о запусках.",
    )


@router.message(Command("set_topic_files"))
async def handle_set_topic_files(message: Message) -> None:
    if not await ensure_topic_command(message):
        return

    config = load_config()
    config["report_chat_id"] = message.chat.id
    config["files_thread_id"] = message.message_thread_id
    save_config(config)

    await message.bot.send_message(
        chat_id=message.chat.id,
        message_thread_id=message.message_thread_id,
        text="✅ Подтверждено. Эта тема назначена для архива файлов.",
    )


@router.message(Command("cancel"))
async def handle_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_keyboard)


@router.message(F.text == MAIN_MENU_BUTTON)
async def handle_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выберите документ:", reply_markup=main_keyboard)


@router.message(F.text == BACK_BUTTON)
async def handle_back_button(message: Message, state: FSMContext) -> None:
    await handle_back(message, state)


@router.message(F.text == MAIN_MENU_CONTRACT)
async def start_contract_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(doc_type="contract")
    await message.answer("Введите ФИО заказчика:", reply_markup=input_keyboard(include_back=False))
    await state.set_state(ContractStates.waiting_for_client_name)
    if message.from_user:
        await send_doc_start_report(message.bot, message.from_user, DOC_TYPE_LABELS["contract"])


@router.message(F.text == MAIN_MENU_ACT)
async def start_act_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(doc_type="act")
    await message.answer("Введите ФИО заказчика:", reply_markup=input_keyboard(include_back=False))
    await state.set_state(ContractStates.waiting_for_client_name)
    if message.from_user:
        await send_doc_start_report(message.bot, message.from_user, DOC_TYPE_LABELS["act"])


@router.message(F.text == MAIN_MENU_SUPPLEMENT)
async def start_supplement_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(doc_type="supplement", supplement_text="")
    await message.answer("Введите номер договора:", reply_markup=input_keyboard(include_back=False))
    await state.set_state(SupplementStates.waiting_for_contract_number)
    if message.from_user:
        await send_doc_start_report(message.bot, message.from_user, DOC_TYPE_LABELS["supplement"])


@router.message(ContractStates.waiting_for_client_name)
async def process_client_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if not text:
        await message.answer("Введите ФИО заказчика:", reply_markup=input_keyboard(include_back=False))
        return

    await state.update_data(client_name=text)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "client_name":
        await finalize_edit(message, state)
        return

    await message.answer("Введите адрес объекта:", reply_markup=input_keyboard())
    await state.set_state(ContractStates.waiting_for_address)


@router.message(ContractStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if not text:
        await message.answer("Введите адрес объекта:", reply_markup=input_keyboard())
        return

    await state.update_data(address=text)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "address":
        await finalize_edit(message, state)
        return

    await message.answer("Введите телефон заказчика:", reply_markup=input_keyboard())
    await state.set_state(ContractStates.waiting_for_phone)


@router.message(ContractStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    normalized = normalize_phone(text)
    if not normalized:
        await message.answer(
            "Телефон должен быть в формате +7XXXXXXXXXX или 8XXXXXXXXXX. Попробуйте снова:",
            reply_markup=input_keyboard(),
        )
        return

    await state.update_data(phone=normalized)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "phone":
        await finalize_edit(message, state)
        return

    await message.answer(
        "Введите дату договора/акта в формате ДД.ММ.ГГГГ (или нажмите «Текущая дата»):",
        reply_markup=date_keyboard(),
    )
    await state.set_state(ContractStates.waiting_for_contract_date)


@router.message(ContractStates.waiting_for_contract_date)
async def process_contract_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    if text == TODAY_BUTTON:
        date_value = datetime.now().strftime("%d.%m.%Y")
    else:
        date_value = text

    if not is_valid_date(date_value):
        await message.answer(
            "Дата должна быть в формате ДД.ММ.ГГГГ. Попробуйте снова:",
            reply_markup=date_keyboard(),
        )
        return

    await state.update_data(contract_date=date_value)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "contract_date":
        await finalize_edit(message, state)
        return

    if data.get("doc_type") == "act":
        await message.answer(
            "Введите серию паспорта (4 цифры) или «Пропустить»:",
            reply_markup=skip_keyboard(),
        )
        await state.set_state(ContractStates.waiting_for_passport_series)
        return

    await message.answer("Введите дату начала работ (или нажмите «По звонку»):", reply_markup=start_date_keyboard())
    await state.set_state(ContractStates.waiting_for_start_date)


@router.message(ContractStates.waiting_for_start_date)
async def process_start_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    if text == CALL_BUTTON:
        start_date = CALL_BUTTON
    else:
        start_date = text

    if start_date != CALL_BUTTON and not is_valid_date(start_date):
        await message.answer(
            "Дата должна быть в формате ДД.ММ.ГГГГ или нажмите «По звонку».",
            reply_markup=start_date_keyboard(),
        )
        return

    await state.update_data(start_date=start_date)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "start_date":
        await finalize_edit(message, state)
        return

    await message.answer("Введите дату окончания работ (или «Пропустить»):", reply_markup=skip_keyboard())
    await state.set_state(ContractStates.waiting_for_end_date)


@router.message(ContractStates.waiting_for_end_date)
async def process_end_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    if text == SKIP_BUTTON:
        end_date = ""
    else:
        end_date = text
        if not is_valid_date(end_date):
            await message.answer(
                "Дата должна быть в формате ДД.ММ.ГГГГ или «Пропустить».",
                reply_markup=skip_keyboard(),
            )
            return

    await state.update_data(end_date=end_date)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "end_date":
        await finalize_edit(message, state)
        return

    await message.answer("Введите общую сумму договора (только цифры):", reply_markup=input_keyboard())
    await state.set_state(ContractStates.waiting_for_total_sum)


@router.message(ContractStates.waiting_for_total_sum)
async def process_total_sum(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    digits = extract_digits(text)
    if not digits:
        await message.answer("Введите сумму цифрами. Например: 150000", reply_markup=input_keyboard())
        return

    await state.update_data(total_sum=digits)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "total_sum":
        await finalize_edit(message, state)
        return

    await message.answer("Введите серию паспорта (4 цифры) или «Пропустить»:", reply_markup=skip_keyboard())
    await state.set_state(ContractStates.waiting_for_passport_series)


@router.message(ContractStates.waiting_for_passport_series)
async def process_passport_series(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().replace(" ", "")
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if text == SKIP_BUTTON:
        await state.update_data(passport_series="")
        data = await state.get_data()
        if data.get("edit_mode") and data.get("edit_field") == "passport_series":
            await finalize_edit(message, state)
            return
        await message.answer("Введите номер паспорта (6 цифр) или «Пропустить»:", reply_markup=skip_keyboard())
        await state.set_state(ContractStates.waiting_for_passport_number)
        return

    if not (text.isdigit() and len(text) == 4):
        await message.answer(
            "Серия паспорта должна состоять из 4 цифр. Попробуйте снова:",
            reply_markup=skip_keyboard(),
        )
        return

    await state.update_data(passport_series=text)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "passport_series":
        await finalize_edit(message, state)
        return

    await message.answer("Введите номер паспорта (6 цифр) или «Пропустить»:", reply_markup=skip_keyboard())
    await state.set_state(ContractStates.waiting_for_passport_number)


@router.message(ContractStates.waiting_for_passport_number)
async def process_passport_number(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().replace(" ", "")
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if text == SKIP_BUTTON:
        await state.update_data(passport_number="")
        data = await state.get_data()
        if data.get("edit_mode") and data.get("edit_field") == "passport_number":
            await finalize_edit(message, state)
            return
        await message.answer("Введите кем и когда выдан паспорт (или «Пропустить»):", reply_markup=skip_keyboard())
        await state.set_state(ContractStates.waiting_for_passport_base)
        return

    if not (text.isdigit() and len(text) == 6):
        await message.answer(
            "Номер паспорта должен состоять из 6 цифр. Попробуйте снова:",
            reply_markup=skip_keyboard(),
        )
        return

    await state.update_data(passport_number=text)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "passport_number":
        await finalize_edit(message, state)
        return

    await message.answer("Введите кем и когда выдан паспорт (или «Пропустить»):", reply_markup=skip_keyboard())
    await state.set_state(ContractStates.waiting_for_passport_base)


@router.message(ContractStates.waiting_for_passport_base)
async def process_passport_base(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if text == SKIP_BUTTON:
        await state.update_data(passport_base="")
        data = await state.get_data()
        if data.get("edit_mode") and data.get("edit_field") == "passport_base":
            await finalize_edit(message, state)
            return
        if data.get("doc_type") == "act":
            await send_summary(message, state)
            return
        await message.answer("Введите сумму предоплаты (или «Пропустить»):", reply_markup=skip_keyboard())
        await state.set_state(ContractStates.waiting_for_pre_pay)
        return

    await state.update_data(passport_base=text)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "passport_base":
        await finalize_edit(message, state)
        return

    if data.get("doc_type") == "act":
        await send_summary(message, state)
        return

    await message.answer("Введите сумму предоплаты (или «Пропустить»):", reply_markup=skip_keyboard())
    await state.set_state(ContractStates.waiting_for_pre_pay)


@router.message(ContractStates.waiting_for_pre_pay)
async def process_pre_pay(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    normalized = normalize_skip(text)
    if normalized in {"нет", "пропустить", "0"}:
        pre_pay = ""
    else:
        digits = extract_digits(text)
        if not digits:
            await message.answer("Введите сумму цифрами или «Пропустить».", reply_markup=skip_keyboard())
            return
        pre_pay = digits

    await state.update_data(pre_pay=pre_pay)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "pre_pay":
        await finalize_edit(message, state)
        return

    await message.answer("Сколько этапов оплаты? Введите 1 или 2:", reply_markup=stage_keyboard())
    await state.set_state(ContractStates.waiting_for_stage_choice)


@router.message(ContractStates.waiting_for_stage_choice)
async def process_stage_choice(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    if text not in {STAGE_ONE_BUTTON, STAGE_TWO_BUTTON}:
        await message.answer("Нужно выбрать 1 или 2.", reply_markup=stage_keyboard())
        return

    data = await state.get_data()
    total = extract_digits_to_int(data.get("total_sum"))
    pre = extract_digits_to_int(data.get("pre_pay"), allow_empty=True)

    if text == STAGE_ONE_BUTTON:
        rest = total - pre
        if rest < 0:
            await message.answer(
                "Предоплата больше общей суммы. Проверьте данные.",
                reply_markup=skip_keyboard(),
            )
            await state.set_state(ContractStates.waiting_for_pre_pay)
            return
        await state.update_data(first_pay=str(rest), second_pay="")
        await send_summary(message, state)
        return

    await message.answer("Введите сумму первого платежа:", reply_markup=input_keyboard())
    await state.set_state(ContractStates.waiting_for_first_pay)


@router.message(ContractStates.waiting_for_first_pay)
async def process_first_pay(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    digits = extract_digits(text)
    if not digits:
        await message.answer("Введите сумму цифрами.", reply_markup=input_keyboard())
        return

    data = await state.get_data()
    total = extract_digits_to_int(data.get("total_sum"))
    pre = extract_digits_to_int(data.get("pre_pay"), allow_empty=True)
    first = extract_digits_to_int(digits, allow_empty=True)
    rest = total - pre - first
    if rest < 0:
        await message.answer(
            "Сумма платежей больше общей суммы. Проверьте данные.",
            reply_markup=input_keyboard(),
        )
        return

    await state.update_data(first_pay=str(first), second_pay=str(rest))
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "first_pay":
        await finalize_edit(message, state)
        return

    await send_summary(message, state)


@router.message(ContractStates.waiting_for_second_pay)
async def process_second_pay(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    digits = extract_digits(text)
    if not digits:
        await message.answer("Введите сумму цифрами.", reply_markup=input_keyboard())
        return

    await state.update_data(second_pay=digits)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "second_pay":
        await finalize_edit(message, state)
        return

    await send_summary(message, state)

async def send_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    doc_type = data.get("doc_type")

    if doc_type == "supplement":
        summary_text = (
            "Проверьте данные для доп. соглашения:\n\n"
            f"Номер договора: <b>{escape_html(data.get('contract_number'))}</b>\n"
            f"Дата доп. соглашения: <b>{escape_html(data.get('supplement_date'))}</b>\n"
            f"Текст:\n<pre>{escape_html(data.get('supplement_text'))}</pre>"
        )
    else:
        date_label = "Дата акта" if doc_type == "act" else "Дата договора"
        summary_text = (
            "Проверьте данные:\n\n"
            f"ФИО заказчика: <b>{escape_html(data.get('client_name'))}</b>\n"
            f"Адрес объекта: <b>{escape_html(data.get('address'))}</b>\n"
            f"Телефон: <b>{escape_html(data.get('phone'))}</b>\n"
            f"{date_label}: <b>{escape_html(data.get('contract_date'))}</b>\n"
        )

        if doc_type != "act":
            summary_text += (
                f"Дата начала: <b>{escape_html(data.get('start_date'))}</b>\n"
                f"Дата окончания: <b>{escape_html(data.get('end_date') or '—')}</b>\n"
                f"Сумма договора: <b>{escape_html(data.get('total_sum'))}</b>\n"
            )

        summary_text += (
            "\nПаспортные данные:\n"
            f"Серия: <b>{escape_html(data.get('passport_series'))}</b>\n"
            f"Номер: <b>{escape_html(data.get('passport_number'))}</b>\n"
            f"Кем и когда выдан: <b>{escape_html(data.get('passport_base'))}</b>\n"
        )

        if doc_type != "act":
            summary_text += (
                "\nПлатежи:\n"
                f"Предоплата: <b>{escape_html(data.get('pre_pay') or '—')}</b>\n"
                f"Платеж 1: <b>{escape_html(data.get('first_pay') or '—')}</b>\n"
                f"Платеж 2: <b>{escape_html(data.get('second_pay') or '—')}</b>\n"
            )

    await message.answer(summary_text, parse_mode="HTML", reply_markup=confirm_keyboard)
    if doc_type == "supplement":
        await state.set_state(SupplementStates.waiting_for_summary_confirm)
    else:
        await state.set_state(ContractStates.waiting_for_summary_confirm)


@router.message(ContractStates.waiting_for_edit_choice)
async def process_edit_choice_contract(message: Message, state: FSMContext) -> None:
    choice = (message.text or "").strip()
    if choice == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    data = await state.get_data()
    doc_type = data.get("doc_type", "contract")

    if choice == EDIT_BACK_BUTTON:
        await send_summary(message, state)
        return

    if doc_type == "act":
        mapping = {
            EDIT_FIO: ("client_name", ContractStates.waiting_for_client_name),
            EDIT_ADDRESS: ("address", ContractStates.waiting_for_address),
            EDIT_PHONE: ("phone", ContractStates.waiting_for_phone),
            EDIT_ACT_DATE: ("contract_date", ContractStates.waiting_for_contract_date),
            EDIT_PASSPORT_SERIES: ("passport_series", ContractStates.waiting_for_passport_series),
            EDIT_PASSPORT_NUMBER: ("passport_number", ContractStates.waiting_for_passport_number),
            EDIT_PASSPORT_BASE: ("passport_base", ContractStates.waiting_for_passport_base),
        }
    else:
        mapping = {
            EDIT_FIO: ("client_name", ContractStates.waiting_for_client_name),
            EDIT_ADDRESS: ("address", ContractStates.waiting_for_address),
            EDIT_PHONE: ("phone", ContractStates.waiting_for_phone),
            EDIT_CONTRACT_DATE: ("contract_date", ContractStates.waiting_for_contract_date),
            EDIT_START_DATE: ("start_date", ContractStates.waiting_for_start_date),
            EDIT_END_DATE: ("end_date", ContractStates.waiting_for_end_date),
            EDIT_TOTAL_SUM: ("total_sum", ContractStates.waiting_for_total_sum),
            EDIT_PASSPORT_SERIES: ("passport_series", ContractStates.waiting_for_passport_series),
            EDIT_PASSPORT_NUMBER: ("passport_number", ContractStates.waiting_for_passport_number),
            EDIT_PASSPORT_BASE: ("passport_base", ContractStates.waiting_for_passport_base),
            EDIT_PREPAY: ("pre_pay", ContractStates.waiting_for_pre_pay),
            EDIT_FIRST_PAY: ("first_pay", ContractStates.waiting_for_first_pay),
            EDIT_SECOND_PAY: ("second_pay", ContractStates.waiting_for_second_pay),
        }

    if choice not in mapping:
        await message.answer("Выберите пункт для изменения.", reply_markup=edit_keyboard_for(doc_type))
        return

    field, target_state = mapping[choice]
    await state.update_data(edit_mode=True, edit_field=field)
    await state.set_state(target_state)
    await prompt_for_state(message, target_state.state, data)


@router.message(SupplementStates.waiting_for_edit_choice)
async def process_edit_choice_supplement(message: Message, state: FSMContext) -> None:
    choice = (message.text or "").strip()
    if choice == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    if choice == EDIT_BACK_BUTTON:
        await send_summary(message, state)
        return

    mapping = {
        EDIT_CONTRACT_NUMBER: ("contract_number", SupplementStates.waiting_for_contract_number),
        EDIT_SUPPLEMENT_DATE: ("supplement_date", SupplementStates.waiting_for_supplement_date),
        EDIT_SUPPLEMENT_TEXT: ("supplement_text", SupplementStates.waiting_for_text),
    }
    if choice not in mapping:
        await message.answer("Выберите пункт для изменения.", reply_markup=edit_keyboard_for("supplement"))
        return

    field, target_state = mapping[choice]
    if field == "supplement_text":
        await state.update_data(edit_mode=True, edit_field=field, supplement_text="")
    else:
        await state.update_data(edit_mode=True, edit_field=field)
    await state.set_state(target_state)
    await prompt_for_state(message, target_state.state, {})


@router.message(ContractStates.waiting_for_summary_confirm)
async def process_contract_confirm(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if text == EDIT_BUTTON:
        await show_edit_menu(message, state)
        return

    if text != CONFIRM_BUTTON:
        await message.answer(
            "Нажмите «Сформировать», «Изменить данные» или «Начать заново».",
            reply_markup=confirm_keyboard,
        )
        return

    data = await state.get_data()
    doc_type = data.get("doc_type")

    if doc_type == "act":
        result = render_act(data)
        caption = "Готовый акт."
    else:
        result = render_contract(data)
        caption = "Готовый договор."

    try:
        if result.pdf_path:
            await message.answer_document(FSInputFile(str(result.pdf_path)), caption=caption, reply_markup=main_keyboard)
            if message.from_user:
                report_caption = build_file_caption(data, message.from_user)
                await send_file_report(message.bot, result.pdf_path, report_caption)
        else:
            await message.answer(
                f"Не удалось конвертировать в PDF. Отправляю DOCX.\nПричина: {result.error}",
                reply_markup=main_keyboard,
            )
            await message.answer_document(FSInputFile(str(result.docx_path)), caption=caption, reply_markup=main_keyboard)
    finally:
        result.cleanup()

    await state.clear()


@router.message(SupplementStates.waiting_for_contract_number)
async def process_contract_number(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if not text:
        await message.answer("Введите номер договора:", reply_markup=input_keyboard(include_back=False))
        return

    await state.update_data(contract_number=text)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "contract_number":
        await finalize_edit(message, state)
        return

    await message.answer(
        "Введите дату доп. соглашения в формате ДД.ММ.ГГГГ (или нажмите «Текущая дата»):",
        reply_markup=date_keyboard(),
    )
    await state.set_state(SupplementStates.waiting_for_supplement_date)


@router.message(SupplementStates.waiting_for_supplement_date)
async def process_supplement_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return

    if text == TODAY_BUTTON:
        date_value = datetime.now().strftime("%d.%m.%Y")
    else:
        date_value = text

    if not is_valid_date(date_value):
        await message.answer(
            "Дата должна быть в формате ДД.ММ.ГГГГ. Попробуйте снова:",
            reply_markup=date_keyboard(),
        )
        return

    await state.update_data(supplement_date=date_value)
    data = await state.get_data()
    if data.get("edit_mode") and data.get("edit_field") == "supplement_date":
        await finalize_edit(message, state)
        return

    await message.answer(
        "Введите текст доп. соглашения. Можно несколькими сообщениями. Для завершения отправьте /done.",
        reply_markup=input_keyboard(),
    )
    await state.set_state(SupplementStates.waiting_for_text)


@router.message(Command("done"), SupplementStates.waiting_for_text)
async def process_supplement_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not (data.get("supplement_text") or "").strip():
        await message.answer("Текст пустой. Добавьте текст или /cancel.")
        return
    if data.get("edit_mode") and data.get("edit_field") == "supplement_text":
        await finalize_edit(message, state)
        return
    await send_summary(message, state)


@router.message(SupplementStates.waiting_for_text)
async def process_supplement_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if not text:
        await message.answer("Введите текст или /done для завершения.")
        return

    data = await state.get_data()
    current_text = data.get("supplement_text", "")
    updated_text = f"{current_text}\n{text}".strip()
    await state.update_data(supplement_text=updated_text)
    await message.answer("Добавлено. Продолжайте или отправьте /done.")


@router.message(SupplementStates.waiting_for_summary_confirm)
async def process_supplement_confirm(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == RESTART_BUTTON:
        await restart_flow(message, state)
        return
    if text == EDIT_BUTTON:
        await show_edit_menu(message, state)
        return

    if text != CONFIRM_BUTTON:
        await message.answer(
            "Нажмите «Сформировать», «Изменить данные» или «Начать заново».",
            reply_markup=confirm_keyboard,
        )
        return

    data = await state.get_data()
    result = render_supplement(data)

    try:
        if result.pdf_path:
            await message.answer_document(
                FSInputFile(str(result.pdf_path)),
                caption="Готовое доп. соглашение.",
                reply_markup=main_keyboard,
            )
            if message.from_user:
                report_caption = build_file_caption(data, message.from_user)
                await send_file_report(message.bot, result.pdf_path, report_caption)
        else:
            await message.answer(
                f"Не удалось конвертировать в PDF. Отправляю DOCX.\nПричина: {result.error}",
                reply_markup=main_keyboard,
            )
            await message.answer_document(
                FSInputFile(str(result.docx_path)),
                caption="Готовое доп. соглашение.",
                reply_markup=main_keyboard,
            )
    finally:
        result.cleanup()

    await state.clear()


async def restart_flow(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    doc_type = data.get("doc_type")
    await state.clear()

    if doc_type == "act":
        await start_act_flow(message, state)
    elif doc_type == "supplement":
        await start_supplement_flow(message, state)
    else:
        await start_contract_flow(message, state)
