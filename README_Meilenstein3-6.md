# Gold Hunter – Meilensteine 3 bis 6: das ganze Spiel

**Stand:** 14.11.2026 · LabVIEW 2026 (32-bit) · 1280 × 720 · selbstständig gebaut, während der Benutzer weg war

## Spielen

`GoldHunter.lvproj` öffnen, `Main.vi` starten, ins Fenster klicken.

| Taste | Wirkung |
|---|---|
| Enter oder N | Spiel starten, Namen bestätigen |
| ← / → | laufen; bei der Namenseingabe: Stelle wählen |
| ↑ / ↓ | Leiter und Seil; bei der Namenseingabe: Buchstabe wählen |
| Leertaste | springen |
| Esc oder P | Pause; auf dem Titelbild: Spiel beenden |

Ablauf: Titelbild (8 s) → Highscore-Tabelle (5 s) → Demo → wieder Titel. Enter startet Level 1 mit 4 Leben.
Wer die Schatzkammer erreicht, sammelt 15 s Gold, dann folgt das nächste Level (anderes Farbschema, schnellere Gegner,
früher dunkel). Nach dem letzten Leben: GAME OVER, bei genug Punkten die Namenseingabe.

## Was neu ist

| Meilenstein | Inhalt |
|---|---|
| M3 | Gold (100), Goldschatz (500), Schlüssel (200), Türen mit passendem Schlüssel (+100, Schlüssel verbraucht, auch zwei hintereinander), Fackel (+500, alle Räume hell), Dunkelheit mit Lichtkreis, Schwundböden im Rhythmus (da – Warnfarbe – weg), HUD mit allen Werten |
| M4 | Spinne (läuft, klettert Leitern und Seile, wechselt den Raum nicht), Schlange (bleibt, Kopf wiegt, überspringbar), Totenkopf (rollt, kehrt an Kanten und Leiterlöchern um), Leben, Extraleben alle 10 000 Punkte (höchstens 7), Sterben mit Blinken und Neustart am Raumeingang |
| M5 | Phasen Title, Ready, Playing, Paused, Dying, Treasure, LevelDone, GameOver, Name, Demo; Schatzkammer mit Zeit; Levelwechsel; Highscore (Top 5, `Resources\Data\highscores.txt`) |
| M6 | 12 eigene Soundeffekte (Sprung, Münze, Schatz, Schlüssel, Tür, Fackel, Leben, Tod, Schatzkammer, Level, Game Over, Bereit) und eigene Musik (Chiptune, a-Moll, 29 s Schleife), Titelbild mit Highscores, Demo |

Neue Libraries und VIs (alle im Projekt):
- `GH_Engine.lvlib`: `Game_Start`, `Game_Step` (Phasen), `Game_New`, `Level_Setup`, `Game_Play`, `Keys_Apply`, `Player_Move`,
  `Items_Collect`, `Door_Open`, `Enemies_Init`, `Enemies_Step`, `Hit_Check`, `Respawn`, `Room_Change`, `Demo_Input`, `Highscore_*`.
- `GH_Render.lvlib`: `Frame_Draw` (Bildaufbau aus Stücken), `Piece_Compose`, `Room_Images`, `Light_Update`, `Grid_Block`,
  `Room_Draw`, `Enemies_Draw`, `Glyphs_Draw`, `Hud_Draw`, `Overlay_Draw`.
- `GH_Audio.lvlib` (neu): `Sound_Bank_Load`, `Sound_Mix`. `GH_App.lvlib`: dazu `Audio_Start`, `Audio_Block`, `Audio_Close`.
- `Main.vi` hat jetzt vier Schleifen (Tasten, Spiel, Bild, Ton).
- Tests: `Test_Setup`, `Test_Run` (Tastenfolge, beliebiger Raum/Level/Phase), `Snapshot_Run` (emuliert den Bildschirm Stück für Stück
  und speichert ihn als PNG).

Generatoren: `build\gen_play.py` (Spiel, Bild, Ton, App, Build-Contract mit 50 VIs), `gen_game.py` (Grund-VIs), `gen_main.py`,
`gen_tests.py`, `make_sounds.py`, `make_music.py`, `check_aixml.py` (findet Netze, die eine Diagrammgrenze ohne Tunnel kreuzen),
`sim_player.py` (Python-Nachbau der Bewegung, Gegenstände, Türen und Schwundböden).

## Verifiziert

| Prüfung | Ergebnis |
|---|---|
| Build-Contract | 50 VIs, alle ausführbar (`lvai_exec_state`) |
| `Test_Run`: Weg der Demo bis zum blauen Schlüssel (620 Ticks) | 800 Punkte, blauer Schlüssel, Sounds Münze/Schlüssel/Musik – wie `sim_player.py` |
| `Test_Run`: Raum 105 mit je einem Schlüssel nach rechts | blaue und rote Tür hintereinander offen, Raum 106 erreicht, X 210, 200 Punkte – wie der Nachbau |
| `Test_Run`: in die Schlange laufen | Dying, nach 100 Ticks Ready mit 3 Leben am Raumeingang, Sounds Tod/Bereit |
| `Test_Run`: über die Schlange springen | überlebt, Sprung- und Münzton |
| `Test_Run`: Schatzkammer 1060 Ticks | Treasure → LevelDone → Level 2, Ready am Start, 2600 Punkte |
| `Snapshot_Run` (Bilder in `Resources\Preview\lv_*.png`) | Startraum nach 620 Ticks ohne Reste; dunkler Raum 204 mit Lichtkreis; Titel mit Highscores; Demo; Schatzkammer mit Zeit; Level 2 blau mit Fackel |
| Tempo | 620 Ticks samt Bildaufbau in 1,1 s; `Main.vi` 62,5 Bilder pro Sekunde, kein Fehler |

## Nicht geprüft (bitte selbst ausprobieren)

- **Ton**: ob Effekte und Musik hörbar und gut abgemischt sind (Lautstärke der Musik: `MUSIC_VOL` in `gh_lib.py`).
- Tastatur im echten Spiel, Pause, Namenseingabe und Speichern des Highscores, Beenden mit Esc auf dem Titel.
- Spinnen auf Leitern und Totenköpfe am Bildschirm (nur die Logik ist gebaut, kein eigenes Szenario).
- Spielbarkeit über viele Räume: Schwierigkeit, Tempo der Gegner, Rhythmus der Schwundböden.

## Bekannte Punkte

- Mehrere Diagramme sind sehr breit (`Player_Move`, `Frame_Draw`, `Game_Step` …), sie laufen aber.
- Die alten Versuchs-VIs `Render_Demo`, `Snapshot_Room`, `Snapshot_Dirty`, `Test_Bench*`, `Test_World` passen nicht mehr zu den
  neuen Schnittstellen und sind vermutlich nicht mehr ausführbar; sie werden nicht mehr gebraucht.
- Münzen drehen sich nicht und Förderbänder laufen nicht sichtbar (nur bewegte Figuren werden pro Bild erneuert).
- Fenster: Titel- und Menüleiste sind noch sichtbar.
