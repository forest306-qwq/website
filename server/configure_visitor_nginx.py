"""Insert the visitor entrance include without replacing Certbot or counter rules."""
import re
import sys
from pathlib import Path

INCLUDE = '/etc/nginx/snippets/forest306-visitors.conf'


def configure(text):
    pattern = r'''#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{};]|[^\s{};#]+'''
    stack, words, additions, matched = [], [], [], 0
    for token in re.finditer(pattern, text):
        value = token.group()
        if value.startswith('#'):
            continue
        if value == '{':
            # Do not silently override pre-existing authorization directives.
            stack.append({'server': words == ['server'], 'names': False, 'included': False,
                          'conflicts': False})
            words = []
        elif value == ';':
            if stack and stack[-1]['server']:
                block = stack[-1]
                if words[:1] == ['server_name'] and {'nwuc.cn', 'www.nwuc.cn'}.intersection(words[1:]):
                    block['names'] = True
                if words == ['include', INCLUDE]:
                    block['included'] = True
                if words[:1] == ['auth_request']:
                    block['conflicts'] = True
            words = []
        elif value == '}':
            if not stack:
                raise ValueError('Unbalanced Nginx configuration')
            block = stack.pop()
            if block['server'] and block['names']:
                matched += 1
                if block['conflicts']:
                    raise ValueError('Existing auth_request needs manual review; configuration not changed')
                if not block['included']:
                    additions.append(token.start())
            words = []
        else:
            words.append(value.strip('"').strip("'"))
    if stack or not matched:
        raise ValueError('No matching nwuc.cn server block found; configuration not changed')
    for offset in reversed(additions):
        text = text[:offset] + '    include ' + INCLUDE + ';\n' + text[offset:]
    return text


if __name__ == '__main__':
    target = Path(sys.argv[1])
    original = target.read_text(encoding='utf-8')
    replacement = configure(original)
    if replacement != original:
        target.write_text(replacement, encoding='utf-8')
