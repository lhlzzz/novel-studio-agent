from commerce.analytics import content_commerce_report
from commerce.models import ContentProductLink, Product
from content.models import ContentPackage


def test_content_is_not_product():
    package = ContentPackage("pkg", "Title", "Body")
    product = Product("sku-1", "Offer")
    link = ContentProductLink(package.package_id, product.product_id)
    assert package.package_id != product.product_id
    assert link.relation == "supports"


def test_commerce_report_keeps_nulls():
    report = content_commerce_report([
        {"content_package_id": "pkg", "product_id": "sku", "platform": "x", "topic": "hooks", "action": "interest"}
    ])
    assert report["product_roi"]["sku"]["revenue"] is None
    assert report["content_interest"]["pkg"]["actions"] == 1
