from typing import TYPE_CHECKING

from interactions.api.http.http_requests.channels import ChannelRequests
from interactions.api.http.route import PAYLOAD_TYPE, Route
from interactions.client.utils.serializer import dict_filter_none

if TYPE_CHECKING:
    from interactions.models.discord.snowflake import Snowflake_Type


async def move_channel(
    self,
    guild_id: "Snowflake_Type",
    channel_id: "Snowflake_Type",
    new_pos: int,
    parent_id: "Snowflake_Type | None" = None,
    lock_perms: bool = False,
    reason: str | None = None,
) -> None:
    """
    Move a channel.

    Args:
        guild_id: The ID of the guild this affects
        channel_id: The ID of the channel to move
        new_pos: The new position of this channel
        parent_id: The parent ID if needed
        lock_perms: Sync permissions with the new parent
        reason: An optional reason for the audit log

    """
    payload: PAYLOAD_TYPE = {
        "id": int(channel_id),
        "position": new_pos,
        "parent_id": int(parent_id) if parent_id else None,
        "lock_permissions": lock_perms,
    }
    payload = dict_filter_none(payload)

    await self.request(
        Route("PATCH", "/guilds/{guild_id}/channels", guild_id=guild_id),
        payload=[payload],
        reason=reason,
    )


ChannelRequests.move_channel = move_channel
