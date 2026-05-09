from datetime import datetime
log_file="token_usage.log"

def log_token_usage (usage):
    with open(log_file,"a",encoding="utf-8") as file:
        file.write(f"""
            Prompt Tokens: {usage.prompt_token_count}
            Completion Tokens: {usage.candidates_token_count}
            Total Tokens: {usage.total_token_count}
            ------------------------------------------------
            """)
