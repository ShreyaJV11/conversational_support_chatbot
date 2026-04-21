# tests/test_email_processor.py

import pytest
from unittest.mock import MagicMock, patch
from app.services.graph_service import GraphServiceError

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_EMAILS = [
    {
        "id": "msg_001",
        "subject": "Login Issue",
        "from": {"emailAddress": {"address": "user1@test.com"}},
        "body": {"content": "I cannot log into my account since yesterday."}
    },
    {
        "id": "msg_002",
        "subject": "UI Bug",
        "from": {"emailAddress": {"address": "user2@test.com"}},
        "body": {"content": "The dashboard is not loading properly."}
    },
    {
        # Malformed — missing body and sender, should be skipped
        "id": "msg_003",
        "subject": "Empty",
        "from": {},
        "body": {"content": ""}
    }
]

MOCK_REPLY = (
    "Hello,\n\n"
    "Thank you for reaching out to MPS Support. "
    "We have received your request and our team will review it shortly.\n\n"
    "Regards,\nMPS Support Team"
)


# ---------------------------------------------------------------------------
# HELPER
# ---------------------------------------------------------------------------

def make_mocks(mock_graph_class, mock_llm, emails=None, draft_side_effect=None):
    """
    Shared setup for GraphService and LLM mocks.
    """
    mock_graph = MagicMock()
    mock_graph_class.return_value = mock_graph
    mock_graph.get_unread_emails.return_value = emails if emails is not None else MOCK_EMAILS
    mock_llm.return_value = MOCK_REPLY

    if draft_side_effect:
        mock_graph.create_draft_reply.side_effect = draft_side_effect
    else:
        mock_graph.create_draft_reply.return_value = "draft_abc123"

    return mock_graph


# ---------------------------------------------------------------------------
# TESTS
# ---------------------------------------------------------------------------

@patch("app.services.email_processor.GraphService")
@patch("app.services.email_processor.generate_email_reply")
def test_process_emails_success(mock_llm, mock_graph_class):
    """
    2 valid emails + 1 malformed.
    Expects: 2 processed, 1 failed, LLM called twice.
    """
    mock_graph = make_mocks(mock_graph_class, mock_llm)

    from app.services.email_processor import process_emails
    result = process_emails()

    assert result["processed"] == 2
    assert result["failed"]    == 1
    assert len(result["results"]) == 2
    assert mock_llm.call_count == 2
    assert mock_graph.create_draft_reply.call_count == 2

    # Verify correct subjects passed to LLM
    call_args = [call.args for call in mock_llm.call_args_list]
    subjects  = [args[0] for args in call_args]
    assert "Login Issue" in subjects
    assert "UI Bug"      in subjects

    print("✅ test_process_emails_success passed")


@patch("app.services.email_processor.GraphService")
@patch("app.services.email_processor.generate_email_reply")
def test_process_emails_graph_failure_isolation(mock_llm, mock_graph_class):
    """
    First email succeeds, second throws GraphServiceError.
    Expects: loop continues, 1 processed, 1 failed.
    """
    make_mocks(
        mock_graph_class, mock_llm,
        emails=MOCK_EMAILS[:2],
        draft_side_effect=["draft_001", GraphServiceError("403 Forbidden")]
    )

    from app.services.email_processor import process_emails
    result = process_emails()

    assert result["processed"] == 1
    assert result["failed"]    == 1
    assert result["results"][0]["status"] == "ok"
    assert result["results"][1]["status"] == "failed"
    assert "403 Forbidden" in result["results"][1]["error"]

    print("✅ test_process_emails_graph_failure_isolation passed")


@patch("app.services.email_processor.GraphService")
@patch("app.services.email_processor.generate_email_reply")
def test_process_emails_llm_failure_isolation(mock_llm, mock_graph_class):
    """
    LLM throws an exception on second email.
    Expects: first processed, second failed, loop does not crash.
    """
    mock_graph = make_mocks(mock_graph_class, mock_llm, emails=MOCK_EMAILS[:2])
    mock_llm.side_effect = [MOCK_REPLY, Exception("LLM timeout")]

    from app.services.email_processor import process_emails
    result = process_emails()

    assert result["processed"] == 1
    assert result["failed"]    == 1
    assert "LLM timeout" in result["results"][1]["error"]

    print("✅ test_process_emails_llm_failure_isolation passed")


@patch("app.services.email_processor.GraphService")
@patch("app.services.email_processor.generate_email_reply")
def test_process_emails_all_malformed(mock_llm, mock_graph_class):
    """
    All emails are malformed.
    Expects: 0 processed, all failed, LLM never called.
    """
    malformed_emails = [
        {"id": "msg_x1", "subject": "Test", "from": {}, "body": {"content": ""}},
        {"id": "msg_x2", "subject": "Test", "from": {}, "body": {"content": ""}},
    ]
    make_mocks(mock_graph_class, mock_llm, emails=malformed_emails)

    from app.services.email_processor import process_emails
    result = process_emails()

    assert result["processed"]    == 0
    assert result["failed"]       == 2
    assert mock_llm.call_count    == 0

    print("✅ test_process_emails_all_malformed passed")


@patch("app.services.email_processor.GraphService")
@patch("app.services.email_processor.generate_email_reply")
def test_process_emails_empty_inbox(mock_llm, mock_graph_class):
    """
    No unread emails in mailbox.
    Expects: 0 processed, 0 failed, LLM never called.
    """
    make_mocks(mock_graph_class, mock_llm, emails=[])

    from app.services.email_processor import process_emails
    result = process_emails()

    assert result["processed"] == 0
    assert result["failed"]    == 0
    assert result["results"]   == []
    assert mock_llm.call_count == 0

    print("✅ test_process_emails_empty_inbox passed")


@patch("app.services.email_processor.GraphService")
@patch("app.services.email_processor.generate_email_reply")
def test_draft_id_returned_in_results(mock_llm, mock_graph_class):
    """
    Verify draft_id is correctly captured in results.
    """
    mock_graph = make_mocks(
        mock_graph_class, mock_llm,
        emails=MOCK_EMAILS[:1],
        draft_side_effect=["draft_xyz999"]
    )

    from app.services.email_processor import process_emails
    result = process_emails()

    assert result["results"][0]["draft_id"]  == "draft_xyz999"
    assert result["results"][0]["status"]    == "ok"
    assert result["results"][0]["message_id"] == "msg_001"

    print("✅ test_draft_id_returned_in_results passed")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_process_emails_success()
    test_process_emails_graph_failure_isolation()
    test_process_emails_llm_failure_isolation()
    test_process_emails_all_malformed()
    test_process_emails_empty_inbox()
    test_draft_id_returned_in_results()
    print("\n✅ All tests passed.")