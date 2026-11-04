import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# Токен бота (получи у @BotFather)
BOT_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("write"))
async def cmd_write(message: Message):
    # Получаем текст после команды
    # message.text = "/write привет"
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer("⚠️ Использование: /write <текст>\nПример: /write привет")
        return
    
    user_text = parts[1]
    
    # Отправляем сообщение от бота
    await message.answer(user_text)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я бот.\n\n"
        "Команды:\n"
        "/write <текст> — отправлю твой текст обратно\n\n"
        "Пример: /write привет"
    )


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())