import hashlib,json,csv,io
from pathlib import Path
import streamlit as st
import pandas as pd
from fusion import reconcile,enrich,csv_bytes,ConversionError
from trame import HEADERS,piece_table,template_rows,validate_template
from parametrage import mapping_tables,apply_mappings,weight_issues,normalize_invalid_weights,ambiguity_review
# Versioned session data: old export tuples must never survive a schema change.
CACHE_SCHEMA = 'fec-enrichi-pennylane-v7'
REQUIRED_REPORT = {'source_rows','output_rows','accounts_promoted','lettered_rows',
                   'unresolved','aux_labels_missing','analytic_discrepancies','output_base_columns'}

def normalize_export(raw,result,rows,fields,report):
    # Compatible with the previous fusion.py: derive account data from the source,
    # not missing report keys and not a potentially stale already-collapsed export.
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('cp1252')
    sep='\t' if '\t' in text.splitlines()[0] else ';'
    source=list(csv.DictReader(io.StringIO(text),delimiter=sep))
    if len(source)!=len(result[0]):raise ConversionError('Nombre de lignes source incohérent.')
    by_id={f'FEC-{parsed["_line"]:07d}':original for parsed,original in zip(result[0],source)}
    headers=list(source[0])
    for row in rows:
        original=by_id.get(row.get('IdentifiantLigneSource'))
        if original is None:raise ConversionError('Version du moteur incompatible : mettez à jour fusion.py.')
        aux=original.get('CompAuxNum','') or ''
        row['CompteNum']=aux if aux.strip() else original['CompteNum']
        aux_label=original.get('CompAuxLib','') or ''
        row['CompteLib']=aux_label if aux.strip() and aux_label.strip() else (original.get('CompteLib','') or '')
        row.pop('CompAuxNum',None);row.pop('CompAuxLib',None)
        for name in headers:
            if name not in ('CompteNum','CompteLib','CompAuxNum','CompAuxLib') and row.get(name)!=original[name]:
                raise ConversionError('Une colonne FEC a changé : régénérez avec les fichiers source.')
    fields=[k for k in fields if k not in ('CompAuxNum','CompAuxLib')]
    if 'CompteLib' not in fields:fields.insert(fields.index('CompteNum')+1,'CompteLib')
    base=[k for k in headers if k not in ('CompAuxNum','CompAuxLib')]
    if 'CompteLib' not in base:base.append('CompteLib')
    report=dict(report)
    report.update(source_rows=len(source),output_rows=len(rows),
        accounts_promoted=sum(bool((r.get('CompAuxNum') or '').strip()) for r in source),
        aux_labels_missing=sum(bool((r.get('CompAuxNum') or '').strip()) and not (r.get('CompAuxLib') or '').strip() for r in source),
        lettered_rows=sum(bool((r.get('EcritureLet') or '').strip()) for r in source),
        unresolved=len(result[4]),output_base_columns=len(base))
    if 'analytic_discrepancies' not in report:
        report['analytic_discrepancies']=len({r['IdentifiantLigneSource'] for r in rows if 'ÉCART ANALYTIQUE' in r.get('StatutRapprochement','')})
    return rows,fields,report,csv_bytes(rows,fields)

def valid_export(value):
    return (isinstance(value,(tuple,list)) and len(value)==4
            and isinstance(value[2],dict) and REQUIRED_REPORT <= value[2].keys()
            and 'CompAuxNum' not in value[1] and 'CompAuxLib' not in value[1])

st.set_page_config(page_title='FEC enrichi avec analytique',page_icon='📑',layout='wide')
st.title('Ton FEC complet + l’analytique')
st.caption('Version 7 · trame Pennylane · contrôle des ambiguïtés · pièces comptables · analytique par ligne · journaux et banques paramétrables')
st.write('Un seul compte et son libellé : l’auxiliaire est prioritaire sur le collectif. Dates, lettrage, références et montants sont conservés ; l’analytique est ajoutée. Les journaux et comptes bancaires changent uniquement selon ton paramétrage.')
with st.sidebar:
    ff=st.file_uploader('FEC initial',type=['txt','csv','fec'])
    pp=st.file_uploader('PNM avec analytique',type=['pnm','txt'])
    enc=st.selectbox('Encodage PNM',['cp850','cp1252','utf-8-sig'])
    family=st.text_input('Nom de la famille analytique','Plan 1')
    mode='Une ligne par catégorie analytique'
    st.caption('Export Pennylane : une catégorie par ligne, identifiant commun et poids.')
    st.caption('1 ligne d’en-tête dans chaque fichier. Aucun envoi à Pennylane.')
if not ff or not pp:st.stop()
raw=ff.getvalue();pnm=pp.getvalue()
engine_path=Path(__file__).with_name('fusion.py')
engine_hash=hashlib.sha256(engine_path.read_bytes()).hexdigest() if engine_path.exists() else 'embedded'
schema_key=(CACHE_SCHEMA,engine_hash)
if st.session_state.get('_cache_schema')!=schema_key:
    for stale in ('source_key','result','export_key','export'):
        st.session_state.pop(stale,None)
    st.session_state['_cache_schema']=schema_key
key=hashlib.sha256(raw+pnm+enc.encode()).hexdigest()
try:
    if st.session_state.get('source_key')!=key or 'result' not in st.session_state:
        with st.spinner('Rapprochement des deux fichiers…'):
            result=reconcile(raw,pnm,enc)
        st.session_state['result']=result;st.session_state['source_key']=key
    result=st.session_state['result']
    ek=(schema_key,key,family,mode)
    if st.session_state.get('export_key')!=ek or not valid_export(st.session_state.get('export')):
        rows,fields,report=enrich(raw,result,family,'original' if mode.startswith('Une ligne par ligne') else 'categories')
        st.session_state['export']=normalize_export(raw,result,rows,fields,report);st.session_state['export_key']=ek
    rows,fields,report,content=st.session_state['export']
except (ConversionError,ValueError) as e:st.error(str(e));st.stop()
a,b,c,d=st.columns(4)
a.metric('Lignes du FEC',report['source_rows']);b.metric('Comptes auxiliaires repris',report['accounts_promoted']);c.metric('Lignes avec lettrage conservé',report['lettered_rows']);d.metric('À rapprocher',report['unresolved'])
st.success('CompteNum et CompteLib sont les seules colonnes de compte et de libellé de compte. CompAuxNum et CompAuxLib ont été fusionnées puis supprimées de l’export.')
if report['aux_labels_missing']:st.caption(f"{report['aux_labels_missing']} auxiliaires n’ont pas de libellé : le libellé du compte général est conservé en remplacement.")
if report['unresolved']:st.warning(f"{report['unresolved']} correspondances sont ambiguës. Les ajouts concernés restent vides ; les candidats et leur analytique sont consultables ci-dessous. Aucun choix au hasard.")
if report['analytic_discrepancies']:st.caption(f"{report['analytic_discrepancies']} écarts analytiques source sont signalés. Les montants source restent inchangés ; toute correction des poids est explicite.")
st.info('À mapper impérativement dans Pennylane : Identifiant de ligne ; Poids de la catégorie ; Catégorie ; Famille de catégories (colonnes de la trame). Les répétitions partagent le même identifiant : leurs débits/crédits ne doivent pas être additionnés.')
with st.expander('Renommer les journaux et les comptes bancaires',expanded=True):
    journal_defaults,bank_defaults=mapping_tables(rows)
    st.caption('Modifie les codes et libellés cibles. Par défaut, les valeurs d’origine sont conservées. Les codes Pennylane attendus comportent au plus 5 lettres.')
    journals=st.data_editor(pd.DataFrame(journal_defaults),disabled=['Journal source'],hide_index=True,key='journals_'+key).to_dict('records')
    st.caption('Chaque remplacement de compte 512 s’applique à toutes ses occurrences, y compris les à-nouveaux et les OD. Les comptes fournisseurs/clients restent inchangés.')
    banks=st.data_editor(pd.DataFrame(bank_defaults),disabled=['Compte source','Journaux source'],hide_index=True,key='banks_'+key).to_dict('records') if bank_defaults else []
try:rows=apply_mappings(rows,journals,banks)
except ConversionError as e:st.error(str(e));st.stop()
import re
invalid_journals=sorted({r['JournalCode'] for r in rows if not re.fullmatch(r'[A-Za-z]{1,5}',r['JournalCode'])})
if invalid_journals:st.warning('Codes journaux à adapter aux codes de ton dossier Pennylane : '+', '.join(invalid_journals)+'. Aucun remplacement automatique.')
issues=weight_issues(rows)
if issues and st.checkbox('Ramener explicitement à 100 % les répartitions invalides, au prorata de leurs poids positifs',value=False,key='normalize_'+key):
    rows=normalize_invalid_weights(rows)
    issues=weight_issues(rows)
    st.caption('Poids recalculés sur demande ; montants PNM d’origine conservés pour contrôle. Les montants analytiques importés seront proportionnels au montant comptable.')
if issues:
    st.warning(f"{len({r['Identifiant'] for r in issues})} lignes source ont des répartitions incompatibles avec les poids Pennylane. Corrige les poids ci-dessous (total 1 par ligne et famille). Les montants comptables ne sont pas modifiés.")
    corrected=st.data_editor(pd.DataFrame(issues),disabled=[k for k in issues[0] if k!='Poids'],hide_index=True,key='weights_'+key+'_'+family).to_dict('records')
    for item in corrected:rows[int(item['Ligne export'])]['PoidsAnalytique']=str(item['Poids'])
    remaining=weight_issues(rows)
    if remaining:st.warning('Des poids restent invalides : le CSV reste téléchargeable pour contrôle, mais ces répartitions pourront être refusées à l’import. Aucun montant ni poids n’est corrigé arbitrairement.')
if 'JournalLib' not in fields:
    fields=list(fields);fields.insert(fields.index('JournalCode')+1,'JournalLib')
content=csv_bytes(rows,fields)
st.subheader('Lignes problématiques — rapprochements à vérifier')
review,details=ambiguity_review(result)
if review:
    st.caption(f"{len(review)} lignes ambiguës ; {sum(r['Analytique possible']=='Oui' for r in review)} avec de l’analytique parmi les candidats. Les références ci-dessous sont celles des fichiers source, avant renommage des journaux et comptes.")
    only_analytic=st.checkbox('Afficher uniquement les lignes avec analytique possible',key='review_analytic')
    review_search=st.text_input('Filtrer les problèmes : facture, pièce, compte, libellé…',key='review_search')
    filtered=[r for r in review if (not only_analytic or r['Analytique possible']=='Oui') and (not review_search or review_search.casefold() in ' '.join(str(v) for v in r.values()).casefold())]
    st.dataframe(pd.DataFrame(filtered,columns=list(review[0])),hide_index=True,width='stretch')
    st.caption(f'{len(filtered)} lignes affichées. Cette liste contient tous les résultats du filtre, sans limite de 300 lignes.')
    if filtered:
        choices={r['Ligne FEC']:f"Ligne {r['Ligne FEC']} — {r['Date']} — {r['Libellé']} — pièce {r['Pièce FEC']}" for r in filtered}
        selected=st.selectbox('Examiner les candidats PNM d’une ligne',list(choices),format_func=lambda n:choices[n],key='review_line_'+key)
        st.dataframe(pd.DataFrame(details[selected]),hide_index=True,width='stretch')
        st.caption('Une ligne par ventilation analytique candidate. Aucun candidat n’est sélectionné automatiquement. Ces détails sont réservés au contrôle dans l’app.')
else:st.success('Aucune ligne ambiguë à vérifier.')
st.subheader('Préparer la trame Pennylane')
st.write('Libellé de ligne = PieceRef du FEC. Numéro de pièce = référence de saisie PNM. Un libellé de pièce commun est repris pour toutes les lignes de la pièce. TVA et pays restent vides : aucun taux n’est inventé.')
st.caption('Les 15 colonnes de la trame sont reprises dans leur ordre. Poids de la catégorie est ajouté en dernière colonne pour les ventilations multiples. Les colonnes techniques du FEC enrichi ne sont plus mélangées à la trame.')
pieces=piece_table(rows)
qualify=st.checkbox('Distinguer les numéros PNM répétés par journal et date (exemple BQ5-20260116-1)',value=False,key='qualify_'+key)
st.caption('Décoché : numéro PNM brut, conformément à ta demande. Coché : le numéro de pièce inclut le journal et la date pour éviter les collisions. Le tableau ci-dessous conserve le numéro brut.')
with st.expander('Numéros et libellés de pièce — modifiables',expanded=True):
    st.caption('Une référence vide signifie qu’aucun numéro PNM unique n’a été identifié. Les références déduites des autres lignes de la pièce sont marquées « à vérifier ». Tu peux corriger les numéros et donner le même numéro à des groupes qui constituent réellement une même pièce.')
    pieces=st.data_editor(pd.DataFrame(pieces),disabled=[c for c in pieces[0] if c not in ['Numéro de pièce','Libellé de pièce']],hide_index=True,key='piece_editor_'+key).to_dict('records')
export_rows=template_rows(rows,pieces,qualify)
checks=validate_template(export_rows)
weights_left=weight_issues(rows)
st.subheader('Contrôles avant import')
if checks:
    st.warning(f'{len(checks)} numéros de pièce ont encore des anomalies. Le tableau donne les erreurs avant tout envoi dans Pennylane.')
    st.dataframe(pd.DataFrame(checks),hide_index=True,width='stretch')
else:st.success('Contrôles de pièce réussis : numéro renseigné, journal/date/libellé uniques et équilibre débit-crédit par pièce (hors répétitions analytiques).')
if weights_left:st.warning('Des poids analytiques restent à corriger dans le tableau des répartitions ci-dessus.')
if any(p['Référence à vérifier']=='Oui' for p in pieces):st.caption('Certaines références PNM nécessitent encore une vérification ; consulter la liste des ambiguïtés et les références à vérifier.')
st.subheader('Aperçu de la trame')
search=st.text_input('Rechercher dans la trame')
view=[r for r in export_rows if search.casefold() in ' '.join(str(v) for v in r.values()).casefold()] if search else export_rows
st.dataframe(pd.DataFrame(view[:300],columns=HEADERS),hide_index=True,width='stretch')
st.caption(f'{len(export_rows)} lignes exportées. Une ligne d’en-tête ; dates AAAAMMJJ ; CSV UTF-8, séparateur point-virgule. Mapper Identifiant de ligne et Poids de la catégorie pour éviter de doubler les montants.')
content=csv_bytes(export_rows,HEADERS)
st.download_button('Télécharger la trame — à corriger avant import' if checks or weights_left or invalid_journals else 'Télécharger la trame Pennylane',content,'PENNYLANE_ECRITURES.csv','text/csv',type='primary')
st.caption('Le fichier contient toutes les lignes, y compris celles signalées. Un téléchargement ne vaut pas validation des anomalies restantes. Le lettrage source est repris dans Identifiant de lettrage ; conserver le FEC initial pour les champs absents de la trame.')
