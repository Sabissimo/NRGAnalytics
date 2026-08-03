# P&L by direction — design record (SD 0206)

Status: live since 2026-07-24; fixed fractional splits + `[ანგარიშის კოდი (P&L)]` added
2026-07-28 (`330d2ce`); **retail split into 3 stores + single-wave allocation DEPLOYED and
verified 2026-07-31** (`31ef5f3`; same day: displayed departments blanked outside retail,
`5065640`, and `[მიმართულება]` made a sort-ranked dual in `SD 0301`, `63f70b5`). The old
`საცალო` sheet column has been deleted — the *Deployment order* section below is historical.
**Match-key departments normalised 2026-08-03** — the sheet was re-authored with mapped
(normalised) department names, so the key, the `საწყისი` field and the display now all carry the
normalised name; see *Name matching*. **Same day, all deployed and user-verified working**:
`vPLEnd` hides the previous month until the 6th; the **budget** went live (see *Budget*);
deletion-marked articles excluded from rank/hierarchy/budget leaf map (extraction re-run done).
Script: `SD 0206. Reg. PL Directions 24.qvs` (daily/24 only).
Source 1C analyst query the register+journal logic reimplements: [pl.txt](pl.txt).
Extraction queries: `_ElvareAnalytics.txt` (ДоходыИРасходы register, ВидыСчетовPL catalog
incl. Порядок, ПодразделенияЗатратДоходовСчетов, НаправленияДеятельности, ВидСчетаPL column
on the management chart of accounts).

## Fact

`РегистрНакопленияДоходыИРасходы` — standalone fact keyed
`orgGUID | 'PL' | date | 0 | direction` (`[ორგანიზაცია_კონტრაგენტი_პერიოდი_ნაშთია]`,
contractor segment is the literal `'PL'`). Grain: org × day × bucket (direction + department:
store name inside საცალო, empty elsewhere) × article × account.
Measures: `[შემოსავალი (P&L)]`, `[ხარჯი (P&L)]`, `[თანხა (P&L)]` (= revenue − expense).
Audit attributes: `[ანგარიშის დასახელება (P&L)]` + `[ანგარიშის კოდი (P&L)]` (empty code = GUID
not in the chart of accounts), `[მუხლი (P&L)]` (**`Null`** = account has no ВидСчетаPL — test with
`IsNull()`, not `Len(Trim(…)) = 0`; the match key still uses `''` there so the key does not change),
`[დამატჩებულია (P&L)]` (`'არა'` = key absent from the sheet), `[წილები დაბალანსებულია (P&L)]`
(`'არა'` = fractional weights don't total 100%), and
`[სტრუქტურული ერთეული (P&L, საწყისი)]` (the raw department — what the sheet must contain).
Those separate the distinct "unmatched" causes, which otherwise look identical.
Its bridge block in `SD 0301` is deliberately UNguarded — it re-scans the persisted fact on
every partial reload and rebuilds identical keys, so fact-side changes need no bridge edits
as long as the key recipe is preserved.

**Data window**: lower bound
`vPLStart = RangeMax(YearStart(YearStart(vNow)-1), MakeDate(2026,1,1))` — current + previous year,
but never earlier than 2026. Both conditions stay: 2026-01-01 in 2026, 2027-01-01 in 2028, so the
window never exceeds two years. Upper bound `vPLEnd`, exclusive — since 2026-08-03:
`MonthStart(reload date)` from the **6th** of the month onward, `MonthStart` of the *previous*
month on days 1–5. The current month is still being closed in 1C, and the previous month's
closing itself runs into the first days of the new month, so the previous month appears in the
fact only from the 6th; before that the last month is two months back.
All four entry points cut at both bounds: register pass, both journal passes, and the
sales-injection staging (which previously had no lower bound at all).

Same formula as the calendar's `[Year SD (ბოლო 2 წელი, 2026+)]`, so the filter and the data window
agree by construction.

**Budget rows are exempt from the window** — the budget (see *Budget* section below) deliberately
covers future months of the current year; neither `vPLStart` nor `vPLEnd` applies to it.

`vPLStart` is deliberately a **separate variable** from `vPLDeptFrom` (the department cut-off).
Same date today, expected to diverge — do not collapse them.

The COGS-share table derives from `ПродажиДляПЛ`, which carries the same window — so shares
exist for exactly the months the fact can reference.

## Assembly (single-wave allocation into final buckets, 2026-07-31)

Allocation targets are **buckets** = (direction, department): (დისტრიბუცია, ''),
(კორპორატიული, ''), (ლოგისტიკა, ''), (ადმინისტრაცია, ''), and the 3 retail stores
(საცალო, store name) — the store list is `SET vPLRetailStores` at the top of the script.
The sheet's 7 target columns map onto these buckets (a store column = საცალო + that store as
department); the two-layer "direction first, then departments within it by COGS" composition is
**gone**. Non-store retail departments receive no allocated costs at all — only their own
injected sales/COGS.

The three sheet-driven parts read the same staging (`ПЛСтейджинг2`), guarded by key-marker maps
(`MapКлючФиксПЛ` / `MapКлючДинамПЛ` / `MapКлючМатчПЛ`). A **mixed row** (numbers +
`დინამიურად`) deliberately flows through BOTH (a) and (b) — the shares are complementary and
sum to 1:

1. **(a) Fixed part** — every numeric cell becomes one row per its bucket, amount ×
   `[_ფიქს წილი (P&L)]` (`ФиксДолиПЛ`, joined on the match key). No month/COGS dependency —
   a 100% cell is just the single-cell case. Weight semantics: absolute on mixed rows with
   sum < 100%, normalized by the row's own sum otherwise.
2. **(b) Dynamic part** — `დინამიურად`-marked buckets only (`ДинамНаправленияПЛ` keeps WHICH
   column held the mark — the old marker map discarded that): amount × remainder
   (`MapДинамОстатокПЛ`: 1 − numeric sum; 1 on number-free rows) × the bucket's monthly COGS
   share renormalized over the marked subset (`ДинамДолиНормПЛ`, joined on key + month).
   A month where no marked bucket has a share stays whole on `'მიმართულების გარეშე'`.
3. **(c) Unmatched key** — no sheet row at all: exploded over the month's FULL 5-bucket basis
   (`ДолиСебестоимости`), flagged `[დამატჩებულია (P&L)] = 'არა'`; a month with no basis stays
   whole on `'მიმართულების გარეშე'`.
4. **Sales injection (revenue + COGS)** — unchanged mechanics: register/journal rows on the
   directions' revenue/COGS accounts are excluded (per account|registrar pairs that actually
   occur in the sales fact) and replaced by rows built from the sales fact, direction per
   document; internal/non-core/direction-less sales fall back to `'ლოგისტიკა'`. Their real
   department is **displayed only inside საცალო** (user decision 2026-07-31) — on any other
   direction the display department is empty like on allocated rows; the raw field keeps the
   real department always, and the injection grain is unchanged (still grouped by the real
   department GUID).
5. **Journal side** (within a–c above): Управленческий ledger rows not covered by the
   register, via anti-join on registrar + the three filter branches from pl.txt
   (income/expense types on Операция; account-group codes 6–9 on ВводНачальныхОстатков;
   loan-interest codes 6–9 on ПриходнаяНакладная); credit side enters with flipped sign.

**Department on allocated rows comes from the bucket**: the store name on store buckets,
**empty** everywhere else (დისტრიბუცია/კორპორატიული/ლოგისტიკა/ადმინისტრაცია and
`'მიმართულების გარეშე'`) — departments outside retail are deliberately not tracked.
`[სტრუქტურული ერთეული (P&L, საწყისი)]` still holds where the cost was incurred (since 2026-08-03
under its normalised name).

**COGS basis** (`ДолиСебестоимости`): month × bucket share of `[თვითღირებულება (გაყიდვები)]`,
same exclusions as `შიდა_და_არაძითადები_ფილტრი`. დისტრიბუცია/კორპორატიული are aggregated to
the direction level (department ''); საცალო is restricted to the 3 stores by **normalised**
department name. ⚠ Retail COGS on non-store departments is **excluded from the basis
entirely** — direction totals shift vs the pre-2026-07-31 scheme by design (retail's dynamic
weight now comes from the stores only).

## Internal / non-core filtering (2026-07-28)

Sales sheets filter with `[Internal (კონტრაგენტები)]={'არა'}, [არ არის ძირითადი (ნომენკლატურა)]={'არა'}`.
The P&L fact now carries its own equivalents so P&L measures can be filtered the same way
instead of the exclusion being hardcoded:

| Row origin | `[Internal (P&L)]` | `[არ არის ძირითადი (P&L)]` |
|---|---|---|
| sales injection (revenue + COGS) | real value from the sales fact; grain extended by both | real value from the sales fact |
| register / journal (fixed part, dynamic part, unmatched) | account-derived — see below (was `'არა'` until 2026-07-29) | `'არა'` — such rows are never non-core, so the standard filter keeps them |
| allocation-variant copies | carried through from the source row | carried through from the source row |

⚠ **The names deliberately differ from the sales-side fields.** `[Internal (კონტრაგენტები)]`
lives on `BridgeTableOrgDate` (`SD 0301`) and `[არ არის ძირითადი (ნომენკლატურა)]` on the items
dimension (`SD 0102`). Reusing either name on the P&L fact would give it a second shared field
with a table it already associates to → synthetic key / circular reference (the single-
attachment-point rule in CLAUDE.md). Hence `(P&L)`-suffixed twins, per the per-fact suffix
convention. Consequence: P&L measures need their **own** modifier, e.g.
`{<[Internal (P&L)]={'არა'}, [არ არის ძირითადი (P&L)]={'არა'}>}` — the sales variable
`შიდა_და_არაძითადები_ფილტრი` will not reach P&L rows.

**The COGS-share basis stays script-filtered** (`ДолиСебестоимостиPre`, internal + non-core
excluded). Shares are a script-time aggregate that must sum to 1 so every allocated row is
distributed in full; making them respond to selections would change the P&L expense total
whenever a contractor or item filter moved. The basis already matches the filter users apply,
so a filtered P&L and its allocation weights agree.

Note the direction rule sends internal / non-core / direction-less sales to `'ლოგისტიკა'`, so
filtering both flags to `'არა'` shrinks ლოგისტიკა — that is the intended parity with sales,
not a bug.

### `[Internal EEE (P&L)]` (2026-07-29)

A **second, narrower** internal flag, populated the same way per row origin (real value on
sales-injected rows, `'არა'` on register/journal/fractional, carried through allocation copies)
but resolved differently:

- the broad flag comes from the contractor's 1C **additional attribute**;
- `[Internal EEE (P&L)]` is `'კი'` only when the contractor's 1C **code** is in an explicit
  list — the group's own companies appearing as counterparties.

The list lives in one place, `SET vPLInternalEEE` at the top of `SD 0206`; a fourth company is a
one-line edit. It needs `MapСправочникКонтрагентыКод` (`SD 0002`) — nothing mapped the contractor
code before, though the extraction has always pulled it (`_SD.txt:108`).

A contractor that is internal by the broad flag but **not** in the code list is `'არა'` on
sales-injected rows — on that side the two flags are independent, not nested.

**Non-sales rows resolve both flags from the account (2026-07-29).** Register and journal rows
have no counterparty, so neither flag can key off a contractor. Both are instead `'კი'` when the
posting's account — **or any of its ancestors** — has a code in `SET vPLInternalEEEAccounts`:

- `Hierarchy()` over the chart of accounts builds each account's root-to-node path of *codes*;
- the path is exploded one row per ancestor and checked with `Exists` against the code list;
- so a posting on a child of `8110/19` is flagged, while `8110` itself is not.

The parent column on that catalog is `[ექვემდებარება ანგარიშს]` (same one `Accounting 0101`
uses) — not the `Родитель`/`ჯგუფში` names other catalogs use.

Two consequences to keep in mind:

- **On non-sales rows the two flags are identical**, sharing one map and one list. They diverge
  only on sales-injected rows. If the broad flag should ever cover more accounts than the EEE
  list, it needs its own list and a second map.
- **The two sides are asymmetric by construction** — sales keyed on contractor, non-sales on
  account. A transaction with an EEE company can therefore be flagged on the sales side and not
  on the register side if its account is absent from the list.

⚠ Silent failure: a listed code that does not exist in the chart of accounts, or differs in
padding (`7450/09` vs `7450/9`), matches nothing and raises no error. Verify by listing
`[ანგარიშის კოდი (P&L)]` where the flag is `'კი'` and confirming every listed code appears.

⚠ Both injection `Group By` lists carry the field. They aggregate, so adding a flag to the select
list without adding it to the grouping fails the reload outright — the same trap applies to any
future per-row attribute on the sales injection.

⚠ Failure mode if the QVD column name or the code format is wrong: `ApplyMap` returns empty and
every row silently reads `'არა'`. Visible as "no `'კი'` bucket at all", not as an error.

## Departments (2026-07-29)

The department is half the matching key, so how it is resolved decides what matches.

### Name matching — shared with the Statement app

`SD 0004` builds `MapСоответствиеНаименованийПодразделенийПЛ` (NAME → NAME) from
`РегистрСведений.СоответствияЗначений`, filtered to type `'EEE განყოფილების ჩანაცვლება'` —
the same register and the same filter the Statement app uses (`Statement 0002`). Applied as
`ApplyMap(map, name, name)`, so an unmatched name passes through unchanged.

⚠ The type filter is not optional: without it every matching type in that register leaks into the
department map. It was once commented out in Statement and had to be re-enabled (`786ad1e`).

⚠ **The old "key raw / display normalised" asymmetry was INVERTED on 2026-08-03.** The Google
Sheet's `[სტრუქტურული ერთეული]` column was re-authored with **normalised** names, so
`ПЛСтейджинг2` now resolves the final unit GUID to its normalised name **once** — a middle
preceding load producing the helper `[_ერთეული სახელი (P&L)]` — and uses it in all three places:
`[_MatchKey (P&L)]`, the display field, and `[სტრუქტურული ერთეული (P&L, საწყისი)]`. The two
sales-injection `საწყისი` sites normalise the same way. The helper never reaches the fact (the
three branch outputs list fields explicitly).

Consequences:

- a **raw** (pre-mapping) name in the sheet is now the mismatch case — that row silently stops
  matching and its fact rows fall through to the dynamic COGS split, with `დამატჩებულია = 'არა'`
  as the only visible symptom;
- names CAN now be copied out of the P&L pivot (or the unmatched report) straight into the sheet;
- two raw departments remapped onto one canonical name merge into ONE match key — the sheet needs
  a single row for them.

One-time invariant break at this deploy: `Sum([თანხა (P&L)])` per `[_MatchKey (P&L)]` and the
`[დამატჩებულია (P&L)]='არა'` list are unchanged **only for departments the mapping register does
not remap**; remapped keys rename/merge once, and their rows — which had been falling through as
unmatched since the sheet was re-authored — match their sheet rows again.

### Sales-sourced rows

Previously `Null()`. Now resolved in the `ПродажиДляПЛ` staging by the same rule 1C uses in
`РасшифровкаБухгалтерии`:

```
Период >= 2026-01-01
  ? (order's СтруктурнаяЕдиницаПродажи name = 'ELV_საპროექტო გაყიდვები'
       ? that unit
       : document's Подразделение)
  : empty
```

Cut-off and literal live in `vPLDeptFrom` / `vPLProjectSalesUnit` at the top of `SD 0206`.

### The 2026 cut-off applies to every source, but only to the displayed field

`[სტრუქტურული ერთეული (P&L)]` is empty before 2026-01-01 for **all** sources — register, journal
and sales alike. Since 2026-07-31 sales-injected rows additionally blank it outside საცალო
(the direction condition sits in the same `if()` as the year gate, in both injection blocks).

`[_MatchKey (P&L)]` is **not** gated: it carries the (since 2026-08-03 normalised) department
regardless of year. That is deliberate — gating the key would change which sheet row a pre-2026
line matches and therefore move money between directions. The cut-off is a presentation rule,
not an allocation rule.

The gate sits at the three display-field sites only (`ПЛСтейджинг2` and the two injection
blocks); normalisation itself is ungated and nothing upstream is year-dependent, so the
normalised value exists for every year on every source. Bucket departments written by allocation
are ungated (see *Department on allocated rows*).

### Two department fields on the fact

| Field | Normalised? | Year-gated? | Use |
|---|---|---|---|
| `[სტრუქტურული ერთეული (P&L)]` | yes | yes — blank before 2026 | display; agrees with Statement |
| `[სტრუქტურული ერთეული (P&L, საწყისი)]` | **yes — since 2026-08-03** | **no** | what the Google Sheet needs |

Since 2026-08-03 both fields are normalised; `საწყისი` differs only in being ungated and in not
being overwritten by the allocation bucket (the name is historical — it meant "raw" while the key
was raw). Pair it with `[მუხლი (P&L)]` and you have exactly the `article|unit` the sheet expects —
which is what an "unmatched departments and articles" sheet should show.

⚠ `'ELV_საპროექტო გაყიდვები'` is a name literal — renaming that unit in 1C silently disables the
branch.

The new staging field is in **both** injection `Group By` lists; they aggregate, so a select-list
addition alone fails the reload.

### Register/journal rows — unchanged

`ApplyMap('MapПодразделенияЗатратДоходовСчетовПЛ', org|account, [_ერთეული (P&L)])` in
`ПЛСтейджинг2` keeps the account register as the **override** and the row's own department as the fallback, so an
empty row department already picks up the account register. Deliberately not inverted.

### Extraction dependency

None of this works until `_ElvareAnalytics.txt` is re-extracted. It gained
`РасходнаяНакладная.Подразделение`, `РасходнаяНакладная.Заказ`,
`ЗаказПокупателя.СтруктурнаяЕдиницаПродажи`, and two new queries
(`РегистрСведений.СоответствияЗначений`, `Перечисление.ТипыСоответствия`).

Note the order reference on the invoice is `Заказ` (→ `[შეკვეთა]`), **not** `ЗаказПокупателя` —
that is the name of the order document itself, not of the attribute pointing at it.

### Verification invariant (historical — the 2026-07-29 change; superseded 2026-08-03)

**Superseded 2026-08-03:** the key is now normalised by design; the one-time invariant break and
the current checks live under *Name matching* above. For the 2026-07-29 change itself the rule
was: `[_MatchKey (P&L)]` is **byte-identical** before and after, so:

- `Sum([თანხა (P&L)])` per direction must be **unchanged**;
- the `[დამატჩებულია (P&L)] = 'არა'` list must be **unchanged**.

Anything that moves means the key was normalised or year-gated somewhere it should not have been.
The only visible differences should be department *labels*: normalised on 2026+ rows of every
source, blank on everything before 2026, and present on 2026+ sales rows where there were
previously blanks.

Column names, confirmed 2026-07-29:

| QVD column | 1C attribute | Document |
|---|---|---|
| `[განყოფილება]` | `Подразделение` | `РасходнаяНакладная` |
| `[შეკვეთა]` | `Заказ` | `РасходнаяНакладная` |
| `[განყოფილება]` | `СтруктурнаяЕдиницаПродажи` | `ЗаказПокупателя` |

Note the first and third share the column name `[განყოფილება]` while being different attributes on
different documents. They live in separate QVDs so there is no collision, but they are easy to
confuse when editing.

⚠ Still assumed: that `ДокументРасходнаяНакладная` is month-partitioned in the ELV batch (loaded as
`-*.qvd`). That one fails loudly if wrong. A wrong *column* name would instead make `ApplyMap`
return empty **with no error** — verify by finding a populated department, not by the absence of a
failure.

## Matching sheet semantics (2026-07-31)

Google Sheet, PL Directions tab. Columns: `მუხლი` | `სტრუქტურული ერთეული` | `სულ` (control sum,
**not loaded**) | `ELV_ბათუმის ფილიალი` | `ELV_აგლაძის ფილიალი` | `ELV_ალექსეევკის ფილიალი` |
`დისტრიბუცია` | `კორპორატიული` | `ლოგისტიკა` | `ადმინისტრაცია`.
`[მუხლი]` is the account's **ВидСчетаPL name**, not the account name.
`[სტრუქტურული ერთეული]` holds **normalised** department names since 2026-08-03 (the sheet was
re-authored; the match key is normalised to agree) — a raw pre-mapping name in this column no
longer matches anything.

⚠ The 3 store column headers must byte-match the stores' **normalised** department names (they
are matched against the COGS basis and written into `[სტრუქტურული ერთეული (P&L)]` verbatim).
A mismatched header makes that store's COGS share silently 0 — the store column then never
receives dynamic money and its static/fixed money carries a department name that exists nowhere
else. The same three names live in `SET vPLRetailStores` in the script; change both together.

Cell semantics per row (key = `მუხლი|ერთეული`):

| Row content | Result |
|---|---|
| numbers only | each cell's bucket gets weight ÷ row sum (60/40 works; a lone `50%` gets 100%); sum ≠ 100% flagged `[წილები დაბალანსებულია (P&L)] = 'არა'` |
| `დინამიურად` only | whole amount split by monthly COGS shares **among the marked columns only** (renormalized over the marked subset) |
| numbers + `დინამიურად` (mixed) | numbers are **absolute** percentages; the remainder (1 − sum) is split by COGS among the marked columns. Sum ≥ 100% → numbers normalized, dynamic part 0, flagged `'არა'` |
| no row for the key | split over the month's full 5-bucket basis, flagged `[დამატჩებულია (P&L)] = 'არა'` |

- Percent-formatted cells arrive as numbers (`100%` → 1) — confirmed in production.
- A month where the marked (or, for unmatched keys, any) buckets have no COGS stays whole on
  `'მიმართულების გარეშე'` — it is **not** re-routed to ლოგისტიკა; that fallback exists only in
  the sales-injection direction rule.
- `დინამიურად` under ლოგისტიკა/ადმინისტრაცია marks nothing: those buckets never exist in the
  COGS basis, so the mark contributes no split (if it is the row's only mark, the whole dynamic
  part lands on `'მიმართულების გარეშე'`).
- `[სულ]` is decorative — it is never loaded, so a row that reads 100% across in the spreadsheet
  is no guarantee Qlik honoured it. The flag field is the real check.

Behaviour changes vs the pre-2026-07-31 scheme, worth knowing when editing the sheet:

- a **lone numeric weight ≠ 1** (e.g. a single `60%`) used to fall through to the dynamic branch
  silently; it now allocates 100% to its column, flagged `'არა'`;
- a **mixed row** used to ignore its numbers and go fully dynamic; the numbers now count;
- `1` in two columns still splits evenly (2-weight row), flagged unbalanced (sum = 2).

⚠ **Routing.** Branch guards are the key-marker maps built from `КлючиПЛ`: `MapКлючФиксПЛ`
(has numeric cells), `MapКлючДинамПЛ` (has marks AND a positive remainder), `MapКлючМатчПЛ`
(in the sheet at all — the unmatched branch requires `= 0`). Fixed and dynamic parts of a mixed
key overlap **by design** (complementary shares); everything else must stay mutually exclusive —
widening one guard double counts silently.

⚠ Fractions cannot be done through a mapping table: `ApplyMap` returns one value per key. Hence
the joined weight tables (`ФиксДолиПЛ` on the key; `ДинамДолиНормПЛ` on key + month).

**Deletion-marked articles are filtered since 2026-08-03** (reverses the 2026-07-28 decision —
the catalog turned out to hold deletion-marked duplicates, e.g. `წმინდა მოგება M`-style
leftovers). The extraction now exports `ПометкаУдаления`; `SD 0206` excludes flagged elements
from the **rank** (`МухлиСортПЛ`), the **hierarchy dimension** (`МухлиИерархияПЛ`) and the
**budget name→GUID leaf map** (`MapМухлиИдЛистПЛ` — a deleted duplicate can never capture a
name). The GUID→name map (`MapСправочникВидыСчетовPLПЛ`) is deliberately still UNfiltered, so a
historical posting on a deleted article keeps its article name — it just has no hierarchy row
(levels null, rank falls to the 9999999 default) instead of losing the name entirely.
⚠ Ordering: the script references the QVD column `[ПометкаУдаления]` — re-sync the ELV
zaprosqlik project and re-run the daily extraction BEFORE deploying the script, or the full
reload fails. ⚠ Caveat: if a deletion-marked element is the PARENT of live elements, filtering
it re-roots those children in the hierarchy — 1C-side cleanup (`Замена ссылок`) remains the
real fix for duplicates.

## Department on allocated rows = the bucket (2026-07-31; replaces the 2026-07-30 two-layer scheme)

The 2026-07-30 scheme ("direction first, then departments within it by COGS", two share
flavours, `ДолиДепСтатичноПЛ`/`ДолиДепПоНаправлениюПЛ`) lived for one day and is **gone**.
Departments outside retail are not tracked at all, so allocation lands directly in the final
buckets and the department is simply the bucket's:

- store buckets → the store name (which equals the sheet column header, normalised);
- every other direction and `'მიმართულების გარეშე'` → **empty** (`''`);
- sales-injected rows show their real department **only when their direction is საცალო**
  (user decision 2026-07-31: outside retail the display department is empty on every row,
  injected sales included) — so non-store retail departments still appear inside საცალო,
  carrying their own sales/COGS and nothing else, while ლოგისტიკა-routed internal/non-core
  sales display no department;
- allocation-variant copies take the bucket's department too (empty on
  დისტრიბუცია/კორპორატიული); the guard there is on the **direction** being joined, not on the
  department being non-empty — otherwise the empty დისტრ/კორპ bucket department would be
  "corrected" back to the source row's department. A no-share month keeps the source direction
  and department (share 1), so totals hold.

The basis is derived from `ПродажиДляПЛ` rather than the sales fact directly, so the department
is defined exactly once and cannot disagree with what the injected sales rows carry.

⚠ `ПродажиДляПЛ`'s `[_ერთეული (P&L გაყიდვები)]` is a **GUID**, not a name — the name only appears
inside the `if()` comparison against the project-sales unit. The share table resolves it to a
**normalised name** immediately, because allocation writes it straight into
`[სტრუქტურული ერთეული (P&L)]`, which holds names everywhere else. Grouping is on the normalised
name too, so two departments remapped onto one count as one for allocation purposes.

⚠ The bucket department is written **ungated** (no 2026 cut-off) — same as the 2026-07-30
behaviour for allocated departments. The cut-off still applies where it always did: the
staging/injection display field for the rows' *own* departments.

**Row count shrinks** vs the 2026-07-30 scheme: the fixed part no longer fans out across a
direction's departments (one row per weighted cell, month-independent), dynamic fans over ≤5
buckets. Note the new fact size on the first reload.

⚠ `[სტრუქტურული ერთეული (P&L, საწყისი)]` is deliberately **not** rewritten — it stays the department
where the cost was incurred (normalised since 2026-08-03) and what the sheet is keyed on. So
"incurred" and "attributed" are two separate visible facts, and the unmatched report keeps working.

⚠ Matching happens **before** allocation, so an allocated row can carry an `(article, department)`
pair that the sheet maps to a *different* direction. Nothing re-matches, so it is not circular, but
anyone reconciling against the sheet must use the `საწყისი` field, not the display one.

## Deployment order (historical — executed 2026-07-31; keep the pattern for future column changes)

The script SELECTs the sheet columns **by name** — a reload against a sheet lacking a listed
column fails outright (and `sync-to-qlik.yml` deploys every push to main immediately, with a
nightly full reload at 00:00 UTC). Any future column change must follow the same sequence:

1. ADD the new columns in the Google Sheet first, keeping the old ones untouched — the deployed
   script only reads columns it names, so every intermediate nightly reload stays green.
2. Push the script change; the next full reload switches over.
3. Verify, then delete the obsolete columns whenever convenient (done for `საცალო` 2026-07-31).

## Allocation variants (გადანაწილების ვარიანტები)

The report supports 4 views: (1) all 5 directions as-is, (2) ლოგისტიკა reallocated onto the
5-bucket COGS basis (დისტრიბუცია, კორპორატიული, and the 3 საცალო stores) by monthly shares,
(3) ადმინისტრაცია reallocated, (4) both.

Implementation — row groups + link table, all inside SD 0206:

- Every fact row carries `[_PL ვარიანტის ჯგუფი]` ∈ COMMON / LOG_AS_IS / ADM_AS_IS /
  LOG_ALLOC / ADM_ALLOC (Latin values on purpose).
- Allocated copies of overhead rows (everything sitting on ლოგისტიკა/ადმინისტრაცია, incl.
  sales-injection fallback rows) are concatenated into the fact: amounts × monthly COGS
  share, direction + composite key rebuilt to the target bucket's direction, the department
  set to the bucket's (store name / empty — see *Department on allocated rows*), original
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

## Budget (გეგმა) — implemented 2026-08-03

The budget flows through the SAME machinery as actuals, with the budget's own COGS as every
basis. Block sits at the end of `SD 0206`, after the actuals variant wave, before the variant
link table. Supersedes the parked 2026-07-29 design (`pl-budget-parked.md` kept as history).

**Source**: budget workbook (`1VRebtvzdH…`, same one SD 0201/0205 read), tab gid `139208043`.
Columns: `მუხლი` | `სტრუქტურული ერთეული` | `მიმართულება` | month columns (header = first day
of month, `YYYY-MM-DD`). Loaded `LOAD *` + `Crosstable(…, 3)` — a new month column needs no
script change, but the three fixed columns must be FIRST and in this order. ⚠ Deployment gate:
the `მიმართულება` column must exist in the tab BEFORE the script is pushed — the staging load
references it by name and the full reload fails without it.

**Semantics**:

- Amounts arrive in report sign (income +, costs −) and land verbatim in `[ბიუჯეტი (P&L)]`;
  `შემოსავალი/ხარჯი/თანხა` stay null on budget rows → no existing measure changes. Empty /
  non-numeric / zero cells are skipped, so the tab can be filled gradually.
- Pseudo-org `'ბიუჯეტი'` (holding level — selecting a real company hides budget, honest),
  contractor `'PL'` (existing SA grant covers it, ADMIN-only; bridge picks the group by
  contractor → `SD 0301`/`SD 0101` untouched), `[წყარო (P&L)]='ბიუჯეტი'`.
- Every row allocates like a register/journal row: same `[_MatchKey (P&L)]`
  (`Trim(მუხლი)|unit`, unit passed through the normalisation map — pass-through since the tab
  already holds normalised names), same marker maps, same `ФиксДолиПЛ` weights and remainder
  (`ФиксДолиПЛ`/`ДинамНаправленияПЛ` now drop inside the budget block, not after the actuals
  branches). Article name → GUID via the leaf-only `MapМухлиИдЛистПЛ` (`Родитель`-based):
  a group/total row that sneaks into the tab cannot resolve and lands unmatched-flagged —
  money is kept, never silently dropped.
- **Except the two sales articles** (`SET vPLBudgetSalesArticles`: შემოსავალი რეალიზაციიდან,
  რეალიზებული პროდუქციის თვითირებულება — the latter spelled without ღ, as in 1C), and only
  their rows **with a filled `მიმართულება`** (legal values `საცალო`/`დისტრიბუცია`/
  `კორპორატიული`): those are the plan's sales injection — they bypass matching and take the
  column's direction verbatim. Display department inside `საცალო` only.
  **A sales-article row with an EMPTY direction is NOT sales data** (user rule 2026-08-03):
  it flows through the matching sheet like any register/journal row and stays OUT of the COGS
  basis — the actuals parity being that such a posting arrives from the register/journal and
  gets matched, not injected. (A stray `მიმართულების გარეშე` in the column is treated as
  empty.) There is no `ლოგისტიკა` fallback in the plan's sales stream.
- **Basis** `ДолиСебестоимостиБюджет`: month × 5 commercial buckets from the COGS article
  (`SET vPLBudgetCogsArticle`) via `Fabs()` (sign-agnostic). Same bucket rules as actuals:
  დისტრიბუცია/კორპორატიული at direction level, საცალო restricted to `vPLRetailStores` —
  non-ELV-store retail COGS (e.g. ELE stores) is excluded from the basis while its amounts
  still land in საცალო. Feeds `ДинамДолиНормБюджет` (renormalized over marked columns, from
  the still-alive `ДинамНаправленияПЛ`) and `ДолиДляАллокацииБюджет` (the budget's own LOG/ADM
  variant wave). No-basis months: dynamic/unmatched amounts stay on `მიმართულების გარეშე`,
  variant copies stay on the source direction at share 1 — totals conserved in every variant.
- The ACTUALS variant wave now carries `and not [წყარო (P&L)] = 'ბიუჯეტი'` — belt-and-braces
  (the budget block also runs after it); without a separate wave the plan would silently be
  spread by actual shares (the parked doc's #1 failure mode).

**`[მიმართულება (P&L, საწყისი)]`** — new fact field (2026-08-03, same commit): the raw,
pre-rule direction, mirror of the department `საწყისი` field. Populated on actuals
sales-injected rows (raw sales-fact direction; both injection `Group By` lists extended → row
count may grow, totals unchanged) and on budget sales rows (the sheet column verbatim); null
on register/journal and allocated-expense rows; carried through variant copies on both waves.

**Measures (app-side contract)**: `Sum({<[გადანაწილების ვარიანტი]={'$(vPLVariant)'}>}
[ბიუჯეტი (P&L)])` — the variant modifier is mandatory exactly like for actuals. Budget rows
carry `'არა'` in Internal/EEE/non-core so the standard filters keep them. Compare at month
granularity or coarser (budget sits on the 1st); selecting a real organization hides budget.

## Article ordering (1C parity)

1C reports sort articles by the catalog's Порядок (`რიგითობა`) at every hierarchy level.
Reproduced by baking the order into the values, not per-chart sort expressions:

- A second `Hierarchy()` pass builds a per-node path of 10-digit zero-padded რიგითობა
  values; ordering by that path yields a global depth-first rank (`МухлиРангПЛ` → mapping).
- `[მუხლი (იერარქია)]` (and therefore all generated level fields) and the fact-side
  `[მუხლი (P&L)]` (via the article-name map) are `dual(name, rank)`, the intent being that plain
  Auto/numeric sorting reproduces 1C order in every object. MatchKey sites keep `Trim()` so
  Google-Sheet matching stays byte-identical.

⚠ **The ordering claim above does not hold — open issue, 2026-07-30.** Ranks read out of the live
app are not depth-first: the level-1 nodes rank as a block (3, 5, 11) and every deeper node follows
much later (52–105), so children do not sit under their parents. Sorting on the dual therefore
looks right at the top level and wrong as soon as the hierarchy is expanded.

Likely cause: a root node's `[_მუხლი sort (P&L)]` is a single `Num()` value — a numeric dual —
while a deeper node's is a concatenated string, and Qlik sorts numerics before text. So the
`Order By` in `МухлиРангПЛ` splits into "all roots, then everything else alphabetically" instead of
one depth-first walk.

Not yet fixed. If it matters, the fix is in `МухлиРангПЛ` — force the path to text for every node
(e.g. build the root's path as a string too) so one comparison rule applies throughout. Building a
form from these ranks is the wrong approach; reconstruct the tree from `[მუხლი path (P&L)]` instead,
which is what the budget-sheet generator ended up doing.
- `[_მუხლი sort (P&L)]` (the padded path) stays on the hierarchy table for verification.
- Caveat: two articles with the same name show as two identical-looking values (different
  ranks). Diagnosing that symptom — two chart rows with the same article text:
  - `=Num([მუხლი (იერარქია)1])` returns the two ranks. **`რიგითობა` is not the rank**:
    `რიგითობა` orders siblings within one parent, the rank is the node's global depth-first
    position, so `რიგითობა`=6 appearing as rank 11 is normal.
  - The rank comes only from `MapМухлиРангПЛ`, keyed on `Ссылка`. A mapping table cannot
    return two values for one key, so **two different numbers can only mean two GUIDs** — no
    other explanation needs checking.
  - **Check the extraction date first.** In the one real occurrence (2026-07-28) the QVD was
    simply stale and a re-extraction resolved it. Rule out that before hunting 1C duplicates.
  - If it is a genuine 1C duplicate: fix with `Замена ссылок` in 1C, not by filtering the
    catalog — dropping the element strands postings that reference its GUID, and they lose
    their article name entirely. A Qlik-side alternative is ranking by trimmed name so
    duplicates share a rank and merge, at the cost of merging same-named distinct articles.
  - `:79` builds the hierarchy node name **untrimmed** while `:58` trims it, so names
    differing only by whitespace look identical here but not there.

## Accounting-style display (app side)

Negative measures red with parentheses: number format `#,##0;(#,##0)` (inheritable via
master measure) + per-column text-color expression `=if(<measure> < 0, '#C00000')` (modern
pivot object).

## Verification checklist

1. Upload changed `.qvs`, full reload, close and REOPEN the app (reduction happens at open).
2. Data model viewer: no `$Syn`; variant link table connects to the fact only; variant field
   4 values, group field 5.
3. Totals invariant: `Sum({<[გადანაწილების ვარიანტი]={'<label>'}>}[თანხა (P&L)])` identical
   across all four labels, and (per label) unchanged vs the previous reload — allocation moves
   money between buckets, never creates or destroys it.
4. Per-key invariant: `Sum([თანხა (P&L)])` per `[_MatchKey (P&L)]` unchanged vs the previous
   reload; the `[დამატჩებულია (P&L)]='არა'` key list unchanged (unless sheet rows were
   added/removed). Direction totals MOVE by design (stores-only retail basis + re-authored
   sheet) — reconcile deliberately, don't treat as regression.
5. Store-name guard: each of the 3 store columns shows non-zero allocated amounts in months
   with sales. A store at 0 everywhere = header/name byte-mismatch (silent failure).
6. Purity: zero rows with `[მიმართულება (P&L)]='საცალო'`, `[წყარო (P&L)]<>'გაყიდვები'` and
   `[სტრუქტურული ერთეული (P&L)]` outside the 3 store names (check both 'საკუთარი' rows and
   the ALLOC variant copies). Non-store retail departments must carry only injected sales/COGS.
7. Mixed rows: per-key total = the full amount; each numeric column receives exactly its
   percentage; the remainder splits across the marked columns only.
8. Variant 2 → ლოგისტიკა ≈ 0 (residue only in no-COGS months); variant 3 → ადმინისტრაცია 0;
   variant 4 → both. Marker splits საკუთარი vs ლოგისტიკიდან/ადმინისტრაციიდან and the
   allocated part equals variant 1's overhead total.
9. Last month present in P&L = month before the reload date (from the 6th of the month);
   on days 1–5 it is the month before that.
10. Articles appear in 1C order with chart sorting on Auto.
11. Partial reload → allocated rows still in the bridge; direction + calendar still slice.
12. `[წილები დაბალანსებულია (P&L)]='არა'` lists exactly: number-only rows with sum ≠ 100% and
    mixed rows with sum ≥ 100%.
13. Fact row count: expected DOWN vs the 2026-07-30 scheme — note the new number.
