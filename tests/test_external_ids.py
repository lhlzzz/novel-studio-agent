from integrations.contracts.distribution import Publication


def test_publication_requires_external_postiz_id():
    publication = Publication("job-1", "postiz-1", "integration-1", "x", "submitted")
    assert publication.postiz_post_id == "postiz-1"
