from aiogram.fsm.state import State, StatesGroup


class ContractStates(StatesGroup):
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
    waiting_for_second_pay = State()
    waiting_for_summary_confirm = State()
    waiting_for_edit_choice = State()


class SupplementStates(StatesGroup):
    waiting_for_contract_number = State()
    waiting_for_supplement_date = State()
    waiting_for_text = State()
    waiting_for_summary_confirm = State()
    waiting_for_edit_choice = State()
