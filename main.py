import telebot
from telebot import types
from datetime import datetime, timedelta

from config import TOKEN, WORK_START, WORK_END, SLOT_DURATION
import db as db

bot = telebot.TeleBot(TOKEN)

INSTRUMENTS = {
    "keys": "Клавіші",
    "drums": "Ударні",
    "bass": "Бас",
    "guitar": "Гітара"
}

# ====================== РОЛІ ======================

def is_manager(user_id: int) -> bool:
    return db.get_user_role(user_id) == "manager"

def is_sound_engineer(user_id: int) -> bool:
    role = db.get_user_role(user_id)
    return role in ("sound_engineer", "manager")

def is_admin(user_id: int) -> bool:
    return db.get_user_role(user_id) is not None

def can_confirm_recordings(user_id: int) -> bool:
    role = db.get_user_role(user_id)
    return role in ("sound_engineer", "manager")

# ====================== ДОПОМІЖНІ ФУНКЦІЇ ======================

def get_dates(days: int = 14) -> list:
    today = datetime.now().date()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

def get_time_slots() -> list:
    return [f"{hour:02d}:00" for hour in range(WORK_START, WORK_END, SLOT_DURATION)]

def format_time_range(start_time: str, hours: int) -> str:
    start_hour = int(start_time.split(":")[0])
    end_time = f"{start_hour + hours:02d}:00"
    return f"{start_time} - {end_time}"

def format_instruments(instruments_str: str) -> str:
    if not instruments_str or instruments_str == "none":
        return "—"
    codes = instruments_str.split(",")
    return ", ".join(INSTRUMENTS.get(code, code) for code in codes if code)

def booking_type_text(btype: str) -> str:
    return "Запис" if btype == "recording" else "Репетиція"

def status_text(status: str) -> str:
    return {
        "pending": "Очікує підтвердження",
        "confirmed": "Підтверджено",
        "rejected": "Відхилено",
        "cancelled": "Скасовано"
    }.get(status, status)

def notify_admins(text: str, reply_markup=None, only_confirmers: bool = False):
    if only_confirmers:
        candidates = db.get_staff_by_role("sound_engineer") + db.get_staff_by_role("manager")
    else:
        candidates = (
            db.get_staff_by_role("admin") +
            db.get_staff_by_role("sound_engineer") +
            db.get_staff_by_role("manager")
        )
    candidates = list(set(candidates))

    for admin_id in candidates:
        if not db.get_notifications(admin_id):
            continue
        try:
            bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            print(f"Не вдалося надіслати повідомлення {admin_id}: {e}")

def format_day_schedule(date: str) -> str:
    dt = datetime.strptime(date, "%Y-%m-%d")
    weekday = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"][dt.weekday()]
    
    bookings = db.get_bookings_for_period(date, date)
    lines = [f"<b>{dt.strftime('%d.%m.%Y')} - {weekday}</b>\n"]

    if not bookings:
        lines.append("Весь день вільний")
        return "\n".join(lines)

    occupied = {}
    for bid, user_id, username, full_name, _, start_time, hours, btype, instruments, status in bookings:
        name = full_name or username or str(user_id)
        time_range = format_time_range(start_time, hours)
        profile_link = f'<a href="tg://user?id={user_id}">{name}</a>'
        type_text = booking_type_text(btype)
        status_icon = " (очікує)" if status == "pending" else ""
        instr = format_instruments(instruments)
        occupied[start_time] = (time_range, profile_link, hours, type_text, status_icon, instr)

    for slot in get_time_slots():
        if slot in occupied:
            time_range, profile_link, hours, type_text, status_icon, instr = occupied[slot]
            lines.append(f"{time_range} | {type_text}{status_icon} - {profile_link}")
            if instr != "—":
                lines.append(f"    Інструменти: {instr}")
        else:
            hour = int(slot.split(":")[0])
            covered = any(
                int(st.split(":")[0]) < hour < int(st.split(":")[0]) + h
                for st, (_, _, h, *_) in occupied.items()
            )
            if not covered:
                lines.append(f"{slot} - вільно")

    return "\n".join(lines)

# ====================== КЛАВІАТУРИ ======================

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Розклад", "Забронювати")
    kb.row("Мої бронювання", "Скасувати бронювання")
    return kb

def dates_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for date in get_dates(14):
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"][dt.weekday()]
        text = f"{dt.strftime('%d.%m')} ({weekday})"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"date_{date}"))
    kb.add(*buttons)
    kb.add(types.InlineKeyboardButton("← Назад", callback_data="cancel"))
    return kb

def schedule_dates_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for date in get_dates(14):
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"][dt.weekday()]
        text = f"{dt.strftime('%d.%m')} ({weekday})"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"sched_{date}"))
    kb.add(*buttons)
    return kb

def type_keyboard(date: str):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Репетиція", callback_data=f"type_{date}_rehearsal"),
        types.InlineKeyboardButton("Запис", callback_data=f"type_{date}_recording")
    )
    kb.add(types.InlineKeyboardButton("← Назад", callback_data="book"))
    return kb

def times_keyboard(date: str, btype: str):
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for slot in get_time_slots():
        if db.is_range_free(date, slot, 1):
            buttons.append(types.InlineKeyboardButton(
                f"{slot}", callback_data=f"start_{date}_{slot}_{btype}"
            ))
        else:
            buttons.append(types.InlineKeyboardButton(f"{slot} (зайнято)", callback_data="busy"))
    kb.add(*buttons)
    kb.add(types.InlineKeyboardButton("← Назад", callback_data=f"date_{date}"))
    return kb

def duration_keyboard(date: str, start_time: str, btype: str):
    kb = types.InlineKeyboardMarkup(row_width=4)
    start_hour = int(start_time.split(":")[0])
    max_hours = WORK_END - start_hour

    buttons = []
    for h in range(1, max_hours + 1):
        if db.is_range_free(date, start_time, h):
            buttons.append(types.InlineKeyboardButton(
                f"{h} год", callback_data=f"dur_{date}_{start_time}_{h}_{btype}"
            ))
        else:
            break

    if buttons:
        kb.add(*buttons)
    else:
        kb.add(types.InlineKeyboardButton("Немає вільних годин", callback_data="busy"))

    kb.add(types.InlineKeyboardButton("← Назад", callback_data=f"type_{date}_{btype}"))
    return kb

def instruments_keyboard(date: str, start_time: str, hours: int, btype: str, selected: set = None):
    if selected is None:
        selected = set()
    kb = types.InlineKeyboardMarkup(row_width=2)

    for code, name in INSTRUMENTS.items():
        mark = "✓ " if code in selected else ""
        new_selected = selected.copy()
        if code in new_selected:
            new_selected.remove(code)
        else:
            new_selected.add(code)
        selected_str = ",".join(sorted(new_selected)) if new_selected else "none"
        kb.add(types.InlineKeyboardButton(
            f"{mark}{name}",
            callback_data=f"instr_{date}_{start_time}_{hours}_{btype}_{selected_str}"
        ))

    selected_str = ",".join(sorted(selected)) if selected else "none"
    kb.add(types.InlineKeyboardButton(
        "Далі →",
        callback_data=f"instr_done_{date}_{start_time}_{hours}_{btype}_{selected_str}"
    ))
    kb.add(types.InlineKeyboardButton(
        "← Назад",
        callback_data=f"start_{date}_{start_time}_{btype}"
    ))
    return kb

def confirm_keyboard(date: str, start_time: str, hours: int, btype: str, instruments: str):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "Підтвердити",
            callback_data=f"confirm_{date}_{start_time}_{hours}_{btype}_{instruments}"
        ),
        types.InlineKeyboardButton("Скасувати", callback_data="cancel")
    )
    return kb

def day_schedule_keyboard(date: str, user_id: int = None):
    kb = types.InlineKeyboardMarkup()

    if user_id and is_admin(user_id):
        bookings = db.get_bookings_for_period(date, date)
        for bid, uid, username, full_name, _, start_time, hours, btype, instruments, status in bookings:
            name = full_name or username or str(uid)
            time_range = format_time_range(start_time, hours)

            if status == "pending":
                if can_confirm_recordings(user_id):
                    kb.add(types.InlineKeyboardButton(
                        f"Підтвердити {time_range}",
                        callback_data=f"admin_confirm_{bid}"
                    ))
                    kb.add(types.InlineKeyboardButton(
                        f"Відхилити {time_range}",
                        callback_data=f"admin_reject_{bid}"
                    ))
            else:
                kb.add(types.InlineKeyboardButton(
                    f"Скасувати {time_range} ({name})",
                    callback_data=f"admin_cancel_{bid}"
                ))

    kb.add(types.InlineKeyboardButton("← Вибрати інший день", callback_data="schedule_menu"))
    return kb

def admin_confirm_keyboard(booking_id: int):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("Підтвердити", callback_data=f"admin_confirm_{booking_id}"),
        types.InlineKeyboardButton("Відхилити", callback_data=f"admin_reject_{booking_id}")
    )
    return kb

# ====================== ОБРОБНИКИ ПОВІДОМЛЕНЬ ======================

@bot.message_handler(commands=["start", "help"])
def start(message):
    text = (
        "Вітаю! Я бот для бронювання студії.\n\n"
        "Доступні дії:\n"
        "Розклад - переглянути зайнятість\n"
        "Забронювати - репетиція або запис\n"
        "Мої бронювання - ваші активні бронювання\n"
        "Скасувати бронювання - скасувати свій запис\n\n"
        "І репетиція, і запис потребують підтвердження звукорежисера/менеджера."
    )
    if is_manager(message.from_user.id):
        text += "\n\nВам доступна команда /staff - управління співробітниками"
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(commands=["staff"])
def staff_menu(message):
    if not is_manager(message.from_user.id):
        bot.send_message(message.chat.id, "Ця команда доступна тільки менеджерам.")
        return

    staff = db.get_all_staff()
    if not staff:
        text = "Список співробітників порожній."
    else:
        lines = ["<b>Співробітники студії:</b>\n"]
        role_names = {
            "manager": "Менеджер",
            "sound_engineer": "Звукорежисер",
            "admin": "Адмін"
        }
        for uid, role in staff:
            lines.append(f"• {role_names.get(role, role)} - <code>{uid}</code>")
        text = "\n".join(lines)

    notif_enabled = db.get_notifications(message.from_user.id)
    notif_status = "Увімкнені" if notif_enabled else "Вимкнені"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Додати адміна", callback_data="staff_add_admin"))
    kb.add(types.InlineKeyboardButton("Додати звукорежисера", callback_data="staff_add_sound"))
    kb.add(types.InlineKeyboardButton("Видалити співробітника", callback_data="staff_remove"))
    kb.add(types.InlineKeyboardButton(
        f"Сповіщення: {notif_status}",
        callback_data="toggle_notifications"
    ))
    kb.add(types.InlineKeyboardButton("← Закрити", callback_data="cancel"))

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "Розклад")
def show_schedule_menu(message):
    bot.send_message(
        message.chat.id,
        "Оберіть день для перегляду розкладу:",
        reply_markup=schedule_dates_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "Забронювати")
def start_booking(message):
    bot.send_message(message.chat.id, "Оберіть дату:", reply_markup=dates_keyboard())

@bot.message_handler(func=lambda m: m.text == "Мої бронювання")
def my_bookings(message):
    bookings = db.get_user_bookings(message.from_user.id)
    if not bookings:
        bot.send_message(message.chat.id, "У вас немає активних бронювань.")
        return

    lines = ["<b>Ваші бронювання:</b>\n"]
    for bid, date, start_time, hours, btype, instruments, status in bookings:
        dt = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        time_range = format_time_range(start_time, hours)
        lines.append(
            f"• {dt}  {time_range}\n"
            f"  {booking_type_text(btype)} | {status_text(status)}\n"
            f"  Інструменти: {format_instruments(instruments)}"
        )
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "Скасувати бронювання")
def cancel_start(message):
    bookings = db.get_user_bookings(message.from_user.id)
    if not bookings:
        bot.send_message(message.chat.id, "У вас немає бронювань для скасування.")
        return

    kb = types.InlineKeyboardMarkup()
    for bid, date, start_time, hours, btype, instruments, status in bookings:
        dt = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m")
        time_range = format_time_range(start_time, hours)
        type_text = booking_type_text(btype)
        kb.add(types.InlineKeyboardButton(
            f"{dt} {time_range} ({type_text})",
            callback_data=f"cancel_{bid}"
        ))
    kb.add(types.InlineKeyboardButton("← Назад", callback_data="cancel"))
    bot.send_message(message.chat.id, "Оберіть бронювання для скасування:", reply_markup=kb)

# ====================== NEXT STEP ======================

def process_add_staff(message, role: str, added_by: int):
    try:
        user_id = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "Потрібно надіслати числовий ID.")
        return

    if db.add_staff(user_id, role, added_by):
        role_name = "адміном" if role == "admin" else "звукорежисером"
        bot.send_message(message.chat.id, f"Користувача {user_id} успішно призначено {role_name}.")
        try:
            bot.send_message(user_id, f"Вас призначено {role_name} студії.")
        except Exception:
            pass
    else:
        bot.send_message(message.chat.id, "Не вдалося додати.")

# ====================== CALLBACK HANDLER ======================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data

    if data == "cancel":
        bot.edit_message_text("Дію скасовано.", call.message.chat.id, call.message.message_id)
        return

    if data == "busy":
        bot.answer_callback_query(call.id, "Цей слот вже зайнятий!", show_alert=True)
        return

    # ---------- Управління персоналом ----------
    if data == "toggle_notifications":
        if not is_manager(call.from_user.id):
            bot.answer_callback_query(call.id, "Недостатньо прав.", show_alert=True)
            return

        current = db.get_notifications(call.from_user.id)
        new_state = not current
        db.set_notifications(call.from_user.id, new_state)

        status = "увімкнені" if new_state else "вимкнені"
        bot.answer_callback_query(call.id, f"Сповіщення {status}")

        staff = db.get_all_staff()
        lines = ["<b>Співробітники студії:</b>\n"]
        role_names = {
            "manager": "Менеджер",
            "sound_engineer": "Звукорежисер",
            "admin": "Адмін"
        }
        for uid, role in staff:
            lines.append(f"• {role_names.get(role, role)} - <code>{uid}</code>")
        text = "\n".join(lines)

        notif_status = "Увімкнені" if new_state else "Вимкнені"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Додати адміна", callback_data="staff_add_admin"))
        kb.add(types.InlineKeyboardButton("Додати звукорежисера", callback_data="staff_add_sound"))
        kb.add(types.InlineKeyboardButton("Видалити співробітника", callback_data="staff_remove"))
        kb.add(types.InlineKeyboardButton(
            f"Сповіщення: {notif_status}",
            callback_data="toggle_notifications"
        ))
        kb.add(types.InlineKeyboardButton("← Закрити", callback_data="cancel"))

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    if data == "staff_add_admin" or data == "staff_add_sound":
        if not is_manager(call.from_user.id):
            bot.answer_callback_query(call.id, "Недостатньо прав.", show_alert=True)
            return

        role = "admin" if data == "staff_add_admin" else "sound_engineer"
        msg = bot.send_message(
            call.message.chat.id,
            f"Надішліть ID користувача, якого хочете зробити "
            f"{'адміном' if role == 'admin' else 'звукорежисером'}.\n"
            f"Дізнатися ID можна через @userinfobot"
        )
        bot.register_next_step_handler(msg, process_add_staff, role, call.from_user.id)
        return

    if data == "staff_remove":
        if not is_manager(call.from_user.id):
            bot.answer_callback_query(call.id, "Недостатньо прав.", show_alert=True)
            return

        staff = [(uid, role) for uid, role in db.get_all_staff() if role != "manager"]
        if not staff:
            bot.answer_callback_query(call.id, "Нікого видаляти.", show_alert=True)
            return

        kb = types.InlineKeyboardMarkup()
        role_names = {"admin": "Адмін", "sound_engineer": "Звукорежисер"}
        for uid, role in staff:
            kb.add(types.InlineKeyboardButton(
                f"{role_names.get(role, role)} {uid}",
                callback_data=f"staff_del_{uid}"
            ))
        kb.add(types.InlineKeyboardButton("← Назад", callback_data="cancel"))
        bot.edit_message_text(
            "Оберіть, кого видалити:",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb
        )
        return

    if data.startswith("staff_del_"):
        if not is_manager(call.from_user.id):
            bot.answer_callback_query(call.id, "Недостатньо прав.", show_alert=True)
            return

        uid = int(data.split("_")[2])
        if db.remove_staff(uid):
            bot.edit_message_text(
                f"Користувача {uid} видалено зі співробітників.",
                call.message.chat.id, call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "Не вдалося видалити.", show_alert=True)
        return

    # ---------- Розклад ----------
    if data == "schedule_menu":
        bot.edit_message_text(
            "Оберіть день для перегляду розкладу:",
            call.message.chat.id, call.message.message_id,
            reply_markup=schedule_dates_keyboard()
        )
        return

    if data.startswith("sched_"):
        date = data[6:]
        text = format_day_schedule(date)
        bot.edit_message_text(
            text, call.message.chat.id, call.message.message_id,
            parse_mode="HTML",
            reply_markup=day_schedule_keyboard(date, user_id=call.from_user.id)
        )
        return

    # ---------- Бронювання ----------
    if data == "book":
        bot.edit_message_text(
            "Оберіть дату:", call.message.chat.id, call.message.message_id,
            reply_markup=dates_keyboard()
        )
        return

    if data.startswith("date_"):
        date = data[5:]
        bot.edit_message_text(
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Оберіть тип бронювання:",
            call.message.chat.id, call.message.message_id,
            reply_markup=type_keyboard(date)
        )
        return

    if data.startswith("type_"):
        _, date, btype = data.split("_", 2)
        bot.edit_message_text(
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Тип: {booking_type_text(btype)}\n\n"
            f"Оберіть час початку:",
            call.message.chat.id, call.message.message_id,
            reply_markup=times_keyboard(date, btype)
        )
        return

    if data.startswith("start_"):
        parts = data.split("_")
        date = parts[1]
        start_time = parts[2]
        btype = parts[3]
        bot.edit_message_text(
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Тип: {booking_type_text(btype)}\n"
            f"Початок: {start_time}\n\n"
            f"На скільки годин?",
            call.message.chat.id, call.message.message_id,
            reply_markup=duration_keyboard(date, start_time, btype)
        )
        return

    if data.startswith("dur_"):
        parts = data.split("_")
        date = parts[1]
        start_time = parts[2]
        hours = int(parts[3])
        btype = parts[4]
        bot.edit_message_text(
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Тип: {booking_type_text(btype)}\n"
            f"Час: {format_time_range(start_time, hours)}\n\n"
            f"Оберіть інструменти (можна кілька):",
            call.message.chat.id, call.message.message_id,
            reply_markup=instruments_keyboard(date, start_time, hours, btype)
        )
        return

    if data.startswith("instr_") and not data.startswith("instr_done_"):
        parts = data.split("_")
        date = parts[1]
        start_time = parts[2]
        hours = int(parts[3])
        btype = parts[4]
        selected_str = parts[5] if len(parts) > 5 else "none"
        selected = set(selected_str.split(",")) if selected_str != "none" else set()

        bot.edit_message_text(
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Тип: {booking_type_text(btype)}\n"
            f"Час: {format_time_range(start_time, hours)}\n\n"
            f"Оберіть інструменти (можна кілька):",
            call.message.chat.id, call.message.message_id,
            reply_markup=instruments_keyboard(date, start_time, hours, btype, selected)
        )
        return

    if data.startswith("instr_done_"):
        parts = data.split("_")
        date = parts[2]
        start_time = parts[3]
        hours = int(parts[4])
        btype = parts[5]
        instruments = parts[6] if len(parts) > 6 else "none"

        time_range = format_time_range(start_time, hours)
        text = (
            f"Підтвердіть бронювання:\n\n"
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Час: {time_range}\n"
            f"Тип: {booking_type_text(btype)}\n"
            f"Інструменти: {format_instruments(instruments)}\n\n"
            f"Бронювання буде підтверджено звукорежисером/менеджером."
        )

        bot.edit_message_text(
            text,
            call.message.chat.id, call.message.message_id,
            reply_markup=confirm_keyboard(date, start_time, hours, btype, instruments)
        )
        return

    if data.startswith("confirm_"):
        parts = data.split("_")
        date = parts[1]
        start_time = parts[2]
        hours = int(parts[3])
        btype = parts[4]
        instruments = parts[5] if len(parts) > 5 else "none"

        user = call.from_user
        booking_id = db.add_booking(
            user.id, user.username, user.full_name,
            date, start_time, hours, btype, instruments
        )

        if booking_id:
            time_range = format_time_range(start_time, hours)
            
            msg = (
                f"Заявку створено!\n\n"
                f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                f"Час: {time_range}\n"
                f"Тип: {booking_type_text(btype)}\n"
                f"Інструменти: {format_instruments(instruments)}\n\n"
                f"Очікуйте підтвердження від звукорежисера/менеджера."
            )
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)

            user_link = f'<a href="tg://user?id={user.id}">{user.full_name or user.username or user.id}</a>'
            admin_text = (
                f"<b>Нове бронювання!</b>\n\n"
                f"Користувач: {user_link}\n"
                f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                f"Час: {time_range}\n"
                f"Тип: {booking_type_text(btype)}\n"
                f"Інструменти: {format_instruments(instruments)}\n"
                f"Статус: {status_text('pending')}"
            )

            notify_admins(
                admin_text,
                reply_markup=admin_confirm_keyboard(booking_id),
                only_confirmers=True
            )
        else:
            bot.edit_message_text(
                "На жаль, обраний діапазон вже зайнятий.\nСпробуйте інший час.",
                call.message.chat.id, call.message.message_id
            )
        return

    # ---------- Скасування свого бронювання ----------
    if data.startswith("cancel_"):
        booking_id = int(data[7:])
        booking = db.cancel_booking(booking_id, call.from_user.id)

        if booking:
            _, user_id, username, full_name, date, start_time, hours, btype, instruments, status, _ = booking
            time_range = format_time_range(start_time, hours)
            bot.edit_message_text("Бронювання скасовано.", call.message.chat.id, call.message.message_id)

            user_link = f'<a href="tg://user?id={user_id}">{full_name or username or user_id}</a>'
            admin_text = (
                f"<b>Бронювання скасовано користувачем</b>\n\n"
                f"Користувач: {user_link}\n"
                f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                f"Час: {time_range}\n"
                f"Тип: {booking_type_text(btype)}"
            )
            notify_admins(admin_text)
        else:
            bot.answer_callback_query(call.id, "Не вдалося скасувати.", show_alert=True)
        return

    # ---------- Адмінські дії ----------
    if data.startswith("admin_confirm_"):
        if not can_confirm_recordings(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Підтверджувати бронювання можуть тільки звукорежисери та менеджери.",
                show_alert=True
            )
            return

        booking_id = int(data.split("_")[2])
        booking = db.confirm_booking(booking_id)

        if booking:
            _, user_id, username, full_name, date, start_time, hours, btype, instruments, status, _ = booking
            time_range = format_time_range(start_time, hours)

            bot.answer_callback_query(call.id, "Бронювання підтверджено!")
            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            except Exception:
                pass

            try:
                bot.send_message(
                    user_id,
                    f"Ваше бронювання підтверджено!\n\n"
                    f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                    f"Час: {time_range}\n"
                    f"Тип: {booking_type_text(btype)}\n"
                    f"Інструменти: {format_instruments(instruments)}"
                )
            except Exception:
                pass

            user_link = f'<a href="tg://user?id={user_id}">{full_name or username or user_id}</a>'
            notify_admins(
                f"<b>Бронювання підтверджено</b>\n\n"
                f"Користувач: {user_link}\n"
                f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')} {time_range}\n"
                f"Тип: {booking_type_text(btype)}\n"
                f"Підтвердив: {call.from_user.full_name or call.from_user.username}"
            )
        else:
            bot.answer_callback_query(call.id, "Не вдалося підтвердити.", show_alert=True)
        return

    if data.startswith("admin_reject_"):
        if not can_confirm_recordings(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Відхиляти бронювання можуть тільки звукорежисери та менеджери.",
                show_alert=True
            )
            return

        booking_id = int(data.split("_")[2])
        booking = db.reject_booking(booking_id)

        if booking:
            _, user_id, username, full_name, date, start_time, hours, btype, instruments, status, _ = booking
            time_range = format_time_range(start_time, hours)

            bot.answer_callback_query(call.id, "Бронювання відхилено.")
            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            except Exception:
                pass

            try:
                bot.send_message(
                    user_id,
                    f"На жаль, вашу заявку відхилено.\n\n"
                    f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                    f"Час: {time_range}\n"
                    f"Тип: {booking_type_text(btype)}"
                )
            except Exception:
                pass

            user_link = f'<a href="tg://user?id={user_id}">{full_name or username or user_id}</a>'
            notify_admins(
                f"<b>Бронювання відхилено</b>\n\n"
                f"Користувач: {user_link}\n"
                f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')} {time_range}\n"
                f"Тип: {booking_type_text(btype)}\n"
                f"Відхилив: {call.from_user.full_name or call.from_user.username}"
            )
        else:
            bot.answer_callback_query(call.id, "Не вдалося відхилити.", show_alert=True)
        return

    if data.startswith("admin_cancel_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "Недостатньо прав.", show_alert=True)
            return

        booking_id = int(data.split("_")[2])
        cancelled = db.admin_cancel_booking(booking_id)

        if cancelled:
            _, user_id, username, full_name, date, start_time, hours, btype, instruments, status, _ = cancelled
            time_range = format_time_range(start_time, hours)

            try:
                text = format_day_schedule(date)
                bot.edit_message_text(
                    text + f"\n\nБлок {time_range} скасовано.",
                    call.message.chat.id, call.message.message_id,
                    parse_mode="HTML",
                    reply_markup=day_schedule_keyboard(date, user_id=call.from_user.id)
                )
            except Exception:
                bot.answer_callback_query(call.id, "Бронювання скасовано.")

            try:
                bot.send_message(
                    user_id,
                    f"Ваше бронювання на {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')} "
                    f"({time_range}) було скасовано адміністратором."
                )
            except Exception:
                pass

            user_link = f'<a href="tg://user?id={user_id}">{full_name or username or user_id}</a>'
            notify_admins(
                f"<b>Адмін скасував бронювання</b>\n\n"
                f"Користувач: {user_link}\n"
                f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')} {time_range}\n"
                f"Тип: {booking_type_text(btype)}\n"
                f"Скасував: {call.from_user.full_name or call.from_user.username}"
            )
        else:
            bot.answer_callback_query(call.id, "Не вдалося скасувати.", show_alert=True)
        return

# ====================== ЗАПУСК ======================

if __name__ == "__main__":
    db.init_db()
    print("Бот запущено...")
    bot.infinity_polling()