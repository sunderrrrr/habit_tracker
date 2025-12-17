from db import Database
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters
import config
from exceptions import TGBotError
import re
from datetime import datetime
ADD_HABIT, DELETE_SELECT, DELETE_CONFIRM = range(3)
class Handler:
    
    """
    Инициализация обработчиков и основных методов класса Handler
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.kb = ReplyKeyboardMarkup(
            config.kb_btns,
            resize_keyboard=True,
            one_time_keyboard=False
        )
        
    def get_kb(self):
        return self.kb
    
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
    
    def get_message_handlers(self):
        return [
             MessageHandler(filters.Text("📋 Мои привычки"), self.habits_list),
             MessageHandler(filters.Text("🗑️ Удалить привычку"), self.habits_list_to_delete),
             MessageHandler(filters.Text("✅ Выполнить привычку"), self.habits_list_to_complete),
            MessageHandler(filters.Regex(r'☑️ .*\(ID: \d+\)'), self.complete_habit),
        ]
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
                MessageHandler(filters.Text(config.back_btn_text), self.cancel_command),
                CommandHandler("cancel", self.cancel_command)
            ]
        )
        delete_habit_dialog = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex(r'🗑️ .*\(ID: \d+\)'), self.delete_confirm)
            ],
            states={
                DELETE_SELECT: [
                    MessageHandler(filters.Regex(r'🗑️ .*\(ID: \d+\)'), self.delete_confirm),
                    MessageHandler(filters.Text(config.back_btn_text), self.cancel_command)
                ],
                DELETE_CONFIRM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.delete_process)
                ],
            },
            fallbacks=[
                MessageHandler(filters.Text(config.back_btn_text), self.cancel_command),
                CommandHandler("cancel", self.cancel_command)
            ]
        )
        return [add_habit_dialog, delete_habit_dialog]
    
    """
    Реализация методов добавления привычки
    """
    
    #"ручка" вызова метода добавления привычки
    async def start_add_habit(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        
        return await self.add_habit(update)
    
    #метод прослойка для изменения состояния диалога
    async def add_habit(self, update: Update):
        
            back_keyboard = ReplyKeyboardMarkup([[config.back_btn_text]], resize_keyboard=True)
            await self.reply(update, "Введите название привычки: ", back_keyboard)
            return ADD_HABIT
        
    #основная реализация функционала по добавлению привычки 
    async def set_habit_name(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        
        habit_name = update.message.text
        if habit_name == config.back_btn_text:
            await self.reply(update, "Отмена добавления привычки")
            return ConversationHandler.END
        try:
            self.db.add_habit(update.effective_user.id, habit_name)
        except Exception as e:
            raise TGBotError(f"Error: {e}")
        await self.reply(update, f"Привычка '{habit_name}' добавлена!")
        return ConversationHandler.END
    
    """
    Метод получения и форматированного вывода всех привычек пользователя
    """

    async def habits_list(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        
        try:
            habits = self.db.get_user_habits(update.effective_user.id)
            
            if not habits:
                await self.reply(update,
                    config.no_habits_msg,
                    keyboard=self.get_kb()
                )
                return
            
            message = "📋Ваши привычки:\n\n"
            
            for habit in habits:
                streak = habit['current_streak']
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
                last_date = habit['last_completed'] or "Никогда"
                new_date = ""
                if last_date != "Никогда":
                    last_date = str(last_date).split("-")
                    new_date = f"{last_date[2]}.{last_date[1]}.{last_date[0]}"
                else:
                    new_date = last_date
                message += f"""{emoji} {habit['name']}\n\n Статистика: \n\n📅 Серия: {streak} дней\n📊 Всего выполнено: {habit['total_completions']} раз\n🗓️ Последнее выполнение: {new_date}\n#️⃣ ID: {habit["id"]}\n\n"""
            
            await self.reply(update,
                message,
                keyboard=self.get_kb(),
            )
            
        except Exception as e:
            await self.reply(update, "Ошибка вывода списка привычек")
            raise TGBotError(f"Error: {e}")
        
    """
    Реализация обработчиков и логики удаления привычек
    """        

    async def habits_list_to_delete(self,  update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            habits = self.db.get_user_habits(update.effective_user.id)  
            if not habits:
                await self.reply(update, 
                                config.no_habits_to_delete_msg,
                                self.get_kb())
                return
            kb = []
            for habit in habits:
                kb.append([f"🗑️ {habit['name']} (ID: {habit['id']})"])            
            kb.append([config.back_btn_text])
            await self.reply(update, "Какую привычку вы хотите удалить?",
                    ReplyKeyboardMarkup(kb, resize_keyboard=True)
            )
        except Exception as e:
            await self.reply(update, "Ошибка вывода списка привычек для удаления")
            raise TGBotError(f"Habit delete error: {e}")
    
    async def delete_confirm(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        
        if update.message.text == "Нет, я передумал":
            await self.reply(update, "Удаление отменено!", keyboard=self.get_kb())
            return ConversationHandler.END
        match = re.search(r'\(ID: (\d+)\)', update.message.text)
        if not match:
            await self.reply(update, "Неверный формат данных", keyboard=self.get_kb())
            raise TGBotError(f"Invalid input data: {match}")
        
        hid = int(match.group(1))
        ctx.user_data["habit_to_del"] = hid
        habit_name = update.message.text.replace("🗑️ ", "").split(" (ID:")[0]
        
        confirm_btns = [["Да, удалить", "Нет, я передумал"], [config.back_btn_text]]
        await self.reply(update,
        f"Вы уверены что хотите удалить привычку '{habit_name}'?\n\nЭто действие не может быть прервано!", 
        keyboard=ReplyKeyboardMarkup(confirm_btns, resize_keyboard=True))
        
        return DELETE_CONFIRM
    
    
    async def delete_process(self, update: Update, ctx:ContextTypes.DEFAULT_TYPE):
        try:
            if update.message.text == "Нет, я передумал":
                await self.reply(update, "Удаление отменено!", keyboard=self.get_kb())
                return ConversationHandler.END
            
            if update.message.text == config.back_btn_text:
                await self.reply(update, "Удаление отменено!", keyboard=self.get_kb())
                return ConversationHandler.END
            
            if update.message.text != "Да, удалить":
                await self.reply(update, "Пожалуйста, выберите один из предложенных вариантов")
                return DELETE_CONFIRM
            
            hid = ctx.user_data.get("habit_to_del")
            if not hid:
                await self.reply(update, "Привычка не найдена", keyboard=self.get_kb())
                return ConversationHandler.END
            
            is_deleted = self.db.delete_habit(update.effective_user.id, hid)
            if is_deleted:
                await self.reply(update, "Привычка успешно удалена", keyboard=self.get_kb())
                
            else:
                await self.reply(update, "Привычка не найдена", keyboard=self.get_kb())
                return ConversationHandler.END

            return ConversationHandler.END
            
        except Exception as e:
            raise TGBotError(f"Habit delete error: {e}")
    
    """
    Реализация логики выполнения привычки
    """
    
    async def habits_list_to_complete(self, update:Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            habits = self.db.get_user_habits(update.effective_user.id)
            
            if not habits:
                await self.reply(update, config.no_habits_msg, keyboard=self.get_kb())
                return
            kb = []
            for habit in habits:
                today = datetime.now().date().isoformat()
                if habit["last_completed"] != today:
                    kb.append([f"☑️ {habit['name']} (ID: {habit['id']})"])      
            if not kb:
                await self.reply(update, "Все привычки на сегодня выполнены! Вы молодец")
                return ConversationHandler.END
            kb.append([config.back_btn_text])
            
            await self.reply(update, "Какую привычку вы хотите выполнить?",
                    ReplyKeyboardMarkup(kb, resize_keyboard=True)
            )
        except Exception as e:
            await self.reply(update, "Ошибка выполнения привычки",
                    ReplyKeyboardMarkup(kb, resize_keyboard=True)
            )
            raise TGBotError(f"Error get habits list to complete: {e}")
    
    async def complete_habit(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.message.text == config.back_btn_text:
            await self.cancel_command(update, ctx)
            return ConversationHandler.END
        match = re.search(r'\(ID: (\d+)\)', update.message.text)
        if not match:
            await self.reply(update, "Неверный формат ввода", keyboard=self.get_kb())
            return
        hid = int(match.group(1))
        
        try:
            res = self.db.complete_habit(hid, update.effective_user.id)
            await self.reply(update, f'Поздравляем! Привычка {res["name"]} выполнена!\n\nВы делаете это уже {res["current_streak"]} дней подряд!\n\nПродолжайте в том же духе!')
        except Exception as e:
            if "not found" in str(e):
                await self.reply(update, "Привычка не найдена, проверьте введенные данные!", keyboard=self.get_kb())
                raise TGBotError(f'Habit with id:{res["id"]} not found to complete')
            if "is completed today" in str(e):
                await self.reply(update, "Вы опережаете план, но привычка уже выполнена сегодня!")
                raise TGBotError(f'Habit with id:{res["id"]} already completed today')
            