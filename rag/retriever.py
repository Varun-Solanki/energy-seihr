from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from tavily import TavilyClient

from config.settings import settings
from knowledge_graph.querier import KnowledgeGraphQuerier
from rag.vector_store import ChromaEvidenceStore


@dataclass(frozen=True)
class RetrievedContext:
    query: str
    tavily_results: list[dict[str, Any]]
    graph_context: list[dict[str, Any]]
    local_documents: list[dict[str, Any]]
    vector_results: list[dict[str, Any]] | None = None
    timestamp: str = ""
    cache_hit: bool = False


class Retriever:
    """Retrieves energy policy + health context via Tavily API and local knowledge graph."""

    def __init__(
        self,
        graph_path: Path | None = None,
        cache_dir: Path | None = None,
    ):
        self.client = TavilyClient(api_key=settings.tavily_api_key) if settings.tavily_api_key else None
        self.graph_path = graph_path or settings.outputs_dir / "knowledge_graph.gexf"
        self.cache_dir = cache_dir or Path("data/retrieval_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load vector store
        try:
            self.vector_store = ChromaEvidenceStore()
        except Exception as e:
            print(f"Warning: Could not initialize ChromaEvidenceStore: {e}")
            self.vector_store = None

        # Load graph if available
        self.querier = None
        if self.graph_path.exists():
            try:
                self.querier = KnowledgeGraphQuerier(self.graph_path)
            except Exception as e:
                print(f"Warning: Could not load graph: {e}")

    def retrieve(
        self,
        query: str,
        region: str = "",
        use_cache: bool = True,
    ) -> RetrievedContext:
        """
        Retrieve context via Tavily + local knowledge graph.
        
        Args:
            query: Search query (e.g., "Yorkshire coal plant closure health impact")
            region: Optional region for graph filtering
            use_cache: Use cached results if available
            
        Returns:
            RetrievedContext with Tavily results + graph context
        """
        cache_key = self._cache_key(query, region)
        
        if use_cache:
            cached = self._load_cache(cache_key)
            if cached:
                return cached._replace(cache_hit=True) if hasattr(cached, '_replace') else RetrievedContext(
                    query=cached.query,
                    tavily_results=cached.tavily_results,
                    graph_context=cached.graph_context,
                    local_documents=cached.local_documents,
                    vector_results=cached.vector_results,
                    timestamp=cached.timestamp,
                    cache_hit=True,
                )
        
        # Tavily search
        print(f"Searching: {query}")
        tavily_results = self._search_tavily(query)
        local_documents = self._search_local_documents(query)
        
        # Vector search
        vector_results = []
        if getattr(self, 'vector_store', None):
            try:
                v_results = self.vector_store.query(query, n_results=5, hybrid=True)
                vector_results = [
                    {
                        'chunk_id': r.chunk_id,
                        'content': r.content,
                        'score': r.score,
                        'metadata': r.metadata,
                    }
                    for r in v_results
                ]
            except Exception as e:
                print(f'Vector search error: {e}')

        # Graph context
        graph_context = self._search_graph(region) if region and self.querier else []
        
        context = RetrievedContext(
            query=query,
            tavily_results=tavily_results,
            graph_context=graph_context,
            local_documents=local_documents,
            vector_results=vector_results,
            timestamp=datetime.now().isoformat(),
            cache_hit=False,
        )
        
        self._save_cache(cache_key, context)
        return context

    def retrieve_policy_context(
        self,
        region: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> RetrievedContext:
        """Retrieve energy policy context for a region during date range."""
        query = (
            f"{region} energy policy coal gas renewable "
            f"decarbonization {start_date} {end_date}"
        )
        return self.retrieve(query, region=region, use_cache=use_cache)

    def retrieve_health_context(
        self,
        region: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> RetrievedContext:
        """Retrieve health data context for a region during date range."""
        query = (
            f"{region} NHS hospitalization respiratory health "
            f"air quality pollution PM2.5 {start_date} {end_date}"
        )
        return self.retrieve(query, region=region, use_cache=use_cache)

    def format_for_llm(self, context: RetrievedContext) -> str:
        """Format retrieved context as structured text for LLM consumption."""
        lines = [
            f"Query: {context.query}",
            f"Retrieved: {context.timestamp}",
            "",
            "=== TAVILY SEARCH RESULTS ===",
        ]
        
        for i, result in enumerate(context.tavily_results[:5], 1):
            lines.append(f"\n{i}. {result.get('title', 'N/A')}")
            lines.append(f"   URL: {result.get('url', '')}")
            content = result.get("content", "")
            lines.append(f"   {content[:300]}...")

        if context.local_documents:
            lines.append("\n=== LOCAL HOSTED PAPER CONTEXT ===")
            for i, item in enumerate(context.local_documents[:5], 1):
                lines.append(f"\n{i}. {item.get('title', item.get('path', 'local document'))}")
                lines.append(f"   Path: {item.get('path', '')}")
                lines.append(f"   {item.get('snippet', '')[:700]}...")

        if context.vector_results:
            lines.append('\n=== VECTOR DB SEMANTIC SEARCH RESULTS ===')
            for i, result in enumerate(context.vector_results[:5], 1):
                chunk_id = result.get('chunk_id', 'Unknown')
                score = result.get('score') or 0.0
                lines.append(f'\n{i}. [Chunk {chunk_id}] (Score: {score:.2f})')
                meta = result.get('metadata', {})
                source = meta.get('source_name', 'Unknown')
                lines.append(f'   Source: {source}')
                content_str = result.get('content', '')
                lines.append(f'   {content_str[:500]}...')
        
        if context.graph_context:
            lines.append("\n=== LOCAL KNOWLEDGE GRAPH CONTEXT ===")
            for item in context.graph_context[:3]:
                lines.append(f"- {item}")
        
        return "\n".join(lines)

    def _search_tavily(self, query: str) -> list[dict[str, Any]]:
        """Search Tavily API."""
        if not self.client:
            print("Tavily API key not configured; using local document context only")
            return []
        try:
            kwargs: dict[str, Any] = {
                "max_results": 5,
                "include_answer": True,
            }
            if settings.tavily_allowed_domains:
                kwargs["include_domains"] = settings.tavily_allowed_domains
            results = self.client.search(
                query,
                search_depth="advanced",
                **kwargs,
            )
            return results.get("results", [])
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []

    def _search_local_documents(self, query: str) -> list[dict[str, Any]]:
        """Rank local hosted HTML summaries with a simple keyword score."""
        directory = settings.hosted_data_dir
        if not directory.exists():
            return []

        terms = {
            term.lower()
            for term in query.replace("_", " ").replace("-", " ").split()
            if len(term) > 3
        }
        scored: list[tuple[int, dict[str, Any]]] = []
        for path in directory.rglob("*.html"):
            text = _strip_html(path.read_text(encoding="utf-8", errors="ignore"))
            lower_text = text.lower()
            score = sum(lower_text.count(term) for term in terms)
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "title": self._title_from_html(path),
                        "path": str(path),
                        "score": score,
                        "snippet": self._best_snippet(text, terms),
                    },
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored[:5]]

    def _best_snippet(self, text: str, terms: set[str], window: int = 900) -> str:
        if not text:
            return ""
        lower_text = text.lower()
        first_match = min((lower_text.find(term) for term in terms if term in lower_text), default=0)
        start = max(0, first_match - window // 3)
        end = min(len(text), start + window)
        return " ".join(text[start:end].split())

    def _title_from_html(self, path: Path) -> str:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower_text = text.lower()
        start = lower_text.find("<title>")
        end = lower_text.find("</title>")
        if start >= 0 and end > start:
            return _strip_html(text[start + 7:end]).strip()
        return path.stem.replace("-", " ").title()

    def _search_graph(self, region: str) -> list[str]:
        """Search local knowledge graph for region context."""
        if not self.querier or not region:
            return []
        
        try:
            records = self.querier.records_for_region(region)
            return [
                f"{r.get('label', 'Unknown')}: {r.get('value', 'N/A')} {r.get('unit', '')}"
                for r in records[:5]
            ]
        except Exception as e:
            print(f"Graph search error: {e}")
            return []

    def _cache_key(self, query: str, region: str) -> str:
        """Generate cache file key."""
        region_suffix = f"_{region}" if region else ""
        digest = hashlib.sha256(f"{query}|{region}".encode("utf-8")).hexdigest()[:12]
        sanitized_query = "".join(char if char.isalnum() else "_" for char in query[:40]).strip("_")
        return f"retrieval_{sanitized_query}{region_suffix}_{digest}.json"

    def _load_cache(self, key: str) -> RetrievedContext | None:
        """Load from cache if exists."""
        cache_file = self.cache_dir / key
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    data.setdefault("local_documents", [])
                    data.setdefault("vector_results", [])
                    if not data["local_documents"]:
                        data["local_documents"] = self._search_local_documents(data.get("query", ""))
                    return RetrievedContext(**data)
            except Exception as e:
                print(f"Cache load error: {e}")
        return None

    def _save_cache(self, key: str, context: RetrievedContext) -> None:
        """Save to cache."""
        try:
            cache_file = self.cache_dir / key
            with open(cache_file, "w") as f:
                json.dump(
                    {
                        "query": context.query,
                        "tavily_results": context.tavily_results,
                        "graph_context": context.graph_context,
                        "local_documents": context.local_documents,
                        "vector_results": context.vector_results,
                        "timestamp": context.timestamp,
                        "cache_hit": False,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            print(f"Cache save error: {e}")


class _TextOnlyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        clean = data.strip()
        if clean:
            self.parts.append(clean)


def _strip_html(html: str) -> str:
    parser = _TextOnlyParser()
    parser.feed(html)
    return " ".join(parser.parts)
