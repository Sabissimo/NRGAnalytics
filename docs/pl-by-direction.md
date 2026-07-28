# P&L by direction — design record (SD 0206)

Status: live since 2026-07-24; fixed fractional splits + `[ანგარიშის კოდი (P&L)]` added
2026-07-28 (`330d2ce`, live after the next daily full reload).
Script: `SD 0206. Reg. PL Directions 24.qvs` (daily/24 only).
Source 1C analyst query the register+journal logic reimplements: [pl.txt](pl.txt).
Extraction queries: `_ElvareAnalytics.txt` (ДоходыИРасходы register, ВидыСчетовPL catalog
incl. Порядок, ПодразделенияЗатратДоходовСчетов, НаправленияДеятельности, ВидСчетаPL column
on the management chart of accounts).

## Fact

`РегистрНакопленияДоходыИРасходы` — standalone fact keyed
`orgGUID | 'PL' | date | 0 | direction` (`[ორგანიზაცია_კონტრაგენტი_პერიოდი_ნაშთია]`,
contractor segment is the literal `'PL'`). Grain: org × day × direction × article × account.
Measures: `[შემოსავალი (P&L)]`, `[ხარჯი (P&L)]`, `[თანხა (P&L)]` (= revenue − expense).
Audit attributes: `[ანგარიშის დასახელება (P&L)]` + `[ანგარიშის კოდი (P&L)]` (empty code = GUID
not in the chart of accounts), `[მუხლი (P&L)]` (empty = account has no ВидСчетаPL),
`[დამატჩებულია (P&L)]` (`'არა'` = key absent from the sheet), `[წილები დაბალანსებულია (P&L)]`
(`'არა'` = fractional weights don't total 100%). Those four separate the distinct
"unmatched" causes, which otherwise look identical.
Its bridge block in `SD 0301` is deliberately UNguarded — it re-scans the persisted fact on
every partial reload and rebuilds identical keys, so fact-side changes need no bridge edits
as long as the key recipe is preserved.

**Data window**: lower bound `YearStart(YearStart(vNow)-1)`; upper bound `vPLEnd =
MonthStart(reload date)`, exclusive — current month is still being closed in 1C, so the last
month in the fact is always the previous month. All four entry points cut at `vPLEnd`:
register pass, both journal passes, sales-injection staging.

## Assembly (five passes + allocation)

Passes 1–3 are mutually exclusive and exhaustive over the staging rows — see "Matching sheet
semantics" below for the routing table and the double-counting trap.

1. **Static** — articles matched in the Google Sheet with weight 1 on exactly one direction:
   whole amount to that direction via the static direction map (`MapНаправлениеСтатично`,
   key = trimmed article|structural-unit).
2. **Fixed fractions** (2026-07-28) — more than one numeric weight on the row: exploded into one
   row per weighted direction, amount × weight normalized by the row's own sum
   (`ФиксДолиПЛ`, marker map `MapНаправлениеФиксДоли`).
3. **Dynamic** — sheet value `'დინამიურად'` or key not found at all: row exploded into ≤3 rows
   by monthly COGS shares (`ДолиСебестоимости`: month × direction share of
   `[თვითღირებულება (გაყიდვები)]`, commercial directions only, same exclusions as
   `შიდა_და_არაძირითადები_ფილტრი`). Months with no shares fall back to the literal
   `'მიმართულების გარეშე'`.
4. **Sales injection (revenue + COGS)** — register/journal rows on the directions'
   revenue/COGS accounts are excluded (per account|registrar pairs that actually occur in
   the sales fact) and replaced by rows built from the sales fact, direction per document;
   internal/non-core/direction-less sales fall back to `'ლოგისტიკა'`.
5. **Journal side** (within 1–3 above): Управленческий ledger rows not covered by the
   register, via anti-join on registrar + the three filter branches from pl.txt
   (income/expense types on Операция; account-group codes 6–9 on ВводНачальныхОстатков;
   loan-interest codes 6–9 on ПриходнаяНакладная); credit side enters with flipped sign.

## Internal / non-core filtering (2026-07-28)

Sales sheets filter with `[Internal (კონტრაგენტები)]={'არა'}, [არ არის ძირითადი (ნომენკლატურა)]={'არა'}`.
The P&L fact now carries its own equivalents so P&L measures can be filtered the same way
instead of the exclusion being hardcoded:

| Row origin | `[Internal (P&L)]` / `[არ არის ძირითადი (P&L)]` |
|---|---|
| sales injection (revenue + COGS) | **real values** from the sales fact; grain extended by both |
| register / journal (static, dynamic, fractional) | both `'არა'` — such rows are neither internal nor non-core, so the standard filter keeps them |
| allocation-variant copies | carried through from the source row |

⚠ **The names deliberately differ from the sales-side fields.** `[Internal (კონტრაგენტები)]`
lives on `BridgeTableOrgDate` (`SD 0301`) and `[არ არის ძირითადი (ნომენკლატურა)]` on the items
dimension (`SD 0102`). Reusing either name on the P&L fact would give it a second shared field
with a table it already associates to → synthetic key / circular reference (the single-
attachment-point rule in CLAUDE.md). Hence `(P&L)`-suffixed twins, per the per-fact suffix
convention. Consequence: P&L measures need their **own** modifier, e.g.
`{<[Internal (P&L)]={'არა'}, [არ არის ძირითადი (P&L)]={'არა'}>}` — the sales variable
`შიდა_და_არაძირითადები_ფილტრი` will not reach P&L rows.

**The COGS-share basis stays script-filtered** (`ДолиСебестоимостиPre`, internal + non-core
excluded). Shares are a script-time aggregate that must sum to 1 so every allocated row is
distributed in full; making them respond to selections would change the P&L expense total
whenever a contractor or item filter moved. The basis already matches the filter users apply,
so a filtered P&L and its allocation weights agree.

Note the direction rule sends internal / non-core / direction-less sales to `'ლოგისტიკა'`, so
filtering both flags to `'არა'` shrinks ლოგისტიკა — that is the intended parity with sales,
not a bug.

## Matching sheet semantics

Google Sheet, PL Directions tab. Columns: `მუხლი` | `სტრუქტურული ერთეული` | `სულ` (control sum,
**not loaded**) | `საცალო` | `დისტრიბუცია` | `კორპორატიული` | `ლოგისტიკა` | `ადმინისტრაცია`.
`[მუხლი]` is the account's **ВидСчетаPL name**, not the account name.

| Row content | Branch |
|---|---|
| `1` / `100%` on exactly one direction | static |
| two or more numeric weights (`60%`, `40%`) | fixed fractions, normalized |
| `დინამიურად` | dynamic (monthly COGS shares) |
| no row for the key | dynamic, flagged `[დამატჩებულია (P&L)] = 'არა'` |

- Percent-formatted cells arrive as numbers (`100%` → 1) — confirmed in production.
- Weights are normalized by the row's own sum, so the amount is always distributed in full and
  the P&L ties to the register even when the row doesn't total 100%; such rows are flagged
  `[წილები დაბალანსებულია (P&L)] = 'არა'`.
- `[სულ]` is decorative — it is never loaded, so a row that reads 100% across in the spreadsheet
  is no guarantee Qlik honoured it. The flag field is the real check.

⚠ **Routing trap.** A fractional key must be excluded from BOTH the static and the dynamic
`Where` clauses (`MapНаправлениеФиксДоли … = 0`, `SD 0206:533` and `:544`). The dynamic branch
historically claimed everything the static map didn't; leaving it open makes fractional rows
flow down two branches and double count.

⚠ Fractions could not be done through `MapНаправлениеСтатично`: it is a **mapping** table and
`ApplyMap` returns one value per key. Hence the separate joined weight table.

⚠ Two `1`s on one row used to resolve to whichever loaded first; since 2026-07-28 that is a
2-weight row → even split, flagged unbalanced.

Known gap: `დინამიურად` mixed with a numeric weight ignores the number and goes fully dynamic
flagged `'კი'` — nothing announces it.

## Allocation variants (გადანაწილების ვარიანტები)

The report supports 4 views: (1) all 5 directions as-is, (2) ლოგისტიკა reallocated onto
საცალო/დისტრიბუცია/კორპორატიული by monthly COGS shares, (3) ადმინისტრაცია reallocated,
(4) both.

Implementation — row groups + link table, all inside SD 0206:

- Every fact row carries `[_PL ვარიანტის ჯგუფი]` ∈ COMMON / LOG_AS_IS / ADM_AS_IS /
  LOG_ALLOC / ADM_ALLOC (Latin values on purpose).
- Allocated copies of overhead rows (everything sitting on ლოგისტიკა/ადმინისტრაცია, incl.
  sales-injection fallback rows) are concatenated into the fact: amounts × monthly COGS
  share, direction + composite key rebuilt to the target commercial direction, original
  article and attributes preserved, marker `[გადანაწილების წყარო (P&L)]` =
  'ლოგისტიკიდან'/'ადმინისტრაციიდან' ('საკუთარი' on originals). Months with no positive
  shares: one copy stays on the source direction at share 1 — **totals are preserved in
  every variant by construction**.
- A 12-row inline link table (`ВариантыРаспределенияПЛ`) maps `[გადანაწილების ვარიანტი]`
  (dual: Georgian label / number 1–4 for sort) to the group combinations. It attaches to the
  fact at exactly ONE point (the group field) — no circular-reference risk.
- Section access: allocated rows keep contractor `'PL'` → covered by the existing 'PL'
  pseudo-group; no SD 0101 changes.

**App-side contract (critical):**

- Variable `vPLVariant` holds the **label text** (default `ცალ-ცალკე`); radio options are
  the four dual labels.
- Every P&L measure MUST carry the quoted modifier or it double-counts by exactly the
  overhead total (as-is and allocated rows coexist in the data):

  ```
  Sum({<[გადანაწილების ვარიანტი] = {'$(vPLVariant)'}>} [თანხა (P&L)])
  ```

- Quotes are mandatory: set-analysis literals match a dual field's TEXT representation; an
  unquoted number silently matches nothing → empty results.

## Article ordering (1C parity)

1C reports sort articles by the catalog's Порядок (`რიგითობა`) at every hierarchy level.
Reproduced by baking the order into the values, not per-chart sort expressions:

- A second `Hierarchy()` pass builds a per-node path of 10-digit zero-padded რიგითობა
  values; ordering by that path yields a global depth-first rank (`МухлиРангПЛ` → mapping).
- `[მუხლი (იერარქია)]` (and therefore all generated level fields) and the fact-side
  `[მუხლი (P&L)]` (via the article-name map) are `dual(name, rank)` → **plain Auto/numeric
  sorting reproduces 1C order in every object**, pivots included. MatchKey sites keep
  `Trim()` so Google-Sheet matching stays byte-identical.
- `[_მუხლი sort (P&L)]` (the padded path) stays on the hierarchy table for verification.
- Caveat: two articles with the same name would show as two identical-looking values
  (different ranks).

## Accounting-style display (app side)

Negative measures red with parentheses: number format `#,##0;(#,##0)` (inheritable via
master measure) + per-column text-color expression `=if(<measure> < 0, '#C00000')` (modern
pivot object).

## Verification checklist

1. Upload changed `.qvs`, full reload, close and REOPEN the app (reduction happens at open).
2. Data model viewer: no `$Syn`; variant link table connects to the fact only; variant field
   4 values, group field 5.
3. Totals invariant: `Sum({<[გადანაწილების ვარიანტი]={'<label>'}>}[თანხა (P&L)])` identical
   across all four labels.
4. Variant 2 → ლოგისტიკა ≈ 0 (residue only in no-COGS months); variant 3 → ადმინისტრაცია 0;
   variant 4 → both. Marker splits საკუთარი vs ლოგისტიკიდან/ადმინისტრაციიდან and the
   allocated part equals variant 1's overhead total.
5. Last month present in P&L = month before the reload date.
6. Articles appear in 1C order with chart sorting on Auto.
7. Partial reload → allocated rows still in the bridge; direction + calendar still slice.
8. Fractions: per-key `Sum([თანხა (P&L)])` unchanged by making a key fractional (normalization
   guarantees it) — a change means a branch double counts. `[წილები დაბალანსებულია (P&L)]='არა'`
   lists exactly the sheet rows whose weights don't total 100%.
