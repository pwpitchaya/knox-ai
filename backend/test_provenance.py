import unittest
from provenance import chunk_sections, LEGACY_THAI


class ProvenanceTests(unittest.TestCase):
    def test_verified_legacy_glyph_normalization(self):
        self.assertEqual('ขอนแก\uf70aน ค\uf70bน เป\uf712น ฝ\uf703ก'.translate(LEGACY_THAI),
                         'ขอนแก่น ค้น เป็น ฝึก')
    def test_chunks_never_cross_pdf_pages(self):
        chunks = chunk_sections([
            {"text": "ก" * 1000, "page_number": 1},
            {"text": "ข" * 900, "page_number": 2},
        ])
        self.assertEqual([c["page_number"] for c in chunks], [1, 1, 2, 2])
        self.assertTrue(all(len(set(c["text"])) == 1 for c in chunks))

    def test_short_tail_is_not_duplicated(self):
        chunks = chunk_sections([{"text": "abc", "page_number": None}])
        self.assertEqual(chunks, [{"text": "abc", "page_number": None}])

    def test_invalid_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            chunk_sections([], chunk_size=100, overlap=100)

    def test_blank_page_does_not_invent_evidence(self):
        self.assertEqual(chunk_sections([{"text": "  ", "page_number": 3}]), [])


if __name__ == "__main__":
    unittest.main()
