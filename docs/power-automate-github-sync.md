# Power Automate – GitHub-synkronisering for RVV Miniputt

Denne siden dokumenterer hvordan Power Automate kan synkronisere godkjente
inndatafiler inn i GitHub-repositoriet slik at GitHub Actions automatisk
regenererer og publiserer de riktige offentlige sidene.

## Prinsipper

- **Power Automate publiserer ikke kalenderen.** Ansvaret stopper etter at
  filen er synkronisert inn i repositoriet. GitHub Actions håndterer validering,
  generering og publisering.
- **Én commit per godkjent snapshot**, ikke én per skjema-respons.
- **Sammenlign innhold før commit.** Ingen commit hvis filen er uendret.
- **Bruk git-SHA for samtidighetskontroll.** Les filens nåværende SHA fra
  GitHub API før oppdatering for å unngå å overskrive endringer.
- **Utelat personopplysninger.** Eksporter kun de operasjonelle feltene
  repositoriet trenger.

## Oppsett av tilgangstoken

Anbefalt tilnærming: **finmasket PAT (Personal Access Token)**.

### Opprette PAT

1. Gå til [GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens](https://github.com/settings/tokens?type=beta).
2. Velg **Generate new token**.
3.Gi tokenet et beskrivende navn, f.eks. `RVV-Power-Automate`.
4. Under **Resource owner**, velg organisasjonen eller brukeren som eier
   `region-viken-vest-hockey/hockey`.
5. Under **Repository access**, velg **Only select repositories** og velg
   `region-viken-vest-hockey/hockey`.
6. Under **Permissions**, velg **Repository permissions**:
   - `Contents`: **Read and write**
7. Klikk **Generate token** og kopier tokenet umiddelbart.

### GitHub App (fremtidig herding)

En GitHub App gir finere tilgangskontroll og rotasjon, men krever mer
infrastruktur. Dagens anbefaling er PAT. Oppgrader til GitHub App når:

- Flere uavhengige flyter trenger forskjellige tillatelsesnivåer.
- Organisasjonen ønsker token-gjennomsiktighet per installasjon.
- Det er operasjonelt forsvarlig å drifte nøkkelrotasjon.

## Flyt A: Aktivitetskalender

Denne flyten dekker sesongens aktivitetsarbeidsbok, som redigeres i Teams
og lagres i SharePoint.

```
Teams-aktivitetsarbeidsbok oppdatert
  → SharePoint-utløser: «When a file is created or modified (properties only)»
  → filtrer til aktuell arbeidsbok
  → vent 2 minutter (AutoSave-debounce)
  → hent binært filinnhold
  → sammenlign med GitHub-filens innhold (SHA-256)
  → oppdater inputs/activities/activities.xlsx kun hvis innhold er endret
  → GitHub Actions regenererer og publiserer aktivitetskalenderen
```

### Power Automate-steg

| Steg | Kobling | Handling |
|------|---------|----------|
| 1 | SharePoint | **When a file is created or modified (properties only)** — pek til dokumentbiblioteket og mappen der aktivitetsarbeidsboken ligger. Filtrer på filnavn. |
| 2 | Innebygd | **Delay** — 2 minutter for å la AutoSave fullføre og unngå delvise opplastinger. |
| 3 | SharePoint | **Get file content** — hent det binære innholdet av filen. |
| 4 | HTTP | **GitHub API: Get file content** — `GET /repos/region-viken-vest-hockey/hockey/contents/inputs/activities/activities.xlsx?ref=main`. Sammenlign `sha`-feltet i responsen med SHA-256 av det lokale filinnholdet. |
| 5 | Betingelse | Hvis innhold er uendret → avslutt. Ellers → fortsett. |
| 6 | HTTP | **GitHub API: Create or update file contents** — `PUT /repos/region-viken-vest-hockey/hockey/contents/inputs/activities/activities.xlsx`. Bruk `sha` fra steg 4. Commit-melding: `Aktivitetskalender: oppdatert fra Teams/SharePoint`. |

### Hva skjer etter commit

GitHub Actions-workflowen `.github/workflows/activity-publish.yml` trigges
automatisk av endringer på `inputs/activities/activities.xlsx` og:

1. Validerer arbeidsboken.
2. Regenererer aktivitetskalenderen (JSON + HTML).
3. Slår sammen med eksisterende `/latest/`-snapshot.
4. Publiserer til GitHub Pages.

Hvis validering feiler, publiseres ingenting. Workflowen laster opp en
feilrapport som artifact.

## Flyt B: Påmeldte lag

Denne flyten dekker lagsregistrering via Microsoft Forms.

```
Microsoft Forms
  → Power Automate-validering
  → privat SharePoint-liste
  → eksporter komplett godkjent/aktuell snapshot
  → sammenlign med eksisterende GitHub CSV
  → commit inputs/registrations/registered-teams.csv kun ved endring
  → GitHub Actions regenererer og publiserer Påmeldte lag
```

### Forhåndsvalidering i Power Automate

Før dataene når SharePoint-listen, bør Power Automate validere:

- Obligatoriske felt er fylt ut (klubb, lagsnavn, aldersgruppe).
- Aldersgruppen er en av de konfigurerte gruppene (f.eks. U7–U12, JU8–JU12).
- Ingen åpenbare duplikater (samme klubb + lagsnavn + aldersgruppe).

Godkjente svar går til en privat SharePoint-liste. Avviste svar varsles
manuelt.

### Eksport og synkronisering

| Steg | Kobling | Handling |
|------|---------|----------|
| 1 | SharePoint | **Get items** — hent alle godkjente rader fra SharePoint-listen. |
| 2 | Innebygd | **Create CSV table** — bygg en CSV med kolonnene `club`, `label`, `age_group`. Inkluder ingen personopplysninger, SharePoint-ID-er, interne statuser eller kommentarer. |
| 3 | HTTP | **GitHub API: Get file content** — `GET /repos/region-viken-vest-hockey/hockey/contents/inputs/registrations/registered-teams.csv?ref=main`. |
| 4 | Betingelse | Sammenlign CSV-innholdet (normalisert: trim + casefold). Hvis uendret → avslutt. |
| 5 | HTTP | **GitHub API: Create or update file contents** — `PUT /repos/region-viken-vest-hockey/hockey/contents/inputs/registrations/registered-teams.csv`. Bruk `sha` fra steg 3. Commit-melding: `Påmeldinger: oppdatert fra SharePoint-godkjente registreringer`. |

### Hva skjer etter commit

GitHub Actions-workflowen `.github/workflows/registration-publish.yml` trigges
automatisk og:

1. Validerer CSV-en.
2. Synkroniserer lagdataene inn i `Lag`-arket i sesongarbeidsboken
   (`inputs/season/input.xlsx`).
3. Committer oppdatert arbeidsbok med `[skip ci]` for å unngå rekursive
   workflow-kjøringer.
4. Genererer `pameldte-lag.html` og `pameldte-lag.json`.
5. Slår sammen med eksisterende `/latest/`-snapshot.
6. Publiserer til GitHub Pages.

Commit-meldingen for arbeidsbokoppdateringen inneholder `[skip ci]` slik at
ingen andre workflows trigges av denne interne oppdateringen.

## Samtidighet og idempotens

- Begge publiseringsworkflowene deler `concurrency`-gruppe
  (`routine-publish-${{ github.ref }}`). Dette serialiserer alle
  rutinepubliseringer og forhindrer samtidige skrivinger til `gh-pages`.
- Power Automate bør alltid hente gjeldende `sha` før `PUT` for å unngå
  «409 Conflict» ved samtidige oppdateringer.
- Ved `409 Conflict`: gjenta lesingen (steg 1–4) og prøv på nytt én gang.
- Identiske inndata produserer identiske utdata. Workflowene genererer ikke
  unødvendige commits eller Pages-oppdateringer.

## Eierskap og tilgang

Minimum to personer bør ha eierskap over hver komponent:

| Komponent | Minimum eiere |
|-----------|---------------|
| Power Automate-flyt (aktiviteter) | 2 klubautoriserte |
| Power Automate-flyt (påmeldinger) | 2 klubautoriserte |
| SharePoint-dokumentbibliotek | 2 klubautoriserte |
| SharePoint-liste (påmeldinger) | 2 klubautoriserte |
| GitHub PAT | 2 klubautoriserte |
| GitHub repository (admin) | 2 klubautoriserte |

Dette sikrer at ingen enkeltperson blir et kritisk flaskehalspunkt.

## Gjenoppretting

### Hvis Power Automate feiler

- **Aktivitetskalender:** Eksporter arbeidsboken manuelt fra Teams/SharePoint,
  og last den opp til `inputs/activities/activities.xlsx` via GitHub-grensesnittet
  eller `git push`. Workflowen trigges automatisk.
- **Påmeldte lag:** Eksporter SharePoint-listen til CSV manuelt, og last opp
  til `inputs/registrations/registered-teams.csv`.

### Hvis GitHub Actions feiler

- Gå til **Actions**-fanen i repositoriet.
- Finn den feilede workflow-kjøringen.
- Last ned artifacten for å se input-fingeravtrykk, valideringsrapport og logger.
- Etter å ha rettet feilen, kjør workflowen manuelt via **Run workflow**
  (begge workflowene støtter `workflow_dispatch`).

### Manuell regenerering uten Power Automate

```bash
# Aktivitetskalender
make aktivitetskalender-publish CONFIRM_PUBLIC=1 \
  ACTIVITY_INPUT=inputs/activities/activities.xlsx

# Påmeldte lag
make registered-teams-publish \
  CSV=inputs/registrations/registered-teams.csv \
  CONFIRM_PUBLIC=1
```

## Sikkerhet

- **Ingen hemmeligheter i repositoriet.** Microsoft 365-legitimasjon,
  GitHub-tokens, skjemakoder og kontaktopplysninger lagres i Power Automate
  sine sikrede tilkoblinger og miljøvariabler — aldri i filer.
- **Offentlig påmeldingsside inneholder kun `club`, `label` og `age_group`.**
  Ingen navn, epostadresser, telefonnumre, kommentarer eller interne statuser.
- **PAT har kun `Contents: Read and write`** på det ene repositoriet.
- **Power Automate-flytene kjører under en dedikert tjenestekonto** som
  klubben kontrollerer — ikke en personlig konto.
- **Workflowene bruker `contents: write`** (minimumstillatelse for
  `gh-pages`-publisering) og serialiseres via `concurrency`-grupper.

## Relatert dokumentasjon

- [CI: required checks and branch protection](ci.md)
- [Engineering principles](engineering-principles.md)
- [Ownership and handover](ownership-and-handover.md)
- [RVV Miniputt deployment architecture](rvv-miniputt-deployment-architecture.md)
