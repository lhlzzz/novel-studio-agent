from content.models import ContentPackage
from social.variants import XHSVariantBuilder, XianyuListingBuilder
import pytest


def test_xhs_image_note_variant():
    package = ContentPackage("p", "title", "body", media_assets=("a.jpg", "b.jpg"))
    variant = XHSVariantBuilder().build(package, account_id="xhs-1")
    assert variant.content_type == "NOTE_IMAGE"
    assert variant.platform == "xiaohongshu"


def test_xianyu_requires_commerce_intent():
    package = ContentPackage("p", "item", "desc")
    with pytest.raises(ValueError):
        XianyuListingBuilder().build(package, account_id="xy-1")
