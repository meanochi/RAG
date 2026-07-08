"""Stage 2 — the event-driven RAG workflow (LlamaIndex Workflows).

Each step has a clear input/output event and decides what happens next by the
event it emits:

    StartEvent
      └─ validate_query ──(invalid)──────────────► StopEvent(error)
           └─ QueryReadyEvent
                └─ route (LLMSingleSelector)
                     ├─ SemanticSearchEvent ─► retrieve ──(empty / low confidence,
                     │                            │         first time)─► SemanticSearchEvent (broadened retry)
                     │                            └─ NodesReadyEvent ─► synthesize_semantic ─► StopEvent
                     └─ StructuredSearchEvent ─► structured_search
                                                   ├─(no results)─► SemanticSearchEvent (fallback)
                                                   └─ StructuredResultsEvent ─► synthesize_structured ─► StopEvent

State (retry counter, original query, chosen route) lives in the workflow
Context store; events carry only the data the next step needs.
"""
from __future__ import annotations

import json

from llama_index.core import VectorStoreIndex, get_response_synthesizer
from llama_index.core.llms import LLM
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.prompts import PromptTemplate
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.core.schema import NodeWithScore
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)

from . import config
from .llm_utils import predict_structured
from .schema import StructuredQuerySpec
from .structured_store import StructuredStore

# ---------------------------------------------------------------- events


class QueryReadyEvent(Event):
    query: str


class SemanticSearchEvent(Event):
    query: str
    top_k: int
    cutoff: float


class StructuredSearchEvent(Event):
    query: str


class NodesReadyEvent(Event):
    query: str
    nodes: list[NodeWithScore]
    low_confidence: bool


class StructuredResultsEvent(Event):
    query: str
    results: list[dict]
    spec: StructuredQuerySpec


# ---------------------------------------------------------------- prompts

HEBREW_QA_PROMPT = PromptTemplate(
    "להלן קטעים מתוך קבצי התיעוד (md) שכלי Agentic Coding שונים מנהלים בפרויקט.\n"
    "המטא-דאטה של כל קטע מציין מאיזה כלי (tool) ומאיזה קובץ (file) הוא הגיע.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "ענה על השאלה בעברית, אך ורק על סמך הקטעים שלמעלה. אם המידע לא מופיע בהם — "
    "אמור זאת במפורש. ציין בתשובה מאיזה כלי/קובץ מגיע המידע כשזה מוסיף ערך.\n"
    "שאלה: {query_str}\n"
    "תשובה: "
)

REWRITE_PROMPT = PromptTemplate(
    "השאלה הבאה לא מצאה תוצאות טובות בחיפוש סמנטי על תיעוד טכני של פרויקט תוכנה.\n"
    "נסח אותה מחדש כשאילתת חיפוש רחבה יותר: מילות מפתח מרכזיות, מונחים נרדפים, "
    "ובנוסף תרגום המונחים הטכניים לאנגלית (התיעוד מעורב עברית ואנגלית).\n"
    "החזר שורת חיפוש אחת בלבד, ללא הסברים.\n"
    "שאלה: {query}\n"
)

SPEC_PROMPT = PromptTemplate(
    "You translate a user question into a query over a structured knowledge base\n"
    "extracted from a software project's documentation.\n\n"
    "Item types available: decisions (technical decisions), rules (conventions/"
    "instructions), warnings (fragile 'do not touch' areas), changes (schema/API/"
    "config changes). Every item has observed_at (YYYY-MM-DD), tags, and text fields\n"
    "in Hebrew and English.\n\n"
    "Today's date: {today}\n"
    "Knowledge base contents: {stats}\n\n"
    "Rules:\n"
    "- 'Everything/all/list' questions: set item_types, leave keywords empty for full coverage.\n"
    "- Time expressions ('last week', 'this month') become date_from/date_to relative to today.\n"
    "- 'Current/latest/עדכני' questions: latest_only=true.\n"
    "- Provide keywords in BOTH Hebrew and English when the topic is specific.\n\n"
    "Question: {question}\n"
)

STRUCTURED_ANSWER_PROMPT = PromptTemplate(
    "שאלת המשתמש: {question}\n\n"
    "אלו הפריטים שנשלפו ממאגר ידע מובנה שחולץ מקבצי התיעוד של כלי ה-Agentic Coding "
    "בפרויקט (ממוינים מהחדש לישן; לכל פריט יש מקור — כלי וקובץ):\n"
    "{results}\n\n"
    "נסח תשובה מלאה בעברית על סמך הפריטים בלבד. אם השאלה מבקשת רשימה — הצג רשימה "
    "מסודרת עם תאריכים ומקורות. אם השאלה על 'המצב העדכני' — התבסס על הפריט החדש "
    "ביותר וציין את תאריכו. אל תמציא פריטים שלא מופיעים.\n"
)

SEMANTIC_ROUTE_DESC = (
    "Semantic search over documentation chunks. Best for open questions about how "
    "something works, why, what the design/setup/architecture is, or any question "
    "about content and explanations."
)
STRUCTURED_ROUTE_DESC = (
    "Query over a structured catalog of decisions, rules, warnings and changes with "
    "dates. Best for: full lists ('all the decisions'), counting, hard time windows "
    "('in the last week/month'), and 'what is the CURRENT/latest rule' questions."
)


# ---------------------------------------------------------------- workflow


class RagWorkflow(Workflow):
    def __init__(
        self,
        index: VectorStoreIndex,
        llm: LLM,
        store: StructuredStore | None = None,
        **kwargs,
    ):
        super().__init__(timeout=kwargs.pop("timeout", 180), **kwargs)
        self.index = index
        self.llm = llm
        self.store = store or StructuredStore()

    # -- step 1: input validation ------------------------------------
    @step
    async def validate_query(
        self, ctx: Context, ev: StartEvent
    ) -> QueryReadyEvent | StopEvent:
        query = (getattr(ev, "query", "") or "").strip()
        if len(query) < 2:
            return StopEvent(
                result=_result("נא להקליד שאלה (לפחות שתי אותיות) 🙂", "validation")
            )
        if len(query) > config.MAX_QUERY_CHARS:
            return StopEvent(
                result=_result(
                    f"השאלה ארוכה מדי ({len(query)} תווים). נסו לקצר אותה.", "validation"
                )
            )
        await ctx.store.set("original_query", query)
        await ctx.store.set("retries", 0)
        return QueryReadyEvent(query=query)

    # -- step 2: routing (semantic vs. structured) ---------------------
    @step
    async def route(
        self, ctx: Context, ev: QueryReadyEvent
    ) -> SemanticSearchEvent | StructuredSearchEvent:
        semantic = SemanticSearchEvent(
            query=ev.query, top_k=config.TOP_K, cutoff=config.SIMILARITY_CUTOFF
        )
        if not self.store.available:
            await ctx.store.set("route", "semantic (structured store not built)")
            return semantic
        try:
            selector = LLMSingleSelector.from_defaults(llm=self.llm)
            result = await selector.aselect(
                [SEMANTIC_ROUTE_DESC, STRUCTURED_ROUTE_DESC], ev.query
            )
            choice = result.selections[0].index
        except Exception:
            choice = 0  # router failure must not kill the question — default to semantic
        if choice == 1:
            await ctx.store.set("route", "structured")
            return StructuredSearchEvent(query=ev.query)
        await ctx.store.set("route", "semantic")
        return semantic

    # -- step 3a: semantic retrieval + confidence validation -----------
    @step
    async def retrieve(
        self, ctx: Context, ev: SemanticSearchEvent
    ) -> NodesReadyEvent | SemanticSearchEvent:
        retriever = self.index.as_retriever(similarity_top_k=ev.top_k)
        nodes = await retriever.aretrieve(ev.query)
        nodes = SimilarityPostprocessor(similarity_cutoff=ev.cutoff).postprocess_nodes(
            nodes
        )
        best = max((n.score or 0.0) for n in nodes) if nodes else 0.0

        retries = await ctx.store.get("retries", default=0)
        if (not nodes or best < config.MIN_CONFIDENCE) and retries < config.MAX_RETRIES:
            await ctx.store.set("retries", retries + 1)
            original = await ctx.store.get("original_query")
            rewritten = await self.llm.acomplete(REWRITE_PROMPT.format(query=original))
            broadened = rewritten.text.strip().splitlines()[0] or original
            return SemanticSearchEvent(
                query=broadened,
                top_k=config.RETRY_TOP_K,
                cutoff=max(ev.cutoff - 0.1, 0.0),
            )

        original = await ctx.store.get("original_query")
        return NodesReadyEvent(
            query=original, nodes=nodes, low_confidence=best < config.MIN_CONFIDENCE
        )

    # -- step 3b: structured query (LLM builds the spec) ---------------
    @step
    async def structured_search(
        self, ctx: Context, ev: StructuredSearchEvent
    ) -> StructuredResultsEvent | SemanticSearchEvent:
        from datetime import date

        try:
            spec = await predict_structured(
                self.llm,
                StructuredQuerySpec,
                SPEC_PROMPT,
                question=ev.query,
                today=date.today().isoformat(),
                stats=self.store.describe(),
            )
            results = self.store.query(spec)
        except Exception:
            spec, results = StructuredQuerySpec(), []

        if not results:
            # validation-driven rerouting: nothing structured matched — try semantic
            await ctx.store.set("route", "structured → fallback to semantic")
            return SemanticSearchEvent(
                query=ev.query, top_k=config.TOP_K, cutoff=config.SIMILARITY_CUTOFF
            )
        return StructuredResultsEvent(query=ev.query, results=results, spec=spec)

    # -- step 4a: synthesis over retrieved chunks ----------------------
    @step
    async def synthesize_semantic(self, ctx: Context, ev: NodesReadyEvent) -> StopEvent:
        route = await ctx.store.get("route", default="semantic")
        if not ev.nodes:
            return StopEvent(
                result=_result(
                    "לא נמצא בתיעוד מידע רלוונטי לשאלה הזו — גם אחרי ניסיון חיפוש מורחב. "
                    "נסו לנסח אחרת או לשאול על נושא אחר.",
                    route,
                )
            )
        synthesizer = get_response_synthesizer(
            llm=self.llm,
            response_mode=ResponseMode.COMPACT,
            text_qa_template=HEBREW_QA_PROMPT,
        )
        response = await synthesizer.asynthesize(ev.query, nodes=ev.nodes)
        answer = str(response)
        if ev.low_confidence:
            answer = (
                "⚠️ *ההתאמה שנמצאה בתיעוד חלשה יחסית — כדאי להתייחס לתשובה בזהירות.*\n\n"
                + answer
            )
        sources = [
            {
                "tool": n.metadata.get("tool", "?"),
                "file": n.metadata.get("file", "?"),
                "score": round(n.score or 0.0, 3),
            }
            for n in ev.nodes
        ]
        return StopEvent(result=_result(answer, route, sources))

    # -- step 4b: synthesis over structured results --------------------
    @step
    async def synthesize_structured(
        self, ctx: Context, ev: StructuredResultsEvent
    ) -> StopEvent:
        results_json = json.dumps(ev.results, ensure_ascii=False, indent=1)
        response = await self.llm.acomplete(
            STRUCTURED_ANSWER_PROMPT.format(question=ev.query, results=results_json)
        )
        sources = [
            {
                "tool": r.get("source", {}).get("tool", "?"),
                "file": r.get("source", {}).get("file", "?"),
                "item": f"{r.get('item_type')}/{r.get('id')}",
            }
            for r in ev.results
        ]
        return StopEvent(
            result=_result(response.text.strip(), "structured", sources, spec=ev.spec)
        )


def _result(answer: str, route: str, sources: list[dict] | None = None, spec=None) -> dict:
    out = {"answer": answer, "route": route, "sources": sources or []}
    if spec is not None:
        out["query_spec"] = spec.model_dump()
    return out


def build_workflow(verbose: bool = False) -> RagWorkflow:
    """Wire the workflow to Pinecone + Cohere (requires env keys)."""
    from . import models

    config.require_env("COHERE_API_KEY", "PINECONE_API_KEY")
    return RagWorkflow(
        index=models.get_query_index(),
        llm=models.get_llm(),
        store=StructuredStore(),
        verbose=verbose,
    )
