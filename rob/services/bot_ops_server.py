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
        leaderboard_service=None,
    ) -> None:
        self.bot = bot
        self.host = host
        self.port = port
        self.secret = secret
        self.leaderboard_service = leaderboard_service
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        if self._runner is not None:
            return

        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/guilds/{guild_id}/scan", self._handle_guild_scan)
        app.router.add_post("/guilds/{guild_id}/leaderboard/public/refresh-names", self._handle_refresh_public_names)

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
        if self.leaderboard_service is None:
            return web.json_response({"error": "leaderboard_service_unavailable"}, status=503)
        try:
            guild_id = int(request.match_info["guild_id"])
        except (KeyError, ValueError):
            return web.json_response({"error": "invalid_guild_id"}, status=400)
        updated = await self.leaderboard_service.refresh_public_display_names(guild_id)
        return web.json_response({"ok": True, "guild_id": guild_id, "updated": updated})
