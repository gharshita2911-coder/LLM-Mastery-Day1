"""
main.py
=======
Interactive entry point for the RAG + Function Calling system.

Usage
-----
  # Start with the built-in knowledge base only:
  python main.py

  # Pre-load one or more files / folders at startup:
  python main.py --files report.pdf notes.txt --dir ./docs

  # Non-interactive: answer a single question and exit:
  python main.py --query "What is cosine similarity?"

  # Use a different Groq model:
  python main.py --model llama-3.1-8b-instant

Interactive commands (once the REPL is running):
  /upload <path>    — ingest a file into the knowledge base
  /dir    <path>    — ingest all supported files in a directory
  /docs             — list all loaded documents
  /remove <doc_id>  — remove a document and rebuild the index
  /stats            — show index statistics
  /clear            — start a fresh session (wipe all documents)
  /help             — show this help text
  /quit or /exit    — exit
  <anything else>   — ask a question
"""

import os
import sys
import json
import argparse
import textwrap
import time
from pathlib import Path
from datetime import datetime, timezone

# ── seed the knowledge base before importing engine ──────────────────────────
from knowledge_base import seed_engine   # seeds built-in docs into a RAGEngine
from rag_engine import RAGEngine, SUPPORTED_EXT
from llm_client import LLMClient
from tools import set_engine_ref
from dotenv import load_dotenv

load_dotenv()
# ─────────────────────────────────────────────────────────────────────────────
# CLI argument parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RAG + Groq Function Calling — interactive QA system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(__doc__ or ""),
    )
    p.add_argument("--files",  nargs="*", metavar="FILE",  default=[],
                   help="Files to ingest at startup (.txt .md .pdf .docx)")
    p.add_argument("--dir",    metavar="DIR",  default=None,
                   help="Directory to ingest recursively at startup")
    p.add_argument("--query",  metavar="Q",    default=None,
                   help="Single question (non-interactive mode)")
    p.add_argument("--model",  default=os.getenv("RAG_MODEL", "llama-3.3-70b-versatile"),
                   help="Groq model name (default: llama-3.3-70b-versatile)")
    p.add_argument("--top-k",  type=int, default=3,
                   help="Number of chunks to retrieve (default: 3)")
    p.add_argument("--verbose",action="store_true",
                   help="Print retrieval and tool traces to stdout")
    p.add_argument("--no-seed",action="store_true",
                   help="Skip the built-in knowledge base (blank slate)")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Pretty printing helpers
# ─────────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"


def _c(text: str, colour: str) -> str:
    """Apply ANSI colour if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"{colour}{text}{RESET}"
    return text


def _banner():
    print(_c("""
╔══════════════════════════════════════════════════════════╗
║         RAG + Function Calling  ·  Groq / Llama 3.3      ║
║   Type /help for commands  ·  Type your question to ask  ║
╚══════════════════════════════════════════════════════════╝
""", CYAN))


def _print_answer(trace: dict) -> None:
    """Print a formatted answer with retrieval and tool info."""
    if trace.get("error"):
        print(_c(f"\n[ERROR] {trace['error']}", RED))
        return

    # Retrieved chunks summary
    chunks = trace.get("retrieved_chunks", [])
    if chunks:
        print(_c("\n  Sources retrieved:", DIM))
        for c in chunks:
            score_bar = "█" * max(1, int(c["score"] * 20))
            print(_c(f"    {score_bar:<20}  {c['score']:.3f}  {c['title']}", DIM))

    # Tool calls
    for tc in trace.get("tool_calls", []):
        print(_c(f"\n  🔧  Tool called: {tc['tool']}({tc['args']})", YELLOW))

    # Final answer
    print(_c("\n" + "─" * 62, DIM))
    answer = trace.get("final_answer", "(no answer)")
    # Word-wrap for readability
    for line in answer.splitlines():
        if line.strip():
            print(textwrap.fill(line, width=80, initial_indent="  ", subsequent_indent="  "))
        else:
            print()
    print(_c("─" * 62, DIM))
    calls = trace.get("llm_calls", 1)
    print(_c(f"  ({calls} LLM call{'s' if calls != 1 else ''}, "
             f"{len(trace.get('tool_calls',[]))} tool call{'s' if len(trace.get('tool_calls',[])) != 1 else ''})", DIM))


def _print_docs(engine: RAGEngine) -> None:
    docs = engine.list_documents()
    if not docs:
        print("  (no documents loaded)")
        return
    print(f"\n  {'ID':<22}  {'Chars':>6}  Title")
    print("  " + "─" * 60)
    for d in docs:
        src = Path(d['source']).name if d['source'] not in ("manual","builtin") else d['source']
        print(f"  {d['id']:<22}  {d['chars']:>6}  {d['title'][:40]}  [{src}]")
    stats = engine.stats()
    print(f"\n  {stats['documents']} doc(s)  ·  {stats['chunks']} chunks  ·  vocab {stats['vocab_size']:,}")


def _print_help() -> None:
    print(_c("""
  Commands:
    /upload <path>      Ingest a file  (.txt  .md  .pdf  .docx)
    /dir    <path>      Ingest all supported files in a directory
    /docs               List loaded documents
    /remove <doc_id>    Remove a document and rebuild the index
    /stats              Index statistics
    /clear              Wipe all documents and start fresh
    /help               Show this help
    /quit | /exit       Exit

  Just type a question to get an answer.
""", DIM))


# ─────────────────────────────────────────────────────────────────────────────
# Engine + client setup
# ─────────────────────────────────────────────────────────────────────────────

def _setup(args: argparse.Namespace) -> tuple[RAGEngine, LLMClient]:
    """Initialise the RAGEngine and LLMClient from CLI args."""

    engine = RAGEngine(top_k=args.top_k)

    # Seed with built-in knowledge base unless --no-seed
    if not args.no_seed:
        seed_engine(engine)
        print(_c(f"  ✔  Built-in knowledge base loaded ({len(engine._raw_docs)} docs)", GREEN))

    # Ingest extra files from --files
    for path in (args.files or []):
        try:
            doc_id = engine.ingest_file(path)
            print(_c(f"  ✔  Ingested: {path}  →  {doc_id}", GREEN))
        except Exception as e:
            print(_c(f"  ✗  {path}: {e}", RED))

    # Ingest directory from --dir
    if args.dir:
        try:
            ids = engine.ingest_directory(args.dir)
            print(_c(f"  ✔  Ingested {len(ids)} file(s) from {args.dir}", GREEN))
        except Exception as e:
            print(_c(f"  ✗  {args.dir}: {e}", RED))

    # Build index
    engine.build()

    # Give tools access to the live engine (for summarise_document)
    set_engine_ref(engine)

    # Init LLM client
    client = LLMClient(model=args.model, top_k=args.top_k)
    return engine, client


def _rebuild(engine: RAGEngine) -> None:
    """Rebuild index and refresh tool engine reference."""
    engine.build()
    set_engine_ref(engine)


# ─────────────────────────────────────────────────────────────────────────────
# REPL
# ─────────────────────────────────────────────────────────────────────────────

def _repl(engine: RAGEngine, client: LLMClient, verbose: bool) -> None:
    _banner()
    _print_docs(engine)
    print()

    while True:
        try:
            raw = input(_c("You › ", BOLD + CYAN)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        # ── Commands ──────────────────────────────────────────────────────
        if raw.lower() in ("/quit", "/exit"):
            print("Goodbye!")
            break

        if raw.lower() == "/help":
            _print_help()
            continue

        if raw.lower() == "/docs":
            _print_docs(engine)
            continue

        if raw.lower() == "/stats":
            s = engine.stats()
            print(json.dumps(s, indent=2))
            continue

        if raw.lower() == "/clear":
            engine = RAGEngine(top_k=client.top_k)
            print(_c("  Knowledge base cleared. Load files with /upload.", YELLOW))
            continue

        if raw.lower().startswith("/upload "):
            path = raw[8:].strip().strip('"').strip("'")
            try:
                doc_id = engine.ingest_file(path)
                _rebuild(engine)
                print(_c(f"  ✔  Ingested and indexed: {path}  →  {doc_id}", GREEN))
            except Exception as e:
                print(_c(f"  ✗  {e}", RED))
            continue

        if raw.lower().startswith("/dir "):
            directory = raw[5:].strip().strip('"').strip("'")
            try:
                ids = engine.ingest_directory(directory)
                _rebuild(engine)
                print(_c(f"  ✔  Ingested {len(ids)} file(s) and rebuilt index", GREEN))
            except Exception as e:
                print(_c(f"  ✗  {e}", RED))
            continue

        if raw.lower().startswith("/remove "):
            doc_id = raw[8:].strip()
            removed = engine.remove_document(doc_id)
            if removed:
                if engine._raw_docs:
                    _rebuild(engine)
                    print(_c(f"  ✔  Removed '{doc_id}' and rebuilt index", GREEN))
                else:
                    print(_c(f"  ✔  Removed '{doc_id}'. No documents left — load files with /upload", YELLOW))
            else:
                print(_c(f"  ✗  Document '{doc_id}' not found", RED))
            continue

        if raw.startswith("/"):
            print(_c(f"  Unknown command '{raw}'. Type /help.", RED))
            continue

        # ── Question ──────────────────────────────────────────────────────
        if not engine._built:
            print(_c("  Index is not built. Add documents with /upload, then /rebuild.", YELLOW))
            continue

        try:
            t0    = time.time()
            trace = client.run(engine, raw, verbose=verbose)
            ms    = round((time.time() - t0) * 1000)
            _print_answer(trace)
            print(_c(f"  ⏱  {ms} ms", DIM))
        except Exception as e:
            print(_c(f"\n[ERROR] {e}", RED))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    try:
        engine, client = _setup(args)
    except EnvironmentError as e:
        print(_c(f"\n[FATAL] {e}", RED))
        sys.exit(1)
    except Exception as e:
        print(_c(f"\n[FATAL] Setup failed: {e}", RED))
        sys.exit(1)

    # Non-interactive single-query mode
    if args.query:
        trace = client.run(engine, args.query, verbose=args.verbose)
        _print_answer(trace)
        return

    # Interactive REPL
    _repl(engine, client, verbose=args.verbose)


if __name__ == "__main__":
    main()
