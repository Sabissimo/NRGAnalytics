# P&L by direction — design record (SD 0206)

Status: live since 2026-07-24. Script: `SD 0206. Reg. PL Directions 24.qvs` (daily/24 only).
Source 1C analyst query the register+journal logic reimplements: [pl.txt](pl.txt).
Extraction queries: `_ElvareAnalytics.txt` (ДоходыИРасходы register, ВидыСчетовPL catalog
incl. Порядок, ПодразделенияЗатратДоходовСчетов, НаправленияДеятельности, ВидСчетаPL column
on the management chart of accounts).

## Fact

`РегистрНакопленияДоходыИРасходы` — standalone fact keyed
`orgGUID | 'PL' | date | 0 | direction` (`[ორგანიზაცია_კონტრაგენტი_პერიოდი_ნაშთია]`,
contractor segment is the literal `'PL'`). Grain: org × day × direction × article × account.
Measures: `[შემოსავალი (P&L)]`, `[ხარჯი (P&L)]`, `[თანხა (P&L)]` (= revenue − expense).
Its bridge block in `SD 0301` is deliberately UNguarded — it re-scans the persisted fact on
every partial reload and rebuilds identical keys, so fact-side changes need no bridge edits
as long as the key recipe is preserved.

**Data window**: lower bound `YearStart(YearStart(vNow)-1)`; upper bound `vPLEnd =
MonthStart(reload date)`, exclusive — current month is still being closed in 1C, so the last
month in the fact is always the previous month. All four entry points cut at `vPLEnd`:
register pass, both journal passes, sales-injection staging.

## Assembly (four passes + allocation)

1. **Static** — articles matched in the Google Sheet with weight 1: whole amount to one
   direction via the static direction map (`MapНаправлениеСтатично`, key = trimmed
   article|structural-unit).
2. **Dynamic** — sheet value `'დინამიურად'` or key not found at all: row exploded into ≤3 rows
   by monthly COGS shares (`ДолиСебестоимости`: month × direction share of
   `[თვითღირებულება (გაყიდვები)]`, commercial directions only, same exclusions as
   `შიდა_და_არაძირითადები_ფილტრი`). Months with no shares fall back to the literal
   `'მიმართულების გარეშე'`.
3. **Sales injection (revenue + COGS)** — register/journal rows on the directions'
   revenue/COGS accounts are excluded (per account|registrar pairs that actually occur in
   the sales fact) and replaced by rows built from the sales fact, direction per document;
   internal/non-core/direction-less sales fall back to `'ლოგისტიკა'`.
4. **Journal side** (within 1–2 above): Управленческий ledger rows not covered by the
   register, via anti-join on registrar + the three filter branches from pl.txt
   (income/expense types on Операция; account-group codes 6–9 on ВводНачальныхОстатков;
   loan-interest codes 6–9 on ПриходнаяНакладная); credit side enters with flipped sign.

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
