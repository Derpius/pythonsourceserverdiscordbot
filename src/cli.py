import argparse

parser = argparse.ArgumentParser(
	prog="SourceBot",
	description="Chat bot that interfaces with Source engine servers and relays game chat"
)

parser.add_argument(
	"-c", "--config",
	default="./config.json",
	required=False,
	help="Path to the config file"
)

parser.add_argument(
	"-d", "--data",
	default="./data.json",
	required=False,
	help="Path to the persistent data file"
)

def getCLIArgs():
	return parser.parse_args()
