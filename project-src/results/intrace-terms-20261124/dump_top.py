import json,sys
from pathlib import Path
sys.argv=[sys.argv[0]]
exec(open("score_s2.py").read().split('if __name__')[0])
ls=label_set("48/38")
pair=Path("triage/+interleaving/1")
out={}
for run in sorted(p for p in pair.iterdir() if (p/"manifest.json").exists()):
    case=json.loads((run/"manifest.json").read_text())["subject"]["name"]
    if case=="svp_simple_001_001": continue
    tri={d["candidate_id"]:d for d in map(json.loads,filter(str.strip,(run/"llm"/"triage.jsonl").read_text().splitlines()))}
    ctx=[json.loads(p.read_text()) for p in sorted((run/"context").glob("*.json"))]
    anns=moved_truth(case,ls)
    rep=match_subject(anns,ctx,subject=case)
    matched={m.candidate_id:(m.annotation.kind,m.annotation.index) for m in rep.bug_matches+rep.trap_matches if m.candidate_id}
    rows=[]
    for c in ctx:
        if tri[c["id"]]["bucket"]!="likely_real": continue
        acc={a["role"]:a for a in c["accesses"]}
        trip=" ".join(f'{acc[r]["kind"][0].upper()}{acc[r]["source"]["line"]}' for r in ("A1","B","A2"))
        rows.append((c["variable"]["name"], trip, acc["A1"]["flow"], acc["B"]["flow"], matched.get(c["id"],("-",0))))
    out[case]=rows
    tag=lambda m: f"{m[0]}#{m[1]}" if m[0]!="-" else "UNANNOT"
    print(f"== {case}: {len(rows)} on top, unannotated {sum(1 for r in rows if r[4][0]=='-')}")
    for r in sorted(rows):
        print(f"   {tag(r[4]):9} {r[0]:40} {r[1]:14} A:{r[2]} B:{r[3]}")
