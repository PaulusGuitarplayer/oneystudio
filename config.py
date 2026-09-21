# TOKEN = "8859563166:AAFdTyWN6VwEdpIKQhZkds9ylP5GWwNh4Eo"

import os

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("Не задано змінну оточення TOKEN")

INITIAL_MANAGER_IDS = [1662741323]

WORK_START = 9
WORK_END = 23
SLOT_DURATION = 1