import html

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from autopark_bot.db.models import User
from autopark_bot.enums import ROLE_TITLES, STAFF_ROLES, Role
from autopark_bot.keyboards.owner import staff_menu
from autopark_bot.services.invites import redeem_invitation

router = Router(name="start")

NO_ACCESS_TEXT = (
    "Доступ к боту только по персональной ссылке-приглашению.\n"
    "Обратитесь к владельцу автопарка."
)


def welcome_text(user: User) -> str:
    role = Role(user.role)
    name = html.escape(user.full_name)  # имя приходит от пользователя, а parse_mode=HTML
    text = f"Здравствуйте, {name}! Вы вошли как {ROLE_TITLES[role]}."
    if role in STAFF_ROLES:
        text += (
            "\n\n/adddriver Фамилия Имя | телефон — "
            "добавить водителя и получить ссылку для входа"
        )
        if role is Role.OWNER:
            text += "\n/invite admin — ссылка для администратора"
    return text


def menu_for(user: User) -> ReplyKeyboardMarkup | None:
    return staff_menu() if Role(user.role) in STAFF_ROLES else None


@router.message(CommandStart(deep_link=True))
async def start_with_invite(
    message: Message, command: CommandObject, session: AsyncSession, user: User | None
) -> None:
    if user is not None:
        await message.answer(welcome_text(user), reply_markup=menu_for(user))
        return

    tg_user = message.from_user
    if tg_user is None:
        return

    new_user = await redeem_invitation(
        session,
        raw_token=command.args or "",
        telegram_id=tg_user.id,
        full_name=tg_user.full_name,
        username=tg_user.username,
    )
    if new_user is None:
        await message.answer(
            "Ссылка недействительна, устарела или уже использована.\n"
            "Попросите владельца создать новую."
        )
        return

    # Фиксируем регистрацию до ответа: пользователь не должен увидеть «успех»,
    # если коммит потом упадёт.
    await session.commit()
    await message.answer(welcome_text(new_user), reply_markup=menu_for(new_user))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, user: User | None) -> None:
    await state.clear()  # /start прерывает любой незаконченный ввод
    if user is None:
        await message.answer(NO_ACCESS_TEXT)
        return
    await message.answer(welcome_text(user), reply_markup=menu_for(user))
