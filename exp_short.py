"""Sensitivity: if the longest entries are shortened, how many slots does the
colouring need?  Only the *window* construction is shortened (glyphs_of), so the
encoding and pool stay untouched - this measures the colour demand alone.
env: KEEP (fraction of each entry's glyphs to keep), N (how many of the longest)
"""
import sys, os
sys.path.insert(0, '.')
import cnbuild5 as cb

KEEP = float(os.environ.get('KEEP', '1.0'))
N = int(os.environ.get('N', '0'))
orig_glyphs_of = cb.glyphs_of

def glyphs_of(text):
    g = orig_glyphs_of(text)
    if KEEP >= 1.0 or N <= 0:
        return g
    # shorten only the N longest entries: keep the first KEEP fraction
    return g

def main():
    pass

# wrap the window builder: shorten per_table entries that are long
orig_choose = cb.choose_windows
def choose_windows(per_table):
    if KEEP < 1.0 and N > 0:
        allw = [(ti, i, len(w)) for ti, gs in per_table.items() for i, w in enumerate(gs)]
        allw.sort(key=lambda t: -t[2])
        cut = set((ti, i) for ti, i, _ in allw[:N])
        newpt = {}
        for ti, gs in per_table.items():
            newpt[ti] = [set(sorted(w)[:max(1, int(len(w) * KEEP))]) if (ti, i) in cut else w
                         for i, w in enumerate(gs)]
        print('  [exp] shortened %d entries to %d%% of their glyphs' % (len(cut), KEEP * 100))
        return orig_choose(newpt)
    return orig_choose(per_table)
cb.choose_windows = choose_windows
cb.OUT_ROM = cb.BASE + '/exp_out.smc'
cb.OUT_IPS = cb.BASE + '/exp_out.ips'
try:
    cb.main()
except SystemExit as e:
    print('build stopped: %s' % e)
