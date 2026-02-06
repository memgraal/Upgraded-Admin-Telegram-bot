from aiogram.fsm.state import State, StatesGroup


class DMFSM(StatesGroup):
    # Навигация
    browsing_groups = State()
    group_settings = State()

    # Оплата
    waiting_for_promo = State()
    waiting_for_stars = State()

    # Бан-слова
    banwords_menu = State()
    banwords_add = State()
    banwords_delete = State()
