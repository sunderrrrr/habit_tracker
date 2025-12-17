import os
from telegram.ext import Application, CommandHandler
import logging
from db import Database
from handlers import Handler
import config
from exceptions import TGBotError
from dotenv import load_dotenv

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)


def main():
    load_dotenv()
    token = os.getenv("TG_BOT_TOKEN")
    if not token:
        print(f"no any token in env file: {token}")
        return
    print("starting bot")
    db = Database(config.db_file)
    hndlr = Handler(db)
    app = Application.builder().token(token).build()
    try:
        app.add_handler(CommandHandler("start", hndlr.start))

        for msg_handler in hndlr.get_message_handlers():
            app.add_handler(msg_handler)
        for conv_handler in hndlr.get_conversation_handlers():
            app.add_handler(conv_handler)
        app.run_polling()
    except Exception as e:
        logging.error(f"Bot init error: {e}")
        raise TGBotError(f"Bot init error: {e}")


if __name__ == "__main__":
    main()
