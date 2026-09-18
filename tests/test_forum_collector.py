from app.collectors.forum import ForumCollector


def test_validate_metrics():

    assert ForumCollector.validate_metrics(
        views=100,
        replies=10,
        likes=20,
        contributors=5,
    )


def test_reject_negative_views():

    assert not ForumCollector.validate_metrics(
        views=-1,
        replies=10,
        likes=20,
        contributors=5,
    )


def test_reject_negative_replies():

    assert not ForumCollector.validate_metrics(
        views=100,
        replies=-1,
        likes=20,
        contributors=5,
    )


def test_reject_negative_likes():

    assert not ForumCollector.validate_metrics(
        views=100,
        replies=10,
        likes=-1,
        contributors=5,
    )


def test_empty_keyword():

    collector = ForumCollector()

    # The collector should not perform a request
    # when the keyword is empty.
    import asyncio

    result = asyncio.run(
        collector.collect("")
    )

    assert result == []