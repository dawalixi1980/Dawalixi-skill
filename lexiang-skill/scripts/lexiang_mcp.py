#!/usr/bin/env python3
"""乐享 MCP 直连助手 —— 不依赖客户端 MCP 集成，直接通过 HTTP 调用乐享 MCP 服务。

凭据来源（按优先级）：
  1. 环境变量 COMPANY_FROM / LEXIANG_TOKEN
  2. 配置文件 ~/.config/lexiang/config.json  {"company_from":"...","token":"lxmcp_..."}

用法：
  python lexiang_mcp.py whoami
  python lexiang_mcp.py teams
  python lexiang_mcp.py spaces --team <team_id>
  python lexiang_mcp.py search 投标 --type all
  python lexiang_mcp.py vsearch "技术方案与项目经验" --limit 5
  python lexiang_mcp.py tools --preset knowledge
  python lexiang_mcp.py call space_list_spaces --args '{"team_id":"xxx"}'
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request

BASE = 'https://mcp.lexiang-app.com/mcp'
DEFAULT_PRESET = 'knowledge'


def load_conf():
    company = os.environ.get('COMPANY_FROM', '').strip()
    token = os.environ.get('LEXIANG_TOKEN', '').strip()
    if not (company and token):
        p = os.path.expanduser('~/.config/lexiang/config.json')
        if os.path.exists(p):
            try:
                d = json.load(open(p, encoding='utf-8'))
                company = company or str(d.get('company_from') or '').strip()
                token = token or str(d.get('token') or '').strip()
            except Exception:
                pass
    if not (company and token):
        sys.exit('缺少凭据：请设置环境变量 COMPANY_FROM / LEXIANG_TOKEN，'
                 '或写入 ~/.config/lexiang/config.json')
    return company, token


class Mcp:
    def __init__(self, company, token, preset=DEFAULT_PRESET):
        q = ('preset=%s&company_from=%s' % (preset, company)) if preset else ('company_from=' + company)
        self.url = BASE + '?' + q
        self.token = token
        self._id = 0
        self._init()

    def _post(self, body):
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + self.token,
                     'Content-Type': 'application/json',
                     'Accept': 'application/json, text/event-stream'},
            method='POST')
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode('utf-8', 'ignore')
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'ignore')[:300]
            sys.exit('HTTP %s: %s' % (e.code, detail))

    @staticmethod
    def _parse(txt):
        """兼容纯 JSON 与 SSE 包装（data: {...}）"""
        if txt.lstrip().startswith('{'):
            return json.loads(txt)
        for line in txt.splitlines():
            if line.startswith('data:'):
                try:
                    return json.loads(line[5:].strip())
                except Exception:
                    pass
        return None

    def _rpc(self, method, params=None, notify=False):
        body = {'jsonrpc': '2.0', 'method': method}
        if not notify:
            self._id += 1
            body['id'] = self._id
        if params is not None:
            body['params'] = params
        return self._parse(self._post(body))

    def _init(self):
        self._rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                                 'clientInfo': {'name': 'lexiang-mcp-cli', 'version': '1.0'}})
        try:
            self._rpc('notifications/initialized', notify=True)
        except Exception:
            pass

    def tools(self):
        d = self._rpc('tools/list', {})
        return [t['name'] for t in (d or {}).get('result', {}).get('tools', [])]

    def call(self, name, args=None):
        d = self._rpc('tools/call', {'name': name, 'arguments': args or {}})
        if d is None:
            return None
        if 'error' in d:
            return {'error': d['error']}
        out = ''
        for c in d.get('result', {}).get('content', []):
            if c.get('type') == 'text':
                out += c['text']
        try:
            return json.loads(out)
        except Exception:
            return out


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    ap = argparse.ArgumentParser(description='乐享 MCP 直连助手')
    ap.add_argument('command',
                    choices=['whoami', 'teams', 'spaces', 'search', 'vsearch', 'tools', 'call'])
    ap.add_argument('query', nargs='?',
                    help='search/vsearch 的查询词；call 时为工具名')
    ap.add_argument('--team', help='spaces 需要的 team_id')
    ap.add_argument('--type', default='all', help='search 的类型：all/doc/space/team')
    ap.add_argument('--limit', type=int, default=10, help='vsearch 返回条数')
    ap.add_argument('--preset', default=DEFAULT_PRESET, help='工具集：meta/search/knowledge')
    ap.add_argument('--args', default='{}', help='call 的 JSON 参数')
    a = ap.parse_args()

    company, token = load_conf()
    m = Mcp(company, token, a.preset)

    if a.command == 'tools':
        for t in m.tools():
            print(t)
        return

    if a.command == 'whoami':
        r = m.call('whoami')
    elif a.command == 'teams':
        r = m.call('team_list_teams', {})
    elif a.command == 'spaces':
        if not a.team:
            sys.exit('spaces 需要 --team <team_id>（可先执行 teams 获取）')
        r = m.call('space_list_spaces', {'team_id': a.team})
    elif a.command == 'search':
        if not a.query:
            sys.exit('search 需要关键词，例如：search 投标 --type all')
        r = m.call('search_kb_search', {'keyword': a.query, 'type': a.type})
    elif a.command == 'vsearch':
        if not a.query:
            sys.exit('vsearch 需要语义查询语句，例如：vsearch "技术方案与项目经验"')
        r = m.call('search_kb_embedding_search',
                   {'filters': {'keyword': a.query}, 'limit': a.limit})
    else:  # call
        if not a.query:
            sys.exit('call 需要工具名，例如：call space_list_spaces --args \'{"team_id":"x"}\'')
        try:
            args = json.loads(a.args)
        except Exception as e:
            sys.exit('--args 不是合法 JSON: %s' % e)
        r = m.call(a.query, args)

    print(json.dumps(r, ensure_ascii=False, indent=2) if not isinstance(r, str) else r)


if __name__ == '__main__':
    main()
