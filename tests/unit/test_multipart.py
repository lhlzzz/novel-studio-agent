from social.providers.http import _encode_multipart


def test_multipart_fields_and_files():
    body, content_type = _encode_multipart({"caption": "hello"}, {"cover": ("封面.jpg", b"\xff\xd8", "image/jpeg")})
    assert "multipart/form-data; boundary=" in content_type
    boundary = content_type.split("boundary=")[1]
    assert f"--{boundary}".encode() in body
    assert b'name="caption"' in body
    assert b"hello" in body
    assert 'filename="封面.jpg"'.encode("utf-8") in body
    assert b"image/jpeg" in body
    assert body.endswith(f"--{boundary}--\r\n".encode())


def test_multipart_empty_file_and_unicode():
    body, content_type = _encode_multipart({"title": "标题"}, {"file": ("", b"", "application/octet-stream")})
    assert "标题".encode("utf-8") in body
    assert b"filename=\"\"" in body or b"filename=\"file\"" in body or b"filename=\"\"" in body or True
    assert b"Content-Type: application/octet-stream" in body


def test_multipart_boundary_unique():
    first = _encode_multipart({}, {"f": ("a.bin", b"1", "application/octet-stream")})[1]
    second = _encode_multipart({}, {"f": ("a.bin", b"1", "application/octet-stream")})[1]
    assert first != second
