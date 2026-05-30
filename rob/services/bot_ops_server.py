from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
import discord

log = logging.getLogger(__name__)


class BotOpsServer:
    def __init__(
        self,
        *,
        bot: discord.Client,
        host: str,
        port: int,
        secret: str | None = None,
    ) -> None:
        self.bot = bot
        self.host = host
        self.port = port
        self.secret = secret
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        if self._runner is not None:
            return

        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/maintenance", self._handle_get_maintenance)
        app.router.add_get("/guilds/{guild_id}/scan", self._handle_guild_scan)
        app.router.add_get("/guilds/{guild_id}/count", self._handle_get_count)
        app.router.add_post(
            "/guilds/{guild_id}/leaderboard/public/refresh-names",
            self._handle_refresh_public_names,
        )
        app.router.add_post(
            "/guilds/{guild_id}/leaderboard/refresh",
            self._handle_refresh_leaderboard,
        )
        app.router.add_post("/ops/sends/process", self._handle_process_send)
        app.router.add_post("/sends/process", self._handle_process_send)
        app.router.add_post("/maintenance", self._handle_set_maintenance)
        app.router.add_post("/guilds/{guild_id}/count", self._handle_set_count)
        app.router.add_post("/guilds/{guild_id}/dommes", self._handle_add_domme)
        app.router.add_post("/guilds/{guild_id}/dommes/remove", self._handle_remove_domme)
        app.router.add_post("/guilds/{guild_id}/subs", self._handle_add_sub)
        app.router.add_post("/guilds/{guild_id}/subs/remove", self._handle_remove_sub)
        app.router.add_post("/guilds/{guild_id}/send-requests/add", self._handle_request_send_add)
        app.router.add_post(
            "/guilds/{guild_id}/send-requests/remove",
            self._handle_request_send_remove,
        )
        app.router.add_post("/block", self._handle_block_user)
        app.router.add_post("/unblock", self._handle_unblock_user)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self.host, port=self.port)
        await self._site.start()
        log.info("Bot ops server listening on http://%s:%s.", self.host, self.port)

    async def stop(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None

    def _is_authorized(self, request: web.Request) -> bool:
        if not self.secret:
            return True
        return request.headers.get("X-Rob-Ops-Secret") == self.secret

    async def _handle_health(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        return web.json_response({"ok": True, "bot_user_id": getattr(self.bot.user, "id", None)})

    async def _handle_guild_scan(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)

        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return web.json_response(
                {
                    "guild_id": guild_id,
                    "guild_name": None,
                    "channels": [],
                    "roles": [],
                    "source": "bot-session",
                    "error": "Guild is not currently available in the running bot cache.",
                },
                status=404,
            )

        channels = [
            {
                "id": channel.id,
                "name": channel.name,
                "kind": type(channel).__name__,
            }
            for channel in sorted(guild.channels, key=lambda item: (item.name.lower(), item.id))
            if isinstance(channel, discord.TextChannel)
        ]
        roles = [
            {
                "id": role.id,
                "name": role.name,
            }
            for role in sorted(guild.roles, key=lambda item: (item.name.lower(), item.id))
            if role.name != "@everyone"
        ]
        return web.json_response(
            {
                "guild_id": guild.id,
                "guild_name": guild.name,
                "channels": channels,
                "roles": roles,
                "source": "bot-session",
            }
        )

    async def _handle_refresh_public_names(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)

        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return web.json_response({"error": "guild_not_in_cache", "guild_id": guild_id}, status=404)

        if not hasattr(self.bot, "dommes_repo"):
            return web.json_response({"error": "dommes_repo_unavailable"}, status=500)

        dommes = await self.bot.dommes_repo.list_for_guild(guild_id)
        updated = 0
        for domme in dommes:
            label: str | None = None
            member = guild.get_member(domme.discord_user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(domme.discord_user_id)
                except (discord.NotFound, discord.HTTPException):
                    member = None
            if member is not None:
                label = (member.display_name or member.name or "").strip() or None

            if label:
                await self.bot.dommes_repo.set_public_display_name(
                    guild_id=guild_id,
                    discord_user_id=domme.discord_user_id,
                    label=label,
                )
                updated += 1

        return web.json_response(
            {
                "ok": True,
                "guild_id": guild_id,
                "registered_dommes": len(dommes),
                "updated_display_names": updated,
            }
        )

    async def _handle_refresh_leaderboard(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)

        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)

        if not hasattr(self.bot, "leaderboard_service"):
            return web.json_response({"error": "leaderboard_service_unavailable"}, status=500)

        refreshed = await self.bot.leaderboard_service.refresh_guild(guild_id)
        return web.json_response({"ok": bool(refreshed), "guild_id": guild_id, "refreshed": bool(refreshed)})

    async def _handle_process_send(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)

        if not hasattr(self.bot, "send_queue_service"):
            return web.json_response({"error": "send_queue_service_unavailable"}, status=500)

        try:
            payload = await request.json()
        except Exception:
            payload = {}

        try:
            send_id = int(payload.get("send_id"))
        except (TypeError, ValueError):
            return web.json_response({"error": "invalid_send_id"}, status=400)

        guild_id = payload.get("guild_id")
        try:
            guild_id = int(guild_id) if guild_id is not None else None
        except (TypeError, ValueError):
            return web.json_response({"error": "invalid_guild_id"}, status=400)

        await self.bot.send_queue_service.notify_send(send_id)
        log.info(
            "Accepted send processing notification send_id=%s guild_id=%s.",
            send_id,
            guild_id,
        )
        return web.json_response(
            {
                "ok": True,
                "queued": True,
                "send_id": send_id,
                "guild_id": guild_id,
            }
        )

    async def _handle_set_maintenance(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)

        if not hasattr(self.bot, "maintenance_service"):
            return web.json_response({"error": "maintenance_service_unavailable"}, status=500)

        try:
            payload = await request.json()
        except Exception:
            payload = {}

        enabled = self._payload_bool(payload, "enabled")
        reason = str(payload.get("reason") or "").strip() or None
        if enabled:
            await self.bot.maintenance_service.enable(reason=reason)
        else:
            await self.bot.maintenance_service.disable()

        state = await self.bot.maintenance_service.get_state()
        return web.json_response({"ok": True, "enabled": state.enabled, "reason": state.reason or ""})

    async def _handle_get_maintenance(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "maintenance_service"):
            return web.json_response({"error": "maintenance_service_unavailable"}, status=500)
        state = await self.bot.maintenance_service.get_state()
        return web.json_response({"ok": True, "enabled": state.enabled, "reason": state.reason or ""})

    async def _handle_get_count(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "counting_service"):
            return web.json_response({"error": "counting_service_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        state = await self.bot.counting_service.get_or_create_state(guild_id)
        return web.json_response(
            {
                "ok": True,
                "guild_id": guild_id,
                "current_number": state.current_number,
                "channel_id": state.channel_id,
                "is_enabled": state.is_enabled,
                "pending_restore": state.pending_restore,
            }
        )

    async def _handle_set_count(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "counting_service"):
            return web.json_response({"error": "counting_service_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        payload = await self._json_payload(request)
        try:
            number = max(0, int(payload.get("number")))
        except (TypeError, ValueError):
            return web.json_response({"error": "invalid_number"}, status=400)
        state = await self.bot.counting_service.set_current_number(guild_id, number)
        return web.json_response(
            {
                "ok": True,
                "guild_id": guild_id,
                "current_number": state.current_number,
                "channel_id": state.channel_id,
                "is_enabled": state.is_enabled,
            }
        )

    async def _handle_add_domme(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "registration_service"):
            return web.json_response({"error": "registration_service_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        payload = await self._json_payload(request)
        discord_user_id = self._payload_user_id(payload)
        throne_input = str(payload.get("throne_input") or "").strip()
        if discord_user_id is None:
            return web.json_response({"error": "invalid_discord_user_id"}, status=400)
        if not throne_input:
            return web.json_response({"error": "missing_throne_input"}, status=400)
        try:
            result = await self.bot.registration_service.register_domme(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                throne_input=throne_input,
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        await self._refresh_guild(guild_id)
        return web.json_response(
            {
                "ok": True,
                "guild_id": guild_id,
                "discord_user_id": result.domme.discord_user_id,
                "domme_id": result.domme.id,
                "throne_handle": result.domme.throne_handle,
                "throne_creator_id": result.domme.throne_creator_id,
                "webhook_url": result.webhook_url,
            }
        )

    async def _handle_remove_domme(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "dommes_repo"):
            return web.json_response({"error": "dommes_repo_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        payload = await self._json_payload(request)
        target = str(payload.get("target") or "").strip()
        if not target:
            return web.json_response({"error": "missing_target"}, status=400)
        domme = await self._resolve_domme(guild_id, target)
        if domme is None:
            return web.json_response({"error": "domme_not_found"}, status=404)
        removed = await self.bot.dommes_repo.remove_by_user_id(guild_id, domme.discord_user_id)
        if removed is None:
            return web.json_response({"error": "domme_not_found"}, status=404)
        await self._refresh_guild(guild_id)
        return web.json_response(
            {
                "ok": True,
                "guild_id": guild_id,
                "discord_user_id": removed.discord_user_id,
                "throne_handle": removed.throne_handle,
            }
        )

    async def _handle_add_sub(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "registration_service"):
            return web.json_response({"error": "registration_service_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        payload = await self._json_payload(request)
        discord_user_id = self._payload_user_id(payload)
        send_names = self._payload_send_names(payload)
        if discord_user_id is None:
            return web.json_response({"error": "invalid_discord_user_id"}, status=400)
        if not send_names:
            return web.json_response({"error": "missing_send_names"}, status=400)
        try:
            result = await self.bot.registration_service.register_sub(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                send_names=[str(value) for value in send_names],
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        await self._refresh_guild(guild_id)
        return web.json_response(
            {
                "ok": True,
                "guild_id": guild_id,
                "discord_user_id": result.sub.discord_user_id,
                "sub_id": result.sub.id,
                "send_names": list(result.send_names),
            }
        )

    async def _handle_remove_sub(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "subs_repo"):
            return web.json_response({"error": "subs_repo_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        payload = await self._json_payload(request)
        target = str(payload.get("target") or "").strip()
        if not target:
            return web.json_response({"error": "missing_target"}, status=400)
        removed = None
        if target.isdigit():
            removed = await self.bot.subs_repo.remove_by_user_id(guild_id, int(target))
        if removed is None:
            removed = await self.bot.subs_repo.remove_by_send_name(guild_id, target)
        if removed is None:
            return web.json_response({"error": "sub_not_found"}, status=404)
        await self._refresh_guild(guild_id)
        return web.json_response(
            {
                "ok": True,
                "guild_id": guild_id,
                "discord_user_id": removed.discord_user_id,
                "send_name": removed.send_name,
            }
        )

    async def _handle_request_send_add(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "send_change_request_service"):
            return web.json_response({"error": "send_change_request_service_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        payload = await self._json_payload(request)
        domme_lookup = str(payload.get("domme_lookup") or "").strip()
        requested_by = str(payload.get("requested_by") or "rob-cli").strip() or "rob-cli"
        sub_name = str(payload.get("sub_name") or "").strip() or None
        note = str(payload.get("note") or "").strip() or None
        method = str(payload.get("method") or "manual").strip() or "manual"
        currency = str(payload.get("currency") or "USD").strip().upper() or "USD"
        if not domme_lookup:
            return web.json_response({"error": "missing_domme_lookup"}, status=400)
        try:
            amount = float(payload.get("amount"))
        except (TypeError, ValueError):
            return web.json_response({"error": "invalid_amount"}, status=400)
        if amount <= 0:
            return web.json_response({"error": "invalid_amount"}, status=400)
        try:
            change_request = await self.bot.send_change_request_service.create_send_add_request(
                guild_id=guild_id,
                domme_lookup=domme_lookup,
                amount_cents=int(round(amount * 100)),
                sub_name=sub_name,
                requested_by=requested_by,
                currency=currency,
                method=method,
                note=note,
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response(
            {
                "ok": True,
                "request_id": change_request.id,
                "action": change_request.action,
                "status": change_request.status,
                "domme_user_id": change_request.domme_user_id,
            }
        )

    async def _handle_request_send_remove(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "send_change_request_service"):
            return web.json_response({"error": "send_change_request_service_unavailable"}, status=500)
        guild_id = self._match_guild_id(request)
        if guild_id is None:
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        payload = await self._json_payload(request)
        domme_lookup = str(payload.get("domme_lookup") or "").strip()
        requested_by = str(payload.get("requested_by") or "rob-cli").strip() or "rob-cli"
        if not domme_lookup:
            return web.json_response({"error": "missing_domme_lookup"}, status=400)
        try:
            send_id = int(payload.get("send_id"))
        except (TypeError, ValueError):
            return web.json_response({"error": "invalid_send_id"}, status=400)
        try:
            change_request = await self.bot.send_change_request_service.create_send_remove_request(
                guild_id=guild_id,
                domme_lookup=domme_lookup,
                send_id=send_id,
                requested_by=requested_by,
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response(
            {
                "ok": True,
                "request_id": change_request.id,
                "action": change_request.action,
                "status": change_request.status,
                "domme_user_id": change_request.domme_user_id,
                "target_send_id": change_request.target_send_id,
            }
        )

    async def _handle_block_user(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "blacklist_repo"):
            return web.json_response({"error": "blacklist_repo_unavailable"}, status=500)
        payload = await self._json_payload(request)
        discord_user_id = self._payload_user_id(payload)
        if discord_user_id is None:
            return web.json_response({"error": "invalid_discord_user_id"}, status=400)
        reason = str(payload.get("reason") or "rob-cli block").strip() or "rob-cli block"
        await self.bot.blacklist_repo.add(
            discord_user_id=discord_user_id,
            reason=reason,
            created_by=None,
            guild_id=0,
        )
        return web.json_response({"ok": True, "discord_user_id": discord_user_id, "blocked": True})

    async def _handle_unblock_user(self, request: web.Request) -> web.Response:
        if not self._is_authorized(request):
            return web.json_response({"error": "forbidden"}, status=403)
        if not hasattr(self.bot, "blacklist_repo"):
            return web.json_response({"error": "blacklist_repo_unavailable"}, status=500)
        payload = await self._json_payload(request)
        discord_user_id = self._payload_user_id(payload)
        if discord_user_id is None:
            return web.json_response({"error": "invalid_discord_user_id"}, status=400)
        await self.bot.blacklist_repo.remove(discord_user_id)
        return web.json_response({"ok": True, "discord_user_id": discord_user_id, "blocked": False})

    @staticmethod
    def _match_guild_id(request: web.Request) -> int | None:
        try:
            return int(request.match_info["guild_id"])
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    async def _json_payload(request: web.Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            return payload

        try:
            form_payload = await request.post()
        except Exception:
            return {}

        parsed: dict[str, Any] = {}
        for key in form_payload.keys():
            values = form_payload.getall(key)
            if not values:
                continue
            parsed[key] = values if len(values) > 1 else values[0]
        return parsed

    @staticmethod
    def _payload_user_id(payload: dict[str, Any]) -> int | None:
        try:
            return int(payload.get("discord_user_id"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _payload_bool(payload: dict[str, Any], key: str) -> bool:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _payload_send_names(payload: dict[str, Any]) -> list[str]:
        raw = payload.get("send_names")
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if raw is None:
            return []
        if isinstance(raw, str):
            parts = [segment.strip() for segment in raw.replace("\n", ",").split(",")]
            return [part for part in parts if part]
        return []

    async def _resolve_domme(self, guild_id: int, lookup: str):
        cleaned = lookup.strip()
        if cleaned.startswith("@"):
            cleaned = cleaned[1:]
        if hasattr(self.bot, "send_change_request_service"):
            return await self.bot.send_change_request_service._resolve_domme(guild_id, cleaned)
        if cleaned.isdigit() and hasattr(self.bot, "dommes_repo"):
            return await self.bot.dommes_repo.get_by_user_id(guild_id, int(cleaned))
        if hasattr(self.bot, "dommes_repo"):
            direct = await self.bot.dommes_repo.get_by_handle(guild_id, cleaned)
            if direct is not None:
                return direct
            for domme in await self.bot.dommes_repo.list_for_guild(guild_id):
                if (domme.public_display_name or "").casefold() == cleaned.casefold():
                    return domme
        return None

    async def _refresh_guild(self, guild_id: int) -> None:
        if not hasattr(self.bot, "leaderboard_service"):
            return
        try:
            await self.bot.leaderboard_service.refresh_guild(guild_id)
        except Exception:
            log.exception("Guild refresh failed after bot ops mutation guild_id=%s", guild_id)
