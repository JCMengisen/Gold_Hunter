# Gold Hunter – Meilenstein 2: neuer Bildaufbau und Claudes Steuerung

**Stand:** 14.11.2026 · LabVIEW 2026 (32-bit) · Auflösung 1280 × 720

## Ergebnis

`GoldHunter.lvproj` öffnen, `Main.vi` starten und das Fenster anklicken. Claude steht im Startraum und lässt sich steuern.

| Taste | Wirkung |
|---|---|
| ← / → | laufen |
| ↑ / ↓ | Leiter und Seil hoch und runter |
| Leertaste | springen |
| Esc oder Stop-Knopf | beenden |

Was schon geht: laufen, springen, Leitern, Seile, Rutschstangen, dünne Böden (von unten durchspringen), Förderbänder,
tödlicher Sturz (ein Leben weniger, zurück zum Eingang des Raums) und der Wechsel in alle 37 Räume.

Was noch fehlt (M3 bis M6): Gold, Schlüssel und Türen (Türen sind jetzt feste Wände), Fackel und Dunkelheit,
Schwundböden (sind jetzt immer da), Gegner (stehen still und tun nichts), HUD-Werte, Schatzkammer-Zeit, Töne.

## Neu in diesem Meilenstein

| Datei | Zweck |
|---|---|
| `Main.vi` | drei Schleifen: Tasten, Spiel (16 ms), Bild |
| `Source\Engine\GH_Engine.lvlib` | `Game_Start`, `Game_Step`, `Player_Move`, `Room_Change` |
| `Source\App\GH_App.lvlib` | `App_Init`, `App_Close`, `Window_Setup`, `Key_Send`, `Engine_Tick`, `Render_Frame` |
| `Source\Render\GH_Render.lvlib` | neu: `Tile_Cut`, `Block_Cut`, `Frame_Draw` |
| `Source\Level\GH_Level.lvlib` | neu: `Tile_Read` (liest am Raumrand die Randkachel weiter) |
| `Tests\Test_Run.vi` | spielt eine Tastenfolge ab und liefert Position, Modus, Raum, Leben |
| `Tests\Render_Demo.vi`, `Snapshot_Dirty.vi`, `Test_Bench3.vi` | Versuche und Messungen zum Bildaufbau |
| `build\sim_player.py` | Python-Nachbau von `Player_Move`, `Room_Change`, `Game_Step`: liefert die Sollwerte für `Test_Run` |
| `build\gen_main.py` | erzeugt `Main.xml` |

## Bildaufbau

Das Picture-Control löscht nie. Beim Raumwechsel zeichnet `Frame_Draw` den ganzen Bildschirm, sonst nur ein Stück von
5 × 6 Kacheln um Claudes letzte drei Positionen. Dieses Stück wird mit allen Objekten und Claude unsichtbar zu einer
einzigen Pixmap zusammengesetzt und in einem Zug gezeichnet. Am Bildschirm geprüft: keine Reste, kein Flackern.

Zwei Irrwege auf dem Weg dorthin, damit sie nicht wiederholt werden:
- Einzelne Kacheln nebeneinander zu erneuern liess Reste der Figur stehen.
- Die Eigenschaft „Synchronous Display“ lässt sich bei laufendem VI nicht setzen (Fehler 1073). Sie wird nicht gebraucht.

## Verifiziert

| Prüfung | Ergebnis |
|---|---|
| `Snapshot_Room`, `Snapshot_Dirty` bei 1280 × 720 | pixelgleich zur Python-Vorlage |
| `Test_Run`, drei Szenarien gegen `sim_player.py` | gleiche Werte: Sprung im Lauf (X 501, höchster Punkt Y 105, 38 Ticks in der Luft), Stange hinunter (X 26, Y 560), Leiter hinunter und über den Schwundboden (X 123, Y 368) |
| `Main.vi`, 3 Sekunden Probelauf | kein Fehler, 62.5 Bilder pro Sekunde |

Noch nicht geprüft: die Tastatur im echten Spiel, Raumwechsel in `Main.vi`, Seile und Förderbänder im Spiel
(im Nachbau enthalten, aber ohne eigenes Szenario).

## Bekannte Punkte

- Ein Sprung am Startplatz greift das Einstiegsseil direkt darüber (Seile werden im Fallen gegriffen).
- Hält man → und drückt dann ←, stoppt Claude beim Loslassen von →.
- `Player_Move` ist als Diagramm sehr breit (über 9000 Pixel) und sollte später in SubVIs zerlegt werden.
- `Test_Bench`, `Test_Bench2`, `Test_Bench3` rechnen noch mit 48 px je Kachel; `Render_Demo.vi` auf der Platte enthält noch
  die wirkungslose Eigenschaft „Synchronous Display“.
- Fenster: Titel-, Menü- und Scrollleisten sind noch sichtbar.
