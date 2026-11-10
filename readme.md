# Nettoyeur de caches Windows

Petit outil en Python pour libérer de l'espace disque sous Windows 11 en vidant des caches
**reconstruits automatiquement** par les applications. Interface graphique : une ligne par
dossier, sa taille, un bouton « Vider le cache » qui passe au vert une fois le travail fait.

> Outil à usage personnel, fourni tel quel. Lis la section « Ce que le script supprime »
> avant de l'utiliser.

## À savoir avant de commencer

Vider un cache **n'accélère pas** l'ordinateur : il sert justement à aller plus vite, et les
applications le reconstruisent à l'usage (la première utilisation suivante peut être un peu plus
lente). Le gain réel, c'est de la **place disque**, utile quand le disque est presque plein.

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `nettoyeur_caches.py` | Fenêtre graphique pour vider les caches de la liste |
| `analyser_caches.py` | Analyse en lecture seule : montre ce qui prend de la place, ne supprime rien |

## Prérequis

- Windows 11
- Python 3.12 ou plus récent, installé depuis [python.org](https://www.python.org/downloads/)
  (tkinter, la bibliothèque graphique, est inclus : rien d'autre à installer)

Vérifier :

```powershell
python --version
```

## Installation

```powershell
git clone https://github.com/TON_PSEUDO/nettoyeur-caches.git
cd nettoyeur-caches
```

## Utilisation

### 1. Regarder avant de supprimer (recommandé)

```powershell
python analyser_caches.py
```

Le script affiche, avec des barres, les caches connus, les caches d'applications trouvés dans
`AppData`, les plus gros dossiers de `AppData\Local` et les dossiers jetables de tes projets
(`node_modules`, `__pycache__`, `.venv`, `.next`...). **Il ne supprime rien.**

### 2. Vider les caches

```powershell
python nettoyeur_caches.py
```

1. Ferme d'abord les applications concernées (Chrome, Edge, VS Code).
2. Pour chaque ligne, clique sur **Vider le cache** puis confirme.
3. Le bouton devient :
   - **vert « Vidé ✓ »** : le dossier est vide ;
   - **orange « Partiel »** : des fichiers sont encore utilisés par un programme.
4. Le total d'espace libéré s'affiche en bas.

## Ce que le script supprime

Uniquement le **contenu** des dossiers de la liste `CACHES`, jamais le dossier lui-même :

| Ligne | Dossier | Conséquence |
|---|---|---|
| Fichiers temporaires | `%LOCALAPPDATA%\Temp` | Aucune |
| Cache DirectX (shaders) | `%LOCALAPPDATA%\D3DSCache` | Les jeux et applications 3D recompilent leurs shaders |
| Rapports de plantage | `%LOCALAPPDATA%\CrashDumps` | Aucune |
| Cache Chrome | `...\Google\Chrome\User Data\Default\Cache` | Pages rechargées plus lentement la première fois |
| Cache Edge | `...\Microsoft\Edge\User Data\Default\Cache` | Idem |
| Cache VS Code | `%APPDATA%\Code\Cache` | Aucune |
| Cache pip | `%LOCALAPPDATA%\pip\Cache` | Les paquets sont retéléchargés à la prochaine installation |
| Cache npm | `%LOCALAPPDATA%\npm-cache` | Idem ; `node_modules` n'est pas touché |

Ne sont **pas** touchés : mots de passe, cookies, historique, sessions, documents, code source,
`node_modules`, et les dossiers système qui demandent les droits administrateur
(`C:\Windows\Temp`, cache de Windows Update).

## Garde-fous

- Liste de dossiers **fermée** : le script ne cherche pas lui-même ce qu'il supprime.
- Un dossier n'est vidé que s'il se trouve **à l'intérieur** d'une zone autorisée
  (`AppData` par défaut). Sinon la ligne affiche « refusé ».
- Les raccourcis de dossier (liens symboliques, jonctions) ne sont jamais suivis.
- Une **confirmation** s'affiche avant chaque suppression.
- Les fichiers utilisés par un programme sont ignorés, sans erreur.

## Ajouter un dossier à la liste

Dans `nettoyeur_caches.py`, ajoute une ligne à `CACHES` :

```python
("Cache Next.js (mon-site)", Path(r"F:\Projets\mon-site\.next\cache")),
```

Si le dossier est en dehors de `AppData`, autorise sa zone dans `RACINES_AUTORISEES` :

```python
RACINES_AUTORISEES = [LOCAL, ROAMING, Path(r"F:\Projets")]
```

Avant d'ajouter un dossier, vérifie qu'il est reconstruit automatiquement, qu'il ne contient que
du cache (pas de données), et pointe toujours le dossier précis, jamais un dossier parent.

## Créer un exécutable (facultatif)

Pour le lancer sur un PC sans Python :

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed nettoyeur_caches.py
```

Le fichier se trouve dans `dist\nettoyeur_caches.exe`. Windows peut afficher l'écran « Windows a
protégé votre PC » (exécutable non signé) : cliquer sur « Informations complémentaires », puis
« Exécuter quand même ». Certains antivirus signalent à tort les exécutables PyInstaller.

## Limites

- L'interface se fige quelques secondes pendant un gros nettoyage.
- Seul le profil `Default` de Chrome et d'Edge est pris en compte.
- La liste est pensée pour un poste de développeur : sur un autre PC, certaines lignes
  s'afficheront en « introuvable » (bouton grisé).

## Avertissement

L'outil supprime des fichiers de façon définitive (sans passer par la corbeille).
Il est fourni sans garantie : vérifie la liste `CACHES` avant de l'utiliser, et teste d'abord
`analyser_caches.py`.