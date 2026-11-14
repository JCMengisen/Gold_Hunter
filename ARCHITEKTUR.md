# Gold Hunter – Architektur

Klassisches Jump and Run in LabVIEW. Claude sammelt in einer unterirdischen Pyramide so viel Gold wie möglich,
sucht farbige Schlüssel für die Türen und springt am tiefsten Punkt in die Schatzkammer.
Eigenes Spiel: Räume, Figuren und Grafik sind selbst entworfen, nur das Genre ist das der Vorlage.

**Sprache:** Alles, was der Spieler sieht, ist englisch (HUD, Titel, Einblendungen). Auch VIs, Controls und
Zustandsfelder bekommen englische Namen. Diese Dokumentation und die Kommentare der Python-Skripte sind deutsch.

## 1. Bildschirm

| Bereich | Pixel | Inhalt |
|---|---|---|
| Fenster | 1280 × 720, fest, ohne Rahmen, Titel-, Menü- und Scrollleisten | nicht skalierbar |
| HUD | 0…79 (80 px) | LIVES, KEYS (Anzahl je Farbe), TORCH, LEVEL, GOLD, TIME |
| Spielfeld | 80…719 (640 px) | ein Raum = 40 × 20 Kacheln zu 32 px |

Gezeichnet wird als Pixel-Art im Raster 640 × 360 (Kachel 16 px, Claude 16 × 24) und 2-fach vergrössert gespeichert (Claude 32 × 48).
Im Spiel wird nichts skaliert.

Die Auflösung wurde am 14.11.2026 von 1920 × 1080 auf 1280 × 720 gesenkt: Der Laptop-Bildschirm (1920 × 1200) läuft mit
125 % Windows-Skalierung, ein Fenster von 1920 × 1080 hätte dort nicht Platz. Die Umstellung ist eine Zeile in
`make_assets.py` (`S = 2`) und zwei Konstanten in `gh_lib.py` (`TILE`, `HUD_H`).

## 2. Welt

Ein Level ist eine Pyramide aus 36 Räumen in 6 Tiefen (1, 3, 5, 7, 9 und 11 Räume) und der Schatzkammer darunter.
Verlässt Claude einen Raum am Rand, wechselt das Bild zum Nachbarraum (kein Scrolling).
Raum-ID = Tiefe und Spalte, z. B. `305` = Tiefe 3, Spalte 5 (Mitte). Die Übersicht zeigt `Resources\Preview\world_0.png`.

```
Tiefe 0                                 005
Tiefe 1                           104 - 105 BR 106
Tiefe 2                     203 B 204 - 205   206 - 207
Tiefe 3               302 - 303 - 304 R 305 Y 306 - 307 R 308
Tiefe 4         401 R 402 - 403 - 404 B 405   406 - 407 Y 408 - 409
Tiefe 5   500 - 501 Y 502 - 503 Y 504   505   506 - 507 - 508 B 509 RY 510
Tiefe 6                                 605 Schatzkammer

-  offener Durchgang      B R Y  Tür im Durchgang (blau, rot, gelb)      BR, RY  zwei Türen hintereinander
Leerraum = Mauer
```

| Nach unten | Räume |
|---|---|
| Leiter (hoch und runter) | 005, 105, 106, 203, 206, 304, 306, 308, 401, 403, 405, 407, 409 |
| Rutschstange (nur abwärts) | 104, 207, 302, 406 |
| Loch in die Schatzkammer | 505, hinter drei Türen (gelb und rot hintereinander in 405, gelb in 505) |

**Türen und Schlüssel (je 20 Stück):** 4 blaue, 8 rote, 8 gelbe. 12 Türen stehen in Durchgängen, 2 weitere als
zweite Tür im selben Durchgang, 3 im Weg zur Schatzkammer und 3 vor Goldnischen (005, 206, 507). Ein Schlüssel öffnet
genau eine Tür seiner Farbe und ist danach verbraucht. Viele Türen sind Abkürzungen oder Zugänge zu Gold:
Der Spieler entscheidet, wofür er einen Schlüssel ausgibt.

| Farbe | Schlüssel liegen in |
|---|---|
| blau | 005, 104, 105, 205 – alle vor der ersten Tür |
| rot | 204, 207, 302, 303, 304, 403, 406, 503 |
| gelb | 305, 307, 402, 404, 408, 409, 500, 502 |

Faustregel beim Verteilen: blaue Schlüssel vor allen Türen, rote möglichst nur hinter blauen, gelbe nie nur hinter
gelben. Ob wirklich keine Sackgasse entsteht, beweist die Prüfung in Abschnitt 4.

**Fackel und Dunkelheit:**
- Ab Tiefe 2 (Level 2 und 3: ab Tiefe 1) sind die Räume ohne Fackel fast schwarz.
- Claude sieht dann nur einen Lichtkreis um sich: bis 3 Kacheln hell, bis 5 Kacheln halbdunkel, dahinter nichts.
  Gegenstände, Türen und Gegner erscheinen erst, wenn sie im Lichtkreis liegen.
- Die Fackel gibt es je Level nur in einem Raum (Raum 106, hinter einer blauen und einer roten Tür). Claude nimmt sie mit,
  danach sind alle Räume hell. Beim Start eines neuen Levels ist die Fackel wieder weg und liegt erneut in ihrem Raum.
  Die Hintergründe zeigen deshalb keine Wandfackeln.

**Schatzkammer:** 15 s Zeit, kein Sturzschaden, danach Start im Raum 005 im nächsten Level.
Die Level benutzen dieselben Räume mit anderem Farbschema und höherem Tempo (`levels.txt`).

### Dateien (`Resources\Levels`)

| Datei | Inhalt |
|---|---|
| `room_<id>.txt` | 20 Zeilen × 40 Zeichen |
| `world.txt` | Raumgitter 7 × 11, `---` = kein Raum |
| `levels.txt` | Level; Schema; dunkel ab Tiefe; Tempo Spinne; Tempo Totenkopf; Schwundboden an; aus; Sekunden Schatzkammer |

| Zeichen | Kachel | Zeichen | Objekt |
|---|---|---|---|
| `.` | 0 leer | `r b y` | Schlüssel rot, blau, gelb |
| `#` | 1 Mauer | `R B Y` | Tür (3 Kacheln hoch) |
| `=` | 2 dünner Steinboden | `g` / `G` | Goldmünze 100 / Goldschatz 500 |
| `~` | 3 Schwundboden | `T` | Fackel |
| `H` | 4 Leiter | `S` `Z` `K` | Spinne, Schlange, Totenkopf |
| `\|` | 5 Rutschstange | `P` | Start |
| `:` | 6 Seil | | |
| `<` `>` | 7 / 8 Förderband nach links / rechts | | |

Böden liegen auf den Zeilen 7, 13 und 19. Dünne Plattformen liegen 2 Kacheln über einem Boden.

### Wie die Räume entstehen (`build\gh_levels.py`)

Von Hand festgelegt ist der **Weltplan**: welche Räume wie verbunden sind (`VLINK`, `HLINK`), wo Türen stehen
(`LINKDOOR`, `NOOK`, `SPECIAL`) und wo Schlüssel und Fackel liegen (`ITEMS`). Startraum und Schatzkammer sind ganz
von Hand gebaut. Die übrigen 35 Räume baut `gen_room` aus dem Plan: zwei Aufstiege im Raum (Leiter oder Seil), Schwundboden mit
Fangplattform, dünne Plattformen, Förderband, Gegner und Gold. 24 Räume haben ein Seil, 15 ein Förderband. Die Einzelheiten folgen fest aus der Raum-ID, jeder Lauf ergibt
also dieselben Räume. Einzelne Räume lassen sich später von Hand ersetzen.

## 3. Regeln und Physik (60 Ticks pro Sekunde, Werte in Pixeln bei 32 px je Kachel)

| Grösse | Wert | Folge |
|---|---|---|
| Laufen | 3.5 px/Tick | |
| Sprung | Start −7.7 px/Tick, Schwerkraft 0.4 | gut 2 Kacheln hoch (74 px), 3 bis 4 Kacheln weit |
| Klettern / Rutschen | 3 / 5 px/Tick | |
| Sturz | mehr als 4 Kacheln (133 px) unter dem letzten festen Stand = tot | eine ganze Etage (6 Kacheln) ist tödlich |

- **Dünne Böden `=` und Schwundböden `~`** tragen nur von oben. Von unten springt man hindurch.
- **Schwundboden**: sichtbar – blinkt 30 Ticks – weg. Der Rhythmus steht in `levels.txt`. Unter jedem liegt eine
  Fangplattform in 4 Kacheln Tiefe: Wer dort landet, überlebt.
- **Leiter**: hoch und runter, seitlich absteigen überall.
- **Seil**: hängt von der Decke, oft durch ein Loch im Boden. Hoch und runter wie eine Leiter, wird auch im
  Fallen gegriffen. Im Startraum klettert Claude zu Beginn am Seil durch die Decke herein.
- **Förderband**: fester Boden, der Claude und Totenköpfe mit 1.5 px/Tick in Pfeilrichtung schiebt.
  Gegen das Band läuft man also langsamer (2 statt 3.5), mit dem Band schneller (5). In der Luft wirkt es nicht.
- **Rutschstange**: wird im Fallen gegriffen, nur abwärts, kein Sturzschaden.
- **Tür**: massiv, bis ein passender Schlüssel im Inventar ist und Claude sie berührt. Türen können hintereinander stehen.
- **Spinne**: läuft auf Böden und Leitern ihres Raums, wechselt den Raum nicht, springt nicht. Sie wählt an
  Leitern zufällig eine Richtung.
- **Schlange**: bleibt am Ort, bewegt den Kopf (3 Bilder), kann übersprungen werden.
- **Totenkopf**: rollt waagrecht auf seinem Boden, kehrt an Wänden, Kanten, Türen und Leiterlöchern um.
- Berührung mit einem Gegner oder ein zu tiefer Sturz kostet ein Leben. Neustart am Eingang des Raums.
- **Leben**: Start mit 4 Leben. Alle 10 000 Punkte gibt es ein neues Leben (Konstante `EXTRA_LIFE`), höchstens 7,
  so viele Symbole haben im HUD Platz. Ein Level bringt 64 600 Punkte, wenn man alles Gold holt.
- Töne: Sprung, Schritt, Gold, Schlüssel, Tür, Fackel, neues Leben, Tod, Schatzkammer, Levelwechsel.

## 4. Lösbarkeit

`build\check_levels.py` prüft in zwei Stufen:

**A. Alle Türen zu.** Die Welt zerfällt in 17 Gebiete, in denen man überall hin und wieder zurück kommt.
Geprüft wird, dass jede Einbahn (Rutschstange, Sprung hinunter) wieder im selben Gebiet endet. Niemand kann sich
ohne Tür in eine Ecke ohne Rückweg bringen.

**B. Schlüsselspiel.** Türen verbinden die Gebiete. Durchgerechnet werden alle Reihenfolgen, in denen man Türen
öffnen kann (56 860 Stände):

1. Die Schatzkammer ist erreichbar.
2. Alle 20 Schlüssel, die Fackel und alles Gold (447 Stück) sind erreichbar.
3. Es gibt keine Sackgasse: Aus jedem Stand führt noch ein Weg in die Schatzkammer, egal wofür man Schlüssel ausgibt.
4. Je Farbe gibt es gleich viele Schlüssel wie Türen.

Das Modell rechnet in Kacheln mit den Werten aus Abschnitt 3 und ohne Gegner. Ein Seil zählt wie eine Leiter,
ein Förderband wie fester Boden. Der Beweis im echten Spiel folgt in M3
mit einem Test-VI, das eine Tastenfolge abspielt. Nach jeder Änderung am Weltplan muss die Prüfung neu laufen.

## 5. Software

### Main.vi (4 Schleifen, wie in Pauls Höhenflug)

```
UI-Schleife (Key Down/Up per ScanCode) --Queue--> Engine-Schleife (16 ms): Game_Step
                                                       |-- Notifier --> Render-Schleife: Scene_Draw -> 2D-Picture
                                                       `-- Queue -----> Audio-Schleife: Sound_Mix -> Sound Output Write
```

### Libraries

| Library | VIs | Aufgabe |
|---|---|---|
| `Source\Level\GH_Level.lvlib` | Resource_Path, World_Load, Room_Load, Tile_At, Entities_From_Tiles | Dateien lesen, Kachelzugriff |
| `Source\Engine\GH_Engine.lvlib` | Game_Start, Game_Step, Game_Play, Player_Move, Room_Change, Floor_Cycle, Belt_Push, Spider_Step, Skull_Step, Snake_Step, Hit_Check, Items_Collect, Door_Open, Extra_Life, Treasure_Step, Level_Enter, Highscore_Load/Save/Insert, Demo_Input, Sound_Flags | Spiellogik, ohne Grafik |
| `Source\Render\GH_Render.lvlib` | Image_Load, SpriteAtlas_Load, Sprite_Draw, Image_Draw, Room_Draw, Tile_Cut, Dirty_Tiles, Glyphs_Draw, Hud_Draw, Overlay_Draw, Scene_Draw | Bild aufbauen |
| `Source\Audio\GH_Audio.lvlib` | Sound_Bank_Load, Sound_Mix | gestreamter Ton |
| `Source\App\GH_App.lvlib` | App_Init, Window_Setup, Audio_Start, Key_Send, Engine_Tick, Render_Frame, Audio_Block, App_Close, Audio_Close | Bausteine von Main.vi |

### Zustand (ein Cluster, Typdefinition `GH_State.ctl`)

| Feld | Inhalt |
|---|---|
| Phase | Title, Ready, Playing, Paused, Dying, Treasure, LevelDone, GameOver, Name |
| Level, Room, Lives, Score, NextLife (Punkteschwelle), Ticks, Seed | Spielstand |
| Player | X, Y, VX, VY, Mode (Ground, Ladder, Air, Pole), Facing, StandY (für die Sturzhöhe), Entry (Neustartpunkt) |
| Inventory | Keys red/blue/yellow (Anzahl), Torch |
| World | je Raum: Tiles (2D U8), Items (Kind, X, Y, Active), Enemies (Kind, X, Y, Dir, Frame) |
| TreasureTicks | Restzeit in der Schatzkammer |

Alle 37 Räume eines Levels liegen im Zustand. So bleiben eingesammeltes Gold und offene Türen beim Raumwechsel erhalten.
Gegner bewegen sich nur im aktuellen Raum.

### Phasen

```
Title -> Ready -> Playing <-> Paused
                  Playing -> Dying -> Ready (Lives > 0) | GameOver -> Name -> Title
                  Ready: im Raum 005 klettert Claude am Seil herein
                  Playing -> Treasure (15 s) -> LevelDone -> Ready (Level + 1, Raum 005, ohne Fackel)
```

### Bildaufbau

Gemessen in M1 (`README_Meilenstein1.md`): Das Verfahren von Pauls Höhenflug (alles in ein Bild, dann rastern) braucht
bei 1920 × 1080 rund 212 ms je Bild. Teuer ist der grosse Hintergrund im Bild, nicht das Sprite: 23 Sprites ohne
Hintergrund kosten 3.5 ms. Deshalb wird nur gezeichnet, was sich ändert:

1. Das Picture-Control löscht nie (`Erase First = never`). Beim Raumwechsel wird der Raum einmal ganz gezeichnet
   (Hintergrund hell oder dunkel, alle Objekte, HUD).
2. Pro Bild bestimmt `Dirty_Tiles` die Kacheln, die sich ändern: wo Claude oder ein Gegner war oder ist, wo eine
   Animation weiterschaltet (Gold, Förderband, Schwundboden, Fackel), wo ein Objekt verschwindet und wo sich der
   Lichtkreis verschiebt.
3. `Tile_Cut` schneidet jede dieser Kacheln direkt aus den Bilddaten des passenden Raumbilds (hell, `_dim` oder
   `_dark`, je nach Abstand zu Claude). NIs `Get Image Subset` ist dafür zu langsam (13 ms je Kachel).
4. Darüber kommen die Sprites, die diese Kacheln berühren – im Dunkeln nur, wenn sie im Lichtkreis liegen.
5. HUD-Felder werden nur neu gezeichnet, wenn sich ihr Wert ändert. Einblendungen (Titel, Level, Game Over) liegen
   als Sprites darüber.

Lichtkreis: bis 3.3 Kacheln um Claude hell, bis 5.3 Kacheln halbdunkel, sonst dunkel.
Je Raum und Farbschema gibt es drei Bilder (hell, `_dim`, `_dark`), zusammen 333 Dateien mit 13 MB.
Geladen werden nur die drei Bilder des aktuellen Raums, beim Raumwechsel (gemessen 78 ms).

**Gemessen zu Beginn von M2** (Raum 405, noch bei 1920 × 1080):

| Messung | Ergebnis |
|---|---|
| `Tile_Cut`: alle 800 Kacheln eines Raums | 4 ms (0.005 ms je Kachel) |
| ein Bild mit 40 erneuerten Kacheln und 23 Sprites (`Test_Bench3`) | 5.5 ms |
| `Render_Demo` im offenen Fenster, 600 Bilder ohne Wartezeit | 4.3 ms je Bild |

Am Bildschirm blieben beim Erneuern einzelner Kacheln Reste der Figur stehen. Die Lösung, vom Benutzer am Bildschirm
bestätigt (keine Reste, kein Flackern): **ein** Stück von 5 × 6 Kacheln um Claudes letzte drei Positionen (`Block_Cut`),
alle Objekte und Claude hineinzeichnen, mit `Picture to Pixmap` unsichtbar zu einer Pixmap rastern und in einem Zug
zeichnen (`Frame_Draw`). `Main.vi` erreicht so 62.5 Bilder pro Sekunde bei 1280 × 720.
Für Gegner und Animationen (M3, M4) kommt je bewegtem Objekt ein weiteres solches Stück dazu.

### Übernommen aus `C:\Projects\Paul_Pensionierung`

| Baustein | Verwendung |
|---|---|
| Main.vi mit 4 Schleifen, `PH_App.lvlib` | gleiche Struktur, Fenstergrösse 1280 × 720, englische Namen |
| Tasten per ScanCode, Queue zur Engine | unverändert |
| Sprite-Atlas (`sprites.txt` + PNGs), Sprite_Draw, Glyphs_Draw | unverändert, neue Bilder |
| Gestreamter Ton (Sound_Bank_Load, Sound_Mix), `make_sounds.py`, `make_music.py` | neue Töne, Sprungton zuerst |
| Phasen-Automat, Highscore, Demo, Namenseingabe | angepasst |
| Generatoren `ph_lib.py`, `gen_game.py`, `gen_main.py`, `gen_tests.py`, `build-contract.json` | als `gh_lib.py` usw. |
| Test-VIs (Snapshot_State, Test_Run, Test_Bench), Caraya-Suite | angepasst |

## 6. Ordner

```
Gold_Hunter\
  ARCHITEKTUR.md
  build\        gh_levels.py  check_levels.py  make_assets.py   (später gh_lib.py, gen_*.py, build-contract.json)
  Resources\
    Levels\     room_<id>.txt  world.txt  levels.txt
    Images\     room_<schema>_<id>.png  ..._dim.png  ..._dark.png  hud.png  title.png
    Sprites\    sprites.txt  <name>.png
    Sounds\     *.wav
    Preview\    Übersichten zum Anschauen
  Source\       Level\ Engine\ Render\ Audio\ App\
  Tests\
```

## 7. Meilensteine

| Nr. | Inhalt | Stand |
|---|---|---|
| M0 | Architektur, Pyramide mit 36 Räumen, Lösbarkeitsprüfung, Sprites, Hintergründe | erledigt |
| M1 | Projekt, Räume laden, Raum mit Sprites zeichnen, Bildrate messen | erledigt, Bildaufbau muss neu (siehe 5) |
| M2 | Neuer Bildaufbau; Claude: laufen, springen, Leiter, Seil, Stange, dünne Böden, Förderband, Sturz, Raumwechsel; `Main.vi` | erledigt |
| M3 | Gold, Schlüssel, Türen, Fackel, Dunkelheit mit Lichtkreis, Schwundböden; Test der Lösung per Tastenfolge | offen |
| M4 | Spinne, Schlange, Totenkopf, Leben und Extraleben | offen |
| M5 | Schatzkammer, Levelwechsel, Phasen, HUD, Highscore | offen |
| M6 | Töne (Sprung zuerst), Musik, Titel und Demo | offen |
| M7 | Caraya-Tests, Feinschliff | offen |
