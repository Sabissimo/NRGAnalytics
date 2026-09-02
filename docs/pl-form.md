# P&L presentation form — design record (SD 0106)

Status: pushed 2026-09-02 (the sync uploads it; live after the next full reload). Both tabs
are filled (46 lines, Membership as a long list with five `*` fallback rows); the article
names are verified against the 1C catalog by the audit table on every full reload.

Script: `SD 0106. Cat. PL Form 24.qvs` (daily/24 only, included right after `SD 0105`).
Source sheet: the **Qlik Matching** workbook (`1khHxo_6tF2-fj0BWu77QLWC9ODRZOnw4DMteglpaYZc`,
the same one the PL Directions and Location tabs live in), tabs `Lines` (gid `356079956`) and
`Membership` (gid `1873343848`).

## Why

The P&L pivot was a 1C hierarchy (`МухлиИерархияПЛ`). The report finance wants is a fixed
form: raw articles, subtotals (ამონაგები, საოპერაციო მოგება, EBITDA, EBIT), margins as
ratios, and the same article feeding its own group total AND every higher total. A tree
cannot express that; a **link table** can. Nothing on the fact changes.

## Model

```
Fact ──[%lnk_მუხლი (P&L)]── PLFormLink ──[%lnk_სტრიქონი (P&L ფორმა)]── PLFormLines
                            (GUID, line, როლი, წონა)                    (dual label, type,
                                                                          format, style)
PLFormAudit — island (two fields, associates with nothing)
```

`%lnk_მუხლი (P&L)` is the same field the article hierarchy uses, so the fact, the hierarchy
and the link table all meet on one field — no synthetic key, no loop. The form table attaches
only to the link table.

`PLFormLink` roles:

| role | meaning | rows |
|---|---|---|
| `S` | member of a `sum` / `unmatched` line | one per (GUID, line) |
| `N` / `D` | numerator / denominator of a `ratio` line — copies of the referenced lines' `S` rows (fallback rows included) | |
| `X` | anchor: EVERY line × EVERY catalog GUID, weight 0 | lines × articles |

Plus `[დამატჩებულია (P&L ფორმა)]`: `'კი'` on rows that came from a Membership pair, `'არა'`
on **fallback** rows (see *Unmatched articles*). `X` rows carry `'კი'`.

## Unmatched articles — nothing is dropped, everything is marked

An article (any catalog GUID, groups included — a posting can sit on a group node) with no
`S` row from Membership is *unmatched*. Two sheet-driven mechanisms route its money into
the form, both producing `S` rows flagged `[დამატჩებულია (P&L ფორმა)] = 'არა'`:

1. **Membership rows with `მუხლი = *`** — the fallback targets. The live sheet has five:
   `* → სხვა არასაოპერაციო ხარჯი` (the visible child line), `* → არასაოპერაციო
   შემოსავალი/(ხარჯები) — სხვა`, `* → EBITDA`, `* → EBIT`, `* → წმინდა მოგება`, so an
   unmatched article lands in a visible line AND in every total below the operating line;
   totals stay complete. `*` rows accept the optional `წონა` too.
2. **A Lines row of type `unmatched`** (optional, not used today) — a form line that shows
   ONLY the unmatched articles. With `* → სხვა არასაოპერაციო ხარჯი` in place it is
   redundant; the "of which unmatched" measure below separates matched from unmatched inside
   that line.

A target named both ways counts once (targets are de-duplicated per line). If there are no
targets at all the audit says so loudly and unmatched money is invisible in the form.

Finding what to match: a table with dimension `[მუხლი (P&L)]` and measure
`Sum({<[როლი (P&L ფორმა)]={'S'}, [დამატჩებულია (P&L ფორმა)]={'არა'}, $(vPLFormSet)>} [თანხა (P&L)])`
(`vPLFormSet` = the shared modifier defined under *App-side contract*)
lists the unmatched articles with their amounts; the audit row
`ცნობარი: ფოთოლი Membership-ში არ არის (fallback)` lists them by name without amounts.
Per-line "of which unmatched": the same set expression on the form dimension.

**Why `X` exists.** `SD 0101` has section access. At app open Qlik deletes every row not
associated with the user's allowed values. A form line whose members have no fact rows
(spacers, an article with no postings in the window) has no chain to the allowed `'PL'`
group and would vanish for everyone, admins included. The `X` rows give every line a path
through every article, so a line survives as long as any article does. Side effect: clicking
a form line selects all articles — turn selection off on the form object.

**Consequence for measures: every measure MUST carry a role modifier.** A bare
`Sum([თანხა (P&L)])` on the form dimension shows the whole fact on every line (via `X`).

## Sheet

### Lines (gid 356079956)

| column | meaning |
|---|---|
| `რიგი` | unique number; key and sort order |
| `სტრიქონი` | label; Membership `ახალი მუხლი` values and ratio references match it **byte for byte** |
| `ტიპი` | `sum` / `ratio` / `spacer` / `unmatched` (Latin, lower-cased on load; other values ignored). `unmatched` = a sum line whose members are exactly the articles Membership does not cover |
| `მრიცხველი`, `მნიშვნელი` | ratio only: labels of two other lines |
| `ფორმატი` | `Num()` format string, e.g. `#,##0;(#,##0)` or `0.0%;(0.0%)` |
| `შეწევა` | indent level, baked into the dual label as non-breaking spaces |
| `მუქი`, `დახრილი`, `ფონის ფერი`, `დადებითი ტექსტის ფერი`, `უარყოფითი ტექსტის ფერი` | style hints for the app; the measure text colour is picked by the sign of the value |
| `სათაურის ფერი` | text colour of the dimension cell (the line label) |

### Membership (gid 1873343848)

Long list, one row per (article, line) pair:

| column | meaning |
|---|---|
| `მუხლი` | a **node name of the 1C article catalog** (`ВидыСчетовPL`), group or leaf; the literal `*` means "every article Membership does not cover" (see *Unmatched articles*) |
| `ახალი მუხლი` | the form line it feeds — a Lines label, byte for byte |
| `წონა` (optional) | weight: empty = 1, `-1` flips the sign, 0 = not a member; if the column is absent every row weighs 1 |

An article that feeds five lines (its own line, the group total, საოპერაციო მოგება, EBITDA,
EBIT, წმინდა მოგება) is simply listed five times. The display label may differ from the 1C
spelling (e.g. 1C's `თვითირებულება` maps to the line `თვითღირებულება`) — the 1C name is the
key, the line label is presentation.

**Exact-name semantics.** A Membership name matches ONLY the catalog node(s) that carry that
exact name — it never includes the node's children. So `რეალიზებული პროდუქციის თვითირებულება`
binds the COGS node itself, and its child `როიალტის გადასახადი (შიდა)` is a separate article
that needs its own pairs (it has them: EBIT and წმინდა მოგება only). A group name binds the
group node, i.e. postings sitting directly on the group. Every GUID with that name is bound
(the catalog is loaded UNfiltered, deletion-marked duplicates included, so historical postings
keep their line). The same name listed twice for one line does not double count: the link
table is `Distinct` on (GUID, line), weight = `Max`.

A new 1C article is therefore NOT in the form until a pair is added; until then it sits in
the `*` fallback lines and in the audit list.

### Audit table `PLFormAudit`

Island table, fields `[შემოწმება (P&L ფორმა)]` / `[შემოწმების მნიშვნელობა (P&L ფორმა)]`. Always
has at least the `ინფო` row (load timestamp). Rows to act on:

- `Membership: მუხლი ცნობარში არ არის` — a name in the first column matches no catalog node.
- `Membership: ახალი მუხლი Lines-ში არ არის` — a target name is not a Lines label.
- `Lines: ratio-ს მითითება Lines-ში არ არის` — numerator/denominator label unresolved (the
  ratio line shows nothing).
- `Lines: რიგი მეორდება` — duplicate key.
- `ცნობარი: ფოთოლი Membership-ში არ არის (fallback)` — a live leaf article no Membership
  pair covers; its money sits in the fallback lines, flagged `'არა'`. This is the to-do list
  for the sheet.
- `Membership: * სტრიქონები არ არის — დაუმატჩებელი მუხლები ფორმაში არ ჩანს` — no fallback
  target exists at all (no `*` rows and no `unmatched` line); unmatched money is invisible.

Put this table on a sheet next to the form.

## App-side contract

Dimension: `[სტრიქონი (P&L ფორმა)]` (sort: Auto / numeric — the dual number is `რიგი`).
Column dimensions (direction, location) go on the pivot's horizontal axis as usual.

**One shared modifier, used in EVERY set expression of the form** — app variable
`vPLFormSet` (variables expand recursively, so the nested `$(vPLVariant)` resolves):

```
[გადანაწილების ვარიანტი]={'$(vPLVariant)'}, [Internal (P&L)]={'არა'}, [არ არის ძირითადი (P&L)]={'არა'}
```

The internal / non-core exclusion is mandatory on the form, exactly like on the sales sheets
(`შიდა_და_არაძითადები_ფილტრი` cannot reach the P&L fact, see *Internal / non-core filtering*
in `pl-by-direction.md`). A role modifier is added per expression on top of it.

Two more app variables hold the numeric value, so the three measures stay short:

`vPLFormFact`:
```
if(Only([ტიპი (P&L ფორმა)])='ratio',
    Sum({<[როლი (P&L ფორმა)]={'N'}, $(vPLFormSet)>} [თანხა (P&L)]*[წონა (P&L ფორმა)])
  / Sum({<[როლი (P&L ფორმა)]={'D'}, $(vPLFormSet)>} [თანხა (P&L)]*[წონა (P&L ფორმა)]),
    Sum({<[როლი (P&L ფორმა)]={'S'}, $(vPLFormSet)>} [თანხა (P&L)]*[წონა (P&L ფორმა)]))
```

`vPLFormBudget`: the same with `[ბიუჯეტი (P&L)]`.

Measure (fact). The spacer branch must return a value ONLY where the column has data:
a constant `' '` keeps a column alive after every real cell in it went null — e.g. the
ლოგისტიკა column under the "ლოგისტიკა გადანაწილებული" variant. The `X` rows make the
check easy: on a spacer line they link every article, so a role-`X` sum is the column total.
⚠ `Sum()` over that column returns **0, not null** (allocation copies for no-basis months
exist there with empty amounts), so the checks use `Alt(…, 0) = 0`, every cell turns a zero
into `Null()`, and the object's "include zero values" must be OFF — otherwise the column
never disappears.

```
=if(Only([ტიპი (P&L ფორმა)]) = 'spacer',
    if(Alt(Sum({<[როლი (P&L ფორმა)]={'X'}, $(vPLFormSet)>} [თანხა (P&L)]), 0) = 0, Null(), ' '),
    if(Alt($(vPLFormFact), 0) = 0, Null(),
       Dual(Num($(vPLFormFact), Only([ფორმატი (P&L ფორმა)])), $(vPLFormFact))))
```

Plan: the same with `$(vPLFormBudget)` and `[ბიუჯეტი (P&L)]` in the spacer check.

Variance — value in a third variable `vPLFormVar` (`fact / plan − 1` on `sum` lines,
`fact − plan` in percentage points on `ratio` lines; a missing fact counts as 0):

```
if(Only([ტიპი (P&L ფორმა)])='ratio',
   Alt($(vPLFormFact), 0) - $(vPLFormBudget),
   Alt($(vPLFormFact), 0) / $(vPLFormBudget) - 1)
```

```
=if(Only([ტიპი (P&L ფორმა)]) = 'spacer',
    if(RangeSum(Sum({<[როლი (P&L ფორმა)]={'X'}, $(vPLFormSet)>} [თანხა (P&L)]),
                Sum({<[როლი (P&L ფორმა)]={'X'}, $(vPLFormSet)>} [ბიუჯეტი (P&L)])) = 0, Null(), ' '),
    if(Alt($(vPLFormBudget), 0) = 0, Null(),
       Dual(Num($(vPLFormVar), '0.0%;(0.0%)'), $(vPLFormVar))))
```

`RangeSum` (not `+`): null counts as 0, so a column that only has plan keeps its spacer.
Red = negative, as on the finance sheet; "red = worse than plan" would need a sign column in
Lines (not implemented).

`unmatched` lines take the `sum` branch (they are sum lines over the fallback set). The
spacer returns a space so the row is not suppressed, and null where the column is empty so
the column is not kept alive. Number formatting of all three measures: "measure expression".
Genuinely zero cells display blank, not `0` — accepted.

Notes:

- The `Dual()` keeps the row numeric (colouring, sorting) while displaying per-row format.
- Set analysis on `[როლი (P&L ფორმა)]` restricts link rows globally; the pivot row restricts
  them to the line; each fact row then meets exactly one link row, so `amount × weight` does
  not fan out. Without the form dimension the same expression DOES fan out — it is a
  form-only measure.
- Turn pivot totals off (they would add lines that already contain each other) and
  "include zero values" off (see the spacer note above).
- Style columns feed the pivot's colour expressions: background `=Only([ფონის ფერი (P&L ფორმა)])`,
  text `=if($(vPLFormFact) < 0, Only([უარყოფითი ტექსტის ფერი (P&L ფორმა)]), Only([დადებითი ტექსტის ფერი (P&L ფორმა)]))`
  (plan: `$(vPLFormBudget)`; variance: `$(vPLFormVar)`). The dimension itself: background
  `=Only([ფონის ფერი (P&L ფორმა)])`, text `=Only([სათაურის ფერი (P&L ფორმა)])`.

## Deployment

1. The two tabs in **Qlik Matching** must be filled with the column headers above BEFORE
   the push — the nightly full reload fails on an empty tab or a missing header column.
   Moving a tab to another spreadsheet changes its gid: update both `worksheetKey`s in
   `SD 0106` in the same push.
2. Push (the sync uploads `SD 0106` and the edited `SD.qvs`), full reload, close and reopen.
3. Read `PLFormAudit`; fix the sheet; full reload again (sheet edits need a FULL reload).

## Verification

1. Data model viewer: no `$Syn`; `PLFormLink` touches the fact only through
   `%lnk_მუხლი (P&L)`; `PLFormLines` only through `%lnk_სტრიქონი (P&L ფორმა)`.
2. `PLFormAudit` shows only the `ინფო` row.
3. Form line `შემოსავალი` = `Sum({<[გადანაწილების ვარიანტი]={'ცალ-ცალკე'}>} [თანხა (P&L)])`
   over the revenue articles in the old hierarchy pivot; `EBIT` line = sum of the fact over
   every article listed anywhere in Membership except `5. ფინანსური ხარჯები`.
4. Every `ratio` line = its numerator line ÷ `შემოსავალი`.
5. Spacer rows visible and empty; totals off; selection off on the form object.
6. Reopen as ADMIN after a partial reload: all 39 lines still present (the `X` anchors held).
