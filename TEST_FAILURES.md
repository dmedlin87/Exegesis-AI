# Test Failures

| Status | Test |
|--------|------|
| FAILED | tests/application/facades/test_telemetry_facade.py::test_facade_delegates_to_provider |
| FAILED | tests/db/test_seeds.py::test_seed_reference_data_repairs_missing_perspective_column |
| FAILED | tests/db/test_seeds.py::test_api_boots_contradiction_seeding_without_migrations |
| FAILED | tests/db/test_seeds.py::test_seed_reference_data_repairs_missing_perspective_in_memory |
| FAILED | tests/api/test_ai_router.py::test_router_shared_spend_across_processes |
| FAILED | tests/api/test_ai_router.py::test_router_shared_latency_across_processes |
| FAILED | tests/api/core/test_runtime.py::test_allow_insecure_startup_requires_non_production_env |
| FAILED | tests/api/ai/test_ai_error_handling.py::test_guarded_answer_or_refusal_returns_refusal_on_safe_error |
| FAILED | tests/api/ai/test_ai_error_handling.py::test_guarded_answer_or_refusal_reraises_non_safe_error |
| FAILED | tests/api/ai/test_ai_error_handling.py::test_guarded_answer_or_refusal_uses_fallback_results |
| FAILED | tests/workers/test_tasks.py::test_process_url_ingests_fixture_url - as... |
| FAILED | tests/workers/test_tasks.py::test_enrich_document_populates_metadata |
| FAILED | tests/api/routes/test_documents.py::TestDocumentAnnotations::test_list_annotations_empty |
| FAILED | tests/api/routes/test_documents.py::TestDocumentAnnotations::test_create_annotation |
| FAILED | tests/api/routes/test_documents.py::TestDocumentAnnotations::test_delete_annotation |
| FAILED | tests/api/routes/test_documents.py::TestDocumentDetail::test_get_document_includes_metadata |
| FAILED | tests/api/routes/test_documents.py::TestDocumentDetail::test_get_document_by_id |
| FAILED | tests/api/routes/test_documents.py::TestDocumentPassages::test_get_document_passages_limit_minimum |
| FAILED | tests/api/routes/test_documents.py::TestDocumentPassages::test_get_document_passages_with_limit |
| FAILED | tests/api/routes/test_documents.py::TestDocumentPassages::test_get_document_passages |
| FAILED | tests/api/routes/test_documents.py::TestDocumentPassages::test_get_document_passages_limit_maximum |
| FAILED | tests/api/routes/test_documents.py::TestDocumentPassages::test_get_document_passages_with_offset |
| FAILED | tests/api/routes/test_documents.py::TestDocumentUpdate::test_update_document_empty_payload |
| FAILED | tests/api/routes/test_documents.py::TestDocumentUpdate::test_update_document_metadata |
| FAILED | tests/api/routes/test_documents.py::TestDocumentUpdate::test_update_document_partial_fields |
| FAILED | tests/api/test_verses_graph.py::test_verse_graph_endpoint_combines_mentions_and_seeds |
| FAILED | tests/api/test_verses_graph.py::test_verse_graph_respects_source_type_filter |
| FAILED | tests/api/test_sql_migrations.py::test_sqlite_seed_loader_handles_disabled_migrations |

**Summary:** 28 failed, 1763 passed, 130 skipped, 9 warnings in 776.04s (0:12:56)
