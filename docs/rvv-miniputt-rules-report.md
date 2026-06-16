# RVV Miniputt rules report

This is a review/discussion snapshot of the current season-planning logic.
It is based on the planner code, not on the marketing/docs wording, so it calls out where a rule is truly hard, soft, automatic, or only a warning.

## Policy vs implementation

### Policy rules

| Rule | What it does | Kind |
|---|---|---|
| Parallelle kamper for JU11: 2 | For aldersgruppen JU11 spilles det 2 kamper samtidig per runde. Det gir plass til opptil 4 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for U10: 3 | For aldersgruppen U10 spilles det 3 kamper samtidig per runde. Det gir plass til opptil 6 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Ferdighetsnivå-bånd: ±2 | Lag med registrert ferdighetsnivå (1–10) foretrekkes sammen med lag innenfor ±2 nivåer av hverandre. Dette er en myk prioritering i participant selection, ikke en absolutt sperre. Lag uten registrert nivå påvirkes ikke. | Myk regel |

### Implementation rules

| Rule | What it does |
|---|---|
| Per-klubb kapasitet beregnes proporsjonalt | Planleggeren starter med et minimumstak på 1 lag per klubb, men det effektive taket beregnes proporsjonalt ut fra klubbens størrelse i aldersgruppen og kan utvides videre av deficit-logikk. Dette er en kapasitetsregel, ikke et hardt forbud mot flere lag fra samme klubb. |
| Minst mulig gjentatte grupperinger | Når planleggeren velger hvilke lag som skal møtes i en turnering, prioriterer den lag som ikke har vært i samme turnering tidligere i sesongen. Målet er at hvert lag skal møte flest mulig forskjellige motstandere gjennom sesongen. |
| Jevn fordeling av turneringer over sesongen | Sesongvinduet deles i omtrent like store tidsbolker, og én turnering legges til hver bolk. Dette sikrer at turneringene er spredt jevnt utover og at ingen periode blir overbelastet. Måneder som avviker mer enn 50% fra forventet antall turneringer flagges som et varsel. |
| Rettferdig fordeling av hjemmeturneringer | Hjemmeturneringer fordeles proporsjonalt etter antall lag hver klubb stiller. Klubber med flere lag får hjemmeturnering oftere. Maksimalt tillatt avvik fra forventet antall er 1 turnering(er). |
| Jevnt antall kamper per lag | Planleggeren teller opp alle kamper hvert lag spiller i løpet av sesongen. Forskjellen mellom laget med flest og færrest kamper skal være maksimalt 2. Lag som blir ferdige for tidlig (mer enn 60 dager før sesongslutt) flagges som et varsel. |
| Jevn fordeling av kamper innad i aldersgruppe/klubb | For hver aldersgruppe beregnes gjennomsnittlig antall kamper per lag. Lag som avviker fra dette gjennomsnittet med mer enn 2 kamper flagges som et varsel. Dette fanger opp skjevheter der en klubb med flere lag i samme aldersgruppe får færre eller flere kamper enn andre lag i samme aldersgruppe. |
| Behovsbasert unntak fra klubb-tak per turnering | Når et lag fra en klubb som allerede har fylt sin forholdsmessige andel av plassene i en turnering (_max_club_teams_for) har et større etterslep i antall spilte kamper enn alle ledige lag fra andre klubber, kan laget likevel velges — med en straff i prioriteringen proporsjonal med hvor langt over taket klubben er. Dette unntaket er brukt 0 gang(er) i denne sesongplanen. |
| Ingen overlappende aldersgrupper | Aldersgrupper som deler spillerbase (for eksempel JU11 og U10) skal helst ikke ha turnering samme helg, fordi noen spillere tilhører begge grupper og ville blitt dobbeltbooket. Planleggeren forsøker å unngå dette; kollisjoner som ikke kan løses, rapporteres. |
| Round-robin: alle mot alle innen turneringen | Innenfor hver turnering spiller alle inviterte lag mot hverandre nøyaktig én gang (round-robin). Turneringens størrelse og antall parallelle kamper avgjør hvor mange runder som trengs. Hjemme/borte byttes annenhver runde for rettferdig fordeling. |
| Sikkerhetsfilter mot klubb-interne kamper | Som en ekstra sikkerhet (belt-and-suspenders) hoppes det over kamper mellom to lag fra samme klubb under round-robin-genereringen, selv om deltakerutvelgelsen allerede skal ha forhindret dette. |
| Mykt mål: cirka 6 turneringsdeltakelser per lag | Hver aldersgruppe planlegges mot et mykt mål på rundt 6 turneringsdeltakelser per lag. Tallet er en ønsket sesongbelastning — planleggeren vil heller lage færre, bedre turneringer enn å presse inn ekstra bare for å nå målet. Dersom en aldersgruppe har for få lag eller for få ledige helger til å oppfylle målet, justeres det ned. |
| Tidspunkt på dagen velges ut fra vertsklubbens egen hallkalender | For hver turnering beregnes hvor lang tid hele turneringen tar (rundelengde × antall runder), og planleggeren ser etter en sammenhengende ledig luke av denne lengden i vertsklubbens egen hallkalender. Tidspunkt nærmest 11:00 foretrekkes, for å unngå svært tidlige eller sene starttider. Hvis vertsklubbens egen hall ikke har en passende ledig luke den dagen, beholdes den opprinnelige vertsklubben og standard starttid i stedet for å låne kapasitet fra andre klubber. |

## WARNINGS / diagnostics

These do not block planning, but they surface problems for review:

- club-load warnings when a club exceeds its per-tournament share in an age group
- hosting warnings when home-tournament distribution deviates too much from proportional fairness
- game-count warnings when team game counts spread too far or teams finish too early
- per-team share warnings when a team is too far from age-group expectations
- feasibility warnings when the season window likely cannot satisfy the participation target
- same-arena / same-day collision warnings for overlapping bookings
- fallback host substitutions when the preferred host cannot fit the hall slot

## Important discussion point

The skill-band rule is soft in the implementation: it adds a penalty during participant selection rather than blocking a team outright.
The per-club "minimum 1" value is also not a standalone policy rule; it is just the floor used before proportional expansion.

## Primary source files

- `tournament_scheduler/rules_report.py`
- `tournament_scheduler/participant_selection.py`
- `tournament_scheduler/warnings.py`
- `tournament_scheduler/season_planner.py`
- `tournament_scheduler/models.py`
- `tournament_scheduler/season_config.py`
