from aiogram.fsm.state import State, StatesGroup

class CertificateStates(StatesGroup):
    choosing_amount   = State()
    entering_amount   = State()  # произвольная сумма
    entering_name     = State()  # имя получателя
    entering_message  = State()  # поздравление
    entering_recipient_phone = State()
    confirming        = State()  # превью перед оплатой
