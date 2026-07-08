"""Gradio chat UI over the RAG workflow.

Usage:
    python app.py                     # launch the chat UI (http://127.0.0.1:7860)
    python app.py --ask "שאלה..."     # one-shot answer in the terminal
"""
import argparse
import asyncio

from ragapp.workflow import build_workflow

_workflow = None


def get_workflow():
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow


def format_result(result: dict) -> str:
    lines = [result["answer"]]
    footer = [f"🧭 מסלול: `{result.get('route', '?')}`"]
    seen, source_lines = set(), []
    for src in result.get("sources", []):
        key = (src.get("tool"), src.get("file"))
        if key in seen:
            continue
        seen.add(key)
        extra = f" (score {src['score']})" if "score" in src else ""
        source_lines.append(f"- `{src.get('tool')}` → `{src.get('file')}`{extra}")
    if source_lines:
        footer.append("📄 מקורות:\n" + "\n".join(source_lines))
    lines.append("\n---\n" + "\n\n".join(footer))
    return "\n".join(lines)


async def answer(message: str, history) -> str:
    result = await get_workflow().run(query=message)
    return format_result(result)


EXAMPLES = [
    "מה הצבע העיקרי שנבחר לדיזיין של המערכת?",
    "לאילו שפות הוחלט לתרגם את הכיתובים בממשק?",
    "האם קיימת הנחיה עקבית לגבי שימוש ב-RTL בממשק?",
    "תן לי רשימה של כל ההחלטות הטכניות שהתקבלו בפרויקט",
    "אילו דברים סומנו כרגישים או 'לא לגעת' בשבוע האחרון?",
    "האם נעשה שינוי במבנה ה-DB בחודש האחרון?",
    "איזו מגבלה טכנית חוזרת בכמה מסמכים שונים?",
]


def launch_ui() -> None:
    import gradio as gr

    gr.ChatInterface(
        fn=answer,
        title="🧠 שכבת ידע על תיעוד כלי Agentic Coding",
        description=(
            "שאלו כל דבר על התיעוד ש-Claude Code, Cursor, Kiro ו-Firebase Studio "
            "מנהלים בפרויקט. המערכת מנתבת כל שאלה לחיפוש סמנטי או לשליפה מובנית."
        ),
        examples=EXAMPLES,
    ).launch()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ask", help="ask a single question and print the answer")
    args = parser.parse_args()

    if args.ask:
        # Workflow.run() must be started inside a running event loop
        async def ask_once() -> dict:
            return await get_workflow().run(query=args.ask)

        print(format_result(asyncio.run(ask_once())))
    else:
        launch_ui()


if __name__ == "__main__":
    main()
