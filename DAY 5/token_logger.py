from datetime import datetime

log_file = "token_usage.log"


def log_token_usage(usage):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] "
            f"Prompt: {usage.prompt_token_count} | "
            f"Completion: {usage.candidates_token_count} | "
            f"Total: {usage.total_token_count}\n"
        )
