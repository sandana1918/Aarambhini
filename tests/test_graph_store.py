"""graph_store's pHash + Hamming distance — pure PIL, no Mongo.

This is the photo-authenticity gate's actual detector: a same/resized photo
must hash to Hamming distance 0 (or very near it), an unrelated photo far
apart, so a cross-seller match can be trusted as a real duplicate rather than
coincidence.
"""
from PIL import Image, ImageDraw

from graph_store import phash, _hamming


def _solid(color, size=(64, 64)):
    return Image.new("RGB", size, color)


def _checker(size=(64, 64)):
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    for x in range(0, size[0], 8):
        for y in range(0, size[1], 8):
            if (x // 8 + y // 8) % 2 == 0:
                d.rectangle([x, y, x + 8, y + 8], fill=(0, 0, 0))
    return img


def test_identical_image_hashes_to_zero_distance():
    img = _checker()
    assert _hamming(phash(img), phash(img)) == 0


def test_resized_copy_of_the_same_photo_stays_within_threshold():
    img = _checker()
    resized = img.resize((128, 128))
    # check_and_store_fingerprint's default threshold is 6 — a resize (what a
    # seller re-uploading her own photo would produce) must stay under it.
    assert _hamming(phash(img), phash(resized)) <= 6


def test_unrelated_images_hash_far_apart():
    a = phash(_solid((10, 10, 10)))
    b = phash(_checker())
    assert _hamming(a, b) > 6


def test_hash_is_a_fixed_length_hex_string():
    h = phash(_checker())
    assert len(h) == 16  # 64 bits, hex-encoded
    int(h, 16)  # must parse as hex — raises ValueError otherwise
