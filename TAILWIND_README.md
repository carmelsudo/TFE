# Configuration Tailwind CSS

## Fichiers créés :

1. **tailwind.config.js** - Fichier de configuration Tailwind à la racine du projet
2. **static/styles.css** - Fichier CSS source avec les directives Tailwind
3. **Liens redirigés** dans les 3 fichiers HTML de `client/interface/` :
   - `main.html`
   - `analyse_IA.html`
   - `optimisation.html`

## Installation et compilation

Pour compiler le CSS Tailwind localement :

```bash
# 1. Installer les dépendances (si pas déjà fait)
npm install -D tailwindcss @tailwindcss/forms @tailwindcss/container-queries postcss autoprefixer

# 2. Compiler le CSS
npx tailwindcss -i ./static/styles.css -o ./static/output.css --watch

# 3. Ensuite rediriger le lien dans les fichiers HTML vers le fichier compilé
# Remplacer : <link href="../../static/styles.css" rel="stylesheet" />
# Par :     <link href="../../static/output.css" rel="stylesheet" />
```

## Structure actuelle

```
TFE/
├── tailwind.config.js          (configuration)
├── static/
│   ├── styles.css               (source CSS)
│   ├── output.css               (CSS compilé - à générer)
│   └── images/
└── client/
    └── interface/
        ├── main.html            (liens redirigés)
        ├── analyse_IA.html      (liens redirigés)
        └── optimisation.html    (liens redirigés)
```

## Option alternative

Si vous voulez garder Tailwind via CDN (plus simple pour le développement), vous pouvez supprimer le lien vers `styles.css` et garder uniquement le CDN dans les fichiers HTML.
