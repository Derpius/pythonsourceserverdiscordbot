import discord

_user: discord.ClientUser | None = None
_avatar: bytes | None = None

async def configure(user: discord.ClientUser):
	global _user, _avatar

	_user = user
	_avatar = await user.avatar.read()

async def connect(self, channel: discord.TextChannel) -> discord.Webhook:
	'''Gets a webhook for a channel, creating one if needed. Returns None if forbidden'''

	if _user is None or _avatar is None:
		raise Exception("Webhook service must be configured before use")

	for webhook in await channel.webhooks():
		if webhook.user.id != _user.id:
			continue

		return webhook

	return await channel.create_webhook(
		name="SourceBot Masquerades",
		avatar=_avatar,
		reason="Create webhook for partial masquerade support"
	)
