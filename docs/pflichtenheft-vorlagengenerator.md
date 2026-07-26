# Pflichtenheft — Ctrl+Grid

*Vorlagengenerator für maßhaltige Papier- und Pad-Vorlagen*
*Stand: überarbeitet nach Wettbewerbsrecherche und Architekturprüfung.*

**Paket- und Kommandoname:** `ctrlgrid`
**Lizenz:** MIT
**Vertrieb:** Open Source auf GitHub, Installation über PyPI/`uvx`

---

## 1. Zweck und Leitbild

Ein Kommandozeilenwerkzeug, das **maßhaltige PDF-Vorlagen** erzeugt: Rasterpapier
(kariert, liniert, gepunktet, isometrisch, Kalligraphie, logarithmisch), leere
Notensysteme, Labyrinthe, beschriftete Gitterblöcke, Polarraster, Kachelmuster
und ausfüllbare Formulare — auf Papierformaten **und** auf E-Ink-/Tablet-Formaten.

**Leitbild:** Ein Kommando, ein fertiges mehrseitiges PDF. Etwa: 30 Blatt
Millimeterpapier, jedes mit einem anderen Namen aus einer Liste — oder ein
anderes Labyrinth pro Seite.

**Zentrale, unverhandelbare Eigenschaft:** *Maßhaltigkeit.* Was 5 mm heißt, misst
auf dem Ausdruck 5 mm. Kein Skalieren, kein „to fit", kein Dehnen von Rastern,
damit sie aufgehen.

**Zielgruppe:** Nutzer, die mit Kommandozeile und GitHub umgehen können.
Anwendungsbeispiele aus dem Schulalltag illustrieren den Zweck, sind aber keine
Anforderungsquelle.

### 1.1 Alleinstellung

Eine Recherche über rund 60 vergleichbare Werkzeuge (Webgeneratoren, CTAN-Pakete,
GitHub-Projekte) ergab: **Mehrseitige Ausgabe, fortlaufende Nummerierung und
listengetriebene Personalisierung fehlen praktisch überall.** Drei der
untersuchten Generatoren können mehr als eine Seite ausgeben; keiner kann eine
Namensliste verarbeiten. Es existiert kein CLI-Werkzeug in der Position
*Definitionsdatei → mehrseitiges druckbares PDF*.

> **Belege: [`docs/research.md`](research.md)** — Stand Juli 2026, mit
> Quellen und Fähigkeitsmatrix. Dieses Kapitel begründet die Existenz des
> Projekts; eine unbelegte Behauptung wäre dafür zu wenig. Wer die Aussage
> später anzweifelt, soll sie nachprüfen können, statt die Recherche zu
> wiederholen.

Zugleich ist das meistimplementierte Einzelfeature aller Konkurrenten „jede N-te
Linie kräftiger", und sein Fehlen die häufigste Nutzerbeschwerde. Das
**Zyklusmodell (§ 5.3) subsumiert das und geht darüber hinaus** — mehrere
unabhängige Zyklen unterschiedlicher Länge für Abstand, Stärke, Größe,
Strichmuster und Farbe. Das ist die tragende Idee des Werkzeugs.

---

## 2. Nicht-Ziele

Bewusst **nicht** gebaut wird:

- **Kein Notensatz.** Nur leere Systeme mit wählbarem Schlüssel. Keine Noten,
  keine Taktstriche, keine Taktangaben.
- **Keine allgemeine Zeichensprache.** Die DSL beschreibt *Strukturen* —
  Familien, Raster, Zeilen und Spalten —, aber **keine Einzelstriche an freien
  Koordinaten**. Das ist die Grenze, nicht die Familienform: Ein Generator darf
  eigene Gesetze rechnen (§ 5.3), solange die Def beschreibt, *was* dasteht, und
  nicht, *wo* jeder Strich anfängt. Wer freie Koordinaten braucht, nimmt SVG oder
  TikZ. (Abgrenzungen im Einzelnen: begrenzte Familien § 7.1, Formularraster
  § 7.8.)
- **Kein Pluginsystem.** Klare Schnittstellen; Beiträge kommen als Pull Request.
- **Kein Reverse Engineering proprietärer Formate.** Nur dokumentierte Wege.
- **Kein Vererbungssystem für Definitionsdateien.** Kopieren ist am Anfang
  ehrlicher als `extends`. Das schließt YAML-Merge-Keys ein (§ 5.4).
- **Keine GUI, auch später nicht.** Weder Desktop noch lokale Web-UI.
- **Keine doppelklickbaren Installer.** Kein PyInstaller, keine Notarisierung.
  Installation über `uvx` bzw. `pip`.
- **Keine Kompensation von Druckertreibern.** Skalierung im Druckdialog ist
  außerhalb unserer Kontrolle (§ 8.2).
- **Keine freien Kurven.** `Arc` deckt Kreisbögen ab; Bézierkurven, Splines und
  beliebige Pfade sind kein Ziel. Sie wären der Einstieg in eine allgemeine
  Zeichensprache.

---

## 3. Architektur

Bild: **ein Taschenmesser** — ein Griff, mehrere Klingen.

Der **Griff** trägt alles Gemeinsame: Seitenformat, Ränder, Musterbereich,
Rahmen, Kopf-/Fußzeile, Stempel, Lochmarken, Seitenschleife, Ausgabe, Presets,
interaktiver Modus. Die **Klingen** (Generatoren) liefern nur Marken.

### 3.1 Schichten

```
CLI
        │
   Loader + Validator      Definitionsdatei → validiertes Modell,
        │                  Einheiten normalisiert (§ 5.1)
   Seitenschleife          für i in 0..n-1: Seitenkontext bauen
        │
   ┌────┴─────┐
Generator   Rahmenwerk     Klinge liefert Marken; Griff liefert
(1 Klinge)  (Kopf/Fuß/     Kopf, Fuß, Rahmen, Stempel, Lochmarken
            Rahmen/…)
        │
   Markenstrom             gemeinsames, kleines Vokabular
        │
   Schreiber               PDF (Pflicht), PNG (später), Fremde (offen)
```

### 3.2 Die drei Nähte

Genau diese drei Schnittstellen sind Vertrag und werden dokumentiert.

1. **Definitionsdatei → Modell.** Validiert, einheitennormalisiert.
2. **Generator → Marken.** Kleines geschlossenes Vokabular (§ 6). Der Generator
   erhält den Seitenkontext **und den Schreiber-Abfragekontext** (§ 10.2) —
   er muss Beschriftungen ausmessen können (Segmentbeschriftung, Gitterlabels).
3. **Marken → Schreiber.** Bidirektional: Marken hinein, Metrik- und
   Fähigkeitsauskünfte heraus (§ 10.2).

### 3.3 Harte Regeln

- **`reportlab` (bzw. jede PDF-Bibliothek) darf ausschließlich im PDF-Schreiber
  vorkommen.** Kein Generator importiert sie.
- **Einheiten werden beim Einlesen normalisiert.** **Positionen und Abstände in
  ganzzahligen Mikrometern (int µm)**, weil sie sich aufsummieren (§ 8.2).
  **Strichstärken, Durchmesser und Deckkraft bleiben Fließkomma** — sie
  akkumulieren nie, und µm wäre für sie zu grob: 0,1 pt sind 35 µm, ein
  Rundungsschritt also 3 %, was bei feinen Rastern sichtbar wird.
  Der **Rohwert samt Originaleinheit wird für Fehlermeldungen mitgeführt** —
  „52,9 µm" ist als Fehlertext unbrauchbar, wenn der Nutzer `0.15pt` schrieb.
- **Zufall ist reproduzierbar oder gar nicht.** Wo prozedural erzeugt wird
  (§ 7.5), speist ein **explizit benannter stabiler Hash** den Generator —
  `blake2b` über `seed` und Seitenindex, daraus die PRNG-Saat. Pythons
  eingebautes `hash()` ist dafür untauglich: Es ist über Versionen hinweg nicht
  garantiert und für Strings prozessabhängig. Sonst bricht die
  Reproduzierbarkeitszusage aus § 10.1 bei jedem Python-Update.
- **Generatoren kennen keine Seitenränder**, nur ihren Musterbereich in lokalen
  Koordinaten.
- **Marken werden als Strom geliefert, nicht als Liste.** Ein Generator gibt
  einen `Iterator[Mark]` zurück, der Schreiber schreibt seitenweise. Bei 200
  Seiten Punktraster liegen sonst Hunderttausende Objekte gleichzeitig im
  Speicher.
- **Jeder Generator meldet, ob er seitenunabhängig ist** (`is_page_invariant`).
  Ist er es, darf der Schreiber das Muster einmal ablegen und je Seite
  referenzieren (§ 10.1). Das ist eine Naht-2-Eigenschaft und muss von Anfang an
  im Vertrag stehen. **Bei `duplex: true` (§ 8.1) ist der Musterbereich auf
  geraden und ungeraden Seiten verschieden — dann gilt `is_page_invariant`
  unabhängig vom Generator als falsch, und das Einrasten wird einmal für beide
  Seitensorten gemeinsam gelöst**, nicht je Seite. Sonst löste es unterschiedlich
  auf, und genau das sähe man beim Durchblättern.

### 3.4 Sprache

**Code, Modulnamen, DSL-Schlüssel, Fehlermeldungen, Presetnamen und
Dokumentation sind englisch.** Ohne Ausnahme und ohne Übersetzungsschicht.
Dieses Pflichtenheft bleibt deutsch — internes Entwurfsdokument, nicht Teil des
Repositories.

### 3.5 Koordinatenursprung

**Links unten**, x nach rechts, y nach oben. Gilt für Blatt- und lokale
Musterkoordinaten. Begründung: PDF rechnet so. Der spätere PNG-Schreiber
spiegelt einmal zentral. Winkel: **mathematisch positiv, 0° zeigt nach rechts.**

### 3.6 Die Nähte als Signaturen

§ 3.2 nennt drei Schnittstellen „Vertrag". Ein Vertrag in Prosa ist keiner —
hier stehen sie als Code. Verbindlich sind die **Formen**, nicht die exakte
Python-Schreibweise.

#### Gemeinsame Typen

```python
Um = int                      # Länge in Mikrometern (§ 3.3)
Mm = float                    # Länge in Millimetern, für Stärken und Größen
Color = str                   # "#rrggbb"

class Layer(Enum):
    PATTERN = 1               # Muster (Generator)
    FRAME   = 2               # Kopf, Fuß, Rahmen, Lochmarken
    OVERLAY = 3               # Stempel

@dataclass(frozen=True)
class Area:                   # der Musterbereich, in LOKALEN Koordinaten
    width:  Um                # Ursprung ist stets (0, 0) links unten
    height: Um

@dataclass(frozen=True)
class PageContext:
    index:      int           # 0-basiert, Deckblatt nicht mitgezählt
    number:     int           # 1-basiert, das was {page} liefert
    count:      int           # das was {page_count} liefert
    name:       str | None    # Eintrag der Namensliste, sonst None
    is_even:    bool          # für duplex (§ 8.1)
    seed_material: bytes      # stabil aus seed + index (§ 3.3)
```

#### Naht 1 — Definitionsdatei → Modell

```python
def load(source: Path | str, overrides: Mapping[str, Any]) -> Document
```

`overrides` sind die CLI-Werte; sie schlagen die Def ausnahmslos (§ 11).
Das Ergebnis ist vollständig validiert und einheitennormalisiert — **nach
`load` gibt es keine Strings mit Einheiten mehr im Kern.**

#### Naht 2 — Generator → Marken

```python
class Generator(Protocol):
    name: str                                   # Registry-Schlüssel
    config_model: type[BaseModel]               # eigener Def-Abschnitt

    def is_page_invariant(self, cfg) -> bool: ...

    def generate(
        self,
        cfg,                      # validierter Generator-Abschnitt
        area: Area,               # lokale Koordinaten, kein Wissen über Ränder
        page: PageContext,
        q: WriterQuery,           # Textmetrik (§ 10.2)
    ) -> Iterator[Mark]: ...
```

Drei Regeln, die aus der Signatur nicht ablesbar sind:

- **Der Generator liefert lokale Koordinaten** mit Ursprung links unten im
  Musterbereich. Die Verschiebung ins Blattkoordinatensystem (§ 6) macht das
  Rahmenwerk beim Verlassen des Generators. Nur so bleibt § 3.3 wahr, dass
  Generatoren keine Ränder kennen.
- **Alle gelieferten Marken tragen `Layer.PATTERN`.** Kopf, Fuß, Rahmen und
  Stempel liefert der Griff.
- **`generate` ist ein Generator im Python-Sinn** — es wird geyieldet, nicht
  gesammelt (§ 3.3).

#### Naht 3 — Marken → Schreiber

```python
class WriterQuery(Protocol):        # nur Fragen, keine Ausgabe
    def capabilities(self) -> set[str]: ...
    def text_width(self, content: str, font: Font, size: Mm) -> Mm: ...
    def text_metrics(self, font: Font, size: Mm) -> tuple[Mm, Mm]:  # ascent, descent
        ...
    def missing_glyphs(self, content: str, font: Font) -> list[str]: ...

class Writer(WriterQuery, Protocol):
    def begin_document(self, meta: DocumentMeta) -> None: ...
    def begin_page(self, width: Um, height: Um) -> None: ...
    def draw(self, mark: Mark) -> None: ...
    def end_page(self) -> None: ...
    def end_document(self) -> None: ...
```

`text_metrics` ist nicht schmückend: § 8.4 verlangt zu prüfen, ob die
Schriftgröße in die Kopfhöhe passt, und dafür braucht es Ober- und Unterlänge.

**Der Schreiber sortiert nicht.** Marken kommen bereits in Ebenenreihenfolge
(§ 6); er zeichnet, was ihm gereicht wird, in der Reihenfolge des Eingangs.
Sortieren im Schreiber hieße, den Markenstrom doch wieder zu sammeln.

---

## 4. Kernbegriffe

| Begriff | DSL-Schlüssel | Bedeutung |
|---|---|---|
| **Blatt** | `page` | Physisches/virtuelles Papier: Format oder Gerät, Ausrichtung |
| **Musterbereich** | — | Was nach Rändern, Kopf, Fuß und Freiraumzeilen übrig bleibt (**Rechenweg in § 8.1**). **Ursprung aller Musterkoordinaten.** |
| **Musterblock** | `pattern` | Def-Abschnitt für Anker, Einrasten und Restbehandlung — nicht der Bereich selbst |
| **Familie** | `families[]`, `rings`, `spokes` | Periodische Schar gleichartiger Marken. Nicht jeder Generator hat Familien — `maze`, `form` und `tiling` rechnen anders (§ 5.3) |
| **Zyklus** | z. B. `spacing` | Liste dimensionsloser Vielfacher, die sich wiederholt |
| **Basis** | z. B. `base_spacing` | Absoluter Bezugswert für die Vielfachen |
| **Gesetz** | `law` | Verteilung innerhalb der Periode: `linear` oder `log10` (§ 7.9) |
| **Generator** | `generator` | Eine Klinge (§ 7) |
| **Marke** | — | Kleinste Ausgabeeinheit (§ 6) |
| **Schreiber** | — | Backend, das Marken in ein Ausgabeformat schreibt |

---

## 5. Definitionsdatei

### 5.1 Format

**YAML.** Das Herzstück (`families`) ist eine Liste verschachtelter Objekte, und
dafür ist YAML die lesbarste Syntax. Da die Presets zugleich die Dokumentation
sind (§ 9.3), zählt Lesbarkeit mehr als die Fallenfreiheit von TOML.

**Pflichtregeln:**

- **Versionszeile obligatorisch** (`version: 1`).
- **Unbekannte Schlüssel sind ein Fehler.** Ein Tippfehler in einer verbogenen
  Preset-Kopie erzeugt sonst ein PDF, das *fast* stimmt — die schlimmste
  Fehlerklasse.
- **Einheit steht am Wert**, nicht in einem Kopf-Abschnitt.
- **In Zahlzyklen stehen nur nackte Zahlen.** Absolute Werte ausschließlich in
  `base_*`. Einzige Ausnahme: Farbzyklen (§ 5.3).

**Erlaubte Einheiten:**

| Art | Einheiten | Geltung |
|---|---|---|
| Länge | `mm`, `cm`, `in`, `pt` | überall |
| Länge | `px` | nur mit Geräteprofil (§ 9.2) |
| Winkel | `deg` | überall |
| Dichte | `dpi` | nur in Geräteprofilen |
| **Anteil** | `%` | nur wo ein Bezugsmaß feststeht (§ 7.8) |
| **Generatorlokal** | `sp` (stave spaces) | nur in `staves` (§ 7.3) |

`in` und `cm` sind nicht optional: Wir liefern `letter`, `legal` und `tabloid`
aus, und ¼-Zoll-Raster ist dort der Normalfall.

**Schlüsselwörter statt Zahl.** An einigen Stellen steht kein Maß, sondern eine
Anweisung, es zu bestimmen: `auto` (das Werkzeug rechnet es aus — Mittelpunkt
und Außenradius bei `polar`, Stempelgröße), `rest` (der verbleibende Platz,
§ 7.8) und `none` (nicht vorhanden). Sie sind **keine Einheiten** und stehen
ohne Zahl. Wo sie erlaubt sind, sagt der jeweilige Abschnitt; anderswo sind sie
ein Fehler.

**Generatorlokale Einheiten** sind Einheiten, deren Bezugswert erst aus dem
Generatorabschnitt hervorgeht. Sie sind ausdrücklich vorgesehen, aber
**ausschließlich innerhalb ihres Generators gültig** — außerhalb fehlt der
Bezug, und ihre Verwendung ist ein Fehler. Weitere sind absehbar (§ 15, Punkt 4);
`sp` ist der Musterfall, an dem sich der Mechanismus zeigt.

Folge für die Normalisierung (§ 3.3): Sie läuft **zweistufig** — erst die
allgemeinen Einheiten, dann je Generator die lokalen, sobald deren Bezugswert
feststeht.

### 5.2 Aufbau

```yaml
version: 1

defs:                        # nur Ankerablage, von der Validierung ignoriert (§ 5.4)
  grid:   &grid   "#7799bb"
  accent: &accent "#4466aa"

# ---------- Griff ----------
page:
  format: a4                 # aus Formattabelle; ODER device: remarkable-2
                             # ODER frei: 210x99mm / 8.5x11in
  orientation: portrait      # portrait | landscape
  duplex: false              # true → inner/outer tauschen auf geraden Seiten
  margin:                    # nicht bedruckbarer Rand (§ 8.1)
    top: 5mm                 # Default aus Format- bzw. Geräteprofil
    bottom: 5mm
    inner: 5mm               # links auf Vorderseiten
    outer: 5mm               # rechts auf Vorderseiten
  background: none           # none | "#rrggbb"
  hole_marks: false          # ISO 838 Lochmarken (§ 8.7)

border:                      # optional, sitzt am Musterbereich
  weight: 0.6pt
  color: "#000000"
  gap: 0mm                   # Luft zwischen Rahmen und Muster

header:
  height: 12mm               # FIX, inhaltsunabhängig (§ 8.4)
  gap: 4mm                   # Freiraumzeile zum Musterbereich
  cut: false                 # true = zu langen Text kürzen statt abbrechen (§ 8.9)
  font: { family: sans, size: 9pt }   # § 10.3
  left:   { image: "logo.png", height: 8mm }
  center: "Class 3B"
  right:  "{name}"

footer:
  height: 8mm
  gap: 4mm
  cut: false
  left:   "Per aspera ad astra"
  center: "{page} / {page_count}"
  right:  "A. Erben"

stamp:                       # optional; besser per CLI-Flag (§ 8.6)
  text: "DRAFT"
  angle: 45deg
  opacity: 0.08
  size: auto

pattern:
  anchor: pattern_area       # einziger erlaubter Wert in v1
  snap:      { x: none,   y: none   }   # none | spacing | cycle | pixel
  remainder: { x: center, y: center }   # end | center | whole_cycles
                                        # Skalar als Kurzform für beide Achsen

pages:
  count: 30
  cover: false               # Deckblatt mit Kalibrierquadrat (§ 8.8)

# ---------- Klinge ----------
generator: lines
families:
  - direction: horizontal
    base_spacing: 1mm
    spacing: [1]
    base_weight: 0.15pt
    weight: [1, 1, 1, 1, 2.7]
    style: solid
    color: [*grid, *grid, *grid, *grid, *accent]
```

### 5.3 Zyklen — das Kernkonzept

**Ein Mechanismus, sieben Anwendungen.** Eine zyklische Liste, deren Einträge
positionsweise auf die laufenden Marken angewendet werden:

| Anwendung | Basis | Zyklus | Einträge |
|---|---|---|---|
| Abstände | `base_spacing` | `spacing: [1, 1, 2]` | Vielfache |
| Radien (polar) | `base_radius` | `radius: [1, 1, 2]` | Vielfache |
| Winkel (polar) | `base_angle` | `angle: [1, 1, 2]` | Vielfache |
| Strichstärken | `base_weight` | `weight: [1, 1, 1, 1, 2.7]` | Vielfache |
| Punktgrößen | `base_size` | `size_x` / `size_y: [1, 1, 1, 1, 2]` | Vielfache |
| Strichel-/Punktmuster | `base_dash` | `dash: [2, 1]` | Vielfache |
| **Farben** | — | `color: [*grid, *accent]` | **Hex-Literale** |

**Regeln:**

- **Farbe ist die einzige Anwendung ohne Basis.** Hex-Werte sind keine
  Vielfachen; der Zyklus enthält die Literale direkt.
- Ein Farbfeld akzeptiert **entweder einen Hex-String** (gilt für alle Marken)
  **oder eine Liste** (Zyklus).
- **Format `#rrggbb`, sechsstellig, RGB.** Keine achtstellige Alpha-Variante,
  keine Farbnamen, kein CMYK. Deckkraft ist ein eigenes Feld.
- Zyklen **verschiedener Anwendungen dürfen unterschiedlich lang sein** und
  laufen unabhängig.

**Effektive Periode — zwei Größen, die nicht verwechselt werden dürfen:**

- **Periode in Marken** = kgV der Längen aller Zyklen der Familie.
- **Periode in Millimetern** = `sum(spacing) × base_spacing × (Marken-Periode ÷ len(spacing))`.

Beim Einrasten (§ 8.3) ist die **mm-Periode** maßgeblich. Das Werkzeug gibt beide
Größen beim Erzeugen aus („pattern repeats every 5 lines = 35.0 mm").

**Grenze des Modells — und was sie nicht bedeutet:** Zyklen sind periodisch.
Nichtperiodische Abstandsgesetze sind *im Zyklusmechanismus* nicht ausdrückbar —
mit einer Ausnahme, die keine ist: Logarithmisches Papier *ist* periodisch, nur
mit ungleichmäßiger Binnenverteilung. Dafür gibt es `law` (§ 7.9).

**Das ist eine Grenze des Zyklusmechanismus, nicht des Werkzeugs.** Ein Generator
ist frei, seine Marken beliebig zu berechnen; Familien und Zyklen sind ein
gemeinsames Angebot, keine Pflicht. Deshalb sind konvergierende Raster
(Perspektive) oder rotationssymmetrische Motive (Mandala) sehr wohl möglich —
eben als **eigene Klingen** mit eigenen Parametern (§ 7.11), so wie `maze` auch
nichts mit Zyklen zu tun hat. Was ausgeschlossen bleibt, ist nur, solche Muster
in Familien *hineinzuzwingen*.

### 5.4 Anker und Aliasse

YAML kennt keine Variablen, aber **Anker (`&`) und Aliasse (`*`)**. Erlaubt und
erwünscht, vor allem für Farben:

```yaml
defs:
  grid: &grid "#7799bb"
# …
    color: [*grid, *grid, *grid, *grid, *accent]
```

**`defs` ist ein reservierter Top-Level-Schlüssel**, den die Validierung
überspringt. Ohne ihn wären Anker unbrauchbar, weil § 5.1 unbekannte Schlüssel
verbietet.

**Grenzen — bewusst nicht umgangen:** keine Arithmetik, keine
String-Interpolation, kein Kürzen von Zyklen, nur innerhalb einer Datei.

**Merge-Keys (`<<:`) sind verboten.** Sie sind Vererbung und damit Nicht-Ziel
(§ 2) — nur eines, das der Parser mitbringt. Sie müssen **aktiv erkannt und
abgelehnt** werden. Meldung: *„merge keys (`<<`) are not supported — copy the
block instead."*

**Expansionsgrenze.** Verschachtelte Aliasse lassen sich zu einer YAML-Bombe
stapeln; der sichere Lademodus schützt davor **nicht** — er verhindert nur die
Ausführung beliebiger Objekte, nicht die Expansion. Da Defs aus fremden
Repositories kopiert werden, ist eine Obergrenze erforderlich, mit klarem
Abbruch statt Speicherfehler.

---

## 6. Marken-Vokabular (Naht 2)

**So klein wie möglich.** Jedes Primitiv ist Arbeit für *jeden* künftigen
Schreiber. Kargheit ist das, was einen Fremdschreiber an einem Abend
schreibbar macht.

| Marke | Felder |
|---|---|
| `Segment` | from (x,y), to (x,y), weight, color, dash, cap, opacity |
| `Arc` | center (x,y), radius, start_angle, sweep, weight, color, dash, opacity |
| `Dot` | pos (x,y), diameter, color, opacity |
| `Polygon` | points[], closed, weight, color, fill_color, opacity |
| `Text` | pos, content, font, size, align, angle, color, opacity |
| `Image` | pos, width/height, source (PNG; SVG ab M5) |

Sechs Primitive. Alle Farben `#rrggbb`.

**Koordinaten: zwei Systeme, ein Übergang.** Ein Generator rechnet in **lokalen
Koordinaten** mit Ursprung links unten im Musterbereich und kennt keine Ränder
(§ 3.3). Eine fertige Marke trägt dagegen **Blattkoordinaten**, Ursprung links
unten im Blatt. Die Verschiebung macht das Rahmenwerk beim Verlassen des
Generators — sie ist eine Addition und steht an genau einer Stelle. Ohne diese
Trennung müsste jeder Generator die Seitengeometrie kennen.

**Einheiten der Felder:** Positionen und Längen als `int` in Mikrometern,
Strichstärken, Durchmesser und Deckkraft als `float` (§ 3.3), Winkel in Grad.

**Begründungen zum Zuschnitt:**

- **`Arc`** deckt Vollkreise (`sweep: 360deg`), Ringe und Segmentbögen ab und ist
  die Voraussetzung für Polarraster (§ 7.6) und spätere Mandalas. PDF, SVG und
  Pillow haben Bögen nativ.
- **`Polygon` ersetzt `Rect`** — ein Rechteck ist ein Viereck. Damit sind
  Sechsecke, Dreiecke und Rauten der Kachelgeneratoren abgedeckt, ohne dass das
  Vokabular um zwei statt um eins wächst.
- **`Dot` bleibt trotz `Arc` erhalten**, weil Punktraster der
  performancekritische Pfad ist (§ 10.1) und eine eigene Optimierung braucht.
- **Keine Bézierkurven, keine freien Pfade** (§ 2).

Marken tragen eine **Ebene** (`pattern`, `frame`, `overlay`). Der Schreiber malt
in dieser Reihenfolge.

---

## 7. Generatoren (Klingen)

### 7.1 `lines`

Beliebig viele Familien. Deckt kariert, liniert, isometrisch, Kalligraphie,
logarithmisch und Cornell ab.

```yaml
families:
  - direction: horizontal     # horizontal | vertical | <angle>deg
    law: linear               # linear | log10 (§ 7.9)
    base_spacing: 2mm
    spacing: [2, 1, 1, 3]     # Kalligraphie: x-Höhe, Ober-, Unterlänge, Zeilenluft
    base_weight: 0.15pt
    weight: [2, 1, 1, 1]
    style: solid              # solid | dashed | dotted
    base_dash: 1mm
    dash: [2, 1]
    color: "#000000"
    extent: { start: 0mm, end: 100mm }   # Ausdehnung quer zur Laufrichtung
    offset: 0mm               # Verschiebung des Zyklusbeginns
  # count: 1                  # optional; fehlt = unbegrenzt (siehe unten)
    governing: false          # für Einrasten (§ 8.3)
```

**`count` — begrenzte Familien.** `count: 1` erzeugt genau eine Linie. **Fehlt
der Schlüssel, ist die Familie unbegrenzt** — es gibt bewusst keinen Magic-String
`unlimited`: Ein Feld, das entweder ein Wort oder eine Zahl ist, erzwingt eine
Union im Modell und liefert schlechte Fehlermeldungen. Das ist
kein Widerspruch zum Nicht-Ziel „freie Einzelstriche" (§ 2): Eine begrenzte
Familie hat weiterhin Richtung, Zyklusbeginn, Stärke und Farbe aus demselben
Modell; sie ist nur endlich. Damit werden ausdrückbar:

- die rote **Randlinie** im Schulheft
- die zwei Senkrechten eines **Cornell-Layouts**
- Trennlinien in Wertungsblättern

Ohne `count` wäre für jede dieser Alltagsformen ein eigener Generator nötig.

**Schräge Familien (`<angle>deg`) — festgelegte Semantik:**

- `base_spacing` ist der **senkrechte Abstand** zwischen benachbarten Linien,
  nicht der Abstand entlang einer Achse.
- `offset` und `extent` werden ebenfalls **senkrecht zur Linienrichtung**
  gemessen.
- Jede Linie wird am Musterbereich-Rechteck **geclippt**.
- **Einrasten ist für schräge Familien nicht unterstützt** — Fehler, kein Raten.
  Eine schräge Familie meldet dem Griff **gar keine periodische Achse** (§ 8.3);
  damit gilt die Regel, ohne dass der Griff je erfährt, was ein Winkel ist.
  `governing: true` und `law: log10` sind an einer schrägen Familie ebenfalls
  Fehler — beides braucht eine Achse, die es dort nicht gibt.

**Wo Linie 0 liegt (festgelegt beim Bau, 2026-07):** auf dem **Ursprung des
Musterbereichs**, genau wie bei einer waagrechten Familie — dieselbe Regel,
verallgemeinert, nicht eine zweite. Eine unbegrenzte schräge Familie füllt die
Fläche von dort aus nach **beiden** Seiten der Senkrechten; bei waagrecht und
senkrecht liegt ohnehin alles auf der positiven Seite, dort ändert das nichts,
bei 45° ist es die einzige Art, das Blatt zu decken. Rückwärts heißt dabei: der
Zyklus **rückwärts gelesen**, nicht die Vorwärtspositionen negiert — `[2, 1]`
schreitet abwärts erst 1, dann 2, sonst verschöbe sich das Muster um einen
Schritt. `count: n` zählt weiterhin n Linien ab Linie 0 in Zyklusrichtung, und
weil es Linien unterhalb von Linie 0 gibt, sind **negative senkrechte
Koordinaten** zulässig: `extent: { start: -40mm }` ist sinnvoll.

Die Senkrechte ist die um 90° gedrehte Linienrichtung, im Vorzeichen so
gewählt, dass sie **zur Fläche zeigt** — nur so zählt `90deg` in das Blatt
hinein wie `vertical` und nicht aus ihm heraus. Liegt die Mitte der Fläche
genau auf Linie 0 (die Diagonale eines Quadrats), bleibt die kanonische
Drehung stehen; geraten wird nie.

### 7.2 `dots`

```yaml
generator: dots
grid:
  x: { base_spacing: 5mm, spacing: [1] }
  y: { base_spacing: 5mm, spacing: [1] }
base_size: 0.3mm
size_x: [1, 1, 1, 1, 2]
size_y: [1, 1, 1, 1, 2]
combine: max                # max | product | intersection_only
color: "#888888"            # Einzelwert ODER Achsenform (siehe unten)
```

**`combine`** beantwortet die Frage, die sonst der Parser raten müsste:
`max` → Kreuzgitter; `product` → Kreuzungen am größten; `intersection_only` →
nur wo beide Zyklen betont sind.

**Farbe braucht eine ausdrückliche Achse.** `max("#888888", "#cc0000")` bedeutet
nichts, und jede Mischregel wäre geraten:

```yaml
color:
  axis: cross               # x | y | cross
  cycle: [*grid, *grid, *grid, *grid, *accent]
```

`x`/`y` → Farbstreifen; `cross` → betonter Eintrag, sobald **Spalte oder Reihe**
an betonter Position steht (farbiges Kreuzgitter, Gegenstück zu `combine: max`).
Ein Farbzyklus ohne `axis` ist ein **Validierungsfehler**, kein geratener
Default.

### 7.3 `staves`

```yaml
generator: staves
count: 10
stave_space: 1.75mm         # Abstand benachbarter Linien (Rastralmaß)
                            # ODER stave_height: 7mm — schließen sich aus
system_gap: 4sp             # LÜCKE zwischen den Systemen (§ unten)
lines: 5                    # 5 = Notensystem, 6 = Gitarren-Tab
weight: 0.2pt
clef: treble                # treble | bass | alto | tenor | none
clef_indent: 3mm
```

Intern: gruppierte Linienfamilie + optionaler Glyph am Zeilenanfang.
**Schlüsselglyphen aus einer eingebetteten Musikschrift** (§ 15.3) — subgesettet,
macht das PDF selbsttragend, ohne das Markenvokabular zu vergrößern. Ursprünglich
waren fest hinterlegte Vektorpfade vorgesehen; warum daraus eine `Text`-Marke
wurde, steht in § 15.3. Umgesetzt in M9: `clef: treble | bass | alto | tenor`
(nur am Fünfliniensystem), Größe und Lage nach SMuFL — ein Em sind vier
Zeilenabstände, der Glyph-Ursprung sitzt auf der Referenzlinie.

**Zwei Wege, dieselbe Systemgröße anzugeben** — `stave_space` (Abstand
benachbarter Linien) oder `stave_height` (oberste bis unterste Linie). Sie
schließen einander aus; beides gesetzt ist ein Fehler. Umrechnung:

```
stave_space = stave_height ÷ (lines − 1)
```

Bei `lines: 5` und `stave_height: 7mm` also 1,75 mm — die Zahlen im Beispiel
oben. Achtung: Der Divisor hängt an `lines`, bei Tabulatur (`lines: 6`) ist er
also 5, nicht 4.

`stave_space` ist die typografisch übliche Größe und der Bezug für die Einheit
`sp`.

**`system_gap` ist die Lücke, nicht der Achsabstand** — gemessen von der
untersten Linie eines Systems zur obersten Linie des nächsten. Diese Definition
ist unabhängig von `lines` und deshalb die robustere: Wer von Notensystem auf
Tabulatur umstellt, will nicht, dass sich der optische Abstand ändert.

Der Name ist bewusst nicht `stave_spacing`: Ein Feld, das sich von `stave_space`
nur durch drei Buchstaben unterscheidet und etwas völlig anderes bedeutet, wird
verwechselt — beim Schreiben der Def wie beim Lesen des Codes.

**Die Einheit `sp` (stave spaces)** ist überall dort erlaubt, wo `staves` Längen
entgegennimmt — vor allem in `system_gap` und `clef_indent`. Der Grund ist
praktisch: Wird der Systemabstand in Notenzeilenabständen angegeben, bleibt das
Blatt bei jeder Systemgröße richtig proportioniert. Bei fester Millimeterangabe
muss man ihn nach jeder Größenänderung neu ausrechnen.

`sp` ist eine **generatorlokale Einheit** (§ 5.1) und außerhalb von `staves`
nicht gültig. Die Normalisierung löst sie in der zweiten Stufe auf, sobald
`stave_space` feststeht.

Nummerierte Rastralgrößen (0–8) sind bewusst **noch nicht** hinterlegt. Es
kursieren zwei Konventionen:

- **historisch:** die Nummer meint die **Gesamthöhe des Fünfliniensystems**
  (grob 9 mm bei Rastral 0 bis 4 mm bei Rastral 8)
- **modern:** angegeben wird der **Zeilenabstand** (calcbe bietet 1,6 / 2,0 /
  3,0 mm)

Beide sind unbelegt, siehe [`docs/research.md`](research.md) § 8. Falsche
Zahlen wären hier genauso schädlich wie falsche Gerätemaße (§ 9.2), deshalb erst
belegen, dann ausliefern (§ 15, Punkt 4).

### 7.4 `grid`

Anzahlgetrieben statt abstandsgetrieben. **In v1 genau ein Block pro Seite**,
zentriert im Musterbereich. Mehrere Blöcke mit Positionierung wären ein
Layoutsystem durch die Hintertür.

```yaml
generator: grid
cells: { x: 10, y: 10 }
labels:                     # Zählmuster, § 7.10
  columns: "A"              # A, B, C … J
  rows: "n"                 # 1, 2, 3 … 10
weight: 0.3pt
color: "#000000"
fill: checker               # none | checker | rows | columns
fill_color: "#eeeeee"
header_row: false
```

### 7.5 `maze`

```yaml
generator: maze
cells: { x: 20, y: 28 }
algorithm: backtracker      # backtracker | prim | kruskal
start: bottom-left
goal: top-right
min_path_factor: 0.5        # garantierte Mindestlänge der Lösung
wall_weight: 0.5pt
color: "#000000"
seed: 4711                  # effektiv = blake2b(seed, page_index)
solution: none              # none | overlay | separate_page | back_mirrored
```

**Nur rechteckige Gittermazes in v1.**

**Kein `complexity`-Regler.** Für die drei Algorithmen gibt es keinen
gemeinsamen 0..1-Parameter; die Charakteristik ist die Algorithmuswahl.

**`min_path_factor` ist kein Luxus.** Ein naiver Generator erzeugt regelmäßig
Labyrinthe, deren Lösungsweg lächerlich kurz ist, obwohl das Bild komplex
aussieht. Die Mindestlänge wird gegen `factor × cells_x × cells_y` geprüft und
bei Unterschreitung neu erzeugt.

**Seed über stabilen Hash, nicht über Addition** — `seed + i` erzeugt bei manchen
PRNGs korrelierte Nachbarseiten. Welcher Hash, ist keine Geschmacksfrage: Er muss
über Python-Versionen und Prozesse hinweg identisch bleiben, sonst ist die
Reproduzierbarkeitszusage wertlos (§ 3.3).

#### Lösungsseiten

| `solution` | Ergebnis |
|---|---|
| `none` | nur Rätsel |
| `overlay` | Lösung auf demselben Blatt über das Labyrinth gezeichnet |
| `separate_page` | Rätsel und Lösung abwechselnd auf eigenen Seiten |
| `back_mirrored` | wie `separate_page`, Lösung aber **seitenverkehrt** (§ unten) |

**Zählung bei `separate_page` und `back_mirrored`:** Alle Seiten werden
fortlaufend nummeriert. **Ungerade Seiten sind Rätsel, gerade sind Lösungen.**
`{page_count}` ist also die doppelte Rätselzahl, und `--pages 10` ergibt zehn
Rätsel auf zwanzig Blättern. Bei einer Namensliste bekommt jeder Eintrag
folglich zwei Seiten; beide tragen denselben `{name}`.

Der **Seitenindex für den Seed** ist der des Rätsels: Seite 2 zeigt die Lösung
zu Seite 1, nicht ein neues Labyrinth.

#### `back_mirrored` — die Lösung durchscheinen lassen

Beidseitig gedruckt, Rätsel vorn, Lösung hinten. Hält man das Blatt gegen das
Licht, deckt sich die Lösung mit dem Labyrinth — **wenn** sie spiegelverkehrt
aufgebracht ist, denn von vorn betrachtet erscheint die Rückseite gespiegelt.

Gespiegelt wird an der **senkrechten Mittelachse des Blattes**, nicht des
Musterbereichs. Bezugspunkt ist die physische Wendekante, und die liegt am
Blatt.

**Drei Bedingungen, sonst passt es nicht übereinander:**

- **Wenden über die lange Kante** wird vorausgesetzt — die übliche
  Duplex-Voreinstellung. Wer über die kurze Kante wendet, bekommt die Lösung
  auf dem Kopf; das gehört ins README (§ 13.3).
- **`duplex: true` mit ungleichen Rändern ist ein Fehler.** Der wechselnde
  Bundsteg (§ 8.1) verschiebt den Musterbereich zwischen Vorder- und Rückseite,
  und genau um diesen Betrag läge die Lösung daneben. Entweder `duplex: false`
  oder `inner` gleich `outer`.
- **Gespiegelt wird nur die Musterebene.** Kopf und Fuß bleiben normal, damit
  sie auf der Rückseite lesbar sind — sie sollen ja nicht durchscheinen.

Papierstärke und Opazität bestimmen, ob es funktioniert; das liegt außerhalb
unserer Kontrolle und gehört ebenfalls ins README.

### 7.6 `polar`

Ring- und Speichenfamilien. Deckt Zielscheiben, Wertungsscheiben, Polarpapier
und Winkelraster ab.

```yaml
generator: polar
center: auto                # auto (Mitte des Musterbereichs) | { x:, y: }
outer_radius: auto          # auto (halbe kürzere Seite) | <länge>
rings:
  base_radius: 10mm
  radius: [1, 1, 1, 2]
  base_weight: 0.2pt
  weight: [1, 1, 1, 2]
  color: [*grid, *grid, *grid, *accent]
spokes:
  base_angle: 30deg
  angle: [1, 1, 2]
  base_weight: 0.2pt
  weight: [1, 1, 2]
  radial_extent: { start: 0mm, end: auto }   # von wo bis wo die Speiche läuft
labels:
  spokes: "n"               # Zählmuster, § 7.10 — hier 1 … 12
  spoke_radius: 0.85        # Anteil des Außenradius
  rings: [10, 8, 6, 4]      # z. B. Punktwertung von außen nach innen
  font: { family: sans, size: 8pt }
```

**Das Zyklusmodell überträgt sich unverändert** — Basis mal dimensionslose
Vielfache, zyklisch, nur in Polarkoordinaten. Zwei Familienarten statt
horizontal/vertikal; Stärke-, Farb- und Strichzyklen funktionieren identisch.
Das ist zugleich der beste Härtetest der Architektur (§ 14).

**Festgelegte Regeln:**

- **Mittelpunkt** = Mitte des Musterbereichs, **Außenradius** = halbe kürzere
  Seite, beides überschreibbar.
- **`radial_extent`, nicht `extent`.** In § 7.1 misst `extent` *quer* zur
  Laufrichtung der Linien; hier läuft die Begrenzung *entlang* der Speiche.
  Derselbe Schlüsselname für zwei verschiedene Bezugsachsen wäre eine Falle,
  deshalb ein eigener Name.
- **Einrasten ist bei `polar` nicht unterstützt** — Fehler, kein Raten.
- **Segmentbeschriftungen werden vorab ausgemessen** (§ 10.2). „12" in ein
  15°-Segment am Innenradius passt nicht, und das muss vor dem Rendern
  auffallen.

### 7.7 `tiling`

Kachelmuster aus geraden Kanten. Deckt Sechseckpapier, Dreiecksraster und
Ausmalmuster ab.

```yaml
generator: tiling
shape: hex                  # hex | tri | square | rhombus | octagon_square
size: 8mm                   # Kantenlänge
orientation: pointy         # pointy | flat  (nur bei hex)
weight: 0.4pt
color: "#333333"
fill: none                  # none | cycle
fill_colors: ["#ffffff", "#eeeeee", "#dddddd"]   # 2-/3-Färbung
labels: none                # none | coordinates
```

**Geteilte Kanten dürfen nur einmal gezeichnet werden.** Wer Kacheln als
geschlossene Polygone ausgibt, malt jede Innenkante doppelt — bei niedriger
Deckkraft sofort sichtbar, und die Dateigröße verdoppelt sich. Der Generator
liefert daher `Segment`-Marken für das Kantennetz und `Polygon`-Marken
ausschließlich für Füllungen.

Die 2- und 3-Färbung von Sechsecken fällt aus dem Farbzyklus praktisch heraus
und ist der Ausmal-Anwendungsfall.

### 7.8 `form`

Ausfüllbare Formulare: Telefonprotokoll, Laufzettel, Übergabeprotokoll,
Beobachtungsbogen.

**Zeilen zuerst, dann Spalten.** Nicht ein globales Raster wie CSS Grid, sondern
eine Folge von Zeilen, deren jede ihre eigene Spaltenaufteilung hat.

Begründung: Formulare werden zeilenweise gedacht und beschrieben („oben drei
Felder nebeneinander, darunter eine breite Notizfläche"). Ein globales
Spaltenraster erzwingt dagegen den gemeinsamen Nenner: Drei gleiche Felder über
einer 25/50/25-Zeile brauchen zwölf Spalten und Spannen von 4/4/4 und 3/6/3 —
technisch möglich, aber unlesbar, und die Presets sind Dokumentation (§ 9.3).

```yaml
generator: form
gap: 2mm                    # Luft zwischen den Feldern
weight: 0.3pt
color: "#000000"
title:
  font: { family: sans, size: 7pt }
  position: above           # above | inline | none

rows:
  - height: 20%             # ein Fünftel der verfügbaren Höhe
    columns:                # ohne width: alle gleich breit
      - { title: "Datum" }
      - { title: "Uhrzeit" }
      - { title: "Anrufer" }

  - height: 25%
    columns:
      - { title: "Firma" }
      - { title: "Betreff", width: 50% }   # der Rest teilt sich 25 / 25
      - { title: "Dringend", kind: choice, options: ["Ja", "Nein"] }

  - height: rest            # der ganze verbleibende Platz
    columns:
      - { title: "Notiz", line_spacing: 8mm }
```

Das ist dieselbe Beschreibung, die man mündlich gäbe — und genau deshalb ist es
die richtige Struktur.

#### Maße für Zeilen und Spalten

| Angabe | Bedeutung |
|---|---|
| `20%` | Anteil der verfügbaren Höhe bzw. Breite |
| `40mm` | absolutes Maß |
| `rest` | der verbleibende Platz |
| *weggelassen* | gleichmäßige Aufteilung des Rests unter allen ohne Angabe |

„Verfügbar" heißt: der Musterbereich **nach Abzug aller `gap`**. Sonst ergäben
mehrere Prozentangaben zusammen mehr als das Blatt.

Mehrere `rest` in derselben Ebene teilen sich zu gleichen Teilen. Übersteigt die
Summe der festen Angaben den Platz, ist das ein Fehler mit beiden Zahlen — nicht
Stauchen (§ 8.2).

Die weggelassene Angabe ist der häufigste Fall und deshalb der Default: Drei
gleich breite Felder schreibt man, indem man über die Breite **nichts** sagt.

#### Verschachtelung — genau eine Ebene

Für ein hohes Feld neben zwei niedrigen darf eine Spalte wieder Zeilen
enthalten:

```yaml
  - height: rest
    columns:
      - width: 40%
        rows:
          - { title: "Erreichbar ab" }
          - { title: "Erreichbar bis" }
      - { title: "Notiz", line_spacing: 8mm }
```

**Tiefer als eine Ebene nicht.** Damit sind alle Formulare abgedeckt, die man
von Hand ausfüllt, und es entsteht keine allgemeine Layoutsprache — genau die
Grenze, um die es in § 2 geht.

**Warum das kein Layoutsystem durch die Hintertür ist.** § 7.4 verbietet
mehrere positionierte Blöcke, und § 2 schließt eine allgemeine Zeichensprache
aus. Beides bleibt gültig: Das Raster hier liegt **innerhalb einer einzigen
Klinge**, ist rein deklarativ und ohne freie Koordinaten, und es reicht nicht in
den Griff hinein. Ein Generator darf eigene Gesetze rechnen (§ 5.3) — `maze` tut
es auch. Verboten bleibt, Layout zu einer Eigenschaft *des Werkzeugs* zu machen,
die für jeden Generator gilt.

#### Keine Spannen, kein Umbruch

Beides entfällt durch die zeilenweise Struktur: Ein Feld über zwei Spalten ist
schlicht ein Feld mit größerer `width`, und ein automatischer Umbruch kann nicht
entstehen, weil jede Zeile ausdrücklich dasteht. Damit fallen zwei Fehlerquellen
weg — Spannen, die über den Rand hinausgreifen, und Felder, die beim Umbrechen
an unerwartete Stellen rutschen.

#### Feldarten

| `kind` | Inhalt |
|---|---|
| `text` (Default) | Titel plus Schreibfläche, optional liniert |
| `check` | Titel plus ein Kästchen |
| `choice` | Titel plus je ein Kästchen pro Eintrag in `options` |

Ja/Nein ist damit `kind: choice, options: ["Ja", "Nein"]` — kein eigener Typ,
sondern der Zweifall des allgemeinen:

```yaml
- { title: "Dringend", kind: choice, options: ["Ja", "Nein"] }
```

> **Dringend**  ☐ Ja  ☐ Nein

Derselbe Mechanismus trägt „Ja / Nein / Unklar" oder „Post / Mail / Telefon",
ohne dass das Werkzeug davon wissen muss. **Die Beschriftungen stehen in der
Def**, weil sie zur Sprache des Formulars gehören — ein eingebautes „Yes/No"
wäre in einem deutschen Telefonprotokoll falsch, und eine Übersetzungstabelle
wäre der Anfang einer Lokalisierung, die § 3.4 ausschließt.

**Anordnung:** Kästchen vor der Beschriftung, alle Optionen in der Reihenfolge
der Def nebeneinander, unterhalb bzw. neben dem Titel je nach
`title.position`. Passt eine Zeile nicht, wird auf die nächste umgebrochen;
reicht die Zelle auch dann nicht, ist es ein Fehler mit der benötigten und der
vorhandenen Breite.

**Ankreuzbar heißt: leeres Kästchen.** Es gibt keine Vorbelegung und keine
Erzwingung von Ausschließlichkeit — auf Papier entscheidet der Stift. `choice`
beschreibt das Angebot, nicht eine Auswahlregel.

Die Kästchengröße folgt der Titelschriftgröße, überschreibbar per `box_size`.

#### Linierung ist absolut, das Raster ist relativ

Der wichtigste Punkt am ganzen Generator: **Spalten- und Zeilenmaße sind
relativ** (sie teilen den vorhandenen Platz), **die Schreiblinien in einem Feld
aber absolut.**

`line_spacing: 8mm` heißt 8 mm — und die Anzahl der Linien ergibt sich daraus,
wie viele in das Feld passen. Nicht umgekehrt. Würde die Linierung mitskalieren,
hätte man ein gedehntes Raster, und das ist nach § 8.2 ausgeschlossen. Wer
stattdessen `lines: 6` fest vorgibt, bekommt einen Fehler, wenn sie nicht
hineinpassen.

Damit bleibt die Def formatunabhängig — dasselbe Telefonprotokoll auf A4 und A5
hat andere Feldgrößen, aber gleich weite Schreiblinien.

#### Weitere Festlegungen

- **Titel werden vorab ausgemessen** (§ 10.2). Ein Titel, der nicht in seine
  Zelle passt, ist ein **Fehler** — `cut` (§ 8.9) gilt hier nicht, wie bei allen
  Generatorbeschriftungen.
- `form` ist die erste Klinge, deren **Layout** von Textmetrik abhängt, nicht
  nur deren Prüfung. Die Abfrage-API aus § 3.2 ist dafür Voraussetzung.
- `is_page_invariant` ist wahr, solange kein Feldtitel einen Platzhalter
  enthält.

### 7.9 Logarithmische Achsen (`law`)

Kein eigener Generator, sondern eine Eigenschaft von Linienfamilien (§ 7.1).

Log-Papier ist **periodisch pro Dekade**: Die Linien liegen bei log₁₀(1…10), und
dieses Muster wiederholt sich in jeder Dekade identisch. Der Unterschied zum
linearen Fall ist nicht die Periodizität, sondern dass die Zykluseinträge
*Positionen innerhalb der Periode* sind statt *Zuwächse*.

```yaml
families:
  - direction: horizontal
    law: log10              # linear (Default) | log10
    base_spacing: 25mm      # Dekadenlänge
    decades: 3
    base_weight: 0.15pt
    weight: [2, 1, 1, 1, 1, 1, 1, 1, 1]   # Dekadenanfang kräftig
```

Die Positionen berechnet das Werkzeug; niemand tippt `0.4771`. Halblogarithmisch
ist eine Achse mit `log10`, die andere ohne.

**Eine Log-Familie hat eine feste Gesamtlänge** von `decades × base_spacing` —
im Beispiel 75 mm. Sie **wiederholt sich nicht**, wenn der Musterbereich länger
ist; `decades` wirkt wie `count` bei linearen Familien (§ 7.1). Wo der Block
im Musterbereich sitzt, bestimmt `remainder` (§ 8.5): `center` mittig, `end`
am Ende. Ist die Gesamtlänge größer als der Musterbereich, ist das ein Fehler
mit Rechnung — dieselbe Prüfung wie bei anzahlgetriebenen Generatoren
(§ 12, Punkt 10).

**Einrasten ist bei `law: log10` nicht unterstützt** — Dekadenlängen sind nicht
sinnvoll in Rasterabstände teilbar.

**Die Periodenangabe aus § 5.3 entfällt.** „Wiederholt sich alle N Linien" ist
bei einer nicht wiederholenden Familie sinnlos; ausgegeben wird stattdessen die
Dekadenlänge.

Der Zweck ist ausdrücklich didaktisch: Der Wert liegt im Selbsteintragen, nicht
im professionellen Gebrauch.

### 7.10 Beschriftungsmuster

Gemeinsam für alle Generatoren, die Zellen oder Segmente beschriften (`grid`
§ 7.4, `polar` § 7.6, `tiling` § 7.7).

**Kein Bereich mit Anfang und Ende, sondern ein Zählmuster.** Die Anzahl der
Beschriftungen ergibt sich aus dem Generator (Zellen, Segmente); das Muster sagt
nur, *wie* gezählt wird. Damit muss niemand die Endmarke nachziehen, wenn sich
die Zellenzahl ändert.

| Zeichen | Zählt |
|---|---|
| `n` | Ziffern: 1, 2, 3, … |
| `a` | Kleinbuchstaben: a, b, c, … |
| `A` | Großbuchstaben: A, B, C, … |
| alles andere | steht wörtlich da |

**Wiederholung setzt die Breite:** `nn` → 01, 02, … 10; `nnn` → 001. Bei
Buchstaben zählt es nach Z tabellenkalkulationsüblich weiter: Z, AA, AB.

**Ein Gegenschrägstrich macht ein Zählzeichen wörtlich.** Nötig, weil `A` beides
sein können muss:

| Muster | Ergebnis |
|---|---|
| `"A"` | A, B, C, … J — die Spalten bei Schiffe versenken |
| `"n"` | 1, 2, 3, … |
| `"nn"` | 01, 02, 03, … |
| `"a"` | a, b, c, … |
| `"\An"` | A1, A2, A3, … |
| `"Feld n"` | Feld 1, Feld 2, … (`F`, `e`, `l`, `d` sind keine Zählzeichen) |

**Explizite Liste statt Muster** ist überall erlaubt, wo ein Muster erlaubt ist:
`columns: ["Nord", "Ost", "Süd", "West"]`. Stimmt ihre Länge nicht mit der
Zellenzahl überein, ist das ein Fehler mit beiden Zahlen — nicht Auffüllen und
nicht Abschneiden.

**`labels: none`** unterdrückt die Beschriftung ganz.

Der Zählbeginn ist fest (1 bzw. a bzw. A). Wer anders anfangen will, nimmt eine
explizite Liste; ein `start`-Schlüssel wäre die zweite Möglichkeit für dasselbe.

### 7.11 Vorgesehene Klingen (nach v1)

Beide arbeiten im **Musterbereich** (§ 8.1) wie jeder andere Generator und
berücksichtigen damit automatisch Kopf-, Fußhöhe, Ränder und — sobald M6 steht —
den gespiegelten Bundsteg auf geraden Seiten.

**`perspective`** — Fluchtpunktraster mit ein, zwei oder drei Fluchtpunkten.
Nutzt das Zyklusmodell **nicht**: Strahlabstände konvergieren, das ist ein
eigenes Gesetz. Fluchtpunkte müssen außerhalb des Musterbereichs liegen dürfen
(Angabe als Anteil, nicht als Koordinate im Blatt). Marken: `Segment`, für den
Horizontkreis ggf. `Arc`.

**`mandala`** — rotationssymmetrische Motive um einen Mittelpunkt. Baut auf
derselben Polargeometrie wie § 7.6 auf: Ring- und Speichenfamilien als Gerüst,
darüber Motive, die um N Sektoren wiederholt und gespiegelt werden. Marken:
`Arc`, `Segment`, `Polygon` **und `Dot`** (für Perlenringe, siehe unten). Die
Arbeit an `polar` in M3 ist hierfür Vorarbeit.

Die Motivfamilien (jede optional):

- **`rings`** — konzentrische Führungskreise, gleichmäßig verteilt.
- **`spokes`** — N Radialstrahlen, innen optional freigelassen.
- **`rosette`** — N Kreise auf den Speichen, optional auf die
  Winkelhalbierenden gespiegelt.
- **`petals`** — ein Kranz aus N spitzen Blättern, jedes aus **zwei Bögen**
  (Basis bei `inner`, Spitze bei `outer`, Wölbung `width`, alles als Anteil des
  Außenradius); nur `Arc`, kein neues Primitiv.
- **`beads`** — Punkte gleichmäßig auf einem Ring (`at`, `count`, `size`,
  `rotate`); führt `Dot` ein. `Dot` ist ein reguläres Primitiv (§ 6), also kein
  neues Vokabular, nur eine bisher ungenutzte Marke.
- **`scallops`** — ein gewellter Ring aus N Bögen, die von einem Basiskreis
  (`at`) um `depth` nach außen wölben; `inward` dreht die Wölbung nach innen
  (Spitzen statt Lappen). Nur `Arc`.
- **`pinwheel`** — kleine `sides`-Ecke (Umkreisradius `size`) auf einem Ring
  (`at`), jede mit ihrer Position und um `twist` gedreht — ein Windrad. Nur
  `Polygon`.
- **`polygons`** — einbeschriebene reguläre oder Sternpolygone.

**Motivring einzeln oder als Liste.** `rosette`, `petals`, `beads`, `scallops`
und `pinwheel` nehmen entweder eine einzelne Angabe **oder** eine Liste —
gestapelte Bänder in verschiedenen Radien. Eine einzelne Map bleibt gültig,
ältere Defs laufen unverändert. (`polygons` ist wie bisher stets eine Liste.)

Beide sind bewusst **nicht** in v1. Sie stehen hier, damit die Architektur sie
nicht ausschließt — insbesondere `Arc` und `Polygon` im Vokabular (§ 6) und die
Freiheit eines Generators, eigene Gesetze zu rechnen (§ 5.3).

### 7.12 `calendar` — verlinkter Kalender (Dokument-Generator)

Der erste Generator, der **keine Klinge** ist. Eine Klinge füllt *einen*
Musterbereich und weiß nichts von Seiten (§ 3.3). Ein Kalender **besitzt** Seiten
und deren Verlinkung. Deshalb ist er ein neuer Generator-Typ, ein
**Dokument-Generator**: statt `generate(cfg, area, page, q) -> Marken` bietet er
`pages(cfg, area, q) -> Folge typisierter Seiten` — Index, Jahr (zwei
Halbjahres-Tabellen), Monat (Liste aller Tage), Tag (konfigurierbare Blockliste),
Notizen-Index (nummeriert, paginiert) und Notizen. Der Griff erkennt ihn am
`pages`-Verfahren und fährt einen eigenen Schreibpfad (kein Deckblatt, kein
Ausschießen, kein Zyklus); bestehende Klingen bleiben unangetastet, `generate`
ändert sich nie.

**Links als Fähigkeit, kein siebtes Primitiv.** Ein Link ist eine PDF-Annotation,
keine Zeichenmarke — genau wie das Lesezeichen (`outline`, § 10.1) *außerhalb* der
sechs Primitive (§ 6) lebt. Die **Navigationsleiste** sitzt am *rechten* Rand: links gehört dem Seitentitel, und die beiden stritten sich sonst um dieselbe Ecke. Der Schreiber bekommt `define_dest`/`link` und die
Capability `"link"` (PDF ja, PNG nein → ein Kalender auf PNG wird benannt
abgelehnt, § 10.2). Das **Sichtbare** eines Links ist ein `Text` mit einem
`Segment`-Unterstrich, den die Seite ohnehin zeichnet — § 6 bleibt ein Vertrag
über sechs, und Platz wie Bytes bleiben minimal.

**Eine Seite je Ansicht, nie scrollen, nie skalieren.** Jede Ansicht füllt ihre
Seite; passt sie bei lesbarer Mindesthöhe nicht, wird der Lauf abgelehnt (§ 8.2),
nicht verkleinert — Detail holt der Nutzer per Geräte-Zoom. Die einzige unbegrenzte
Menge, die Notizen, **paginiert** ihren nummerierten Index über mehrere
Ein-Seiten-Blätter, statt Zeilen zu stauchen.

**Namen aus der Def, Englisch als Default** (§ 7.8 — keine mitgelieferte
Übersetzung); Daten aus `year` gerechnet, ohne Wall-Clock (§ 10.1). `{year}` ist
ein dokumentgelieferter Kopf-Platzhalter (§ 8.10), durch `extra` an
`resolve_placeholders`/`layout_band` gereicht, ohne Klingen zu berühren.
Vollständiger Entwurf in
[`docs/superpowers/specs/2026-07-24-calendar-generator-design.md`](superpowers/specs/2026-07-24-calendar-generator-design.md).
Seiten: optionales **Titelblatt** (Vollflächenfarbe über ein neues
`DocumentPage.background`, vom Griff gezeichnet, optional mit
einem **Vollflächen-PNG** darüber (`background_image`, `cover`/`contain`, dessen
transparente Stellen die Farbe durchlassen) und **optional Kopf-/Fußzeile**
(`header`/`footer` je einzeln; `plain` wich `show_header`/`show_footer`)), **Inhaltsverzeichnis**
(Nabe — **eine mittige Spalte** mit gemeinsamer linker Kante, die drei Gruppen
Übersichten/Monate/Notizen durch Weißraum statt Linien getrennt, der Block
vertikal zwischen Navigationsleiste und Fuß zentriert; passt er nicht auf eine
Seite — ein sehr langer Notizen-Index —, wird der Lauf abgelehnt, § 8.2),
eine minimale **Ganzjahresübersicht** (nur Zahlen als unterstrichene
Links, keine Boxen, alles auf einer Seite; je Mini-Monat **eine rechte Kante pro
Spalte** — der Wochentagsbuchstabe steht über seiner Spalte, die Tageszahlen
stehen rechtsbündig übereinander — und links jeder Woche ihre **Wochennummer**,
verlinkt, sobald es Wochenseiten gibt; die Spalte dafür nimmt ihre Breite von
den Tagesspalten. Der **Monatsname beginnt an der Kante der ersten Tagesspalte**,
nicht an der Zellkante — sonst steht er über den Wochennummern, und eine Zahl
unter einem Monatsnamen wird als Tag gelesen; die Wochennummern stehen mit
deutlichem Abstand links davon. Das Raster ist **aus seinem Inhalt gebaut**, nicht
aus der Zelle geteilt: eine Spalte ist ein zweistelliger Tag plus Luft, also rücken
die Tage eng zusammen, der Abstand neben der Wochennummer bleibt deutlich größer
als der zwischen zwei Tagen, und der Rest fällt zwischen die Monate. Passt ein
Mini-Monat nicht in seine Zelle — ein zu schmales Blatt —, wird der Lauf abgelehnt,
§ 8.2), **Halbjahr 1 & 2** als Tabellen,
Monate und **Wochen** (der Wochentag hält die linke Kante, die Tageszahlen stehen
**rechtsbündig** in einer eigenen Spalte darunter, beides zusammen bleibt *ein*
Sprungziel; beide Ansichten rechnen dieselben Spalten über `date_columns`, und
ein Tag außerhalb des Jahres steht in denselben Spalten, nur ohne Link), Tage, optional **Wochen** (an `week_start` ausgerichtet, nicht ISO) und
**Notizen**. `notes` nimmt **einen Block oder eine Liste**: jeder Block hat
seine eigene Seitenzahl, seine eigene Fläche (Linien zum Schreiben, Karo zum
Rechnen, Punkte zum Skizzieren) und seinen eigenen Namen. Jeder Block zählt
**ab 1** — man greift zu „Skizze 3", nicht zu „Notiz 23" —, hat seinen eigenen
nummerierten Index, und jeder Index verlinkt auf die anderen Blöcke. Das
Inhaltsverzeichnis führt **eine Zeile je Block**. `{year}` als Kopf-Platzhalter. Feiertage kommen **inline oder aus
einer Datei** (`holidays_file`, YAML-Liste oder konkret-datiertes `.ics`),
gegen `base_dir` aufgelöst wie `logo`, aufs Jahr gefiltert und mit der
Inline-Liste vereint (Inline gewinnt bei Datumsgleichheit). Wiederkehrende
(`RRULE`) und terminierte (DATE-TIME) `.ics`-Events werden **gezählt
übersprungen**, nie still verschluckt; die Quelle nennt der Laufbericht
(`X-WR-CALNAME`/`PRODID`), nichts im PDF.

Ein Eintrag ist nicht auf Feiertage beschränkt — Geburtstage und Jahrestage sind
demselben Kalender dasselbe. Jeder trägt optional eine **eigene Farbe** (`color`),
sonst die des Dokuments (`holiday_color`); sie **schlägt die Wochenend-Tönung**,
weil der markierte Tag die besondere Aussage ist. Gezeigt wird sie überall
*hinter* dem Tag: als Zellfüllung in der Halbjahrestabelle, als Zeilenfüllung auf
der Monatsseite, als Fläche hinter der Zahl in der Ganzjahresübersicht (die
bewusst keine Zellrahmen hat) und als Fläche hinter der Bezeichnung auf der
Tagesseite. Was eine Farbe *bedeutet*, weiß nur der Nutzer: eine optionale
**Farblegende** (`legend`, je Zeile `color` und `label`) steht als vierte Gruppe
auf dem Inhaltsverzeichnis, wird mitgezählt, wenn geprüft wird, ob die Seite
passt, und bleibt leer, wenn keine angegeben ist — der Kalender erfindet keine
Bedeutungen. Damit ist § 7.12 vollständig.

#### Die Sprache des Blattes (ergänzt 2026-07-26)

§ 7.8 entscheidet den Grundsatz — die Beschriftungen gehören zur Sprache des
Formulars, also nimmt das Werkzeug sie entgegen und erfindet sie nicht — und
§ 7.12 hatte ihn auf die **Namen** angewandt (`months`, `weekdays`, `label`)
und auf das eigene Vokabular nicht. Ein deutscher Kalender kam deshalb gemischt
heraus: `Jänner` unter einer englischen Navigationsleiste, daneben `Contents`,
`Full-year overview` und `Half-year 1`. Das sind Wörter des *Werkzeugs* auf dem
Blatt des Nutzers, und genau die schließt § 7.8 aus.

**`words:`** benennt sie: `index`, `year`, `month`, `week`, `notes` (die
Navigationsleiste), `contents`, `full_year_overview`, `half_year` und
`full_year`. Jede Vorgabe ist das Englisch, das bisher gedruckt wurde, also
ändert der Block keine bestehende Definition. Beim Notizbuch heißt das eine Wort
`contents_title`, und der Rücklink auf einem Trennblatt folgt ihm.

Das ist **keine Lokalisierung** (§ 3.4) und es wird weiterhin keine
Übersetzungstabelle mitgeliefert: Das Werkzeug nimmt Wörter entgegen und kennt
keine.

**`font:` an einem Dokument-Generator.** Die Grenze dahinter ist die Glyphen-
abdeckung (§ 10.3): Die Standardschriften reichen bis Latin-1, decken also
Deutsch, Französisch, Spanisch, Italienisch, Portugiesisch und die nordischen
Sprachen ab — aber nicht Polnisch, Tschechisch, Ungarisch, Türkisch, Rumänisch
oder Kroatisch. Deshalb nimmt ein Dokument-Generator wie jede Klinge eine eigene
Schrift entgegen, **eine für das ganze Dokument**; ohne sie lehnt die
Vorabprüfung ein Zeichen ab, das die Schrift nicht zeichnen kann (§ 12 Punkt 13),
statt ein Kästchen zu drucken.

### 7.13 `notebook` — verlinktes Notizbuch aus Abschnitten (Dokument-Generator)

Ein PDF, das mehrere Papiere trägt: vierzig gepunktete Seiten zum Journalen,
zwanzig karierte zum Rechnen, zehn Notenseiten — und ein Inhaltsverzeichnis, das
auf jede verlinkt. Für ein E-Ink-Gerät ist das der fehlende Baustein: **ein**
Notizbuch auf dem Gerät statt zwölf PDFs.

```yaml
generator: notebook
title_page: { title: "Notebook", subtitle: "2026" }   # optional
sections:
  - label: "Bullet journal"
    pages: 40
    divider: true               # Trennblatt mit dem Namen davor
    generator: dots
    grid: { x: { base_spacing: 5mm }, y: { base_spacing: 5mm } }
    base_size: 0.4mm
```

**Ein Abschnitt ist eine Definition im Kleinen:** `generator:` und danach die
eigenen Schlüssel dieses Generators, genau wie am Kopf einer Datei. Validiert
werden sie vom `config_model` der genannten Klinge — mit demselben
Validierungskontext, sodass `px` und `%w`/`%h`/`%s` in einem Abschnitt auflösen
wie überall (§ 8.3.1, § 8.11). Ein Tippfehler im Abschnitt ist damit ein Fehler
in den Worten der Klinge und nennt den Abschnitt (`sections.2`), nicht bloß
„unbekannter Schlüssel" (§ 5.1).

**Die Seite beschreibt, der Griff füllt** (festgelegt beim Bau, 2026-07). Eine
`DocumentPage` darf statt eigener Marken eine *Beschreibung* tragen — Generator
plus dessen fertig validierte Konfiguration —, und der **Griff** ruft die Klinge,
wie er es auf dem gewöhnlichen Seitenweg tut. Das Notizbuch fasst nie eine
Klinge an. Verworfen wurde, dass der Generator `generate` selbst aufruft: er
täte damit Griffarbeit und müsste Seitenkontext und Geometrie nachbauen, sobald
ein Abschnitt sie braucht (§ 3.3).

Seitenfolge: optionale **Titelseite**, **Inhaltsverzeichnis**, dann je Abschnitt
sein **Trennblatt** (falls verlangt) und seine Seiten. Das Verzeichnis nennt zu
jedem Abschnitt die Seitenzahl, auf der er beginnt — ein Notizbuch ist auch ein
Ding aus Papier, und dort ist der Link nur unterstrichener Text.

**Bänder werden seitenweise gesetzt** (§ 8.10). Ein Notizbuch wird geblättert,
also zählt `{page}`, und `{section}` nennt den Abschnitt der Seite: Nur der
Generator weiß, zu welchem Abschnitt eine Seite gehört, nur der Griff kennt ihre
Nummer — deshalb trägt die Seite ihre eigenen Platzhalter und der Griff die
seinen. Jede Seite eines Notizbuchs beantwortet `{section}`, auch Titel und
Inhalt, denn ein unbekannter Platzhalter ist ein Fehler und bleibt es.

**Abgelehnt wird, vor Seite eins:** ein unbekannter Generator (mit Liste der
bekannten), ein **Dokument**generator in einem Abschnitt — Notizbücher schachteln
nicht, ein Abschnitt *ist* Seiten —, `pages: 0`, eine leere `sections`-Liste,
alles, was das `check` der jeweiligen Klinge gegen den Musterbereich verweigert,
und ein Inhaltsverzeichnis, das nicht auf seine Seite passt (mit der nötigen
Höhe).

#### Mehrere Blätter je Stück (ergänzt 2026-07-26)

**Ein Abschnitt mit einem Blattplan** (§ 7.5, `maze` mit `solution:
separate_page` oder `back_mirrored`) wird ausgeführt, nicht mehr abgelehnt
(Entscheidung 55, sie ersetzt die vierte Ablehnung aus Entscheidung 52).
`pages:` zählt weiterhin **Stücke**, wie § 7.5 es auf dem Klingenweg liest —
`pages: 10` sind also zehn Rätsel auf zwanzig Seiten. Eine Regel für beide Wege,
statt eines Wortes mit zwei Bedeutungen.

**Ein Abschnitt ist eine Definition im Kleinen, und das gilt jetzt auch für den
Seitenkontext:** die Klinge eines Abschnitts bekommt Index 0…n−1 *ihres*
Abschnitts, nicht den der Dokumentseite. Damit stimmen die beiden Ablesungen aus
§ 7.5 wieder — die Parität für Rätsel gegen Lösung und `index // 2` für das
Stück hinter dem Seed —, und ein Titelblatt davor verschiebt kein Labyrinth mehr.

**Bei `back_mirrored` schiebt das Notizbuch ein leeres Blatt ein**, wenn der
Abschnitt sonst auf einer Rückseite begänne: beim Duplexdruck ist eine Seite
genau dann vorne, wenn ihre Nummer ungerade ist. Gemessen **nach** dem
Trennblatt, denn das ist eine Seite wie jede andere. Danach bleibt die Paarung
von selbst erhalten, weil jedes Paar zwei Seiten lang ist.

Dieses Blatt ist eine **echte Seite**: es trägt die Bänder, beantwortet
`{section}` und zählt in `{page}`; nur sein Musterbereich bleibt leer. Das ist
ausdrücklich die *andere* Entscheidung als die aufgefüllte Zelle eines Hefts
(§ 14) — die ist die Abwesenheit einer Seite und zeichnet gar nichts. Der
Laufbericht nennt jede Einfügung (§ 12).

Die Bedingung aus § 7.5 gilt unverändert: `back_mirrored` verlangt
`duplex: false` oder gleiche `inner`/`outer`, sonst wird abgelehnt — auf dem
Dokumentweg genauso wie auf dem Klingenweg. Der Griff fragt das Dokument dafür
nach seinen gespiegelten Abschnitten; die Prüfung selbst gehört zum Seitenmodell
und bleibt beim Griff.

**Bewusst nicht in dieser Fassung**, damit es niemand für vergessen hält: kein
`snap`, `remainder` oder `align` je Abschnitt (das ist Griffgeometrie für das
ganze Dokument, ein Abschnitt nimmt den Musterbereich, wie er ist), kein eigenes
Format je Abschnitt, keine verschachtelten Notizbücher.

### 7.14 `net` — parametrische Schachtelnetze

Maße hinein, das Gesetz rechnet das Netz: Schnittlinien durchgezogen, Falzlinien
gestrichelt, Klebelaschen ausgerechnet. Der Generator, der das Versprechen des
Werkzeugs **beweist**, statt es zu beschreiben — eine Schachtel, die 2 mm daneben
liegt, schließt nicht.

```yaml
generator: net
style: tuck_top          # tuck_top | tray
length: 80mm             # Innenmaße — der Raum *in* der Schachtel
width: 50mm
height: 30mm
thickness: 0.3mm         # Material; 0 für dünnes Papier
glue_tab: 12mm
tuck: 15mm               # die Zunge, die in die Vorderwand rutscht (tuck_top)
cut:  { weight: 0.4pt, color: "#000000" }
fold: { weight: 0.25pt, color: "#888888", style: dashed }
```

**Warum das keine Zeichensprache ist (§ 2).** § 2 schließt freie Striche an
gewählten Koordinaten aus und erlaubt einem Generator ein eigenes Gesetz. Ein
Netz ist das Zweite: Die Def sagt *Steckschachtel, 80 × 50 × 30 mm, 0,3 mm
Karton*, und jede Koordinate folgt daraus. Einen Schlüssel, der eine Fläche
*platziert*, gibt es nicht und darf es nicht geben.

**Der Mechanismus: Flächen, und Kanten, die zweimal vorkommen.** Eine Bauart
liefert **Flächen** — geschlossene Polygone in lokalen Mikrometern — und sonst
nichts. Dann gilt eine Regel:

> Eine Kante, die zwei Flächen teilen, ist eine **Falz**; eine Kante, die nur zu
> einer gehört, ist ein **Schnitt**.

Damit fällt die Unterscheidung aus der Geometrie heraus, statt von Hand gepflegt
zu werden, und eine neue Bauart ist eine Liste von Flächen statt eines
nachgezeichneten Umrisses. Der Vergleich ist **exakt**, weil Positionen
ganzzahlige Mikrometer sind (§ 3.3) — keine Toleranz zum Justieren. Der Preis
ist eine Regel für die Bauarten: **jede Lasche überdeckt ihre Anschlusskante
vollständig** und verjüngt nur an ihrer freien Seite. So wird ein Karton ohnehin
gestanzt.

**Zwei Konventionen, beide Entscheidungen und keine Herleitungen:**

1. **Maße sind Innenmaße.** Die Zahl, die der Nutzer hat, ist das Ding, das
   hineinsoll.
2. **Materialstärke hat eine Regel:** Eine Fläche, die *über* eine Lage
   schließt, wird um `thickness` breiter; eine Lasche, die *hinein* rutscht,
   wird um ebenso viel kürzer. Bei `thickness: 0` verschwindet jede Zugabe und
   das Netz ist das ideale — ein Test hält genau das fest.

**Am Karton geprüft (2026-07-26).** `box-tuck-a4` wurde bei 100 % gedruckt,
ausgeschnitten und gefaltet: die Schachtel schließt. Das ist der Nachweis, den
diese Klinge tragen sollte und den **kein Test führen kann** — die Steckschachtel
belastet nicht nur die Geometrie (das täte die Wanne auch), sondern gerade die
zweite Konvention oben, die *entschieden* und nicht hergeleitet ist. Die
Zugaberegel ist damit nicht mehr nur mit sich selbst konsistent, sondern mit
Material. Weitere Bauarten (siehe unten) sind damit von der Bedingung befreit,
erst zu warten, bis eine bestehende gefaltet wurde.

**Bauarten.** `tray`: Boden, vier Wände, an den Enden der beiden Stirnwände je
eine verjüngte Klebelasche. `tuck_top`: ein Wandstreifen (`length`, `width + t`,
`length + t`, `width + t`) mit Klebelasche, dazu oben wie unten ein Deckel
(`width + t` tief) mit Zunge (`tuck − t`) und zwei Staublaschen. Die
Faltnotation ist die aus § 2a und braucht keine neue Mechanik: `style: dashed`
für die Talfalte, `dash: [3, 1, 1, 1]` für die Bergfalte.

**Abgelehnt wird, vor Seite eins:** ein Netz, das nicht auf den Musterbereich
passt — mit Flachgröße und Bereich in Millimetern und dem Hinweis, dass ein Netz
**nie skaliert** wird (§ 8.2) —, ein Maß ≤ 0, eine `thickness` ab der Hälfte des
kleinsten Maßes (die Wände träfen sich in der Mitte), ein Schlüssel, der für die
gewählte Bauart nichts tut (`tuck` an einer Wanne, § 5.1), und eine unbekannte
Bauart, die die vorhandenen nennt.

#### Faltnotation — Benennung, keine neue Mechanik

Die Yoshizawa–Randlett-Notation des Papierfaltens braucht **keine neuen
Schlüssel**: sie ist die Strichmechanik aus § 5.3 und § 7.1, benannt.

| Bedeutung | Schreibweise |
|---|---|
| **Talfalte** (zu mir hin) | `style: dashed` |
| **Bergfalte** (von mir weg) | `style: dashed` mit `dash: [3, 1, 1, 1]` — Strichpunkt |
| **Hilfsfalte** (Bezug, keine Faltung) | `style: dotted` oder eine hellere `color` |
| **Schnittlinie** | `style: solid` — womit `net` seinen Umriss zeichnet |

Bewusst **keine** Werte `valley`/`mountain` in der DSL: es gäbe zwei Wege,
dasselbe zu sagen, und der zweite müsste gepflegt werden. Eine Konvention, die
im Handbuch steht und die ein Preset vorführt (`precrease-16-a4`, ein 16 × 16
Vorfalzraster mit beiden Diagonalen), leistet dasselbe, ohne die Sprache zu
verdoppeln — dieselbe Zurückhaltung wie bei den Formularbeschriftungen (§ 7.8).

Welche Linie Berg und welche Tal ist, gehört zum Modell und nicht zum Papier;
ein Vorfalzbogen leistet die nützliche Hälfte, nämlich sie unterscheidbar zu
machen.

**Bewusst nicht enthalten:** weitere Bauarten (Umschlag, Wickelschachtel,
Stülpdeckel — alle dieselbe Mechanik mit anderer Flächenliste, sie kommen, wenn
sie jemand braucht), Beschriftungen auf den Flächen (§ 2: das Werkzeug
beschreibt Struktur), das Schachteln mehrerer Netze auf einem Blatt, und eine
Falzzugabe je Rille — Letzteres ist Druckereipraxis und wäre hier eine geratene
Zahl (§ 9.2).

---

## 8. Geometrie

### 8.1 Der Seitenaufbau

Das Papierformat ist die **Basis**, aber alles Weitere rechnet sich relativ
daraus — deshalb ist es austauschbar, ohne die Def anzufassen.

```
┌──────────────────────────────────────────┐ ← Blatt (format/device)
│           margin.top                     │
│  ┌────────────────────────────────────┐  │
│  │ header   links │ mitte │ rechts    │  │  height (fix, § 8.4)
│  ├────────────────────────────────────┤  │
│  │           header.gap               │  │  Freiraumzeile
│  ├────────────────────────────────────┤  │
│  │                                    │  │
│ m│         MUSTERBEREICH              │m │  optional gerahmt (border)
│ a│    (Generatoren haben freie Hand)  │a │
│ r│                                    │r │
│ g│                                    │g │
│ i├────────────────────────────────────┤i │
│ n│           footer.gap               │n │  Freiraumzeile
│ .├────────────────────────────────────┤. │
│ i│ footer   links │ mitte │ rechts    │o │  height (fix)
│ n└────────────────────────────────────┘u │
│ n         margin.bottom               t  │
└──────────────────────────────────────────┘
```

**Rechenweg:**

```
content_width  = page_width  − margin.inner − margin.outer
pattern_height = page_height − margin.top − margin.bottom
                             − header.height − header.gap
                             − footer.height − footer.gap
```

Kopf, Fuß und Musterbereich haben **dieselbe Breite** (`content_width`). Der
Rahmen (`border`, optional) sitzt genau auf der Kante des Musterbereichs.
**Alle Musterkoordinaten beginnen hier** — dieselbe Def funktioniert auf A4,
Letter und einem Pad.

**`margin` ist der nicht bedruckbare Rand.** Er ist keine Gestaltungsgröße,
sondern eine Geräteeigenschaft, und sein **Default kommt deshalb aus der
Format- bzw. Geräteprofiltabelle**, nicht aus dem Code: Papierformate tragen
5 mm (typischer Wert handelsüblicher Drucker), Geräteprofile 0 (ein E-Ink-Pad
hat keinen unbedruckbaren Rand). Damit stimmt die Bedeutung in beiden Welten.
Wer bewusst kleiner geht, bekommt eine Warnung (§ 8.2), keinen Fehler.

**`inner` / `outer` statt `left` / `right`.** Auf Vorderseiten ist `inner`
links. Bei `duplex: true` tauschen beide auf geraden Seiten, sodass der breitere
Rand immer an der Bindekante liegt. Bei `duplex: false` ist `inner` schlicht
immer links.

Angabe entweder als Skalar (`margin: 5mm`, rundum gleich) oder als benannte
Abbildung. **Eine Viererliste gibt es nicht** — sie wäre mit `inner`/`outer`
mehrdeutig.

**Freiraumzeilen** (`header.gap`, `footer.gap`) gehören zum jeweiligen Element
und entfallen mit ihm: Wer keinen Kopf definiert, bekommt auch keinen Freiraum
oben. Das erspart eine Sonderregel.

Fehlen Kopf und Fuß ganz und ist `margin` null, füllt der Musterbereich das
ganze Blatt — Raster bis zur Kante ist damit ausdrückbar, ohne Sonderfall.

### 8.2 Maßhaltigkeit

- PDF mit exakter MediaBox in absoluten Einheiten. **Nie** „scale to fit".
- Strichstärken in pt/mm, **nie** in Pixeln (außer bei Geräteprofilen).
- **Ein Raster wird niemals gedehnt, um aufzugehen.** Es gibt keine Option dafür.
- **Positionen werden nie durch Aufaddieren berechnet.** Entweder aus dem Index
  (`origin + k·periode + teilsumme`) oder in ganzzahligen Mikrometern. Wiederholte
  Float-Addition akkumuliert über 300 Linien Fehler, macht Golden-File-Tests
  instabil und ist bei einem Werkzeug mit dieser Kernzusage kein akzeptables
  Fundament.

**Grenze unserer Zuständigkeit — auf beiden Seiten:**

*Beim Drucken:* Was der Druckertreiber tut, können wir nicht beeinflussen, und
wir versuchen es nicht. Die meisten PDF-Betrachter haben „Fit to page"
voreingestellt und skalieren still auf ~96 %. Die Recherche zeigt, dass dies die
häufigste Beschwerde über *alle* vergleichbaren Werkzeuge ist.

*Beim Anzeigen:* Dasselbe gilt für Pads. Ein PDF ist auf dem Gerät nur dann
maßhaltig, wenn es **seitenfüllend und ohne Zoom** dargestellt wird. Jede
Zoomstufe, jeder Rand, den der Betrachter hinzufügt, verändert das Maß.

Daraus folgt aber ein Gestaltungshinweis, der in unserer Hand liegt: **Wer ein
Geräteprofil verwendet, bekommt eine Seitengröße, die dem Bildschirm exakt
entspricht** (§ 9.2). Dann liefert gerade die übliche
„Seite einpassen"-Darstellung das richtige Maß, weil nichts einzupassen ist.
Ein A4-PDF auf einem 3:4-Bildschirm wird dagegen immer skaliert — das ist der
eigentliche Grund, warum es Geräteprofile gibt, und nicht nur die Pixelzahl.

Deshalb zwei Antworten, die einander ergänzen:

1. **Nach jedem erfolgreichen Lauf ein Hinweis**, der die nötige Einstellung
   konkret benennt („Actual size" / „100 %" / „Custom scale: 100"), nicht bloß
   „achte auf die Skalierung". Erscheint jedes Mal, abschaltbar per `--quiet`.
2. **Ein optionales Deckblatt** (§ 8.8) mit Kalibrierquadrat.

**Nicht bedruckbarer Rand:** Unterschreitet ein `margin`-Wert den Default des
gewählten Formats bzw. Geräteprofils (§ 8.1), warnt das Werkzeug, dass der
Drucker den äußeren Bereich abschneiden wird. Das ist eine andere Frage als die
Skalierung — hier geht Inhalt verloren, statt dass Maße verrutschen.

### 8.3 Einrasten

Da ein Raster im Musterbereich fast nie glatt aufgeht, kann der **Musterbereich
verkleinert** werden — die Periode bleibt exakt, der Überschuss wird zu freiem
Raum zwischen Rand und Muster.

**Wichtig zur Abgrenzung:** Einrasten verändert **nicht** `margin`. Der Rand ist
seit § 8.1 der nicht bedruckbare Bereich und damit eine Geräteeigenschaft, an
der niemand dreht. Was hier entsteht, ist zusätzlicher *Leerraum innerhalb* des
bedruckbaren Bereichs.

| Wert | Verhalten |
|---|---|
| `none` | **Default.** Der Musterbereich bleibt exakt so groß wie berechnet. |
| `spacing` | Auf ganzzahlige Vielfache des Grundabstands einrasten |
| `cycle` | Auf ganzzahlige Vielfache der **mm-Periode** einrasten |
| `pixel` | Abstände auf **ganze Gerätepixel** einrasten (§ 8.3.1) |

`cycle` ist meist das optisch Richtige: Sonst sitzt das Raster sauber, aber die
kräftigen Linien asymmetrisch — und genau die sieht man.

**`none` ist Default, weil Einrasten die berechnete Geometrie verändert.** Wer
10 mm Rand und eine bestimmte Kopfhöhe angibt, bekäme sonst eine kleinere
Musterfläche, als die Rechnung in § 8.1 ergibt.

**Pro Achse getrennt.** Bei mehreren Familien auf einer Achse muss eine mit
`governing: true` markiert sein; sonst → **Fehler mit Nennung der Familien**.

**Verhältnis zu `remainder` (§ 8.5):** Einrasten beseitigt den Rest nicht, es
*verlagert* ihn — aus einer angeschnittenen Periode am Ende wird zusammenhängender
Leerraum. Wo dieser landet, bestimmt weiterhin `remainder`: bei `center`
gleichmäßig auf beide Seiten, bei `end` gesammelt am Ende.

Einzige Wechselwirkung: `whole_cycles` ist neben `snap: cycle` wirkungslos, weil
dort ohnehin nur ganze Zyklen entstehen. Das Werkzeug weist einmal darauf hin,
damit niemand an einer folgenlosen Einstellung dreht.

**Nur für Generatoren mit periodischen Familien.** Einrasten setzt eine Periode
voraus, an der man einrasten kann — das sind `lines` und `dots`. Bei `staves`,
`grid`, `maze`, `tiling` und `form` gibt es keine, und ein gesetztes `snap` ist
dort ein **Fehler**, keine stille Wirkungslosigkeit: Wer es hinschreibt, erwartet
eine Wirkung.

**Ebenfalls nicht unterstützt:** schräge Familien (§ 7.1), `polar` (§ 7.6),
`law: log10` (§ 7.9). Jeweils Fehler, kein Raten.

#### 8.3.1 `snap: pixel` — die einzige Ausnahme von der Maßtreue

Auf einem Rasterbildschirm ist das Nennmaß **nicht exakt darstellbar**. Ein
5-mm-Raster sind auf 229 dpi 45,08 Pixel je Zelle; das Gerät zeichnet
abwechselnd 45 und 46 Pixel, und das Raster wirkt ungleichmäßig, obwohl es exakt
gerechnet ist (§ 12.1).

Der Nutzer hat also die Wahl zwischen zwei Übeln, und **beide sind legitim**:

| | Maß | Aussehen |
|---|---|---|
| `none` | exakt 5,000 mm | ungleichmäßige Zellen |
| `pixel` | 4,991 mm (45 px) | völlig gleichmäßig |

Deshalb ist es eine Option und **niemals der Default**: Das Werkzeug darf diese
Abwägung nicht für den Nutzer treffen, aber es muss sie ihm zeigen.

**Regeln:**

- **Nur mit Geräteprofil erlaubt.** Auf Papierformaten ist es ein Fehler: Deren
  `assumed_dpi` (§ 9.1) ist ein Prüfmaßstab für Warnungen, keine echte
  Auflösung. Geometrie darf niemals auf einer geratenen Zahl beruhen.
- **Gerundet wird jeder Schritt**, nicht nur die Basis — nur so liegen auch bei
  Zyklen mit gebrochenen Vielfachen alle Positionen auf ganzen Pixeln.
- **Das tatsächliche Maß wird gemeldet**, unaufgefordert und in beiden
  Einheiten: *„snap: pixel — spacing 5mm → 4.991mm (45px at 229dpi)"*. Eine
  stille Maßänderung wäre genau der Vertrauensbruch, den § 8.2 verhindern soll.
- Hebt die Befunde „Positionen nicht auf ganzen Pixeln" aus § 12.1 auf — das
  ist ja gerade sein Zweck.

**Warum das § 8.2 nicht widerspricht:** Dort ist verboten, ein Raster zu
*dehnen, damit es aufgeht* — also die Geometrie an das Blatt anzupassen. Hier
wird an das **physische Pixelraster** des Ausgabegeräts angepasst, das ohnehin
quantisiert. Das Nennmaß wird nicht gebeugt, sondern auf die kleinste real
darstellbare Einheit gelegt.

### 8.4 Kopf- und Fußhöhe sind fix

Höhen **und** Freiraumzeilen kommen aus der Def, nie aus dem gerenderten Inhalt.
Sonst hat Seite 1 mit „Anna Berger" eine andere Musterfläche als Seite 7 mit
„Maximilian Sonnenschein-Hofstätter", und das Raster springt von Blatt zu Blatt.

Das gilt auch, wenn ein Feld leer bleibt: Ein Kopf ohne Text ist **nicht** ein
Kopf der Höhe 0. Wer keinen Kopf will, lässt den Abschnitt weg.

**Die Schrifthöhe bestimmt den gebrauchten Platz.** Die angegebene `height` muss
groß genug sein für die gewählte Schriftgröße (Ober- plus Unterlänge) und für
jedes eingesetzte Bild. Das ist eine **Prüfung, keine Ableitung** — die Höhe
bleibt die aus der Def, aber sie muss ausreichen. Sonst ragt der Text in den
Musterbereich oder wird vom Rand beschnitten, ohne dass es jemand merkt.
Geprüft in § 12, Punkt 13.

### 8.5 Der Rest

Was nach dem Auslegen der Perioden übrig bleibt:

| `remainder` | Verhalten |
|---|---|
| `end` | Rest sammelt sich am Ende |
| `center` | Rest gleichmäßig auf beide Seiten |
| `whole_cycles` | Nur ganze Zyklen ausgeben, angeschnittener Rest entfällt |

`whole_cycles` ist für Kalligraphie und Notensysteme gedacht, wo ein
angeschnittener halber Zyklus am Blattende unbrauchbar ist.

**Pro Achse getrennt**, wie `snap`: `remainder: { x: …, y: … }`, mit einem
Skalar als Kurzform für beide. Ein einzelner Wert für beide Achsen wäre bei
Kalligraphie falsch — dort ist die y-Achse zyklisch gegliedert und die x-Achse
nicht.

Eine Option „dehnen, bis es aufgeht" gibt es **nicht** (§ 8.2).

**`pattern.align` — die Ecke, an der das Muster verankert ist.** `remainder`
verschiebt den Sub-Zyklus-Rest, aber der *Zyklus selbst* zählt vom
Koordinatenursprung (§ 3.5, links unten). Damit liegt die schwere Ursprungslinie
unten-links und ein angeschnittener Block landet gegenüber, oben-rechts. Wer es
umgekehrt will — schwerer Start oben-links, wie ein Notizbuch beschrieben wird,
und der unvollständige Block **unten** — setzt `align: top-left` (Werte:
`bottom-left` als Default, `top-left`, `bottom-right`, `top-right`). Der Griff
**spiegelt** das fertige Muster in seinem eigenen Bereich an der gewählten
Achse; für ein symmetrisches Raster ist das genau eine Umverankerung, und die
Klinge erfährt davon nichts (§ 3.3). Text wird dabei nie auf den Kopf gestellt,
nur seine Ablage wandert. Kombiniert mit `remainder: end` liegt das Raster
bündig an den Ankerkanten.

### 8.6 Stempel

Ganzseitig, diagonal, niedrige Deckkraft, **oberste Ebene**. „Draft" ist ein
transienter Zustand, keine Eigenschaft des Papiers — deshalb primär als
CLI-Flag (`--stamp "DRAFT"`). In der Def erlaubt, aber nicht der vorgesehene Weg.

### 8.7 Lochmarken

`page.hole_marks: true | false` (Default `false`). Eine Zeile, ein Schalter.

Erzeugt Markierungen nach **ISO 838** (zwei Löcher, 80 mm Abstand, 12 mm vom
Rand, symmetrisch zur Blattmitte) an der Bindekante. Keine weiteren Parameter;
wer andere Lochungen braucht, setzt eine begrenzte Familie (§ 7.1).

**Die Marken wandern mit der Ausrichtung.** Im Hochformat sitzen sie an
`margin.inner`, im Querformat an der **oberen** Kante — dort wird geheftet. Weil
die obere Kante beim Duplexdruck nicht spiegelt, bleiben sie im Querformat auf
Vorder- und Rückseite an derselben Stelle; `inner`/`outer` bezeichnen weiterhin
die seitlichen Ränder.

**Sie liegen im Musterbereich, nicht im Rand.** Bei einem inneren Rand von 5 mm
und Lochmitten bei 12 mm sitzen die Marken zwangsläufig über dem Raster. Das ist
kein Fehler, sondern der Normalfall — deshalb:

- Lochmarken liegen auf Ebene `frame`, werden also **über** das Muster gezeichnet.
- Ist `margin.inner` kleiner als 12 mm, **warnt** das Werkzeug, dass die Marken
  im Muster liegen. Kein Fehler: Genau so sieht ein normales Blatt Papier aus.
- Es wird **kein Platz reserviert**. Wer die Marken freistellen will, setzt
  `margin.inner` auf mindestens 15 mm — das ist eine Gestaltungsentscheidung und
  bleibt beim Nutzer.

### 8.8 Deckblatt

`--cover` erzeugt **eine zusätzliche erste Seite**, die drei Dinge trägt:

**1. Kalibrierquadrat.** Ein beschriftetes Quadrat von exakt 50 mm Kantenlänge
und eine 100-mm-Strecke, beide mit Sollmaß beschriftet. Der Nutzer legt ein
Lineal an; stimmt das Maß nicht, hat der Druckertreiber skaliert. Das ist die
einzig mögliche Antwort auf ein Problem außerhalb unserer Kontrolle (§ 8.2):
Wir können die Skalierung nicht verhindern, aber sichtbar machen.

**2. Strichstärken-Leiter.** Kurze waagerechte Linien in einer festen,
aufsteigenden Folge von Strichstärken (0,1 bis 1,0 pt), jede beschriftet. So
sieht der Nutzer auf seinem *eigenen* Drucker oder E-Ink-Gerät, wie eine
gegebene Stärke wirklich aussieht — die Medienprüfung (§ 12.1) sagt nur, *dass*
eine Haarlinie zu dünn ist, die Leiter zeigt, *wie* dünn. Ist ein Gerät aktiv,
trägt jede Beschriftung zusätzlich die Pixelbreite (`0,15pt · 0,48px`) und
verbindet die Warnung mit dem, wovor sie warnt. Auf Papier nicht, weil ein
`assumed_dpi` ein Maßstab und keine Auflösung ist (§ 8.3.1). Feste Zahlen wie
Quadrat und Lineal, kein einstellbarer Wert.

**3. Einstellungszusammenfassung.** Generator, Format, Ränder, Basiswerte,
Zyklen, effektive Periode in Marken und Millimetern, Einrastmodus,
Werkzeugversion und Name bzw. Prüfsumme der zugrunde liegenden Def. Damit ist
ein gelungenes Blatt Jahre später reproduzierbar, ohne dass jemand die Def
wiederfinden muss.

**Warum als eigene Seite und nicht auf jedem Blatt:** Beides ist Metainformation
über den Druck, keine Eigenschaft des Papiers — dieselbe Begründung wie beim
Stempel (§ 8.6). Auf jedem Blatt wäre es Verschmutzung; einmal vorne ist es
Dokumentation.

**Regeln:**

- **Default aus.** Nur `--cover` bzw. `pages.cover: true` in der Def schaltet es ein.
- Das Deckblatt **zählt nicht bei der Seitennummerierung**: `--pages 30` erzeugt
  30 nummerierte Blätter plus ein Deckblatt, und `{page} / {page_count}` bezieht
  sich weiterhin auf 1…30.
- Es trägt **weder Kopf-, Fuß-, Rahmen- noch Lochmarken** und ist von
  Ausschießen (§ 14, M6) ausgenommen.
- Es enthält die Werkzeugversion und ist deshalb **von Golden-File-Tests
  auszunehmen** (§ 13.2), sonst bricht jede Versionsanhebung die Suite.

**Die Def als Dateianhang im PDF** (§ 15, Punkt 5) — **gebaut.** `--embed-def`
bzw. `pages.embed_def: true` bettet die vollständige Def als Anhang ein: die
*exakten Bytes*, die der Nutzer geschrieben hat (dieselben, über die die
Prüfsumme oben läuft), nicht das aufgelöste Modell. Dann trägt das Dokument
buchstäblich seinen eigenen Quelltext, und ein gelungenes Blatt reproduziert sich
Jahre später, ohne dass jemand die Def wiederfinden muss. Default aus, nur ein
Weg an — dieselbe Einweg-Logik wie `--cover` (§ 11). **Nur PDF:** der
PNG-Schreiber kann keine Datei tragen, also lehnt die Vorabprüfung den Lauf
benannt ab, statt den Anhang stillschweigend fallenzulassen (§ 10.2). `reportlab`
kennt keine Filespecs, also baut der Schreiber die Objekte selbst — eine
`EmbeddedFile`-Stream, ein `Filespec` und der Namensbaum `/Names /EmbeddedFiles`
im Katalog (PDF 1.4+, genau die Zielversion) —, alles aus Bytes und Name
abgeleitet, ohne Datum und ohne Zufalls-ID, damit § 10.1 hält.

### 8.9 Textüberlauf in Kopf und Fuß

Kopf und Fuß haben drei Felder (`left`, `center`, `right`) auf einer festen
Breite. Bei langen Namen stoßen sie zusammen. `cut` entscheidet, was dann
passiert:

| `cut` | Verhalten |
|---|---|
| `false` | **Default.** Fehler vor dem Rendern, mit Nennung des Feldes, des Textes und der fehlenden Millimeter |
| `true` | Text wird gekürzt und mit einem Auslassungszeichen (…) abgeschlossen |

**Warum `false` der Default ist:** Ein abgeschnittener Name ist ein stiller
Datenverlust, und § 12 verbietet stilles Verstümmeln. Wer 30 Blatt für eine
Klasse druckt, will erfahren, dass „Maximilian Sonnenschein-Hofstätter" nicht
passt — nicht 30 Blatt mit „Maximilian Sonnensch…" bekommen.

**Warum das Auslassungszeichen Pflicht ist**, wenn `cut: true` gesetzt wird:
Auch die ausdrücklich gewollte Kürzung soll sichtbar bleiben. Ohne das Zeichen
sieht ein abgeschnittener Text aus wie ein vollständiger.

Fehlt `…` in der gewählten Schrift, wird auf drei Punkte (`...`) ausgewichen —
sonst bräche ausgerechnet die Kürzung an einer fehlenden Glyphe (§ 10.2).

**Platzaufteilung — festgelegt, damit nichts geraten wird:**

1. `center` wird in der Inhaltsbreite zentriert und darf sie nicht
   überschreiten; ist es allein schon zu breit, trifft es die Kürzung zuerst.
2. `left` reicht vom linken Rand bis zur linken Kante des Mittelblocks.
3. `right` reicht von dessen rechter Kante bis zum rechten Rand.
4. Wer sein Feld überschreitet, wird gekürzt — nicht der Nachbar.
5. **Ist `center` leer**, gibt es keinen Mittelblock, aus dem sich Grenzen
   ableiten ließen. Dann teilen `left` und `right` die Inhaltsbreite an der
   **Mitte**: jedes bekommt die Hälfte. Ohne diese Regel liefe der Fall ins
   Leere, und er ist der häufigste — Name links, Seitenzahl rechts.

Für Bilder (`{ image: … }`) gilt dasselbe, nur ohne Kürzung: Ein Logo wird nie
beschnitten, es passt oder es ist ein Fehler.

**Für Generatorbeschriftungen gilt `cut` nicht.** Ein gekürztes Gitterlabel
(`A…` statt `A10`) oder eine gekürzte Segmentbeschriftung ist wertlos; dort
bleibt es immer beim Fehler. Kürzen ist nur für Freitext in Kopf und Fuß
sinnvoll.

Ein Band trägt optional eine **Hintergrundfarbe** (`background`, ein Farbstreifen
über die volle Blattbreite und die Bandhöhe — nicht den `gap`) und eine
**Textfarbe** (`text_color`, Standard Schwarz). Beide sind ohne Angabe aus und
ändern kein bestehendes Blatt. Der Streifen liegt hinter dem Text.

### 8.10 Platzhalter

Kopf und Fuß haben je drei Felder (`left`, `center`, `right`). **Was darin
steht, entscheidet allein der Nutzer** — es gibt keine vorgegebene Belegung und
keine Pflichtfelder. Freitext ist der Normalfall; vier Platzhalter werden beim
Seitenaufbau ersetzt.

**Wo sie gelten:** in Kopf- und Fußfeldern **und in Formulartiteln** (§ 7.8) —
überall dort, wo die Def freien Text liefert. Ein Telefonprotokoll je Anrufer
mit `title: "{name}"` ist genau der Fall, für den die Namenslisten da sind.

**Wo sie nicht gelten:** in Beschriftungsmustern (§ 7.10). Dort zählen `n`, `a`
und `A` bereits, und ein zweiter Ersetzungsmechanismus im selben String wäre
eine Falle.

| Platzhalter | Ersetzt durch |
|---|---|
| `{name}` | Der Eintrag der Namensliste für diese Seite (§ 9.4) |
| `{page}` | Laufende Seitenzahl, beginnend bei 1 |
| `{page_count}` | Gesamtzahl der Seiten |
| `{date}` | Das aktuelle Datum beim Erzeugen |

**Das Deckblatt zählt nicht mit** (§ 8.8). Bei `--pages 30 --cover` liefert
`{page_count}` also 30, und das erste gezählte Blatt ist das erste Musterblatt.

**Lösungsseiten zählen dagegen mit** (§ 7.5). Bei zehn Labyrinthen mit Lösung
läuft `{page}` von 1 bis 20 — ungerade Rätsel, gerade Lösungen. Der Unterschied
zum Deckblatt ist beabsichtigt: Das Deckblatt ist Beiwerk zum Druckvorgang, eine
Lösungsseite ist Inhalt.

**`{name}` ohne Namensliste ist ein Fehler**, kein leerer String — sonst
entstünde stillschweigend ein Blatt mit leerem Kopf, wo einer erwartet wurde.

**`{date}` bricht die Reproduzierbarkeit — mit Ansage.** Zwei Läufe an
verschiedenen Tagen ergeben verschiedene PDFs. Das ist kein Fehler, sondern die
ausdrückliche Entscheidung des Nutzers: Wer ein reproduzierbares Blatt will,
schreibt das Datum als Text hin (`right: "01.01.2026"`) statt als Platzhalter.

Daraus folgen zwei Pflichten:

- Beim Erzeugen weist das Werkzeug **einmal darauf hin**, dass `{date}` das
  Ergebnis datumsabhängig macht.
- **Presets und Golden-File-Tests verwenden `{date}` nicht** (§ 13.2), sonst
  schlägt die Suite jeden Tag anders aus.

Die Reproduzierbarkeitsanforderung an die PDF-Metadaten (§ 10.1) bleibt davon
unberührt — sie betrifft das Erstellungsdatum *im Dateikopf*, nicht sichtbaren
Inhalt.

### 8.11 Relatives Maß

Ein festes Millimetermaß füllt A4 (1:√2) und ein 3:4-E-Ink-Gerät verschieden
(§ 9.2). Damit **dieselbe Definition jedes Medium füllt**, darf eine Länge als
**Anteil des Musterbereichs** geschrieben werden:

- `%w` — Anteil der **Breite** des Musterbereichs,
- `%h` — Anteil der **Höhe**,
- `%s` — Anteil der **kürzeren Seite** (natürlich für Kreise und Radien).

**Explizit, nicht magisch.** Der Musterbereich hat Breite *und* Höhe; welche
gemeint ist, sagt der Nutzer selbst über die Einheit, statt dass die Klinge aus
der Richtung eines Feldes rät. So bleibt es eindeutig — dieselbe Sorgfalt wie
bei `inner`/`outer` (§ 8.1). Die Schreibweise `%w`/`%h`/`%s` kollidiert bewusst
nicht mit dem generatorlokalen `%` von `form` (§ 7.8).

**Auflösung wie `px`.** Ein `%`-Maß wird gegen den **Rohbereich** aufgelöst —
Blatt minus Ränder und Bänder (§ 8.1), *vor* dem Einrasten. Dieser Bezug hängt
nicht vom Generator ab und ist bereits in Naht 1 bekannt, genau wie die
Gerätedichte für `px` (§ 8.3.1): der Griff reicht ihn über denselben
Validierungskontext, und danach sieht der Kern keine Einheit mehr (§ 3.6). Rastet
das Muster ein, schrumpft der Bereich auf ganze Perioden des nun konkreten
Maßes — der Anteil ist am Rohbereich fixiert, das Ergebnis bleibt maßhaltig
(§ 8.2, § 8.3).

**Nur Raummaße.** Erlaubt in den Raummaßen einer Klinge — Abständen, Radien,
Extents, Systemgrößen. **Nicht** in Rändern und Bändern (sie *definieren* den
Bereich — ein Anteil davon wäre zirkulär), und nicht in Strichstärken oder
Schriftgrößen (die skalieren nicht mit dem Blatt). Dort ist `%w`/`%h`/`%s` ein
lauter Fehler mit Begründung, nie eine stille Null — dasselbe Muster wie `px`
auf Papier (§ 8.3.1).

### 8.12 Randlineal

Ein gedruckter Maßstab entlang gewählter Blattkanten, optional — Rahmen-Möbel
neben `border`, `hole_marks` und `stamp` (§ 5.2, § 8.7), keine Klinge.

```yaml
ruler:
  edges: [bottom, left]   # bottom | left | top | right, mindestens eine
  unit: mm                # mm | cm | in — was die Zahlen bedeuten
  step: 1mm               # kleinster Strich
  mid_every: 5mm          # mittlerer Strich; `none` lässt ihn weg
  label_every: 10mm       # langer Strich, und die Zahl daneben
  weight: 0.2pt
  color: "#000000"
  font: { size: 6pt }
```

**Arbeitsmaßstab, keine zweite Kalibrierfigur.** Null sitzt am **Ursprung des
Musterbereichs** der jeweiligen Kante, nicht in der Papierecke: die Zahlen sollen
mit dem Raster übereinstimmen, damit man am Blatt misst und zuschneidet. Der
Kalibrierfall ist bereits beantwortet — das Deckblatt trägt Quadrat und
100-mm-Regel (§ 8.8) — und bekommt deshalb kein zusätzliches Lineal.

**Wo genau die Null sitzt, sagt `origin`** (ergänzt 2026-07-26, nach drei realen
Fällen): `bottom-left` für die technische Zeichnung, `top-left` für den
Bildschirmentwurf (senkrecht wird **abwärts** gezählt), `center` für den
Funktionsplot — dort steht die Null in der Mitte jeder Kante und davor stehen
**negative Zahlen**. `bottom-right` und `top-right` fallen aus derselben Formel
heraus: jede Achse nimmt ihre Hälfte des Eckennamens.

Fehlt `origin`, **folgt das Lineal `pattern.align`** (§ 8.5). Das ist keine
Bequemlichkeit, sondern die Regel von oben zu Ende gedacht: Wer sein Raster oben
links verankert, dessen erste schwere Linie liegt oben — ein Lineal, dessen Null
unten sitzt, widerspräche genau der Übereinstimmung, für die es da ist. Ein
ausdrückliches `origin` sticht, für den Fall „ich messe das Blatt, nicht das
Raster".

**Die Strichleiter hängt an der Null, nicht an der Blattkante.** Bei `center`
müssen die Zahlstriche symmetrisch um die Mitte liegen, sonst fiele die 0
zwischen zwei Striche; die Leiter läuft daher von der Null aus in beide
Richtungen und endet an den Kanten. Ein Strich trägt deshalb seine **Position**
und seinen **Wert** getrennt: gezeichnet wird an der Position, gedruckt wird der
Wert, und die beiden sind erst gleich, wenn die Null am Kantenanfang sitzt.

**Im Rand, ohne Platzreservierung.** Die Striche wachsen von der Musterkante
**nach außen** in den Rand, auf `Layer.FRAME`. Der Musterbereich wird nicht
verkleinert: § 8.1 berechnet ihn aus Rändern und Bändern allein, und ein
eingeschaltetes Lineal verschiebt so wenig eine Rasterlinie wie ein `border`.
Gemessen wird gegen den Bereich, den das Muster **tatsächlich bekommen hat** —
lässt `remainder` (§ 8.5) Rest an einer Kante, zählt der als Platz.

**Physische Kanten, nicht `inner`/`outer`.** Ein Maßstab ist ein Ding an der
Papierkante und folgt nicht der Bindung; unter `duplex` tauscht er die Seite
nicht, während die Ränder es tun (§ 8.1). Gezeichnet wird trotzdem aus der
Geometrie *dieser* Seite, damit das Lineal dem Bereich folgt, wenn dieser wandert.

**Die Leiter.** `unit` bestimmt nur, was die Zahlen bedeuten; die drei Intervalle
bestimmen, wo die Striche stehen. Vorgaben: `mm` und `cm` teilen 1/5/10 mm (die
Zahlen zählen Millimeter bzw. Zentimeter), `in` nutzt 1/8″, 1/2″, 1″. Jede Sprosse
muss ein **ganzes Vielfaches** der darunterliegenden sein; sonst wird abgelehnt,
denn ein Zahlstrich, der auf keinem Teilstrich sitzt, ist das stille
„fast richtig" aus § 5.1. Strichlängen sind feste Maße (1,2 / 2,0 / 3,0 mm) und
der Abstand zur Zahl ist 1 mm — ein Maßstab, den niemand verbiegen kann, ist der
Sinn eines Maßstabs (wie die Deckblattfiguren, § 8.8).

**Zahlen.** Eine Zahl nennt ihre Position **exakt**, mit den wenigsten Ziffern,
die das leisten: `label_every: 25mm` unter `unit: cm` druckt 2,5 — nie gerundet,
denn ein Maßstab, der ein falsches Maß druckt, ist schlechter als keiner. Auf den
**senkrechten** Kanten stehen die Zahlen um 90° gedreht (von unten nach oben
lesend), damit der benötigte Streifen auf allen vier Kanten gleich breit ist:
Strich + Abstand + Zahlenhöhe, statt links und rechts die volle Textbreite.

**Ablehnungen, alle vor Seite eins** (§ 12 Punkt 13), jede mit Millimetern:

1. Der Streifen passt nicht zwischen Musterkante und Blattkante.
2. Ein Kopf- oder Fußband endet dort — dann nennt die Meldung das Band.
3. Die Zahlen kollidieren: die breiteste wird beim Writer **gemessen**
   (§ 10.2) und mit `label_every` verglichen.
4. Eine Sprosse sitzt neben der Leiter (siehe oben), oder eine Kante ist
   unbekannt bzw. doppelt genannt.

Nichts wird geschrumpft, beschnitten oder verschoben, damit ein Lineal passt
(§ 8.2). Die Zahlen sind `Text`-Marken; auf PNG lehnt der Capability-Vorlauf den
Lauf mit Namen ab (§ 10.2, § 10.4).

---

## 9. Datendateien

### 9.1 Formattabelle (eingebaut)

`a3, a4, a5, letter, legal, tabloid …` mit Maßen, dem Default für den **nicht
bedruckbaren Rand** (§ 8.1, typisch 5 mm) und einer **angenommenen
Druckauflösung** (`assumed_dpi`, typisch 600). Letztere gibt es nur, damit die
Medienprüfung (§ 12.1) auch auf Papier greift — sie behauptet nichts über den
tatsächlichen Drucker, sondern liefert einen vernünftigen Prüfmaßstab.

```yaml
formats:
  - id: a4
    name: "A4"
    size: { x: 210mm, y: 297mm }   # stets im Hochformat
    margin: 5mm                    # nicht bedruckbarer Rand (§ 8.1)
    assumed_dpi: 600               # nur für die Medienprüfung (§ 12.1)
  - id: letter
    name: "US Letter"
    size: { x: 8.5in, y: 11in }
    margin: 5mm
    assumed_dpi: 600
```

**Nicht in der Def definieren** — A4 ist Weltwissen. Die Def *referenziert*
(`format: a4`) oder gibt frei an (`format: 8.5x11in`; dann greifen die
allgemeinen Defaults).

Maße stehen **immer im Hochformat**, wie bei den Geräteprofilen (§ 9.2);
`orientation: landscape` tauscht sie. Eine einzige Konvention für beide
Datendateien.

Das Format gehört eigentlich zum *Aufruf*: in der Def als Default, per CLI-Flag
überschreibbar.

### 9.2 Geräteprofile

Jedes Profil trägt **Pixel *und* physische Maße** — daraus fällt die Dichte, und
der Kern kann zwischen beiden Welten rechnen. Papier ist schlicht das Profil
ohne Pixel.

```yaml
devices:
  - id: remarkable-paper-pro
    name: "reMarkable Paper Pro"
    pixels:   { x: 1620, y: 2160 }        # Hochformat
    physical: { x: 179.7mm, y: 239.6mm }  # aus Pixeln und Dichte gerechnet
    density: 229dpi
    diagonal: 11.8in
    color: color             # am Gerät bestätigt (Farbgerät), § 15 Punkt 1
    margin: 0mm              # E-Ink hat keinen unbedruckbaren Rand (§ 8.1)
    quirks: []               # gerätespezifische Eigenheiten, siehe unten
    source: "owner-verified — Maße und Farbe am Gerät bestätigt"
    verified: 2026-07

  - id: remarkable-2
    name: "reMarkable 2"
    pixels:   { x: 1404, y: 1872 }
    physical: { x: 157.8mm, y: 210.4mm }
    density: 226dpi
    color: grayscale
    margin: 0mm
    quirks: []
    source: "manufacturer-specified — reMarkable-Vergleichsseite (2026): 1872×1404 px, 226 ppi, monochrom; nicht am Gerät geprüft"
    verified: 2026-07
```

**Pixel stehen im Hochformat**, auch wenn Herstellerangaben oft quer zählen
(„2160 × 1620"). Eine einzige Konvention, sonst kippt irgendwann ein Profil.

**Physische Maße werden aus Pixelzahl und Dichte gerechnet**, nicht aus
gerundeten Herstellerangaben übernommen. Beim Paper Pro ergibt 1620 ÷ 229 dpi
= 179,7 mm, was die vermarkteten „18 × 24 cm" bestätigt und zugleich präzisiert.
Die Diagonale fällt mit 11,79″ auf die angegebenen 11,8″ — die Angaben sind
also in sich stimmig, und `density` ist der gerundete Wert, nicht das Maß.

**`source` und `verified` sind Pflichtfelder bei mitgelieferten Profilen.**
Gerätespezifikationen sind genau die Sorte Daten, die sich still verbreiten und
still falsch werden. Zugleich ist ein belegtes Geräteprofil der ideale erste
Fremdbeitrag (§ 10.5).

**`quirks` ist bewusst vorgesehen.** Geräte haben Eigenheiten, die kein
px/mm-Modell vorhersagt: Ein Boox Note skaliert die Vorlage in der
Werkzeugleistenansicht destruktiv und verschluckt dabei etwa jede 16. Pixelzeile;
ein Generator muss die toten Zeilen kennen und Linien um ±1 px verschieben.
Geräteprofile brauchen Platz für solche Fälle, nicht nur für Maße.

> **Stand reMarkable:** Der Widerspruch beim Paper Pro (1620 × 2160 vs.
> 2160 × 2880, siehe [`docs/research.md`](research.md) § 8) ist **erledigt:
> 1620 × 2160 px bei 229 dpi.** Nicht nur quellenkonsistent, sondern **praktisch
> belegt** — ein mit genau diesen Maßen erzeugtes PDF sitzt auf dem Gerät exakt.
> Die Angaben sind zudem in sich stimmig (Diagonale 11,79″, physisch
> 179,7 × 239,6 mm, Verhältnis exakt 3:4). Die verbreitete Angabe 2160 × 2880
> ist falsch.
>
> Das ist zugleich der Belegtyp, den § 9.2 anstrebt: **ein am Gerät geprüftes
> Profil schlägt jede Herstellerseite.** Die rM2-Zahlen stützen sich nun auf die
> **offizielle reMarkable-Vergleichsseite** (Primärquelle statt Sekundär­konsens)
> und stimmen mit ihr exakt überein — 1872 × 1404 px bei 226 ppi, monochrom —,
> sind aber weiterhin **nicht am Gerät geprüft** und entsprechend markiert.
>
> **Zum Umfang:** Ein **PDF** wird als Dokument synchronisiert und beschrieben
> (kein Entwicklermodus nötig) — dafür ist das mehrseitige PDF exakt das richtige
> Artefakt. Eine echte **Vorlage** verlangt PNG in Geräteauflösung plus Eintrag
> in `templates.json` via SSH. Der PDF-Weg genügt; der PNG-Schreiber ist Kür.

Zwei abgeleitete Anforderungen: Das Seitenverhältnis 3:4 beider reMarkables ist
**nicht** A4 (1:√2) — relative Maßangaben sind nötig, nicht Kür.

Und Linien dünner als ein Pixel verschwinden oder werden stufig. Beim Paper Pro
ist **1 px = 0,111 mm = 0,314 pt** — die Standardstärke aus § 7.3
(`weight: 0.2pt`) wäre dort 0,64 Pixel und damit unbrauchbar. Das ist kein
Randfall, sondern der Normalfall beim Übertragen einer Papierdefinition aufs
Pad. Deshalb prüft das Werkzeug die Definition gegen das Medium, sobald dieses
feststeht — **unabhängig vom Ausgabeformat** (§ 12.1).

### 9.3 Presets

**Ein Preset ist eine mitgelieferte Definitionsdatei, kein einprogrammierter
Sonderweg.** Sonst spaltet sich das Werkzeug in Preset-Land und Custom-Land.

Nebeneffekt: **Die Presets sind auch die Dokumentation.**

Konkret benannte Defs statt eines parametrisierten Preset-Systems:
`millimeter-a4`, `millimeter-letter`, `quarter-inch-letter`, `calligraphy-a4`,
`cornell-a4`, `staves-12`, `dots-5mm`, `battleship`, `maze-medium`,
`target-10-rings`, `hex-8mm`, `semilog-a4`, `phone-log-a4`.

### 9.4 Namenslisten

**Gehören nicht in die Definitionsdatei.** Die Struktur ist die Form, die Liste
ist Wegwerf-Datei.

- Extern per `--names list.txt` (eine Zeile je Eintrag)
- Inline in der Def **erlaubt** für den Einmalfall, aber nicht Default

| Modus | Wer führt | Verhalten |
|---|---|---|
| datengetrieben | Namensliste | Ein Blatt je Eintrag. **Default bei `--names`.** |
| feste Anzahl | `--pages n` | Einträge zyklisch wiederholt bzw. abgeschnitten |

**Liste kürzer als `--pages`:** zyklisch wiederholen. **Liste länger:** die
ersten n Einträge verwenden — aber **die Ausgabe sagt es** („using 10 of 27
names"). Das ist der legitime Testfall („erst mal drei Blatt ansehen"), und es
ist kein stilles Verstümmeln, solange die Zahl genannt wird.

**Kodierung:** UTF-8 erwartet, BOM wird toleriert. Bei Dekodierfehler nennt die
Meldung **Zeilennummer und Byteposition** — nicht „invalid start byte". Aus
Tabellenkalkulationen exportierte Listen sind regelmäßig CP1252, und das ist
der häufigste Stolperstein an dieser Stelle.

Mechanisch ist das dasselbe Seite(i)-Modell wie der Maze-Seed.

---

## 10. Schreiber (Naht 3)

### 10.1 PDF (Pflicht, v1)

Vektoriell, exakte MediaBox, absolute Einheiten. Fonteinbettung für
Kopf-/Fußtext. Bibliothek: `reportlab` (BSD-3-Clause, vor Festlegung
gegenprüfen).

**Reproduzierbarkeit ist Anforderung.** `reportlab` schreibt standardmäßig
Erstellungszeit und Producer-Zeile, wodurch identische Eingaben unterschiedliche
Bytes ergeben und jeder Golden-File-Test in CI ausschlägt. Erforderlich:
Erstellungsdatum fest bzw. aus `SOURCE_DATE_EPOCH`, fester Producer-String,
deterministische Dokument-ID.

**Dateigröße ist ein reales Problem, kein theoretisches.** Linien sind O(X+Y)
Zeichenoperationen, Punkte O(X·Y). 5-mm-Punkte auf A4 sind ~2.500 Punkte je
Seite; als gefüllte Kreise aus je vier Bézierkurven ergibt das bei 30 Seiten ein
zweistelliges Megabyte-PDF. Zwei Gegenmittel, beide im Schreiber:

- **Punkte als nulllange Segmente mit runder Strichkappe** — ein Bruchteil der
  Bytes, optisch identisch.
- **Seitenunabhängige Muster als Form-XObject** einmal ablegen und je Seite
  referenzieren. Setzt `is_page_invariant` am Generator voraus (§ 3.3).

**Weitere Pflichten:** PDF-Metadaten (Titel, Autor, Ersteller) setzen; bei
datengetriebenen Läufen ein **PDF-Inhaltsverzeichnis mit den Listeneinträgen**,
damit ein 30-Seiten-Dokument navigierbar ist.

### 10.2 Fähigkeitsmodell und Vorabfragen

Naht 3 ist **bidirektional**:

```
capabilities()                          -> set[str]
text_width(content, font, size)         -> mm
missing_glyphs(content, font)           -> list[str]
```

Notwendig, weil § 12 verlangt, alle Seiten vorab durchzumessen — und
Fontmetriken kennt nur der Schreiber, während § 3.3 dem Kern jeden Kontakt zur
PDF-Bibliothek verbietet.

**Die Abfragen stehen auch Generatoren zur Verfügung** (§ 3.2). Segment- und
Gitterbeschriftungen müssen ebenso vorab passen wie Kopfzeilen.

`missing_glyphs` ist kein Randfall: Ein Name mit `ł`, `ğ` oder `ő` fehlt in der
Standardkodierung vieler Basisschriften und wird still als Kästchen gedruckt.

Fähigkeiten sind z. B. `opacity`, `color`, `text`, `arc`, `polygon`,
`image_png`, `image_svg`, `vector`.

**Die Prüfung läuft vor dem Rendern, nicht mittendrin** — Def gegen
Schreiberfähigkeiten abgleichen, dann klarer Abbruch mit Benennung des
fehlenden Features. Sonst entstehen halbe Dateien.

`--skip-unsupported` (Feature weglassen und weitermachen) ist sinnvoll, aber
**nur als ausdrückliche Entscheidung des Nutzers**. Der Name ist bewusst
sprechend: Ein `--anyway` neben dem `--force` aus § 11.3 wären zwei Flags, die
beide „mach trotzdem" heißen und Verschiedenes tun.

**Gebaut (2026-07).** Das Flag ist ein Einwegschalter wie `--cover` und `--strict`
und steht deshalb **nur** auf der Kommandozeile — eine Def kann es nicht
verlangen, weil das Weglassen die Entscheidung des Nutzers ist und nicht die des
Dokuments. Der Vorlauf lehnt dann nicht ab, sondern meldet **einmal**, was
fehlen wird; beim Schreiben lässt ein Hüllen-Writer genau die Marken aus, deren
Fähigkeit dem Schreiber fehlt, dazu Links, Lesezeichen und den Anhang. Eine
Hülle statt einer Prüfung an jedem `draw`-Aufruf: davon gibt es ein Dutzend, und
eine würde irgendwann vergessen (§ 5.1).

### 10.3 Schriften

**Zwei Stufen, bewusst getrennt.**

#### Stufe 1 (M1): drei logische Familien

```yaml
font: { family: sans, size: 9pt }   # serif | sans | mono
```

Aufgelöst über die **14 PDF-Standardschriften**, die jeder PDF-Betrachter
mitbringt und die deshalb *nicht eingebettet* werden müssen:

| `family` | Schrift |
|---|---|
| `serif` | Times |
| `sans` | Helvetica |
| `mono` | Courier |

je in normal, fett, kursiv und fett-kursiv.

**Das ist kein Rückfall in Systemschriften.** Der Einwand gegen Systemschriften
war die Reproduzierbarkeit — dass dasselbe Kommando auf zwei Rechnern
verschiedene Ergebnisse liefert. Bei den Standardschriften tritt das nicht ein:
Ihre **Metriken sind Teil der PDF-Spezifikation** und in `reportlab` fest
hinterlegt. Zeichenbreiten, Umbruchpunkte und damit die gesamte Geometrie sind
überall identisch; nur die konkrete Glyphenzeichnung darf der Betrachter
ersetzen. Für ein Werkzeug, dessen Zusage Maßhaltigkeit ist, zählt genau die
Geometrie.

Nebeneffekte, alle willkommen: keine mitgelieferte Schriftdatei, keine
Schriftlizenz im Repository, kein Einbettungsgewicht, und das PDF bleibt
schriftfrei — dieselbe Eigenschaft, die § 7.3 für die Notenschlüssel anstrebt.

**Der Preis ist die Glyphenabdeckung.** Die Standardschriften decken Latin-1 ab
(`ä ö ü ß é à ñ ç` ja, `…` ja) — aber **nicht** `ł`, `ğ`, `ő`. Bei einer
Namensliste mit polnischen, türkischen oder ungarischen Namen schlägt
`missing_glyphs` (§ 10.2) also zu, und die Antwort darauf ist Stufe 2. Die
Fehlermeldung muss das sagen, statt nur die fehlende Glyphe zu nennen.

**Diese Einschränkung gehört ausdrücklich ins README** (§ 13.3). Sie ist keine
Nebensächlichkeit: Wer eine Klassenliste einliest, trifft sie beim ersten
polnischen Namen — und dann soll die Antwort schon dastehen, statt als
Fehlermeldung zu überraschen.

#### Stufe 2 (M2): eine bestimmte Schriftdatei

```yaml
font: { file: "~/Library/Fonts/EBGaramond-Regular.ttf", size: 11pt }
```

**Angabe über den Dateipfad, nicht über den Namen.** Namenssuche ist auf jeder
Plattform anders (fontconfig, CoreText, Registry), liefert je nach installierten
Schriften andere Treffer und ist damit genau die Unzuverlässigkeit, die wir
vermeiden wollen. Ein Pfad ist eindeutig, prüfbar und in Fehlermeldungen
nennbar. Eine Namenssuche als Bequemlichkeit kann später darüber gelegt werden.

**Die Schrift wird eingebettet und untergesetzt** (nur die verwendeten Glyphen).
Damit ist das *PDF* auf jedem Rechner gleich; dass sein *Erzeugen* eine lokal
vorhandene Datei braucht, ist unvermeidlich und ehrlich. Die
Einstellungszusammenfassung auf dem Deckblatt (§ 8.8) nennt deshalb Dateiname
und Schriftversion.

**Einbettungsrechte werden geprüft, nicht angenommen.** TrueType- und
OpenType-Schriften tragen in der `OS/2`-Tabelle ein `fsType`-Feld, das
Einbettung untersagen kann. Wer das ignoriert, erzeugt PDFs, die die
Schriftlizenz verletzen. Ist die Einbettung untersagt, bricht das Werkzeug ab
und nennt die Schrift — kein stilles Ausweichen auf eine Ersatzschrift.

### 10.4 PNG (später)

Rasterung in exakter Geräteauflösung. Die Prüfung auf zu dünne Linien und
ungleichmäßige Raster liegt **nicht hier**, sondern in der Medienprüfung
(§ 12.1) — sie gilt für den PDF-Weg genauso.

### 10.5 Offenheit

Die Marken-Schnittstelle wird dokumentiert, damit Dritte eigene Schreiber
beitragen können. **Kein Lade-/Discovery-System.**

`CONTRIBUTING.md` benennt die zwei Beiträge, die ohne Codeverständnis möglich
sind: **neue Geräteprofile** (mit `source` und `verified`) und **neue Presets**.

---

## 11. Kommandozeile

```bash
ctrlgrid millimeter-a4 --pages 30 -o ~/Downloads/grid.pdf
ctrlgrid -d my-def.yaml --pages 10
ctrlgrid millimeter-a4 --names class3b.txt
ctrlgrid millimeter-a4 --format letter --stamp "DRAFT" --pages 5
ctrlgrid maze-medium --names class3b.txt --seed 4711
ctrlgrid millimeter-a4 --pages 30 --cover   # mit Deckblatt (§ 8.8)
ctrlgrid                                    # interaktiver Modus
```

| Kommando | Zweck |
|---|---|
| `ctrlgrid <preset\|-d file>` | Erzeugen |
| `ctrlgrid presets` | Presets auflisten |
| `ctrlgrid devices` | Geräteprofile auflisten |
| `ctrlgrid show <preset>` | Def ausgeben (zum Kopieren und Abwandeln) |
| `ctrlgrid check <file>` | Nur validieren, nichts erzeugen |

**Die Kommandozeile schlägt die Def — immer und ohne Ausnahme.** Jede Angabe,
die es als Flag gibt (`--format`, `--pages`, `--names`, `--stamp`, `--seed`,
`--cover`, `--orientation`, …), überschreibt den gleichnamigen Wert aus der
Definitionsdatei. Eine Rangordnung mit Ausnahmen wäre nicht merkbar; diese ist
es. Die Def liefert damit die Vorgabe, der Aufruf die Abweichung für diesen
einen Lauf.

### 11.1 Vollständige Flagliste

| Flag | Wirkung | Abschnitt |
|---|---|---|
| `-d`, `--def <datei>` | Eigene Definitionsdatei statt Preset | § 5 |
| `-o`, `--out <pfad>` | Ausgabepfad; Default Downloads-Ordner | § 11.3 |
| `--pages <n>` | Seitenzahl; überschreibt `pages.count` | § 9.4 |
| `--names <datei>` | Namensliste, ein Eintrag je Zeile | § 9.4 |
| `--format <name>` | Papierformat | § 9.1 |
| `--device <id>` | Geräteprofil statt Papierformat | § 9.2 |
| `--orientation <portrait\|landscape>` | Ausrichtung | § 8.1 |
| `--stamp <text>` | Ganzseitiger Stempel | § 8.6 |
| `--seed <n>` | Basis-Seed für prozedurale Generatoren | § 7.5 |
| `--cover` | Deckblatt mit Kalibrierquadrat erzeugen | § 8.8 |
| `--embed-def` | Die Def als Dateianhang ins PDF einbetten | § 8.8 |
| `--nup <sxz>` | Ausschießen, **ohne Skalierung** | § 14, M6 |
| `--nup-sheet <format>` | Bogenformat fürs Ausschießen | § 14, M6 |
| `--booklet` | Als gefalztes Heft ausschießen, **ohne Skalierung** | § 14 |
| `--force` | Vorhandene Ausgabedatei überschreiben | § 11.3 |
| `--skip-unsupported` | Nicht unterstützte Marken weglassen statt abbrechen | § 10.2 |
| `--strict` | Warnungen als Fehler behandeln | § 12.1 |
| `--quiet` | Nur den Ausgabepfad melden | § 11.3 |

**Alle Flags schlagen die Def** (§ 11). Zwei Flags sehen sich ähnlich und meinen
Verschiedenes: `--force` betrifft die *Datei*, `--skip-unsupported` das
*Feature*. Deshalb heißt keines von beiden `--anyway`.

`--nup` und `--nup-sheet` erscheinen erst mit M6.

### 11.2 Interaktiver Modus

`ctrlgrid` ohne Argumente fragt: Preset aus Liste → Seitenzahl bzw. Namensliste
→ Ausgabeort.

**Zweck: Preset-Browser, nicht Zugangsbrücke.** Bequemlichkeit für Nutzer, die
die Kommandozeile beherrschen — kein Ersatz für sie und kein Argument gegen eine
GUI (Nicht-Ziel, § 2).

### 11.3 Ausgabe

**Der Prozess schreibt die Datei selbst.** Default: Downloads-Ordner, per `-o`
überschreibbar.

**Eine vorhandene Datei wird nicht still überschrieben.** Ohne `--force` bricht
das Werkzeug ab. (Vergleichbare Werkzeuge werden für das Gegenteil ausdrücklich
kritisiert.)

Nach erfolgreichem Schreiben: Pfad, Seitenzahl, effektive Periode (§ 5.3) und
der Skalierungshinweis (§ 8.2). Mit `--quiet` nur der Pfad.

---

## 12. Validierung und Fehlerverhalten

**Grundsatz: laut scheitern, niemals still verstümmeln.**

Alles wird **vor** dem Schreiben der ersten Seite geprüft:

1. YAML-Syntax
2. Merge-Keys (`<<`) abgelehnt; Aliasexpansion innerhalb der Grenze (§ 5.4)
3. Versionszeile vorhanden und unterstützt
4. Unbekannte Schlüssel → Fehler (Vorschlag bei ähnlichem Namen via `difflib`).
   `defs` ist der einzige übersprungene Top-Level-Schlüssel
5. Einheiten parsebar
6. **Einheiten plausibel** (siehe unten)
7. Farbwerte als `#rrggbb` parsebar; Farbzyklen bei `dots` mit `axis` versehen
8. Generator existiert; sein Abschnitt vollständig
9. Musterbereich > 0 nach Abzug von Rändern, Kopf, Fuß **und Freiraumzeilen**
   (§ 8.1). Die Meldung nennt die Rechnung Posten für Posten — bei sechs
   Abzügen ist „pattern area is negative" nutzlos
10. **Anzahlgetriebener Inhalt passt in den Musterbereich** (siehe unten)
11. Einrasten auflösbar und für den Generator zulässig (§ 8.3)
12. Schreiber kann alle vorkommenden Markenarten (§ 10.2)
13. **Alle Seiten vorab durchgemessen** — in der Breite: passt jeder Kopf-,
    Fuß- und Beschriftungstext (bzw. ist `cut: true` gesetzt, § 8.9)? In der
    Höhe: reicht `header.height` / `footer.height` für Schriftgröße und Bilder
    (§ 8.4)? Und sind alle Glyphen in der Schrift vorhanden?
14. **Medienprüfung** gegen Auflösung und Farbfähigkeit (§ 12.1)

**Zu Punkt 6 — Plausibilität.** Der häufigste Nutzerfehler ist die
Einheitenverwechslung: `0.15mm` statt `0.15pt` ist Faktor 2,8; `5pt` statt `5mm`
ist Faktor 0,35. Konkrete Regeln:

- Strichstärke muss kleiner sein als der zugehörige Abstand (sonst läuft das
  Raster zu einer Fläche zusammen)
- Warnung bei Abweichung um mehr als Faktor 10 von der Größenordnung des
  zugrunde liegenden Presets

**Zu dünne Linien prüft Punkt 6 ausdrücklich nicht.** „Zu dünn" ist keine
absolute Größe, sondern hängt an der Auflösung des Mediums — 0,1 pt sind auf
600 dpi knapp brauchbar und auf 229 dpi unsichtbar. Diese Prüfung gehört
deshalb ganz in § 12.1; ein zweiter fester Schwellenwert hier würde ihr
widersprechen.

**Zu Punkt 10.** `staves`, `grid` und Log-Familien (§ 7.9) sind anzahl- bzw.
längengetrieben und können den Musterbereich sprengen; beim Herumprobieren ist
das der Normalfall. Meldung mit Rechnung: *„10 staves need 203 mm, pattern area
is 187 mm — reduce count to 9 or system_gap to 3sp."*

**Zu Punkt 13.** Bei 30 Namen scheitert der siebzehnte. Wird erst beim Rendern
geprüft, liegen 16 Seiten schon in der Datei. Also **komplett abbrechen oder
komplett bauen.**

**Fehlermeldungen müssen handlungsfähig machen.** Nicht „text does not fit",
sondern: welcher Eintrag, wie breit, wie viel Platz war da. Werte werden in der
**vom Nutzer geschriebenen Einheit** genannt (§ 3.3).

### 12.1 Medienprüfung

**Sobald das Medium feststeht** — Geräteprofil oder Papierformat —, prüft das
Werkzeug die Definition gegen dessen Eigenschaften und meldet, was auf diesem
Medium nicht funktionieren wird.

**Das ist ausdrücklich keine Aufgabe des Schreibers.** Eine 0,2-pt-Linie ist auf
einem 229-dpi-Gerät 0,64 Pixel breit, ob wir nun PDF oder PNG ausgeben. Wer die
Prüfung an den PNG-Schreiber hängt, findet den Fehler erst, wenn er ohnehin
sichtbar wäre — und beim PDF-Weg (§ 9.2), der der übliche ist, nie.

Grundlage ist eine **Auflösung je Medium**: bei Geräteprofilen `density`, bei
Papierformaten ein angenommener Druckwert (`assumed_dpi`, § 9.1, typisch 600).

**Auch Dokumentgeneratoren werden geprüft** (§ 7, festgelegt beim Bau 2026-07).
Eine Klinge füllt eine Musterfläche mit einem sich wiederholenden Muster —
Seite 0 zeigt alles, was sie hat. Ein Dokument besitzt dagegen ungleiche Seiten,
deshalb werden **alle** Seiten durchlaufen und je Stärke und Farbe eine Marke
behalten. Nicht eine Seite je Seitenart: die eigene Farbe eines markierten Tages
steht nur auf den Seiten dieses Datums, ein Geburtstag im Mai bliebe also
ungemessen — das stille „fast richtig" aus § 5.1. Der volle Durchlauf eines
Jahresplaners mit 456 Seiten kostet etwa zwei Zehntelsekunden, einmal pro Lauf.
Die **Hintergrundfarbe einer Seite** zählt dabei als Farbe mit, obwohl der Griff
sie malt und sie keine Marke ist: auf einem Graustufenschirm ist gerade sie es,
die zu Brei wird.

#### Auflösungsbedingte Befunde

| Befund | Bedeutung |
|---|---|
| Strichstärke oder Punktdurchmesser **< 1 px** | verschwindet oder wird zufällig ein Pixel dick |
| **1–2 px** auf E-Ink | wird stufig; die Kantenglättung ist dort schwach |
| Abstand benachbarter Marken **< 3 px** | Linien laufen optisch zu einer Fläche zusammen |
| Positionen **nicht auf ganzen Pixeln** | ungleichmäßige Zellen (siehe unten) |

Der letzte Punkt ist der unauffälligste und der ärgerlichste: Ein 5-mm-Raster
sind auf 229 dpi **45,08 px** je Zelle. Gerundet wird daraus abwechselnd 45 und
46 Pixel — das Raster *sieht* ungleichmäßig aus, obwohl es exakt gerechnet ist.
Die Meldung nennt deshalb die Zellbreite in Pixeln und die auftretende
Schwankung, nicht bloß „nicht ganzzahlig".

#### Farbbedingte Befunde

| Befund | Bedeutung |
|---|---|
| Farbe auf `color: grayscale` | wird zu Grau; die Meldung nennt den Grauwert |
| **Zwei Farben, die denselben Grauwert ergeben** | die Betonung verschwindet vollständig |

Der zweite Fall ist der heimtückische: Wer Raster in `#7799bb` und Betonung in
`#4466aa` setzt, hat auf Farbe einen klaren Unterschied — und auf einem
Graustufengerät zwei fast identische Grautöne. Genau die Linien, die man sehen
soll, verschwinden.

#### Meldeform

- **Gesammelt vor dem Rendern**, nicht einzeln beim Auftreten.
- **Warnungen, kein Abbruch** — das Medium mag trotzdem gewollt sein. Ausnahme:
  Werte, die auf null runden, sind ein Fehler.
- Immer **mit der konkreten Zahl**: „line weight 0.2pt = 0.64px at 229dpi",
  nicht „line too thin".
- **`--strict` macht Warnungen zu Fehlern.** Nötig, damit CI-Läufe und
  `ctrlgrid check` eine Preset-Sammlung tatsächlich absichern können.

---

## 13. Implementierung

- **Sprache: Python** (≥ 3.11)
- **PDF:** `reportlab`
- **PNG (später):** `Pillow`
- **YAML:** `ruamel.yaml`, **nicht** `PyYAML`. Grund: § 12 verlangt
  handlungsfähige Fehlermeldungen, und dazu gehört die **Zeilennummer** in der
  Def. `PyYAML` wirft die Position beim Laden weg; `pydantic` kennt danach nur
  noch den Schlüsselpfad. Bei einer 80-zeiligen Preset-Kopie ist
  „families.2.base_spacing" deutlich schlechter als „line 47". Der Aufpreis ist
  eine etwas umständlichere Bibliothek — die Fehlermeldungen sind laut § 12 „das
  Gesicht des Werkzeugs", also ist er gerechtfertigt.
- **Validierung:** `pydantic` (`extra="forbid"` erfüllt Punkt 4 aus § 12 direkt)
- **CLI:** `typer`
- **Tests:** `pytest` + `pypdf` zum Zurücklesen erzeugter PDFs
- **SVG:** **nicht in v1.** `svglib` ist die fragilste denkbare Abhängigkeit —
  „SVG" reicht von zwei Pfaden bis zu Filtern, Verläufen und Clip-Paths. In v1
  nur PNG als Bildquelle, mit klarer Fehlermeldung bei `.svg`.
- **Schriften:** keine mitgelieferte Schriftdatei. Stufe 1 nutzt die
  PDF-Standardschriften (feste Metriken, keine Einbettung), Stufe 2 eine
  benannte Schriftdatei mit Einbettung und `fsType`-Prüfung — Einzelheiten und
  Begründung in § 10.3. Für Stufe 2 wird `fontTools` gebraucht.
- **Distribution:** PyPI, `uvx ctrlgrid …`, Release über GitHub Actions bei Tag.

### 13.1 Projektstruktur

```
ctrlgrid/
  cli.py              Argumente, interaktiver Modus
  model.py            validierte Datenklassen, Einheiten, Farben
  units.py            Parsen und Normalisieren auf int µm
  loader.py           YAML → Modell, Presets, Geräte, Formate
  pages.py            Seitenschleife, Seitenkontext, Platzhalter
  frame.py            Kopf, Fuß, Rahmen, Stempel, Lochmarken
  marks.py            Marken-Vokabular (Naht 2)
  cycles.py           Zyklusauswertung, law=linear|log10
  generators/
    __init__.py       Registry: name → Generator
    lines.py
    dots.py
    staves.py
    grid.py
    maze.py
    polar.py
    tiling.py
    form.py
  writers/
    __init__.py       Registry, Fähigkeiten, Vorabfragen (Naht 3)
    pdf.py            EINZIGE Stelle mit reportlab
    png.py            später
  data/
    formats.yaml
    devices.yaml
    presets/*.yaml
tests/
  test_dimensional.py Maßhaltigkeit: PDF zurücklesen, Koordinaten prüfen
```

Eine neue Klinge ist ein Registry-Eintrag und bekommt Rahmenwerk, Seitenschleife
und Ausgabe geschenkt. Genau daran misst sich, ob das Taschenmesser hält.

### 13.2 Tests und CI

Maßhaltigkeit ist die zentrale Zusage (§ 1) und darf keine Behauptung bleiben.
Der wichtigste Test ist kein Unit-Test: **PDF erzeugen → mit `pypdf`
zurücklesen → MediaBox und Markenkoordinaten gegen Sollwerte prüfen.** Das
gehört in M1 — nachträglich eingezogen findet er nichts mehr, weil man die
Sollwerte dann aus dem Ist ableitet.

Golden-File-Vergleiche prüfen **geparste Geometrie, nicht Bytes** — sonst bricht
jedes `reportlab`-Update die Suite.

GitHub Actions führt die Suite bei jedem Push und PR aus.

### 13.3 Dokumentationspflichten (README)

Neun Punkte sind über dieses Dokument verstreut, die der Nutzer **vor** dem
ersten Lauf wissen muss. Sie stehen hier gesammelt, damit keiner beim Schreiben
des README vergessen wird — jeder von ihnen führt sonst zu einer Überraschung,
die wie ein Fehler des Werkzeugs aussieht.

1. **Glyphenabdeckung.** Ohne eigene Schriftdatei ist nur Latin-1 verfügbar;
   `ł`, `ğ`, `ő` und alles außerhalb fehlen. Ausweg: `font: { file: … }`
   (§ 10.3). Der wahrscheinlichste erste Stolperstein überhaupt.
2. **Druckeinstellung.** „Actual size" bzw. „100 %" wählen, **nicht** „Fit to
   page" — sonst ist das Blatt nicht maßhaltig (§ 8.2). Mit dem Hinweis, dass
   `--cover` ein Kalibrierquadrat mitliefert.
2b. **Anzeige auf Pads.** Maßhaltig nur seitenfüllend und ohne Zoom. Wer ein
   Geräteprofil verwendet, bekommt genau dafür die passende Seitengröße
   (§ 8.2) — das ist der Hauptgrund, Geräteprofile zu benutzen.
3. **Nicht bedruckbarer Rand.** Ränder unter etwa 5 mm schneiden die meisten
   Drucker ab (§ 8.1).
4. **Ausschießen skaliert nicht.** `--nup` setzt Seiten bei 100 % und scheitert,
   wenn sie nicht passen — anders als `pdfjam` und `pdfcpu`, und das überrascht
   jeden, der die kennt (§ 14, M6).
5. **`{date}` macht das Ergebnis datumsabhängig** und damit nicht mehr
   reproduzierbar (§ 8.10).
6. **Kein GUI-Modus** — auch nicht geplant (§ 2). Gehört gesagt, bevor jemand
   danach sucht.
7. **Installation über `uvx`/`pip`**, keine doppelklickbaren Binaries (§ 2).
8. **`solution: back_mirrored`** (§ 7.5) verlangt beidseitigen Druck mit Wenden
   über die **lange Kante**, und ob die Lösung wirklich durchscheint, hängt an
   Papierstärke und Opazität. Beides außerhalb unserer Kontrolle, beides
   überraschend, wenn es nicht dasteht.
9. **Zwei Duplexmodi wenden verschieden** (ergänzt 2026-07-27). Ein Heft (§ 14)
   ist für die **kurze** Kante gebaut, `back_mirrored` (§ 7.5) setzt die
   **lange** voraus. Wer beides kennt, verwechselt sie sonst — jeder Lauf nennt
   deshalb die Kante, die *er* meint.

Ergänzend: Die Presets sind zugleich Beispieldokumentation (§ 9.3), das README
soll also auf sie verweisen statt eine eigene Syntaxreferenz aufzumachen, die
auseinanderdriftet.

**Umgesetzt in `README.md`.** Die Einschränkungen stehen dort unter
„Known limitations"; Punkt 6 aus der Liste oben (kein GUI) und Punkt 7
(Installation) sind in den Fließtext gewandert, weil sie dort weniger nach
Entschuldigung klingen. Solange keine Implementierung existiert, trägt das
README einen Statushinweis — er entfällt mit M1.

---

## 14. Meilensteine

**M1 — Die Achse durchstechen.** Parser + Modell, Einheiten (`mm cm in pt`;
`px` erst mit den Geräteprofilen in M5), *ein* Generator (`lines`),
PDF-Schreiber, Seitenschleife mit Kopf/Fuß, Vorabfrage-API (§ 10.2),
Maßhaltigkeitstest + CI (§ 13.2), PyPI-Release über `uvx` erreichbar.
Ein senkrechter Durchstich durch alle Schichten.

**Das Markenvokabular (§ 6) steht ab M1 vollständig** — es ist Vertrag, nicht
Ausbaustufe. Der PDF-Schreiber darf zu Beginn weniger können; was er kann,
meldet er über `capabilities()` (§ 10.2), und die Vorabprüfung fängt den Rest
ab. So wächst nie die Schnittstelle, sondern nur ihre Erfüllung.

**Abnahmekriterien.** M1 ist fertig, wenn all das zutrifft — nicht früher:

1. `uvx ctrlgrid millimeter-a4 --pages 3 -o out.pdf` erzeugt ein dreiseitiges
   PDF ohne weitere Einrichtung.
2. Der Test aus § 13.2 liest dieses PDF zurück und bestätigt: MediaBox
   210 × 297 mm, Linienabstand 1,000 mm, Betonung jede fünfte Linie — jeweils
   auf 1 µm genau.
3. Zweimal erzeugt ergibt **byteidentische** Dateien (§ 10.1).
4. `ctrlgrid check` meldet bei einem Tippfehler im Schlüssel den Fehler **mit
   Namensvorschlag**, und bei einem zu langen Kopfzeilentext Feldnamen, Breite
   und verfügbaren Platz (§ 12).
5. Kopf und Fuß werden über `text_width` ausgemessen, nicht geschätzt — die
   Vorabfrage-API (§ 3.6) ist wirklich benutzt, nicht nur vorhanden.
6. `import reportlab` kommt ausschließlich in `writers/pdf.py` vor; ein Test
   prüft das (§ 3.3).
7. CI läuft grün auf Linux, macOS und Windows.

Punkt 3 und 6 sind die, die man später nicht mehr nachrüstet, ohne umzubauen.

**M2 — Griff komplettieren.** Schriften Stufe 2 (§ 10.3), Rahmen, Stempel,
Lochmarken, Hintergrundfarbe,
Deckblatt (§ 8.8), **Duplex mit tauschendem `inner`/`outer`** (§ 8.1),
Platzhalter, Namenslisten (beide Modi), Einrasten, `remainder`, begrenzte
Familien (`count`), Formattabelle, Presets, `check`, PDF-Metadaten und
Inhaltsverzeichnis, Überschreibschutz, gute Fehlermeldungen.

**M3 — `polar` als Härtetest.** Bewusst als *zweite* Klinge, nicht als letzte.
Alle übrigen Generatoren arbeiten kartesisch; wenn der Griff auch mit einem
polaren Generator zurechtkommt — Musterbereich, Rahmenwerk, Fähigkeitsprüfung,
Beschriftungsmessung —, dann trägt die Architektur. Fällt sie auseinander, will
man das nach Klinge zwei wissen, nicht nach Klinge sieben. Erste Klinge, die
`Arc` und `Polygon` tatsächlich benutzt — im Vokabular stehen sie seit M1.

**M4 — Restliche Klingen.** `dots`, `staves`, `grid`, `maze`, `tiling`, `form`,
`law: log10`.

**M5 — Geräte.** Geräteprofile, px/mm-Umrechnung, `quirks`, relative Maßangaben.
Ggf. SVG-Bildquellen.

**M6 — Druckweiterverarbeitung.** Ausschießen `--nup 2x2` mit optionalen
Schnittmarken. Arbeitet auf **fertigen Seiten** und verletzt daher das „kein
Layoutsystem"-Prinzip nicht. Kein untersuchter Papiergenerator kann das; Nutzer
werden sonst auf `pdfjam` oder `pdfcpu` verwiesen.

**Ausschießen skaliert nicht — niemals.** Jedes vergleichbare Werkzeug
verkleinert beim N-up die Einzelseiten, damit sie auf den Bogen passen. Aus 5 mm
würden dann 2,5 mm, und das widerspricht § 8.2 unmittelbar. Bei uns gilt
stattdessen:

- Seiten werden bei **100 %** auf den Bogen gesetzt.
- Passen sie nicht, ist das ein **Fehler mit Rechnung** („4 A4 pages at 100 %
  need 420 × 594 mm, sheet is 210 × 297 mm — use a larger `--nup-sheet` or a
  smaller page format"), keine automatische Verkleinerung.
- Der sinnvolle Anwendungsfall ist damit: kleines Format definieren
  (A6, A5), großen Bogen bedrucken, zerschneiden.

Das ist unüblich gegenüber `pdfjam` und `pdfcpu` — und die einzige mit der
Kernzusage verträgliche Auslegung.

**`--booklet` — Rückstichheftung (2026-07-26).** Ein gefalztes Heft: Bogen *i*
trägt vorne die Seiten `P − 2i` und `2i + 1`, hinten `2i + 2` und `P − 2i − 1`,
mit *P* der auf ein Vielfaches von vier aufgerundeten Seitenzahl. Acht Seiten
ergeben also 8-1, 2-7, 6-3, 4-5. Geometrisch ist das ein 2×1, also gilt alles
oben Gesagte unverändert — insbesondere, dass **nicht skaliert** wird. Was
hinzukommt, ist allein die **Reihenfolge**.

Eine Seitenzahl, die kein Vielfaches von vier ist, wird **aufgefüllt und
gemeldet**, nicht abgelehnt: Das leere Blatt entsteht physisch, sobald man
faltet, und es wird kein Maß verändert — § 8.2 ist also nicht berührt, und § 5.1
verlangt nur, dass es nicht still geschieht. Eine aufgefüllte Zelle zeichnet gar
nichts, auch keinen Kopf und keinen Fuß, und `{page_count}` zählt sie nicht: Sie
ist eine Tatsache über das Papier, nicht über das Dokument.

**Eine Lage**, ineinandergelegt und durch den Falz geheftet. Lagen wählbarer
Größe sind bewusst nicht gebaut — sie brächten eine zweite Zählung und die Frage
nach der angebrochenen letzten Lage, und niemand hat danach gefragt. Ab etwa
vierzig Seiten wird der Falzversatz sichtbar; eine Falzversatz-Kompensation wäre
eine geratene Zahl und entfällt aus demselben Grund wie die Falzzugabe je Rille
(§ 7.14).

**Die Wendekante ist wählbar, und die Vorgabe ist die kurze** (`--booklet-flip
short | long`, ergänzt 2026-07-26). Der Falz läuft senkrecht, also dreht sich ein
Querbogen um seine kurzen Kanten: links und rechts tauschen, oben bleibt oben.
Das ist die Vorgabe. Über die **lange** Kante gewendet bleiben die Hälften, wo
sie sind, und das Blatt steht kopf — die Rückseite wird deshalb **um 180° gedreht
gedruckt**, damit der Leser sie nach dem Wenden richtig herum sieht.

Die **Falzordnung ist für beide Kanten dieselbe**. Das ist keine Bequemlichkeit,
sondern Geometrie: eine halbe Drehung vertauscht die beiden Hälften bereits, und
zusätzlich umzusortieren vertauschte sie zweimal. Der Unterschied ist allein die
Drehung der Rückseiten.

Dafür gibt es `rotate_180` im Markenvokabular — eine **Drehung**, keine
Spiegelung, und damit die erste Transformation, die **Text mitnimmt**:
`mirror_x`/`mirror_y` lassen Schrift ausdrücklich stehen (§ 7.5, § 8.5), weil
spiegelverkehrte Schrift niemand will. Kopfstehende Schrift will man hier sehr
wohl, denn der Leser dreht das Papier.

Der Laufbericht nennt die *gewählte* Einstellung, den Handgriff, der sie prüft
(Seite 2 muss hinter Seite 1 liegen), und den Schalter für den anderen Fall — wie
§ 8.2 es für die Skalierung verlangt. Ein unbekannter Wert wird abgelehnt, und
`--booklet-flip` ohne `--booklet` ebenfalls.

**Und er merkt, wenn dieser Handgriff nicht geht** (ergänzt 2026-07-26, nach dem
ersten gedruckten Heft). Auf leerem Rasterpapier — dem häufigsten, was dieses
Werkzeug erzeugt — steht überhaupt keine Zahl, „Seite 2 hinter Seite 1" ist dort
also nicht falsch, sondern *unausführbar*, und § 12 zählt eine Anweisung, nach der
niemand handeln kann, als Fehler. Trägt kein Band `{page}`, nennt der Bericht
deshalb den einen Weg, es prüfbar zu machen (`footer: {center: "{page}"}` für
einen Probelauf) — und sagt dazu, dass die Wendekante bei völlig gleichen Seiten
ohnehin gleichgültig ist. Trägt ein Band die Zahl, schweigt er: das Blatt
beantwortet die Frage dann selbst.

**Abgelehnt wird, vor Seite eins:** `--booklet` neben `--nup` (zwei Wege für
dasselbe), `--booklet` an einem Dokument-Generator (wie `--nup`, Entscheidung
52), `--nup-sheet`/`--crop-marks` ohne beides, und ein Bogen, auf den zwei Seiten
bei 100 % nicht passen — mit dem **Querformat in der Meldung**, denn die
Formattabelle steht im Hochformat (§ 9.1) und `--nup-sheet a4` kann deshalb nie
der richtige Bogen sein. `--cover` bleibt erlaubt und vom Ausschießen ausgenommen
(§ 8.8); die Folge ist ein PDF mit zwei Seitengrößen, wie bei `--nup` auch.

*Nebenwirkung:* Ausschießen zerstört Verknüpfungen und Lesezeichen in PDFs.
Wird beides gebraucht, muss das Inhaltsverzeichnis **nach** dem Ausschießen
entstehen. Das Deckblatt (§ 8.8) ist vom Ausschießen ausgenommen.

*(Bundsteg und Duplex sind seit der Überarbeitung von § 8.1 Kerngeometrie und
liegen in M2 — sie sind keine Nachbearbeitung, sondern bestimmen den
Musterbereich.)*

**M7 (optional) — PNG-Schreiber.** Erst, wenn der Pad-Vorlagenweg wirklich
gebraucht wird.

**M8 (vorgesehen) — `perspective` und `mandala`** (§ 7.11). Nach M6, damit beide
den gespiegelten Bundsteg von Anfang an mitbekommen.

**M9 — Notenschlüssel für `staves`** (§ 7.3, § 15.3). *Umgesetzt.* Ein Schlüssel
ist eine `Text`-Marke aus einer eingebetteten, subgesetzten Musikschrift
(Bravura, SIL OFL, auf die vier Schlüsselglyphen reduziert und nach
OFL-Vorgabe umbenannt, mitgeliefert). Größe und Lage folgen SMuFL:
`clef: treble | bass | alto | tenor` am Fünfliniensystem.

---

## 15. Offene Entscheidungen

Entschieden und eingearbeitet: Lizenz (MIT), Name (`ctrlgrid`), Sprache
(englisch), Koordinatenursprung (links unten), Schriften (zweistufig, § 10.3),
Notenschlüssel (eingebettete Musikschrift statt Vektorpfad, § 15.3),
Farbmodell (RGB `#rrggbb`),
Markenvokabular (sechs Primitive, § 6), interne Einheit (int µm für Positionen),
Seitenaufbau (§ 8.1), Platzhalter (§ 8.10), Beschriftungsmuster (§ 7.10),
Rangordnung CLI über Def (§ 11).

Bewusst noch offen:

1. **reMarkable:** Paper Pro ist vollständig geklärt — 1620 × 2160 px, 229 dpi,
   und **als Farbgerät geführt** (beides am Gerät bestätigt, 2026-07, § 9.2).
   Die **rM2-Zahlen** stützen sich jetzt auf die **offizielle
   reMarkable-Vergleichsseite** (1872 × 1404 px, 226 ppi, monochrom) und stimmen
   mit ihr exakt überein — Primärquelle statt Sekundärkonsens. Offen bleibt nur
   noch die On-Device-Prüfung, wie sie der Paper Pro hat; die Zahlen selbst sind
   kein Rateposten mehr (§ 9.2).
2. **Ob doch eine Schrift mitgeliefert werden muss.** Stufe 1 (§ 10.3) deckt nur
   Latin-1 ab. Zeigt sich, dass Namen mit `ł`, `ğ` oder `ő` häufig genug sind,
   um Stufe 2 zur Pflicht zu machen, wäre eine mitgelieferte OFL-Schrift der
   bequemere Weg. Erst nach Erfahrung entscheiden, nicht auf Verdacht.

   **Der Boden dafür ist seit 2026-07-26 gelegt, die Frage bleibt offen.** Bis
   dahin war sie theoretisch, weil ein fehlendes Zeichen in Generatortext gar
   nicht auffiel: `missing_glyphs` lief nur über die Bänder, ein polnischer
   Monatsname wurde still als Kästchen gedruckt, und ein Dokument-Generator nahm
   überhaupt keine Schrift entgegen — die dokumentierte Abhilfe existierte für
   ihn also nicht. Beides ist behoben (§ 7.12, § 12 Punkt 13). Damit ist Stufe 2
   für jeden Fall *erreichbar*, und die Frage lautet jetzt sauber: ist sie
   **zumutbar**, oder soll eine breite OFL-Schrift mitreisen? Das entscheidet
   Gebrauch, nicht Verdacht — aber es entscheidet ihn jetzt an einer Stelle, wo
   der Nutzer die Wahl überhaupt gezeigt bekommt.
3. ~~**`reportlab`-Lizenz** am Repository gegenprüfen (BSD-3-Clause erwartet).~~
   **Geklärt (2026-07-24):** reportlab 5.0.0 steht unter **BSD-3-Clause** — der
   Lizenztext (`reportlab-5.0.0.dist-info/licenses/LICENSE`) führt exakt die drei
   Bedingungen (Copyright-Hinweis in Quell- und Binärform, keine Werbung mit dem
   Firmennamen), ohne Advertising-Klausel. Belegt zusätzlich über die
   Paket-Metadaten (`License :: OSI Approved :: BSD License`). Verträglich mit der
   MIT-Lizenz von ctrlgrid; reportlab bleibt Laufzeitabhängigkeit, nicht
   mitgeliefert — nichts weiter zu tun.
4. **Weitere domänenspezifische Einheiten** — Federbreiten (Kalligraphie) und
   `lpi` (lines per inch). Dasselbe Muster wie `sp` bei den Notensystemen
   (§ 7.3): Die Domäne rechnet nicht in Millimetern. Billig, aber erst sinnvoll,
   wenn die betroffenen Generatoren stehen.
   Ebenso offen: die **nummerierten Rastralgrößen 0–8** — erst belegen, dann
   ausliefern (§ 7.3).
5. ~~**Def als Dateianhang im PDF einbetten** (§ 8.8).~~ **Gebaut (2026-07-24):**
   `--embed-def` / `pages.embed_def`. Das Dokument trägt jetzt seinen eigenen
   Quelltext — die exakten Bytes, über die auch die Prüfsumme läuft. Mechanik in
   § 8.8: ein `EmbeddedFile`-Stream und der Namensbaum `/Names /EmbeddedFiles`,
   von Hand gebaut (reportlab kennt keine Filespecs), determiniert und PDF-only
   (der PNG-Schreiber lehnt benannt ab, § 10.2). Verifiziert per CLI und zwei
   unabhängigen Parsern (pypdf, pikepdf/qpdf). Offen bleibt nur der ursprüngliche
   *Verdacht* — wie Betrachter und Synchronisationsdienste mit Anhängen umgehen;
   das entscheidet die Praxis, nicht der Code.
6. **Wendekante beim Duplexdruck.** ~~Ob ein Schalter nötig ist, zeigt die
   Praxis.~~ **Für das Heft gebaut (2026-07-26):** `--booklet-flip short | long`,
   Vorgabe kurz (§ 14). Die Einschätzung „eine einzige Fallunterscheidung beim
   Spiegeln" traf dabei **nicht** zu: eine Spiegelung genügt nicht, die Rückseite
   muss um 180° *gedreht* werden, und eine Drehung nimmt anders als eine
   Spiegelung den Text mit — daher `rotate_180` als dritte Transformation im
   Vokabular. Offen bleibt allein `back_mirrored` (§ 7.5), das weiterhin die
   lange Kante voraussetzt und sie benennt; dort *wäre* es die eine
   Fallunterscheidung, weil nur die Musterebene gespiegelt wird und kein Blatt
   kopfsteht.

### 15.1 Vorgesehen, aber nicht in v1

- **`perspective` und `mandala`** als eigene Klingen im Musterbereich (§ 7.11,
  M8). Beide nutzen das Zyklusmodell nicht — ein Generator darf eigene Gesetze
  rechnen (§ 5.3). Die Voraussetzungen dafür stehen bereits: `Arc` und `Polygon`
  im Vokabular (§ 6) und die Polargeometrie aus M3.

### 15.2 Ausdrücklich verworfen

- **Freie Kurven und Pfade** (§ 2). `Arc` deckt Kreisbögen ab; Bézierkurven,
  Splines und beliebige Pfade wären der Einstieg in eine allgemeine
  Zeichensprache und damit in ein anderes Projekt.
- **Kalibrierquadrat auf *jedem* Blatt.** Die Recherche bestätigt, dass
  Druckskalierung die häufigste Beschwerde über alle vergleichbaren Werkzeuge
  ist; [calcbe](https://calcbe.com/en/tools/) druckt sein 50-mm-Quadrat deshalb
  auf nahezu jeden Bogen. Bei uns sitzt es stattdessen auf dem Deckblatt
  (§ 8.8) — Metainformation über den Druck gehört nicht auf das Papier selbst.
  Siehe [`docs/research.md`](research.md) § 5 und § 6.

### 15.3 Notenschlüssel: eingebettete Musikschrift, kein Vektorpfad

Ursprünglich wollte § 7.3 die Schlüsselglyphen als **fest hinterlegte
Vektorpfade** — fontfrei und selbsttragend. Das steht im Widerspruch zu § 6: das
Markenvokabular ist auf sechs Primitive festgelegt, ausdrücklich als *Vertrag*
und nicht als Baustufe, und keines der sechs ist ein Kurvenpfad. § 15.2 verwirft
freie Pfade zusätzlich als Einstieg in eine allgemeine Zeichensprache. Ein aus
`Arc` und `Polygon` zusammengesetzter Violinschlüssel wäre erkennbar falsch —
genau das *fast richtige* Blatt, das § 5.1 als schlimmste Fehlerklasse führt.

**Entscheidung.** Ein Schlüssel wird eine **`Text`-Marke in einer eingebetteten
Musikschrift** — kein neues Primitiv, kein Vektorpfad. Das eigentliche Ziel von
§ 7.3 war nicht *fontfrei* um seiner selbst willen, sondern **selbsttragend**.
Fonts Stufe 2 (§ 10.3) bettet ein und subsettet, das PDF trägt dann nur die
wenigen benötigten Schlüsselglyphen und bleibt selbsttragend. Das Ziel ist damit
erreicht, ohne das Vokabular zu vergrößern: § 6 und § 15.2 bleiben unangetastet.
Wiederverwendet werden die `fsType`-Lizenzprüfung, das Subsetting, die
Coverage-Prüfung (§ 10.3) und der Capability-/Orakel-Mechanismus, über den der
PNG-Schreiber Text, den er nicht rendern kann, vorab und benannt ablehnt
(§ 10.2, § 10.4).

**Verworfen wurde** das siebte Primitiv (ein Pfad): es widerspräche § 6 und
§ 15.2 direkt und wäre Arbeit für *jeden* künftigen Schreiber (§ 6). Ebenso
verworfen wurde, die Schlüssel ganz zu streichen — § 7.3 nennt sie ausdrücklich,
und Vordruck-Schlüssel sind für Unterricht und Tabulatur real gefragt.

**Mitgelieferte Schrift, überschreibbar.** Damit `clef: treble` ohne Zutun
funktioniert, liefert das Werkzeug eine kleine Musikschrift unter OFL mit (auf
die Schlüsselglyphen subgesettet). Die Alternative — der Nutzer muss selbst eine
SMuFL-Schrift beschaffen — ließe das bequeme Feature an der Beschaffungshürde
scheitern. Wer eine bestimmte Stichschrift will, überschreibt sie über den
bestehenden `font: {file:}`-Weg (§ 10.3). Für den Musik-Fall ist damit Punkt 2
der offenen Fragen beantwortet: hier *wird* eine Schrift mitgeliefert.

**Umgesetzt (M9).** Mitgeliefert wird Bravura (SIL OFL), auf die vier
Schlüsselglyphen subgesettet und — weil reportlab keine CFF-Umrisse einbettet —
nach TrueType konvertiert; die OFL verlangt für eine geänderte Fassung einen
anderen Namen als den reservierten, also heißt sie nicht mehr „Bravura". Größe
und Lage sind reine SMuFL-Konvention und brauchen keine Nachjustierung pro
Glyph: ein Em sind vier Zeilenabstände (Schriftgröße = 4 × `stave_space`), und
der Glyph-Ursprung sitzt auf der Referenzlinie (G-, F- bzw. Mittellinie), auf
die die Text-Grundlinie gelegt wird. Schlüssel gibt es nur am Fünfliniensystem —
auf Tabulatur hat ein Notenschlüssel keine Linie, das wird abgelehnt statt
geraten. Auf dem PNG-Weg erscheint kein Schlüssel, weil dort kein
Schrift-Rendering existiert; der Capability-Check sagt das vorab (§ 10.4).
