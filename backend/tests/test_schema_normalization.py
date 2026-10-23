"""Unit tests for Two-Way Schema Normalization."""
import unittest
from backend.models.product import ProductRecord
from backend.registry.capability_map import CanonicalCapability
from backend.registry.schema_normalizer import SchemaNormalizer


class TestSchemaNormalization(unittest.TestCase):
    def test_request_translation_search(self):
        canonical_args = {"query": "laptop under 70000", "max_price": 70000.0}

        # Alpha expects query & max_price
        alpha_args = SchemaNormalizer.translate_request_to_provider(
            CanonicalCapability.PRODUCT_SEARCH,
            "provider_alpha",
            canonical_args
        )
        self.assertEqual(alpha_args, {"query": "laptop under 70000", "max_price": 70000.0})

        # Beta expects keywords & budget
        beta_args = SchemaNormalizer.translate_request_to_provider(
            CanonicalCapability.PRODUCT_SEARCH,
            "provider_beta",
            canonical_args
        )
        self.assertEqual(beta_args, {"keywords": "laptop under 70000", "budget": 70000.0})

        # Gamma expects filter_dict
        gamma_args = SchemaNormalizer.translate_request_to_provider(
            CanonicalCapability.PRODUCT_SEARCH,
            "provider_gamma",
            canonical_args
        )
        self.assertEqual(gamma_args, {"filter_dict": {"q": "laptop under 70000", "ceiling": 70000.0}})

    def test_request_translation_cart_add(self):
        canonical_cart = {
            "session_id": "sess_123",
            "product_id": "item_laptop_99",
            "quantity": 2
        }

        # Alpha expects session_id, product_id, quantity
        alpha_args = SchemaNormalizer.translate_request_to_provider(
            CanonicalCapability.CART_ADD,
            "provider_alpha",
            canonical_cart
        )
        self.assertEqual(alpha_args, {
            "session_id": "sess_123",
            "product_id": "item_laptop_99",
            "quantity": 2
        })

        # Beta expects session_id, item_sku, count
        beta_args = SchemaNormalizer.translate_request_to_provider(
            CanonicalCapability.CART_ADD,
            "provider_beta",
            canonical_cart
        )
        self.assertEqual(beta_args, {
            "session_id": "sess_123",
            "item_sku": "item_laptop_99",
            "count": 2
        })

    def test_normalize_provider_alpha_product(self):
        raw_alpha = {
            "id": "prod_1",
            "sku": "SKU-THINKPAD",
            "name": "ThinkPad E14",
            "brand": "Lenovo",
            "price": 64990.0,
            "currency": "INR",
            "specs": {
                "cpu": "Ryzen 7",
                "ram": "16GB",
                "storage": "512GB",
                "battery": "57Wh"
            },
            "stock_quantity": 8
        }
        record = SchemaNormalizer.normalize_product_record("provider_alpha", raw_alpha)
        self.assertIsInstance(record, ProductRecord)
        self.assertEqual(record.product_id, "prod_1")
        self.assertEqual(record.title, "ThinkPad E14")
        self.assertEqual(record.price, 64990.0)
        self.assertEqual(record.specs.cpu, "Ryzen 7")
        self.assertEqual(record.specs.ram, "16GB")
        self.assertEqual(record.specs.battery, "57Wh")
        self.assertEqual(record.provenance, "Provider Alpha (TechMart)")

    def test_normalize_provider_beta_product(self):
        raw_beta = {
            "item_sku": "SKU-VIVOBOOK",
            "item_title": "Vivobook S 14",
            "manufacturer": "ASUS",
            "cost": 68990.0,
            "curr": "INR",
            "hardware": {
                "processor": "Intel i5-13500H",
                "memory": "16GB LPDDR5",
                "drive": "512GB SSD",
                "runtime_hours": 10.5
            },
            "units_available": 5
        }
        record = SchemaNormalizer.normalize_product_record("provider_beta", raw_beta)
        self.assertIsInstance(record, ProductRecord)
        self.assertEqual(record.product_id, "SKU-VIVOBOOK")
        self.assertEqual(record.title, "Vivobook S 14")
        self.assertEqual(record.brand, "ASUS")
        self.assertEqual(record.price, 68990.0)
        self.assertEqual(record.specs.cpu, "Intel i5-13500H")
        self.assertEqual(record.specs.battery, "10.5 hrs")
        self.assertEqual(record.provenance, "Provider Beta (ElectroStore Pro)")


if __name__ == "__main__":
    unittest.main()
