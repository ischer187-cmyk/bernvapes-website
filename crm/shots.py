"""Nikotin-Shot-Rechner: Shots (Standard 20 mg/ml, 10 ml) für Zielstärke in einer Flasche.
Formel: n*shot_ml*shot_mg / (liquid_ml + n*shot_ml) = ziel  ->  n = ziel*liquid / (shot_ml*(shot_mg-ziel))"""
import math,sys
def shots(target_mg, bottle_ml, liquid_ml=None, shot_mg=20, shot_ml=10):
    """bottle_ml = Flaschenvolumen; liquid_ml = Shortfill-Menge (wenn None: Liquid + Shots füllen die Flasche genau)."""
    if target_mg<=0: return 0, 0.0
    if target_mg>=shot_mg: raise ValueError("Ziel muss < Shot-Stärke sein")
    if liquid_ml is None:  # passend füllen: liquid + n*shot = bottle
        n=bottle_ml*target_mg/(shot_mg*shot_ml); n=round(n)
        liquid=bottle_ml-n*shot_ml
    else:
        n=round(target_mg*liquid_ml/(shot_ml*(shot_mg-target_mg))); liquid=liquid_ml
    eff=n*shot_ml*shot_mg/(liquid+n*shot_ml) if n else 0.0
    return n, round(eff,2)
if __name__=="__main__":
    for t,b,l in [(3,60,50),(6,60,40),(3,120,100),(6,120,None)]:
        print(f"Ziel {t} mg, Flasche {b} ml, Liquid {l}: Shots/effektiv", shots(t,b,l))
