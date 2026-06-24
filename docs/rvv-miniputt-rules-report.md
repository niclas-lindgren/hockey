# RVV Miniputt rules report

This is a review/discussion snapshot of the current season-planning logic.
It is based on the planner code, not on the marketing/docs wording, so it calls out where a rule is truly hard, soft, automatic, or only a warning.

## Policy vs implementation

### Policy rules

| Rule | What it does | Kind |
|---|---|---|
| Parallelle kamper for JU10: 3 | For aldersgruppen JU10 spilles det 3 kamper samtidig per runde. Det gir plass til opptil 6 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for JU11: 2 | For aldersgruppen JU11 spilles det 2 kamper samtidig per runde. Det gir plass til opptil 4 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for JU12: 2 | For aldersgruppen JU12 spilles det 2 kamper samtidig per runde. Det gir plass til opptil 4 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for U10: 3 | For aldersgruppen U10 spilles det 3 kamper samtidig per runde. Det gir plass til opptil 6 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for U11: 2 | For aldersgruppen U11 spilles det 2 kamper samtidig per runde. Det gir plass til opptil 4 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for U12: 2 | For aldersgruppen U12 spilles det 2 kamper samtidig per runde. Det gir plass til opptil 4 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for U7: 4 | For aldersgruppen U7 spilles det 4 kamper samtidig per runde. Det gir plass til opptil 8 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for U8: 4 | For aldersgruppen U8 spilles det 4 kamper samtidig per runde. Det gir plass til opptil 8 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |
| Parallelle kamper for U9: 3 | For aldersgruppen U9 spilles det 3 kamper samtidig per runde. Det gir plass til opptil 6 lag per turnering, og hvis lagetallet er oddetall får ett lag pause i hver runde. | Hard krav |

### Configuration defaults / guardrails

| Rule | What it does | Kind |
|---|---|---|
| Konfigurasjonsstandarder og fairness-terskler | Standard deltakelsesmål er 6 turneringsdeltakelser per lag, minimumsklubb-taket starter på 1 lag per klubb, og deficit-kapasitet kan utvides med 1. Fairness-terskler som brukes av fairness-gaten: max_game_count_spread=2, max_hosting_deviation=1, max_same_weekend_club_load=3, max_team_travel_km=700, min_diversity_score=0.75, min_month_balance_score=0.75, min_pairwise_matchup_score=0.25. | Konfigurasjonsstandard |
| Standard parallel-games fallback | Hvis en aldersgruppe ikke er konfigurert, brukes 2 parallelle kamper som fallback. Dette er bare en teknisk standard; konkrete aldersgrupper kan fortsatt ha egne konfigurerte verdier. | Konfigurasjonsstandard |
| Standard starttid: 10:00 | Når en turnering ikke får et mer spesifikt slot-forslag fra hallkalenderen, brukes 10:00 som standard starttid. Dette er hovedsakelig et teknisk utgangspunkt for planlegging og visning. | Konfigurasjonsstandard |
| Buffer mellom turneringer i samme hall-dag: 5 min | Når flere turneringer havner i samme arena samme dag, legges det inn 5 minutter buffer mellom starttidene. Det hindrer at arrangementene overlapper tidsmessig. | Konfigurasjonsstandard |

### Implementation rules

| Rule | What it does |
|---|---|
| Per-klubb kapasitet beregnes proporsjonalt | Planleggeren starter med et minimumstak på 1 lag per klubb, men det effektive taket beregnes proporsjonalt ut fra klubbens størrelse i aldersgruppen og kan utvides videre av deficit-logikk. Dette er en kapasitetsregel, ikke et hardt forbud mot flere lag fra samme klubb. |
| Minst mulig gjentatte grupperinger | Når planleggeren velger hvilke lag som skal møtes i en turnering, regnes det ut én samlet score for hver kandidat. Scoren balanserer klubb-tak, game-count-deficit og gjentatte motstandere, slik at lag som både trenger flere kamper og passer inn i turneringen prioriteres først. |
| Jevn fordeling av turneringer over sesongen | Sesongvinduet deles i omtrent like store tidsbolker, og planleggeren gjør i tillegg en global utjevningspass over hele sesongen før datoene låses. Det gjør at månedslast, overlappende aldersgrupper og gjentatte matchups kan rebalanseres på tvers av grupper, i stedet for at hver aldersgruppe bare følger sin egen lokale bucket. Måneder som avviker mer enn 50% fra forventet antall turneringer flagges som et varsel. |
| Rettferdig fordeling av hjemmeturneringer | Hjemmeturneringer fordeles proporsjonalt etter antall lag hver klubb stiller. Klubber med flere lag får hjemmeturnering oftere. Maksimalt tillatt avvik fra forventet antall er 1 turnering(er). |
| Jevnt antall kamper per lag | Planleggeren teller opp alle kamper hvert lag spiller i løpet av sesongen. Forskjellen mellom laget med flest og færrest kamper skal være maksimalt 2. Lag som blir ferdige for tidlig (mer enn 60 dager før sesongslutt) flagges som et varsel. |
| Jevn fordeling av kamper innad i aldersgruppe/klubb | For hver aldersgruppe beregnes gjennomsnittlig antall kamper per lag. Lag som avviker fra dette gjennomsnittet med mer enn 2 kamper flagges som et varsel. Dette fanger opp skjevheter der en klubb med flere lag i samme aldersgruppe får færre eller flere kamper enn andre lag i samme aldersgruppe. |
| Behovsbasert unntak fra klubb-tak per turnering | Når et lag fra en klubb som allerede har fylt sin forholdsmessige andel av plassene i en turnering (_max_club_teams_for) har et større etterslep i antall spilte kamper enn alle ledige lag fra andre klubber, kan laget likevel velges — med en straff i prioriteringen proporsjonal med hvor langt over taket klubben er. Dette unntaket er brukt 0 gang(er) i denne sesongplanen. |
| Ingen overlappende aldersgrupper | Aldersgrupper som deler spillerbase (for eksempel JU11 og U10) skal helst ikke ha turnering samme helg, fordi noen spillere tilhører begge grupper og ville blitt dobbeltbooket. Planleggeren forsøker å unngå dette; kollisjoner som ikke kan løses, rapporteres. |
| Round-robin: alle mot alle innen turneringen | Innenfor hver turnering spiller alle inviterte lag mot hverandre nøyaktig én gang (round-robin). Turneringens størrelse og antall parallelle kamper avgjør hvor mange runder som trengs. Hjemme/borte byttes annenhver runde for rettferdig fordeling. |
| Sikkerhetsfilter mot klubb-interne kamper | Som en ekstra sikkerhet (belt-and-suspenders) hoppes det over kamper mellom to lag fra samme klubb under round-robin-genereringen, selv om deltakerutvelgelsen allerede skal ha forhindret dette. |
| Mykt mål: cirka 6 turneringsdeltakelser per lag | Hver aldersgruppe planlegges mot et mykt mål på rundt 6 turneringsdeltakelser per lag. Tallet er en ønsket sesongbelastning — planleggeren vil heller lage færre, bedre turneringer enn å presse inn ekstra bare for å nå målet. Dersom en aldersgruppe har for få lag eller for få ledige helger til å oppfylle målet, justeres det ned. |
| Tidspunkt på dagen velges ut fra vertsklubbens egen hallkalender | For hver turnering beregnes hvor lang tid hele turneringen tar (rundelengde × antall runder), og planleggeren ser etter en sammenhengende ledig luke av denne lengden i vertsklubbens egen hallkalender. Tidspunkt nærmest 11:00 foretrekkes, for å unngå svært tidlige eller sene starttider. Hvis vertsklubbens egen hall ikke har en passende ledig luke den dagen, beholdes den opprinnelige vertsklubben og standard starttid i stedet for å låne kapasitet fra andre klubber. |

### Warnings / diagnostics

| Rule | What it does | Kind |
|---|---|---|
| Klubbbelastning per turnering | Kjører en advarsel når en klubb har flere lag i en turnering enn det effektive taket tillater; 0 tilfelle(r) er registrert i denne planen. | Advarsel |
| Hjemmeturneringsfordeling | Kjører en advarsel når en klubb avviker for mye fra proporsjonal hjemmeturneringsfordeling; 0 tilfelle(r) er registrert i denne planen. | Advarsel |
| Kampbalanse og tidlig slutt | Kjører en advarsel når kampantall spres for mye mellom lag eller når lag blir ferdige for tidlig; 0 tilfelle(r) er registrert i denne planen. | Advarsel |
| Skjev kampfordeling per aldersgruppe | Kjører en advarsel når et lag avviker for mye fra aldersgruppens forventede kampmengde; 0 tilfelle(r) er registrert i denne planen. | Advarsel |
| Feasibility / kapasitet | Kjører en advarsel når sesongvinduet sannsynligvis ikke kan oppfylle deltakelsesmålet; 0 tilfelle(r) er registrert i denne planen. | Advarsel |
| Samme arena / samme dag | Kjører en advarsel når to turneringer kolliderer i samme hall samme dag; 0 tilfelle(r) er registrert i denne planen. | Advarsel |
| Fallback vertsklubb | Kjører en advarsel når planleggeren må beholde opprinnelig vertsklubb fordi ønsket slot ikke finnes; 0 tilfelle(r) er registrert i denne planen. | Advarsel |
| Månedslast | Kjører en advarsel når en måned avviker mer enn terskelen fra forventet turneringslast; 0 tilfelle(r) er registrert i denne planen. | Advarsel |

## Important discussion point

The per-club "minimum 1" value is also not a standalone policy rule; it is just the floor used before proportional expansion.

## Primary source files

- `tournament_scheduler/rules_report.py`
- `tournament_scheduler/participant_selection.py`
- `tournament_scheduler/warnings.py`
- `tournament_scheduler/season_planner.py`
- `tournament_scheduler/models.py`
- `tournament_scheduler/season_config.py`
