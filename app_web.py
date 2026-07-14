# app_web.py

from flask import Flask, render_template, request, redirect, session, url_for, send_file, flash
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
import io

app = Flask(__name__)
app.secret_key = "change-cette-cle-secrete-plus-tard"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.route("/")
def accueil():
    if "utilisateur_id" in session:
        return redirect(url_for("tableau_de_bord"))
    return redirect(url_for("connexion"))


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        mdp = request.form.get("mdp", "").strip()
        try:
            reponse = supabase.auth.sign_in_with_password({"email": email, "password": mdp})
            session["utilisateur_id"] = reponse.user.id
            session["utilisateur_email"] = reponse.user.email
            return redirect(url_for("tableau_de_bord"))
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
        email = request.form.get("email", "").strip()
        mdp = request.form.get("mdp", "").strip()

        if len(mdp) < 6:
            flash("Le mot de passe doit faire au moins 6 caractères.")
            return redirect(url_for("inscription"))

        try:
            supabase.auth.sign_up({"email": email, "password": mdp})
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


@app.route("/tableau-de-bord")
def tableau_de_bord():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    utilisateur_id = session["utilisateur_id"]

    resultat_progression = supabase.table("progression_utilisateur") \
        .select("chapitre_actuel").eq("id", utilisateur_id).execute()
    chapitre_actuel = resultat_progression.data[0]["chapitre_actuel"] if resultat_progression.data else 1

    resultat_chapitres = supabase.table("chapitres").select("*").order("numero").execute()
    chapitres = resultat_chapitres.data

    return render_template(
        "tableau_de_bord.html",
        email=session["utilisateur_email"],
        chapitres=chapitres,
        chapitre_actuel=chapitre_actuel
    )


@app.route("/telecharger/<nom_fichier>")
def telecharger(nom_fichier):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    try:
        donnees_pdf = supabase.storage.from_("cours-pdf").download(nom_fichier)
        return send_file(io.BytesIO(donnees_pdf), download_name=nom_fichier, as_attachment=True)
    except Exception as erreur:
        flash(f"Erreur de téléchargement : {erreur}")
        return redirect(url_for("tableau_de_bord"))


@app.route("/chapitre-suivant/<int:numero>")
def chapitre_suivant(numero):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))
    supabase.table("progression_utilisateur").update(
        {"chapitre_actuel": numero + 1}
    ).eq("id", session["utilisateur_id"]).execute()
    return redirect(url_for("tableau_de_bord"))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)