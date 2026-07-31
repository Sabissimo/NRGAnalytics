# P&L budget — parked design (2026-07-29)

**Status: parked, nothing deployed.** A first implementation was written and reverted at the
user's request because the Google-Sheet format is being redesigned. The raw diff is kept as
[pl-budget-v1.patch](pl-budget-v1.patch).

⚠ The patch was generated against `fc62b69`, before the `Internal EEE` work landed in
`SD 0206`. It will **not** `git apply` cleanly to the current script — the file gained a block
at the top and all three non-sales branches changed. Treat it as a reference implementation, not
something to replay.

⚠ Superseded assumption (2026-07-31): the allocation has since been redesigned — retail split
into 3 store buckets, single wave, `დინამიურად` restricted to marked columns, mixed rows.
A revived budget must decide how budgeted overhead maps onto the store buckets (budgeted COGS
exists per direction, not per store) — the "budgeted COGS shares" decision below predates that.

Most of the design below is independent of the sheet layout. Only the load block is not.

## Decisions already taken (user-confirmed)

| Question | Decision |
|---|---|
| Budget grain | month × direction × article. **Holding level — no organization split** |
| Sheet shape | one tab per direction (5), months as columns, article rows |
| Article level | numbers on **leaves only**; groups are formulas in the sheet, ignored on load |
| Unbalanced weights | not applicable — see the *matching* sheet; budget rows are absolute amounts |
| Overhead allocation | budget follows the same 4 variants as actuals |
| Allocation basis | **budgeted** COGS shares, not actual |

The last one matters most and is the least obvious: actual COGS shares don't exist for future
months, because the P&L fact stops at `vPLEnd` (previous month end) while a budget covers the
year ahead. Allocating budget by actual shares would leave every future month unallocated. So
budget overhead is spread by the budget's own `რეალიზებული პროდუქციის თვითირებულება` lines per
direction per month.

Note that article name is spelled **without `ღ`** — that is the real 1C spelling, not a typo.

## Reusable regardless of sheet format

### 1. Leaf-only load, which makes group rows self-ignoring

Budget sheets are laid out like a P&L form: group rows carrying `SUM()` formulas, plus a totals
row. Those must never load, or they double-count against their own children. Rather than tagging
rows in the sheet, build a name→GUID map over **leaves only** — a group name simply isn't in the
map, so its row is dropped by the `Where`:

```qvs
МухлиРодителиПЛ:
Load Distinct
    [Родитель] as [%exists_მუხლი მშობელი (P&L)]
FROM [...СправочникВидыСчетовPL.qvd] (qvd)
Where not [Родитель] = '00000000000000000000000000000000';

MapМухлиИдЛистПЛ:
Mapping Load
    Trim([Наименование]),
    [Ссылка]
FROM [...СправочникВидыСчетовPL.qvd] (qvd)
Where not Exists([%exists_მუხლი მშობელი (P&L)], [Ссылка]);

Drop Table МухлиРодителиПЛ;
```

This also sidesteps the duplicate-article-name problem: the only repeated name in the catalog is
a group and its same-named child, and the group never enters a leaf-only map.

### 2. Budget rows go **into** the fact, not into a new table

Concatenated into `РегистрНакопленияДоходыИРасходы` with the amount in its own field
`[ბიუჯეტი (P&L)]` and `შემოსავალი`/`ხარჯი`/`თანხა` left null, so no existing measure changes.
Reusing the fact means reusing its bridge key — no new table, no association risk.

- pseudo-org `'ბიუჯეტი'` (holding level; selecting a real company hides budget, which is honest)
- contractor `'PL'`, so the existing `'PL'` section-access grant covers it with no `SD 0101` edit
- `[_PL ვარიანტის ჯგუფი]` derived from the direction, exactly as the static branch does

### 3. Allocation must be split, or budget is spread by the wrong shares

The actuals allocation block claims rows by `Where match([_PL ვარიანტის ჯგუფი],'LOG_AS_IS','ADM_AS_IS')`.
Budget rows match that too, so they must be excluded there and handled by a parallel block that
joins the budget share table instead:

```qvs
-- actuals block
Where match([_PL ვარიანტის ჯგუფი],'LOG_AS_IS','ADM_AS_IS') > 0
    and not [წყარო (P&L)] = 'ბიუჯეტი';

-- budget block
Where match([_PL ვარიანტის ჯგუფი],'LOG_AS_IS','ADM_AS_IS') > 0
    and [წყარო (P&L)] = 'ბიუჯეტი';
```

Forgetting the first line is the failure mode: budget silently spread by actual shares, and
nothing anywhere reports it.

## Format-specific (expect to rewrite)

The load block only. v1 used one `SUB` per tab so the direction came from the call rather than a
cell, with `LOAD *` so a new month column needs no script change:

```qvs
SUB LoadPLBudgetTab(vDir, vGid)
BudgetPLPre:
Add Load
    *,
    '$(vDir)' as [_მიმართულება (ბიუჯეტი)];
Crosstable([_თვე (ბიუჯეტი)], [_თანხა (ბიუჯეტი)], 1)
Load *;
SELECT * FROM GetWorksheetV2
WITH PROPERTIES (worksheetKey='$(vPLBudgetBook):_$(vGid)', gidOverride='',
                 generatedNumberedColumns='false', skipRows='');
END SUB
```

Workbook `1VRebtvzdH-Ij2UpG2GdwX0lBCf708UCYBTg_1ojhCy0` — the same one `SD 0201` and `SD 0205`
already read, so the connection is proven. v1 tab gids: საცალო `431849543`,
დისტრიბუცია `82043609`, კორპორატიული `616673310`, ლოგისტიკა `866585555`,
ადმინისტრაცია `2019413042`.

## Measures

Budget needs the variant modifier like every other P&L measure, plus the internal/non-core flags
for symmetry with actuals:

```
Sum({<[გადანაწილების ვარიანტი]={'$(vPLVariant)'},
      [Internal (P&L)]={'არა'}, [არ არის ძირითადი (P&L)]={'არა'}>} [ბიუჯეტი (P&L)])
```

## Behaviours to expect, not debug

- **Compare at month granularity or coarser.** Budget sits on the 1st of each month; a day-level
  selection shows actuals with no budget.
- **Selecting a real organization hides the budget** — holding-level by design.
- **A budget reaching into next year extends `SDCalendar`**, which moves `isME`/`isQE`/`isYE` and
  anything keyed on the calendar's last date, on other sheets too. A current-year budget changes
  nothing, since the sales plans already extend to year end.
- **An article budgeted but never posted to still displays**, because the budget row itself
  supplies the article value — and it rescues the hierarchy node from section-access reduction.
