from pathlib import Path
import json

from .households import *
from .quotes import *
from .assistance import *


class Application:
    def __init__(self, store):
        self.store = store

    def seed(self):
        directory = Path(__file__).resolve().parent.parent / 'fixtures'
        for path in sorted(directory.glob('*.json')):
            if not self.store.all(path.stem):
                self.store.put_many(path.stem, json.loads(path.read_text(encoding='utf-8')))

    def demo(self):
        return {'eligible': [row['id'] for row in eligible_households(self.store, '2026-11-01')], 'needs': family_needs(self.store, 'h1'), 'quote': service_quote(self.store, 'h1', {'home': 12, 'daycare': 4}), 'decision': subsidy_decision(self.store, 'h1', 50000)}

    def check(self):
        value = self.demo()
        return {'status': 'ok', 'summary': value}

    def call(self, method, route, payload):
        if method == 'GET' and route == 'summary':
            return self.demo()
        if method == 'POST' and route == 'income':
            return {'revision': save_income(self.store, payload)}
        if method == 'POST' and route == 'quote':
            return service_quote(self.store, payload['household'], payload['basket'])
        if method == 'POST' and route == 'award':
            return approve_subsidy(self.store, payload['household'], payload['charge_cents'], payload['reference'])
        raise KeyError('接口不存在')
