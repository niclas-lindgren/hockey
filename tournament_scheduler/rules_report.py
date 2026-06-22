"""Rules-report helper for `SeasonPlanner`."""

from __future__ import annotations

from typing import Dict, List, Sequence

from tournament_scheduler.season_config import DEFAULT_PARALLEL_GAMES


def rules_report(planner) -> List[Dict[str, str]]:
    """Return a structured report of every constraint and automatic decision."""
    report: List[Dict[str, str]] = []

    report.append({
        "regel": "Per-klubb kapasitet beregnes proporsjonalt",
        "forklaring": (
            f"Planleggeren starter med et minimumstak på {planner.max_club_teams_per_tournament} lag per klubb, "
            "men det effektive taket beregnes proporsjonalt ut fra klubbens størrelse i aldersgruppen og kan "
            "utvides videre av deficit-logikk. Dette er en kapasitetsregel, ikke et hardt forbud mot flere lag fra samme klubb."
        ),
        "kategori": "Automatisk avgjørelse",
    })

    if planner.parallel_games_for_age_group:
        for ag, pg in sorted(planner.parallel_games_for_age_group.items()):
            capacity = planner._max_teams_for(ag)
            report.append({
                "regel": f"Parallelle kamper for {ag}: {pg}",
                "forklaring": (
                    f"For aldersgruppen {ag} spilles det {pg} kamper samtidig per runde. "
                    f"Det gir plass til opptil {capacity} lag per turnering, og hvis lagetallet er oddetall "
                    "får ett lag pause i hver runde."
                ),
                "kategori": "Hard krav",
            })
    else:
        report.append({
            "regel": "Parallelle kamper: ingen spesifisert",
            "forklaring": (
                "Ingen aldersgrupper har spesifisert antall parallelle kamper. "
                f"Planleggeren bruker et standard nivå på {DEFAULT_PARALLEL_GAMES} parallelle kamper "
                f"og kan dermed invitere opptil {DEFAULT_PARALLEL_GAMES * 2 + 1} lag per turnering."
            ),
            "kategori": "Hard krav",
        })

    report.append({
        "regel": f"Ferdighetsnivå-bånd: ±{planner.division_skill_band}",
        "forklaring": (
            f"Lag med registrert ferdighetsnivå (1–10) foretrekkes sammen med lag innenfor ±{planner.division_skill_band} "
            "nivåer av hverandre. Dette er en myk prioritering i participant selection, ikke en absolutt sperre. "
            "Lag uten registrert nivå påvirkes ikke."
        ),
        "kategori": "Myk regel",
    })

    fairness_thresholds = planner.fairness_thresholds
    thresholds_text = ", ".join(
        f"{key}={fairness_thresholds[key]}"
        for key in sorted(fairness_thresholds)
    )
    report.extend([
        {
            "regel": "Konfigurasjonsstandarder og fairness-terskler",
            "forklaring": (
                f"Standard deltakelsesmål er {planner.target_tournament_count or 6} turneringsdeltakelser per lag, "
                f"minimumsklubb-taket starter på {planner.max_club_teams_per_tournament} lag per klubb, og deficit-kapasitet "
                f"kan utvides med {planner.deficit_cap_expansion}. Fairness-terskler som brukes av fairness-gaten: {thresholds_text}."
            ),
            "kategori": "Konfigurasjonsstandard",
        },
        {
            "regel": "Standard parallel-games fallback",
            "forklaring": (
                f"Hvis en aldersgruppe ikke er konfigurert, brukes {DEFAULT_PARALLEL_GAMES} parallelle kamper som fallback. "
                "Dette er bare en teknisk standard; konkrete aldersgrupper kan fortsatt ha egne konfigurerte verdier."
            ),
            "kategori": "Konfigurasjonsstandard",
        },
        {
            "regel": f"Standard starttid: {planner.DEFAULT_TOURNAMENT_START_TIME}",
            "forklaring": (
                f"Når en turnering ikke får et mer spesifikt slot-forslag fra hallkalenderen, brukes {planner.DEFAULT_TOURNAMENT_START_TIME} som standard starttid. "
                "Dette er hovedsakelig et teknisk utgangspunkt for planlegging og visning."
            ),
            "kategori": "Konfigurasjonsstandard",
        },
        {
            "regel": f"Buffer mellom turneringer i samme hall-dag: {planner.ARENA_DAY_SEQUENCE_BUFFER_MINUTES} min",
            "forklaring": (
                f"Når flere turneringer havner i samme arena samme dag, legges det inn {planner.ARENA_DAY_SEQUENCE_BUFFER_MINUTES} minutter buffer mellom starttidene. "
                "Det hindrer at arrangementene overlapper tidsmessig."
            ),
            "kategori": "Konfigurasjonsstandard",
        },

        {
            "regel": "Minst mulig gjentatte grupperinger",
            "forklaring": (
                "Når planleggeren velger hvilke lag som skal møtes i en turnering, regnes det ut én samlet score for hver kandidat. "
                "Scoren balanserer klubb-tak, game-count-deficit, gjentatte motstandere og skill-band, slik at lag som både trenger flere kamper og passer inn i turneringen prioriteres først."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Jevn fordeling av turneringer over sesongen",
            "forklaring": (
                f"Sesongvinduet deles i omtrent like store tidsbolker, og planleggeren gjør i tillegg en global utjevningspass over hele sesongen "
                "før datoene låses. Det gjør at månedslast, overlappende aldersgrupper og gjentatte matchups kan rebalanseres på tvers av grupper, "
                f"i stedet for at hver aldersgruppe bare følger sin egen lokale bucket. Måneder som avviker mer enn {int(planner.max_month_deviation_ratio * 100)}% fra forventet antall turneringer flagges som et varsel."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Rettferdig fordeling av hjemmeturneringer",
            "forklaring": (
                f"Hjemmeturneringer fordeles proporsjonalt etter antall lag hver klubb stiller. Klubber med flere lag får "
                f"hjemmeturnering oftere. Maksimalt tillatt avvik fra forventet antall er {planner.max_hosting_deviation} turnering(er)."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Helgebelastning og feriehelger",
            "forklaring": (
                f"Når flere klubber er aktuelle som vertskap på samme dato, foretrekker planleggeren klubber som ikke har hatt vertskap på forrige helg, "
                f"og som har færre ferie-/helligdagshelger allerede. Fairness-gaten kan slå ut når samme klubb får mer enn {planner.fairness_thresholds.get('max_consecutive_weekend_club_load', 2)} sammenhengende vertskapshelger eller mer enn {planner.fairness_thresholds.get('max_holiday_stretch_club_load', 2)} ferie-/helligdagshelger."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Jevnt antall kamper per lag",
            "forklaring": (
                f"Planleggeren teller opp alle kamper hvert lag spiller i løpet av sesongen. Forskjellen mellom laget med flest "
                f"og færrest kamper skal være maksimalt {planner.max_game_count_spread}. Lag som blir ferdige for tidlig (mer enn "
                f"{planner.max_early_finish_gap_days} dager før sesongslutt) flagges som et varsel."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Jevn fordeling av kamper innad i aldersgruppe/klubb",
            "forklaring": (
                f"For hver aldersgruppe beregnes gjennomsnittlig antall kamper per lag. Lag som avviker fra dette gjennomsnittet "
                f"med mer enn {planner.max_game_count_spread} kamper flagges som et varsel. Dette fanger opp skjevheter der en klubb "
                "med flere lag i samme aldersgruppe får færre eller flere kamper enn andre lag i samme aldersgruppe."
            ),
            "kategori": "Automatisk avgjørelse",
        },
    ])

    for label, club, age_group, actual, expected in planner._per_team_share_warnings:
        direction = "flere" if actual > expected else "færre"
        report.append({
            "regel": f"Skjev kampfordeling: {label}",
            "forklaring": (
                f"{label} ({club}, {age_group}) spiller {actual} kamper, mens snittet for {age_group} er {expected:.1f} — "
                f"{abs(actual - expected):.1f} {direction} enn snittet."
            ),
            "kategori": "Anbefaling",
        })

    report.extend([
        {
            "regel": "Behovsbasert unntak fra klubb-tak per turnering",
            "forklaring": (
                "Når et lag fra en klubb som allerede har fylt sin forholdsmessige andel av plassene i en turnering "
                "(_max_club_teams_for) har et større etterslep i antall spilte kamper enn alle ledige lag fra andre klubber, "
                "kan laget likevel velges — med en straff i prioriteringen proporsjonal med hvor langt over taket klubben er. "
                f"Dette unntaket er brukt {planner._club_cap_overrides} gang(er) i denne sesongplanen."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Ingen overlappende aldersgrupper",
            "forklaring": (
                "Aldersgrupper som deler spillerbase (for eksempel JU11 og U10) skal helst ikke ha turnering samme helg, "
                "fordi noen spillere tilhører begge grupper og ville blitt dobbeltbooket. Planleggeren forsøker å unngå dette; "
                "kollisjoner som ikke kan løses, rapporteres."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Round-robin: alle mot alle innen turneringen",
            "forklaring": (
                "Innenfor hver turnering spiller alle inviterte lag mot hverandre nøyaktig én gang (round-robin). "
                "Turneringens størrelse og antall parallelle kamper avgjør hvor mange runder som trengs. "
                "Hjemme/borte byttes annenhver runde for rettferdig fordeling."
            ),
            "kategori": "Automatisk avgjørelse",
        },
        {
            "regel": "Sikkerhetsfilter mot klubb-interne kamper",
            "forklaring": (
                "Som en ekstra sikkerhet (belt-and-suspenders) hoppes det over kamper mellom to lag fra samme klubb under round-robin-genereringen, "
                "selv om deltakerutvelgelsen allerede skal ha forhindret dette."
            ),
            "kategori": "Automatisk avgjørelse",
        },
    ])

    report.extend([
        {
            "regel": "Klubbbelastning per turnering",
            "forklaring": (
                f"Kjører en advarsel når en klubb har flere lag i en turnering enn det effektive taket tillater; "
                f"{len(planner._club_load_warnings)} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
        {
            "regel": "Hjemmeturneringsfordeling",
            "forklaring": (
                f"Kjører en advarsel når en klubb avviker for mye fra proporsjonal hjemmeturneringsfordeling; "
                f"{len(planner._hosting_warnings)} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
        {
            "regel": "Kampbalanse og tidlig slutt",
            "forklaring": (
                f"Kjører en advarsel når kampantall spres for mye mellom lag eller når lag blir ferdige for tidlig; "
                f"{len(planner._game_count_warnings)} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
        {
            "regel": "Skjev kampfordeling per aldersgruppe",
            "forklaring": (
                f"Kjører en advarsel når et lag avviker for mye fra aldersgruppens forventede kampmengde; "
                f"{len(planner._per_team_share_warnings)} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
        {
            "regel": "Feasibility / kapasitet",
            "forklaring": (
                f"Kjører en advarsel når sesongvinduet sannsynligvis ikke kan oppfylle deltakelsesmålet; "
                f"{len(planner._feasibility_warnings)} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
        {
            "regel": "Samme arena / samme dag",
            "forklaring": (
                f"Kjører en advarsel når to turneringer kolliderer i samme hall samme dag; "
                f"{len(getattr(planner, '_collisions', []))} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
        {
            "regel": "Fallback vertsklubb",
            "forklaring": (
                f"Kjører en advarsel når planleggeren må beholde opprinnelig vertsklubb fordi ønsket slot ikke finnes; "
                f"{len(planner.fallback_host_substitutions)} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
        {
            "regel": "Månedslast",
            "forklaring": (
                f"Kjører en advarsel når en måned avviker mer enn terskelen fra forventet turneringslast; "
                f"{len(planner._month_load_warnings)} tilfelle(r) er registrert i denne planen."
            ),
            "kategori": "Advarsel",
        },
    ])

    target_val = planner.target_tournament_count or 6
    all_same_target = all(
        t.target_tournament_count is None or t.target_tournament_count == target_val for t in planner.roster.teams
    )
    if all_same_target:
        target_desc = f"cirka {target_val} turneringsdeltakelser per lag"
        target_detail = f"Hver aldersgruppe planlegges mot et mykt mål på rundt {target_val} turneringsdeltakelser per lag."
    else:
        targets = {t.target_tournament_count or target_val for t in planner.roster.teams}
        target_range = ", ".join(sorted(str(t) for t in targets))
        target_desc = f"{min(targets)}–{max(targets)} turneringsdeltakelser per lag (varierer per lag)"
        target_detail = (
            f"Lag planlegges mot individuelle mål for turneringsdeltakelser: {target_range}. "
            f"Lag uten eget mål bruker standarden på {target_val}. "
        )
    report.append({
        "regel": f"Mykt mål: {target_desc}",
        "forklaring": (
            f"{target_detail} Tallet er en ønsket sesongbelastning — planleggeren vil heller lage færre, bedre turneringer "
            "enn å presse inn ekstra bare for å nå målet. Dersom en aldersgruppe har for få lag eller for få ledige helger "
            "til å oppfylle målet, justeres det ned."
        ),
        "kategori": "Automatisk avgjørelse",
    })

    if planner.events_by_club:
        report.append({
            "regel": "Tidspunkt på dagen velges ut fra vertsklubbens egen hallkalender",
            "forklaring": (
                "For hver turnering beregnes hvor lang tid hele turneringen tar (rundelengde × antall runder), og planleggeren "
                "ser etter en sammenhengende ledig luke av denne lengden i vertsklubbens egen hallkalender. Tidspunkt nærmest 11:00 "
                "foretrekkes, for å unngå svært tidlige eller sene starttider. Hvis den opprinnelige vertsklubben ikke har en passende "
                "ledig luke, prøver planleggeren andre klubber med ledig kapasitet på samme dato før den faller tilbake til standard starttid."
            ),
            "kategori": "Automatisk avgjørelse",
        })

    return report


def render_rules_markdown(planner) -> str:
    """Render the rules report as markdown for docs / review snapshots."""
    report = rules_report(planner)

    def _table(rows: Sequence[Dict[str, str]], include_category: bool = True) -> str:
        if not rows:
            return ""
        if include_category:
            lines = ["| Rule | What it does | Kind |", "|---|---|---|"]
            for row in rows:
                lines.append(f"| {row['regel']} | {row['forklaring']} | {row['kategori']} |")
        else:
            lines = ["| Rule | What it does |", "|---|---|"]
            for row in rows:
                lines.append(f"| {row['regel']} | {row['forklaring']} |")
        return "\n".join(lines)

    policy_rows = [r for r in report if r["kategori"] in {"Hard krav", "Myk regel"}]
    config_rows = [r for r in report if r["kategori"] == "Konfigurasjonsstandard"]
    implementation_rows = [r for r in report if r["kategori"] == "Automatisk avgjørelse"]
    warning_rows = [r for r in report if r["kategori"] == "Advarsel"]
    recommendation_rows = [r for r in report if r["kategori"] == "Anbefaling"]

    lines = [
        "# RVV Miniputt rules report",
        "",
        "This is a review/discussion snapshot of the current season-planning logic.",
        "It is based on the planner code, not on the marketing/docs wording, so it calls out where a rule is truly hard, soft, automatic, or only a warning.",
        "",
        "## Policy vs implementation",
        "",
        "### Policy rules",
        "",
        _table(policy_rows),
        "",
        "### Configuration defaults / guardrails",
        "",
        _table(config_rows),
        "",
        "### Implementation rules",
        "",
        _table(implementation_rows, include_category=False),
        "",
    ]

    if warning_rows:
        lines.extend([
            "### Warnings / diagnostics",
            "",
            _table(warning_rows),
            "",
        ])

    if recommendation_rows:
        lines.extend([
            "### Recommendations / review notes",
            "",
            _table(recommendation_rows),
            "",
        ])

    lines.extend([
        "## Important discussion point",
        "",
        "The skill-band rule is soft in the implementation: it adds a penalty during participant selection rather than blocking a team outright.",
        "The per-club \"minimum 1\" value is also not a standalone policy rule; it is just the floor used before proportional expansion.",
        "",
        "## Primary source files",
        "",
        "- `tournament_scheduler/rules_report.py`",
        "- `tournament_scheduler/participant_selection.py`",
        "- `tournament_scheduler/warnings.py`",
        "- `tournament_scheduler/season_planner.py`",
        "- `tournament_scheduler/models.py`",
        "- `tournament_scheduler/season_config.py`",
    ])

    return "\n".join(lines) + "\n"
