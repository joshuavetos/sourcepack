import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    return parser.parse_args()
