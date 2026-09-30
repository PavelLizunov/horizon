# News dashboard prototype

An isolated Russian-language homepage prototype. It does not replace the MkDocs
site or make API/model calls. All stories, scores, audio flags, and SVG cover
illustrations are demonstration content. The existing penguin is reused intact.

## Open and try

Open `index.html` through the OpenDesign HTTP preview. Try:

- Open a headline, dismiss with Escape or the close button.
- Save with the `+` control, switch to **Отложенное**, and reload.
- Open a few stories and visit **История** or the recent-reading sidebar.
- Search a topic/title, change topic/period, and sort by score.
- Toggle light/dark theme. Preferences persist in namespaced localStorage.
- Expand **Проверить состояния макета** to exercise loading, empty, and error/retry.

No real audio file is bundled. The article view explains sample audio flags
instead of offering a fake Play button. Storage is browser-local, not synced.

## Source and rebuild

`app.jsx` is the editable React source; `app.js` is the precompiled browser output.
React 18.3.1 and ReactDOM 18.3.1 are served locally under `vendor/`, with their MIT
licenses. IBM Plex Sans and IBM Plex Serif are local fonts from Google Fonts,
with their SIL Open Font License under `fonts/`. No CDN is needed at runtime.

To rebuild after editing JSX, use Babel standalone 7.26.9 as a temporary compiler
outside the served directory, or an existing JSX compiler with the classic React
transform. The build used `Babel.transform(source, {presets: ['react'], comments:
false}).code`; do not copy a compiler into the final preview assets.

The next phase is an owner-approved production feed contract and MkDocs
integration. Asynchronous local cover generation remains separate; no image
model, quantization, hardware, or production timing has been selected or tested.
