from aiogram.fsm.state import State, StatesGroup


class GroupFSM(StatesGroup):
    waiting_for_promo = State()


class BanwordsFSM(StatesGroup):
    waiting_for_add = State()
    waiting_for_delete = State()
