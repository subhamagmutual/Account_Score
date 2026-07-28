import pandas as pd
from pathlib import Path
from pas_diagnostics.schema import ColumnMap
from pas_diagnostics import reasons, card

cm = ColumnMap()
df = pd.read_csv("fixture_physician_scores.csv", low_memory=False)

print("=== Reconciliation: do the reason codes reproduce the score? ===")
print(reasons.reconciliation(df, cm).to_string(index=False, max_colwidth=60))

print("\n=== Composite dispersion ===")
tab, notes = reasons.dispersion(df, cm)
print(tab.to_string(index=False))
for n in notes:
    print(" -", n)

print("\n=== Reason codes, one physician ===")
rc = reasons.reason_codes(df.head(400), cm, top_n=3)
one = rc[rc["record"] == rc["record"].iloc[0]]
print(one[["direction","rank","variable","score","raw_value",
           "effective_weight","contribution_points","caveat"]].to_string(index=False,
           max_colwidth=44))

print("\n=== Triage queue, top 6 by premium at risk ===")
tq = reasons.triage(df, cm, cm.exposure_premium, top_n=6)
print(tq.to_string(index=False, max_colwidth=30))

out = card.render(df.sort_values("PAS_COMPOSITE_SCORE", ascending=False),
                  cm, Path("out/pas_cards.html"), limit=12)
print(f"\ncards -> {out}  ({out.stat().st_size/1024:.0f} KB)")

sent = df[df["CV_LOSS_FREE_YEARS"] == -99]
print(f"\nsanity: {len(sent):,} sentinel records; their loss_free_years score "
      f"= {sent['SCORE_LOSS_FREE_YEARS'].unique()}")
