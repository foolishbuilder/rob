from __future__ import annotations

import logging

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
        app.router.add_get("/guilds/{guild_id}/scan", self._handle_guild_scan)
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

        try:
            guild_id = int(request.match_info["guild_id"])
        except (KeyError, ValueError):
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

        try:
            guild_id = int(request.match_info["guild_id"])
        except (KeyError, ValueError):
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

        try:
            guild_id = int(request.match_info["guild_id"])
        except (KeyError, ValueError):
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

        enabled = bool(payload.get("enabled"))
        reason = str(payload.get("reason") or "").strip() or None
        if enabled:
            await self.bot.maintenance_service.enable(reason=reason)
        else:
            await self.bot.maintenance_service.disable()

        state = await self.bot.maintenance_service.get_state()
        return web.json_response({"ok": True, "enabled": state.enabled, "reason": state.reason or ""})
