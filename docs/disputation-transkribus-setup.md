# Disputation via Transkribus API

Diese Integration deckt die Disputationsfassungen ohne IIIF-Manifest ab:
- A V 1447 (Schlussredaktion)
- A V 1443 (Hertwig)
- A V 1444 (Cyro)
- A V 1445 (Schoeni)
- A V 1446 (Ruemlang)

Die Daten werden serverseitig aus Transkribus synchronisiert und lokal in
`data/disputation/<variante>/` abgelegt. Das Frontend liest dann lokale Dateien
(`viewer_manifest.json`, `transcriptions/`, `line_coords/`, optional `images/`).

## Benoetigte Credentials

Du kannst **eine** der folgenden Auth-Varianten verwenden:

- `TRANSKRIBUS_ACCESS_TOKEN`: bereits vorhandener OIDC Access Token
- oder:
- `TRANSKRIBUS_USER`: Dein Transkribus Login (normalerweise E-Mail)
- `TRANSKRIBUS_PASSWORD`: Dein Transkribus Passwort
- optional `TRANSKRIBUS_OIDC_CLIENT_ID` (Default: `transkribus-api-client`)

Die Skripte versuchen zuerst Legacy-Login (`/rest/auth/login`) und fallen bei Bedarf auf OIDC Password Grant (Bearer Token) zurueck.

## Bereitstellung der Credentials

### Option A: Nur fuer eine Shell-Session

```bash
# Option 1: tokenbasiert
export TRANSKRIBUS_ACCESS_TOKEN="<access-token>"

# Option 2: Benutzername/Passwort
export TRANSKRIBUS_USER="you@example.org"
export TRANSKRIBUS_PASSWORD="<dein-passwort>"
```

### Option B: `.env` lokal (nicht einchecken)

```bash
cat > .env <<'ENV'
# Option 1: direktes Token (empfohlen fuer SSO/2FA-Accounts)
TRANSKRIBUS_ACCESS_TOKEN=

# Option 2: Benutzername/Passwort (wenn kein Token gesetzt ist)
TRANSKRIBUS_USER=you@example.org
TRANSKRIBUS_PASSWORD=<dein-passwort>
TRANSKRIBUS_OIDC_CLIENT_ID=transkribus-api-client
ENV
set -a
source .env
set +a
```

`.env` ist bereits via `.gitignore` ausgeschlossen.

## Konfiguration der Dokumente

1. Beispiel kopieren:

```bash
cp config/disputation_transkribus.example.json config/disputation_transkribus.json
```

2. In `config/disputation_transkribus.json` pro Variante setzen:
- `collection_id`
- `document_id`
- optional `status_preference` (z. B. `["FINAL", "GT"]`)

## Sync ausfuehren

Abhaengigkeit (einmalig):

```bash
pip install requests
```

```bash
# Empfohlen: keine lokalen Bilder speichern, nur Transkribus-URLs in viewer_manifest.json
python3 scripts/sync_disputation_transkribus.py --config config/disputation_transkribus.json --no-images
```

Optional:

```bash
# Mit lokalem Bilddownload
python3 scripts/sync_disputation_transkribus.py --config config/disputation_transkribus.json --overwrite
```

## Credentials testen (vor dem Sync)

```bash
python3 scripts/check_transkribus_credentials.py --collection-id 2313234 --document-id 13922579
```

Erwartung:
- `Auth OK (...)`
- `Document reachable: ... pages=755`

## Output pro Variante

Unter `data/disputation/<variante>/` werden erzeugt:
- `viewer_manifest.json`
- `images/page_<n>.<ext>` (nur ohne `--no-images`)
- `pagexml/page_<n>.xml`
- `transcriptions/page_<n>.md`
- `line_coords/page_<n>.json`

`line_coords/page_<n>.json` wird im Frontend als Zeilen-Overlay genutzt.
