# PrixCession France

PrixCession France transforme les avis officiels de ventes et cessions du BODACC en un repère de prix simple : médiane, moyenne, quartiles et exemples de transactions récentes.

Il s'agit de **cessions déjà réalisées et publiées**, pas d'entreprises encore disponibles à la vente. Cette précision est essentielle.

## À qui cela sert

- courtiers et intermédiaires en cession de fonds de commerce ;
- experts-comptables et conseils en transmission ;
- repreneurs qui veulent préparer une première discussion ;
- analystes qui veulent une sortie JSON/CSV/Excel utilisable par un agent IA.

## Démarrage rapide

L'entrée proposée par défaut cherche des boulangeries et pâtisseries à Paris sur les 24 derniers mois.

```json
{
  "activityKeywords": ["boulangerie", "pâtisserie"],
  "departments": ["75"],
  "monthsBack": 24,
  "maxComparables": 40,
  "minPriceEur": 1000,
  "maxPriceEur": 5000000
}
```

Le premier élément du dataset est le résumé. Les éléments suivants sont les transactions comparables utilisées.

```json
{
  "record_type": "summary",
  "comparables_found": 27,
  "median_price_eur": 185000,
  "q1_price_eur": 120000,
  "q3_price_eur": 270000,
  "confidence": "élevée"
}
```

## Méthode

1. Interrogation de l'API open data du BODACC.
2. Filtrage sur la famille `vente`, la période, les départements et les mots-clés.
3. Extraction déterministe des prix présents dans le texte des avis.
4. Exclusion des montants hors de la fourchette choisie.
5. Calcul des statistiques et restitution des sources officielles.

Aucun LLM n'est utilisé dans l'Actor : pas de coût par jeton et pas de montant inventé.

## Limites honnêtes

- Certains avis ne contiennent pas de prix exploitable automatiquement.
- Une recherche par mot-clé n'est pas une classification comptable parfaite.
- Deux fonds de commerce peuvent être très différents malgré une activité et une zone identiques.
- Le résultat est un repère documentaire, pas une expertise de valorisation, un conseil financier ou un conseil juridique.
- Vérifiez toujours les avis officiels avant toute décision.

## Source et attribution

Source : BODACC, Direction de l'information légale et administrative (DILA), données réutilisées sous Licence Ouverte 2.0. Chaque comparable conserve son lien vers l'avis officiel.

## Monétisation suggérée

Sur Apify, activez le modèle **Pay per event**. Pour une première version, gardez un démarrage peu cher et facturez les éléments ajoutés au dataset avec l'événement intégré `apify-default-dataset-item`. Commencez bas, observez les usages, puis ajustez.

## Utilisation avec des agents IA

Une fois publié dans l'Apify Store, l'Actor est découvrable et exécutable via le serveur MCP d'Apify. Son schéma d'entrée et son schéma de sortie permettent à un agent de comprendre les filtres et le résultat sans lire le code.
