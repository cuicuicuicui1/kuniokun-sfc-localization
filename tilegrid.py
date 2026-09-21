# -*- coding: utf-8 -*-
import sys
from PIL import Image

def dec2(b,off):
    p0=b[off:off+8]; p1=b[off+8:off+16]
    px=[]
    for y in range(8):
        row=[]
        for x in range(8):
            bit=7-x
            row.append(((p0[y]>>bit)&1)|(((p1[y]>>bit)&1)<<1))
        px.append(row)
    return px

def dec4(b,off):
    px=[[0]*8 for _ in range(8)]
    for pl in range(2):
        base=off+pl*16
        for y in range(8):
            for x in range(8):
                bit=7-x
                v=((b[base+y]>>bit)&1)|(((b[base+8+y]>>bit)&1)<<1)
                px[y][x]|= v<<(pl*2)
    return px

PAL=[(255,255,255),(170,170,170),(85,85,85),(0,0,0),
     (255,0,0),(0,255,0),(0,0,255),(255,255,0),
     (255,0,255),(0,255,255),(128,64,0),(0,128,64),
     (64,0,128),(192,192,128),(128,192,192),(64,64,64)]

def render(rom, off, ntiles, bpp, cols, scale, path, marks=()):
    d=open(rom,'rb').read()
    dec = dec2 if bpp==2 else dec4
    step = 16 if bpp==2 else 32
    rows=(ntiles+cols-1)//cols
    tw=8*scale
    W=cols*tw; H=rows*tw
    img=Image.new('RGB',(W,H),(255,255,255))
    px=img.load()
    for t in range(ntiles):
        g=dec(d, off+t*step)
        r=t//cols; c=t%cols
        for y in range(8):
            for x in range(8):
                col=PAL[g[y][x] & 15]
                for dy in range(scale):
                    for dx in range(scale):
                        px[c*tw+x*scale+dx, r*tw+y*scale+dy]=col
    if marks:
        for mt in marks:
            r=mt//cols
            for x in range(W):
                for dy in range(2):
                    px[x, r*tw+dy]=(255,0,0)
    img.save(path)
    print('wrote',path,W,'x',H)

if __name__=='__main__':
    rom=sys.argv[1]; off=int(sys.argv[2],16); nt=int(sys.argv[3]); bpp=int(sys.argv[4]); cols=int(sys.argv[5]); sc=int(sys.argv[6]); out=sys.argv[7]
    render(rom,off,nt,bpp,cols,sc,out)
