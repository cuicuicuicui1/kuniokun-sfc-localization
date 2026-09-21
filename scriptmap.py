# -*- coding: utf-8 -*-
"""Find SRW4 custom-code script regions and classify chars."""
def classify(d):
    N=len(d); cls=bytearray(N); ln=bytearray(N)
    i=0
    while i<N:
        b=d[i]
        if 0x40<=b<=0x8F: cls[i]=1; ln[i]=1; i+=1      # hiragana
        elif 0x90<=b<=0xDF: cls[i]=2; ln[i]=1; i+=1    # katakana
        elif 0xF0<=b<=0xF5 and i+1<N: cls[i]=3; ln[i]=2; i+=2   # kanji
        elif b==0xF6 and d[i:i+4]==bytes([0xF6,0xFC,0x00,0x01]): cls[i]=4; ln[i]=4; i+=4  # newline
        elif b==0xFF: cls[i]=5; ln[i]=1; i+=1          # end
        elif b<0x40: cls[i]=6; ln[i]=1; i+=1           # symbols/digits
        else: cls[i]=7; ln[i]=1; i+=1                  # 0xE0-0xEF, 0xF6-0xFE
    return cls,ln

def regions(d, win=0x100, minhira=0.22, maxkata=0.20, mingood=0.55):
    cls,ln=classify(d); N=len(d)
    good=bytearray(N)
    for i in range(N):
        if cls[i]==1: good[i]=1
        elif cls[i]==3: good[i]=1
        elif cls[i]==6: good[i]=1
        elif cls[i]==4: good[i]=1
    hits=[]
    for off in range(0,N-win,0x40):
        h=k=ka=s=0
        for i in range(off,off+win):
            if cls[i]==1: h+=1
            elif cls[i]==2: k+=1
            elif cls[i]==3: ka+=1
            elif cls[i]==6: s+=1
        tot=h+k+ka+s
        if tot==0: continue
        if h/tot>=minhira and k/tot<=maxkata and (h+ka+s)/tot>=mingood:
            hits.append((off,h/tot,k/tot,ka/tot))
    # merge
    out=[]
    for off,hf,kf,kaf in hits:
        if out and off-out[-1][1]<=0x200:
            out[-1][1]=off; out[-1][2].append(hf)
        else:
            out.append([off,off,[hf]])
    return [(a,b,sum(v)/len(v)) for a,b,v in out]
