from integrations.contracts.distribution import ContentVariant, DistributionJob


def test_distribution_job_has_one_content_package_and_one_account():
    job = DistributionJob("test-job", "test-package-001", "account-1",
                          ContentVariant("account-1", "MEITI NATIVE SOCIAL TEST"))
    assert job.content_package_id == "test-package-001"
    assert job.variant.account_id == job.account_id
    assert job.integration_id == job.account_id
