def judge(answer: str, known_files: set[str]) -> list[str]:
    return [line for line in answer.splitlines() if "server.py" in line]
