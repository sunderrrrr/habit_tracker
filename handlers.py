from db import Database
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters
import config
from exceptions import TGBotError
ADD_HABIT, DELETE_CONFIRM = range(2)
class Handler:
    def __init__(self, db: Database):
        self.db = db
        self.kb = ReplyKeyboardMarkup(
            config.kb_btns,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    async def start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await self.reply(update, config.wellcome_msg)
    async def cancel_command(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await self.reply(update, "Действие отменено!")
        return ConversationHandler.END
    async def reply(self, update: Update, text:str, keyboard=None):
        try:
            await update.message.reply_text(
                text,
                reply_markup=keyboard or self.kb
            )
        except Exception as e:
            raise TGBotError(f"Ошибка отправки сообщения: {str(e)}")
    
    async def add_habit(self, update: Update):
            back_keyboard = ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            await self.reply(update, "Введите название привычки: ", back_keyboard)
            return ADD_HABIT
    async def start_add_habit(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        return await self.add_habit(update)
    async def set_habit_name(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        habit_name = update.message.text
        if habit_name == "⬅️ Назад":
            await self.reply(update, "Отмена добавления привычки.")
            return ConversationHandler.END
        try:
            self.db.add_habit(update.effective_user.id, habit_name)
        except Exception as e:
            raise TGBotError(f"Error: {e}")
        await self.reply(update, f"Привычка '{habit_name}' добавлена!")
        return ConversationHandler.END

    def get_conversation_handlers(self):
        add_habit_dialog = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Text("➕ Добавить привычку"), self.start_add_habit)
            ],
            
            states={
                ADD_HABIT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, 
                        self.set_habit_name
                    )
                ],
            },
                        fallbacks=[
                MessageHandler(filters.Text("⬅️ Назад"), self.cancel_command),
                CommandHandler("cancel", self.cancel_command)
            ]
        )
        return add_habit_dialog