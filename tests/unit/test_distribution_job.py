from integrations.contracts.distribution import ContentVariant, DistributionJob


def test_distribution_job_has_one_content_package_and_one_integration():
    job = DistributionJob("test-job", "test-package-001", "integration-1",
                          ContentVariant("integration-1", "MEITI V3 POSTIZ INTEGRATION TEST"))
    assert job.content_package_id == "test-package-001"
    assert job.variant.integration_id == job.integration_id
