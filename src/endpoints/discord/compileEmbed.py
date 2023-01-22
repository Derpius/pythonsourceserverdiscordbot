import discord

from ...interface import Embed

def compileEmbed(embed: Embed | None) -> discord.Embed | None:
	if not embed: return None

	compiled = discord.Embed(
		title=embed.title,
		description=embed.description,
		colour=discord.Colour(int(embed.colour)),
		url=embed.url
	)

	if embed.footer:
		compiled.set_footer(text=embed.footer)
	if embed.icon:
		compiled.set_thumbnail(url=embed.icon)

	if embed.fields:
		for field in embed.fields:
			compiled.add_field(name=field.name, value=field.value, inline=field.inline)

	return compiled
