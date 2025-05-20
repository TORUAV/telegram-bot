import os
import logging
from telegram import Update, Poll
from telegram.ext import Application, ChatMemberHandler, PollAnswerHandler, ContextTypes
import asyncio

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота и ID чата из переменных окружения
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RULES_LINK = "https://docs.google.com/document/d/1qeZiwRYSPC8xGu7_YGm-n8t6rdSX3fUrQREvatHJnFE/edit?tab=t.0#heading=h.9rz9952de7oc"

# Словарь для отслеживания опросов и времени их создания
active_polls = {}

async def greet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка новых участников группы"""
    try:
        chat_member = update.chat_member
        if chat_member.new_chat_member.status == "member" and chat_member.new_chat_member.user.id != context.bot.id:
            user_id = chat_member.new_chat_member.user.id
            username = chat_member.new_chat_member.user.username or chat_member.new_chat_member.user.first_name or "Новичок"
            if username.startswith("@"):
                username_display = username
            else:
                username_display = f"@{username}"
            logger.info(f"New user {username} ({user_id}) joined the group")

            # Отправляем опрос в группу
            question = f"Привет, {username_display}! До конца таймера (30 минут) тебе нужно изучить правила клуба по ссылке ниже и либо принять их, либо нет.\n\n{RULES_LINK}"
            options = ["Подтверждаю", "Не подтверждаю"]
            try:
                poll = await context.bot.send_poll(
                    chat_id=CHAT_ID,
                    question=question,
                    options=options,
                    is_anonymous=False,
                    allows_multiple_answers=False
                )
                # Сохраняем данные опроса
                active_polls[user_id] = {
                    "poll_id": poll.poll.id,
                    "chat_id": CHAT_ID,
                    "message_id": poll.message_id,
                    "username": username
                }
                logger.info(f"Poll sent for user {username} ({user_id}) in group")
            except Exception as e:
                logger.error(f"Failed to send poll for {username} ({user_id}): {e}")
                await context.bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"❌ Не удалось отправить опрос для {username_display}. Пожалуйста, начни диалог с ботом в личных сообщениях (/start) и попробуй снова."
                )
                return

            # Запускаем таймер на 30 минут
            await asyncio.sleep(30 * 60)  # 30 минут
            if user_id in active_polls:
                # Проверяем, ответил ли пользователь
                if active_polls[user_id]["poll_id"] not in context.bot_data.get("answered_polls", {}):
                    try:
                        await context.bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
                        await context.bot.send_message(
                            chat_id=CHAT_ID,
                            text=f"❌ Участник {username_display} не ответил вовремя и был удалён.",
                            reply_to_message_id=active_polls[user_id]["message_id"]
                        )
                        logger.info(f"User {username} ({user_id}) banned due to no response")
                    except Exception as e:
                        logger.error(f"Error banning user {username} ({user_id}): {e}")
                    del active_polls[user_id]
    except Exception as e:
        logger.error(f"Error in greet_user: {e}")

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на опрос"""
    try:
        poll_answer = update.poll_answer
        user_id = poll_answer.user.id
        poll_id = poll_answer.poll_id
        option = poll_answer.option_ids[0]  # 0 для "Подтверждаю", 1 для "Не подтверждаю"
        username = active_polls.get(user_id, {}).get("username", "User")
        username_display = f"@{username}" if not username.startswith("@") else username

        if user_id in active_polls and active_polls[user_id]["poll_id"] == poll_id:
            if option == 1:  # Пользователь выбрал "Не подтверждаю"
                try:
                    await context.bot.ban_chat_member(
                        chat_id=active_polls[user_id]["chat_id"],
                        user_id=user_id
                    )
                    await context.bot.send_message(
                        chat_id=active_polls[user_id]["chat_id"],
                        text=f"❌ Участник {username_display} не принял правила и был удалён.",
                        reply_to_message_id=active_polls[user_id]["message_id"]
                    )
                    logger.info(f"User {username} ({user_id}) banned for selecting 'Не подтверждаю'")
                except Exception as e:
                    logger.error(f"Error banning user {username} ({user_id}): {e}")
            else:  # Пользователь выбрал "Подтверждаю"
                await context.bot.send_message(
                    chat_id=active_polls[user_id]["chat_id"],
                    text=f"✅ {username_display} принял(а) правила и присоединился(ась) к клубу!",
                    reply_to_message_id=active_polls[user_id]["message_id"]
                )
                logger.info(f"User {username} ({user_id}) accepted rules")
            # Отмечаем, что пользователь ответил
            context.bot_data.setdefault("answered_polls", {})[poll_id] = True
            del active_polls[user_id]
    except Exception as e:
        logger.error(f"Error in handle_poll_answer: {e}")

async def main():
    """Основная функция для запуска бота"""
    try:
        application = Application.builder().token(TOKEN).build()

        # Обработчик новых участников
        application.add_handler(ChatMemberHandler(greet_user, ChatMemberHandler.CHAT_MEMBER))
        # Обработчик ответов на опрос
        application.add_handler(PollAnswerHandler(handle_poll_answer))

        logger.info("Starting bot...")
        await application.run_polling()
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())