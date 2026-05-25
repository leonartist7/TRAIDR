from sentiment.spam_filter import spam_repetition_score


def test_spam_repetition_scores_duplicates_and_shill_language() -> None:
    score = spam_repetition_score(["$ABC moon 100x", "$ABC moon 100x", "ape now guaranteed"])

    assert score > 0


def test_spam_empty_is_zero() -> None:
    assert spam_repetition_score([]) == 0
