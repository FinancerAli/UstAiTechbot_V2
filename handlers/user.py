from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

import database as db
from config import (
    ADMIN_IDS,
    CARD_NUMBER,
    CARD_OWNER,
    BOT_USERNAME,
    BONUS_JOIN,
    BONUS_ORDER_PCT,
    get_tier,
    TIER_LABELS,
    TIER_THRESHOLDS,
)
from locales import t
from keyboards.user_kb import (
    main_menu, lang_keyboard, categories_keyboard, services_keyboard,
    service_detail_keyboard, cancel_keyboard, skip_cancel_keyboard, rating_keyboard,
    STATUS_EMOJI,
)

SKIP_TEXTS = ["\u23ed O'tkazib yuborish", "\u23ed \u041f\u0440\u043e\u043f\u0443\u0441\u0442\u0438\u0442\u044c", "skip", "-", "o'tkazib yuborish"]
CANCEL_TEXTS = ["\u274c Bekor qilish", "\u274c \u041e\u0442\u043c\u0435\u043d\u0430"]

router = Router()


class OrderState(StatesGroup):
    waiting_quantity = State()
    waiting_coupon = State()
    waiting_note = State()
    waiting_receipt = State()


class ReviewState(StatesGroup):
    waiting_comment = State()


class SupportState(StatesGroup):
    message = State()


class SearchState(StatesGroup):
    query = State()


async def get_lang(user_id: int) -> str:
    user = await db.get_user(user_id)
    return (user["language"] or "uz") if user else "uz"


# -----------------------------------------------------------------------------
# NEW FEATURE: Referral status and Top Services handlers
# -----------------------------------------------------------------------------

@router.message(F.text.in_(["🎖 Referral", "🎖 Рефералы"]))
async def show_referral_status(message: Message):
    lang = await get_lang(message.from_user.id)
    user_id = message.from_user.id
    refs = await db.get_referral_count(user_id)
    tier_key = get_tier(refs)
    
    bot_me = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start=ref_{user_id}"

    if tier_key == "bronze":
        remaining = TIER_THRESHOLDS["silver"] - refs
        text = t(lang, "ref_status_bronze", remaining=remaining, current_bonus=BONUS_JOIN["bronze"], next_bonus=BONUS_JOIN["silver"], ref_link=ref_link)
    elif tier_key == "silver":
        remaining = TIER_THRESHOLDS["gold"] - refs
        text = t(lang, "ref_status_silver", remaining=remaining, current_bonus=BONUS_JOIN["silver"], next_bonus=BONUS_JOIN["gold"], ref_link=ref_link)
    else:
        text = t(lang, "ref_status_gold", current_bonus=BONUS_JOIN["gold"], ref_link=ref_link)

    await message.answer(text, parse_mode="HTML")


@router.message(F.text.in_(["💡 Yordam / FAQ", "💡 Помощь / FAQ"]))
async def show_faq(message: Message):
    lang = await get_lang(message.from_user.id)
    from locales import t
    await message.answer(t(lang, "faq_text"), parse_mode="HTML")

@router.message(F.text.in_(["⭐ Top xizmatlar", "⭐ Топ услуги", "⭐ Топ услуг"]))
async def show_top_services(message: Message):
    """
    Display a list of the most ordered services. If there are no orders,
    inform the user accordingly.
    """
    lang = await get_lang(message.from_user.id)
    # Fetch the top services from the database
    services = await db.get_top_services(limit=3)
    # If there are no orders or the highest order count is zero, show empty state
    if not services or services[0]["order_count"] == 0:
        await message.answer(t(lang, "no_top_services"))
        return
    # Construct the message header
    text = t(lang, "top_services_title")
    suffix = t(lang, "orders_suffix")
    for idx, svc in enumerate(services, start=1):
        # For each service, include its ranking, name and number of orders
        cnt = svc["order_count"]
        # Skip services with zero orders if they appear lower in the list
        if cnt == 0:
            continue
        text += f"{idx}. <b>{svc['name']}</b> — {cnt} {suffix}\n"
    await message.answer(text, parse_mode="HTML")


# START

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split(maxsplit=1)
    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1][4:]
        ref_user = await db.get_user_by_referral(ref_code)
        if ref_user and ref_user["id"] != message.from_user.id:
            referred_by = ref_user["id"]

    user = await db.get_user(message.from_user.id)
    is_new = user is None
    await db.save_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name, referred_by)

    if referred_by and is_new:
        ref_user = await db.get_user(referred_by)
        if ref_user:
            lang_ref = ref_user["language"] or "uz"
            ref_count = await db.get_referral_count(referred_by)
            tier = get_tier(ref_count)
            bonus_amount = BONUS_JOIN[tier]
            await db.add_bonus(referred_by, bonus_amount, f"Yangi a'zo: {message.from_user.full_name}")
            updated_ref = await db.get_user(referred_by)
            new_balance = updated_ref["bonus_balance"] if updated_ref else 0
            tier_label = TIER_LABELS[tier][lang_ref]
            try:
                await message.bot.send_message(
                    referred_by,
                    t(lang_ref, "referral_bonus_notify",
                      name=message.from_user.full_name,
                      amount=bonus_amount,
                      balance=new_balance),
                    parse_mode="HTML",
                )
                
                if ref_count == TIER_THRESHOLDS["silver"]:
                    await message.bot.send_message(
                        referred_by,
                        "🎉 Tabriklaymiz! Siz yuborgan havolangiz orqali 5 ta do'stingiz botdan ro'yxatdan o'tdi va siz Kumush darajasiga ko'tarildingiz! Endi xaridlaringiz yanada daromadli.",
                        parse_mode="HTML"
                    )
                elif ref_count == TIER_THRESHOLDS["gold"]:
                    await message.bot.send_message(
                        referred_by,
                        "🎉 Tabriklaymiz! Siz yuborgan havolangiz orqali 10 ta do'stingiz botdan ro'yxatdan o'tdi va siz Oltin darajasiga ko'tarildingiz! Endi xaridlaringiz yanada daromadli.",
                        parse_mode="HTML"
                    )
            except Exception:
                pass

    user = await db.get_user(message.from_user.id)
    if is_new or not user or not user["language"]:
        await message.answer(t("uz", "choose_lang"), reply_markup=lang_keyboard())
        return

    lang = user["language"] or "uz"
    await message.answer(
        t(lang, "welcome", name=message.from_user.full_name),
        reply_markup=main_menu(lang),
        parse_mode="HTML",
    )


async def abandoned_cart_job(user_id: int, order_id: int, bot: Bot, lang: str):
    await asyncio.sleep(900)  # 15 minutes trigger
    try:
        from database import get_order
        order = await get_order(order_id)
        if order and order['status'] == 'pending':
            from locales import t
            await bot.send_message(user_id, t(lang, "remarketing_text"), parse_mode="HTML")
    except Exception:
        pass


# LANGUAGE

@router.callback_query(F.data.startswith("set_lang:"))
async def set_language(call: CallbackQuery):
    lang = call.data.split(":")[1]
    await db.set_user_language(call.from_user.id, lang)
    await call.answer()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        t(lang, "welcome", name=call.from_user.full_name),
        reply_markup=main_menu(lang),
        parse_mode="HTML",
    )


@router.message(F.text.in_(["🌐 Til", "🌐 Язык"]))
async def change_lang(message: Message):
    await message.answer(t("uz", "choose_lang"), reply_markup=lang_keyboard())


@router.message(F.text.in_(["💬 Operatorga yozish", "💬 Написать оператору"]))
async def support_start(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(SupportState.message)
    await message.answer(t(lang, "support_ask"), parse_mode="HTML", reply_markup=cancel_keyboard(lang))


@router.message(SupportState.message)
async def support_message_receive(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if message.text in CANCEL_TEXTS:
        await state.clear()
        await message.answer(t(lang, "action_canceled"), reply_markup=main_menu(lang))
        return

    from keyboards.admin_kb import support_reply_keyboard
    admin_text = (
        f"📩 <b>Yangi murojaat:</b>\n"
        f"👤 User: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n\n"
        f"💬 <b>Xabar:</b>\n{message.text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                int(admin_id),
                admin_text,
                reply_markup=support_reply_keyboard(message.from_user.id, message.message_id),
                parse_mode="HTML"
            )
        except Exception:
            pass

    await state.clear()
    await message.answer(t(lang, "support_sent"), reply_markup=main_menu(lang))


# CATEGORIES / SERVICES

@router.message(F.text.in_(["🛍 Xizmatlar", "🛍 Услуги"]))
async def show_categories(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    categories = await db.get_categories()
    stats = await db.get_stats()
    confirmed = stats["confirmed"]
    if not categories:
        services = await db.get_services(only_active=True, limit=10, offset=0)
        total_count = await db.get_services_count(only_active=True)
        if not services:
            await message.answer(t(lang, "no_services"))
            return
        await message.answer(t(lang, "services_list", confirmed_orders=confirmed), reply_markup=services_keyboard(services, lang, page=1, total_count=total_count), parse_mode="HTML")
        return
    await message.answer(t(lang, "categories_list", confirmed_orders=confirmed), reply_markup=categories_keyboard(categories, lang), parse_mode="HTML")


@router.callback_query(F.data == "back_categories")
async def back_to_categories(call: CallbackQuery):
    await call.answer()
    lang = await get_lang(call.from_user.id)
    categories = await db.get_categories()
    stats = await db.get_stats()
    confirmed = stats["confirmed"]
    if not categories:
        services = await db.get_services(only_active=True, limit=10, offset=0)
        total_count = await db.get_services_count(only_active=True)
        await call.message.edit_text(t(lang, "services_list", confirmed_orders=confirmed), reply_markup=services_keyboard(services, lang, page=1, total_count=total_count), parse_mode="HTML")
        return
    await call.message.edit_text(t(lang, "categories_list", confirmed_orders=confirmed), reply_markup=categories_keyboard(categories, lang), parse_mode="HTML")


@router.message(F.text.in_(["🔍 Qidiruv", "🔍 Поиск"]))
async def search_start(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(SearchState.query)
    await message.answer(t(lang, "search_prompt"), reply_markup=cancel_keyboard(lang))


@router.message(SearchState.query)
async def search_execute(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    if message.text in CANCEL_TEXTS:
        await state.clear()
        await message.answer(t(lang, "action_canceled"), reply_markup=main_menu(lang))
        return
    query = message.text.strip().lower()
    await state.clear()
    services = await db.get_services(only_active=True, query=query, limit=10, offset=0)
    total_count = await db.get_services_count(only_active=True, query=query)
    if not services:
        await message.answer(t(lang, "search_empty"), reply_markup=main_menu(lang))
        return
    await message.answer(
        f"🔍 <b>Qidiruv natijalari:</b> {total_count} ta topildi", 
        reply_markup=services_keyboard(services, lang, page=1, total_count=total_count, query=query), 
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_home")
async def back_home_callback(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    await call.message.delete()
    await call.message.answer(
        t(lang, "welcome", name=call.from_user.full_name),
        reply_markup=main_menu(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("page:"))
async def pagination_handler(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    parts = call.data.split(":", 2)
    page = int(parts[1])
    query = parts[2] if len(parts) > 2 else ""
    offset = (page - 1) * 10
    services = await db.get_services(only_active=True, query=query, limit=10, offset=offset)
    total_count = await db.get_services_count(only_active=True, query=query)
    if query:
        text = f"🔍 <b>Qidiruv natijalari:</b> {total_count} ta topildi (Sahifa {page})"
    else:
        text = t(lang, "services_list", confirmed_orders=(await db.get_stats())["confirmed"])

    await call.message.edit_text(
        text, 
        reply_markup=services_keyboard(services, lang, page=page, total_count=total_count, query=query), 
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("category:"))
async def show_category_services(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    cat_id = int(call.data.split(":")[1])
    services = await db.get_services(only_active=True, category_id=cat_id, limit=10, offset=0)
    total_count = await db.get_services_count(only_active=True, category_id=cat_id)
    cat = await db.get_category(cat_id)
    if not services:
        await call.answer(t(lang, "no_services"), show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(
        f"<b>{cat['name']}</b>\n\n{t(lang, 'category_services_list')}",
        reply_markup=services_keyboard(services, lang, page=1, total_count=total_count, query=""),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "back_services_list")
async def back_to_services_list(call: CallbackQuery):
    await call.answer()
    lang = await get_lang(call.from_user.id)
    categories = await db.get_categories()
    stats = await db.get_stats()
    confirmed = stats["confirmed"]
    if not categories:
        services = await db.get_services(only_active=True)
        await call.message.edit_text(t(lang, "services_list", confirmed_orders=confirmed), reply_markup=services_keyboard(services, lang), parse_mode="HTML")
        return
    await call.message.edit_text(t(lang, "categories_list", confirmed_orders=confirmed), reply_markup=categories_keyboard(categories, lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("service:"))
async def service_detail(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    service_id = int(call.data.split(":")[1])
    s = await db.get_service(service_id)
    if not s:
        await call.answer(t(lang, "service_not_found"), show_alert=True)
        return
    await call.answer()
    avg, cnt = await db.get_service_avg_rating(service_id)
    rating_text = t(lang, "rating_info", avg=avg, cnt=cnt) if cnt else ""
    s_dict = dict(s)
    if lang == "ru":
        desc = s_dict.get("description_ru") or s_dict.get("description_uz") or s_dict.get("description") or "-"
    else:
        desc = s_dict.get("description_uz") or s_dict.get("description") or "-"
    
    badge = ""
    if avg >= 4.5: badge = f"{t(lang, 'badge_rec')} | "
    elif cnt > 10: badge = f"{t(lang, 'badge_top')} | "

    cb_text = ""
    if dict(s).get("promo_active"):
        perc = s['cashback_percent']
        perc_fmt = int(perc) if perc == int(perc) else perc
        cb_bonus = int(s['price'] * perc / 100)
        cb_text = f"\n{t(lang, 'cb_perc', percent=perc_fmt)}\n{t(lang, 'cb_amount', amount=cb_bonus)}\n"


    tiers = await db.get_bulk_prices(service_id)
    bulk_text = ""
    if tiers:
        bulk_text = f"\n{t(lang, 'bulk_title')}"
        for t_ in tiers:
            bulk_text += t(lang, 'bulk_tier', min=t_['min_quantity'], price=t_['price_per_unit'])
        bulk_text += "\n"
        
    onetime_suffix = " (bir martalik)" if lang == "uz" else " (единоразово)"
    price_text = f"{t(lang, 'service_price', price=s['price'])}{onetime_suffix}\n"
    stock_txt = (t(lang, 'stock_avail', count=s['stock']) + "\n") if s['stock'] > 0 else (f"\n{t(lang, 'stock_empty')}\n")
    urgency = f"\n{t(lang, 'urgency')}"

    text = (
        f"<b>1️⃣ {t(lang, 'services')} \u2192</b>\n\n"
        f"\U0001f4e6 <b>{badge}{s['name']}</b>\n\n"
        f"{desc}\n\n"
        f"{price_text}"
        f"{cb_text}"
        f"{bulk_text}"
        f"{stock_txt}"
        f"{rating_text}"
        f"{urgency}"
    )
    if s["image_file_id"]:
        await call.message.answer_photo(
            s["image_file_id"],
            caption=text,
            reply_markup=service_detail_keyboard(service_id, lang, s["stock"]),
            parse_mode="HTML",
        )
    else:
        await call.message.edit_text(text, reply_markup=service_detail_keyboard(service_id, lang, s["stock"]), parse_mode="HTML")


# ORDER FLOW

@router.callback_query(F.data.startswith("order:"))
async def start_order(call: CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    service_id = int(call.data.split(":")[1])
    s = await db.get_service(service_id)
    if not s:
        await call.answer(t(lang, "service_not_found"), show_alert=True)
        return
    if s["stock"] <= 0:
        await call.answer(t(lang, "out_of_stock"), show_alert=True)
        return
    await call.answer()
    await state.update_data(service_id=service_id, service_name=s["name"], base_price=s["price"], lang=lang)
    
    from keyboards.user_kb import quantity_keyboard
    q_txt = "Iltimos, xarid miqdorini tanlang:" if lang == "uz" else "Пожалуйста, выберите количество покупок:"
    text = f"<b>{t(lang, 'step_2')} \u2192</b>\n\n{q_txt}"
    await call.message.answer(text, reply_markup=quantity_keyboard(service_id, lang), parse_mode="HTML")

@router.callback_query(F.data.startswith("qty:"))
async def receive_preset_quantity(call: CallbackQuery, state: FSMContext):
    _, service_id_str, qty_str = call.data.split(":")
    qty = int(qty_str)
    
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    s = await db.get_service(int(service_id_str))
    if s["stock"] != -1 and qty > s["stock"]:
        await call.answer(t(lang, "stock_error", stock=s["stock"]), show_alert=True)
        return
        
    await call.message.delete()
        
    unit_price = await db.get_price_for_quantity(int(service_id_str), qty, data["base_price"])
    total_price = unit_price * qty
    
    await state.update_data(quantity=qty, price=total_price, unit_price=unit_price)
    
    await state.set_state(OrderState.waiting_coupon)
    text = f"<b>{t(lang, 'step_3')} \u2192</b>\n\n💰 {qty} ta x {unit_price:,} so'm = <b>{total_price:,} so'm</b>\n\n{t(lang, 'coupon_ask')}"
    from keyboards.user_kb import skip_cancel_keyboard
    await call.message.answer(text, reply_markup=skip_cancel_keyboard(lang), parse_mode="HTML")

@router.callback_query(F.data.startswith("qty_custom:"))
async def receive_custom_quantity(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    await call.message.delete()
    
    await state.set_state(OrderState.waiting_quantity)
    text = t(lang, "ask_custom_quantity")
    from keyboards.user_kb import cancel_keyboard
    await call.message.answer(text, reply_markup=cancel_keyboard(lang), parse_mode="HTML")

@router.callback_query(F.data == "cancel_quantity_prompt")
async def cancel_quantity_prompt(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer("Bekor qilindi")

@router.message(OrderState.waiting_quantity)
async def receive_quantity(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if message.text in CANCEL_TEXTS:
        await state.clear()
        await message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang))
        return
        
    try:
        qty = int(message.text)
        if qty <= 0: raise ValueError
    except ValueError:
        await message.answer(t(lang, "invalid_quantity"))
        return
        
    s = await db.get_service(data["service_id"])
    if s["stock"] != -1 and qty > s["stock"]:
        await message.answer(t(lang, "stock_error", stock=s["stock"]))
        return
        
    unit_price = await db.get_price_for_quantity(data["service_id"], qty, data["base_price"])
    total_price = unit_price * qty
    
    await state.update_data(quantity=qty, price=total_price, unit_price=unit_price)
    
    await state.set_state(OrderState.waiting_coupon)
    text = f"<b>{t(lang, 'step_3')} \u2192</b>\n\n" + (
        f"\U0001f4b0 {qty} ta x {unit_price:,} so'm = <b>{total_price:,} so'm</b>\n\n" if qty > 1 else ""
    ) + t(lang, 'coupon_ask')
    await message.answer(text, reply_markup=skip_cancel_keyboard(lang), parse_mode="HTML")


@router.message(OrderState.waiting_coupon)
async def receive_coupon(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if message.text in CANCEL_TEXTS:
        await state.clear()
        await message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang))
        return
    discount = 0
    coupon_code = None
    if message.text not in SKIP_TEXTS:
        coupon = await db.get_coupon(message.text.strip())
        if coupon:
            discount = coupon["discount_percent"]
            coupon_code = coupon["code"]
            price = data["price"]
            final = price - (price * discount // 100)
            await message.answer(t(lang, "coupon_applied", discount=discount, final=final), parse_mode="HTML")
        else:
            await message.answer(t(lang, "coupon_invalid"), parse_mode="HTML")
            return
    # Auto-apply bonus
    user = await db.get_user(message.from_user.id)
    balance = (user["bonus_balance"] or 0) if user else 0
    price = data["price"]
    price_after_coupon = price - (price * discount // 100)
    bonus_used = min(balance, price_after_coupon)
    final_after_bonus = price_after_coupon - bonus_used

    if bonus_used > 0:
        if final_after_bonus == 0:
            await message.answer(t(lang, "bonus_full_cover", amount=bonus_used), parse_mode="HTML")
        else:
            await message.answer(t(lang, "bonus_applied", amount=bonus_used, final=final_after_bonus), parse_mode="HTML")

    await state.update_data(discount=discount, coupon_code=coupon_code, bonus_used=bonus_used)
    await state.set_state(OrderState.waiting_note)
    text = f"<b>{t(lang, 'step_2')} \u2192</b>\n\n{t(lang, 'order_note', name=data['service_name'])}"
    await message.answer(text, reply_markup=skip_cancel_keyboard(lang), parse_mode="HTML")


@router.message(OrderState.waiting_note)
async def receive_note(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if message.text in CANCEL_TEXTS:
        bonus_used = data.get("bonus_used", 0) or 0
        if bonus_used > 0:
            await db.add_bonus(message.from_user.id, bonus_used, "Buyurtma bekor qilindi (izoh bosqichi)")
        await state.clear()
        await message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang))
        return
    note = "" if message.text in SKIP_TEXTS else message.text
    discount = data.get("discount", 0)
    coupon_code = data.get("coupon_code")
    bonus_used = data.get("bonus_used", 0) or 0
    price = data["price"]
    final_price = max(0, price - (price * discount // 100) - bonus_used)
    order_id = await db.create_order(
        user_id=message.from_user.id,
        service_id=data["service_id"],
        service_name=data["service_name"],
        price=price,
        note=note,
        discount=discount,
        final_price=final_price,
        coupon_code=coupon_code,
        bonus_used=bonus_used,
        quantity=data.get("quantity", 1),
    )
    await db.decrease_stock(data["service_id"], amount=data.get("quantity", 1))
    if coupon_code:
        await db.use_coupon(coupon_code)
    if bonus_used > 0:
        await db.use_bonus(message.from_user.id, bonus_used, f"Buyurtma #{order_id}")

    import keyboards.admin_kb as adm_kb
    username = message.from_user.username or "nomalum"
    discount_text = f"\nChegirma: {discount}% | Yakuniy: {final_price:,} so'm" if discount else ""
    bonus_text = f"\n\U0001f381 Bonus: {bonus_used:,} so'm" if bonus_used else ""

    if final_price == 0:
        # Bonus covers full price — no payment needed
        await state.clear()
        await message.answer(t(lang, "order_accepted_free", order_id=order_id), reply_markup=main_menu(lang), parse_mode="HTML")
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"\U0001f514 <b>Yangi buyurtma #{order_id}</b> (Bonus bilan to'liq to'langan)\n\n"
                    f"\U0001f464 @{username} (<code>{message.from_user.id}</code>)\n"
                    f"\U0001f6cd {data['service_name']}\n"
                    f"\U0001f4b0 {price:,} so'm{discount_text}{bonus_text}\n"
                    f"\U0001f4dd {note or '—'}",
                    reply_markup=adm_kb.order_action_keyboard(order_id),
                    parse_mode="HTML",
                )
            except Exception:
                pass
    else:
        await state.update_data(order_id=order_id, final_price=final_price)
        await state.set_state(OrderState.waiting_receipt)
        text = f"<b>{t(lang, 'step_3')} \u2192</b>\n\n{t(lang, 'payment_info', price=final_price, card=CARD_NUMBER, owner=CARD_OWNER)}"
        await message.answer(
            text,
            reply_markup=cancel_keyboard(lang),
            parse_mode="HTML",
        )
        asyncio.create_task(abandoned_cart_job(message.from_user.id, order_id, message.bot, lang))


@router.message(OrderState.waiting_receipt, F.photo)
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    order_id = data["order_id"]
    file_id = message.photo[-1].file_id
    await db.set_order_receipt(order_id, file_id)
    await state.clear()
    await message.answer(
        t(lang, "order_accepted", order_id=order_id),
        reply_markup=main_menu(lang),
        parse_mode="HTML",
    )
    order = await db.get_order(order_id)
    import keyboards.admin_kb as adm_kb
    for admin_id in ADMIN_IDS:
        try:
            username = message.from_user.username or "nomalum"
            discount_text = f"\nChegirma: {order['discount']}% | Yakuniy: {order['final_price']:,} so'm" if order["discount"] else ""
            bonus_text = f"\n\U0001f381 Bonus: {order['bonus_used']:,} so'm" if (order["bonus_used"] or 0) > 0 else ""
            text = (
                f"\U0001f514 <b>Yangi buyurtma #{order_id}</b>\n\n"
                f"\U0001f464 @{username} (<code>{message.from_user.id}</code>)\n"
                f"\U0001f6cd {order['service_name']}\n"
                f"\U0001f4b0 {order['price']:,} so'm{discount_text}{bonus_text}\n"
                f"\U0001f4dd {order['note'] or '—'}"
            )
            await bot.send_photo(
                admin_id, file_id,
                caption=text,
                reply_markup=adm_kb.order_action_keyboard(order_id),
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.message(OrderState.waiting_receipt)
async def receipt_not_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if message.text in CANCEL_TEXTS:
        order_id = data.get("order_id")
        if order_id:
            await db.update_order_status(order_id, "cancelled")
            order = await db.get_order(order_id)
            if order:
                await db.increase_stock(order["service_id"])
                bonus_used = order["bonus_used"] or 0
                if bonus_used > 0:
                    await db.add_bonus(message.from_user.id, bonus_used, f"Buyurtma #{order_id} bekor qilindi")
        await state.clear()
        await message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang))
        return
    await message.answer(t(lang, "send_photo_receipt"), parse_mode="HTML")


# MY ORDERS

@router.message(F.text.in_(["📦 Buyurtmalarim", "📦 Мои заказы"]))
async def my_orders(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    orders = await db.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(t(lang, "no_orders"))
        return
    text = t(lang, "orders_list")
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "?")
        fp = o["final_price"] or o["price"]
        text += f"{emoji} <b>#{o['id']}</b> — {o['service_name']}\n   {fp:,} so'm | {o['created_at'][:10]}\n\n"
    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if order and order["user_id"] == call.from_user.id and order["status"] == "pending":
        await db.update_order_status(order_id, "cancelled")
        await db.increase_stock(order["service_id"])
        bonus_used = order["bonus_used"] or 0
        if bonus_used > 0:
            await db.add_bonus(call.from_user.id, bonus_used, f"Buyurtma #{order_id} bekor qilindi")
        await call.answer(t(lang, "order_cancelled"), show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
    else:
        await call.answer(t(lang, "order_cancel_forbidden"), show_alert=True)


# PROFILE

@router.message(F.text.in_(["👤 Profil", "👤 Профиль"]))
async def show_profile(message: Message):
    lang = await get_lang(message.from_user.id)
    user = await db.get_user(message.from_user.id)
    orders = await db.get_user_orders(message.from_user.id)
    spent = await db.get_user_total_spent(message.from_user.id)
    refs = await db.get_referral_count(message.from_user.id)
    ref_code = user["referral_code"] if user else ""
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{ref_code}" if BOT_USERNAME and ref_code else ref_code
    bonus = (user["bonus_balance"] or 0) if user else 0
    total_cashback = await db.get_user_total_cashback(message.from_user.id)
    tier = get_tier(refs)
    tier_label = TIER_LABELS[tier][lang]
    await message.answer(
        t(lang, "profile_text",
          user_id=message.from_user.id,
          full_name=message.from_user.full_name,
          orders=len(orders),
          spent=spent,
          referrals=refs,
          ref_link=ref_link) +
        t(lang, "profile_bonus", bonus=bonus, tier=tier_label) +
        t(lang, "profile_cashback", total=total_cashback),
        parse_mode="HTML",
    )


# REVIEW

@router.callback_query(F.data.startswith("rate:"))
async def rate_service(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    order_id, rating = int(parts[1]), int(parts[2])
    order = await db.get_order(order_id)
    lang = await get_lang(call.from_user.id)
    if not order:
        await call.answer(t(lang, "order_not_found"), show_alert=True)
        return
    if await db.review_exists(order_id):
        await call.answer(t(lang, "already_reviewed"), show_alert=True)
        return
    await call.answer()
    await state.update_data(order_id=order_id, rating=rating, service_id=order["service_id"], lang=lang)
    await state.set_state(ReviewState.waiting_comment)
    await call.message.edit_text(
        "\u2b50" * rating + f"\n\n{t(lang, 'rate_comment')}",
        parse_mode="HTML",
    )


@router.message(ReviewState.waiting_comment)
async def receive_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    comment = "" if message.text.strip() == "-" else message.text
    await db.add_review(data["order_id"], message.from_user.id, data["service_id"], data["rating"], comment)
    await state.clear()
    await message.answer(t(lang, "rate_thanks"), reply_markup=main_menu(lang))


@router.message(F.text.in_(["🎉 Aksiyalar", "🎉 Акции"]))
async def show_promos(message: Message):
    lang = await get_lang(message.from_user.id)
    promos = await db.get_active_service_promotions()
    if not promos:
        await message.answer("🎉 Hozircha aksiyalar yo'q. / Пока нет активных акций.")
        return
    text = "🎉 <b>Faol Aksiyalar / Активные акции:</b>\n\n"
    for p in promos:
        bonus = int(p["price"] * p["cashback_percent"] / 100)
        text += f"🛍 <b>{p['service_name']}</b>\n🎁 {p['title']} ({p['cashback_percent']}% cashback)\n💎 Kutilayotgan bonus: {bonus:,} so'm\n\n"
    await message.answer(text, parse_mode="HTML")


# CONTACT / ABOUT

@router.message(F.text.in_(["📞 Aloqa", "📞 Контакты"]))
async def contact(message: Message):
    lang = await get_lang(message.from_user.id)
    from keyboards.user_kb import contact_keyboard
    await message.answer(t(lang, "contact_text"), reply_markup=contact_keyboard(lang), parse_mode="HTML")


@router.message(F.text.in_(["ℹ️ Haqida", "ℹ️ О боте"]))
async def about(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "about_text"), parse_mode="HTML")
