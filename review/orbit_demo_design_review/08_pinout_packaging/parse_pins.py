import re, sys, csv, json, collections
DEF = sys.argv[1]; OUT = sys.argv[2]
txt = open(DEF).read().splitlines()
units = None; die = None
for l in txt:
    m = re.match(r'UNITS DISTANCE MICRONS (\d+)', l)
    if m: units = int(m.group(1))
    m = re.match(r'DIEAREA \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)', l)
    if m: die = tuple(int(x) for x in m.groups())
s = next(i for i,l in enumerate(txt) if l.startswith('PINS '))
e = next(i for i,l in enumerate(txt) if l.startswith('END PINS'))
declared = int(txt[s].split()[1])
body = '\n'.join(txt[s+1:e])
pins = []
for chunk in body.split(';'):
    chunk = chunk.strip()
    if not chunk.startswith('-'): continue
    name = chunk.split()[1]
    d = re.search(r'DIRECTION (\w+)', chunk); u = re.search(r'USE (\w+)', chunk)
    layers = re.findall(r'LAYER (\w+) \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)', chunk)
    pl = re.search(r'\+ (PLACED|FIXED|COVER) \( (-?\d+) (-?\d+) \) (\w+)', chunk)
    special = '+ SPECIAL' in chunk
    pins.append(dict(name=name, dir=d.group(1) if d else '', use=u.group(1) if u else '',
        layers=layers, status=pl.group(1), x=int(pl.group(2)), y=int(pl.group(3)), orient=pl.group(4), special=special))
x0,y0,x1,y1 = die
def edge(p):
    if p['special']: return 'none (met5 core straps)'
    dists = {'W': p['x']-x0, 'E': x1-p['x'], 'S': p['y']-y0, 'N': y1-p['y']}
    return min(dists, key=dists.get)
# spec meaning
meaning = {
 'clk':'Clock','rst_n':'Synchronous reset, active low','in_valid':'Input beat valid',
 'in_ready':'Input beat accepted this cycle if in_valid is also high','in_first':'This beat starts a new sum (acc = a*b)',
 'in_last':"After this beat, copy every lane's sum to the output buffer",
 'in_a':'Signed INT8 operands; lane i at [8*i +: 8]','in_b':'Signed INT8 operands; lane i at [8*i +: 8]',
 'out_valid':'Output buffer holds a presentable result','out_ready':'Consumer takes the result this cycle if out_valid is high',
 'out_data':'Result; lane i at [32*i +: 32], signed INT32','temp_valid':'Thermal reading is valid','temp_c':'Signed whole degrees Celsius',
 'clear_fault':'Synchronous: clear fault, zero all lane storage, empty output buffer',
 'fault':'Sticky: a duplicated copy disagreed (registered, 1-cycle latency)',
 'therm_state':'Voted thermal state: 0 NORMAL, 1 THROTTLE, 2 STOP, 3 unused (behaves as STOP)',
 'therm_repair':'The three thermal copies do not all agree this cycle','shutdown_req':'therm_state[1]: STOP (or the unused code 3)',
}
spec_dir = {'clk':'in','rst_n':'in','in_valid':'in','in_ready':'out','in_first':'in','in_last':'in','in_a':'in','in_b':'in',
 'out_valid':'out','out_ready':'in','out_data':'out','temp_valid':'in','temp_c':'in','clear_fault':'in','fault':'out',
 'therm_state':'out','therm_repair':'out','shutdown_req':'out'}
spec_width = {'clk':1,'rst_n':1,'in_valid':1,'in_ready':1,'in_first':1,'in_last':1,'in_a':32,'in_b':32,'out_valid':1,'out_ready':1,
 'out_data':128,'temp_valid':1,'temp_c':8,'clear_fault':1,'fault':1,'therm_state':2,'therm_repair':1,'shutdown_req':1}
rows=[]; issues=[]
seen=collections.defaultdict(set)
for p in pins:
    m = re.match(r'([A-Za-z_0-9]+)(?:\[(\d+)\])?$', p['name'])
    base, bit = m.group(1), m.group(2)
    lay = p['layers'][0][0]
    nrect = len(p['layers'])
    if base in ('VDD','VSS'):
        ys=sorted(((r[1]+r[3])/2+p['y'])/units for r in [tuple(map(int,q[1:])) for q in p['layers']])
        xs=((int(p['layers'][0][1])+p['x'])/units,(int(p['layers'][0][3])+p['x'])/units)
        w=(int(p['layers'][0][4])-int(p['layers'][0][2]))/units
        sp='none'
        mean=(f"Not in SPEC port table. DEF {p['use']} pin: {nrect} horizontal met5 straps, {w:g} um wide, x {xs[0]:g}-{xs[1]:g} um, "
              f"centres y {ys[0]:g}-{ys[-1]:g} um, pitch {ys[1]-ys[0]:.1f} um; x_um/y_um = DEF pin origin (FIXED). No bond pad or pad cell.")
        bitlbl=''
    else:
        if base not in meaning: issues.append('extra port '+p['name']); sp='NOT IN SPEC'; mean=''
        else:
            sp=base; mean=meaning[base]
            if bit is not None:
                b=int(bit)
                if base in ('in_a','in_b'): mean += f' | lane {b//8} bit {b%8}' + (' (sign)' if b%8==7 else '')
                if base=='out_data': mean += f' | lane {b//32} bit {b%32}' + (' (sign)' if b%32==31 else '')
                if base=='temp_c' and b==7: mean += ' | bit 7 (sign)'
            dmap={'INPUT':'in','OUTPUT':'out'}
            if dmap.get(p['dir'])!=spec_dir[base]: issues.append(f"direction mismatch {p['name']} DEF {p['dir']} SPEC {spec_dir[base]}")
        bitlbl = bit if bit is not None else ''
        seen[base].add(int(bit) if bit is not None else -1)
    # for power pins report placement origin; width of rect
    rows.append(dict(pin=p['name'],direction=p['dir'],use=p['use'],layer=lay,
        x_um=f"{p['x']/units:.3f}", y_um=f"{p['y']/units:.3f}", edge=edge(p), spec_port=sp, bit=bitlbl, spec_meaning=mean,
        _orient=p['orient'], _status=p['status'], _rect=p['layers'][0][1:], _nrect=nrect))
for base,w in spec_width.items():
    exp = set(range(w)) if w>1 else {-1}
    if seen[base]!=exp: issues.append(f'{base}: missing {sorted(exp-seen[base])} extra {sorted(seen[base]-exp)}')
# sort rows: power first, then by spec order then bit
order=list(spec_width)
def key(r):
    if r['pin'] in('VDD','VSS'): return (-1, r['pin'], 0)
    return (order.index(r['spec_port']) if r['spec_port'] in order else 99, r['spec_port'], int(r['bit']) if r['bit']!='' else -1)
rows.sort(key=key)
cols=['pin','direction','use','layer','x_um','y_um','edge','spec_port','bit','spec_meaning']
with open(OUT,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
# stats
st = dict(units=units, die=die, die_um=[v/units for v in die], declared=declared, parsed=len(pins), issues=issues,
  by_edge=collections.Counter(r['edge'] for r in rows), by_layer=collections.Counter(r['layer'] for r in rows),
  by_use=collections.Counter(r['use'] for r in rows), by_dir=collections.Counter(r['direction'] for r in rows),
  orient=collections.Counter(r['_orient'] for r in rows), status=collections.Counter(r['_status'] for r in rows),
  rect=collections.Counter(r['layer']+' '+str(r['_rect']) for r in rows if r['pin'] not in ('VDD','VSS')))
edge_port=collections.defaultdict(collections.Counter)
for r in rows: edge_port[r['edge']][r['spec_port']]+=1
st['edge_port']={k:dict(v) for k,v in edge_port.items()}
# per edge coordinate range
rng=collections.defaultdict(list)
for r in rows:
    if r['pin'] in ('VDD','VSS'): continue
    rng[r['edge']].append((float(r['x_um']),float(r['y_um'])))
st['ranges']={k:(min(a for a,b in v),max(a for a,b in v),min(b for a,b in v),max(b for a,b in v)) for k,v in rng.items()}
for r in rows:
    if r['pin'] in ('VDD','VSS','clk','rst_n','clear_fault','fault','in_valid','in_ready','out_valid','out_ready','in_first','in_last','temp_valid','therm_repair','shutdown_req'):
        print(r['pin'],r['direction'],r['use'],r['layer'],r['x_um'],r['y_um'],r['edge'],r['_status'],r['_orient'],r['_nrect'])
print(json.dumps(st, default=str, indent=1))
