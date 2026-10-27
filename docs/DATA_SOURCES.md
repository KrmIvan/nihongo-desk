# Fuentes de datos

Todo el contenido japonés está en `nihongo_desk/resources/`:

| Archivo | Contenido | Origen | Licencia |
|---|---|---|---|
| `content.db` | 2211 kanji (N5–N1) y 7991 palabras (N5–N1) | generado por `tools/build_content.py` | ver abajo |
| `grammar_demo.json` | 32 ejercicios de gramática (N5 y N4) | **redactado a mano: DEMO** | — |

## Fuentes de `content.db`

| Dato | Fuente | Licencia |
|---|---|---|
| Lecturas on/kun y significados de kanji (EN y **ES**) | [KANJIDIC2](https://www.edrdg.org/wiki/index.php/KANJIDIC_Project) (EDRDG) | CC BY-SA 4.0 |
| Nivel JLPT de los kanji | [kanji-data](https://github.com/davidluzgouveia/kanji-data) (campo `jlpt_new`, basado en las listas de Jonathan Waller) | MIT |
| Lista de vocabulario por nivel | [open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks) (listas de Jonathan Waller) | CC BY |
| Significados del vocabulario (EN y **ES**) | [JMdict](https://www.edrdg.org/jmdict/j_jmdict.html) (EDRDG) | CC BY-SA 4.0 |
| Frases de ejemplo (japonés + inglés) | `JMdict_e_examp` → frases de [Tatoeba](https://tatoeba.org) | CC BY 2.0 FR |

Cobertura al generar la base de datos (27/10/2026):

- Kanji: 100 % tienen significado en español.
- Vocabulario: 7211 de 7991 (90 %) tienen glosa en español. El resto se muestra en inglés con la marca «(EN)».
- Frases de ejemplo: 6614 de 7991 palabras. La traducción solo está en inglés, porque `JMdict_e_examp` solo incluye la traducción inglesa. Añadir el español requiere enlazar con los pares jpn–spa de Tatoeba por ID de frase.

## Avisos importantes

- **Los niveles JLPT no son oficiales.** La organización del JLPT no publica listas de kanji ni de vocabulario desde 2010. Las listas de J. Waller son la referencia más usada por la comunidad, y la app lo indica en la pantalla de nivel.
- **La gramática es de demostración.** Los 32 ejercicios de `grammar_demo.json` se redactaron para esta versión y conviene que alguien con buen nivel los revise. N3, N2 y N1 aparecen como «Sin contenido aún».
- La correspondencia entre las listas JLPT y JMdict se hace por (palabra, lectura). Si una palabra no aparece en JMdict, se usa la glosa inglesa de la lista.

## Regenerar el contenido

```bash
mkdir -p data/raw && cd data/raw
curl -LO http://www.edrdg.org/kanjidic/kanjidic2.xml.gz
curl -LO http://ftp.edrdg.org/pub/Nihongo/JMdict.gz
curl -LO http://ftp.edrdg.org/pub/Nihongo/JMdict_e_examp.gz
curl -LO https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json
for n in 1 2 3 4 5; do curl -L -o jlpt_vocab_n$n.csv https://raw.githubusercontent.com/jamsinclair/open-anki-jlpt-decks/main/src/n$n.csv; done
cd ../.. && python tools/build_content.py
```

## Añadir gramática

Cada ejercicio de `grammar_demo.json` es un objeto con este formato:

```json
{"id": "n5-wa-topic", "jlpt": 5, "type": "particle",         // particle | structure | order
 "sentence": "わたし＿学生です。", "options": ["は","を","に","で"], "answer": "は",
 "translation": {"es": "…", "en": "…"}, "explanation": {"es": "…", "en": "…"}}
```

Los ejercicios de tipo `order` usan `"tokens": [...]` y `"accepted": [[...], ...]`, una lista con todos los órdenes válidos. El `id` no debe cambiar nunca, porque el progreso se guarda con él.
