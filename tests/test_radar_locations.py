import json
import tempfile
import unittest
from pathlib import Path

from scripts.radar_locations import (
    LocationCatalogError,
    find_location_candidates,
    infer_exact_location_mentions,
    load_location_catalog,
    merge_location_mentions,
    resolve_location_mentions,
)


class RadarLocationTests(unittest.TestCase):
    def test_catalog_uses_canonical_names_and_codes(self):
        catalog = load_location_catalog()
        self.assertEqual(catalog.by_id["hainan-haikou"]["name"], "海口市")
        self.assertEqual(catalog.by_id["hainan-sansha"]["code"], "460300")
        self.assertEqual(catalog.by_id["hainan-baisha"]["name"], "白沙黎族自治县")

    def test_default_catalog_lives_with_other_controlled_configuration(self):
        self.assertEqual(
            load_location_catalog().metadata["verified_on"],
            "2026-07-12",
        )

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

    def test_resolver_orders_province_before_city_or_county(self):
        catalog = load_location_catalog()
        candidates = find_location_candidates(
            "海南省海口市",
            "海南省海口市举行活动",
            catalog,
        )
        resolved = resolve_location_mentions(
            [
                {"location_id": "hainan-haikou", "evidence": "海口市"},
                {"location_id": "hainan", "evidence": "海南省"},
            ],
            candidates,
            catalog,
        )
        self.assertEqual([row["name"] for row in resolved], ["海南省", "海口市"])

    def test_official_full_name_is_inferred_but_alias_is_not(self):
        catalog = load_location_catalog()
        candidates = find_location_candidates("文昌胡椒产业", "文昌市蓬莱镇发展胡椒", catalog)
        self.assertEqual(
            infer_exact_location_mentions("文昌胡椒产业", "文昌市蓬莱镇发展胡椒", candidates, catalog),
            [{"location_id": "hainan-wenchang", "evidence": "文昌市"}],
        )
        alias_candidates = find_location_candidates("文昌胡椒产业", "蓬莱镇发展胡椒", catalog)
        self.assertEqual(
            infer_exact_location_mentions("文昌胡椒产业", "蓬莱镇发展胡椒", alias_candidates, catalog),
            [],
        )

    def test_model_location_wins_when_exact_pass_finds_same_id(self):
        merged = merge_location_mentions(
            [{"location_id": "hainan-wenchang", "evidence": "文昌市蓬莱镇"}],
            [{"location_id": "hainan-wenchang", "evidence": "文昌市"}],
        )
        self.assertEqual(merged, [{"location_id": "hainan-wenchang", "evidence": "文昌市蓬莱镇"}])

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
