def calculateColumnWidths(headerRow: tuple, table: tuple) -> tuple:
	columnWidths = [len(str(header)) + 2 for header in headerRow]
	
	for row in table:
		if len(row) != len(headerRow): raise ValueError("Number of elements in row does not match header")

		for i in range(len(row)):
			if len(str(row[i])) + 2 > columnWidths[i]: columnWidths[i] = len(str(row[i])) + 2
	
	return tuple(columnWidths)

def makeTable(header: tuple, tableRaw: tuple) -> str:
	'''Takes in a tuple of tuples, where each sub tuple is a row, and each element in a row is a column'''
	columnWidths = calculateColumnWidths(header, tableRaw)

	# Top cap
	table = "╔"
	for i in range(len(header)):
		table += "═" * columnWidths[i]
		table += "╗\n" if i == len(header) - 1 else "╤"

	# Headers
	table += "║"
	for i in range(len(header)):
		table += " " + str(header[i]) + (columnWidths[i] - len(str(header[i])) - 1) * " "
		table += "║\n" if i == len(header) - 1 else "|"
	
	# Separator
	table += "╠"
	for j in range(len(header)):
		table += "═" * columnWidths[j]
		table += "╣\n" if j == len(header) - 1 else "╪"
	
	# Rows
	for i in range(len(tableRaw)):
		row = tableRaw[i]
		last = len(tableRaw) - 1

		table += "║"
		for j in range(len(header)):
			table += " " + str(row[j]) + (columnWidths[j] - len(str(row[j])) - 1) * " "
			table += "║\n" if j == len(header) - 1 else "|"
		
		table += "╚" if i == last else "╟"
		for j in range(len(header)):
			table += ("═" if i == last else "─") * columnWidths[j]
			table += ("╝" if i == last else "╢\n") if j == len(header) - 1 else ("╧" if i == last else "┼")
	
	return table