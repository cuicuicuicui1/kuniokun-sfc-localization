"""ROM-independent subset of the project's 65816 assembler.

Kept separate because importing the historical builder opens a Japanese ROM
relative to cwd. This patcher needs only the supplied edited ROM and font.
"""
def snes_of_rom(off):
    return off//0x8000,0x8000+(off&0x7FFF)

class Asm:
    def __init__(self,base):
        self.base=base;self.b=bytearray();self.lab={};self.fix=[]
    def op(self,*values):self.b.extend(values)
    def hexs(self,value):self.b.extend(bytes.fromhex(value))
    def label(self,name):
        assert name not in self.lab
        self.lab[name]=len(self.b)
    def rel(self,opcode,name):
        self.fix.append(('rel',len(self.b)+1,name));self.op(opcode,0)
    def jmp_to(self,name):
        self.fix.append(('abs',len(self.b)+1,name));self.op(0x4C,0,0)
    def far_rel(self,opcode,name,tag):
        inv={0xB0:0x90,0x90:0xB0,0xD0:0xF0,0xF0:0xD0}[opcode]
        self.rel(inv,'far_'+tag);self.jmp_to(name);self.label('far_'+tag)
    def long_to(self,off):
        bank,addr=snes_of_rom(off);self.op(0x5C,addr&255,addr>>8,bank)
    def queue_load_x(self):
        self.hexs('08 C2 20 48 E2 20 AF DF 09 7E C2 20 29 FF 00 AA 68 28')
    def queue_store_x(self):
        self.hexs('08 C2 20 48 E2 20 8A 8F DF 09 7E C2 20 68 28')
    def done(self):
        for kind,pos,name in self.fix:
            target=self.lab[name]
            if kind=='rel':
                delta=target-pos-1;assert -128<=delta<=127,(name,delta)
                self.b[pos]=delta&255
            else:
                addr=0x8000+(self.base+target)%0x8000
                self.b[pos:pos+2]=addr.to_bytes(2,'little')
        return bytes(self.b)
