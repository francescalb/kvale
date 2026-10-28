# Kvale UI strings

Every string visible in `mockup.html`, by key, in Norwegian bokmål (nb), English (en)
and Italian (it). `{name}` marks a value filled in at run time. Keys starting with
`mock.` belong only to the mockup's helper panel and are not part of the app.

Wording rules: plain everyday words, no technical terms ("rute" not "enhetscelle",
"Lagre bilde" not "Eksporter PNG"), sentence case, and "–" (en dash) with spaces
between clauses. Keyboard shortcuts appear only in tooltips.

## loading

| Key | nb | en | it |
|---|---|---|---|
| `loading.title` | Gjør klar Kvale … | Getting Kvale ready … | Preparazione di Kvale … |
| `loading.body` | Første gang kan det ta noen sekunder. Neste gang går det raskere. | The first time can take a few seconds. Next time it is quicker. | La prima volta può richiedere qualche secondo. Le volte successive sarà più veloce. |
| `loading.restore` | Mønsteret du jobbet med sist, åpnes når alt er klart. | The pattern you were working on will open when everything is ready. | Il disegno su cui stavi lavorando si aprirà appena tutto sarà pronto. |

## autosave

| Key | nb | en | it |
|---|---|---|---|
| `autosave.saved` | Lagret i nettleseren kl. {time} | Saved in this browser at {time} | Salvato nel browser alle {time} |
| `autosave.hint` | Arbeidet lagres automatisk her i nettleseren. Bruk «Lagre» for å få en fil du kan ta vare på. | Your work is saved automatically here in the browser. Use “Save” to get a file you can keep. | Il lavoro viene salvato automaticamente qui nel browser. Usa «Salva» per avere un file da conservare. |

## file

| Key | nb | en | it |
|---|---|---|---|
| `file.new` | Ny | New | Nuovo |
| `file.new.hint` | Start et nytt mønster | Start a new pattern | Inizia un nuovo disegno |
| `file.open` | Åpne | Open | Apri |
| `file.open.hint` | Åpne en mønsterfil (.json) – Ctrl+O | Open a pattern file (.json) – Ctrl+O | Apri un file di disegno (.json) – Ctrl+O |
| `file.save` | Lagre | Save | Salva |
| `file.save.hint` | Lagre mønsteret som fil på maskinen – Ctrl+S | Save the pattern as a file on your computer – Ctrl+S | Salva il disegno come file sul computer – Ctrl+S |
| `file.export` | Lagre bilde | Save image | Salva immagine |
| `file.export.hint` | Last ned hele bordet som bilde (PNG) | Download the whole band as a picture (PNG) | Scarica l’intera bordura come immagine (PNG) |

## lang

| Key | nb | en | it |
|---|---|---|---|
| `lang.label` | Språk | Language | Lingua |

## theme

| Key | nb | en | it |
|---|---|---|---|
| `theme.label` | Utseende | Appearance | Aspetto |
| `theme.light` | Lys visning | Light mode | Tema chiaro |
| `theme.dark` | Mørk visning | Dark mode | Tema scuro |

## mode

| Key | nb | en | it |
|---|---|---|---|
| `mode.edit` | Tegn | Draw | Disegna |
| `mode.preview` | Se gjentakelsene | See the repeats | Vedi le ripetizioni |

## tool

| Key | nb | en | it |
|---|---|---|---|
| `tool.label` | Verktøy | Tool | Strumento |
| `tool.paint` | Sy | Stitch | Ricama |
| `tool.paint.hint` | Sy sting med valgt farge | Place stitches in the selected colour | Aggiungi punti nel colore scelto |
| `tool.erase` | Visk ut | Erase | Cancella |
| `tool.erase.hint` | Fjern sting (med mus: høyreklikk) | Remove stitches (with a mouse: right-click) | Togli punti (con il mouse: clic destro) |

## history

| Key | nb | en | it |
|---|---|---|---|
| `history.undo` | Angre (Ctrl+Z) | Undo (Ctrl+Z) | Annulla (Ctrl+Z) |
| `history.redo` | Gjør om (Ctrl+Y) | Redo (Ctrl+Y) | Ripeti (Ctrl+Y) |

## zoom

| Key | nb | en | it |
|---|---|---|---|
| `zoom.in` | Zoom inn | Zoom in | Ingrandisci |
| `zoom.out` | Zoom ut | Zoom out | Riduci |
| `zoom.fit` | Tilpass | Fit | Adatta |
| `zoom.fit.hint` | Tilpass mønsteret til skjermen | Fit the pattern to the screen | Adatta il disegno allo schermo |

## canvas

| Key | nb | en | it |
|---|---|---|---|
| `canvas.hint.edit` | Trykk i rutene for å sy. Høyreklikk visker ut. | Tap the squares to stitch. Right-click erases. | Tocca i quadretti per ricamare. Il clic destro cancella. |
| `canvas.hint.edges` | Trykk på et tall i kanten for å legge til eller fjerne rader og kolonner. | Tap a number along the edge to add or remove rows and columns. | Tocca un numero sul bordo per aggiungere o togliere righe e colonne. |

## legend

| Key | nb | en | it |
|---|---|---|---|
| `legend.seed` | Sting du har satt | Stitches you placed | Punti messi da te |
| `legend.copy` | Kopier fra symmetrien | Copies made by symmetry | Copie create dalla simmetria |

## band

| Key | nb | en | it |
|---|---|---|---|
| `band.mini.title` | Slik blir bordet | How the band will look | Ecco come verrà la bordura |
| `band.mini.open` | Vis stort | Show large | Mostra in grande |

## preview

| Key | nb | en | it |
|---|---|---|---|
| `preview.caption` | {rx} × {ry} gjentakelser · {w} × {h} sting | {rx} × {ry} repeats · {w} × {h} stitches | {rx} × {ry} ripetizioni · {w} × {h} punti |
| `preview.hint` | Her kan du bare se. Gå tilbake til «Tegn» for å endre mønsteret. | This view is for looking only. Go back to “Draw” to change the pattern. | Questa vista serve solo a guardare. Torna a «Disegna» per modificare il disegno. |

## edge

| Key | nb | en | it |
|---|---|---|---|
| `edge.col.title` | Kolonne {n} | Column {n} | Colonna {n} |
| `edge.row.title` | Rad {n} | Row {n} | Riga {n} |
| `edge.col.insertBefore` | Ny kolonne til venstre | New column to the left | Nuova colonna a sinistra |
| `edge.col.insertAfter` | Ny kolonne til høyre | New column to the right | Nuova colonna a destra |
| `edge.col.remove` | Fjern denne kolonnen | Remove this column | Togli questa colonna |
| `edge.row.insertBefore` | Ny rad over | New row above | Nuova riga sopra |
| `edge.row.insertAfter` | Ny rad under | New row below | Nuova riga sotto |
| `edge.row.remove` | Fjern denne raden | Remove this row | Togli questa riga |
| `edge.close` | Lukk | Close | Chiudi |

## panel

| Key | nb | en | it |
|---|---|---|---|
| `panel.colours` | Farger | Colours | Colori |
| `panel.symmetry` | Symmetri | Symmetry | Simmetria |
| `panel.grid` | Rute og gjentakelser | Unit and repeats | Modulo e ripetizioni |

## colours

| Key | nb | en | it |
|---|---|---|---|
| `colours.slot` | Farge {n} | Colour {n} | Colore {n} |
| `colours.selected` | Valgt | Selected | Scelto |
| `colours.one` | Én farge | One colour | Un colore |
| `colours.many` | {n} farger etter hverandre | {n} colours in turn | {n} colori a turno |
| `colours.edit` | Endre farge {n} | Change colour {n} | Modifica il colore {n} |
| `colours.change` | Endre | Change | Modifica |
| `colours.add` | Legg til farge | Add colour | Aggiungi colore |
| `colours.useSeq` | Bruk fargesekvens | Use colour sequence | Usa la sequenza di colori |
| `colours.useSeq.hint` | På: fargene skifter for hver gjentakelse. Av: bare den første fargen brukes. | On: the colours change with each repeat. Off: only the first colour is used. | Attiva: i colori cambiano a ogni ripetizione. Disattiva: si usa solo il primo colore. |
| `colours.background` | Stoffet (bakgrunn) | Fabric (background) | Tessuto (sfondo) |

## symmetry

| Key | nb | en | it |
|---|---|---|---|
| `symmetry.intro` | Velg hvordan stingene dine kopieres inne i mønsterruten. | Choose how your stitches are copied inside the pattern unit. | Scegli come vengono copiati i tuoi punti all’interno del modulo. |
| `symmetry.squareGroup` | Bare for kvadratisk rute | Only for a square unit | Solo per moduli quadrati |
| `symmetry.alwaysOn` | Alltid på | Always on | Sempre attivo |
| `symmetry.needsSquare` | Krever kvadratisk rute | Needs a square unit | Serve un modulo quadrato |
| `symmetry.squareNotice` | Disse virker bare når ruten er like bred som høy. Nå er den {w} × {h}. | These only work when the unit is as wide as it is tall. It is now {w} × {h}. | Funzionano solo se il modulo è largo quanto è alto. Ora è {w} × {h}. |
| `symmetry.makeSquare` | Gjør ruten {n} × {n} | Make the unit {n} × {n} | Rendi il modulo {n} × {n} |

## sym

| Key | nb | en | it |
|---|---|---|---|
| `sym.identity` | Original | Original | Originale |
| `sym.mirror_x` | Speil venstre–høyre | Mirror left–right | Specchia sinistra–destra |
| `sym.mirror_y` | Speil opp–ned | Mirror top–bottom | Specchia sopra–sotto |
| `sym.rotate_180` | Roter 180° | Rotate 180° | Ruota di 180° |
| `sym.rotate_90` | Roter 90° | Rotate 90° | Ruota di 90° |
| `sym.rotate_270` | Roter 270° | Rotate 270° | Ruota di 270° |
| `sym.diag_main` | Speil på skrå ╲ | Mirror diagonally ╲ | Specchia in diagonale ╲ |
| `sym.diag_anti` | Speil på skrå ╱ | Mirror diagonally ╱ | Specchia in diagonale ╱ |

## grid

| Key | nb | en | it |
|---|---|---|---|
| `grid.unit` | Mønsterruten | Pattern unit | Modulo |
| `grid.unit.hint` | Den lille ruten du tegner i, som gjentas. | The small square you draw in, which is repeated. | Il riquadro in cui disegni e che viene ripetuto. |
| `grid.width` | Bredde | Width | Larghezza |
| `grid.height` | Høyde | Height | Altezza |
| `grid.cells` | ruter | squares | quadretti |
| `grid.repeats` | Gjentakelser | Repeats | Ripetizioni |
| `grid.repeats.hint` | Hvor mange ganger ruten gjentas i bordet (1–100). | How many times the unit is repeated in the band (1–100). | Quante volte il modulo si ripete nella bordura (1–100). |
| `grid.across` | Bortover | Across | In orizzontale |
| `grid.down` | Nedover | Down | In verticale |
| `grid.times` | ganger | times | volte |

## step

| Key | nb | en | it |
|---|---|---|---|
| `step.less` | Mindre | Less | Meno |
| `step.more` | Mer | More | Più |

## edges

| Key | nb | en | it |
|---|---|---|---|
| `edges.title` | Der rutene møtes | Where the units meet | Dove i moduli si toccano |
| `edges.explain` | Ligger en speillinje helt i kanten av ruten, blir kanten dobbel der to ruter møtes. Slå av kanten for å la naboene dele den – da sys den bare ytterst i bordet. | If a mirror line runs right along the edge of the unit, that edge is doubled where two units meet. Switch the edge off to let neighbours share it – it is then only stitched at the very outside of the band. | Se una linea di simmetria corre proprio sul bordo del modulo, quel bordo raddoppia dove due moduli si toccano. Disattivalo per farlo condividere ai moduli vicini: verrà ricamato solo all’esterno della bordura. |
| `edges.key.cols` | Venstre/høyre kolonne | Left/right column | Colonna sinistra/destra |
| `edges.key.rows` | Øverste/nederste rad | Top/bottom row | Riga superiore/inferiore |
| `edges.diagramCaption` | Eksempel: 3 × 2 ruter | Example: 3 × 2 units | Esempio: 3 × 2 moduli |
| `edges.left` | Venstre kolonne | Left column | Colonna sinistra |
| `edges.right` | Høyre kolonne | Right column | Colonna destra |
| `edges.top` | Øverste rad | Top row | Riga superiore |
| `edges.bottom` | Nederste rad | Bottom row | Riga inferiore |
| `edges.on` | Med i hver gjentakelse | Included in every repeat | In ogni ripetizione |
| `edges.off.left` | Bare helt til venstre i bordet | Only at the far left of the band | Solo all’estrema sinistra della bordura |
| `edges.off.right` | Bare helt til høyre i bordet | Only at the far right of the band | Solo all’estrema destra della bordura |
| `edges.off.top` | Bare helt øverst i bordet | Only at the very top of the band | Solo in cima alla bordura |
| `edges.off.bottom` | Bare helt nederst i bordet | Only at the very bottom of the band | Solo in fondo alla bordura |

## dialog

| Key | nb | en | it |
|---|---|---|---|
| `dialog.title` | Farge {n} | Colour {n} | Colore {n} |
| `dialog.intro` | En farge kan være én tråd, eller en rekke farger som skifter for hver gjentakelse. | A colour can be a single thread, or a row of colours that changes with each repeat. | Un colore può essere un solo filo, oppure una serie di colori che cambia a ogni ripetizione. |
| `dialog.count` | Antall farger | Number of colours | Numero di colori |
| `dialog.parts` | Trykk på en del for å velge fargen | Tap a part to choose its colour | Tocca una parte per sceglierne il colore |
| `dialog.part` | Del {n} | Part {n} | Parte {n} |
| `dialog.pick` | Farge for del {n} | Colour for part {n} | Colore della parte {n} |
| `dialog.custom` | Egen farge … | Custom colour … | Colore personalizzato … |
| `dialog.howItRepeats` | Slik skifter fargen bortover i bordet: | How the colour changes across the band: | Come cambia il colore lungo la bordura: |
| `dialog.offNote` | Fargesekvens er slått av – bare del 1 brukes nå. | Colour sequence is switched off – only part 1 is used now. | La sequenza di colori è disattivata: ora si usa solo la parte 1. |
| `dialog.cancel` | Avbryt | Cancel | Annulla |
| `dialog.ok` | Bruk | Apply | Applica |

## mock

| Key | nb | en | it |
|---|---|---|---|
| `mock.title` | Mockup ▸ | Mockup ▸ | Mockup ▸ |
| `mock.loading` | Vis lastesiden | Show loading screen | Mostra la schermata di caricamento |
| `mock.square` | Bytt kvadratisk / ikke kvadratisk | Toggle square / not square | Alterna quadrato / non quadrato |
| `mock.dialog` | Åpne fargesekvens for farge 1 | Open colour sequence for colour 1 | Apri la sequenza del colore 1 |
| `mock.edge` | Vis kantmenyen | Show the edge menu | Mostra il menu del bordo |
