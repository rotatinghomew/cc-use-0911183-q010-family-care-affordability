import argparse
import csv
import io
import json
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .app import Application
from .store import Conflict, Store


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True).encode('utf-8')


def csv_text(rows, columns):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='raise')
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column) for column in columns})
    return output.getvalue()


def load_dataset(store, path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not value:
        raise ValueError('数据集须为按记录类型组织的对象')
    prepared = []
    for kind, rows in value.items():
        if not isinstance(kind, str) or not isinstance(rows, list):
            raise ValueError('数据集类型或记录集合不合法')
        keys = []
        for row in rows:
            if not isinstance(row, dict) or 'id' not in row:
                raise ValueError('每条记录须有编号')
            keys.append(str(row['id']))
            prepared.append((kind, str(row['id']), json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True)))
        if len(keys) != len(set(keys)):
            raise ValueError('同一类型记录编号重复')
    with store.transaction():
        for kind, key, payload in prepared:
            store.connection.execute('INSERT INTO records VALUES(?,?,?,1) ON CONFLICT(kind,key) DO UPDATE SET payload=excluded.payload,revision=records.revision+1', (kind, key, payload))
    return {'types': len(value), 'records': len(prepared)}


def handler_for(application):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, status, value):
            body = json_bytes(value)
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def dispatch(self, method):
            parsed = urlsplit(self.path)
            if parsed.path == '/health' and method == 'GET':
                return self.send_json(200, {'status': 'ok'})
            if not parsed.path.startswith('/api/'):
                return self.send_json(404, {'error': '接口不存在'})
            try:
                if method == 'POST':
                    length = int(self.headers.get('Content-Length', '0'))
                    if length <= 0 or length > 1048576:
                        return self.send_json(400, {'error': '请求长度不合法'})
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError('请求内容须为对象')
                else:
                    payload = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
                value = application.call(method, parsed.path[5:], payload)
                return self.send_json(200, value)
            except Conflict as error:
                return self.send_json(409, {'error': str(error)})
            except (ValueError, TypeError) as error:
                return self.send_json(400, {'error': str(error)})
            except KeyError as error:
                return self.send_json(404, {'error': str(error)})

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')

    return Handler


def main():
    parser = argparse.ArgumentParser(description='本地业务服务与数据核对')
    parser.add_argument('command', choices=['demo', 'check', 'serve', 'load'])
    parser.add_argument('--database')
    parser.add_argument('--input')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        store = Store(args.database or str(Path(directory) / 'business.sqlite3'))
        application = Application(store)
        application.seed()
        try:
            if args.command == 'load':
                if not args.input or not args.database:
                    parser.error('load 需要 --input 和 --database')
                print(json_bytes(load_dataset(store, args.input)).decode('utf-8'))
            elif args.command == 'serve':
                HTTPServer((args.host, args.port), handler_for(application)).serve_forever()
            else:
                value = application.demo() if args.command == 'demo' else application.check()
                print(json_bytes(value).decode('utf-8'))
        finally:
            store.close()
