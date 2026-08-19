import hashlib
import hmac
import json
import os
import urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiohttp import web

from config import (
    BOT_TOKEN,
    CHANNEL_ID,
    ADMIN_IDS,
)

from database import (
    get_story,
    get_all_stories,
    get_open_dialogs,
    get_dialog,
    get_dialog_messages,
    get_admin_audit,
    get_extended_stats,
    get_analytics,
    get_admin_roles,
    get_admin_role,
    set_admin_role,
    get_complaints,
    update_complaint,
    get_story_versions,
    restore_story_version,
    get_moderator_metrics,
    get_top_stories,
    get_user_retention,
    get_sla_breaches,
    set_support_priority,
    get_support_priority,
    get_admin_notifications,
    mark_admin_notification_read,
    add_support_message,
    update_story_content,
    schedule_story,
    cancel_scheduled_story,
    publish_story,
    reject_story,
    log_admin_action,
)

from ai import (
    analyze_story,
    moderate_story,
)

from keyboards import (
    channel_story_keyboard,
)


# =========================================================
# TIMEZONE
# =========================================================

TZ = ZoneInfo(
    "Europe/Moscow"
)


# =========================================================
# MINI APP FILES
# =========================================================

BASE_DIR = Path(
    __file__
).resolve().parent

# В ZIP файле Mini App лежит в корне проекта:
#
# index.html
# app.js
# style.css
#
# Поэтому здесь НЕ должна использоваться папка miniapp.

WEB_DIR = BASE_DIR


# =========================================================
# JSON HELPERS
# =========================================================

def _json(row):

    if row is None:
        return None

    if hasattr(row, "keys"):

        return {
            key: row[key]
            for key in row.keys()
        }

    return row


def _rows(rows):

    return [
        _json(row)
        for row in rows
    ]


# =========================================================
# TELEGRAM MINI APP AUTH
# =========================================================

def validate_init_data(
    init_data: str,
):

    if not init_data:
        return None

    try:

        data = dict(
            urllib.parse.parse_qsl(
                init_data,
                keep_blank_values=True,
            )
        )

        received_hash = data.pop(
            "hash",
            None,
        )

        if not received_hash:
            return None

        check_string = "\n".join(
            f"{key}={data[key]}"
            for key in sorted(data)
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()

        expected_hash = hmac.new(
            secret_key,
            check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            expected_hash,
            received_hash,
        ):
            return None

        auth_date = int(
            data.get(
                "auth_date",
                "0",
            )
        )

        if (
            abs(
                datetime.now().timestamp()
                - auth_date
            )
            > 86400
        ):
            return None

        user = json.loads(
            data.get(
                "user",
                "{}",
            )
        )

        data["user"] = user

        return data

    except Exception as error:

        print(
            "MINI APP AUTH ERROR:",
            error,
        )

        return None


# =========================================================
# ADMIN AUTH
# =========================================================

def auth(
    request,
    allowed=None,
):

    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        "",
    )

    data = validate_init_data(
        init_data
    )

    if not data:

        raise web.HTTPUnauthorized(
            text="Invalid Telegram initData"
        )

    user = (
        data.get("user")
        or {}
    )

    user_id = int(
        user.get(
            "id",
            0,
        )
    )

    if user_id not in ADMIN_IDS:

        raise web.HTTPForbidden(
            text="Admin access required"
        )

    role = get_admin_role(
        user_id
    )

    if (
        allowed
        and role not in allowed
    ):

        raise web.HTTPForbidden(
            text="Insufficient role"
        )

    return user_id


# =========================================================
# MINI APP FRONTEND
# =========================================================

async def index(request):

    index_path = (
        WEB_DIR
        / "index.html"
    )

    if not index_path.exists():

        raise web.HTTPNotFound(
            text=(
                "Mini App index.html "
                "not found"
            )
        )

    return web.FileResponse(
        index_path
    )


async def static_file(request):

    name = request.match_info[
        "name"
    ]

    if (
        "/"
        in name
        or "\\"
        in name
    ):

        raise web.HTTPNotFound()

    path = (
        WEB_DIR
        / name
    )

    if not path.exists():

        raise web.HTTPNotFound()

    return web.FileResponse(
        path
    )


# =========================================================
# DASHBOARD
# =========================================================

async def dashboard(request):

    user_id = auth(
        request
    )

    stats = (
        get_extended_stats()
    )

    return web.json_response(
        {
            "me": {
                "id": user_id,
                "role": get_admin_role(
                    user_id
                ),
            },
            "stats": stats,
            "analytics": get_analytics(),
            "complaints": _rows(
                get_complaints(
                    "new",
                    20,
                )
            ),
            "sla_breaches": _rows(
                get_sla_breaches()
            ),
            "notifications": _rows(
                get_admin_notifications(
                    user_id,
                    False,
                    20,
                )
            ),
            "top_stories": _rows(
                get_top_stories(10)
            ),
            "retention": _json(
                get_user_retention()
            ),
        }
    )


# =========================================================
# STORIES
# =========================================================

async def stories(request):

    auth(request)

    status = request.query.get(
        "status"
    )

    rows = get_all_stories()

    if status:

        rows = [
            row
            for row in rows
            if row["status"] == status
        ]

    return web.json_response(
        {
            "items": _rows(
                rows[:100]
            )
        }
    )


async def story(request):

    auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
            "analyst",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    return web.json_response(
        {
            "story": _json(row),
            "versions": _rows(
                get_story_versions(
                    story_id
                )
            ),
        }
    )


async def story_edit(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    payload = await request.json()

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    text = str(
        payload.get(
            "text",
            row["text"],
        )
    )[:20000]

    post_text = str(
        payload.get(
            "post_text",
            row["post_text"]
            or "",
        )
    )[:10000]

    update_story_content(
        story_id,
        text,
        post_text,
        user_id,
    )

    log_admin_action(
        user_id,
        "miniapp_edit_story",
        story_id=story_id,
        user_id=row["user_id"],
    )

    return web.json_response(
        {
            "story": _json(
                get_story(
                    story_id
                )
            )
        }
    )


# =========================================================
# AI
# =========================================================

async def story_ai(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    result = await analyze_story(
        row["text"]
    )

    from database import (
        update_ai_result
    )

    update_ai_result(
        story_id,
        result,
    )

    log_admin_action(
        user_id,
        "miniapp_ai_retry",
        story_id=story_id,
        user_id=row["user_id"],
    )

    return web.json_response(
        {
            "story": _json(
                get_story(
                    story_id
                )
            )
        }
    )


async def story_moderate_ai(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    result = await moderate_story(
        row["text"]
    )

    from database import (
        update_ai_moderation_result
    )

    update_ai_moderation_result(
        story_id,
        result,
    )

    log_admin_action(
        user_id,
        "miniapp_ai_moderate",
        story_id=story_id,
        user_id=row["user_id"],
    )

    return web.json_response(
        {
            "story": _json(
                get_story(
                    story_id
                )
            )
        }
    )


# =========================================================
# PUBLISH
# =========================================================

async def story_publish(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    text = (
        row["post_text"]
        or ""
    ).strip()

    if not text:

        raise web.HTTPBadRequest(
            text="Post is empty"
        )

    bot = request.app["bot"]

    sent = await bot.send_message(
        CHANNEL_ID,
        text,
        reply_markup=channel_story_keyboard(
            story_id,
            None,
        ),
    )

    publish_story(
        story_id,
        sent.message_id,
    )

    log_admin_action(
        user_id,
        "miniapp_publish",
        story_id=story_id,
        user_id=row["user_id"],
    )

    return web.json_response(
        {
            "story": _json(
                get_story(
                    story_id
                )
            ),
            "message_id": sent.message_id,
        }
    )


# =========================================================
# REJECT
# =========================================================

async def story_reject(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    payload = await request.json()

    reason = str(
        payload.get(
            "reason",
            "",
        )
    )[:1000]

    reject_story(
        story_id,
        reason,
    )

    log_admin_action(
        user_id,
        "miniapp_reject",
        story_id=story_id,
        user_id=row["user_id"],
    )

    return web.json_response(
        {
            "story": _json(
                get_story(
                    story_id
                )
            )
        }
    )


# =========================================================
# SCHEDULE
# =========================================================

async def story_schedule(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    payload = await request.json()

    raw = str(
        payload.get(
            "scheduled_at",
            "",
        )
    )

    try:

        dt = datetime.fromisoformat(
            raw.replace(
                "Z",
                "+00:00",
            )
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=TZ
            )

        if (
            dt
            <= datetime.now(
                dt.tzinfo
            )
        ):

            raise ValueError()

    except Exception:

        raise web.HTTPBadRequest(
            text=(
                "Invalid future "
                "datetime"
            )
        )

    schedule_story(
        story_id,
        dt.astimezone(
            ZoneInfo("UTC")
        ).isoformat(),
        user_id,
    )

    log_admin_action(
        user_id,
        "miniapp_schedule",
        story_id=story_id,
        user_id=row["user_id"],
        details=dt.isoformat(),
    )

    return web.json_response(
        {
            "story": _json(
                get_story(
                    story_id
                )
            )
        }
    )


async def story_unschedule(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    story_id = int(
        request.match_info["id"]
    )

    row = get_story(
        story_id
    )

    if not row:

        raise web.HTTPNotFound()

    cancel_scheduled_story(
        story_id
    )

    log_admin_action(
        user_id,
        "miniapp_unschedule",
        story_id=story_id,
    )

    return web.json_response(
        {
            "story": _json(
                get_story(
                    story_id
                )
            )
        }
    )


# =========================================================
# BULK
# =========================================================

async def bulk(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    payload = await request.json()

    ids = [
        int(x)
        for x in payload.get(
            "ids",
            [],
        )
    ]

    action = payload.get(
        "action"
    )

    changed = []

    for story_id in ids[:100]:

        row = get_story(
            story_id
        )

        if not row:
            continue

        if action == "reject":

            reject_story(
                story_id,
                "Массовое отклонение через Mini App",
            )

            changed.append(
                story_id
            )

        elif action == "unschedule":

            cancel_scheduled_story(
                story_id
            )

            changed.append(
                story_id
            )

    log_admin_action(
        user_id,
        f"miniapp_bulk_{action}",
        details=json.dumps(
            changed
        ),
    )

    return web.json_response(
        {
            "changed": changed
        }
    )


# =========================================================
# VERSIONS
# =========================================================

async def versions(request):

    auth(request)

    story_id = int(
        request.match_info["id"]
    )

    return web.json_response(
        {
            "items": _rows(
                get_story_versions(
                    story_id
                )
            )
        }
    )


async def restore_version(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "editor",
        },
    )

    version_id = int(
        request.match_info[
            "version_id"
        ]
    )

    row = restore_story_version(
        version_id,
        user_id,
    )

    if not row:

        raise web.HTTPNotFound()

    log_admin_action(
        user_id,
        "miniapp_restore_version",
        story_id=row["id"],
    )

    return web.json_response(
        {
            "story": _json(row)
        }
    )


# =========================================================
# SUPPORT
# =========================================================

async def dialogs(request):

    auth(
        request,
        {
            "owner",
            "moderator",
            "support",
        },
    )

    return web.json_response(
        {
            "items": _rows(
                get_open_dialogs()
            )
        }
    )


async def dialog(request):

    auth(
        request,
        {
            "owner",
            "moderator",
            "support",
        },
    )

    dialog_id = int(
        request.match_info["id"]
    )

    data = get_dialog(
        dialog_id
    )

    if not data:

        raise web.HTTPNotFound()

    return web.json_response(
        {
            "dialog": _json(data),
            "messages": _rows(
                get_dialog_messages(
                    dialog_id
                )
            ),
            "sla": _json(
                get_support_priority(
                    dialog_id
                )
            ),
        }
    )


async def dialog_update(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "support",
        },
    )

    dialog_id = int(
        request.match_info["id"]
    )

    data = get_dialog(
        dialog_id
    )

    if not data:

        raise web.HTTPNotFound()

    payload = await request.json()

    if "priority" in payload:

        set_support_priority(
            dialog_id,
            payload["priority"],
        )

    if "assigned_admin_id" in payload:

        from database import (
            assign_dialog
        )

        assign_dialog(
            dialog_id,
            (
                int(
                    payload[
                        "assigned_admin_id"
                    ]
                )
                if payload[
                    "assigned_admin_id"
                ]
                else user_id
            ),
        )

    if "status" in payload:

        from database import (
            set_dialog_status
        )

        set_dialog_status(
            dialog_id,
            payload["status"],
        )

    log_admin_action(
        user_id,
        "miniapp_dialog_update",
        dialog_id=dialog_id,
        user_id=data["user_id"],
    )

    return web.json_response(
        {
            "dialog": _json(
                get_dialog(
                    dialog_id
                )
            ),
            "sla": _json(
                get_support_priority(
                    dialog_id
                )
            ),
        }
    )


# =========================================================
# COMPLAINTS
# =========================================================

async def complaints(request):

    auth(
        request,
        {
            "owner",
            "moderator",
            "support",
        },
    )

    return web.json_response(
        {
            "items": _rows(
                get_complaints(
                    request.query.get(
                        "status"
                    ),
                    100,
                )
            )
        }
    )


async def complaint_update(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "support",
        },
    )

    complaint_id = int(
        request.match_info["id"]
    )

    payload = await request.json()

    update_complaint(
        complaint_id,
        payload.get("status"),
        payload.get("priority"),
        payload.get("assigned_admin_id"),
    )

    log_admin_action(
        user_id,
        "miniapp_complaint_update",
        details=str(
            complaint_id
        ),
    )

    return web.json_response(
        {
            "ok": True
        }
    )


# =========================================================
# ROLES
# =========================================================

async def roles(request):

    user_id = auth(
        request,
        {"owner"},
    )

    if (
        get_admin_role(user_id)
        != "owner"
    ):

        raise web.HTTPForbidden()

    return web.json_response(
        {
            "items": _rows(
                get_admin_roles()
            )
        }
    )


async def role_update(request):

    user_id = auth(
        request,
        {"owner"},
    )

    target_id = int(
        request.match_info["id"]
    )

    payload = await request.json()

    role = payload.get(
        "role"
    )

    if role not in {
        "owner",
        "moderator",
        "support",
        "analyst",
        "editor",
    }:

        raise web.HTTPBadRequest(
            text="Invalid role"
        )

    set_admin_role(
        target_id,
        role,
    )

    log_admin_action(
        user_id,
        "miniapp_role_update",
        user_id=target_id,
        details=role,
    )

    return web.json_response(
        {
            "ok": True
        }
    )


# =========================================================
# AUDIT
# =========================================================

async def audit(request):

    auth(
        request,
        {
            "owner",
            "analyst",
        },
    )

    return web.json_response(
        {
            "items": _rows(
                get_admin_audit(
                    200
                )
            )
        }
    )


# =========================================================
# ANALYTICS
# =========================================================

async def analytics(request):

    auth(
        request,
        {
            "owner",
            "analyst",
        },
    )

    return web.json_response(
        {
            "analytics":
                get_analytics(),

            "moderators":
                _rows(
                    get_moderator_metrics(
                        30
                    )
                ),

            "top":
                _rows(
                    get_top_stories(
                        20
                    )
                ),

            "retention":
                _json(
                    get_user_retention()
                ),
        }
    )


# =========================================================
# NOTIFICATIONS
# =========================================================

async def notifications(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "support",
            "analyst",
            "editor",
        },
    )

    return web.json_response(
        {
            "items": _rows(
                get_admin_notifications(
                    user_id,
                    False,
                    100,
                )
            )
        }
    )


async def notification_read(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "support",
            "analyst",
            "editor",
        },
    )

    notification_id = int(
        request.match_info["id"]
    )

    mark_admin_notification_read(
        notification_id,
        user_id,
    )

    return web.json_response(
        {
            "ok": True
        }
    )


# =========================================================
# DIALOG MESSAGE
# =========================================================

async def dialog_message(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "support",
        },
    )

    dialog_id = int(
        request.match_info["id"]
    )

    data = get_dialog(
        dialog_id
    )

    if not data:

        raise web.HTTPNotFound()

    payload = await request.json()

    text = str(
        payload.get(
            "text",
            "",
        )
    ).strip()

    if not text:

        raise web.HTTPBadRequest(
            text="Empty message"
        )

    if data["status"] != "open":

        raise web.HTTPBadRequest(
            text="Dialog closed"
        )

    add_support_message(
        dialog_id,
        user_id,
        "admin",
        text[:4000],
    )

    try:

        await request.app["bot"].send_message(
            data["user_id"],
            (
                "💬 <b>Сообщение поддержки:</b>\n\n"
                + text[:4000]
            ),
            parse_mode="HTML",
        )

    except Exception as error:

        print(
            "MINIAPP SUPPORT SEND ERROR:",
            error,
        )

    log_admin_action(
        user_id,
        "miniapp_support_message",
        dialog_id=dialog_id,
        user_id=data["user_id"],
    )

    return web.json_response(
        {
            "dialog": _json(
                get_dialog(
                    dialog_id
                )
            ),
            "messages": _rows(
                get_dialog_messages(
                    dialog_id
                )
            ),
        }
    )


# =========================================================
# CONTACT USER
# =========================================================

async def story_contact(request):

    user_id = auth(
        request
    )

    story_id = int(
        request.match_info["id"]
    )

    story = get_story(
        story_id
    )

    if not story:

        raise web.HTTPNotFound()

    try:

        await request.app["bot"].send_message(
            story["user_id"],
            (
                "💬 С вами хочет связаться "
                "сотрудник поддержки.\n\n"
                "Если вы готовы продолжить диалог, "
                "откройте «🆘 Экстренная поддержка»."
            ),
        )

    except Exception as error:

        print(
            "MINIAPP CONTACT ERROR:",
            error,
        )

    log_admin_action(
        user_id,
        "miniapp_contact_user",
        story_id=story_id,
        user_id=story["user_id"],
    )

    return web.json_response(
        {
            "ok": True
        }
    )


# =========================================================
# DIALOG ACTION
# =========================================================

async def dialog_action(request):

    user_id = auth(
        request,
        {
            "owner",
            "moderator",
            "support",
        },
    )

    dialog_id = int(
        request.match_info["id"]
    )

    data = get_dialog(
        dialog_id
    )

    if not data:

        raise web.HTTPNotFound()

    action = request.match_info[
        "action"
    ]

    from database import (
        set_dialog_status,
        assign_dialog,
        unassign_dialog,
        close_dialog,
    )

    if action == "assign":

        assign_dialog(
            dialog_id,
            user_id,
        )

    elif action == "waiting":

        set_dialog_status(
            dialog_id,
            "waiting_user",
        )

    elif action == "resolved":

        set_dialog_status(
            dialog_id,
            "resolved",
        )

    elif action == "close":

        close_dialog(
            dialog_id
        )

    elif action == "exit":

        unassign_dialog(
            dialog_id
        )

        set_dialog_status(
            dialog_id,
            "new",
        )

    else:

        raise web.HTTPBadRequest(
            text="Unknown action"
        )

    log_admin_action(
        user_id,
        f"miniapp_dialog_{action}",
        dialog_id=dialog_id,
        user_id=data["user_id"],
    )

    return web.json_response(
        {
            "dialog": _json(
                get_dialog(
                    dialog_id
                )
            )
        }
    )


# =========================================================
# CREATE APP
# =========================================================

def create_app(bot):

    app = web.Application()

    app["bot"] = bot

    # Mini App

    app.router.add_get(
        "/admin",
        index,
    )

    app.router.add_get(
        "/admin/",
        index,
    )

    app.router.add_get(
        "/admin/{name}",
        static_file,
    )

    # API

    app.router.add_get(
        "/admin/api/dashboard",
        dashboard,
    )

    app.router.add_get(
        "/admin/api/stories",
        stories,
    )

    app.router.add_get(
        "/admin/api/story/{id}",
        story,
    )

    app.router.add_put(
        "/admin/api/story/{id}",
        story_edit,
    )

    app.router.add_post(
        "/admin/api/story/{id}/ai",
        story_ai,
    )

    app.router.add_post(
        "/admin/api/story/{id}/ai-moderate",
        story_moderate_ai,
    )

    app.router.add_post(
        "/admin/api/story/{id}/publish",
        story_publish,
    )

    app.router.add_post(
        "/admin/api/story/{id}/contact",
        story_contact,
    )

    app.router.add_post(
        "/admin/api/story/{id}/reject",
        story_reject,
    )

    app.router.add_post(
        "/admin/api/story/{id}/schedule",
        story_schedule,
    )

    app.router.add_post(
        "/admin/api/story/{id}/unschedule",
        story_unschedule,
    )

    app.router.add_post(
        "/admin/api/bulk",
        bulk,
    )

    app.router.add_get(
        "/admin/api/story/{id}/versions",
        versions,
    )

    app.router.add_post(
        "/admin/api/version/{version_id}/restore",
        restore_version,
    )

    app.router.add_get(
        "/admin/api/dialogs",
        dialogs,
    )

    app.router.add_get(
        "/admin/api/dialog/{id}",
        dialog,
    )

    app.router.add_put(
        "/admin/api/dialog/{id}",
        dialog_update,
    )

    app.router.add_post(
        "/admin/api/dialog/{id}/message",
        dialog_message,
    )

    app.router.add_post(
        "/admin/api/dialog/{id}/{action}",
        dialog_action,
    )

    app.router.add_get(
        "/admin/api/complaints",
        complaints,
    )

    app.router.add_put(
        "/admin/api/complaint/{id}",
        complaint_update,
    )

    app.router.add_get(
        "/admin/api/roles",
        roles,
    )

    app.router.add_put(
        "/admin/api/role/{id}",
        role_update,
    )

    app.router.add_get(
        "/admin/api/audit",
        audit,
    )

    app.router.add_get(
        "/admin/api/analytics",
        analytics,
    )

    app.router.add_get(
        "/admin/api/notifications",
        notifications,
    )

    app.router.add_post(
        "/admin/api/notification/{id}/read",
        notification_read,
    )

    return app


# =========================================================
# START SERVER
# =========================================================

async def start_admin_web(bot):

    app = create_app(
        bot
    )

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    port = int(
        os.getenv(
            "PORT",
            "8080",
        )
    )

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port,
    )

    await site.start()

    print(
        f"🖥 Admin Mini App server "
        f"listening on :{port}"
    )

    print(
        f"🖥 Mini App files directory: "
        f"{WEB_DIR}"
    )

    return runner
