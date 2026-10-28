# Import FEC + analytique — version 7, trame Pennylane

Remplacer tous les fichiers Python de cette archive à la racine du dépôt. Ajouter impérativement trame.py. Le fichier principal Streamlit reste app.py. Dépendances : requirements.txt.

## Export demandé
Un seul CSV PENNYLANE_ECRITURES.csv, UTF-8 BOM, point-virgule, une ligne d'en-tête. Il reprend les 15 colonnes de pennylane_trame_import_écritures (12).xlsx dans le même ordre, sans les lignes d'exemple. Une 16e colonne « Poids de la catégorie » est nécessaire à l'analytique multiple.
- Libellé de ligne : PieceRef du FEC (référence externe), sans substitution.
- Numéro de pièce : référence de saisie du PNM rapproché. Lorsque les références d'un groupe FEC sont multiples ou absentes, le champ reste vide pour vérification. Une référence unique déduite des autres lignes est signalée à vérifier.
- Libellé de pièce : un libellé commun, initialisé avec le premier EcritureLib non vide du groupe. Modifiable dans le tableau des pièces. Les lignes partageant numéro, journal et date ont un libellé commun.
- Date : EcritureDate originale AAAAMMJJ, jamais ramenée au premier jour.
- Numéro et libellé de compte : auxiliaire prioritaire sur collectif.
- Débit / Crédit : valeurs comptables originales.
- TVA et pays : vides, aucun paramètre fiscal inventé.
- Famille, catégorie, poids, identifiant de ligne : ventilation analytique ; mapper impérativement identifiant et poids pour éviter de compter les répétitions comme de nouvelles lignes.
- Identifiant de lettrage : EcritureLet source conservé.
Les autres colonnes FEC, dont DateLet et EcritureLib original de chaque ligne, ne font pas partie de la trame ; conserver impérativement le FEC initial. Les candidats et détails PNM sont consultables dans l'app.

## Collisions de numéros de pièce
Le rapport fourni contient 239 lignes signalant MULTIPLE_ENTRY_LABELS, MULTIPLE_JOURNAL_CODE et UNBALANCED_IMPORT, autour du numéro 1 réutilisé dans plusieurs journaux/mois.
Le numéro PNM brut est conservé par défaut, comme demandé. Pour éviter les collisions, cocher « Distinguer les numéros PNM répétés par journal et date » : le numéro devient JOURNAL-AAAAMMJJ-REFERENCE. Cela modifie explicitement le format du numéro de pièce, pas sa référence PNM dans le tableau de préparation. Les numéros et libellés sont éditables.
Il n'est pas possible de garantir simultanément numéro PNM brut non unique, un seul import global et absence de collisions de regroupement. Le contrôle le montre avant import, sans inventer de numéro.

## Contrôles et corrections
Le tableau de préparation contient les références PNM, leur statut, les écarts et les numéros/libellés modifiables. La validation finale regroupe selon le numéro réellement exporté ; contrôle journal, date, libellé unique et équilibre, en dédupliquant les identifiants analytiques. Elle ne crée aucune ligne 471 ni correction de montant.
Sur les sources fournies, avec numéros qualifiés : 10 groupes numérotés restent déséquilibrés, plus les lignes sans numéro PNM unique à vérifier. Les ambiguïtés d'analytique restent visibles : 672 lignes, dont 19 avec analytique possible.
Les poids invalides sont éditables ; une option explicite permet leur normalisation proportionnelle positive. Aucune correction tacite. Le bouton indique « à corriger avant import » si les contrôles de pièce ou de poids échouent. Le CSV de contrôle contient quand même toutes les lignes, pour ne pas masquer de données.

## Journaux et banques
Le paramétrage des codes/libellés journaux et des comptes 512 est conservé. Les remplacements 512 s'appliquent à toutes les occurrences, AN et OD compris. Par défaut les valeurs source restent inchangées. Les saisies sont conservées pendant la session ; après redémarrage elles doivent être ressaisies.

## Installation locale et tests
python -m pip install -r requirements.txt
python -m streamlit run app.py
python -m unittest discover -s . -v

L'app ne publie rien dans Pennylane. Ne pas réimporter par-dessus les mêmes écritures déjà intégrées sans traiter les doublons dans le dossier.
Documentation : https://help.pennylane.com/fr/articles/18793-importer-des-ecritures
