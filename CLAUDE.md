# NRGAnalytics — Qlik Sense load scripts

**Working rules.** No project knowledge in assistant memory — the user works across several
machines, so everything durable lives in this repo's `.md` files and must be pushed; memory does not
travel. "push" means update the affected docs first, then commit and push — never ship code with
docs describing the old behaviour; but do not push unprompted.

Qlik Cloud (tenant `elvare.de.qlikcloud.com`) load scripts for Electro Market / NRG analytics.
Data source: 1C exports QVDs with **Russian** table/field names; scripts rename fields to **Georgian**.
The `_*.txt` files are the 1C-side query definitions (reference only, not executed here).

## File layout

Scripts are grouped per app by filename prefix: `SD` (executive model), `Sales`, `Stock`,
`Debitors`, `Cashflow`, `Credits`, `Accounting`, `Statement`. Within a prefix:

- `00xx` mappings, `01xx` catalogs, `02xx` facts/registers, `03xx` bridges, `04xx` calendar
- The master file (e.g. `SD.qvs`) `$(include)`s the others **from `lib://Holding:DataFiles`**
- `…24.qvs` suffix = wrapped in `if(not IsPartialReload())` → runs only on the **daily full
  reload** (partials every 30 min skip it; its tables persist in memory). SD-app QVD sources
  (variables set app-side, not in these files): `vPrefix='SD' vSpace='Electro Market'
  vSpacePrefix='EM'` ← 30-min batch `_SD.txt`; `vPrefix24='ELV' vSpace24='Holding'
  vSpacePrefix24='HLD'` ← daily batch `_ElvareAnalytics.txt`.

**Deployment: editing locally does nothing until the changed `.qvs` files are uploaded to the
Holding space DataFiles and the app is reloaded.** A confusing test result often means the
deployed copy is stale — always confirm upload state before debugging "impossible" behavior.

**Push = deploy.** `.github/workflows/sync-to-qlik.yml` runs `upload_files_to_qlik.py` on every
push to main (plus nightly 00:00 UTC + manual): uploads **only `*.qvs`** files and **deletes**
any cloud `*.qvs` absent from the repo. Never push scripts that depend on QVDs/columns the
extraction hasn't produced yet — the nightly full reload will run them and can break the whole app.

## SD data model (the important one)

Single association chain — a new table may attach at exactly ONE point or you create a
circular reference (Qlik silently "loosely couples" a table → charts show 0):

```
Sales fact ──┐
Debitors ────┼─[ორგანიზაცია_კონტრაგენტი_პერიოდი_ნაშთია]── BridgeTableOrgDate
P&L fact ────┘        (org|contractor|date|ნაშთია|direction)      │
                                    [კონტრაგენტის_ჯგუფი_პერიოდი_ნაშთია]
                                                                  │
   СправочникКонтрагентыИерархия ──[%lnk_კონტრაგენტის ჯგუფი]── BridgeTableContrDate
   СправочникКонтрагентыОбратная  ──[%lnk_… ჯგუფი_დაგეგმვის პერიოდი]──┤
        └── segment plan tables                            [DateForConnect]
                                                                  │
   royalty fact + royalty budget ──[DateForConnect]────────── SDCalendar
```

- `%lnk_*` fields are hidden key fields; display fields are suffixed per fact
  (`… (გაყიდვები)`, `… (ანგარიშსწორებები მყიდველებთან)`) precisely so they do NOT associate.
- The bridges in `SD 0301` **rebuild the composite keys from component fields** by resident-
  scanning the facts. Any change to a key (e.g. adding the direction segment) must be made
  identically in every build site: sales fact, plan rows, debitors (×2 blocks), both bridge scans.
- `[მიმართულება]` (global direction dimension, filters sales + plans + debitors + P&L) lives on
  `BridgeTableOrgDate`.
- P&L fact (`SD 0206. Reg. PL Directions 24.qvs`, daily/24): standalone fact keyed
  `orgGUID|'PL'|date|0|direction`; adds directions ლოგისტიკა/ადმინისტრაცია. Its bridge block in
  `SD 0301` is deliberately UNguarded (must re-scan the persisted fact on every partial reload).
  Data window: starts at `vPLStart` = `RangeMax(YearStart(YearStart(vNow)-1), MakeDate(2026,1,1))`
  — rolling two years but never before 2026, same formula as the calendar's
  `[Year SD (ბოლო 2 წელი, 2026+)]` so filter and window agree. Ends at the month BEFORE the reload
  date (`vPLEnd`) — current month is excluded
  on purpose. Allocation variants: group field + allocated overhead copies + 12-row link table
  on `[გადანაწილების ვარიანტი]`; app variable `vPLVariant` holds the LABEL and every P&L
  measure needs the quoted modifier `{'$(vPLVariant)'}` or it double-counts. Articles carry
  1C `რიგითობა` order as the numeric part of `dual()` values → charts sort on plain Auto.
  Allocation is a **single wave into final buckets** (2026-07-31): the sheet has 7 target
  columns — 3 retail stores (`SET vPLRetailStores`; store column = direction 'საცალო' +
  department = store name, headers must byte-match the NORMALISED department names) + the 4
  other directions (department kept EMPTY on allocated rows — only stores are tracked).
  Three parts guarded by key-marker maps: numeric cells → fixed part (joined on the match key,
  month-independent); `დინამიურად` marks → dynamic part over the MARKED buckets only,
  renormalized (a real marks table remembers which column held the mark); key absent → the
  month's full 5-bucket COGS basis, flagged. Mixed rows are supported: numbers are absolute,
  the remainder splits dynamically — a mixed key flows through BOTH the fixed and dynamic
  parts by design (complementary shares); everything else must stay mutually exclusive, and
  widening a guard double counts silently. Fractions need joined weight tables, not a map:
  `ApplyMap` returns one value per key. The COGS basis excludes retail COGS on non-store
  departments entirely.
  P&L carries its own `[Internal (P&L)]` / `[არ არის ძირითადი (P&L)]` (real values on
  sales-injected rows, `'არა'` on register/journal rows) — **the sales-side names could not be
  reused**: they live on `BridgeTableOrgDate` / the items dimension, so putting them on the fact
  would add a second shared field with an already-associated table → synthetic key. P&L measures
  therefore need their own modifier, not `$(შიდა_და_არაძითადები_ფილტრი)`. A second, narrower
  flag `[Internal EEE (P&L)]` keys off an explicit contractor-code list (`SET vPLInternalEEE`)
  instead of the additional attribute. On **non-sales rows there is no contractor**, so BOTH
  flags come from the posting's account instead: `'კი'` when the account or any ancestor has a
  code in `SET vPLInternalEEEAccounts` (real `Hierarchy()` walk; the CoA parent column is
  `[ექვემდებარება ანგარიშს]`). They are therefore identical on non-sales rows and diverge only
  on sales rows. Any new per-row attribute on the sales injection must also go into BOTH
  injection `Group By` lists; they aggregate, so a select-list-only addition fails the reload.
  Departments: names are normalised through the SAME 1C register the Statement app uses
  (`СоответствияЗначений`, type `'EEE განყოფილების ჩანაცვლება'`), but ONLY on the displayed field —
  `[_MatchKey (P&L)]` deliberately keeps the RAW name, because the Google Sheet's unit column holds
  raw names. Normalising both sides silently breaks the match for every remapped department. The
  2026 cut-off (`vPLDeptFrom`) likewise applies ONLY to the displayed field, for every source — the
  match key carries the department regardless of year, because gating it would move money between
  directions. Sales rows never touch the match key at all, so their department is display-only.
  **The department on every allocated row IS the bucket's** (store name / empty) — the
  2026-07-30 "departments within the direction by COGS" layer is gone; only sales-injected rows
  keep their real department (so non-store retail departments carry ONLY their own sales/COGS).
  Dynamic months with no basis in the marked buckets stay whole on 'მიმართულების გარეშე'
  (NOT re-routed to ლოგისტიკა — that fallback is sales-injection-only); variant copies in
  no-share months keep the source direction and department at share 1.
  `[სტრუქტურული ერთეული (P&L, საწყისი)]` is never reassigned: incurred vs attributed stay separate,
  and it is what the Google Sheet is keyed on.
  Full design: `docs/pl-by-direction.md`; original 1C query: `docs/pl.txt`.
- Budget/plan tables load from Google Sheets via `GetWorksheetV2` (two spreadsheets concatenated).
  Sheet direction names must exactly match `MapПеречислениеНаправленияПокупателей` output.
- Direction plans are **concatenated into the sales fact** as rows with pseudo-org `'გეგმა'` —
  see `docs/direction-plans.md` for the full design and why every alternative fails.

## SECTION ACCESS — the #1 trap

`SD 0101` has `SECTION ACCESS` reducing on `[%lnk_კონტრაგენტი]` (lives only in
`СправочникКонтрагентыИерархия`). On **app open** (not reload) Qlik deletes every row not
transitively associated with the user's allowed values — **rows whose link chain ends in a
null die for everyone, including admins**. Symptom: fields exist, unconditional `Sum()` = 0,
rows counted = 0, yet the reload log shows rows loaded.

Any new data must have an association path to an allowed value. Pattern used for plan rows:
pseudo-group `'PLAN'` — assigned in `SD 0301` OrgBridge, a pseudo-row in the hierarchy table,
and one `'PLAN'` row per user/admin appended to the SA sources in `SD 0101`. Section-access
values must be uppercase; use Latin markers (Georgian has risky case folding there).
Same pattern, second instance: pseudo-group `'PL'` for the P&L fact rows (SD 0206) —
granted in the **ADMIN block only**; to expose P&L to USERs, add the same one-liner in the
`UserDescendants` block of `SD 0101`.

## Debugging rules learned the hard way

- **`exit script` bisecting is only valid at block boundaries** (after `Drop Table …NonDistinct`).
  Stopping between a NonDistinct load and its Drop freezes a model where both twins coexist →
  4 shared fields → synthetic key + circular reference → misleading zeros.
- A plain (no set-analysis) `Sum()` with no selections can NOT be zeroed by associations.
  If it is 0, the rows are physically absent — think section-access reduction or empty source.
- Exec-dashboard period variables (`მიმდინარე_წელი`, `…_დღეის_ჩათვლით`, etc.) are defined
  app-side (not in these scripts) and modify calendar fields `[Year SD]`/`[Date SD]`;
  `შიდა_და_არაძითადები_ფილტრი` = internal-contractors + non-core-items exclusion.
  That variable (and the measure `ჩეკები (შიდა და არაძითადების გარეშე)`) is spelled WITHOUT
  რი (არაძითადები) in the app itself — confirmed by the user 2026-07-30; do not "correct" it,
  a corrected name stops matching the app object.
- **Never retype Georgian/Russian identifiers — always copy-paste.** Cyrillic lookalikes
  (е, а, о, р, ф…) corrupt field names silently and the script still parses.
- Copy-paste discipline is NOT enough: generation itself injects Cyrillic phonetic chars into
  Georgian words (ф→ფ, х→ხ, е→ე, б→ბ, у→უ, л→ლ). **After ANY edit touching Georgian text, run
  a scan for words mixing Georgian (U+10A0–10FF) and Cyrillic (U+0400–04FF)** and fix to zero;
  the only legitimate mixes are Georgian+Latin (`%lnk_*`, `path`, `sort`). Then verify token
  counts of new field names across all build sites.
- **Set-analysis literals match a dual field's TEXT, not its number.** For dual values like
  `[გადანაწილების ვარიანტი]`, `{<F={$(v)}>}` with a numeric variable silently matches nothing
  — use the label in quotes: `{<F={'$(v)'}>}`. Conversely, dual's numeric part is what Auto
  sorting uses — baking a rank into `dual(name, rank)` beats per-chart sort expressions
  (pivot tables apply expression sorting unreliably).
- **`Alt()` is numeric-only** — it returns the first argument with a valid NUMBER, so it
  silently rejects text like 'საცალო'. For text fallbacks use `if(Len(Trim(x))>0, x, y)`.
- **Never put code literals (table names, statements) verbatim in instruction comments** —
  search/replace-based edits and greps match the comment instead of the code.
- A field can hold the literal STRING 'მიმართულების გარეშე' (ApplyMap defaults), not null —
  emptiness checks alone don't catch "no direction".
- Partial-reload prefixes (`Replace LOAD` / `Add LOAD`) are used everywhere; keep new
  statements consistent or partial reloads will drop/duplicate data.

## Related Qlik apps

- **EXECUTIVE DASHBOARD** — appId `d5fbc0e4-9d85-431b-976d-4004f656e299`, space Electro Market.
  Runs the SD scripts. Master measures: segment-plan family "(ინსტალერები და მომხმარებლები, …)",
  direction-plan family "(მიმართულებები, …)" (16 measures created 2026-07-09).
  Known dead items: `Plan (CYTD)` / `Plan ∆` reference nonexistent `[თანხა (გეგმა)]`.

## Verification checklist after touching plan wiring

1. Upload ALL changed `.qvs` files, full reload, then **close and reopen the app**
   (reduction happens at open).
2. Unconditional `Sum([გაყიდვები მიმართულებებით (გეგმა)])` > 0.
3. Table: dimension `[მიმართულება]` + plan + fact measures — every direction shows both
   (a direction with only one side = spelling mismatch sheet vs enum).
4. Master-calendar month/year selections slice the plan, including future dates.
5. If possible, open once as a USER-role account.
