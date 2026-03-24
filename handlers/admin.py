from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import datetime

import database as db
from config import ADMIN_IDS, BONUS_ORDER_PCT, get_tier, TIER_LABELS
from keyboards.admin_kb import (
    admin_menu, services_manage_keyboard, service_admin_detail,
    order_action_keyboard, cancel_keyboard, confirm_delete_keyboard,
    categories_manage_keyboard, coupons_keyboard, delivery_choose_keyboard,
    bonus_manage_keyboard,
)
from keyboards.user_kb import main_menu, STATUS_EMOJI
from utils.excel import generate_orders_excel
from utils.backup import send_backup

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# STATES

class AddServiceState(StatesGroup):
    category = State()
    name = State()
    description_uz = State()
    description_ru = State()
    price = State()
    stock = State()
    image = State()
    delivery = State()


class EditServiceStockState(StatesGroup):
    stock = State()


class AdminSupportReplyState(StatesGroup):
    user_id = State()
    message = State()


class EditServiceState(StatesGroup):
    name = State()
    description_uz = State()
    description_ru = State()
    price = State()


class BroadcastState(StatesGroup):
    message = State()


class BlockState(StatesGroup):
    user_id = State()


class AddCouponState(StatesGroup):
    code = State()
    discount = State()
    max_uses = State()


class AddCategoryState(StatesGroup):
    name = State()


class BonusManageState(StatesGroup):
    user_id = State()
    amount = State()
    action = State()


class AdminReplyState(StatesGroup):
    message = State()


class SetDeliveryState(StatesGroup):
    content = State()


class DeliveryCustomState(StatesGroup):
    message = State()


class PromoAddState(StatesGroup):
    title = State()
    text = State()
    image = State()


class PromoCashbackState(StatesGroup):
    title = State()
    percent = State()


# ADMIN PANEL

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("\U0001f468\u200d\U0001f4bc <b>Admin panel</b>", reply_markup=admin_menu(), parse_mode="HTML")


@router.message(F.text == "\U0001f519 Foydalanuvchi menyusi")
async def back_to_user(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Foydalanuvchi menyusi", reply_markup=main_menu())


# STATISTICS

@router.message(F.text == "\U0001f4ca Statistika")
async def statistics(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = await db.get_stats()
    await message.answer(
        f"\U0001f4ca <b>Statistika:</b>\n\n"
        f"\U0001f465 Foydalanuvchilar: <b>{stats['users']}</b>\n"
        f"\U0001f4e6 Jami buyurtmalar: <b>{stats['total_orders']}</b>\n"
        f"\u23f3 Kutilayotgan: <b>{stats['pending']}</b>\n"
        f"\u2705 Tasdiqlangan: <b>{stats['confirmed']}</b>\n"
        f"\u274c Rad etilgan: <b>{stats['rejected']}</b>\n"
        f"\U0001f4b0 Daromad: <b>{stats['revenue']:,} so'm</b>\n"
        f"📅 Bugungi daromad: <b>{stats['today_revenue']:,} so'm</b>\n"
        f"📈 Konversiya: <b>{stats['conversion']}%</b>",
        parse_mode="HTML",
    )


# PENDING ORDERS

@router.message(F.text == "\U0001f4cb Kutilayotgan buyurtmalar")
async def pending_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    orders = await db.get_pending_orders()
    if not orders:
        await message.answer("\u2705 Kutilayotgan buyurtmalar yo'q.")
        return
    await message.answer(f"\u23f3 <b>{len(orders)} ta kutilayotgan buyurtma:</b>", parse_mode="HTML")
    for o in orders:
        text = (
            f"\U0001f514 <b>Buyurtma #{o['id']}</b>\n"
            f"\U0001f464 {o['full_name'] or ''} @{o['username'] or 'nomalum'} (<code>{o['user_id']}</code>)\n"
            f"\U0001f6cd {o['service_name']}\n"
            f"\U0001f4b0 {o['price']:,} so'm\n"
            f"\U0001f4dd {o['note'] or '—'}\n"
            f"\U0001f4c5 {o['created_at'][:16]}"
        )
        if o["receipt_file_id"]:
            await message.answer_photo(o["receipt_file_id"], caption=text, reply_markup=order_action_keyboard(o["id"]), parse_mode="HTML")
        else:
            await message.answer(text + "\n\n\U0001f4f8 Chek yuborilmagan", reply_markup=order_action_keyboard(o["id"]), parse_mode="HTML")


# ALL ORDERS

@router.message(F.text == "\U0001f4dc Barcha buyurtmalar")
async def all_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    orders = await db.get_all_orders(50)
    if not orders:
        await message.answer("Buyurtmalar yo'q.")
        return
    text = "\U0001f4dc <b>So'nggi 50 ta buyurtma:</b>\n\n"
    for o in orders:
        emoji = STATUS_EMOJI.get(o["status"], "?")
        fp = o["final_price"] or o["price"]
        text += f"{emoji} <b>#{o['id']}</b> — {o['service_name']}\n   @{o['username'] or 'nomalum'} | {fp:,} so'm | {o['created_at'][:10]}\n\n"
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await message.answer(text, parse_mode="HTML")


# CONFIRM / REJECT

@router.callback_query(F.data.startswith("adm_confirm:"))
async def confirm_order(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return
    await db.update_order_status(order_id, "confirmed")
    await call.answer("\u2705 Tasdiqlandi!")
    await call.message.edit_reply_markup(reply_markup=None)

    final = order["final_price"] or order["price"]
    promo = await db.get_service_promo_admin(order["service_id"])
    cashback_text = ""
    if promo and promo["is_active"] and order.get("cashback_awarded", 0) == 0:
        cashback_bonus = int(final * promo["cashback_percent"] / 100)
        if cashback_bonus > 0:
            await db.add_bonus_transaction(order["user_id"], order_id, cashback_bonus, f"Cashback: {promo['title']}")
            await db.mark_order_cashback_awarded(order_id)
            cashback_text = f"\n\n🎁 Sizga <b>{promo['title']}</b> aksiyasi doirasida cashback berildi!\n💎 <b>+{cashback_bonus:,} so'm</b> bonus hisobingizga qo'shildi."

    # Notify user
    try:
        await bot.send_message(
            order["user_id"],
            f"\u2705 <b>Buyurtmangiz tasdiqlandi!</b>\n\nBuyurtma #<b>{order_id}</b>\n"
            f"{order['service_name']}\n{final:,} so'm\n\nTez orada bog'lanamiz!{cashback_text}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Referral order bonus: if this is buyer's first confirmed order
    confirmed_count = await db.get_user_confirmed_orders_count(order["user_id"])
    if confirmed_count == 1:
        buyer = await db.get_user(order["user_id"])
        if buyer and buyer["referred_by"]:
            referrer_id = buyer["referred_by"]
            referrer = await db.get_user(referrer_id)
            if referrer:
                ref_count = await db.get_referral_count(referrer_id)
                tier = get_tier(ref_count)
                pct = BONUS_ORDER_PCT[tier]
                final = order["final_price"] or order["price"]
                bonus_amount = final * pct // 100
                if bonus_amount > 0:
                    await db.add_bonus(referrer_id, bonus_amount, f"Buyurtma #{order_id} foizi")
                    updated = await db.get_user(referrer_id)
                    new_balance = updated["bonus_balance"] if updated else 0
                    lang_ref = referrer["language"] or "uz"
                    from locales import t as lt
                    try:
                        await bot.send_message(
                            referrer_id,
                            lt(lang_ref, "referral_order_bonus_notify",
                               name=buyer["full_name"] or "Foydalanuvchi",
                               amount=bonus_amount,
                               pct=pct,
                               balance=new_balance),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

    # Ask admin how to deliver
    service = await db.get_service(order["service_id"])
    has_preset = bool(service and service["delivery_content"])
    preset_preview = ""
    if has_preset:
        preview = service["delivery_content"][:80]
        preset_preview = f"\n\n<i>Standart: {preview}{'...' if len(service['delivery_content']) > 80 else ''}</i>"
    await call.message.reply(
        f"\u2705 Buyurtma #{order_id} tasdiqlandi.\n\n"
        f"\U0001f4e6 Mijozga nima yuborasiz?{preset_preview}",
        reply_markup=delivery_choose_keyboard(order_id, has_preset),
        parse_mode="HTML",
    )


async def _send_review_request(bot: Bot, order_id: int, user_id: int, service_name: str):
    try:
        from keyboards.user_kb import rating_keyboard
        await bot.send_message(
            user_id,
            f"\u2b50 <b>{service_name}</b> xizmatini baholang:",
            reply_markup=rating_keyboard(order_id),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_deliver_std:"))
async def deliver_standard(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    service = await db.get_service(order["service_id"])
    await call.message.edit_reply_markup(reply_markup=None)
    try:
        await bot.send_message(
            order["user_id"],
            f"\U0001f4e6 <b>Sizning xizmatingiz:</b>\n\n{service['delivery_content']}",
            parse_mode="HTML",
        )
        await call.answer("\u2705 Standart xabar yuborildi!")
    except Exception as e:
        await call.answer(f"Xatolik: {e}", show_alert=True)
    await _send_review_request(bot, order_id, order["user_id"], order["service_name"])


@router.callback_query(F.data.startswith("adm_deliver_custom:"))
async def deliver_custom_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    await state.update_data(deliver_order_id=order_id, deliver_user_id=order["user_id"],
                            deliver_service_name=order["service_name"])
    await state.set_state(DeliveryCustomState.message)
    await call.answer()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        f"\u270f\ufe0f Buyurtma #{order_id} uchun individual xabar yozing\n"
        "(kalit, link, qo'llanma — istaganingizni):",
        reply_markup=cancel_keyboard(),
    )


@router.message(DeliveryCustomState.message)
async def deliver_custom_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(
            data["deliver_user_id"],
            f"\U0001f4e6 <b>Sizning xizmatingiz:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.answer("\u2705 Individual xabar yuborildi!", reply_markup=admin_menu())
    except Exception as e:
        await message.answer(f"\u274c Xatolik: {e}", reply_markup=admin_menu())
    await _send_review_request(bot, data["deliver_order_id"], data["deliver_user_id"], data["deliver_service_name"])


@router.callback_query(F.data.startswith("adm_deliver_skip:"))
async def deliver_skip(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("O'tkazib yuborildi.")
    await _send_review_request(bot, order_id, order["user_id"], order["service_name"])


@router.callback_query(F.data.startswith("adm_reject:"))
async def reject_order(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return
    await db.update_order_status(order_id, "rejected")
    await call.answer("\u274c Rad etildi!")
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply(f"\u274c Buyurtma #{order_id} rad etildi.")
    # Bonus refund
    bonus_used = order["bonus_used"] or 0
    if bonus_used > 0:
        await db.add_bonus(order["user_id"], bonus_used, f"Buyurtma #{order_id} rad etildi")
    await db.increase_stock(order["service_id"])
    try:
        bonus_note = f"\n\n\U0001f48e Bonus ({bonus_used:,} so'm) hisobingizga qaytarildi." if bonus_used > 0 else ""
        await bot.send_message(
            order["user_id"],
            f"\u274c <b>Buyurtmangiz rad etildi.</b>\n\nBuyurtma #<b>{order_id}</b>\nSavollar uchun admin bilan bog'laning.{bonus_note}",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ADMIN REPLY TO ORDER

@router.callback_query(F.data.startswith("adm_reply:"))
async def admin_reply_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return
    await state.update_data(reply_to_user=order["user_id"], reply_order_id=order_id)
    await state.set_state(AdminReplyState.message)
    await call.message.answer(
        f"\u2709\ufe0f Buyurtma #{order_id} egasiga xabar yozing:",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminReplyState.message)
async def admin_reply_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(
            data["reply_to_user"],
            f"\U0001f4ac <b>Admin xabari:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.answer("\u2705 Xabar yuborildi!", reply_markup=admin_menu())
    except Exception as e:
        await message.answer(f"\u274c Xatolik: {e}", reply_markup=admin_menu())


# USERS

@router.message(F.text == "\U0001f465 Foydalanuvchilar")
async def all_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    users = await db.get_all_users()
    count = len(users)
    text = f"\U0001f465 <b>Jami: {count}</b>\n\n"
    for u in users[:50]:
        blocked = " \U0001f6ab" if u["is_blocked"] else ""
        bonus = u["bonus_balance"] if u["bonus_balance"] else 0
        bonus_text = f" 💎{bonus:,}" if bonus > 0 else ""
        text += f"• @{u['username'] or 'nomalum'} — {u['full_name'] or ''} (<code>{u['id']}</code>){blocked}{bonus_text}\n"
    if count > 50:
        text += f"\n... va yana {count - 50} ta"
    await message.answer(text, parse_mode="HTML")


# BLOCK / UNBLOCK

@router.message(F.text == "\U0001f6ab Bloklash/Unblock")
async def block_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BlockState.user_id)
    await message.answer("Foydalanuvchi ID kiriting (blok uchun) yoki unblock ID:", reply_markup=cancel_keyboard())


@router.message(BlockState.user_id)
async def block_execute(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.lstrip("-").isdigit():
        await message.answer("ID raqam kiriting:")
        return
    uid = int(message.text.lstrip("-"))
    user = await db.get_user(abs(uid))
    await state.clear()
    if not user:
        await message.answer("Foydalanuvchi topilmadi.", reply_markup=admin_menu())
        return
    new_status = 0 if user["is_blocked"] else 1
    await db.block_user(abs(uid), new_status)
    status_text = "\U0001f6ab Bloklandi" if new_status else "\u2705 Blok olindi"
    await message.answer(f"{status_text}: {user['full_name']} (<code>{abs(uid)}</code>)", reply_markup=admin_menu(), parse_mode="HTML")


# BROADCAST

@router.message(F.text == "\U0001f4e2 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastState.message)
    await message.answer("\U0001f4e2 Xabar yozing:", reply_markup=cancel_keyboard())


@router.message(BroadcastState.message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.clear()
    users = await db.get_all_users()
    sent, failed = 0, 0
    for u in users:
        if u["is_blocked"]:
            continue
        try:
            await bot.copy_message(chat_id=u["id"], from_chat_id=message.chat.id, message_id=message.message_id)
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"\U0001f4e2 Yuborildi!\n\u2705 Muvaffaqiyatli: {sent}\n\u274c Yuborilmadi: {failed}", reply_markup=admin_menu())


# SERVICES MANAGEMENT

@router.message(F.text == "\U0001f6e0 Xizmatlarni boshqarish")
async def manage_services(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    services = await db.get_services(only_active=False)
    await message.answer("\U0001f6e0 <b>Xizmatlarni boshqarish:</b>", reply_markup=services_manage_keyboard(services), parse_mode="HTML")


@router.callback_query(F.data == "adm_back_services")
async def adm_back_services(call: CallbackQuery):
    await call.answer()
    services = await db.get_services(only_active=False)
    await call.message.edit_text("\U0001f6e0 <b>Xizmatlarni boshqarish:</b>", reply_markup=services_manage_keyboard(services), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_service:"))
async def adm_service_detail(call: CallbackQuery):
    service_id = int(call.data.split(":")[1])
    s = await db.get_service(service_id)
    if not s:
        await call.answer("Topilmadi!", show_alert=True)
        return
    await call.answer()
    status = "\u2705 Faol" if s["active"] else "\U0001f534 Nofaol"
    avg, cnt = await db.get_service_avg_rating(service_id)
    rating_text = f"\n\u2b50 {avg}/5 ({cnt})" if cnt else ""
    delivery_preview = ""
    if s["delivery_content"]:
        preview = s["delivery_content"][:60] + ("..." if len(s["delivery_content"]) > 60 else "")
        delivery_preview = f"\n\U0001f4e6 Yetkazish: <code>{preview}</code>"
    text = f"\U0001f539 <b>{s['name']}</b>\n{s['description'] or '—'}\n\U0001f4b0 {s['price']:,} so'm\n\U0001f4e6 Qoldiq: {s['stock']} ta\nHolat: {status}{rating_text}{delivery_preview}"
    await call.message.edit_text(text, reply_markup=service_admin_detail(service_id, s["active"], bool(s["delivery_content"])), parse_mode="HTML")


# SET DELIVERY CONTENT

@router.callback_query(F.data.startswith("adm_set_delivery:"))
async def adm_set_delivery_start(call: CallbackQuery, state: FSMContext):
    service_id = int(call.data.split(":")[1])
    s = await db.get_service(service_id)
    await call.answer()
    await state.update_data(delivery_service_id=service_id)
    await state.set_state(SetDeliveryState.content)
    current = f"\n\nHozirgi: <code>{s['delivery_content']}</code>" if s["delivery_content"] else "\n\nHozircha o'rnatilmagan."
    await call.message.answer(
        f"\U0001f4e6 <b>{s['name']}</b> xizmati uchun yetkazish mazmunini kiriting:{current}\n\n"
        "Kalit, link yoki qo'llanma matnini yozing.\n"
        "O'chirish uchun <b>-</b> bosing.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(SetDeliveryState.content)
async def adm_set_delivery_save(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    service_id = data["delivery_service_id"]
    delivery_content = None if message.text.strip() == "-" else message.text.strip()
    await db.set_service_delivery(service_id, delivery_content)
    await state.clear()
    if delivery_content:
        await message.answer(
            "\u2705 Yetkazish mazmuni saqlandi!\n\n"
            "Bundan keyin bu xizmat tasdiqlanganda mijozga avtomatik yuboriladi.",
            reply_markup=admin_menu(),
        )
    else:
        await message.answer("\U0001f5d1 Yetkazish mazmuni o'chirildi.", reply_markup=admin_menu())


# ADD SERVICE

@router.callback_query(F.data == "adm_add_service")
async def adm_add_service_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    categories = await db.get_categories()
    if categories:
        from keyboards.admin_kb import categories_manage_keyboard
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        buttons = [[InlineKeyboardButton(text=c["name"], callback_data=f"adm_pick_cat:{c['id']}")] for c in categories]
        buttons.append([InlineKeyboardButton(text="Kategoriyasiz", callback_data="adm_pick_cat:0")])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await state.set_state(AddServiceState.category)
        await call.message.answer("Kategoriya tanlang:", reply_markup=markup)
    else:
        await state.update_data(category_id=None)
        await state.set_state(AddServiceState.name)
        await call.message.answer("\u2795 Xizmat nomi:", reply_markup=cancel_keyboard())


@router.callback_query(F.data.startswith("adm_pick_cat:"))
async def adm_pick_category(call: CallbackQuery, state: FSMContext):
    await call.answer()
    cat_id = call.data.split(":")[1]
    await state.update_data(category_id=int(cat_id) if cat_id != "0" else None)
    await state.set_state(AddServiceState.name)
    await call.message.answer("\u2795 Xizmat nomi:", reply_markup=cancel_keyboard())


@router.message(AddServiceState.name)
async def adm_add_name(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.update_data(name=message.text)
    await state.set_state(AddServiceState.description_uz)
    await message.answer("📝 Xizmat tavsifini kiriting (O'zbek tilida):")


@router.message(AddServiceState.description_uz)
async def adm_add_desc_uz(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.update_data(description_uz="" if message.text == "-" else message.text)
    await state.set_state(AddServiceState.description_ru)
    await message.answer("📝 Xizmat tavsifini kiriting (Rus tilida):")


@router.message(AddServiceState.description_ru)
async def adm_add_desc_ru(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.update_data(description_ru="" if message.text == "-" else message.text)
    await state.set_state(AddServiceState.price)
    await message.answer("\U0001f4b0 Narx (raqam):")


@router.message(AddServiceState.price)
async def adm_add_price(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("\u2757 Faqat raqam:")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddServiceState.stock)
    await message.answer("\U0001f4e6 Qoldiq soni (agar cheksiz bo'lsa 99999 deb yozing):")


@router.message(AddServiceState.stock)
async def adm_add_stock(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("\u2757 Faqat raqam:")
        return
    await state.update_data(stock=int(message.text))
    await state.set_state(AddServiceState.image)
    await message.answer("\U0001f5bc Rasm yuboring yoki '-' bosing:")


@router.message(AddServiceState.image)
async def adm_add_image(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    image_file_id = message.photo[-1].file_id if message.photo else None
    await state.update_data(image_file_id=image_file_id)
    await state.set_state(AddServiceState.delivery)
    await message.answer(
        "\U0001f4e6 <b>Yetkazish mazmunini kiriting:</b>\n\n"
        "Bu xabar buyurtma tasdiqlanganda mijozga avtomatik yuboriladi.\n"
        "Misol: kalit so'z, kanal linki, qo'llanma matni...\n\n"
        "O'tkazib yuborish uchun <b>-</b> bosing.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AddServiceState.delivery)
async def adm_add_delivery(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    delivery_content = None if message.text.strip() == "-" else message.text.strip()
    service_id = await db.add_service(
        data["name"], data.get("description_uz", ""), data["price"],
        data.get("category_id"), data.get("image_file_id"), delivery_content, data.get("stock", 0),
        description_uz=data.get("description_uz", ""),
        description_ru=data.get("description_ru", ""),
    )
    await state.clear()
    delivery_status = "\U0001f4e6 Yetkazish mazmuni saqlandi." if delivery_content else ""
    await message.answer(
        f"\u2705 Xizmat qo'shildi #{service_id}: <b>{data['name']}</b> — {data['price']:,} so'm\n{delivery_status}",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# EDIT SERVICE

@router.callback_query(F.data.startswith("adm_edit:"))
async def adm_edit_start(call: CallbackQuery, state: FSMContext):
    service_id = int(call.data.split(":")[1])
    await call.answer()
    await state.update_data(edit_id=service_id)
    await state.set_state(EditServiceState.name)
    await call.message.answer("\u270f\ufe0f Yangi nom ('-' = o'zgartirmaslik):", reply_markup=cancel_keyboard())


@router.message(EditServiceState.name)
async def adm_edit_name(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    if message.text != "-":
        await state.update_data(new_name=message.text)
    else:
        s = await db.get_service(data["edit_id"])
        await state.update_data(new_name=s["name"])
    await state.set_state(EditServiceState.description_uz)
    await message.answer("📝 Yangi tavsif O'zbekcha ('-' = o'zgartirmaslik):")


@router.message(EditServiceState.description_uz)
async def adm_edit_desc_uz(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    if message.text != "-":
        await state.update_data(new_desc_uz=message.text)
    else:
        s = await db.get_service(data["edit_id"])
        await state.update_data(new_desc_uz=s["description_uz"] or s["description"] or "")
    await state.set_state(EditServiceState.description_ru)
    await message.answer("📝 Yangi tavsif Ruscha ('-' = o'zgartirmaslik):")


@router.message(EditServiceState.description_ru)
async def adm_edit_desc_ru(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    if message.text != "-":
        await state.update_data(new_desc_ru=message.text)
    else:
        s = await db.get_service(data["edit_id"])
        await state.update_data(new_desc_ru=s["description_ru"] or s["description"] or "")
    await state.set_state(EditServiceState.price)
    await message.answer("\U0001f4b0 Yangi narx ('-' = o'zgartirmaslik):")


@router.message(EditServiceState.price)
async def adm_edit_price(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    if message.text != "-":
        if not message.text.isdigit():
            await message.answer("\u2757 Faqat raqam:")
            return
        new_price = int(message.text)
    else:
        s = await db.get_service(data["edit_id"])
        new_price = s["price"]
    await state.clear()
    await db.update_service(data["edit_id"], data["new_name"], data.get("new_desc_uz", ""), new_price, description_ru=data.get("new_desc_ru", ""))
    await message.answer(
        f"\u2705 Yangilandi: <b>{data['new_name']}</b> — {new_price:,} so'm",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_edit_stock:"))
async def adm_edit_stock_start(call: CallbackQuery, state: FSMContext):
    service_id = int(call.data.split(":")[1])
    await call.answer()
    await state.update_data(edit_stock_id=service_id)
    await state.set_state(EditServiceStockState.stock)
    await call.message.answer("\U0001f4e6 Yangi qoldiq sonini kiriting:", reply_markup=cancel_keyboard())


@router.message(EditServiceStockState.stock)
async def adm_edit_stock_save(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("\u2757 Faqat raqam:")
        return
    data = await state.get_data()
    service_id = data["edit_stock_id"]
    new_stock = int(message.text)
    await db.update_stock(service_id, new_stock)
    await state.clear()
    await message.answer(f"\u2705 Qoldiq o'zgartirildi: {new_stock} ta", reply_markup=admin_menu())


@router.callback_query(F.data.startswith("adm_toggle:"))
async def adm_toggle(call: CallbackQuery):
    service_id = int(call.data.split(":")[1])
    await db.toggle_service(service_id)
    s = await db.get_service(service_id)
    status = "\u2705 Faol" if s["active"] else "\U0001f534 Nofaol"
    await call.answer(f"Holat: {status}")
    avg, cnt = await db.get_service_avg_rating(service_id)
    text = f"\U0001f539 <b>{s['name']}</b>\n{s['description'] or '—'}\n\U0001f4b0 {s['price']:,} so'm\n\U0001f4e6 Qoldiq: {s['stock']} ta\nHolat: {status}"
    await call.message.edit_text(text, reply_markup=service_admin_detail(service_id, s["active"], bool(s["delivery_content"])), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_delete:"))
async def adm_delete_confirm(call: CallbackQuery):
    service_id = int(call.data.split(":")[1])
    await call.answer()
    s = await db.get_service(service_id)
    await call.message.edit_text(
        f"\U0001f5d1 <b>{s['name']}</b> o'chirilsinmi?",
        reply_markup=confirm_delete_keyboard(service_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_confirm_delete:"))
async def adm_delete_execute(call: CallbackQuery):
    service_id = int(call.data.split(":")[1])
    await db.delete_service(service_id)
    await call.answer("O'chirildi!")
    services = await db.get_services(only_active=False)
    await call.message.edit_text("\U0001f6e0 <b>Xizmatlarni boshqarish:</b>", reply_markup=services_manage_keyboard(services), parse_mode="HTML")


# CATEGORIES

@router.message(F.text == "\U0001f4c2 Kategoriyalar")
async def manage_categories(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    categories = await db.get_categories()
    await message.answer("\U0001f4c2 <b>Kategoriyalar:</b>", reply_markup=categories_manage_keyboard(categories), parse_mode="HTML")


@router.callback_query(F.data == "adm_cat_add")
async def add_category_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AddCategoryState.name)
    await call.message.answer("\U0001f4c2 Kategoriya nomi:", reply_markup=cancel_keyboard())


@router.message(AddCategoryState.name)
async def add_category_name(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.clear()
    cat_id = await db.add_category(message.text)
    categories = await db.get_categories()
    await message.answer(
        f"\u2705 Kategoriya qo'shildi: <b>{message.text}</b>",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_cat_del:"))
async def delete_category(call: CallbackQuery):
    cat_id = int(call.data.split(":")[1])
    cat = await db.get_category(cat_id)
    if cat:
        await db.delete_category(cat_id)
        await call.answer("O'chirildi!")
    else:
        await call.answer()
    categories = await db.get_categories()
    await call.message.edit_text("\U0001f4c2 <b>Kategoriyalar:</b>", reply_markup=categories_manage_keyboard(categories), parse_mode="HTML")


# COUPONS

@router.message(F.text == "\U0001f3f7 Kuponlar")
async def manage_coupons(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    coupons = await db.get_all_coupons()
    await message.answer("\U0001f3f7 <b>Kuponlar:</b>", reply_markup=coupons_keyboard(coupons), parse_mode="HTML")


@router.callback_query(F.data == "adm_coupon_add")
async def add_coupon_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AddCouponState.code)
    await call.message.answer("\U0001f3f7 Kupon kodi (lotin harflari):", reply_markup=cancel_keyboard())


@router.message(AddCouponState.code)
async def add_coupon_code(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.update_data(code=message.text.upper())
    await state.set_state(AddCouponState.discount)
    await message.answer("\U0001f4b5 Chegirma foizi (1-99):")


@router.message(AddCouponState.discount)
async def add_coupon_discount(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.isdigit() or not (1 <= int(message.text) <= 99):
        await message.answer("\u2757 1-99 oralig'ida raqam kiriting:")
        return
    await state.update_data(discount=int(message.text))
    await state.set_state(AddCouponState.max_uses)
    await message.answer("\U0001f522 Maksimal foydalanish soni:")


@router.message(AddCouponState.max_uses)
async def add_coupon_max(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("\u2757 Raqam kiriting:")
        return
    data = await state.get_data()
    await state.clear()
    coupon_id = await db.add_coupon(data["code"], data["discount"], int(message.text))
    await message.answer(
        f"\u2705 Kupon yaratildi: <b>{data['code']}</b> -{data['discount']}% (max {message.text}x)",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_coupon_del:"))
async def delete_coupon(call: CallbackQuery):
    coupon_id = int(call.data.split(":")[1])
    await db.delete_coupon(coupon_id)
    await call.answer("O'chirildi!")
    coupons = await db.get_all_coupons()
    await call.message.edit_text("\U0001f3f7 <b>Kuponlar:</b>", reply_markup=coupons_keyboard(coupons), parse_mode="HTML")


# EXCEL EXPORT

@router.message(F.text == "\U0001f4e5 Excel eksport")
async def excel_export(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    orders = await db.get_all_orders(1000)
    buf = await generate_orders_excel(orders)
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    doc = BufferedInputFile(buf.read(), filename=f"orders_{now}.xlsx")
    await bot.send_document(message.chat.id, doc, caption="\U0001f4c8 Barcha buyurtmalar eksporti")


# BACKUP

@router.message(F.text == "\U0001f4be Backup")
async def backup_db(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await send_backup(bot, message.chat.id)


# BONUS MANAGEMENT

@router.message(F.text == "\U0001f48e Bonus boshqaruv")
async def bonus_manage_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BonusManageState.user_id)
    await message.answer(
        "\U0001f48e <b>Bonus boshqaruv</b>\n\nFoydalanuvchi ID kiriting:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(BonusManageState.user_id)
async def bonus_manage_find_user(message: Message, state: FSMContext):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.strip().lstrip("-").isdigit():
        await message.answer("\u2757 Faqat raqam (user ID) kiriting:")
        return
    uid = int(message.text.strip())
    user = await db.get_user(uid)
    if not user:
        await message.answer("\u274c Foydalanuvchi topilmadi.")
        return
    await state.clear()
    balance = user["bonus_balance"] or 0
    ref_count = await db.get_referral_count(uid)
    tier = get_tier(ref_count)
    tier_label = TIER_LABELS[tier]["uz"]
    await message.answer(
        f"\U0001f464 <b>{user['full_name'] or 'Nomalum'}</b> (@{user['username'] or '—'})\n"
        f"\U0001f194 ID: <code>{uid}</code>\n"
        f"\U0001f48e Bonus balans: <b>{balance:,} so'm</b>\n"
        f"\U0001f3c6 Daraja: {tier_label} ({ref_count} ta taklif)",
        reply_markup=bonus_manage_keyboard(uid, balance),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_bonus_add:"))
async def bonus_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[1])
    await state.update_data(bonus_uid=uid, bonus_action="add")
    await state.set_state(BonusManageState.amount)
    await call.answer()
    await call.message.answer(
        f"\u2795 <code>{uid}</code> ga qo'shiladigan bonus miqdorini kiriting (so'm):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_bonus_sub:"))
async def bonus_sub_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[1])
    await state.update_data(bonus_uid=uid, bonus_action="sub")
    await state.set_state(BonusManageState.amount)
    await call.answer()
    await call.message.answer(
        f"\u2796 <code>{uid}</code> dan ayiriladigan bonus miqdorini kiriting (so'm):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(BonusManageState.amount)
async def bonus_manage_execute(message: Message, state: FSMContext, bot: Bot):
    if message.text == "\u274c Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    if not message.text.strip().isdigit():
        await message.answer("\u2757 Faqat musbat raqam kiriting:")
        return
    amount = int(message.text.strip())
    data = await state.get_data()
    uid = data["bonus_uid"]
    action = data["bonus_action"]
    await state.clear()
    if action == "add":
        await db.add_bonus(uid, amount, f"Admin qo'shdi: {message.from_user.full_name}")
        action_text = f"\u2795 +{amount:,} so'm qo'shildi"
    else:
        await db.use_bonus(uid, amount, f"Admin ayirdi: {message.from_user.full_name}")
        action_text = f"\u2796 {amount:,} so'm ayirildi"
    user = await db.get_user(uid)
    new_balance = user["bonus_balance"] if user else 0
    await message.answer(
        f"\u2705 {action_text}\n\U0001f48e Yangi balans: <b>{new_balance:,} so'm</b>",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )
    # Notify user
    if user:
        lang = user["language"] or "uz"
        try:
            sign = "+" if action == "add" else "-"
            await bot.send_message(
                uid,
                f"\U0001f48e <b>Bonus balansingiz yangilandi</b>\n\n"
                f"{sign}{amount:,} so'm\n"
                f"\U0001f4b0 Joriy balans: <b>{new_balance:,} so'm</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("adm_bonus_log:"))
async def bonus_log_show(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[1])
    logs = await db.get_bonus_log(uid, 15)
    if not logs:
        await call.answer("Bonus tarixi yo'q.", show_alert=True)
        return
    text = f"\U0001f4cb <b>Bonus tarixi (ID: {uid}):</b>\n\n"
    for log in logs:
        sign = "\u2795" if log["type"] == "credit" else "\u2796"
        text += f"{sign} {log['amount']:,} so'm — {log['description'] or '—'}\n   {log['created_at'][:16]}\n\n"
    await call.answer()
    await call.message.answer(text, parse_mode="HTML")


@router.message(F.text == "⭐ Reviewlar")
async def adm_recent_reviews(message: Message):
    if not is_admin(message.from_user.id): return
    reviews = await db.get_recent_reviews(limit=20)
    if not reviews:
        await message.answer("Hozircha izohlar yo'q.")
        return
    text = "⭐ <b>So'nggi 20 ta izoh:</b>\n\n"
    for r in reviews:
        stars = "⭐" * r["rating"]
        text += f"👤 <b>{r['full_name']}</b> ({r['service_name']})\n{stars}\n💬 <i>{r['comment'] or 'Izohsiz'}</i>\n\n"
    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_sup_reply:"))
async def adm_sup_reply_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    parts = call.data.split(":")
    user_id = int(parts[1])
    message_id = int(parts[2])
    await call.answer()
    await state.update_data(reply_user_id=user_id)
    await state.set_state(AdminSupportReplyState.message)
    await call.message.answer(
        f"💬 ID <code>{user_id}</code> bo'lgan mijozga javobingizni kiriting:", 
        parse_mode="HTML", 
        reply_markup=cancel_keyboard()
    )


@router.message(AdminSupportReplyState.message)
async def adm_sup_reply_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    if message.text in ["\u274c Bekor qilish", "❌ Bekor qilish"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    data = await state.get_data()
    user_id = data.get("reply_user_id")
    if user_id:
        try:
            await bot.send_message(
                user_id, 
                f"📨 <b>Operatordan javob:</b>\n\n{message.text}", 
                parse_mode="HTML"
            )
            await message.answer("✅ Mijozga javob yuborildi!", reply_markup=admin_menu())
        except Exception as e:
            await message.answer(f"❌ Xatolik yuz berdi: {e}", reply_markup=admin_menu())
    await state.clear()


@router.message(F.text == "🎉 Aksiyalar boshqaruvi")
async def manage_promos(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    promos = await db.get_promos()
    from keyboards.admin_kb import promos_manage_keyboard
    await message.answer("🎉 <b>Aksiyalar:</b>", reply_markup=promos_manage_keyboard(promos), parse_mode="HTML")

@router.callback_query(F.data == "adm_add_promo")
async def add_promo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.answer()
    await state.set_state(PromoAddState.title)
    await call.message.answer("📝 Aksiya sarlavhasini kiriting:", reply_markup=cancel_keyboard())

@router.message(PromoAddState.title)
async def add_promo_title(message: Message, state: FSMContext):
    if message.text in ["❌ Bekor qilish", "🔙 Orqaga", "\u274c Bekor qilish"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.update_data(title=message.text)
    await state.set_state(PromoAddState.text)
    await message.answer("📄 Aksiya matnini kiriting:")

@router.message(PromoAddState.text)
async def add_promo_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(PromoAddState.image)
    await message.answer("🖼 Aksiya rasmini yuboring (yoki matn ko'rinishida 'o'tkazish' deb yozing):")

@router.message(PromoAddState.image)
async def add_promo_image(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    
    await db.add_promo(title=data["title"], text=data["text"], image_file_id=file_id, url=None)
    await state.clear()
    await message.answer("✅ Aksiya muvaffaqiyatli saqlandi!", reply_markup=admin_menu())

@router.callback_query(F.data.startswith("adm_del_promo:"))
async def del_promo(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    promo_id = int(call.data.split(":")[1])
    await db.delete_promo(promo_id)
    promos = await db.get_promos()
    from keyboards.admin_kb import promos_manage_keyboard
    await call.message.edit_reply_markup(reply_markup=promos_manage_keyboard(promos))
    await call.answer("O'chirildi")


@router.message(F.text == "🎁 Cashback aksiyalar")
async def manage_cashback_promos(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    promos = await db.list_all_service_promotions()
    from keyboards.admin_kb import cashback_promos_manage_keyboard
    await message.answer("🎁 <b>Cashback Aksiyalar:</b>", reply_markup=cashback_promos_manage_keyboard(promos), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_set_cashback:"))
async def adm_set_cashback_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    service_id = int(call.data.split(":")[1])
    s = await db.get_service(service_id)
    promo = await db.get_service_promo_admin(service_id)
    await state.update_data(cashback_service_id=service_id)
    
    text = f"🎁 <b>{s['name']}</b> uchun Cashback:\n\n"
    if promo:
        status = "🟢 Faol" if promo['is_active'] else "🔴 Nofaol"
        text += f"Sarlavha: <b>{promo['title']}</b>\nFoiz: <b>{promo['cashback_percent']}%</b>\nHolat: {status}\n\n"
    else:
        text += "Hozircha o'rnatilmagan.\n\n"
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text="✏️ O'zgartirish / Qo'shish", callback_data=f"adm_edit_cb:{service_id}")],
    ]
    if promo:
        buttons.append([InlineKeyboardButton(text="✅/⛔ Holatni o'zgartirish", callback_data=f"adm_toggle_cb:{promo['id']}")])
        buttons.append([InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"adm_del_cb:{promo['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"adm_service:{service_id}")])
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_edit_cb:"))
async def adm_edit_cb_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    service_id = int(call.data.split(":")[1])
    await state.update_data(cashback_service_id=service_id)
    await state.set_state(PromoCashbackState.title)
    await call.message.answer("📝 Cashback sarlavhasini kiriting (masalan: Yozgi cashback):", reply_markup=cancel_keyboard())
    await call.answer()

@router.message(PromoCashbackState.title)
async def adm_edit_cb_title(message: Message, state: FSMContext):
    if message.text in ["❌ Bekor qilish", "🔙 Orqaga", "\u274c Bekor qilish"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu())
        return
    await state.update_data(cb_title=message.text)
    await state.set_state(PromoCashbackState.percent)
    await message.answer("📊 Necha foiz cashback beriladi? (Raqam kiriting, 0 dan 100 gacha, masalan: 10):", reply_markup=cancel_keyboard())

@router.message(PromoCashbackState.percent)
async def adm_edit_cb_percent(message: Message, state: FSMContext):
    try:
        if message.text in ["❌ Bekor qilish", "🔙 Orqaga", "\u274c Bekor qilish"]:
            await state.clear()
            await message.answer("Bekor qilindi.", reply_markup=admin_menu())
            return
        percent = float(message.text)
        if not (0 < percent <= 100):
            raise ValueError
    except ValueError:
        await message.answer("❌ Noto'g'ri foiz kiritdingiz. Qaytadan raqam kiriting (masalan: 10):")
        return
        
    data = await state.get_data()
    service_id = data["cashback_service_id"]
    await db.create_or_update_service_promo(service_id, data["cb_title"], percent)
    await state.clear()
    await message.answer(f"✅ <b>{data['cb_title']}</b> {percent}% qilib saqlandi!", reply_markup=admin_menu(), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_toggle_cb:"))
async def adm_toggle_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    promo_id = int(call.data.split(":")[1])
    await db.toggle_service_promo(promo_id)
    await call.answer("Holati o'zgardi!")
    await call.message.delete()
    
@router.callback_query(F.data.startswith("adm_del_cb:"))
async def adm_delete_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    promo_id = int(call.data.split(":")[1])
    await db.delete_service_promo(promo_id)
    await call.answer("O'chirildi!")
    await call.message.delete()


# BULK PRICING ADMIN FLOW
class BulkPriceState(StatesGroup):
    waiting_min_qty = State()
    waiting_price = State()

@router.callback_query(F.data.startswith("adm_bulk:"))
async def manage_bulk_prices(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    service_id = int(call.data.split(":")[1])
    s = await db.get_service(service_id)
    tiers = await db.get_bulk_prices(service_id)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    text = f"📦 <b>{s['name']}</b>\nUlgurji narxlar ro'yxati:\n\n"
    buttons = []
    if tiers:
        for t in tiers:
            text += f"▪️ {t['min_quantity']} ta dan boshlab — {t['price_per_unit']:,} so'm/dona\n"
            buttons.append([InlineKeyboardButton(text=f"🗑 O'chirish: {t['min_quantity']} ta", callback_data=f"adm_del_bulk:{t['id']}:{service_id}")])
    else:
        text += "Hali narxlar qo'shilmagan.\n\n"
        
    buttons.append([InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data=f"adm_add_bulk:{service_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"adm_service:{service_id}")])
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_del_bulk:"))
async def delete_bulk_price_call(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    _, price_id, service_id = call.data.split(":")
    await db.delete_bulk_price(int(price_id))
    await call.answer("O'chirildi!", show_alert=True)
    call.data = f"adm_bulk:{service_id}"
    await manage_bulk_prices(call, state)

@router.callback_query(F.data.startswith("adm_add_bulk:"))
async def add_bulk_price_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    service_id = int(call.data.split(":")[1])
    await state.update_data(bulk_service_id=service_id)
    await state.set_state(BulkPriceState.waiting_min_qty)
    await call.message.edit_text("Nechta dan boshlab chegirma beriladi? (Faqat raqam kiriting)")

@router.message(BulkPriceState.waiting_min_qty)
async def bulk_qty_entered(message: Message, state: FSMContext):
    try:
        qty = int(message.text)
        if qty <= 1: raise ValueError
    except ValueError:
        await message.answer("Faqat 1 dan katta raqam kiriting!")
        return
    await state.update_data(min_qty=qty)
    await state.set_state(BulkPriceState.waiting_price)
    await message.answer(f"{qty} ta dan boshlanganda 1 donasi narxi qancha bo'ladi?")

@router.message(BulkPriceState.waiting_price)
async def bulk_price_entered(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0: raise ValueError
    except ValueError:
        await message.answer("Faqat musbat raqam kiriting!")
        return
    data = await state.get_data()
    service_id = data["bulk_service_id"]
    await db.add_bulk_price(service_id, data["min_qty"], price)
    await state.clear()
    
    s = await db.get_service(service_id)
    await message.answer(f"✅ <b>{s['name']}</b> uchun {data['min_qty']} ta dan narx <b>{price:,} so'm</b> etib belgilandi.", parse_mode="HTML")
