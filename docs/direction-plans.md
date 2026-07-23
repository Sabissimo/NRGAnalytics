# Direction plans (გეგმები მიმართულებებით) — design record

Implemented 2026-07-09. Sales and profit plans per business direction
(`ПеречислениеНаправленияПокупателей`), loaded from Google Sheets, comparable against
actuals by direction AND date, reacting to master-calendar selections including future dates
— i.e. full parity with the older segment (contractor-group) plans.

## Where things live

| Piece | File | What |
|---|---|---|
| Sheets pipelines + concatenate | `SD 0201` (tail) | crosstab → filter to current year → day-spread → merged temp `ПланыПоНаправлениям` → `Add Concatenate(РегистрНакопленияПродажи)` |
| Direction on debitors | `SD 0202` | `ApplyMap('MapНаправленияПокупателейДоговора', [ხელშეკრულება], …)` display field + key segment |
| Direction in bridge | `SD 0301` | `[მიმართულება]` field on `BridgeTableOrgDate`; key rebuilds include direction; plan rows get group `'PLAN'` |
| Section-access survival | `SD 0101` | `'PLAN'` pseudo-row in `СправочникКонтрагентыИерархия`; `'PLAN'` per user/admin in SA sources |
| Direction mapping | `SD 0002` | `MapНаправленияПокупателейДоговора` (contract → direction), `MapНаправлениеДокумента` (document → contract → direction) |

## The plan-row shape (concatenated into the sales fact)

One row per direction × day of current year, spread across working days via
`MapВыходныеПоМесяцам` / `MapВыходныеПоДням`:

- `SalesDate` = plan day; `[ნაშთია (გაყიდვები)]` = 0
- `[%lnk_ორგანიზაცია (გაყიდვები)]` = `'გეგმა'` — dummy org: makes the bridge's key rebuild
  match the row's literal key, guarantees no collision with real keys (real orgs are 32-char hex),
  and labels the rows for debugging. Contractor link left **null** so `Count(distinct contractor)`
  is not inflated.
- `[ორგანიზაცია_კონტрагентი_პერიოდი_ნაშთია]` = `'გეგმა' & '||' & day & '|0|' & direction`
- `[მიმართულება (გაყიდვები)]` = direction — same field as actual rows → one chart dimension
  slices plan and fact together
- Measures: `[გაყიდвები მიმართულებებით (გეგმა)]`, `[ამონაგები მიმართულებებით (გეგმა)]`

The existing bridge code picks these rows up automatically (it resident-scans the fact),
creating `BridgeTableOrgDate` rows (group `'PLAN'`) → `BridgeTableContrDate` rows with
`DateForConnect = day|0` → calendar. So calendar selections and the exec-app period variables
(`[Year SD]`/`[Date SD]` modifiers) slice the plan, including future days.

## Why the obvious alternatives fail (do not retry these)

1. **Standalone table keyed `direction|date` shared with the fact** — plan rows for days
   without sales are association orphans; ANY calendar selection excludes them → plan totals
   silently understated (future days + zero-sale days vanish).
2. **Standalone table with `DateForConnect` (royalty-budget style)** — full calendar
   reactivity, but the plan's direction field cannot associate with the facts' direction
   (adding any second link closes a loop) → no single-dimension plan-vs-fact chart.
3. **Both links on one table** — circular reference; Qlik loosens a table; charts break.
4. **Direction-date key on BOTH facts** — Sales—OrgBridge—Debitors already meet at the bridge;
   a second shared field closes a loop. Only the sales fact carries plan rows.
5. **Direction column on the bridge without extending the keys** — bridge grain is
   (org, contractor, date); one contractor-day can span multiple directions → fact rows would
   associate with both directions' bridge rows → double counting. Hence direction is a segment
   of the composite key itself, in ALL seven build/rebuild sites.

The segment plans get full parity via a different trick (budget rows injected into
`BridgeTableContrDate`, possible because group is in the bridge grain); direction is
document-level, so the concatenate-into-fact pattern is the loop-free equivalent.

## The section-access incident (why `'PLAN'` exists)

First deployment loaded correctly but every plan value read 0. Root cause: SECTION ACCESS
reduction on `[%lnk_კონტрагентი]` — plan rows' bridge chain ended in a null group
(`ApplyMap` group of a null contractor), so reduction deleted the entire chain at app open,
for admins too. Fix: plan bridge rows get group `'PLAN'` (SD 0301), a `'PLAN'` hierarchy
pseudo-row provides the reduction anchor (SD 0101), and `'PLAN'` is appended to every
USER/ADMIN row in the SA sources (SD 0101). Latin marker on purpose: SA uppercases values
and Georgian case folding (Mtavruli) is risky there.

Debugging note for posterity: this was chased as an association problem for a while because
`exit script` bisecting inside the `NonDistinct → final → Drop` sandwich of SD 0301 produces
a synthetic-key/circular-reference model that also zeroes plans — a different, fake failure.
Valid bisect points are only AFTER `Drop` statements. The real tell was: fields present,
unconditional sums = 0, zero rows with `'გеგმა'` — data physically absent, which associations
can never cause.

## Exec dashboard master measures (created 2026-07-09)

App `d5fbc0e4-9d85-431b-976d-4004f656e299`. Names follow the old family's convention:

- `გაყიდვების გეგმა (მიმართულებები, მიმდინარე დღე | დღე სრული | თვე | თვე სრული | წელი | წელი სრული)`
- `ამონაგების გეგმა (მიმართულებები, …same six…)`
- `გაყიდвების გადახრა (მიმართულებები, მიმდინარე თვე | წელი)` and
  `ამონაგების გადახრა (…)` — `(fact/plan)−1`, fact side inlined with
  `$(შიდა_და_არაძითადები_ფილტрი)`, plan side without it.

Deliberate differences from the segment-plan measures: no
`$(ფილტри_ინსტალерები_მომხმარебლები)` on plan sums (plan rows have no segment — the modifier
would zero them), and deviations are self-contained (no master-measure name references).

Chart recipe: dimension `[მიმართულება]` (bridge field — includes directions with plan but no
sales), measures = fact + plan pairs. Time axis: master calendar works, past and future.
