"""What a community can do against each hazard (shown in the app and given to the AI)."""

PREVENTION: dict[str, dict] = {
    "heat": {
        "fr": ["Isoler et ventiler les toits", "Créer de l'ombre (auvents, arbres)", "Prévoir des points d'eau potable"],
        "en": ["Insulate and ventilate roofs", "Add shade (awnings, trees)", "Plan drinking-water points"],
    },
    "flood": {
        "fr": ["Curer et agrandir les caniveaux", "Surélever les seuils et fondations", "Éviter de construire dans les bas-fonds"],
        "en": ["Clean and widen drains", "Raise doorsteps and foundations", "Avoid building in low-lying areas"],
    },
    "drought": {
        "fr": ["Récupérer l'eau de pluie (citernes)", "Creuser ou réhabiliter des puits", "Irrigation goutte-à-goutte"],
        "en": ["Harvest rainwater (tanks)", "Dig or repair wells", "Drip irrigation"],
    },
    "landslide": {
        "fr": ["Construire des murs de soutènement", "Drainer les pentes", "Replanter la végétation sur les talus"],
        "en": ["Build retaining walls", "Drain slopes", "Replant vegetation on embankments"],
    },
}
