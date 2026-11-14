# ArtisanConnect Geo Intelligence

Prototype preparatoire independant cree le 7 novembre 2026 pour explorer le
defi "Be An Earth System Trend Detective". Verifier le reglement du concours
et declarer le travail preexistant avant toute soumission.

## Demarrage

Node.js 22 ou plus recent. Aucune dependance a installer.

```powershell
Set-Location C:\POC\ArtisanConnectGeoIntelligence
npm test
npm start
```

Ouvrir http://localhost:3040. Le serveur ecoute uniquement sur 127.0.0.1.
Si le port est occupe, definir `$env:PORT='3041'` avant `npm start`.

## Isolation

- Aucun import du code ArtisanConnect, aucune base de donnees ni authentification.
- Chargement NASA POWER uniquement a la demande : un point fixe a Yaounde, T2M annuel
  (MERRA-2), via une URL serveur fixe. Aucun parametre utilisateur n'est relaye a NASA.
- Aucun autre appel a un fournisseur tiers.
- CSV analyse dans le navigateur, sans envoi au serveur ni stockage persistant.
- Aucun compte artisan, paiement, effectif reel ou donnee personnelle.
- Aucun deploiement staging ou production, aucune modification du depot principal.

## Fonctionnalites

Scenario synthetique reproductible de trois zones illustratives autour de Yaounde,
sur 2005-2024. Option de chargement a la demande d'une serie T2M annuelle de NASA
POWER/MERRA-2 (2005-2024) pour un point a Yaounde. Carte **schematique**, selection de zone et periode, graphique,
regression descriptive, ecart entre premiere et derniere valeur, annees absentes.
Tableau comparatif des tendances descriptives de toutes les zones sur la meme
periode, avec acces direct a la serie selectionnee.
Les emplacements ne sont ni des quartiers officiels ni des zones de risque.
Les trois points fictifs ne constituent pas une analyse spatiale de resolution
MERRA-2 ; le chargement NASA n'expose qu'une seule serie de point.
Le point utilise les coordonnees 3.87 N, 11.52 E et le produit MERRA-2 via
NASA POWER Monthly and Annual API. Les donnees annuelles renvoyees par l'API sont
les entrees de l'analyse ; aucune donnee NASA n'est embarquee dans le projet.

Suggestions artisanales uniquement pour le scenario fictif de temperature ;
aucune relation automatique avec une variable importee.

Un catalogue de ressources externes est disponible dans l'interface : outils de
donnees, references d'analyse de tendances et ressources RADAR/ecosystemes. Ces
liens sont documentaires uniquement ; ils ne declenchent aucun appel reseau du
prototype. Les deux references statistiques dont l'URL ne figurait pas dans le
document fourni sont signalees comme telles.

### CSV

Utiliser le bouton "CSV de demonstration" pour telecharger un exemple fictif.
Schema UTF-8, virgules, point decimal :

```csv
zone,year,value,latitude,longitude,unit
Zone A,2000,27.1,3.87,11.52,degC
Zone A,2001,27.2,3.87,11.52,degC
Zone A,2002,27.4,3.87,11.52,degC
```

### Premier jeu de donnees : NASA POWER a Yaounde

Le fichier [NASA-POWER-Yaounde-T2M-2005-2024.csv](./NASA-POWER-Yaounde-T2M-2005-2024.csv)
contient 20 observations annuelles reelles de T2M, telechargees le 14 novembre
2026 depuis l'API
[NASA POWER Monthly and Annual](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/).
La reponse identifie MERRA-2 comme source et degres Celsius (`C`) comme unite.
La requete porte sur 3.87 N, 11.52 E, de 2005 a 2024.

Pour l'importer dans l'application, renseigner :

- **Source et version** : `NASA POWER T2M / MERRA-2, API Monthly and Annual, 2005-2024, extrait 2026-11-14`
- **Indicateur** : `Temperature annuelle de l'air a 2 m (T2M)`
- **Fichier** : `NASA-POWER-Yaounde-T2M-2005-2024.csv`

NASA POWER indique que les variables meteorologiques conservent la resolution
spatiale de leur source. MERRA-2 utilise une grille native de 0.5 degre en
latitude par 0.625 degre en longitude. Les coordonnees de la requete ne
signifient donc pas une mesure a l'echelle d'un quartier : ce jeu ne permet pas
de comparer les quartiers de Yaounde. Il s'agit de temperature de l'air a 2 m,
pas de temperature de surface. L'application calcule une tendance descriptive,
pas sa significativite statistique.

Source/version et nom d'indicateur requis dans le formulaire. Une source declaree
ne certifie pas l'origine NASA. Limites : 1 Mo, 5 000 lignes de donnees, 50 zones,
trois annees distinctes minimum par zone, une seule unite par fichier.
Meme emplacement et unite sur toute la serie d'une zone ; pas d'annees en double.
Une importation invalide conserve le jeu precedent et affiche son erreur.
Recharger la page remet le scenario fictif.

## Methode et limites

Regression lineaire par moindres carres, utilisant les annees reelles :
pente = somme((annee - moyenneAnnees) * (valeur - moyenneValeurs)) /
somme((annee - moyenneAnnees)^2). Affichage par decennie = pente * 10.
L'ecart premiere/derniere valeur n'est pas le changement estime par regression.
Les annees manquantes ne sont pas interpolees.

**Pas de test de significativite, p-value, intervalle de confiance ou prediction.**
Cette premiere version ne remplit donc pas encore tout le volet statistique du
defi. Avant des conclusions scientifiques : verifier qualite, resolution,
agregation annuelle, saisonnalite, autocorrelation, comparaisons multiples et
adapter la methode avec un specialiste. Ne pas confondre temperature de surface
et temperature de l'air, tendance de precipitation et risque d'inondation.

## Suite a valider

1. Verifier les exigences du defi et les regles de soumission ; le chargement POWER est une premiere integration, pas encore le jeu final valide.
2. Documenter la couverture et la resolution native de MERRA-2, et determiner si elles conviennent a la zone d'etude.
3. Implementer une methode d'inference adaptee aux series climatiques, incluant la dependance temporelle, puis la tester sur des cas connus.
4. Remplacer le schema par une carte des cellules de grille reelles avec echelle et limites sourcees, si le jeu retenu le permet.
5. Valider les hypotheses d'adaptation avec les acteurs locaux.
