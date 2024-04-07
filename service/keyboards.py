from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback

from service.db_engine import db

another_profession = Keyboard().add(Text("Другая", {"profession": "another_profession"}), KeyboardButtonColor.NEGATIVE)
orientations = Keyboard().add(Text("Гетеро", {"orientation": 0}), KeyboardButtonColor.PRIMARY).row().add(
    Text("Би", {"orientation": 1}), KeyboardButtonColor.PRIMARY).row().add(
    Text("Гомо", {"orientation": 2}), KeyboardButtonColor.PRIMARY
)


def create_accept_form(form_id: int):
    form_accept = Keyboard(one_time=False, inline=True).add(
        Callback("Подтвердить", {"form_accept": form_id}), KeyboardButtonColor.POSITIVE
    ).add(
        Callback("Отклонить", {"form_decline": form_id}), KeyboardButtonColor.NEGATIVE
    )
    return form_accept


def get_skip_button(field: str):
    return Keyboard().add(Text("Пропустить", {field: "skip"}), KeyboardButtonColor.SECONDARY)


async def main_menu(user_id: int):
    is_admin = (await db.select([db.User.admin]).where(db.User.user_id == user_id).gino.scalar()) > 0
    keyboard = (Keyboard().add(
        Text("Анкета", {"menu": "form"}), KeyboardButtonColor.PRIMARY
    ).add(
        Text("Банк", {"menu": "bank"}), KeyboardButtonColor.PRIMARY
    ).add(
        Text("Магазин", {"menu": "shop"}), KeyboardButtonColor.PRIMARY
    ).add(
        Text("Настройки", {"menu": "settings"}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Квесты и ежедневные задания", {"menu": "quests and daylics"}), KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Администрация проекта", {"menu": "staff"}), KeyboardButtonColor.NEGATIVE
    ))
    if is_admin:
        keyboard.row().add(
            Text("Админ-панель", {"menu": "admin_panel"}), KeyboardButtonColor.NEGATIVE
        )
    return keyboard


reason_decline_form = Keyboard().add(
    Text("Без причины", {"reason_decline": "Null"}), KeyboardButtonColor.NEGATIVE
)

fill_quiz = Keyboard().add(
    Text("Заполнить заново", {"command": "start"}), KeyboardButtonColor.PRIMARY
)

admin_menu = Keyboard().add(
    Text("Редактирование анкет", {"admin_menu": "edit_form"}), KeyboardButtonColor.SECONDARY
).add(
    Text("Пользователи бота", {"admin_menu": "users_list"}), KeyboardButtonColor.SECONDARY
).row().add(
    Text("Управление администраторами", {"admin_menu": "admins_edit"}), KeyboardButtonColor.SECONDARY
).add(
    Text("Выдача награды/штрафа", {"admin_menu": "present_reward"}), KeyboardButtonColor.SECONDARY
).row().add(
    Text("Изменение состава", {"admin_menu": "edit_content"}), KeyboardButtonColor.SECONDARY
).row().add(
    Text("Рассылки и опросы", {"admin_menu": "mailing"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Экспорт", {"admin_menu": "export"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("В главное меню", {"admin_menu": "back"}), KeyboardButtonColor.NEGATIVE
)

manage_admins = Keyboard().add(
    Text("Добавить администратора", {"manage_admins": "add_admin"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Удалить администратора", {"manage_admins": "delete_admins"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Назад", {"manage_admins": "back"}), KeyboardButtonColor.NEGATIVE
)

manage_content = Keyboard().add(
    Text("Товары", {"edit_content": "products"}), KeyboardButtonColor.PRIMARY
).add(
    Text("Профессии", {"edit_content": "professions"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Типы кают", {"edit_content": "cabins"}), KeyboardButtonColor.PRIMARY
).add(
    Text("Статусы", {"edit_content": "statuses"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Квесты", {"edit_content": "quests"}), KeyboardButtonColor.PRIMARY
).add(
    Text("Дейлики", {"edit_content": "daylics"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Назад", {"edit_content": "back"}), KeyboardButtonColor.NEGATIVE
)


def gen_type_change_content(item):
    return Keyboard().add(
        Text("Добавить", {item: "add"}), KeyboardButtonColor.POSITIVE
    ).add(
        Text("Удалить", {item: "delete"}), KeyboardButtonColor.NEGATIVE
    ).row().add(
        Text("Назад", {item: "back"}), KeyboardButtonColor.NEGATIVE
    )


form_activity = Keyboard().add(
    Text("Поиск анкеты пользователя", {"form": "search"}), KeyboardButtonColor.SECONDARY
).row().add(
    Text("Редактировать анкету", {"form": "edit"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
)

form_search = Keyboard().add(
    Text("Назад", {"form_search": "back"}), KeyboardButtonColor.NEGATIVE
)

next_form = Keyboard(inline=True).add(
    Callback("->", {"form": "next"}), KeyboardButtonColor.PRIMARY
)

previous_form = Keyboard(inline=True).add(
    Callback("<-", {"form": "previous"}), KeyboardButtonColor.PRIMARY
)

how_edit_form = Keyboard().add(
    Text("Поменять некоторые поля", {"form_edit": "edit_fields"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Назад", {"form_edit": "back"}), KeyboardButtonColor.NEGATIVE
)

confirm_edit_form = Keyboard().add(
    Text("Подтвердить изменения", {"form_edit": "confirm"}), KeyboardButtonColor.POSITIVE
).row().add(
    Text("Отменить изменения", {"form_edit": "decline"}), KeyboardButtonColor.NEGATIVE
)

bank = Keyboard().add(
    Text("Баланс кошелька", {"bank_menu": "balance"}), KeyboardButtonColor.PRIMARY
).add(
    Text("Совершить сделку", {"bank_menu": "transfer"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("История сделок", {"bank_menu": "history"}), KeyboardButtonColor.PRIMARY
).add(
    Text("Запрос зарплаты", {"bank_menu": "ask_salary"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Постоянные расходы", {"bank_menu": "fixed_costs"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Пожертвования в храм", {"bank_menu": "donate"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
)

shop_menu = Keyboard().add(
    Text("Услуги", {"shop": "services"}), KeyboardButtonColor.PRIMARY
).add(
    Text("Товары", {"shop": "products"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Назад", {"shop": "back"}), KeyboardButtonColor.NEGATIVE
)

donate_menu = Keyboard().add(
    Text("Пожертвовать", {"bank": "create_donate"}), KeyboardButtonColor.PRIMARY
).row().add(
    Text("Назад", {"menu": "bank"}), KeyboardButtonColor.NEGATIVE
)


async def get_settings_menu(user_id: int) -> Keyboard:
    notifications_enabled, freeze, admin = (
        await db.select([db.User.notification_enabled, db.Form.freeze, db.User.admin])
        .select_from(db.User.join(db.Form, db.User.user_id == db.Form.user_id))
        .where(db.User.user_id == user_id).gino.first())
    settings_menu = (Keyboard().add(
        Text(f"Уведомления: {'✅' if notifications_enabled else '❌'}", {"settings": "notifications"}),
        KeyboardButtonColor.SECONDARY
    ).row().add(
        Text(f"{'Разморозить' if freeze else 'Заморозить'} анкету", {"settings": "freeze_request"}),
        KeyboardButtonColor.PRIMARY
    ).row().add(
        Text("Удалить анкету", {"settings": "delete_request"}), KeyboardButtonColor.NEGATIVE
    ))
    if admin > 0:
        m_break = await db.select([db.Metadata.maintainence_break]).gino.scalar()
        settings_menu.row().add(
            Text(f"{'Вкл.' if not m_break else 'Выкл.'} техническое обслуживание",
                 {"settings": "maintainence"}),
            KeyboardButtonColor.NEGATIVE
        )
        settings_menu.add(
            Text("Перезапуск бота", {"settings": "restart"}), KeyboardButtonColor.NEGATIVE
        )
    settings_menu.row().add(
        Text("Назад", {"menu": "home"}), KeyboardButtonColor.NEGATIVE
    )
    return settings_menu


def another_profession_to_user(user_id: int):
    return Keyboard().add(Text("Другая", {"skip_profession": user_id}), KeyboardButtonColor.NEGATIVE)
