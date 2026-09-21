"""Generate a small test translation (cn_translation.json) covering a few strings
from each of the 5 tables, so the whole pipeline can be verified in the simulator."""
import json
import re
import sys

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'

TESTS = {
    (0x0193B5, 8): '什么也没发生',
    (0x0193B5, 9): '这个不能用！',
    (0x0193B5, 28): '我是怪叔叔',
    (0x0193B5, 61): '嗯',
    (0x01DBC5, 0): '入场券',
    (0x01DBC5, 1): '1区间定期票',
    (0x01DBC5, 2): '2区间定期票',
    (0x01DBC5, 10): '冰镇麦芽水',
    (0x01DBC5, 30): '银项链',
    (0x01E098, 0): '等级',
    (0x01E098, 1): '体力',
    (0x01E098, 2): '气力',
    (0x01E098, 3): '力量',
    (0x01E1D5, 0): '梅田 梅地下 东',
    (0x01E1D5, 1): '梅田 梅地下 西',
    (0x01E1D5, 2): '梅田 梅地下 北',
    (0x01E4CE, 0): '上升了',
    (0x01E4CE, 1): '下降了',
    (0x01E4CE, 2): '学会了',
}

TOKEN = re.compile(r'\{([0-9A-Fa-f]{2})\}')


def ctrl_suffix(text):
    """Append {F3} if the original string is terminated by a F3 control code."""
    m = re.search(r'\{([0-9A-Fa-f]+)\}$', text)
    if m and 'F3' in m.group(1).upper():
        return '{F3}'
    return ''


def main():
    recs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))
    by = {}
    for r in recs:
        by[(r['table_rom_off'], r['index'])] = r

    out = {}
    for (table, idx), cn in sorted(TESTS.items()):
        r = by.get((table, idx))
        if r is None:
            print('MISSING %06X[%d]' % (table, idx))
            continue
        key = '%06X' % r['text_rom_off']
        full = cn + ctrl_suffix(r['text'])
        out[key] = full
        print('%06X[%3d]  orig=%-34s -> %s' % (table, idx, r['text'][:34], full))
    json.dump(out, open(BASE + '/cn_translation.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\nwrote cn_translation.json with %d entries' % len(out))


if __name__ == '__main__':
    main()