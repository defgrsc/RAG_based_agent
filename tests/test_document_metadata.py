from unittest.mock import Mock, patch

import pytest

from document_metadata import (
    METADATA_SCHEMA_VERSION,
    annotate_document,
    annotate_documents,
    summarize_document_metadata,
    validate_document_metadata,
)


def test_structured_coverage_metadata_is_preserved_and_completed():
    document = annotate_document({
        "title": "清大校園無線網路服務範圍",
        "url": "https://net.nthu.edu.tw/netsys/wireless:uniform",
        "chunk_index": 1,
        "content": "服務：校園無線網路\n資訊類型：服務範圍",
        "service": "campus_wifi",
        "intent": "coverage",
        "source_type": "official_coverage",
    })

    assert document["service"] == "campus_wifi"
    assert document["services"] == ["campus_wifi"]
    assert document["task"] == "coverage"
    assert document["tasks"] == ["coverage"]
    assert document["intent"] == "coverage"
    assert document["language"] == "zh-Hant"
    assert document["document_type"] == "coverage_record"
    assert document["metadata_schema_version"] == METADATA_SCHEMA_VERSION


def test_url_service_namespace_wins_over_cross_service_content_mentions():
    document = annotate_document({
        "title": "SSL VPN setup",
        "url": "https://net.nthu.edu.tw/netsys/sslvpn:info",
        "chunk_index": 1,
        "content": "先申請校園無線帳號，再安裝 Ivanti 並設定 VPN server。",
    })

    assert document["service"] == "vpn"
    assert document["services"] == ["vpn"]
    assert "campus_wifi" not in document["services"]
    assert "application" in document["tasks"]
    assert "configuration" in document["tasks"]


def test_generic_english_faq_chunk_can_be_multi_service():
    document = annotate_document({
        "title": "en:faq [Network Systems Division]",
        "url": "https://net.nthu.edu.tw/netsys/en:faq",
        "chunk_index": 2,
        "content": "DormNet registration and campus Wi-Fi authentication help.",
    })

    assert document["service"] == "multi_service"
    assert document["services"] == ["campus_wifi", "dorm_network"]
    assert document["language"] == "en"
    assert document["source_type"] == "official_faq"
    assert document["document_type"] == "faq_chunk"


def test_gapp_url_has_email_application_metadata():
    document = annotate_document({
        "title": "en:gapp",
        "url": "https://net.nthu.edu.tw/netsys/en:gapp",
        "chunk_index": 1,
        "content": "Google Workspace account application procedure.",
    })

    assert document["services"] == ["email"]
    assert document["tasks"] == ["application"]
    assert document["language"] == "en"


def test_unclassified_official_page_uses_explicit_general_labels():
    document = annotate_document({
        "title": "about:contact",
        "url": "https://net.nthu.edu.tw/netsys/about:contact",
        "chunk_index": 1,
        "content": "網路系統組聯絡方式。",
    })

    assert document["service"] == "general_network"
    assert document["services"] == ["general_network"]
    assert document["task"] == "general"
    assert document["tasks"] == ["general"]


def test_validation_rejects_untagged_documents_before_embedding():
    with pytest.raises(ValueError, match="missing service"):
        validate_document_metadata([{"content": "legacy chunk"}])


def test_summary_counts_multi_value_metadata():
    documents = annotate_documents([
        {
            "title": "wireless",
            "url": "https://net.nthu.edu.tw/netsys/wireless/",
            "content": "校園無線網路",
        },
        {
            "title": "dormnet",
            "url": "https://net.nthu.edu.tw/netsys/dormnet/",
            "content": "宿網申請流程",
        },
    ])
    validate_document_metadata(documents)

    summary = summarize_document_metadata(documents)

    assert summary["schema_version"] == METADATA_SCHEMA_VERSION
    assert summary["documents"] == 2
    assert summary["services"] == {"campus_wifi": 1, "dorm_network": 1}
    assert summary["languages"] == {"zh-Hant": 2}


def test_ingestion_validates_and_upserts_only_enriched_documents():
    page = {
        "title": "en:gapp",
        "url": "https://net.nthu.edu.tw/netsys/en:gapp",
        "text": "Google Workspace account application procedure.",
    }
    vectors = [[0.1, 0.2]]
    with (
        patch("ingest.crawl_pages", return_value=[page]),
        patch("ingest.build_coverage_documents", return_value=[]),
        patch("ingest.embed_texts", return_value=vectors) as embed,
        patch("ingest.upsert_documents", return_value="staging-v2") as upsert,
    ):
        from ingest import ingest_nthu_docs

        result = ingest_nthu_docs(replace=True)

    embedded_document = upsert.call_args.args[0][0]
    assert embedded_document["services"] == ["email"]
    assert embedded_document["tasks"] == ["application"]
    assert embedded_document["metadata_schema_version"] == METADATA_SCHEMA_VERSION
    embed.assert_called_once_with([embedded_document["content"]])
    upsert.assert_called_once_with([embedded_document], vectors, replace=True)
    assert result["active_collection"] == "staging-v2"
    assert result["metadata"]["schema_version"] == METADATA_SCHEMA_VERSION


def test_ingestion_metadata_failure_does_not_embed_or_modify_qdrant():
    embed = Mock()
    upsert = Mock()
    with (
        patch("ingest.crawl_pages", return_value=[{"title": "x", "url": "x", "text": "x"}]),
        patch("ingest.build_coverage_documents", return_value=[]),
        patch("ingest.annotate_documents", return_value=[{"content": "legacy"}]),
        patch("ingest.embed_texts", embed),
        patch("ingest.upsert_documents", upsert),
    ):
        from ingest import ingest_nthu_docs

        with pytest.raises(ValueError, match="metadata validation failed"):
            ingest_nthu_docs(replace=True)

    embed.assert_not_called()
    upsert.assert_not_called()
