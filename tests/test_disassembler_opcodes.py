"""Protect opcode identities used in relocation and WRAM ownership audits."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dis65 import MODES
class NativeOpcodes(unittest.TestCase):
 def test_pull_registers(self):
  self.assertEqual(MODES[0x7A],('PLY','imp'))
  self.assertEqual(MODES[0xFA],('PLX','imp'))
 def test_indexed_zero(self):
  self.assertEqual(MODES[0x9E],('STZ','absX'))
  self.assertEqual(MODES[0x96],('STX','dpY'))
if __name__=='__main__':unittest.main()
