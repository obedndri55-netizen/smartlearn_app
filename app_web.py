# app_web.py

from flask import Flask, render_template, request, redirect, session, url_for, send_file, flash
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
import io

app = Flask(__name__)
app.secret_key = "change-cette-cle-secrete-plus-tard"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def client_utilisateur():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.auth.set_session(session["access_token"], session["refresh_token"])
    return client


def utilisateur_connecte():
    return "utilisateur_id" in session


@app.route("/")
def accueil():
    if utilisateur_connecte():
        return redirect(url_for("modules"))
    return redirect(url_for("connexion"))


@app.route("/a-propos")
def a_propos():
    return render_template("a_propos.html", connecte=utilisateur_connecte())


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        mdp = request.form.get("mdp", "").strip()
        try:
            reponse = supabase.auth.sign_in_with_password({"email": email, "password": mdp})
            session["utilisateur_id"] = reponse.user.id
            session["utilisateur_email"] = reponse.user.email
            metadata = reponse.user.user_metadata or {}
            session["utilisateur_nom"] = metadata.get("nom", reponse.user.email)
            session["access_token"] = reponse.session.access_token
            session["refresh_token"] = reponse.session.refresh_token
            return redirect(url_for("modules"))
        except Exception as erreur:
            message = str(erreur)
            if "Email not confirmed" in message:
                flash("Vérifie ta boîte mail pour confirmer ton adresse avant de te connecter.")
            else:
                flash("E-mail ou mot de passe incorrect.")
            return redirect(url_for("connexion"))
    return render_template("connexion.html")


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip()
        mdp = request.form.get("mdp", "").strip()

        if not nom:
            flash("Merci d'indiquer ton nom d'utilisateur.")
            return redirect(url_for("inscription"))
        if len(mdp) < 6:
            flash("Le mot de passe doit faire au moins 6 caractères.")
            return redirect(url_for("inscription"))

        try:
            supabase.auth.sign_up({
                "email": email,
                "password": mdp,
                "options": {"data": {"nom": nom}}
            })
            flash("Un e-mail de confirmation t'a été envoyé. Clique sur le lien reçu avant de te connecter.")
            return redirect(url_for("connexion"))
        except Exception as erreur:
            flash(f"Erreur : {erreur}")
            return redirect(url_for("inscription"))
    return render_template("inscription.html")


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


def calculer_modules_avec_progression(client):
    resultat_modules = client.table("modules").select("*").order("ordre").execute()
    tous_modules = resultat_modules.data

    liste_finale = []
    for m in tous_modules:
        resultat_chapitres = client.table("chapitres").select("numero").eq("module_id", m["id"]).execute()
        total_chapitres = len(resultat_chapitres.data)

        resultat_prog = client.table("progression_module").select("chapitre_actuel") \
            .eq("utilisateur_id", session["utilisateur_id"]).eq("module_id", m["id"]).execute()

        chapitre_actuel = resultat_prog.data[0]["chapitre_actuel"] if resultat_prog.data else 1

        pourcentage = min(100, round((chapitre_actuel - 1) / total_chapitres * 100)) if total_chapitres > 0 else 0

        m["total_chapitres"] = total_chapitres
        m["chapitre_actuel"] = chapitre_actuel
        m["pourcentage"] = pourcentage
        liste_finale.append(m)

    return liste_finale


@app.route("/modules")
def modules():
    if not utilisateur_connecte():
        return redirect(url_for("connexion"))

    client = client_utilisateur()
    recherche = request.args.get("q", "").strip().lower()

    liste_finale = calculer_modules_avec_progression(client)
    if recherche:
        liste_finale = [m for m in liste_finale if recherche in m["nom"].lower()]

    return render_template("modules.html", nom=session.get("utilisateur_nom", session["utilisateur_email"]),
                            modules=liste_finale, recherche=recherche)


@app.route("/ma-progression")
def ma_progression():
    if not utilisateur_connecte():
        return redirect(url_for("connexion"))

    client = client_utilisateur()
    liste_finale = calculer_modules_avec_progression(client)

    modules_commences = [m for m in liste_finale if m["chapitre_actuel"] > 1 or m["pourcentage"] > 0]
    modules_termines = [m for m in liste_finale if m["pourcentage"] >= 100]

    moyenne_generale = round(sum(m["pourcentage"] for m in liste_finale) / len(liste_finale)) if liste_finale else 0

    return render_template("ma_progression.html", nom=session.get("utilisateur_nom", session["utilisateur_email"]),
                            modules=liste_finale, moyenne_generale=moyenne_generale,
                            nb_commences=len(modules_commences), nb_termines=len(modules_termines),
                            nb_total=len(liste_finale))


@app.route("/module/<int:module_id>")
def module_detail(module_id):
    if not utilisateur_connecte():
        return redirect(url_for("connexion"))

    client = client_utilisateur()

    resultat_module = client.table("modules").select("*").eq("id", module_id).execute()
    if not resultat_module.data:
        flash("Module introuvable.")
        return redirect(url_for("modules"))
    module = resultat_module.data[0]

    resultat_prog = client.table("progression_module").select("*") \
        .eq("utilisateur_id", session["utilisateur_id"]).eq("module_id", module_id).execute()

    if not resultat_prog.data:
        client.table("progression_module").insert({
            "utilisateur_id": session["utilisateur_id"],
            "module_id": module_id,
            "chapitre_actuel": 1
        }).execute()
        chapitre_actuel = 1
    else:
        chapitre_actuel = resultat_prog.data[0]["chapitre_actuel"]

    resultat_chapitres = client.table("chapitres").select("*").eq("module_id", module_id).order("numero").execute()
    chapitres = resultat_chapitres.data

    return render_template("chapitres_module.html", module=module, chapitres=chapitres,
                            chapitre_actuel=chapitre_actuel,
                            nom=session.get("utilisateur_nom", session["utilisateur_email"]))


@app.route("/telecharger/<nom_fichier>")
def telecharger(nom_fichier):
    if not utilisateur_connecte():
        return redirect(url_for("connexion"))
    try:
        client = client_utilisateur()
        donnees_pdf = client.storage.from_("cours-pdf").download(nom_fichier)
        return send_file(io.BytesIO(donnees_pdf), download_name=nom_fichier, as_attachment=True)
    except Exception as erreur:
        flash(f"Erreur de téléchargement : {erreur}")
        return redirect(url_for("modules"))


@app.route("/quiz/<int:chapitre_id>", methods=["GET", "POST"])
def quiz(chapitre_id):
    if not utilisateur_connecte():
        return redirect(url_for("connexion"))

    client = client_utilisateur()

    resultat_chapitre = client.table("chapitres").select("*").eq("id", chapitre_id).execute()
    if not resultat_chapitre.data:
        flash("Chapitre introuvable.")
        return redirect(url_for("modules"))
    chapitre = resultat_chapitre.data[0]

    resultat_questions = client.table("quiz_questions").select("*") \
        .eq("chapitre_id", chapitre_id).order("numero_question").execute()
    questions = resultat_questions.data

    if not questions:
        flash("Aucun quiz disponible pour ce chapitre pour le moment.")
        return redirect(url_for("module_detail", module_id=chapitre["module_id"]))

    if request.method == "POST":
        bonnes_reponses = 0
        total = len(questions)
        for q in questions:
            reponse_utilisateur = request.form.get(f"question_{q['id']}")
            if reponse_utilisateur == q["bonne_reponse"]:
                bonnes_reponses += 1

        pourcentage = round((bonnes_reponses / total) * 100)

        if pourcentage >= 50:
            client.table("progression_module").update(
                {"chapitre_actuel": chapitre["numero"] + 1}
            ).eq("utilisateur_id", session["utilisateur_id"]).eq("module_id", chapitre["module_id"]).execute()
            flash(f"🎉 Bravo ! Tu as obtenu {bonnes_reponses}/{total} ({pourcentage}%). Chapitre suivant débloqué !")
        else:
            flash(f"Malheureusement, vous devriez reprendre le quiz et tentez d'avoir au minimum 50% "
                  f"(c'est-à-dire 5 bonnes réponses sur 10) pour débloquer le chapitre suivant. "
                  f"Votre score : {bonnes_reponses}/{total} ({pourcentage}%).")

        return redirect(url_for("module_detail", module_id=chapitre["module_id"]))

    return render_template("quiz.html", chapitre=chapitre, questions=questions)


@app.route("/profil", methods=["GET", "POST"])
def profil():
    if not utilisateur_connecte():
        return redirect(url_for("connexion"))

    if request.method == "POST":
        nouveau_mdp = request.form.get("nouveau_mdp", "").strip()
        confirmer_mdp = request.form.get("confirmer_mdp", "").strip()

        if len(nouveau_mdp) < 6:
            flash("Le nouveau mot de passe doit faire au moins 6 caractères.")
            return redirect(url_for("profil"))
        if nouveau_mdp != confirmer_mdp:
            flash("Les deux mots de passe ne correspondent pas.")
            return redirect(url_for("profil"))

        try:
            client = client_utilisateur()
            client.auth.update_user({"password": nouveau_mdp})
            flash("Mot de passe mis à jour avec succès !")
        except Exception as erreur:
            flash(f"Erreur : {erreur}")
        return redirect(url_for("profil"))

    return render_template("profil.html", email=session["utilisateur_email"],
                            nom=session.get("utilisateur_nom", session["utilisateur_email"]))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
