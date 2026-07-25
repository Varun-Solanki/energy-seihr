from rag.retriever import Retriever, _strip_html


def test_strip_html_omits_style_blocks() -> None:
    text = _strip_html("<html><head><style>body { color: red; }</style></head><body><p>PM2.5 health evidence</p></body></html>")

    assert "color" not in text
    assert "PM2.5 health evidence" in text


def test_local_document_search_returns_hosted_paper_context() -> None:
    retriever = Retriever()

    docs = retriever._search_local_documents("PM2.5 respiratory health fossil fuel")

    assert docs
    assert all("snippet" in item for item in docs)
    assert any("PM2.5" in item["snippet"] or "pm2.5" in item["snippet"].lower() for item in docs)
