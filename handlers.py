from db import Database
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
)
import config
from exceptions import TGBotError, ServiceError
import re
from typing import List
from datetime import datetime

ADD_HABIT, DELETE_SELECT, DELETE_CONFIRM = range(3)


class Handler:
    """
    Основной класс-обработчик для Telegram бота трекера привычек

    :ivar db: Объект базы данных для работы с привычками
    :type db: Database
    :ivar kb: Клавиатура по умолчанию для всех сообщений
    :type kb: ReplyKeyboardMarkup
    """

    def __init__(self, db: Database):
        self.db = db
        self.kb = ReplyKeyboardMarkup(
            config.kb_btns, resize_keyboard=True, one_time_keyboard=False
        )

    def get_kb(self) -> ReplyKeyboardMarkup:
        """
        Возвращает основную клавиатуру

        :returns: Основная клавиатура
        :type: ReplyKeyboardMarkup
        """

        return self.kb

    def format_date(self, date: str) -> str:
        if not date:
            return "Никогда"
        try:
            if "-" in date:
                parts = date.split("-")
                if len(parts[0]) == 4:
                    return f"{parts[2]}.{parts[1]}.{parts[0]}"
                elif len(parts[2]) == 4:
                    return date
            return date
        except Exception as e:
            raise ServiceError("Date format error")

    def get_habit_id(self, text) -> int:
        match = re.search(r"\(ID\s*:\s*(\d+)\)", text)
        if not match:
            raise ServiceError(f"Invalid format data error")
        return int(match.group(1))

    async def start(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обработчик команды /start

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        """

        await self.reply(update, config.wellcome_msg)

    async def cancel_command(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обработчик отмены действия

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :returns: Завершение диалога
        :type: int
        """

        await self.reply(update, "Действие отменено!")
        return ConversationHandler.END

    async def reply(self, update: Update, text: str, keyboard=None) -> None:
        """
        Вспомогательный метод для отправки сообщений с обработкой ошибок

        :param update: Объект обновления от Telegram
        :type update: Update
        :param text: Текст сообщения
        :type text: str
        :param keyboard: Клавиатура для сообщения (по умолчанию используется self.kb)
        :type keyboard: ReplyKeyboardMarkup или None
        :raises TGBotError: Если произошла ошибка при отправке сообщения
        """

        try:
            if update.message:
                await update.message.reply_text(
                    text, reply_markup=keyboard or self.kb
                )
            elif update.callback_query:
                await update.callback_query.message.reply_text(
                    text, reply_markup=keyboard or self.kb
                )
            else:
                await update.effective_chat.send_message(
                    text, reply_markup=keyboard or self.kb
                )
        except Exception as e:
            raise TGBotError(f"Ошибка отправки сообщения: {str(e)}")

    def get_message_handlers(self) -> List[MessageHandler]:
        """
        Возвращает список обработчиков сообщений

        :returns: Список обработчиков сообщений
        :type: :List[MessageHandler]
        """

        return [
            MessageHandler(filters.Text("📋 Мои привычки"), self.habits_list),
            MessageHandler(
                filters.Text("✅ Выполнить привычку"),
                self.habits_list_to_complete,
            ),
            MessageHandler(
                filters.Regex(r"☑️ .*\(ID: \d+\)"), self.complete_habit
            ),
            MessageHandler(
                filters.Text(config.back_btn_text), self.cancel_command
            ),
        ]

    def get_conversation_handlers(self) -> List[ConversationHandler]:
        """
        Возвращает список диалоговых обработчиков

        :returns: Список диалоговых обработчиков
        :type: list[ConversationHandler]
        """

        add_habit_dialog = ConversationHandler(
            entry_points=[
                MessageHandler(
                    filters.Text("➕ Добавить привычку"), self.start_add_habit
                )
            ],
            states={
                ADD_HABIT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.set_habit_name
                    )
                ],
            },
            fallbacks=[
                MessageHandler(
                    filters.Text(config.back_btn_text), self.cancel_command
                ),
                CommandHandler("cancel", self.cancel_command),
            ],
        )
        delete_habit_dialog = ConversationHandler(
            entry_points=[
                MessageHandler(
                    filters.Text("🗑️ Удалить привычку"),
                    self.habits_list_to_delete,
                )
            ],
            states={
                DELETE_SELECT: [
                    MessageHandler(
                        filters.Regex(r"🗑️ .*\(ID: \d+\)"), self.delete_confirm
                    ),
                    MessageHandler(
                        filters.Text(config.back_btn_text), self.cancel_command
                    ),
                ],
                DELETE_CONFIRM: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.delete_process
                    )
                ],
            },
            fallbacks=[
                MessageHandler(
                    filters.Text(config.back_btn_text), self.cancel_command
                ),
                CommandHandler("cancel", self.cancel_command),
            ],
        )
        return [add_habit_dialog, delete_habit_dialog]

    async def start_add_habit(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Начало диалога добавления привычки

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :returns: Состояние диалога добавления привычки
        :type: int
        """

        return await self.add_habit(update)

    # метод прослойка для изменения состояния диалога
    async def add_habit(self, update: Update) -> int:
        """
        Метод-прослойка для изменения состояния диалога добавления привычки

        :param update: Объект обновления от Telegram
        :type update: Update
        :returns: Состояние диалога добавления привычки
        :type: int
        """

        back_keyboard = ReplyKeyboardMarkup(
            [[config.back_btn_text]], resize_keyboard=True
        )
        await self.reply(update, "Введите название привычки: ", back_keyboard)
        return ADD_HABIT

    # основная реализация функционала по добавлению привычки
    async def set_habit_name(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Основная реализация функционала по добавлению привычки

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :returns: Завершение диалога
        :type: int
        :raises TGBotError: Если произошла ошибка при добавлении привычки в БД
        """

        habit_name = update.message.text.strip()
        if habit_name == config.back_btn_text:
            await self.reply(update, "Отмена добавления привычки")
            return ConversationHandler.END
        try:
            if len(habit_name) < 5:
                await self.reply(update, "Слишком короткое имя привычки")
                return ConversationHandler.END
            if len(habit_name) > 20:
                await self.reply(update, "Слишком длинное имя привычки")
                return ConversationHandler.END
            self.db.add_habit(update.effective_user.id, habit_name)
        except Exception as e:
            raise TGBotError(f"Error: {e}")

        await self.reply(update, f"Привычка '{habit_name}' добавлена!")
        return ConversationHandler.END

    """
    Метод получения и форматированного вывода всех привычек пользователя
    """

    async def habits_list(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Метод получения и форматированного вывода всех привычек пользователя

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :raises TGBotError: Если произошла ошибка при получении привычек
        """
        try:
            habits = self.db.get_user_habits(update.effective_user.id)

            if not habits:
                await self.reply(
                    update, config.no_habits_msg, keyboard=self.get_kb()
                )
                return

            message = "📋Ваши привычки:\n\n"

            for habit in habits:
                streak = habit.get("current_streak", 0)
                if streak >= 30:
                    emoji = "🔥"
                elif streak >= 7:
                    emoji = "🚀"
                elif streak >= 3:
                    emoji = "⭐"
                elif streak > 0:
                    emoji = "🆕"
                else:
                    emoji = "📝"
                last_date = self.format_date(
                    habit.get("last_completed", "Никогда")
                )
                message += f'{emoji} {habit.get("name", "Не найдено")}\n\n Статистика: \n\n📅 Серия: {streak} дней\n📊 Всего выполнено: {habit.get("total_completions", 0)} раз\n🗓️ Последнее выполнение: {last_date}\n#️⃣ ID: {habit.get("id", 0)}\n\n'

            await self.reply(
                update,
                message,
                keyboard=self.get_kb(),
            )

        except Exception as e:
            await self.reply(update, "Ошибка вывода списка привычек")
            raise TGBotError(f"Error: {e}")

    """
    Реализация обработчиков и логики удаления привычек
    """

    async def habits_list_to_delete(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Отображение списка привычек для удаления

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :raises TGBotError: Если произошла ошибка при получении привычек
        """
        try:
            habits = self.db.get_user_habits(update.effective_user.id)
            if not habits:
                await self.reply(
                    update, config.no_habits_to_delete_msg, self.get_kb()
                )
                return ConversationHandler.END
            kb = []
            for habit in habits:
                kb.append(
                    [
                        f"🗑️ {habit.get("name", "Не найдено")} (ID: {habit.get("id", 0)})"
                    ]
                )
            kb.append([config.back_btn_text])
            await self.reply(
                update,
                "Какую привычку вы хотите удалить?",
                ReplyKeyboardMarkup(kb, resize_keyboard=True),
            )
            return DELETE_SELECT
        except Exception as e:
            await self.reply(
                update, "Ошибка вывода списка привычек для удаления"
            )
            raise TGBotError(f"Habit delete error: {e}")

    async def delete_confirm(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Подтверждение удаления привычки

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :returns: Состояние диалога подтверждения удаления
        :type: int
        :raises TGBotError: Если неверный формат входных данных
        """

        if update.message.text == "Нет, я передумал":
            await self.reply(
                update, "Удаление отменено!", keyboard=self.get_kb()
            )
            return ConversationHandler.END
        hid = self.get_habit_id(update.message.text)
        ctx.user_data["habit_to_del"] = hid
        habit_name = update.message.text.replace("🗑️ ", "").split(" (ID:")[0]

        await self.reply(
            update,
            f"Вы уверены что хотите удалить привычку '{habit_name}'?\n\nЭто действие не может быть прервано!",
            keyboard=ReplyKeyboardMarkup(
                config.confirm_btns, resize_keyboard=True
            ),
        )

        return DELETE_CONFIRM

    async def delete_process(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Процесс удаления привычки

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :returns: Завершение диалога
        :type: int
        :raises TGBotError: Если произошла ошибка при удалении привычки
        """

        try:
            if update.message.text == "Нет, я передумал":
                await self.reply(
                    update, "Удаление отменено!", keyboard=self.get_kb()
                )
                return ConversationHandler.END

            if update.message.text == config.back_btn_text:
                await self.reply(
                    update, "Удаление отменено!", keyboard=self.get_kb()
                )
                return ConversationHandler.END

            if update.message.text != "Да, удалить":
                await self.reply(
                    update,
                    "Пожалуйста, выберите один из предложенных вариантов",
                )
                return DELETE_CONFIRM

            hid = ctx.user_data.get("habit_to_del")
            if not hid:
                await self.reply(
                    update, "Привычка не найдена", keyboard=self.get_kb()
                )
                return ConversationHandler.END

            is_deleted = self.db.delete_habit(update.effective_user.id, hid)
            if is_deleted:
                await self.reply(
                    update, "Привычка успешно удалена", keyboard=self.get_kb()
                )

            else:
                await self.reply(
                    update, "Привычка не найдена", keyboard=self.get_kb()
                )
                return ConversationHandler.END

            return ConversationHandler.END

        except Exception as e:
            raise TGBotError(f"Habit delete error: {e}")

    """
    Реализация логики выполнения привычки
    """

    async def habits_list_to_complete(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Отображение списка привычек для выполнения

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :returns: Завершение диалога (если все привычки выполнены)
        :type: int или None
        :raises TGBotError: Если произошла ошибка при получении привычек
        """

        try:
            habits = self.db.get_user_habits(update.effective_user.id)

            if not habits:
                await self.reply(
                    update, config.no_habits_msg, keyboard=self.get_kb()
                )
                return
            kb = []
            for habit in habits:
                today = datetime.now().date().isoformat()
                last_comp = habit.get("last_completed", "")
                if not last_comp or last_comp != today:
                    kb.append(
                        [
                            f"☑️ {habit.get("name", "Не найдено")} (ID: {habit.get("id", 0)})"
                        ]
                    )
            if not kb:
                await self.reply(
                    update,
                    "Все привычки на сегодня выполнены! Вы молодец",
                    self.get_kb(),
                )
                return ConversationHandler.END
            kb.append([config.back_btn_text])

            await self.reply(
                update,
                "Какую привычку вы хотите выполнить?",
                ReplyKeyboardMarkup(kb, resize_keyboard=True),
            )
        except Exception as e:
            await self.reply(
                update,
                "Ошибка выполнения привычки",
                self.get_kb(),
            )
            raise TGBotError(f"Error get habits list to complete: {e}")

    async def complete_habit(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Обработчик выполнения привычки

        :param update: Объект обновления от Telegram
        :type update: Update
        :param ctx: Контекст выполнения
        :type ctx: ContextTypes.DEFAULT_TYPE
        :returns: Завершение диалога
        :type: int
        :raises TGBotError: Если привычка не найдена или уже выполнена сегодня
        """

        if update.message.text == config.back_btn_text:
            await self.cancel_command(update, ctx)
            return ConversationHandler.END

        hid = self.get_habit_id(update.message.text)

        try:
            res = self.db.complete_habit(hid, update.effective_user.id)
            await self.reply(
                update,
                f'Поздравляем! Привычка {res["name"]} выполнена!\n\nВы делаете это уже {res["current_streak"]} дней подряд!\n\nПродолжайте в том же духе!',
            )
        except Exception as e:
            if "not found" in str(e):
                await self.reply(
                    update,
                    "Привычка не найдена, проверьте введенные данные!",
                    keyboard=self.get_kb(),
                )
                raise TGBotError(f"Habit not found to complete")
            if "is completed today" in str(e):
                await self.reply(
                    update,
                    "Вы опережаете план, но привычка уже выполнена сегодня!",
                )
                raise TGBotError(f"Habit already completed today")
