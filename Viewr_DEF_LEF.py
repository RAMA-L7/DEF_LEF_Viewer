# -*- coding: utf-8 -*-

import os, io, re, sys, math
import tkinter as tk
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
from matplotlib import patches

# ========================= USER PATHS (EDIT THESE) =========================
# Put your full paths here, e.g. r"C:\\work\\chip\\DEF_MACRO1.txt" or "/home/user/DEF_MACRO1.txt"
DEF_PATH = r"C:\Users\7714\python_projects\data\DEF_MACRO1.txt"   # <-- CHANGE THIS to your DEF file path
LEF_PATH = r"C:\Users\7714\python_projects\data\LEF_2MACRO11.txt" # <-- CHANGE THIS to your LEF file path
# ===========================================================================

# ----------------------------- Parsers -----------------------------
DEF_UNITS_RE = re.compile(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)")
PAIR_RE = re.compile(r"\(\s*(\d+)\s+(\d+)\s*\)")
COMP_START_RE = re.compile(r"^-\s+(\S+)\s+(\S+)\s+\+\s+(UNPLACED|PLACED|FIXED)(.*)")
PLACED_RE = re.compile(r"\(\s*(\d+)\s+(\d+)\s*\)\s+([NSEWFR]{1,2})")
PIN_START_RE = re.compile(r"^-\s+(\S+).*?")
DIR_RE = re.compile(r"\+\s+DIRECTION\s+(INPUT|OUTPUT|INOUT)")
PIN_PLACED_RE = re.compile(r"\+\s+PLACED\s*\(\s*(\d+)\s+(\d+)\s*\)")
SIZE_RE = re.compile(r"SIZE\s+([0-9]*\.?[0-9]+)\s+BY\s+([0-9]*\.?[0-9]+)")
MACRO_RE = re.compile(r"^MACRO\s+(\S+)")

class DefData:
    def __init__(self):
        self.units = 1000; self.die_polygon=[]; self.components=[]; self.pins=[]; self.design=None

def parse_def(path):
    d = DefData();
    with io.open(path,'r',encoding='utf-8',errors='ignore') as f:
        lines=[ln.strip() for ln in f]
    i=0
    while i<len(lines):
        ln=lines[i]
        if ln.startswith('DESIGN'):
            parts=ln.split(); d.design = parts[1] if len(parts)>1 else None
        m=DEF_UNITS_RE.search(ln)
        if m: d.units=int(m.group(1))
        if ln.startswith('DIEAREA'):
            j=i; buf=ln
            while ';' not in buf and j+1<len(lines): j+=1; buf+=' '+lines[j]
            pts=PAIR_RE.findall(buf); d.die_polygon=[(int(x),int(y)) for x,y in pts]; i=j
        if ln.startswith('COMPONENTS'):
            i+=1
            while i<len(lines):
                l=lines[i]
                if l.startswith('END COMPONENTS'): break
                if l.startswith('-'):
                    buf=l; j=i
                    while ';' not in buf and j+1<len(lines): j+=1; buf+=' '+lines[j]
                    i=j; m=COMP_START_RE.search(buf)
                    if m:
                        inst,cell,status,rest=m.groups(); x=y=None; orient='N'
                        pm=PLACED_RE.search(rest)
                        if pm: x,y,orient=int(pm.group(1)),int(pm.group(2)),pm.group(3)
                        d.components.append({'inst':inst,'cell':cell,'status':status,'x':x,'y':y,'orient':orient})
                i+=1
        if ln.startswith('PINS'):
            i+=1; cur=None
            while i<len(lines):
                l=lines[i]
                if l.startswith('END PINS'): break
                if l.startswith('-'):
                    m=PIN_START_RE.match(l)
                    if m: 
                        cur={'name':m.group(1),'dir':None,'x':None,'y':None}
                        dm = DIR_RE.search(l)
                        if dm:
                             cur['dir'] = dm.group(1)
                else:
                    if cur is not None:
                        dm=DIR_RE.search(l)
                        if dm: cur['dir']=dm.group(1)
                        pm=PIN_PLACED_RE.search(l)
                        if pm: cur['x'],cur['y']=int(pm.group(1)),int(pm.group(2))
                if l.endswith(';') and cur is not None: d.pins.append(cur); cur=None
                i+=1
        i+=1
    return d

def parse_lef_sizes(path):
    sizes={}; cur=None
    with io.open(path,'r',encoding='utf-8',errors='ignore') as f:
        for raw in f:
            ln=raw.strip(); mm=MACRO_RE.match(ln)
            if mm: cur=mm.group(1); continue
            if cur:
                sm=SIZE_RE.search(ln)
                if sm: sizes[cur]=(float(sm.group(1)), float(sm.group(2)))
                if ln.startswith('END'): cur=None
    return sizes

# ----------------------------- Plotting -----------------------------
COLORS={'die':'#222222','placed':'#2ca02c','fixed':'#1f77b4','unplaced':'#d62728','pin_in':'#ff7f0e','pin_out':'#9467bd','pin_inout':"#121210"}

def which_edge(pt,bbox,tol):
    (xmin,ymin,xmax,ymax)=bbox; x,y=pt
    if abs(y-ymax)<=tol: return 'top'
    if abs(y-ymin)<=tol: return 'bottom'
    if abs(x-xmin)<=tol: return 'left'
    if abs(x-xmax)<=tol: return 'right'
    d={'top':abs(y-ymax),'bottom':abs(y-ymin),'left':abs(x-xmin),'right':abs(x-xmax)}
    return min(d,key=d.get)

def draw_scene(ax, d, sizes_lef):
    ax.clear(); poly=d.die_polygon
    if len(poly)==2:
        (x0,y0),(x1,y1)=poly; xs=[x0,x1,x1,x0]; ys=[y0,y0,y1,y1]
    else:
        xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    die_poly=list(zip(xs,ys))
    ax.add_patch(patches.Polygon(die_poly, fill=False, edgecolor=COLORS['die'], linewidth=2))
    xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys)
    for (cx,cy) in [(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)]:
        ax.plot([cx],[cy], marker='o', color=COLORS['die'])
        ax.text(cx, cy, f"({cx},{cy})", fontsize=8, va='bottom', ha='left', color=COLORS['die'], bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.6))
    units=d.units

    # >>> ADDED (1 line): start Y for stacking unplaced macros to the right
    ypos_tracker = ymax - (ymax - ymin)/2 - units*400

    unplaced_bin_y=ymin-(ymax-ymin)*0.12; unplaced_x=xmin  # (kept; no longer used after the change)

    for comp in d.components:
        cell=comp['cell']; inst=comp['inst']; status=comp['status']
        wmic,hmic=sizes_lef.get(cell,(10.0,10.0)); w=wmic*units; h=hmic*units
        if status=='UNPLACED' or comp['x'] is None:
            # >>> REPLACED (single line): move to right side and stack downward
            x = xmax + (xmax - xmin) * 0.12; y = ypos_tracker; ypos_tracker -= (h + units*5)
            color=COLORS['unplaced']; ls='--'; alpha=0.35; extra='\n(UNPLACED)'
        else:
            x,y=comp['x'],comp['y']; color=COLORS['fixed'] if status=='FIXED' else COLORS['placed']; ls='-'; alpha=0.6; extra=''
        rect=patches.Rectangle((x,y), w,h, linewidth=1.2, edgecolor=color, facecolor=color, alpha=alpha, linestyle=ls)
        ax.add_patch(rect)
        ax.text(x+w*0.02, y+h*0.5, f"{os.path.basename(inst)}\n{cell}{extra}", fontsize=7, color='black', va='center')

    bbox=(xmin,ymin,xmax,ymax); tol=max((xmax-xmin),(ymax-ymin))*0.01
    for p in d.pins:
        if p['x'] is None: continue
        x,y=p['x'],p['y']; direction=(p['dir'] or 'INOUT').upper()
        col=COLORS['pin_inout'];
        if direction=='INPUT': col=COLORS['pin_in']
        elif direction=='OUTPUT': col=COLORS['pin_out']
        edge=which_edge((x,y),bbox,tol); rot={'top':0,'right':0,'bottom':180,'left':90}[edge]
        tri=patches.RegularPolygon((x,y), numVertices=3, radius=tol*0.2, orientation=math.radians(rot), facecolor=col, edgecolor='k', linewidth=0.6, alpha=0.9)
        ax.add_patch(tri)
        ax.text(x, y, p['name'], fontsize=6, color='black', va='center', ha='center', bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none', alpha=0.6))
    ax.set_aspect('equal', adjustable='datalim')
    padx=(xmax-xmin)*0.08; pady=(ymax-ymin)*0.18
    ax.set_xlim(xmin-padx, xmax+padx); ax.set_ylim(ymin-pady, ymax+pady)
    ax.set_xlabel(f"DEF units (DBU). 1 micron = {units} DBU"); ax.set_ylabel("DBU")
    ax.set_title(f"Design: {d.design or ''} | Macros & I/O Ports")
    from matplotlib.lines import Line2D
    handles=[patches.Patch(color=COLORS['placed'],alpha=0.6,label='PLACED'),
             patches.Patch(color=COLORS['fixed'],alpha=0.6,label='FIXED'),
             patches.Patch(color=COLORS['unplaced'],alpha=0.35,label='UNPLACED'),
             Line2D([0],[0], marker=(3,0,0), color='w', label='PIN INPUT',  markerfacecolor=COLORS['pin_in'], markersize=10, markeredgecolor='k'),
             Line2D([0],[0], marker=(3,0,0), color='w', label='PIN OUTPUT', markerfacecolor=COLORS['pin_out'], markersize=10, markeredgecolor='k'),
             Line2D([0],[0], marker=(3,0,0), color='w', label='PIN INOUT',  markerfacecolor=COLORS['pin_inout'], markersize=10, markeredgecolor='k')]
    ax.legend(handles=handles, loc='upper right', fontsize=7, framealpha=0.7)

# ----------------------------- Tk App -----------------------------
class App(tk.Tk):
    def __init__(self, def_path=None, lef_path=None):
        super().__init__(); self.title("DEF/LEF Macro Viewer v3"); self.geometry("1200x1050")
        self.def_path=def_path; self.lef_path=lef_path
        # Figure + Toolbar
        self.fig,self.ax=plt.subplots(figsize=(26,22))
        self.canvas=FigureCanvasTkAgg(self.fig, master=self)
        self.toolbar=NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
        # Controls row
        ctrl=tk.Frame(self); ctrl.pack(fill=tk.X)
        tk.Label(ctrl, text='DEF:').pack(side=tk.LEFT, padx=4)
        self.def_entry=tk.Entry(ctrl, width=60); self.def_entry.pack(side=tk.LEFT, padx=4)
        tk.Label(ctrl, text='LEF:').pack(side=tk.LEFT, padx=4)
        self.lef_entry=tk.Entry(ctrl, width=40); self.lef_entry.pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text='Load', command=self.load_from_entries).pack(side=tk.LEFT, padx=6)
        tk.Button(ctrl, text='Save PNG', command=self.save_png).pack(side=tk.RIGHT, padx=6)
        # Status bar
        self.status=tk.Label(self, text='Ready', anchor='w'); self.status.pack(fill=tk.X)
        # Bindings for wheel zoom and pan drag
        # Prefill entries and render
        if self.def_path: self.def_entry.delete(0,tk.END); self.def_entry.insert(0,self.def_path)
        if self.lef_path: self.lef_entry.delete(0,tk.END); self.lef_entry.insert(0,self.lef_path)
        if self.def_path and self.lef_path: self.render()

    def load_from_entries(self):
        self.def_path=self.def_entry.get().strip(); self.lef_path=self.lef_entry.get().strip(); self.render()

    def save_png(self):
        # Save next to DEF by default
        base=os.path.splitext(os.path.basename(self.def_path or 'view'))[0]
        out=f"{base}_view.png"
        try:
            self.fig.savefig(out, dpi=300, bbox_inches='tight')
            self.status.config(text=f"Saved {out}")
        except Exception as e:
            messagebox.showerror('Save error', str(e))

    def render(self):
        if not self.def_path or not os.path.isfile(self.def_path):
            messagebox.showwarning('DEF missing', f'Invalid DEF path: {self.def_path}'); return
        if not self.lef_path or not os.path.isfile(self.lef_path):
            messagebox.showwarning('LEF missing', f'Invalid LEF path: {self.lef_path}'); return
        try:
            d=parse_def(self.def_path); sizes=parse_lef_sizes(self.lef_path)
            draw_scene(self.ax, d, sizes)
            self.canvas.draw()
            self.status.config(text=f"DEF: {self.def_path} | LEF: {self.lef_path} | 1µm={d.units} DBU  |  Scroll=Zoom, Right/Middle drag=Pan, 'r'=Reset")
        except Exception as e:
            messagebox.showerror('Error', str(e))

    # ----------- Zoom/Pan helpers -----------

# ----------------------------- Entry -----------------------------
if __name__=='__main__':
    # Allow command line override but also default to the path constants above
    def_arg=None; lef_arg=None
    args=sys.argv[1:]
    for i,a in enumerate(args):
        if a=='--def' and i+1<len(args): def_arg=args[i+1]
        if a=='--lef' and i+1<len(args): lef_arg=args[i+1]
    def_path = def_arg or DEF_PATH
    lef_path = lef_arg or LEF_PATH
    app=App(def_path, lef_path)
    app.mainloop()