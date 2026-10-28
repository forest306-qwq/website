"""Insert the counter location include into this site's existing Nginx server blocks."""
import re
import sys
from pathlib import Path

INCLUDE = 'include /etc/nginx/snippets/forest306-counter.conf;'


def configure(text):
    token_pattern = r"""#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{};]|[^\s{};#]+"""
    stack, words, additions, matched = [], [], [], 0
    for token in re.finditer(token_pattern, text):
        value = token.group()
        if value.startswith('#'):
            continue
        if value == '{':
            stack.append({'server': words == ['server'], 'names': False, 'included': False, 'end': token.end()})
            words = []
        elif value == ';':
            if stack and stack[-1]['server']:
                if words[:1] == ['server_name'] and {'nwuc.cn', 'www.nwuc.cn'}.intersection(words[1:]):
                    stack[-1]['names'] = True
                if words == ['include', '/etc/nginx/snippets/forest306-counter.conf']:
                    stack[-1]['included'] = True
            words = []
        elif value == '}':
            if not stack:
                raise ValueError('Unbalanced Nginx configuration')
            block = stack.pop()
            if block['server'] and block['names']:
                matched += 1
                if not block['included']:
                    additions.append(token.start())
            words = []
        else:
            words.append(value.strip('"').strip("'"))
    if stack or not matched:
        raise ValueError('No matching nwuc.cn server block found; configuration left unchanged')
    for offset in reversed(additions):
        text = text[:offset] + '    ' + INCLUDE + '\n' + text[offset:]
    return text


if __name__ == '__main__':
    target = Path(sys.argv[1])
    original = target.read_text(encoding='utf-8')
    replacement = configure(original)
    if replacement != original:
        target.write_text(replacement, encoding='utf-8')
