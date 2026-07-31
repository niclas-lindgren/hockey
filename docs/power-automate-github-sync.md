# Power Automate – GitHub-synkronisering for RVV Miniputt

Denne siden dokumenterer hvordan Power Automate synkroniserer godkjente
inndatafiler til GitHub-repositoriet via **issues**, slik at GitHub Actions
automatisk importerer, validerer, og publiserer de riktige offentlige sidene.

## Arkitektur

Power Automate oppretter en maskinlesbar GitHub issue. GitHub Actions laster
ned filen fra en midlertidig lenke, validerer den, og committer den til den
kanoniske `inputs/`-stien. En eksisterende path-trigger workflow regenererer og
publiserer deretter offentlige sider.

```text
SharePoint-fil endres
  → Power Automate oppretter GitHub issue med nedlastingslenke
  → GitHub Actions import-workflow laster ned og validerer filen
  → commit til inputs/activities/activities.xlsx
  → path-trigger workflow regenererer og publiserer aktivitetskalender
```

## Prinsipper

- **Power Automate publiserer ikke noe.** Ansvaret stopper etter at en
  maskinlesbar issue er opprettet. GitHub Actions håndterer all validering,
  import, generering og publisering.
- **Én commit per godkjent snapshot**, ikke én per skjema-respons.
- **Sammenlign innhold før commit.** Ingen commit hvis filen er uendret.
- **Stabil identifikasjon.** SharePoint-filer identifiseres med `DriveId` +
  `DriveItemId`, ikke filnavn eller sti.
- **Utelat personopplysninger.** Eksporter kun de operasjonelle feltene
  repositoriet trenger.
- **Power Automate trenger kun den innebygde GitHub-koblingen** for å opprette
  issues — ingen premium HTTP actions eller PAT med skrivetilgang.

## Flyt A: Aktivitetskalender (via GitHub issues)

### Power Automate-oppsett

| Steg | Kobling | Handling |
|------|---------|----------|
| 1 | SharePoint | **When a file is created or modified (properties only)** — pek til dokumentbiblioteket. Filtrer på `DriveId` og `DriveItemId` for aktivitetsarbeidsboken. |
| 2 | Innebygd | **Delay** — 2 minutter for å la AutoSave fullføre. |
| 3 | SharePoint | **Create sharing link** — opprett en midlertidig, skrivebeskyttet delingslenke (`view`, ikke `edit`). |
| 4 | Innebygd | Bygg issue-body: se kontrakten under. |
| 5 | GitHub | **Create issue** — repo `region-viken-vest-hockey/hockey`, tittel `sharepoint-sync: activities`, body som spesifisert. |

### Issue-kontrakt

Issuen må ha **nøyaktig** denne tittelen:

```text
sharepoint-sync: activities
```

Body er én `nøkkel=verdi` per linje (pluss tillatte tomme/Markdown-linjer):

```text
source=sharepoint
target_path=inputs/activities/activities.xlsx
drive_id=<SharePoint DriveId>
drive_item_id=<SharePoint DriveItemId>
version=<SharePoint VersionNumber>
download_url=<midlertidig skrivebeskyttet delingslenke>
```

| Felt | Påkrevd | Beskrivelse |
|------|---------|-------------|
| `source` | Ja | Må være `sharepoint`. |
| `target_path` | Ja | Må være `inputs/activities/activities.xlsx`. |
| `download_url` | Ja | Midlertidig skrivebeskyttet delingslenke. Må peke til en gyldig XLSX-fil. |
| `drive_id` | Nei | SharePoint DriveId. Brukes kun i diagnostikk. |
| `drive_item_id` | Nei | SharePoint DriveItemId. Brukes kun i diagnostikk. |
| `version` | Nei | SharePoint-versjonsnummer. Brukes kun i diagnostikk. |

Andre nøkler avvises. Duplikate nøkler avvises. URL-en skrives aldri til
logger, artifakter eller issue-kommentarer.

### Hva skjer etter at issuen er opprettet

1. **GitHub Actions** `.github/workflows/sharepoint-import.yml` trigges av
   `issues: [opened]`.
2. Kun issues med tittel `sharepoint-sync: activities` kjøres.
3. Workflowen:
   - Parser og validerer issue-body.
   - Laster ned filen fra `download_url` (følger redirects).
   - Verifiserer at responsen er en gyldig XLSX (magic bytes + openpyxl).
   - Sammenligner SHA-256 med eksisterende kanonisk fil.
   - **Hvis endret:** committer til `inputs/activities/activities.xlsx`.
   - **Hvis uendret:** ingen commit.
   - Kommenterer og lukker issuen.
4. **Ved commit:** `.github/workflows/activity-publish.yml` trigges av
   path-endringen og regenererer + publiserer aktivitetskalenderen.
5. **Ved feil:** issuen forblir åpen med en diagnosekommentar. Ingen
   repository-filer endres.

### Håndtering av SharePoint-filer som slettes og gjenskapes

Hvis aktivitetsarbeidsboken slettes og lastes opp på nytt i SharePoint, får
den en ny `DriveItemId`. Power Automate må da:

1. Identifisere den nye filen ved hjelp av filnavn eller dokumentbibliotek-sti.
2. Oppdatere `DriveItemId`-filteret i Power Automate-flyten.
3. Opprette en ny `sharepoint-sync: activities`-issue med den nye ID-en.

Dette er en manuell operasjon — den skjer svært sjelden og dokumenteres her
for fullstendighet.

## Flyt B: Påmeldte lag

Denne flyten dekker lagsregistrering via Microsoft Forms og synkroniseres
foreløpig via direkte CSV-commit. Den kan senere migreres til samme
issue-baserte mønster som aktivitetskalenderen.

### Dagens flyt

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

### Hva skjer etter commit

GitHub Actions-workflowen `.github/workflows/registration-publish.yml` trigges
automatisk og:

1. Validerer CSV-en.
2. Synkroniserer lagdataene inn i `Lag`-arket i sesongarbeidsboken.
3. Committer oppdatert arbeidsbok med `[skip ci]` for å unngå rekursive
   workflow-kjøringer.
4. Genererer `pameldte-lag.html` og `pameldte-lag.json`.
5. Slår sammen med eksisterende `/latest/`-snapshot.
6. Publiserer til GitHub Pages.

## Samtidighet og idempotens

- **Import-workflowen** har egen `concurrency`-gruppe (`sharepoint-import`).
  Dette forhindrer samtidige importer.
- **Publiseringsworkflowene** deler `concurrency`-gruppe
  (`routine-publish`). Dette serialiserer alle rutinepubliseringer og
  forhindrer samtidige skrivinger til `gh-pages`.
- Import-workflowen bruker `git push` og GitHub håndterer push-konflikter.
- SHA-256-sammenligning forhindrer unødvendige commits.
- Identiske inndata produserer identiske utdata.

## Eierskap og tilgang

Minimum to personer bør ha eierskap over hver komponent:

| Komponent | Minimum eiere |
|-----------|---------------|
| Power Automate-flyt (aktiviteter) | 2 klubautoriserte |
| Power Automate-flyt (påmeldinger) | 2 klubautoriserte |
| SharePoint-dokumentbibliotek | 2 klubautoriserte |
| SharePoint-liste (påmeldinger) | 2 klubautoriserte |
| GitHub repository (admin) | 2 klubautoriserte |

GitHub-koblingen i Power Automate bruker OAuth mot en klubautorisert
GitHub-konto. Ingen PAT eller hemmeligheter lagres i Power Automate-miljøet
utover den innebygde koblingen.

## Gjenoppretting

### Hvis Power Automate feiler

- **Aktivitetskalender:** Eksporter arbeidsboken manuelt fra Teams/SharePoint,
  og last den opp til `inputs/activities/activities.xlsx` via GitHub-grensesnittet
  eller `git push`. Workflowen trigges automatisk.
- **Påmeldte lag:** Eksporter SharePoint-listen til CSV manuelt, og last opp
  til `inputs/registrations/registered-teams.csv`.

### Hvis import-workflowen feiler

- Issuen forblir åpen med en diagnosekommentar.
- Gå til **Actions**-fanen og finn den feilede kjøringen.
- Rett feilen og opprett en ny issue med tittel `sharepoint-sync: activities`
  og oppdatert body.
- Alternativt: commit filen manuelt til `inputs/activities/activities.xlsx`.

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

### Hvis SharePoint-filen får ny DriveItemId

1. Identifiser den nye filens `DriveItemId` via SharePoint-grensesnittet eller
   Microsoft Graph.
2. Oppdater `DriveItemId`-filteret i Power Automate-flyten.
3. Opprett en ny `sharepoint-sync: activities`-issue for å trigge import.

## Sikkerhet

- **Ingen hemmeligheter i repositoriet.** Microsoft 365-legitimasjon,
  skjemakoder og kontaktopplysninger lagres i Power Automate/SharePoint —
  aldri i filer.
- **Offentlig påmeldingsside inneholder kun `club`, `label` og `age_group`.**
  Ingen navn, epostadresser, telefonnumre, kommentarer eller interne statuser.
- **Nedlastingslenker skrives aldri til logger, artifakter eller
  issue-kommentarer.** URL-en finnes kun i den opprinnelige issue-bodyen og
  brukes én gang av import-workflowen.
- **Power Automate har kun tilgang til å opprette issues** via den innebygde
  GitHub-koblingen — ingen repository-skrivetilgang.
- **Import-workflowen bruker `contents: write` og `issues: write`** —
  minimumstillatelser for å committe filer og administrere trigger-issues.
- **Workflowene serialiseres via `concurrency`-grupper.**
- **Midlertidige delingslenker er skrivebeskyttet (`view`)** og utløper
  automatisk.

## Relatert dokumentasjon

- [CI: required checks and branch protection](ci.md)
- [Engineering principles](engineering-principles.md)
- [Ownership and handover](ownership-and-handover.md)
- [RVV Miniputt deployment architecture](rvv-miniputt-deployment-architecture.md)
