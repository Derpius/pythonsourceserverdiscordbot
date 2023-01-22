import discord
from discord.ext import commands

class WebhookService:
	def __init__(self, user: discord.ClientUser) -> None:
		self.user = user

	async def connect(self, channel: discord.TextChannel) -> discord.Webhook:
		'''Gets a webhook for a channel, creating one if needed. Returns None if forbidden'''

		for webhook in await channel.webhooks():
			if webhook.user.id != self.user.id:
				continue

			return webhook

		return await channel.create_webhook(
			name="SourceBot Masquerades",
			reason="Create webhook for partial masquerade support"
		)
