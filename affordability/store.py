import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ':memory:':
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.execute('PRAGMA busy_timeout=5000')
        self.connection.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, key TEXT, payload TEXT NOT NULL, revision INTEGER NOT NULL, PRIMARY KEY(kind,key))')
        self.connection.commit()

    def close(self):
        self.connection.close()

    def all(self, kind):
        rows = self.connection.execute('SELECT payload FROM records WHERE kind=? ORDER BY key', (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, kind, key):
        row = self.connection.execute('SELECT payload FROM records WHERE kind=? AND key=?', (kind, str(key))).fetchone()
        if row is None:
            raise KeyError(f'没有找到 {kind}/{key}')
        return json.loads(row[0])

    def revision(self, kind, key):
        row = self.connection.execute('SELECT revision FROM records WHERE kind=? AND key=?', (kind, str(key))).fetchone()
        return row[0] if row else 0

    @contextmanager
    def transaction(self):
        try:
            self.connection.execute('BEGIN IMMEDIATE')
            yield
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def put(self, kind, value, expected=None):
        return self.put_many(kind, [value], {str(value['id']): expected} if expected is not None else {})[0]

    def put_many(self, kind, values, expected=None):
        expected = expected or {}
        keys = [str(value['id']) for value in values]
        if len(set(keys)) != len(keys):
            raise ValueError('一次写入包含重复编号')
        results = []
        with self.transaction():
            for key, value in zip(keys, values):
                revision = self.revision(kind, key)
                if key in expected and expected[key] != revision:
                    raise Conflict('记录已被其他操作修改')
                payload = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
                self.connection.execute('INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(kind,key) DO UPDATE SET payload=excluded.payload,revision=excluded.revision', (kind, key, payload, revision + 1))
                results.append(revision + 1)
        return results
