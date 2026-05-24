from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from rob.discord.permissions import member_has_role
from rob.ui.cards.errors import error_card, error_permission
from rob.ui.cards.registration import registration_card
from rob.ui.cards.send_request import (
    send_request_domme_review_card,
    send_request_resolution_card,
    send_request_sent_card,
    send_request_sub_accepted_dm_card,
    send_request_sub_denied_dm_card,
)
from rob.ui.render import add_card_actions
from rob.ui.copy import PERMISSION_ROLE_MISSING, PERMISSION_ROLE_NOT_CONFIGURED
from rob.utils.money import dollars_to_cents, format_money_from_cents

if TYPE_CHECKING:
    from rob.discord.client import RobBot

log = logging.getLogger(__name__)

_MANUAL_METHODS = ["cashapp", "venmo", "paypal", "onlyfans", "loyalfans", "youpay", "other"]
_REQUEST_METHODS = ["cashapp", "venmo", "paypal", "onlyfans", "loyalfans", "youpay", "other"]


def add_send_request_review_actions(
    view: discord.ui.LayoutView,
    *,
    bot: "RobBot",
    request_id: int,
    guild_id: int,
    domme_id: int | None,
) -> None:
    del guild_id, domme_id
    add_card_actions(
        view,
        _ApproveSendRequestButton(bot=bot, request_id=request_id),
        _DenySendRequestButton(bot=bot, request_id=request_id),
    )


class _DenySendRequestModal(discord.ui.Modal, title="Reason for denial"):
    def __init__(self, *, button: "_DenySendRequestButton") -> None:
        super().__init__()
        self.button = button
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Tell them why this send was not accepted.",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.button.handle_deny_submit(interaction, str(self.reason.value).strip())


class _ApproveSendRequestButton(discord.ui.Button):
    def __init__(self, *, bot: "RobBot", request_id: int) -> None:
        super().__init__(
            label="Accept",
            style=discord.ButtonStyle.success,
            custom_id=f"sendrequest:accept:{request_id}",
        )
        self.bot = bot
        self.request_id = request_id

    async def callback(self, interaction: discord.Interaction) -> None:
        request = await self.bot.send_requests_repo.get(self.request_id)
        if request is None:
            await interaction.response.edit_message(
                **send_request_resolution_card(
                    title="Request no longer available",
                    body="Rob could not find this send request anymore.",
                ).edit_kwargs()
            )
            return

        if interaction.user.id != request.domme_user_id:
            await interaction.response.send_message(
                **error_permission("Only the target Dom/me can action this request.").send_kwargs(),
                ephemeral=True,
            )
            return

        domme = await self.bot.dommes_repo.get_by_user_id(request.guild_id, request.domme_user_id)
        out = await self.bot.send_request_service.approve(
            request_id=self.request_id,
            guild_id=request.guild_id,
            domme_id=domme.id if domme is not None else None,
            acted_by_user_id=interaction.user.id,
        )
        if not out.ok:
            if out.status in {"approved", "denied", "ignored"}:
                await interaction.response.edit_message(
                    **send_request_resolution_card(
                        title="Request already handled",
                        body=f"This request was already resolved as **{out.status}**.",
                    ).edit_kwargs()
                )
                return
            await interaction.response.send_message(
                **error_card("Rob couldn't approve that request right now.").send_kwargs(),
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            **send_request_resolution_card(
                title="Request accepted",
                body="Rob logged the send and queued it for tracker posting.",
            ).edit_kwargs()
        )

        sub_user = self.bot.get_user(request.sub_user_id)
        if sub_user is None:
            try:
                sub_user = await self.bot.fetch_user(request.sub_user_id)
            except discord.HTTPException:
                sub_user = None
        if sub_user is None:
            log.warning(
                "Could not resolve sub user for send request acceptance request_id=%s sub_user_id=%s",
                self.request_id,
                request.sub_user_id,
            )
            return

        try:
            await sub_user.send(
                **send_request_sub_accepted_dm_card(
                    sub_display_name=sub_user.display_name,
                    domme_display_name=interaction.user.display_name,
                    amount_cents=request.amount_cents,
                    currency=request.currency,
                    service=request.method,
                ).send_kwargs()
            )
        except discord.HTTPException:
            log.warning(
                "Failed to DM sub user for accepted request request_id=%s sub_user_id=%s",
                self.request_id,
                request.sub_user_id,
                exc_info=True,
            )


class _DenySendRequestButton(discord.ui.Button):
    def __init__(self, *, bot: "RobBot", request_id: int) -> None:
        super().__init__(
            label="Deny",
            style=discord.ButtonStyle.danger,
            custom_id=f"sendrequest:deny:{request_id}",
        )
        self.bot = bot
        self.request_id = request_id

    async def callback(self, interaction: discord.Interaction) -> None:
        request = await self.bot.send_requests_repo.get(self.request_id)
        if request is None:
            await interaction.response.edit_message(
                **send_request_resolution_card(
                    title="Request no longer available",
                    body="Rob could not find this send request anymore.",
                ).edit_kwargs()
            )
            return

        if interaction.user.id != request.domme_user_id:
            await interaction.response.send_message(
                **error_permission("Only the target Dom/me can action this request.").send_kwargs(),
                ephemeral=True,
            )
            return

        if request.status != "pending":
            await interaction.response.edit_message(
                **send_request_resolution_card(
                    title="Request already handled",
                    body=f"This request was already resolved as **{request.status}**.",
                ).edit_kwargs()
            )
            return

        await interaction.response.send_modal(_DenySendRequestModal(button=self))

    async def handle_deny_submit(self, interaction: discord.Interaction, reason: str) -> None:
        request = await self.bot.send_requests_repo.get(self.request_id)
        if request is None:
            await interaction.response.send_message(
                **error_card("Rob could not find that request anymore.").send_kwargs(),
                ephemeral=True,
            )
            return
        if interaction.user.id != request.domme_user_id:
            await interaction.response.send_message(
                **error_permission("Only the target Dom/me can action this request.").send_kwargs(),
                ephemeral=True,
            )
            return

        out = await self.bot.send_request_service.deny(
            request_id=self.request_id,
            reason=reason,
            acted_by_user_id=interaction.user.id,
        )
        if not out.ok:
            await interaction.response.send_message(
                **error_card("Rob couldn't deny that request right now.").send_kwargs(),
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            **send_request_resolution_card(
                title="Request denied",
                body="Rob saved the denial reason and notified the Sub.",
            ).edit_kwargs()
        )

        sub_user = self.bot.get_user(request.sub_user_id)
        if sub_user is None:
            try:
                sub_user = await self.bot.fetch_user(request.sub_user_id)
            except discord.HTTPException:
                sub_user = None
        if sub_user is None:
            log.warning(
                "Could not resolve sub user for denied request request_id=%s sub_user_id=%s",
                self.request_id,
                request.sub_user_id,
            )
            return

        try:
            await sub_user.send(
                **send_request_sub_denied_dm_card(
                    sub_display_name=sub_user.display_name,
                    domme_display_name=interaction.user.display_name,
                    amount_cents=request.amount_cents,
                    currency=request.currency,
                    service=request.method,
                    reason=reason,
                ).send_kwargs()
            )
        except discord.HTTPException:
            log.warning(
                "Failed to DM sub user for denied request request_id=%s sub_user_id=%s",
                self.request_id,
                request.sub_user_id,
                exc_info=True,
            )


class SendsCog(commands.Cog):
    def __init__(self, bot: RobBot) -> None:
        self.bot = bot

    @app_commands.command(name="add", description="Log a manual send for the leaderboard.")
    @app_commands.describe(
        amount="Amount sent in USD.",
        method="Where the send happened.",
        sub="Optional sending name to attribute.",
        note="Optional item or note for the send.",
    )
    @app_commands.choices(
        method=[app_commands.Choice(name=value, value=value) for value in _MANUAL_METHODS]
    )
    async def add_send(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[float, 0.01],
        method: app_commands.Choice[str],
        sub: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                **error_card("This command can only be used in a server.").send_kwargs(),
                ephemeral=True,
            )
            return

        domme = await self.bot.dommes_repo.get_by_user_id(
            interaction.guild.id,
            interaction.user.id,
        )
        if domme is None:
            await interaction.response.send_message(
                **error_card("Only registered Dom/mes can use `/add`.").send_kwargs(),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        send = await self.bot.send_service.record_manual_send(
            guild_id=interaction.guild.id,
            domme_id=domme.id,
            domme_user_id=interaction.user.id,
            sub_name=(sub or "").strip() or None,
            amount_cents=dollars_to_cents(float(amount)),
            currency="USD",
            method=method.value,
            note=(note or "").strip() or None,
        )
        if send is None:
            await interaction.followup.send(
                **error_card("That send could not be recorded.").send_kwargs(),
                ephemeral=True,
            )
            return

        queue_label = (
            "queued for after maintenance"
            if send.discord_post_status == "queued_maintenance"
            else "queued for posting"
        )
        await interaction.followup.send(
            **registration_card(
                title="Rob | Send Logged",
                summary=f"Recorded {format_money_from_cents(send.amount_cents)} and {queue_label}.",
                details=[
                    ("Method", method.value),
                    ("Sender", send.sub_name or "Unclaimed"),
                ],
            ).send_kwargs(),
            ephemeral=True,
        )

    @app_commands.command(name="sendrequest", description="Ask a Dom/me to log a send you made.")
    @app_commands.describe(
        domme="The Dom/me you sent to.",
        amount="Amount sent in USD.",
        service="Where the send happened.",
        note="Optional proof link or note.",
    )
    @app_commands.choices(
        service=[app_commands.Choice(name=value, value=value) for value in _REQUEST_METHODS]
    )
    async def send_request(
        self,
        interaction: discord.Interaction,
        domme: discord.Member,
        amount: app_commands.Range[float, 0.01],
        service: app_commands.Choice[str],
        note: Optional[str] = None,
    ) -> None:
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message(
                **error_card("This command can only be used in a server.").send_kwargs(),
                ephemeral=True,
            )
            return

        settings = await self.bot.guild_settings_repo.get(interaction.guild.id)
        sub_role_id = settings.sub_role_id if settings is not None else None
        if sub_role_id is None:
            await interaction.response.send_message(
                **error_permission(PERMISSION_ROLE_NOT_CONFIGURED).send_kwargs(),
                ephemeral=True,
            )
            return
        if not member_has_role(interaction.user, sub_role_id):
            await interaction.response.send_message(
                **error_permission(PERMISSION_ROLE_MISSING).send_kwargs(),
                ephemeral=True,
            )
            return

        domme_record = await self.bot.dommes_repo.get_by_user_id(interaction.guild.id, domme.id)
        if domme_record is None:
            await interaction.response.send_message(
                **error_card("That user is not a registered Dom/me.").send_kwargs(),
                ephemeral=True,
            )
            return

        if await self.bot.send_request_service.is_rate_limited(
            guild_id=interaction.guild.id,
            sub_user_id=interaction.user.id,
            domme_user_id=domme.id,
        ):
            await interaction.response.send_message(
                **error_card(
                    "Rate limit reached.",
                    "You can only request 3 send reviews from the same Dom/me in 24 hours.",
                ).send_kwargs(),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        request_record = await self.bot.send_requests_repo.create(
            guild_id=interaction.guild.id,
            sub_user_id=interaction.user.id,
            domme_user_id=domme.id,
            amount_cents=dollars_to_cents(float(amount)),
            currency="USD",
            method=service.value,
            note=(note or "").strip() or None,
        )

        try:
            accept_button = _ApproveSendRequestButton(bot=self.bot, request_id=request_record.id)
            deny_button = _DenySendRequestButton(bot=self.bot, request_id=request_record.id)
            domme_msg = send_request_domme_review_card(
                sub_mention=interaction.user.mention,
                domme_display_name=domme.display_name,
                amount_cents=request_record.amount_cents,
                currency=request_record.currency,
                service=request_record.method,
                note=request_record.note,
                accept_button=accept_button,
                deny_button=deny_button,
            )
            await domme.send(**domme_msg.send_kwargs())
        except discord.HTTPException:
            await self.bot.send_requests_repo.delete(request_record.id)
            await interaction.followup.send(
                **error_card("Rob couldn't DM that Dom/me right now.").send_kwargs(),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            **send_request_sent_card(domme_mention=domme.mention).send_kwargs(),
            ephemeral=True,
        )
