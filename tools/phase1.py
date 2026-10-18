"""Revisión de fichas capturadas. No envía alertas ni inventa precios."""
import argparse
import json
from pathlib import Path
from core.pricing import grouped_offers

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--out",default="reports/candidates_checked.json")
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf8"))
    if not isinstance(data,list):parser.error("Se requiere lista JSON")
    result=grouped_offers(data)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("Aceptados:",sum(len(x) for x in result["verified_by_condition"].values()))
    print("Rechazados:",len(result["rejected"]))
if __name__=="__main__":main()
