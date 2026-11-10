"""Analyse un disque (par défaut C:\\) : plus gros dossiers, caches et dossiers jetables.
NE SUPPRIME RIEN. Ctrl+C pour interrompre : les résultats partiels s'affichent."""
import argparse
import os
from pathlib import Path

# Dossiers qu'on peut reconstruire à tout moment dans un projet
NOMS_JETABLES = {"__pycache__", "node_modules", ".venv", "target", ".next", "dist"}

# Noms de dossiers qui sont (presque toujours) des caches reconstruits automatiquement
NOMS_CACHE = {"cache", "code cache", "gpucache", "dawncache", "grshadercache",
              "shadercache", "d3dscache", "npm-cache", "crashdumps"}

# On n'affiche pas les dossiers plus petits que 1 Mo (du bruit)
SEUIL = 1024 * 1024


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


def scanner(chemin, profondeur, resultats, ignores, dans_jetable=False):
    """Parcourt 'chemin' et renvoie sa taille totale en octets.
    Note au passage dans 'resultats' : la taille des dossiers de niveau 1 et 2,
    ainsi que les caches et dossiers jetables rencontrés."""
    total = 0
    try:
        with os.scandir(chemin) as entrees:
            for entree in entrees:
                try:
                    if entree.is_symlink() or entree.is_junction():
                        continue                    # évite les boucles et les doublons
                    if entree.is_file(follow_symlinks=False):
                        total += entree.stat(follow_symlinks=False).st_size
                    elif entree.is_dir(follow_symlinks=False):
                        if entree.path.lower() in ignores:
                            continue
                        nom = entree.name.lower()
                        categorie = None
                        if not dans_jetable:        # pas de recherche DANS un dossier déjà repéré
                            if nom in NOMS_CACHE:
                                categorie = "cache"
                            elif nom in NOMS_JETABLES:
                                categorie = "jetable"

                        resultats["compteur"] += 1
                        if resultats["compteur"] % 2000 == 0:
                            print(f"\r  {resultats['compteur']} dossiers analysés...",
                                  end="", flush=True)

                        taille = scanner(entree.path, profondeur + 1, resultats, ignores,
                                         dans_jetable or categorie is not None)
                        total += taille
                        if categorie:
                            resultats[categorie].append((entree.path, taille))
                        if profondeur in (1, 2):
                            resultats[profondeur].append((entree.path, taille))
                except OSError:
                    pass                            # fichier ou dossier inaccessible : on passe
    except OSError:
        pass                                        # dossier illisible (droits) : on passe
    return total


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
    parser = argparse.ArgumentParser(description="Analyse un disque. Ne supprime rien.")
    parser.add_argument("racine", nargs="?", default="C:\\",
                        help="disque ou dossier à analyser (par défaut : C:\\)")
    parser.add_argument("--avec-windows", action="store_true",
                        help="inclut C:\\Windows (beaucoup plus long)")
    args = parser.parse_args()

    racine = Path(args.racine)
    if not racine.is_dir():
        print(f"Dossier introuvable : {racine}")
        return

    ignores = set()
    if not args.avec_windows:
        ignores.add(str(racine / "Windows").lower())

    resultats = {"cache": [], "jetable": [], 1: [], 2: [], "compteur": 0}
    print(f"Analyse de {racine} (ça peut durer plusieurs minutes, Ctrl+C pour arrêter)...")
    try:
        scanner(str(racine), 1, resultats, ignores)
        print("\rAnalyse terminée.                              ")
    except KeyboardInterrupt:
        print("\nAnalyse interrompue : les résultats ci-dessous sont PARTIELS.")

    afficher("Plus gros dossiers (niveau 1)", resultats[1], limite=10)
    afficher("Plus gros dossiers (niveau 2)", resultats[2], limite=15)
    afficher("Caches trouvés (candidats à la suppression)",
             [(c, t) for c, t in resultats["cache"] if t >= SEUIL], limite=20)
    afficher("Dossiers jetables (reconstructibles)",
             [(c, t) for c, t in resultats["jetable"] if t >= SEUIL], limite=20)

    print("\nRien n'a été supprimé.")


if __name__ == "__main__":
    main()