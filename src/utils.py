from datetime import timedelta

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
