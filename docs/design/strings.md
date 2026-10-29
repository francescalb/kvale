# Kvale UI strings

Every string visible in `mockup.html`, by key, in Norwegian bokmål (nb), English (en)
and Italian (it). `{name}` marks a value filled in at run time. Keys starting with
`mock.` belong only to the mockup's helper panel and are not part of the app.
The tables match the `STR` object in `mockup.html`; change both together.

## Wording rules

- Short, plain words in sentence case. Say what happens, not how the program works.
- Use the words embroiderers use, not software terms:

  | Idea | nb | en | it |
  |---|---|---|---|
  | the repeating unit | rapport | repeat | modulo |
  | the finished strip | bord (borden) | band | bordura |
  | one square on the chart | sting / rute | stitch / square | punto / quadretto |
  | cross stitch | korssting | cross stitch | punto croce |
  | backstitch | attersting | backstitch | punto scritto |
  | remove stitches | sprette opp | unpick | scucire |
  | an end piece | endestykke | end / edge | estremità / bordo |
  | a corner (where two end pieces meet) | hjørne | corner | angolo |
  | the background | stoffet | fabric | tela |
  | a thread colour | garn | thread | filato |
  | a thread brand (DMC, Anchor …) | garnprodusent | thread brand | marca |
  | the chart / pattern | mønster | pattern | schema |

- Norwegian: «bord» for an embroidered band is *en bord / borden* – never *bordet*
  (that is a table). Use «drei» for rotation, «speil» for mirroring.
- Italian: address the user with *tu*; use «schema» for the pattern file and chart.
- "–" (en dash) with spaces joins two clauses. Keyboard shortcuts appear only in tooltips.
- A thread code is never shown alone: always with its brand, as «DMC 321» (key `thread.code`).
- Thread colour names stay in English, as the brand publishes them; the picker says so.

## Owner-approved design decisions

The owner reviewed the mockup and approved these decisions. The mockup and the string
tables below follow them.

1. **Backstitch keeps chaining from the last point.** After a line is stitched, the next
   line starts where the last one ended. The chain stops with Esc, by tapping the last
   point again, or by choosing another stitch. The on-screen hint (`canvas.hint.back`)
   and the tool tooltip (`tool.back.hint`) say so.
2. **Resetting an end piece or a corner asks "Are you sure?" first.** «Tilbakestill» opens
   a confirm dialog in the usual dialog style. It names the piece and lists what will be
   lost: the stitch changes, the extra rows/columns (for an end piece) and any corner
   stitches that lie in them. Cancel has focus; the destructive button is red and reads
   «Ja, tilbakestill». Undo can still bring the piece back afterwards (`end.confirm.*`,
   `corner.confirm.*`).
3. **«Endestykke» is the Norwegian term** for an end piece (English "end" / "edge",
   Italian «estremità» / «bordo»).
4. **Thread codes always name their brand, and the design allows more brands later.**
   A colour is a (brand, code) pair, or an own colour with no code. Every place a code
   is shown says «DMC 321», not «321»: colour slots, the picker list, the colour dialog,
   and the thread list under the whole band. The picker has a labelled selector
   «Garnprodusent: DMC», with Anchor and Madeira listed but disabled as «kommer senere»,
   so it is clear that the numbers are DMC numbers and that more brands can come.
   Search works within the chosen brand, and «DMC 321» finds the same as «321».
   «Legg til farge» opens this picker.
5. **The four corners are editable on their own.** A corner (top-left, top-right,
   bottom-left, bottom-right) is where two end pieces meet. It starts from the result of
   its two end pieces; you can then add or unpick stitches and backstitch there, also in
   the square where the extra rows and columns cross. A corner has no size of its own:
   it follows the neighbouring ends' extra rows and columns. The corners are in the
   «Du tegner i» bar (under «Hjørner») and can be clicked in the mini band; changed
   corners get a dot. A corner is shown with its two neighbouring end pieces faded
   beside it, and has «Tilbakestill» (with the same confirm dialog) and «Ferdig».
   In the band, the end pieces are applied first and the corners last.

## loading

| Key | nb | en | it |
|---|---|---|---|
| `loading.title` | Gjør klar Kvale … | Getting Kvale ready … | Preparo Kvale … |
| `loading.body` | Første gang kan det ta litt tid. Etterpå går det fortere. | The first time can take a moment. After that it is quicker. | La prima volta ci vuole qualche secondo. Poi sarà più veloce. |
| `loading.restore` | Mønsteret du jobbet med sist, åpnes straks. | The pattern you were working on will open in a moment. | Lo schema a cui stavi lavorando si riaprirà tra poco. |

## autosave

| Key | nb | en | it |
|---|---|---|---|
| `autosave.saved` | Lagret i nettleseren kl. {time} | Saved in this browser at {time} | Salvato nel browser alle {time} |
| `autosave.hint` | Arbeidet lagres av seg selv her i nettleseren. Trykk «Lagre» for å få en fil du kan ta vare på. | Your work is saved automatically here in the browser. Press “Save” to get a file you can keep. | Il lavoro si salva da solo qui nel browser. Premi «Salva» per avere un file da conservare. |

## file

| Key | nb | en | it |
|---|---|---|---|
| `file.label` | Fil | File | File |
| `file.new` | Ny | New | Nuovo |
| `file.new.hint` | Begynn på et nytt mønster | Start a new pattern | Inizia un nuovo schema |
| `file.open` | Åpne | Open | Apri |
| `file.open.hint` | Åpne en mønsterfil (.json) – Ctrl+O | Open a pattern file (.json) – Ctrl+O | Apri un file di schema (.json) – Ctrl+O |
| `file.save` | Lagre | Save | Salva |
| `file.save.hint` | Last ned mønsteret som fil, så du kan åpne det igjen – Ctrl+S | Download the pattern as a file so you can open it again – Ctrl+S | Scarica lo schema come file, per riaprirlo in seguito – Ctrl+S |
| `file.export` | Lagre bilde | Save image | Salva immagine |
| `file.export.hint` | Last ned hele borden som bilde (PNG), med attersting og endestykker | Download the whole band as a picture (PNG), with backstitch and ends | Scarica tutta la bordura come immagine (PNG), con punto scritto ed estremità |

## lang

| Key | nb | en | it |
|---|---|---|---|
| `lang.label` | Språk | Language | Lingua |

## theme

| Key | nb | en | it |
|---|---|---|---|
| `theme.label` | Utseende | Appearance | Aspetto |
| `theme.light` | Lyst | Light | Chiaro |
| `theme.dark` | Mørkt | Dark | Scuro |

## mode

| Key | nb | en | it |
|---|---|---|---|
| `mode.label` | Visning | View | Vista |
| `mode.edit` | Tegn | Draw | Disegna |
| `mode.preview` | Hele borden | Whole band | Bordura intera |

## tool

| Key | nb | en | it |
|---|---|---|---|
| `tool.label` | Sting | Stitch | Punto |
| `tool.cross` | Korssting | Cross stitch | Punto croce |
| `tool.cross.hint` | Sy korssting i valgt farge. Dra for å sy flere. | Stitch crosses in the chosen colour. Drag to stitch several. | Ricama a punto croce nel colore scelto. Trascina per farne di più. |
| `tool.back` | Attersting | Backstitch | Punto scritto |
| `tool.back.hint` | Sy attersting langs linjene i rutenettet. Linjen fortsetter fra det siste punktet til du stopper. | Stitch backstitch along the grid lines. The line carries on from the last point until you stop. | Ricama linee a punto scritto lungo la griglia. La linea riparte dall’ultimo punto finché non ti fermi. |
| `tool.unpick` | Sprett opp | Unpick | Scuci |
| `tool.unpick.hint` | Fjern korssting eller attersting (med mus: høyreklikk) | Remove cross stitches or backstitch (with a mouse: right-click) | Togli punti croce o linee a punto scritto (col mouse: clic destro) |

## history

| Key | nb | en | it |
|---|---|---|---|
| `history.undo` | Angre (Ctrl+Z) | Undo (Ctrl+Z) | Annulla (Ctrl+Z) |
| `history.redo` | Gjør om (Ctrl+Y) | Redo (Ctrl+Y) | Ripeti (Ctrl+Y) |
| `history.undone` | Angret. | Undone. | Annullato. |
| `history.redone` | Gjort om. | Redone. | Ripetuto. |

## zoom

| Key | nb | en | it |
|---|---|---|---|
| `zoom.in` | Zoom inn | Zoom in | Ingrandisci |
| `zoom.out` | Zoom ut | Zoom out | Riduci |
| `zoom.fit` | Tilpass | Fit | Adatta |
| `zoom.fit.hint` | Vis hele mønsteret på skjermen | Show the whole pattern on screen | Mostra tutto lo schema sullo schermo |

## target

| Key | nb | en | it |
|---|---|---|---|
| `target.label` | Du tegner i | Drawing in | Stai disegnando |
| `target.unit` | Rapporten | The repeat | Il modulo |
| `target.unit.hint` | Mønsteret som gjentas bortover borden | The pattern that repeats along the band | Il motivo che si ripete lungo la bordura |
| `target.left` | Venstre ende | Left end | Estremità sinistra |
| `target.right` | Høyre ende | Right end | Estremità destra |
| `target.top` | Øvre kant | Top edge | Bordo in alto |
| `target.bottom` | Nedre kant | Bottom edge | Bordo in basso |
| `target.corners` | Hjørner | Corners | Angoli |
| `target.tl` | Oppe til venstre | Top left | In alto a sinistra |
| `target.tr` | Oppe til høyre | Top right | In alto a destra |
| `target.bl` | Nede til venstre | Bottom left | In basso a sinistra |
| `target.br` | Nede til høyre | Bottom right | In basso a destra |
| `target.corner.hint` | gi hjørnet en egen avslutning | give the corner its own finish | dai all’angolo una chiusura diversa |
| `target.edge.hint` | Gi borden en egen avslutning her | Give the band its own finish here | Dai alla bordura una chiusura diversa qui |
| `target.changed` | endret | changed | modificata |

## end

| Key | nb | en | it |
|---|---|---|---|
| `end.title.left` | Venstre endestykke | Left end | Estremità sinistra |
| `end.title.right` | Høyre endestykke | Right end | Estremità destra |
| `end.title.top` | Øvre endestykke | Top edge | Bordo in alto |
| `end.title.bottom` | Nedre endestykke | Bottom edge | Bordo in basso |
| `end.where.left` | Den første rapporten til venstre. | The first repeat on the left. | È il primo modulo a sinistra. |
| `end.where.right` | Den siste rapporten til høyre. | The last repeat on the right. | È l’ultimo modulo a destra. |
| `end.where.top` | Den øverste raden med rapporter. | The top row of repeats. | È la fila di moduli più in alto. |
| `end.where.bottom` | Den nederste raden med rapporter. | The bottom row of repeats. | È la fila di moduli più in basso. |
| `end.explain` | Det du syr eller spretter opp her, gjelder bare denne enden. Resten av borden følger rapporten. | What you stitch or unpick here only changes this end. The rest of the band follows the repeat. | Quello che ricami o scuci qui vale solo per questa parte. Il resto della bordura segue il modulo. |
| `end.extra.cols` | Ekstra kolonner utenfor | Extra columns outside | Colonne in più all’esterno |
| `end.extra.rows` | Ekstra rader utenfor | Extra rows outside | Righe in più all’esterno |
| `end.extra.hint` | Gir plass til en kant utenfor rapporten | Makes room for a border outside the repeat | Lascia spazio per una chiusura fuori dal modulo |
| `end.summary.none` | Ingen endringer ennå – enden er lik rapporten. | No changes yet – this end matches the repeat. | Nessuna modifica: è uguale al modulo. |
| `end.summary` | Lagt til: {added} · Sprettet opp: {removed} · Attersting endret: {lines} | Added: {added} · Unpicked: {removed} · Backstitch changed: {lines} | Aggiunti: {added} · Scuciti: {removed} · Linee cambiate: {lines} |
| `end.reset` | Tilbakestill | Reset | Ripristina |
| `end.reset.hint` | Fjern alle endringer her, også ekstra rader og kolonner. Du blir spurt først. | Remove every change here, including extra rows and columns. You will be asked first. | Togli tutte le modifiche di questa parte, anche le righe e colonne in più. Ti verrà chiesto prima. |
| `end.done` | Ferdig | Done | Fatto |
| `end.done.hint` | Tilbake til rapporten | Back to the repeat | Torna al modulo |
| `end.resetDone` | {name} er tilbakestilt. | {name} has been reset. | {name}: ripristinata. |
| `end.confirm.title` | Tilbakestille endestykket? | Reset this end? | Ripristinare questa parte? |
| `end.confirm.body` | {name} blir likt rapporten igjen. Dette blir borte: | {name} will match the repeat again. This will be lost: | {name} tornerà uguale al modulo. Si perderà: |
| `end.confirm.changes` | Endringer i stingene – lagt til: {added}, sprettet opp: {removed}, attersting: {lines} | Stitch changes – added: {added}, unpicked: {removed}, backstitch: {lines} | Modifiche ai punti – aggiunti: {added}, scuciti: {removed}, punto scritto: {lines} |
| `end.confirm.extraCols` | Ekstra kolonner utenfor rapporten: {n} | Extra columns outside the repeat: {n} | Colonne in più all’esterno: {n} |
| `end.confirm.extraRows` | Ekstra rader utenfor rapporten: {n} | Extra rows outside the repeat: {n} | Righe in più all’esterno: {n} |
| `end.confirm.corners` | Sting i hjørnene som ligger i disse radene eller kolonnene: {n} | Stitches in the corners that lie in these rows or columns: {n} | Punti negli angoli che stanno in queste righe o colonne: {n} |
| `end.confirm.undo` | Ombestemmer du deg, kan du angre etterpå. | If you change your mind, you can undo it afterwards. | Se cambi idea, puoi annullare dopo. |
| `end.confirm.cancel` | Avbryt | Cancel | Annulla |
| `end.confirm.ok` | Ja, tilbakestill | Yes, reset | Sì, ripristina |

## corner

| Key | nb | en | it |
|---|---|---|---|
| `corner.title.tl` | Hjørne oppe til venstre | Top-left corner | Angolo in alto a sinistra |
| `corner.title.tr` | Hjørne oppe til høyre | Top-right corner | Angolo in alto a destra |
| `corner.title.bl` | Hjørne nede til venstre | Bottom-left corner | Angolo in basso a sinistra |
| `corner.title.br` | Hjørne nede til høyre | Bottom-right corner | Angolo in basso a destra |
| `corner.where.tl` | Der øvre og venstre endestykke møtes. | Where the top edge meets the left end. | Dove il bordo in alto incontra l’estremità sinistra. |
| `corner.where.tr` | Der øvre og høyre endestykke møtes. | Where the top edge meets the right end. | Dove il bordo in alto incontra l’estremità destra. |
| `corner.where.bl` | Der nedre og venstre endestykke møtes. | Where the bottom edge meets the left end. | Dove il bordo in basso incontra l’estremità sinistra. |
| `corner.where.br` | Der nedre og høyre endestykke møtes. | Where the bottom edge meets the right end. | Dove il bordo in basso incontra l’estremità destra. |
| `corner.explain` | Hjørnet begynner slik de to endestykkene gjør det. Det du syr eller spretter opp her, gjelder bare hjørnet – også i ruta der de ekstra radene og kolonnene krysser hverandre. | The corner starts out as the two ends make it. What you stitch or unpick here only changes this corner – also in the square where the extra rows and columns cross. | L’angolo parte da come lo fanno le due parti vicine. Quello che ricami o scuci qui vale solo per l’angolo, anche nel riquadro dove si incrociano le righe e le colonne in più. |
| `corner.size` | Størrelsen følger de ekstra radene og kolonnene i endestykkene ved siden av. | Its size follows the extra rows and columns of the two ends beside it. | La misura segue le righe e le colonne in più delle due parti vicine. |
| `corner.summary.none` | Ingen endringer ennå – hjørnet er likt endestykkene ved siden av. | No changes yet – the corner matches the ends beside it. | Nessuna modifica: l’angolo è uguale alle parti vicine. |
| `corner.confirm.title` | Tilbakestille hjørnet? | Reset this corner? | Ripristinare l’angolo? |
| `corner.confirm.body` | {name} blir likt endestykkene ved siden av igjen. Dette blir borte: | {name} will match the ends beside it again. This will be lost: | {name} tornerà uguale alle parti vicine. Si perderà: |

## toast

| Key | nb | en | it |
|---|---|---|---|
| `toast.undo` | Angre | Undo | Annulla |

## legend

| Key | nb | en | it |
|---|---|---|---|
| `legend.seed` | Sting du har sydd | Stitches you made | Punti ricamati da te |
| `legend.copy` | Speilet fra stingene dine | Mirrored from your stitches | Specchiati dai tuoi punti |
| `legend.back` | Attersting | Backstitch | Punto scritto |
| `legend.fromUnit` | Som i rapporten | As in the repeat | Come nel modulo |
| `legend.added` | Lagt til i enden | Added at this end | Aggiunti qui |
| `legend.removed` | Sprettet opp i enden | Unpicked at this end | Scuciti qui |
| `legend.extra` | Ekstra, utenfor rapporten | Extra, outside the repeat | In più, fuori dal modulo |
| `legend.neighbour` | Neste rapport – bare til å se på | Next repeat – for reference only | Modulo vicino – solo da vedere |
| `legend.fromEnds` | Som i endestykkene | As in the ends | Come nelle parti vicine |
| `legend.addedCorner` | Lagt til i hjørnet | Added in this corner | Aggiunti nell’angolo |
| `legend.removedCorner` | Sprettet opp i hjørnet | Unpicked in this corner | Scuciti nell’angolo |
| `legend.neighbourEnds` | Endestykkene ved siden av – bare til å se på | The ends beside it – for reference only | Parti vicine – solo da vedere |

## canvas

| Key | nb | en | it |
|---|---|---|---|
| `canvas.hint.cross` | Trykk eller dra over rutene for å sy. Høyreklikk spretter opp. | Tap or drag across the squares to stitch. Right-click unpicks. | Tocca o trascina sui quadretti per ricamare. Il clic destro scuce. |
| `canvas.hint.back` | Trykk på et hjørne for å begynne, og på neste hjørne for å sy en linje. Linjen fortsetter fra det siste punktet, så du kan sy flere linjer etter hverandre. For å slutte: trykk Esc, trykk på det siste punktet en gang til, eller velg et annet sting. | Tap a corner to start, then the next corner to stitch a line. The line carries on from the last point, so you can stitch several lines in a row. To stop: press Esc, tap the last point again, or choose another stitch. | Tocca un angolo per iniziare e poi l’angolo successivo per tracciare una linea. La linea riparte dall’ultimo punto, così puoi farne diverse di seguito. Per finire: premi Esc, tocca di nuovo l’ultimo punto o scegli un altro tipo di punto. |
| `canvas.hint.unpick` | Trykk på et sting eller en attersting for å sprette det opp. | Tap a stitch or a backstitch line to unpick it. | Tocca un punto o una linea per scucirlo. |
| `canvas.hint.edges` | Trykk på et tall langs kanten for å legge til eller fjerne en rad eller kolonne. | Tap a number along the edge to add or remove a row or column. | Tocca un numero sul bordo per aggiungere o togliere una riga o una colonna. |
| `canvas.hint.end` | Det svake feltet er neste rapport, så du ser hvordan enden møter resten av borden. | The faded part is the next repeat, so you can see how the end meets the rest of the band. | La parte sbiadita è il modulo vicino: così vedi come la chiusura si unisce al resto della bordura. |
| `canvas.hint.corner` | De svake feltene er endestykkene ved siden av, så du ser hvordan hjørnet møter dem. | The faded parts are the ends beside it, so you can see how the corner meets them. | Le parti sbiadite sono le parti vicine: così vedi come l’angolo si unisce a loro. |
| `canvas.neighbour` | neste rapport | next repeat | modulo vicino |

## band

| Key | nb | en | it |
|---|---|---|---|
| `band.mini.title` | Slik blir borden | How the band will look | Ecco la bordura |
| `band.mini.open` | Vis stor | Show large | Mostra grande |
| `band.mini.hint` | Trykk på en ende eller et hjørne av borden for å gi det en egen avslutning. | Tap an end or a corner of the band to give it its own finish. | Tocca un’estremità o un angolo della bordura per darle una chiusura diversa. |

## preview

| Key | nb | en | it |
|---|---|---|---|
| `preview.caption` | {rx} × {ry} rapporter · {w} × {h} sting | {rx} × {ry} repeats · {w} × {h} stitches | {rx} × {ry} moduli · {w} × {h} punti |
| `preview.hint` | Her ser du hele borden. Gå til «Tegn» for å endre den. | This is the whole band. Go to “Draw” to change it. | Qui vedi tutta la bordura. Torna a «Disegna» per modificarla. |

## threads

| Key | nb | en | it |
|---|---|---|---|
| `threads.title` | Garn i mønsteret | Threads in this pattern | Filati dello schema |

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
| `edge.also` | Symmetrien tar også med {list}. | The symmetry also takes {list}. | La simmetria cambia anche {list}. |
| `edge.more` | Flere valg … | More options … | Altre opzioni … |

## list

| Key | nb | en | it |
|---|---|---|---|
| `list.and` |  og  |  and  |  e  |

## grid

| Key | nb | en | it |
|---|---|---|---|
| `grid.colN` | kolonne {n} | column {n} | la colonna {n} |
| `grid.rowN` | rad {n} | row {n} | la riga {n} |
| `grid.newColN` | ny kolonne {n} | new column {n} | una nuova colonna {n} |
| `grid.newRowN` | ny rad {n} | new row {n} | una nuova riga {n} |
| `grid.unit` | Rapporten | The repeat | Il modulo |
| `grid.unit.hint` | Feltet du tegner i. Det gjentas bortover og nedover borden. | The area you draw in. It repeats across and down the band. | Il riquadro in cui disegni. Si ripete lungo la bordura. |
| `grid.width` | Bredde | Width | Larghezza |
| `grid.height` | Høyde | Height | Altezza |
| `grid.cells` | sting | stitches | punti |
| `grid.repeats` | Antall rapporter | Number of repeats | Quanti moduli |
| `grid.repeats.hint` | Hvor mange ganger rapporten gjentas (1–100). | How many times the repeat is used (1–100). | Quante volte si ripete il modulo (1–100). |
| `grid.across` | Bortover | Across | In larghezza |
| `grid.down` | Nedover | Down | In altezza |
| `grid.times` | ganger | times | volte |
| `grid.lines` | Legg til eller fjern rad/kolonne … | Add or remove a row/column … | Aggiungi o togli righe/colonne … |

## panel

| Key | nb | en | it |
|---|---|---|---|
| `panel.colours` | Farger | Colours | Colori |
| `panel.symmetry` | Symmetri | Symmetry | Simmetria |
| `panel.grid` | Rapport og størrelse | Repeat and size | Modulo e misure |

## colours

| Key | nb | en | it |
|---|---|---|---|
| `colours.slot` | Farge {n} | Colour {n} | Colore {n} |
| `colours.selected` | I bruk | In use | In uso |
| `colours.own` | Egen farge | Own colour | Colore libero |
| `colours.many` | {n} farger som skifter | {n} colours in turn | {n} colori che si alternano |
| `colours.edit` | Endre farge {n} | Change colour {n} | Modifica il colore {n} |
| `colours.change` | Endre | Change | Cambia |
| `colours.add` | Legg til farge | Add colour | Aggiungi colore |
| `colours.useSeq` | Skift farge fra rapport til rapport | Change colour from repeat to repeat | Cambia colore da un modulo all’altro |
| `colours.useSeq.hint` | Gjelder farger med flere trådfarger. Av: bare den første brukes. | For colours with several threads. Off: only the first is used. | Vale per i colori con più fili. Se è spento si usa solo il primo. |
| `colours.background` | Stoffet | Fabric | Tela |
| `colours.background.hint` | Bakgrunnsfargen i mønsteret | The background colour of the pattern | Il colore di fondo dello schema |

## symmetry

| Key | nb | en | it |
|---|---|---|---|
| `symmetry.intro` | Velg hvordan stingene dine speiles i rapporten. | Choose how your stitches are mirrored in the repeat. | Scegli come i tuoi punti si specchiano nel modulo. |
| `symmetry.squareGroup` | Krever kvadratisk rapport | Needs a square repeat | Serve un modulo quadrato |
| `symmetry.alwaysOn` | Alltid med | Always on | Sempre attivo |
| `symmetry.needsSquare` | Krever kvadrat | Needs a square | Serve un quadrato |
| `symmetry.squareNotice` | Disse virker bare når rapporten er like bred som høy. Nå er den {w} × {h} sting. | These only work when the repeat is as wide as it is tall. It is now {w} × {h} stitches. | Funzionano solo se il modulo è largo quanto è alto. Ora è {w} × {h} punti. |
| `symmetry.makeSquare` | Gjør rapporten {n} × {n} | Make the repeat {n} × {n} | Rendi il modulo {n} × {n} |
| `symmetry.switchedOff` | Rapporten er ikke kvadratisk lenger, så dreiing og skrå speiling er slått av. | The repeat is no longer square, so turning and diagonal mirroring are switched off. | Il modulo non è più quadrato: le rotazioni di 90° e gli specchi in diagonale sono stati spenti. |

## sym

| Key | nb | en | it |
|---|---|---|---|
| `sym.identity` | Slik du syr | As you stitch it | Come lo ricami |
| `sym.mirror_x` | Speil venstre–høyre | Mirror left–right | Specchia destra–sinistra |
| `sym.mirror_y` | Speil opp–ned | Mirror top–bottom | Specchia sopra–sotto |
| `sym.rotate_180` | Drei 180° | Turn 180° | Ruota di 180° |
| `sym.rotate_90` | Drei 90° | Turn 90° | Ruota di 90° |
| `sym.rotate_270` | Drei 270° | Turn 270° | Ruota di 270° |
| `sym.diag_main` | Speil på skrå ╲ | Mirror diagonally ╲ | Specchia in diagonale ╲ |
| `sym.diag_anti` | Speil på skrå ╱ | Mirror diagonally ╱ | Specchia in diagonale ╱ |

## step

| Key | nb | en | it |
|---|---|---|---|
| `step.less` | Færre | Fewer | Meno |
| `step.more` | Flere | More | Più |

## edges

| Key | nb | en | it |
|---|---|---|---|
| `edges.title` | Kanten mellom rapportene | Where repeats meet | Dove i moduli si toccano |
| `edges.explain` | Ligger en speillinje helt ytterst i rapporten, blir den raden eller kolonnen dobbel der to rapporter møtes. Slå av for å la naborapportene dele den. | If a mirror line runs along the very edge of the repeat, that row or column is doubled where two repeats meet. Switch it off to let neighbouring repeats share it. | Se un asse di simmetria cade proprio sul bordo del modulo, quella riga o colonna raddoppia dove due moduli si toccano. Spegnila per farla condividere ai moduli vicini. |
| `edges.key.cols` | Ytterste kolonner | Outer columns | Colonne esterne |
| `edges.key.rows` | Ytterste rader | Outer rows | Righe esterne |
| `edges.diagramCaption` | Eksempel: 3 × 2 rapporter | Example: 3 × 2 repeats | Esempio: 3 × 2 moduli |
| `edges.left` | Venstre kolonne | Left column | Colonna sinistra |
| `edges.right` | Høyre kolonne | Right column | Colonna destra |
| `edges.top` | Øverste rad | Top row | Riga in alto |
| `edges.bottom` | Nederste rad | Bottom row | Riga in basso |
| `edges.on` | Med i hver rapport | In every repeat | In ogni modulo |
| `edges.off.left` | Delt – sys bare lengst til venstre | Shared – only stitched at the far left | Condivisa – solo all’estrema sinistra |
| `edges.off.right` | Delt – sys bare lengst til høyre | Shared – only stitched at the far right | Condivisa – solo all’estrema destra |
| `edges.off.top` | Delt – sys bare helt øverst | Shared – only stitched at the very top | Condivisa – solo in cima |
| `edges.off.bottom` | Delt – sys bare helt nederst | Shared – only stitched at the very bottom | Condivisa – solo in fondo |

## dialog

| Key | nb | en | it |
|---|---|---|---|
| `dialog.title` | Farge {n} | Colour {n} | Colore {n} |
| `dialog.intro` | Én trådfarge, eller flere som skifter fra rapport til rapport. | One thread colour, or several that change from repeat to repeat. | Un solo filo, oppure più colori che cambiano da un modulo all’altro. |
| `dialog.count` | Antall trådfarger | Number of thread colours | Quanti colori |
| `dialog.parts` | Trykk på en del for å velge farge | Tap a part to choose its colour | Tocca una parte per sceglierne il colore |
| `dialog.part` | Del {n} | Part {n} | Parte {n} |
| `dialog.pick` | Farge til del {n} | Colour for part {n} | Colore della parte {n} |
| `dialog.thread` | Finn garn … | Find a thread … | Cerca un filato … |
| `dialog.custom` | Egen farge … | Own colour … | Colore libero … |
| `dialog.howItRepeats` | Slik skifter fargen bortover borden: | How the colour changes along the band: | Ecco come cambia lungo la bordura: |
| `dialog.offNote` | Fargeskift er slått av – bare del 1 brukes nå. | Colour change is switched off – only part 1 is used now. | Il cambio colore è spento: ora si usa solo la parte 1. |
| `dialog.cancel` | Avbryt | Cancel | Annulla |
| `dialog.ok` | Bruk | Apply | Applica |

## thread

| Key | nb | en | it |
|---|---|---|---|
| `thread.title` | Velg garn | Choose a thread | Scegli un filato |
| `thread.system` | Garnprodusent | Thread brand | Marca |
| `thread.system.soon` | {name} – kommer senere | {name} – coming later | {name} – in arrivo |
| `thread.system.hint` | Numrene i lista er {system}-numre. Flere garnprodusenter kan komme senere. | The numbers in the list are {system} numbers. More thread brands may come later. | I numeri dell’elenco sono numeri {system}. Altre marche potranno arrivare in seguito. |
| `thread.code` | {system} {code} | {system} {code} | {system} {code} |
| `thread.search` | Søk | Search | Cerca |
| `thread.search.placeholder` | {system}-nummer eller navn, f.eks. 321 | {system} number or name, e.g. 321 | Numero {system} o nome, es. 321 |
| `thread.namesNote` | Fargenavnene er på engelsk, slik {system} skriver dem. | Colour names are in English, as {system} writes them. | I nomi dei colori sono in inglese, come li scrive {system}. |
| `thread.family.all` | Alle | All | Tutti |
| `thread.family.red` | Rød | Red | Rossi |
| `thread.family.pink` | Rosa | Pink | Rosa |
| `thread.family.orange` | Oransje | Orange | Arancioni |
| `thread.family.yellow` | Gul | Yellow | Gialli |
| `thread.family.green` | Grønn | Green | Verdi |
| `thread.family.blue` | Blå | Blue | Blu |
| `thread.family.purple` | Lilla | Purple | Viola |
| `thread.family.brown` | Brun | Brown | Marroni |
| `thread.family.neutral` | Hvit, grå, svart | White, grey, black | Bianchi, grigi, neri |
| `thread.count` | {n} farger fra {system} | {n} {system} colours | {n} colori {system} |
| `thread.none` | Ingen treff. Prøv et {system}-nummer, f.eks. 321. | Nothing found. Try a {system} number, e.g. 321. | Nessun risultato. Prova con un numero {system}, es. 321. |
| `thread.approx` | Fargene på skjermen er omtrentlige. Sjekk mot et fargekart når fargen må stemme. | Screen colours are approximate. Check against a shade card when the colour must match. | I colori sullo schermo sono indicativi. Controlla su una cartella colori quando la tinta deve essere esatta. |
| `thread.pickPrompt` | Velg en farge i lista. | Choose a colour from the list. | Scegli un colore dall’elenco. |
| `thread.own` | Egen farge … | Own colour … | Colore libero … |
| `thread.cancel` | Avbryt | Cancel | Annulla |
| `thread.choose` | Velg | Choose | Scegli |

## lines

| Key | nb | en | it |
|---|---|---|---|
| `lines.title` | Rader og kolonner | Rows and columns | Righe e colonne |
| `lines.action` | Hva vil du gjøre? | What do you want to do? | Cosa vuoi fare? |
| `lines.add` | Legge til | Add | Aggiungere |
| `lines.remove` | Fjerne | Remove | Togliere |
| `lines.where` | Hvor? | Where? | Dove? |
| `lines.place.top` | Øverst | At the top | In alto |
| `lines.place.bottom` | Nederst | At the bottom | In basso |
| `lines.place.first` | Lengst til venstre | At the far left | All’estrema sinistra |
| `lines.place.last` | Lengst til høyre | At the far right | All’estrema destra |
| `lines.place.row` | Rad nummer … | Row number … | Riga numero … |
| `lines.place.col` | Kolonne nummer … | Column number … | Colonna numero … |
| `lines.number` | Nummer | Number | Numero |
| `lines.effect.add` | Legger til {list}. | Adds {list}. | Aggiunge {list}. |
| `lines.effect.remove` | Fjerner {list}. | Removes {list}. | Toglie {list}. |
| `lines.symNote` | Symmetrien tar med flere enn den du valgte, så mønsteret holder seg likt. | The symmetry takes more than the one you chose, so the pattern stays the same. | La simmetria ne prende più di una, così il motivo resta uguale. |
| `lines.result` | Rapporten blir {w} × {h} sting. | The repeat becomes {w} × {h} stitches. | Il modulo diventa {w} × {h} punti. |
| `lines.cantRemove` | Det går ikke – rapporten må ha minst én rad og én kolonne. | Not possible – the repeat needs at least one row and one column. | Non si può: il modulo deve avere almeno una riga e una colonna. |
| `lines.cancel` | Avbryt | Cancel | Annulla |
| `lines.apply.add` | Legg til | Add | Aggiungi |
| `lines.apply.remove` | Fjern | Remove | Togli |

## mock

| Key | nb | en | it |
|---|---|---|---|
| `mock.title` | Mockup ▸ | Mockup ▸ | Mockup ▸ |
| `mock.loading` | Vis lastesiden | Show loading screen | Mostra la schermata di caricamento |
| `mock.square` | Bytt kvadratisk / ikke kvadratisk | Toggle square / not square | Alterna quadrato / non quadrato |
| `mock.dialog` | Åpne farge 1 | Open colour 1 | Apri il colore 1 |
| `mock.thread` | Åpne garnvelgeren | Open the thread picker | Apri la scelta dei filati |
| `mock.edge` | Vis kantmenyen | Show the edge menu | Mostra il menu del bordo |
| `mock.lines` | Åpne «Rader og kolonner» | Open “Rows and columns” | Apri «Righe e colonne» |
| `mock.end` | Rediger høyre endestykke | Edit the right end | Modifica l’estremità destra |
| `mock.reset` | Tilbakestill høyre endestykke (spør først) | Reset the right end (asks first) | Ripristina l’estremità destra (chiede prima) |
| `mock.corner` | Rediger hjørnet oppe til høyre | Edit the top-right corner | Modifica l’angolo in alto a destra |
| `mock.back` | Velg attersting | Choose backstitch | Scegli il punto scritto |
