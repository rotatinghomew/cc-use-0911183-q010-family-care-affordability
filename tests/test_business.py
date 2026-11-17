import unittest
from affordability.app import Application
from affordability.store import Store
from affordability.households import eligible_households, family_needs, save_income
from affordability.quotes import service_quote
from affordability.assistance import subsidy_decision, approve_subsidy


class AffordabilityTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:')
        Application(self.store).seed()

    def tearDown(self):
        self.store.close()

    def test_family_needs_combine_residents(self):
        self.assertEqual(family_needs(self.store, 'h1')['home'], 12)

    def test_eligibility_end(self):
        self.assertNotIn('h3', [row['id'] for row in eligible_households(self.store, '2026-10-01')])

    def test_interval_does_not_create_verified_income(self):
        self.assertEqual(subsidy_decision(self.store, 'h1', 50000)['status'], 'needs_verification')

    def test_verified_subsidy_cap(self):
        self.assertEqual(subsidy_decision(self.store, 'h2', 50000)['cents'], 20000)

    def test_unavailable_service(self):
        with self.assertRaises(ValueError):
            service_quote(self.store, 'h2', {'daycare': 4})

    def test_family_time_not_per_resident(self):
        self.assertFalse(service_quote(self.store, 'h1', {'daycare': 11})['within_time'])

    def test_income_interval_validation(self):
        row = dict(self.store.get('income', 'i1'), lower_cents=500000)
        with self.assertRaises(ValueError):
            save_income(self.store, row)

    def test_award_requires_verification(self):
        with self.assertRaises(ValueError):
            approve_subsidy(self.store, 'h1', 50000, 'a1')

    def test_paid_award_does_not_change_with_policy(self):
        before = approve_subsidy(self.store, 'h2', 50000, 'a1')
        self.store.put('policies', {'id': 'current', 'income_limit_cents': 0, 'max_cents': 0})
        self.assertEqual(approve_subsidy(self.store, 'h2', 50000, 'a1'), before)

    def test_reference_reuse_for_other_application_fails(self):
        approve_subsidy(self.store, 'h2', 50000, 'a1')
        with self.assertRaises(ValueError):
            approve_subsidy(self.store, 'h2', 10000, 'a1')
