"""Nettoyeur de caches : analyse d'abord, puis tu vides ce que tu choisis. Interface tkinter.
L'analyse tourne dans un fil séparé (thread) pour que la fenêtre reste utilisable."""
import os
import queue
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
ROAMING = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
PROJETS = Path(r"F:\Projets")          # À adapter : le dossier où sont tes projets

# Noms de dossiers reconnus. ATTENTION : chaque nom n'est cherché que dans SA zone (voir ZONES).
NOMS_CACHE = {"cache", "code cache", "gpucache", "dawncache", "grshadercache",
              "shadercache", "d3dscache", "npm-cache", "crashdumps"}
NOMS_JETABLES = {"__pycache__", "node_modules", ".venv", "target", ".next", "dist"}

# Les seules zones analysées ET autorisées à la suppression.
#  - Dans AppData : on cherche des CACHES (jamais node_modules, dist... qui pourraient
#    faire partie d'une application installée).
#  - Dans tes projets : on cherche des dossiers RECONSTRUCTIBLES (jamais "cache", qui peut
#    être du vrai code source).
ZONES = [
    {"nom": "Local", "racine": LOCAL, "noms": NOMS_CACHE, "categorie": "cache",
     "ignores": [LOCAL / "Temp", LOCAL / "Programs", LOCAL / "Packages"]},
    {"nom": "Roaming", "racine": ROAMING, "noms": NOMS_CACHE, "categorie": "cache",
     "ignores": []},
    {"nom": "Projets", "racine": PROJETS, "noms": NOMS_JETABLES, "categorie": "jetable",
     "ignores": []},
]

SEUIL = 1024 * 1024              # on n'affiche pas les dossiers de moins de 1 Mo
SEUIL_PARTIEL = 1024 * 1024      # s'il reste plus de 1 Mo après nettoyage : "partiel"
VERT = "#2ea043"
ORANGE = "#d29922"

TYPES = {"cache": "Cache", "jetable": "Reconstructible", "temp": "Temporaire"}
COULEURS = {"cache": "#57606a", "jetable": "#bc4c00", "temp": "#57606a"}
CONSEQUENCES = {
    "cache": "Ce cache est reconstruit automatiquement par l'application.",
    "jetable": "Dossier reconstructible (npm install, pip install -r requirements.txt...).\n"
               "Le projet ne fonctionnera plus tant que tu ne l'auras pas reconstruit.",
    "temp": "Fichiers temporaires. Ceux utilisés par un programme seront ignorés.",
}


def lisible(octets):
    """Transforme 1536000 en '1.5 Mo'."""
    for unite in ("o", "Ko", "Mo"):
        if octets < 1024:
            return f"{octets:.1f} {unite}"
        octets /= 1024
    return f"{octets:.1f} Go"


def raccourcir(texte, longueur=70):
    """Raccourcit un long chemin en gardant le début et la fin."""
    if len(texte) <= longueur:
        return texte
    return texte[:25] + " … " + texte[-(longueur - 28):]


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


def chemin_valide(chemin, categorie):
    """Garde-fou appliqué AU MOMENT de supprimer (même si l'analyse s'est trompée)."""
    chemin = chemin.resolve()
    if categorie == "temp":
        return chemin == (LOCAL / "Temp").resolve()
    for zone in ZONES:
        if zone["racine"].resolve() in chemin.parents:
            return chemin.name.lower() in zone["noms"]
    return False


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
            pass


class Application:
    def __init__(self, fenetre):
        self.fenetre = fenetre
        self.elements = []                    # les dossiers trouvés
        self.liberes = 0
        self.compteur = 0                     # nombre de dossiers parcourus
        self.arret = threading.Event()        # sert à interrompre l'analyse
        self.file = queue.Queue()             # messages du thread d'analyse vers la fenêtre

        fenetre.title("Nettoyeur de caches")
        fenetre.geometry("1000x620")
        fenetre.configure(bg="white")

        tk.Label(fenetre, text="Nettoyeur de caches", font=("Segoe UI", 16, "bold"),
                 bg="white").pack(anchor="w", padx=15, pady=(12, 0))
        tk.Label(fenetre, bg="white", fg="#9a6700",
                 text="Ferme Chrome, Edge et VS Code avant de vider leurs caches. "
                      "Rien n'est supprimé sans ta confirmation.").pack(anchor="w", padx=15)

        commandes = tk.Frame(fenetre, bg="white")
        commandes.pack(fill="x", padx=15, pady=10)
        self.bouton_analyser = tk.Button(commandes, text="Analyser", width=14, bg="#0969da",
                                         fg="white", command=self.lancer_analyse)
        self.bouton_analyser.pack(side="left")
        self.bouton_arreter = tk.Button(commandes, text="Arrêter", width=10, state="disabled",
                                        command=self.arret.set)
        self.bouton_arreter.pack(side="left", padx=8)
        self.statut = tk.Label(commandes, text="Clique sur Analyser pour commencer.",
                               bg="white", fg="gray")
        self.statut.pack(side="left", padx=10)

        # Zone de liste avec barre de défilement
        conteneur = tk.Frame(fenetre, bg="white")
        conteneur.pack(fill="both", expand=True, padx=15)
        canvas = tk.Canvas(conteneur, bg="white", highlightthickness=0)
        barre = tk.Scrollbar(conteneur, orient="vertical", command=canvas.yview)
        self.cadre = tk.Frame(canvas, bg="white")
        self.cadre.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.cadre, anchor="nw")
        canvas.configure(yscrollcommand=barre.set)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        canvas.pack(side="left", fill="both", expand=True)
        barre.pack(side="right", fill="y")

        self.label_totaux = tk.Label(fenetre, bg="white", font=("Segoe UI", 11, "bold"))
        self.label_totaux.pack(pady=10)
        self.maj_totaux()

    # ---------- Analyse (dans un thread) ----------

    def lancer_analyse(self):
        self.effacer_liste()
        self.elements = []
        self.liberes = 0
        self.compteur = 0
        self.arret.clear()
        self.bouton_analyser.config(state="disabled")
        self.bouton_arreter.config(state="normal")
        self.maj_totaux()
        threading.Thread(target=self.travail, daemon=True).start()
        self.surveiller()

    def travail(self):
        """Exécuté dans le thread : parcourt les zones et envoie les résultats dans la file."""
        temp = LOCAL / "Temp"
        if temp.is_dir():
            self.file.put(("trouve", {"chemin": temp, "taille": taille_dossier(temp),
                                      "categorie": "temp",
                                      "libelle": "Local\\Temp (fichiers temporaires)"}))
        for zone in ZONES:
            if self.arret.is_set():
                break
            if not zone["racine"].is_dir():
                continue
            ignores = {str(p).lower() for p in zone["ignores"]}
            self.scanner(str(zone["racine"]), zone, ignores)
        self.file.put(("fin", self.arret.is_set()))

    def scanner(self, chemin, zone, ignores, dans_trouve=False):
        """Renvoie la taille de 'chemin' et signale les dossiers reconnus de la zone."""
        total = 0
        try:
            with os.scandir(chemin) as entrees:
                for entree in entrees:
                    if self.arret.is_set():
                        return total
                    try:
                        if entree.is_symlink() or entree.is_junction():
                            continue
                        if entree.is_file(follow_symlinks=False):
                            total += entree.stat(follow_symlinks=False).st_size
                        elif entree.is_dir(follow_symlinks=False):
                            if entree.name == ".git" or entree.path.lower() in ignores:
                                continue
                            self.compteur += 1
                            trouve = (not dans_trouve) and entree.name.lower() in zone["noms"]
                            taille = self.scanner(entree.path, zone, ignores,
                                                  dans_trouve or trouve)
                            total += taille
                            if trouve and not self.arret.is_set():
                                dossier = Path(entree.path)
                                self.file.put(("trouve", {
                                    "chemin": dossier, "taille": taille,
                                    "categorie": zone["categorie"],
                                    "libelle": f"{zone['nom']}\\{dossier.relative_to(zone['racine'])}"}))
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    # ---------- Fenêtre (thread principal) ----------

    def surveiller(self):
        """Toutes les 100 ms : récupère les résultats envoyés par le thread et les affiche."""
        while True:
            try:
                message = self.file.get_nowait()
            except queue.Empty:
                break
            if message[0] == "trouve":
                self.afficher_trouve(message[1])
            else:                              # "fin"
                self.terminer_analyse(message[1])
                return
        self.statut.config(text=f"Analyse en cours... {self.compteur} dossiers parcourus")
        self.fenetre.after(100, self.surveiller)

    def afficher_trouve(self, element):
        if element["taille"] < SEUIL and element["categorie"] != "temp":
            return
        self.elements.append(element)
        self.ajouter_ligne(len(self.elements) - 1, element, avec_boutons=False)
        self.maj_totaux()

    def terminer_analyse(self, interrompu):
        """Affiche la liste triée par taille, cette fois avec les boutons."""
        self.elements.sort(key=lambda e: e["taille"], reverse=True)
        self.effacer_liste()
        for numero, element in enumerate(self.elements):
            self.ajouter_ligne(numero, element, avec_boutons=True)
        if interrompu:
            self.statut.config(text="Analyse interrompue : résultats partiels.")
        elif self.elements:
            self.statut.config(text="Analyse terminée. Les boutons « Vider » sont disponibles.")
        else:
            self.statut.config(text="Analyse terminée : rien à nettoyer.")
        self.bouton_analyser.config(state="normal")
        self.bouton_arreter.config(state="disabled")
        self.maj_totaux()

    def effacer_liste(self):
        for widget in self.cadre.winfo_children():
            widget.destroy()

    def ajouter_ligne(self, numero, element, avec_boutons):
        tk.Label(self.cadre, text=raccourcir(element["libelle"]), anchor="w", width=62,
                 bg="white").grid(row=numero, column=0, sticky="w", padx=(8, 4), pady=3)
        tk.Label(self.cadre, text=TYPES[element["categorie"]], anchor="w", width=16,
                 bg="white", fg=COULEURS[element["categorie"]]).grid(row=numero, column=1)
        label_taille = tk.Label(self.cadre, text=lisible(element["taille"]), width=10,
                                anchor="e", bg="white")
        label_taille.grid(row=numero, column=2, padx=6)
        if not avec_boutons:
            return
        tk.Button(self.cadre, text="Ouvrir",
                  command=lambda: os.startfile(str(element["chemin"]))
                  ).grid(row=numero, column=3, padx=4)
        bouton = tk.Button(self.cadre, text="Vider", width=22)
        bouton.grid(row=numero, column=4, padx=4)
        bouton.config(command=lambda: self.vider(element, label_taille, bouton))

    def vider(self, element, label_taille, bouton):
        chemin = element["chemin"]
        if not chemin.is_dir() or not chemin_valide(chemin, element["categorie"]):
            messagebox.showerror("Refusé", "Ce dossier n'existe plus ou n'est pas autorisé.")
            return
        if not messagebox.askyesno("Confirmer",
                                   f"Vider ce dossier ?\n\n{chemin}\n\n"
                                   f"{CONSEQUENCES[element['categorie']]}"):
            return

        bouton.config(state="disabled", text="En cours...")
        self.fenetre.update()                  # affiche le changement tout de suite
        avant = taille_dossier(chemin)
        vider_dossier(chemin)
        apres = taille_dossier(chemin)

        element["taille"] = apres
        self.liberes += avant - apres
        label_taille.config(text=lisible(apres))
        if apres > SEUIL_PARTIEL:
            bouton.config(text="Partiel (fichiers utilisés)", bg=ORANGE,
                          disabledforeground="white")
        else:
            bouton.config(text="Vidé ✓", bg=VERT, disabledforeground="white")
        self.maj_totaux()

    def maj_totaux(self):
        recuperable = sum(e["taille"] for e in self.elements)
        self.label_totaux.config(
            text=f"Récupérable : {lisible(recuperable)}          Libéré : {lisible(self.liberes)}")


def main():
    fenetre = tk.Tk()
    Application(fenetre)
    fenetre.mainloop()


if __name__ == "__main__":
    main()