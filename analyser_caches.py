"""Analyse l'espace pris par des caches et dossiers jetables. NE SUPPRIME RIEN."""
import os
import tempfile
from pathlib import Path

# À adapter : le dossier où sont tes projets
DOSSIER_PROJETS = Path(r"F:\Projets")

# Dossiers qu'on peut reconstruire à tout moment dans un projet
NOMS_JETABLES = {"__pycache__", "node_modules", ".venv", "target", ".next", "dist"}

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
ROAMING = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))

# Noms de dossiers qui sont (presque toujours) des caches reconstruits automatiquement
NOMS_CACHE = {"cache", "code cache", "gpucache", "dawncache",
              "grshadercache", "shadercache", "d3dscache"}

# On n'affiche pas les caches plus petits que 1 Mo (du bruit)
SEUIL = 1024 * 1024

# Caches connus de l'ordinateur
CACHES_CONNUS = {
    "Dossier temporaire (TEMP)": Path(tempfile.gettempdir()),
    "Cache pip": LOCAL / "pip" / "Cache",
    "Cache npm": LOCAL / "npm-cache",
    "Dépôt Maven (retéléchargeable)": Path.home() / ".m2" / "repository",
}


def taille_dossier(chemin):
    """Additionne la taille de tous les fichiers d'un dossier, en octets."""
    total = 0
    for racine, _dossiers, fichiers in os.walk(chemin):
        for nom in fichiers:
            try:
                total += os.path.getsize(os.path.join(racine, nom))
            except OSError:
                pass  # fichier verrouillé ou disparu : on l'ignore
    return total


def lisible(octets):
    """Transforme 1536000 en '1.5 Mo'."""
    for unite in ("o", "Ko", "Mo"):
        if octets < 1024:
            return f"{octets:.1f} {unite}"
        octets /= 1024
    return f"{octets:.1f} Go"


def barre(valeur, maximum, largeur=30):
    """Une barre de '#' proportionnelle à la valeur."""
    if maximum == 0:
        return ""
    return "#" * round(largeur * valeur / maximum)


def chercher_jetables(racine):
    """Trouve les dossiers jetables dans les projets. Renvoie [(chemin, taille), ...]."""
    trouves = []
    for dossier, sous_dossiers, _fichiers in os.walk(racine):
        if ".git" in sous_dossiers:
            sous_dossiers.remove(".git")        # on n'entre jamais dans .git
        for nom in list(sous_dossiers):
            if nom in NOMS_JETABLES:
                chemin = Path(dossier) / nom
                trouves.append((chemin, taille_dossier(chemin)))
                sous_dossiers.remove(nom)       # inutile de descendre dedans
    return trouves


def chercher_caches(racine):
    """Trouve les dossiers de cache d'applications sous 'racine' (par leur nom)."""
    trouves = []
    for dossier, sous_dossiers, _fichiers in os.walk(racine):
        for nom in list(sous_dossiers):
            if nom.lower() in NOMS_CACHE:
                chemin = Path(dossier) / nom
                trouves.append((chemin, taille_dossier(chemin)))
                sous_dossiers.remove(nom)       # on ne descend pas dans un cache
    return trouves


def gros_dossiers(racine):
    """Taille de chaque dossier directement sous 'racine'."""
    resultat = []
    try:
        for enfant in racine.iterdir():
            if enfant.is_dir():
                resultat.append((enfant.name, taille_dossier(enfant)))
    except OSError:
        pass
    return resultat


def afficher(titre, lignes, limite=15):
    """lignes = [(libelle, taille), ...] : affichées triées, avec une barre."""
    print(f"\n=== {titre} ===")
    if not lignes:
        print("(rien trouvé)")
        return
    lignes = sorted(lignes, key=lambda ligne: ligne[1], reverse=True)
    maximum = lignes[0][1]
    for libelle, taille in lignes[:limite]:
        print(f"{lisible(taille):>10}  {barre(taille, maximum):<30}  {libelle}")
    if len(lignes) > limite:
        print(f"           ... et {len(lignes) - limite} autre(s)")
    print(f"{lisible(sum(t for _, t in lignes)):>10}  TOTAL")


def main():
    print("Analyse en cours (AppData peut prendre quelques minutes)...")

    caches = [(nom, taille_dossier(chemin))
              for nom, chemin in CACHES_CONNUS.items() if chemin.exists()]
    afficher("Caches connus de l'ordinateur", caches)

    caches_app = []
    for etiquette, racine in (("Local", LOCAL), ("Roaming", ROAMING)):
        for chemin, taille in chercher_caches(racine):
            if taille >= SEUIL:
                caches_app.append((f"{etiquette}\\{chemin.relative_to(racine)}", taille))
    afficher("Caches d'applications dans AppData (candidats à la suppression)", caches_app)

    afficher("Plus gros dossiers de AppData\\Local (à examiner à la main)",
             gros_dossiers(LOCAL), limite=10)

    if DOSSIER_PROJETS.exists():
        jetables = [(str(c), t) for c, t in chercher_jetables(DOSSIER_PROJETS)]
        afficher(f"Dossiers jetables dans {DOSSIER_PROJETS}", jetables)
    else:
        print(f"Dossier introuvable : {DOSSIER_PROJETS}")

    print("\nRien n'a été supprimé.")


if __name__ == "__main__":
    main()