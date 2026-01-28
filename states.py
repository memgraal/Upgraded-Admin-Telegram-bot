from aiogram.fsm.state import State, StatesGroup


class AdminStateGroup(StatesGroup):
    select_group = State()
    group_setting = State()
    group_subscription = State()
