from datetime import timedelta
from dataclasses import dataclass

@dataclass
class Colour:
	r: int
	g: int
	b: int

	def __str__(self) -> str:
		return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

	def __int__(self) -> int:
		return (self.r << 16) + (self.g << 8) + self.b

def formatTimedelta(delta: timedelta) -> str:
	'''Utility to convert timedelta to formatted string'''
	days, seconds = delta.days, delta.seconds
	hours = seconds // 3600
	minutes = (seconds % 3600) // 60
	seconds = seconds % 60

	datetimeStr = []
	if days != 0: datetimeStr.append(f"{days} day{'s' if days != 1 else ''}")
	if hours != 0: datetimeStr.append(f"{hours} hour{'s' if hours != 1 else ''}")
	if minutes != 0: datetimeStr.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
	if seconds != 0: datetimeStr.append(f"{seconds} second{'s' if seconds != 1 else ''}")
	return " ".join(datetimeStr)
