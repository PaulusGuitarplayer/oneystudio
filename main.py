import telebot
from telebot import types
from datetime import datetime, timedelta
from config import TOKEN, WORK_START, WORK_END, SLOT_DURATION, ADMIN_IDS
import db as db

bot = telebot.TeleBot(TOKEN)

# ---------- Вспомогательные функции ----------
def schedule_dates_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for date in get_dates(14):
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][dt.weekday()]
        text = f"{dt.strftime('%d.%m')} ({weekday})"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"sched_{date}"))
    kb.add(*buttons)
    return kb

def notify_admins(text: str):
    """Отправляет сообщение всем администраторам"""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"Не удалось отправить уведомление админу {admin_id}: {e}")

def day_schedule_keyboard(date: str):
    """Кнопка «Выбрать другой день»"""
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("« Выбрать другой день", callback_data="schedule_menu"))
    return kb

def get_available_start_times(date: str) -> list:
    """Возвращает список свободных времён начала"""
    free = []
    for slot in get_time_slots():
        if db.is_slot_free(date, slot):
            free.append(slot)
    return free

def get_dates(days: int = 14) -> list:
    """Список дат на ближайшие N дней"""
    today = datetime.now().date()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

def get_time_slots() -> list:
    """Все возможные временные слоты"""
    slots = []
    for hour in range(WORK_START, WORK_END, SLOT_DURATION):
        slots.append(f"{hour:02d}:00")
    return slots

def format_day_schedule(date: str) -> str:
    """Красивое расписание на один день с кликабельными профилями"""
    dt = datetime.strptime(date, "%Y-%m-%d")
    weekday = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][dt.weekday()]
    
    bookings = db.get_bookings_for_period(date, date)
    
    # time_slot → (user_id, display_name)
    booked = {}
    for _, time_slot, user_id, username, full_name in bookings:
        display_name = full_name or username or f"ID{user_id}"
        booked[time_slot] = (user_id, display_name)

    lines = [
        f"📅 <b>{dt.strftime('%d.%m.%Y')} — {weekday}</b>\n"
    ]

    free_count = 0
    for slot in get_time_slots():
        if slot in booked:
            user_id, name = booked[slot]
            # Кликабельная ссылка на профиль
            profile_link = f'<a href="tg://user?id={user_id}">{name}</a>'
            lines.append(f"🔴 {slot} — {profile_link}")
        else:
            lines.append(f"🟢 {slot} — свободно")
            free_count += 1

    if free_count == 0:
        lines.append("\n⚠️ В этот день все слоты заняты")
    else:
        lines.append(f"\nСвободно слотов: {free_count}")

    return "\n".join(lines)

# def format_schedule(days: int = 14) -> str:
#     """Красивое текстовое расписание"""
#     dates = get_dates(days)
#     start, end = dates[0], dates[-1]
#     bookings = db.get_bookings_for_period(start, end)

#     booked = {}  # (date, time) -> info
#     for date, time_slot, user_id, username, full_name in bookings:
#         name = full_name or username or str(user_id)
#         booked[(date, time_slot)] = name

#     lines = ["📅 <b>Расписание студии на 2 недели</b>\n"]
#     for date in dates:
#         dt = datetime.strptime(date, "%Y-%m-%d")
#         weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][dt.weekday()]
#         lines.append(f"\n<b>{dt.strftime('%d.%m')} ({weekday})</b>")
        
#         free_count = 0
#         for slot in get_time_slots():
#             if (date, slot) in booked:
#                 lines.append(f"  🔴 {slot} — {booked[(date, slot)]}")
#             else:
#                 lines.append(f"  🟢 {slot} — свободно")
#                 free_count += 1
        
#         if free_count == 0:
#             lines.append("  ⚠️ Все слоты заняты")

#     return "\n".join(lines)

# ---------- Клавиатуры ----------

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📅 Расписание", "➕ Забронировать")
    kb.row("📋 Мои брони", "❌ Отменить бронь")
    return kb

def dates_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for date in get_dates(14):
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][dt.weekday()]
        text = f"{dt.strftime('%d.%m')} ({weekday})"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"date_{date}"))
    kb.add(*buttons)
    kb.add(types.InlineKeyboardButton("« Назад", callback_data="cancel"))
    return kb

def times_keyboard(date: str):
    """Клавиатура выбора времени начала"""
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for slot in get_time_slots():
        if db.is_slot_free(date, slot):
            buttons.append(types.InlineKeyboardButton(
                f"🟢 {slot}", callback_data=f"start_{date}_{slot}"
            ))
        else:
            buttons.append(types.InlineKeyboardButton(
                f"🔴 {slot}", callback_data="busy"
            ))
    kb.add(*buttons)
    kb.add(types.InlineKeyboardButton("« Выбрать другую дату", callback_data="book"))
    return kb

def duration_keyboard(date: str, start_time: str):
    """Клавиатура выбора длительности"""
    kb = types.InlineKeyboardMarkup(row_width=4)
    start_hour = int(start_time.split(":")[0])
    max_hours = WORK_END - start_hour          # сколько максимум можно взять

    buttons = []
    for h in range(1, max_hours + 1):
        # Проверяем, свободны ли все часы
        if db.are_slots_free(date, start_time, h):
            text = f"{h} ч"
            buttons.append(types.InlineKeyboardButton(
                text, callback_data=f"dur_{date}_{start_time}_{h}"
            ))
        else:
            # Дальше бронировать нельзя — прерываем
            break

    if not buttons:
        kb.add(types.InlineKeyboardButton("Нет свободных часов", callback_data="busy"))
    else:
        kb.add(*buttons)

    kb.add(types.InlineKeyboardButton("« Выбрать другое время", callback_data=f"date_{date}"))
    return kb

def confirm_keyboard(date: str, start_time: str, hours: int):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "✅ Подтвердить",
            callback_data=f"confirm_{date}_{start_time}_{hours}"
        ),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )
    return kb

# ---------- Обработчики ----------

@bot.message_handler(func=lambda m: m.text == "📅 Расписание")
def show_schedule_menu(message):
    bot.send_message(
        message.chat.id,
        "Выберите день для просмотра расписания:",
        reply_markup=schedule_dates_keyboard()
    )

def show_schedule(message):
    text = format_schedule(14)
    # Telegram ограничивает длину сообщения, поэтому при необходимости можно разбивать
    if len(text) > 4000:
        # Разбиваем по дням (простой вариант)
        parts = text.split("\n\n")
        current = ""
        for part in parts:
            if len(current) + len(part) > 3800:
                bot.send_message(message.chat.id, current, parse_mode="HTML")
                current = part
            else:
                current += "\n\n" + part if current else part
        if current:
            bot.send_message(message.chat.id, current, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "➕ Забронировать")
def start_booking(message):
    bot.send_message(
        message.chat.id,
        "Выберите дату:",
        reply_markup=dates_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "📋 Мои брони")
def my_bookings(message):
    bookings = db.get_user_bookings(message.from_user.id)
    if not bookings:
        bot.send_message(message.chat.id, "У вас нет активных бронирований.")
        return

    lines = ["📋 <b>Ваши бронирования:</b>\n"]
    for bid, date, slot in bookings:
        dt = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        lines.append(f"• {dt} в {slot} (ID: {bid})")
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "❌ Отменить бронь")
def cancel_start(message):
    bookings = db.get_user_bookings(message.from_user.id)
    if not bookings:
        bot.send_message(message.chat.id, "У вас нет бронирований для отмены.")
        return

    kb = types.InlineKeyboardMarkup()
    for bid, date, slot in bookings:
        dt = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m")
        kb.add(types.InlineKeyboardButton(
            f"{dt} {slot}",
            callback_data=f"cancel_{bid}"
        ))
    kb.add(types.InlineKeyboardButton("« Назад", callback_data="cancel"))
    bot.send_message(message.chat.id, "Выберите бронь для отмены:", reply_markup=kb)

# ---------- Callback-обработчики ----------

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data

    if data == "cancel":
        bot.edit_message_text("Действие отменено.", call.message.chat.id, call.message.message_id)
        return

    if data == "busy":
        bot.answer_callback_query(call.id, "Этот слот уже занят!", show_alert=True)
        return

    # --- Меню выбора дня для расписания ---
    if data == "schedule_menu":
        bot.edit_message_text(
            "Выберите день для просмотра расписания:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=schedule_dates_keyboard()
        )
        return

    # --- Показ расписания на выбранный день ---
    if data.startswith("sched_"):
        date = data[6:]  # sched_YYYY-MM-DD
        text = format_day_schedule(date)
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=day_schedule_keyboard(date)
        )
        return

    if data == "book":
        bot.edit_message_text(
            "Выберите дату:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=dates_keyboard()
        )
        return

    # --- Выбор даты ---
    if data.startswith("date_"):
        date = data[5:]
        bot.edit_message_text(
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Выберите время начала:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=times_keyboard(date)
        )
        return

    # --- Выбор времени начала ---
    if data.startswith("start_"):
        _, date, start_time = data.split("_", 2)
        bot.edit_message_text(
            f"Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Начало: {start_time}\n\n"
            f"На сколько часов хотите забронировать?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=duration_keyboard(date, start_time)
        )
        return

    # --- Выбор длительности ---
    if data.startswith("dur_"):
        # format: dur_YYYY-MM-DD_HH:MM_hours
        parts = data.split("_")
        date = parts[1]
        start_time = parts[2]
        hours = int(parts[3])

        end_hour = int(start_time.split(":")[0]) + hours
        end_time = f"{end_hour:02d}:00"

        text = (
            f"Подтвердите бронирование:\n\n"
            f"📅 Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"🕐 Время: {start_time} – {end_time}\n"
            f"⏱ Длительность: {hours} ч."
        )
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=confirm_keyboard(date, start_time, hours)
        )
        return

    # --- Подтверждение ---
    if data.startswith("confirm_"):
        # format: confirm_YYYY-MM-DD_HH:MM_hours
        parts = data.split("_")
        date = parts[1]
        start_time = parts[2]
        hours = int(parts[3])

        user = call.from_user
        success = db.add_booking(
            user.id,
            user.username,
            user.full_name,
            date,
            start_time,
            hours
        )

        if success:
            end_hour = int(start_time.split(":")[0]) + hours
            end_time = f"{end_hour:02d}:00"
            
            # Сообщение пользователю
            bot.edit_message_text(
                f"✅ Бронь успешно создана!\n\n"
                f"📅 {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                f"🕐 {start_time} – {end_time} ({hours} ч.)",
                call.message.chat.id,
                call.message.message_id
            )

            # === Уведомление администраторам ===
            user_link = f'<a href="tg://user?id={user.id}">{user.full_name or user.username or user.id}</a>'
            admin_text = (
                f"🔔 <b>Новая бронь!</b>\n\n"
                f"👤 Пользователь: {user_link}\n"
                f"📅 Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                f"🕐 Время: {start_time} – {end_time}\n"
                f"⏱ Длительность: {hours} ч."
            )
            notify_admins(admin_text)

        else:
            bot.edit_message_text(
                "❌ К сожалению, один из слотов только что заняли.\n"
                "Попробуйте выбрать другое время.",
                call.message.chat.id,
                call.message.message_id
            )
        return

    # --- Отмена брони ---
    if data.startswith("cancel_"):
        booking_id = int(data[7:])
        booking = db.cancel_booking(booking_id, call.from_user.id)

        if booking:
            _, user_id, username, full_name, date, time_slot = booking

            # Сообщение пользователю
            bot.edit_message_text(
                "✅ Бронь отменена.",
                call.message.chat.id,
                call.message.message_id
            )

            # === Уведомление администраторам ===
            user_link = f'<a href="tg://user?id={user_id}">{full_name or username or user_id}</a>'
            admin_text = (
                f"❌ <b>Бронь отменена</b>\n\n"
                f"👤 Пользователь: {user_link}\n"
                f"📅 Дата: {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
                f"🕐 Время: {time_slot}"
            )
            notify_admins(admin_text)

        else:
            bot.answer_callback_query(
                call.id,
                "Не удалось отменить (возможно, бронь уже удалена).",
                show_alert=True
            )
        return

# ---------- Запуск ----------

if __name__ == "__main__":
    db.init_db()
    print("Бот запущен...")
    bot.infinity_polling()