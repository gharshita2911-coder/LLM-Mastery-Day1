from datetime import datetime

log_file = "token_usage.log"


def log_token_usage(usage):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        prompt     = getattr(usage, "prompt_token_count", 0) or 0
        completion = getattr(usage, "candidates_token_count", 0) or 0
        total      = getattr(usage, "total_token_count", prompt + completion) or 0
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(
                f"[{timestamp}] Prompt: {prompt} | Completion: {completion} | Total: {total}\n"
            )
    except Exception as e:
        print(f"[TOKEN LOG] Failed to log: {e}")