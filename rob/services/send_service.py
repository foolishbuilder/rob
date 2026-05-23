from __future__ import annotations

from rob.database.repositories.models import NewSend, SendRecord, ThroneCreator
from rob.database.repositories.sends import SendsRepository
from rob.database.repositories.subs import SubsRepository
from rob.services.maintenance_service import MaintenanceService
from rob.services.throne_service import ThroneService
from rob.throne.payloads import ThroneSendPayload, is_known_test_sender
from rob.utils.time import utc_now


class SendService:
    def __init__(
        self,
        *,
        sends: SendsRepository,
        subs: SubsRepository,
        maintenance: MaintenanceService,
        throne: ThroneService | None = None,
        throne_test_gifter_usernames: tuple[str, ...] = (),
    ) -> None:
        self.sends = sends
        self.subs = subs
        self.maintenance = maintenance
        self.throne = throne
        self.throne_test_gifter_usernames = throne_test_gifter_usernames

    async def record_throne_send(
        self,
        *,
        creator: ThroneCreator,
        payload: ThroneSendPayload,
    ) -> SendRecord | None:
        amount_cents = payload.amount_cents
        currency = payload.currency or "USD"
        is_private = payload.is_private
        is_test_send = is_known_test_sender(
            payload.gifter_username,
            test_gifter_usernames=set(self.throne_test_gifter_usernames),
        )

        if False and (
            amount_cents == 0
            and payload.event_type == "gift_purchased"
            and self.throne is not None
        ):
            match = await self.throne.match_item(
                creator_id=creator.throne_creator_id,
                item_name=payload.item_name,
                item_image_url=payload.item_image_url,
            )
            if match is not None and match.amount_cents > 0:
                amount_cents = match.amount_cents
                if match.currency:
                    currency = match.currency
                is_private = False

        status = "queued_maintenance" if await self.maintenance.is_enabled() else "pending"

        sub_id = None
        sub_user_id = None
        if payload.gifter_username and payload.gifter_username.lower() != "anonymous":
            sub = await self.subs.get_by_name(creator.guild_id, payload.gifter_username)
            if sub is not None:
                sub_id = sub.id
                sub_user_id = sub.discord_user_id

        return await self.sends.insert(
            NewSend(
                guild_id=creator.guild_id,
                domme_id=creator.domme_id,
                domme_user_id=creator.discord_user_id,
                sub_id=sub_id,
                sub_user_id=sub_user_id,
                sub_name=payload.gifter_username,
                amount_cents=amount_cents,
                currency=currency,
                method="throne",
                source="throne_webhook",
                item_name=payload.item_name,
                item_image_url=payload.item_image_url,
                external_id=None,
                event_id=payload.event_id,
                fallback_event_hash=payload.fallback_event_hash,
                is_private=is_private,
                seeded=False,
                sent_at=payload.purchased_at,
                discord_post_status=status,
                is_test_send=is_test_send,
            )
        )

    async def record_manual_send(
        self,
        *,
        guild_id: int,
        domme_id: int | None,
        domme_user_id: int,
        sub_name: str | None,
        amount_cents: int,
        currency: str,
        method: str,
        note: str | None,
        source: str | None = None,
    ) -> SendRecord | None:
        status = "queued_maintenance" if await self.maintenance.is_enabled() else "pending"
        sub_id = None
        sub_user_id = None
        if sub_name:
            sub = await self.subs.get_by_name(guild_id, sub_name)
            if sub is not None:
                sub_id = sub.id
                sub_user_id = sub.discord_user_id
        return await self.sends.insert(
            NewSend(
                guild_id=guild_id,
                domme_id=domme_id,
                domme_user_id=domme_user_id,
                sub_id=sub_id,
                sub_user_id=sub_user_id,
                sub_name=sub_name,
                amount_cents=amount_cents,
                currency=currency,
                method=method,
                source=source or f"manual:{method}",
                item_name=note or f"Manual send via {method}",
                item_image_url=None,
                external_id=None,
                event_id=None,
                fallback_event_hash=None,
                is_private=False,
                seeded=False,
                sent_at=utc_now(),
                discord_post_status=status,
                is_test_send=False,
            )
        )
