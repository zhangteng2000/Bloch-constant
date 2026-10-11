"""Parallel numerical processes for the same validated area cover.

This is ordinary interval arithmetic computation, with no agent delegation.
Every accepted rectangle and every pending rectangle is accounted for.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from fractions import Fraction as Qr
import hashlib
import json
from pathlib import Path
import time
from bloch_shear_prym_area_core import Geometry,B,pair,txt,arb,acb,ctx

G=None
def initialize():
    global G
    ctx.prec=128;ctx.cap=1
    G=Geometry()

def evaluate(row):
    sl,sh,tl,th=[Qr(x) for x in row[:4]]
    mode,depth=row[4:]
    val=G.cell(sl,sh,tl,th,mode,B(Qr(3,4)))
    return None if val is None else [pair(x) for x in val],G.last_direction

def load_complex(v):return acb(arb(v[0]),arb(v[1]))
def row_text(row):return [str(x) for x in row[:4]]+list(row[4:])
def hashes():
    return {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ["bloch_shear_prym_area_core.py","bloch_shear_prym_area_audit.py"]}

def main(args):
    ctx.prec=128;ctx.cap=1
    initial=(json.loads(Path(args.resume).read_text(encoding="utf8")) if args.resume else
             {"area":"0","accepted":0,"attempts":0,"totals":[["0","0"],["0","0"]],
              "stack":[["0","1","0","1",0,0],["0","1","0","1",1,0]]})
    stack=[[Qr(x) for x in row[:4]]+row[4:] for row in initial["stack"]]
    total=[load_complex(v) for v in initial["totals"]]
    area=Qr(initial["area"]);accepted=initial["accepted"];attempts=initial["attempts"]
    started=time.perf_counter();tol=B(Qr(1,20000));jobs={}
    checkpoint=Path(args.out).with_suffix(".checkpoint.json")
    stopping=False
    with ProcessPoolExecutor(max_workers=args.workers,initializer=initialize) as pool:
        while stack or jobs:
            while stack and len(jobs)<args.workers and not stopping:
                row=stack.pop()
                jobs[pool.submit(evaluate,row_text(row))]=row
            if not jobs:break
            done,_=wait(jobs,return_when=FIRST_COMPLETED,timeout=1)
            for future in done:
                row=jobs.pop(future)
                sl,sh,tl,th,mode,depth=row
                result,direction=future.result();attempts+=1
                val=None if result is None else [load_complex(v) for v in result]
                ar=(sh-sl)*(th-tl)
                if val is not None and all(max(x.real.rad(),x.imag.rad())<=tol*B(ar) for x in val):
                    total=[a+b for a,b in zip(total,val)]
                    area+=ar;accepted+=1
                else:
                    assert depth<50,("excess depth",row_text(row))
                    if direction==0 or (direction is None and sh-sl>=th-tl):
                        mid=(sl+sh)/2
                        stack.extend([[sl,mid,tl,th,mode,depth+1],[mid,sh,tl,th,mode,depth+1]])
                    else:
                        mid=(tl+th)/2
                        stack.extend([[sl,sh,tl,mid,mode,depth+1],[sl,sh,mid,th,mode,depth+1]])
                if attempts%100==0:
                    pending=stack+list(jobs.values())
                    snapshot={"status":"INCOMPLETE valid cover checkpoint","area":str(area),
                        "accepted":accepted,"attempts":attempts,"totals":[pair(x) for x in total],
                        "stack":[row_text(x) for x in pending],"source_sha256":hashes()}
                    checkpoint.write_text(json.dumps(snapshot,indent=2),encoding="utf8")
                    print("attempts",attempts,"accepted",accepted,"area",float(area),
                          "pending",len(pending),"seconds",time.perf_counter()-started,flush=True)
            if time.perf_counter()-started>args.seconds_limit:stopping=True
    complete=not stack and area==2
    if not complete:
        snapshot={"status":"INCOMPLETE valid cover checkpoint","area":str(area),
            "accepted":accepted,"attempts":attempts,"totals":[pair(x) for x in total],
            "stack":[row_text(x) for x in stack],"source_sha256":hashes()}
        checkpoint.write_text(json.dumps(snapshot,indent=2),encoding="utf8")
    report={"status":"Finite outer area enclosure" if complete else "INCOMPLETE outer cover",
        "complete":complete,"covered_parameter_area":str(area),"inner_xi_radius":"3/4",
        "denominator":pair(total[0]),"numerator":pair(total[1]),
        "accepted":accepted,"attempts":attempts,"seconds":time.perf_counter()-started,
        "workers":args.workers,"source_sha256":hashes(),
        "error_per_parameter_area":"1/20000 per real/imaginary component",
        "quadrature":"4 by 4 Gauss; error coefficient for eighth Taylor jet is 1/44100"}
    Path(args.out).write_text(json.dumps(report,indent=2),encoding="utf8")
    print(json.dumps(report,indent=2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--resume")
    p.add_argument("--out",default=str(Path(__file__).with_name("bloch_shear_prym_area_result.json")))
    p.add_argument("--workers",type=int,default=3)
    p.add_argument("--seconds-limit",type=float,default=3000)
    main(p.parse_args())
