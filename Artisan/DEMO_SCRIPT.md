# ArtisanConnect — 4-minute demo video script

Record the screen of the real app (no slides needed), browser at 1440×900, French interface.
Speak slowly; each block lists **what to show** and **what to say** (English voice-over; a French
version can be read the same way). Total ≈ 4:00.

Before recording: start the app (`run.bat`), open each page once so the data is cached
(the Fiabilité page takes ~30 s the first time), close other tabs, hide the bookmarks bar.

---

## 0:00 – 0:25 · The problem
**Show:** home page, the 3D map of Cameroon turning slowly, hazard set to *Chaleur*.

**Say:** "In Cameroon, floods, landslides, droughts and extreme heat kill people every year —
Limbe in 2001, Bafoussam in 2019, Mbankolo in 2023. Local authorities rarely have the climate
evidence to see these risks coming. ArtisanConnect turns 45 years of NASA data into that evidence."

## 0:25 – 0:55 · One look at the whole country
**Show:** hover two regions (score tooltip), then click *Sécheresse* and let the columns rise and fall.

**Say:** "Every column is NASA POWER data — the MERRA-2 reanalysis, daily, 1981 to 2025 — at the
10 regional capitals. Its height is a risk score out of 100: is the hazard getting worse since 1981,
and were the last three years unusual? Switch the hazard and the whole country updates."

## 0:55 – 1:35 · Your town, in plain words
**Show:** type "kousseri" in *Trouver votre ville* → short view: overview, **3 messages à retenir**,
*En bref*, forecasts. Point at the first message.

**Say:** "A mayor doesn't need a statistics course. They type their town and get three things to
remember: the clearest change — very hot days went from 17 to 50 a year in Kousséri —, what to
expect in 2030 with its likely range, and the first action to take."

## 1:35 – 2:15 · The full evidence, for scientists
**Show:** click *Voir toutes les statistiques* → table 01 (all columns visible), scroll to the charts
(regression line, forecast band), open *Que veulent dire ces mentions ?*.

**Say:** "Behind it, the full analysis: mean, median, records, trends with two methods — Sen's slope
with an autocorrelation-corrected Mann-Kendall test, and the classic linear regression with its
95 % interval. 'No change detected' means the year-to-year swings are larger than the change — we
never call something a trend when it could be chance."

## 2:15 – 2:50 · Forecasts that are honest about their error
**Show:** *Prévisions* → Centre, *Chaleur*, °C chart; point at "Erreur habituelle ± 0,47 °C".

**Say:** "For the next years we don't trust one formula: four simple methods are replayed on the
past and the least wrong one is kept. The range is built from the errors it really made — when we
test it, the '80 %' range contains the real value 79 % of the time."

## 2:50 – 3:25 · Proof that the analysis is right
**Show:** *Fiabilité* page, the 7 green checks; read two of them.

**Say:** "Every number can be checked. Our yearly values match NASA's own exports to 0.007; our
formulas give the same results as scipy and numpy; on simulated series with no trend we raise a
false alarm 5 % of the time — exactly the target. And we say what the data cannot tell us."

## 3:25 – 3:45 · Share it, print it, ask it
**Show:** *Bulletin (PDF)* print preview (title "Bulletin climatique — novembre 2026"), then
*Données (CSV)*, then one question in *Assistant IA* (answer already loaded).

**Say:** "A dated bulletin for the council meeting, the raw data in one click, and an assistant
that explains the results in plain language — using only numbers computed from NASA data."

## 3:45 – 4:00 · Close
**Show:** back to the home page, map turning.

**Say:** "ArtisanConnect: NASA data, Cameroon's risks, decisions before the disaster."

---

### Recording tips
- Free tools: OBS Studio (Windows) or the Xbox Game Bar (Win + G). Record at 1080p, 30 fps.
- Record each block separately, then join them; cut the waiting times while pages load.
- Keep the mouse slow and still while speaking; zoom (Ctrl + +) on tables if needed.
- Add captions: many judges watch without sound.
