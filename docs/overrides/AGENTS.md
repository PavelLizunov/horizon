# Material override guide

Parent documentation rules apply. `main.html` overrides only the container when
`page.meta.dashboard_home` is set by the native hook; all other pages delegate to
Material. Keep the shared header/nav/palette and player lifecycle intact. Templates
are excluded from public docs; test against the installed MkDocs/Material version.
