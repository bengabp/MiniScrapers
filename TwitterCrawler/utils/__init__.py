
def parse_humanreadable_string(string: str) -> int:
	""" This function converts human-readable values such as
	 	- 300.4k
	 	- 4.5M
	 	- 8B
	to integers.
	"""
	suffixes = {"K": 1000, "M": 1000000, "B": 1000000000}
	string = string.replace(",", "") # Remove commas
	if string[-1] in suffixes:
		multiplier = suffixes[string[-1]]
		number = float(string[:-1]) * multiplier
		return int(number)
	return int(string)
