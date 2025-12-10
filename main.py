import os
from telegram.ext import Application, CommandHandler
import logging
from db import Database
from handlers import Handler
import config
from exceptions import TGBotError
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

def main():
    #token = os.getenv("TG_BOT_TOKEN")
    token = "7998592901:AAGxEi2aB1tkCBhtckz4xFjtvmAwNKTlmIE"
    if not token:
        print(f"no any token in env file: {token}")
        return
    print("starting bot")
    db = Database(config.db_file)
    hndlr = Handler(db)
    app = Application.builder().token(token).build()
    try:
        app.add_handler(CommandHandler("start", hndlr.start))
        app.add_handler(hndlr.get_conversation_handlers())
        app.run_polling()
    except Exception as e:
        logging.error(f"Bot init error: {e}")
        raise TGBotError(f"Bot init error: {e}")
if __name__ == "__main__":
    main()