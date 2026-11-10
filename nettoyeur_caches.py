"""Nettoyeur de caches Windows avec interface graphique (tkinter).
Chaque ligne = un dossier de cache, sa taille, et un bouton pour le vider.
On vide le CONTENU du dossier, jamais le dossier lui-même."""
import os
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
ROAMING = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))

VERT = "#2ea043"
ORANGE = "#d29922"
SEUIL_PARTIEL = 1024 * 1024   # s'il reste plus de 1 Mo, le nettoyage est "partiel"

# (nom affiché, chemin) : UNIQUEMENT des caches reconstruits automatiquement
CACHES = [
    ("Fichiers temporaires", LOCAL / "Temp"),
    ("Cache DirectX (shaders)", LOCAL / "D3DSCache"),
    ("Rapports de plantage", LOCAL / "CrashDumps"),
   #("Cache Chrome", LOCAL / "Google" / "Chrome" / "User Data" / "Default" / "Cache"),
    ("Cache Edge", LOCAL / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"),
    ("Cache VS Code", ROAMING / "Code" / "Cache"),
    ("Cache pip", LOCAL / "pip" / "Cache"),
    ("Cache npm", LOCAL / "npm-cache"),
]


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


def chemin_sur(chemin):
    """Garde-fou : on ne vide que des dossiers situés À L'INTÉRIEUR de AppData."""
    chemin = chemin.resolve()
    return any(racine.resolve() in chemin.parents for racine in (LOCAL, ROAMING))


def vider_dossier(chemin):
    """Supprime tout ce qui est DANS le dossier. Ignore ce qui est utilisé par un programme."""
    try:
        elements = list(chemin.iterdir())
    except OSError:
        return
    for element in elements:
        try:
            if element.is_symlink() or element.is_junction():
                continue                      # on ne touche jamais aux raccourcis de dossier
            if element.is_dir():
                shutil.rmtree(element, ignore_errors=True)
            else:
                element.unlink()
        except OSError:
            pass                              # fichier utilisé : on passe au suivant


def creer_ligne(fenetre, numero, nom, chemin, etat, label_total):
    """Construit une ligne de la fenêtre : nom, chemin, taille, bouton."""
    if not chemin.exists():
        texte_taille = "introuvable"
    elif not chemin_sur(chemin):
        texte_taille = "refusé"
    else:
        texte_taille = lisible(taille_dossier(chemin))
    utilisable = texte_taille not in ("introuvable", "refusé")

    tk.Label(fenetre, text=nom, font=("Segoe UI", 10, "bold"), anchor="w").grid(
        row=numero, column=0, sticky="w", padx=10, pady=4)
    tk.Label(fenetre, text=str(chemin), fg="gray", anchor="w").grid(
        row=numero, column=1, sticky="w", padx=10)
    label_taille = tk.Label(fenetre, text=texte_taille, width=12, anchor="e")
    label_taille.grid(row=numero, column=2, padx=10)
    bouton = tk.Button(fenetre, text="Vider le cache", width=16)
    bouton.grid(row=numero, column=3, padx=10)

    if not utilisable:
        bouton.config(state="disabled")
        return

    def vider():
        if not messagebox.askyesno("Confirmer", f"Vider « {nom} » ?\n\n{chemin}"):
            return
        bouton.config(state="disabled", text="En cours...")
        fenetre.update()                      # affiche le changement tout de suite

        avant = taille_dossier(chemin)
        vider_dossier(chemin)
        apres = taille_dossier(chemin)

        etat["liberes"] += avant - apres
        label_taille.config(text=lisible(apres))
        label_total.config(text=f"Espace libéré : {lisible(etat['liberes'])}")

        if apres > SEUIL_PARTIEL:
            bouton.config(text="Partiel (fichiers utilisés)", bg=ORANGE, disabledforeground="white")
        else:
            bouton.config(text="Vidé ✓", bg=VERT, disabledforeground="white")

    bouton.config(command=vider)


def main():
    fenetre = tk.Tk()
    fenetre.title("Nettoyeur de caches")

    tk.Label(fenetre, text="Ferme Chrome, Edge et VS Code avant de vider leurs caches.",
             fg="#9a6700").grid(row=0, column=0, columnspan=4, pady=(10, 0))

    etat = {"liberes": 0}
    label_total = tk.Label(fenetre, text="Espace libéré : 0.0 o", font=("Segoe UI", 11, "bold"))

    for numero, (nom, chemin) in enumerate(CACHES, start=1):
        creer_ligne(fenetre, numero, nom, chemin, etat, label_total)

    label_total.grid(row=len(CACHES) + 1, column=0, columnspan=4, pady=12)
    fenetre.mainloop()


if __name__ == "__main__":
    main()