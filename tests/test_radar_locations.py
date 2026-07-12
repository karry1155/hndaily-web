import json
import tempfile
import unittest
from pathlib import Path

from scripts.radar_locations import (
    LocationCatalogError,
    find_location_candidates,
    load_location_catalog,
    resolve_location_mentions,
)


class RadarLocationTests(unittest.TestCase):
    def test_catalog_uses_canonical_names_and_codes(self):
        catalog = load_location_catalog()
        self.assertEqual(catalog.by_id["hainan-haikou"]["name"], "海口市")
        self.assertEqual(catalog.by_id["hainan-sansha"]["code"], "460300")
        self.assertEqual(catalog.by_id["hainan-baisha"]["name"], "白沙黎族自治县")

    def test_candidates_use_aliases_but_return_canonical_records(self):
        result = find_location_candidates(
            "在白沙调研", "刘小明来到白沙黎族自治县", load_location_catalog()
        )
        self.assertEqual(result[0]["name"], "白沙黎族自治县")

    def test_resolver_rejects_id_outside_article_candidates(self):
        catalog = load_location_catalog()
        candidates = find_location_candidates("三沙调研", "在三沙市调研", catalog)
        with self.assertRaisesRegex(LocationCatalogError, "candidate"):
            resolve_location_mentions(
                [{"location_id": "hainan-sanya", "evidence": "三亚市"}],
                candidates,
                catalog,
            )

    def test_duplicate_codes_fail_catalog_validation(self):
        payload = {
            "version": "test", "source": "official", "verified_on": "2026-07-12",
            "divisions": [
                {"location_id": "a", "name": "海口市", "code": "460100", "level": "prefecture", "aliases": []},
                {"location_id": "b", "name": "三亚市", "code": "460100", "level": "prefecture", "aliases": []},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "locations.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(LocationCatalogError, "duplicate code"):
                load_location_catalog(path)


if __name__ == "__main__":
    unittest.main()
