from integrations.contracts.distribution import Publication


def test_publication_requires_external_provider_post_id():
    publication = Publication("job-1", "account-1", "x", "x-1", "x-status-1", "submitted")
    assert publication.provider_post_id == "x-1"
    assert publication.platform_object_id == "x-status-1"
    assert publication.account_id == "account-1"
    assert publication.distribution_job_id != publication.provider_post_id
