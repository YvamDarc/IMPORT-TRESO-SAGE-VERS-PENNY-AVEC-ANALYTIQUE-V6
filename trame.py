"""Pennylane template supplied by the user, plus the required analytic weight."""
from collections import defaultdict
from decimal import Decimal
from fusion import amount

HEADERS=['Date','Code Journal','Numéro de compte','Libellé de compte','Libellé de ligne','Taux de TVA du compte','Code pays du compte','Libellé de pièce','Numéro de pièce','Débit et/ou Crédit','Crédit','Famille de catégories','Catégorie','Identifiant de ligne','Identifiant de lettrage','Poids de la catégorie']

def piece_table(rows):
    groups=defaultdict(list)
    for r in rows:groups[r['EcritureNum'],r['JournalCode'],r['EcritureDate']].append(r)
    table=[]
    for (entry,journal,date),rs in groups.items():
        unique={r['IdentifiantLigneSource']:r for r in rs}
        refs=sorted({r['NumeroPieceComptablePNM'] for r in rs if r['NumeroPieceComptablePNM']})
        ref=refs[0] if len(refs)==1 else ''
        table.append({'Groupe source':str(len(table)+1),'Écriture FEC':entry,'Journal':journal,'Date':date,
            'Références PNM trouvées':' | '.join(refs),'Numéro de pièce':ref,
            'Libellé de pièce':next((r['EcritureLib'] for r in rs if r['EcritureLib'].strip()),entry),
            'Écart débit-crédit':format(sum((amount(r['Debit'])-amount(r['Credit']) for r in unique.values()),Decimal(0)),'.2f'),
            'Référence à vérifier':'Oui' if len(refs)!=1 or any(not r['NumeroPieceComptablePNM'] for r in rs) else 'Non'})
    return table

def template_rows(rows,pieces,qualify=False):
    lookup={(p['Écriture FEC'],p['Journal'],p['Date']):p for p in pieces}
    out=[];labels={}
    for r in rows:
        p=lookup[r['EcritureNum'],r['JournalCode'],r['EcritureDate']]
        ref=str(p['Numéro de pièce'] or '').strip()
        if qualify and ref:ref=f"{r['JournalCode']}-{r['EcritureDate']}-{ref}"
        label=labels.setdefault((ref,r['JournalCode'],r['EcritureDate']),p['Libellé de pièce'])
        out.append(dict(zip(HEADERS,[r['EcritureDate'],r['JournalCode'],r['CompteNum'],r['CompteLib'],r['PieceRef'],'','',
            label,ref,r['Debit'],r['Credit'],r['FamilleAnalytique'],r['CategorieAnalytique'],r['IdentifiantLigneSource'],r.get('EcritureLet',''),r['PoidsAnalytique']])))
    return out

def validate_template(rows):
    groups=defaultdict(list);issues=[]
    for r in rows:groups[r['Numéro de pièce']].append(r)
    for ref,rs in groups.items():
        reasons=[]
        if not ref:reasons.append('Numéro de pièce absent : référence PNM à renseigner')
        if len({r['Code Journal'] for r in rs})>1:reasons.append('MULTIPLE_JOURNAL_CODE')
        if len({r['Libellé de pièce'] for r in rs})>1:reasons.append('MULTIPLE_ENTRY_LABELS')
        if len({r['Date'] for r in rs})>1:reasons.append('Dates différentes pour un même numéro')
        unique={r['Identifiant de ligne']:r for r in rs}
        balance=sum((amount(r['Débit et/ou Crédit'])-amount(r['Crédit']) for r in unique.values()),Decimal(0))
        if balance:reasons.append('UNBALANCED_IMPORT')
        if reasons:issues.append({'Numéro de pièce':ref,'Lignes source':len(unique),'Écart':format(balance,'.2f'),'Problèmes':' ; '.join(reasons)})
    return issues
